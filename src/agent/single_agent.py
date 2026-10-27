"""基于 Responses API 工具调用的低成本单 Agent。"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from types import SimpleNamespace

import pandas as pd
from dotenv import load_dotenv

from src.detection import DEFAULT_THRESHOLD_RULES
from src.data_processing.adapters import describe_dataset
from src.data_processing.schema import schema_uncertainties

from .tools import DatasetToolbox, TOOL_DEFINITIONS
from .evidence import build_evidence, summarize_tool
from .requirements import completion_status, task_requirements
from .configuration import read_llm_settings


# 允许初学者直接在项目根目录维护 .env；已有系统环境变量优先级更高。
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


MAX_TOOL_CALLS = 3
MAX_MODEL_CALLS = 2
MAX_TASK_CHARS = 2000
PLANNING_OUTPUT_TOKENS = 400
REPORT_OUTPUT_TOKENS = 2000
REQUIRED_REPORT_SECTIONS = (
    "数据分析摘要",
    "检测到的异常",
    "相关数据证据",
    "可能的故障原因",
    "建议的排查步骤",
    "无法确定的结论及其原因",
)


SYSTEM_INSTRUCTIONS = """你是 NetDiag-Agent 的校园网络诊断助手。
字段语义以dataset_adapter.schema_mapping为准：user_confirmation为人工确认，exact/strong_alias为自动映射，needs_confirmation为未确认。
Generic Analysis可统计和IQR分析未知数值字段，但不得解释为网络故障；Semantic Network Analysis只允许semantic_enabled字段。
单位未知不得猜测、换算或使用专业固定阈值；未知字段必须在不确定性中逐项说明。工具参数一律使用原始列名。
第一轮必须从提供的工具中选择 1 到 3 个工具，不能直接生成最终报告。
所有统计数字、异常数量、时间和触发规则只能来自工具结果，禁止编造。
按用户任务自主选择工具，不能固定执行全部工具：
1. 只问规模、字段、缺失值和基本情况：优先仅 get_dataset_summary，不做无关异常检测和知识检索。
2. 问指标状态、均值、P95或资源利用：analyze_network_metrics；没有异常诊断需求时不强制检索。
3. 问有无异常、异常时间或异常指标：优先 detect_anomalies，必要时结合 analyze_network_metrics。
4. 问原因、解释异常或排查建议：先选择 detect_anomalies 获取证据，再选择 search_fault_knowledge。
仅问“能否确定唯一根因、还需要哪些数据”的不确定性任务，先检测即可，不强制检索知识。
第一轮可以按这个顺序选择多个工具，由 Python 顺序执行；知识查询会结合前序真实异常指标。
每个任务最多3次工具执行，两次模型请求；第一轮一次选好必要工具，第二轮只生成报告。
如果没有足够证据，不要无限调用工具，应明确需要补充哪些数据并建议人工复核。
知识库内容只能作为参考知识，不能描述为已确认的故障根因。
最终报告必须包含：数据分析摘要、检测到的异常、相关数据证据、可能的故障原因、建议的排查步骤、无法确定的结论及其原因。
必须在相关陈述前使用“[实际检测结果]”“[参考知识]”或“[模型推测]”标签。证据不足时明确说明无法确定根因。
不要声称访问了原始 CSV、任意文件系统、命令行或互联网。"""


FINAL_REPORT_REQUEST = """工具执行已经结束。现在请只生成最终诊断报告，不要再请求工具。
必须严格使用以下六个 Markdown 二级标题，标题文字不得省略、改名或翻译：
## 数据分析摘要
## 检测到的异常
## 相关数据证据
## 可能的故障原因
## 建议的排查步骤
## 无法确定的结论及其原因
每个部分都必须有内容，整份报告控制在 800 个汉字以内。实际工具结果使用“[实际检测结果]”标注；知识检索结果使用“[参考知识]”标注并写明来源名称；原因推断使用“[模型推测]”标注。只有实际检索到知识时才能引用来源；无匹配时明确说明本地知识库无相关条目。参考知识中的可能原因不得写成已确认根因。
结合提供的统一证据结构，说明建议与实际检测证据之间的关系。当前工具不能验证因果，必须明确“无法确认根因”，列出需补充的链路利用率、接口队列/错误计数或设备日志，并建议人工复核。仅概览或统计任务应说明未执行异常检测，不得自行宣称存在异常。
固定阈值与IQR是“或”的并集，任一规则触发即可，不是必须同时满足。若is_truncated为true，明细只是返回样本，不能将样本时间范围断言为全量异常分布或持续性故障。“未调用知识检索”与“检索无匹配”是不同状态，必须准确表述。
页面会展示公开证据链：数据事实→工具检测→参考知识→模型推断→不确定性。不要输出内部思考过程。"""


class AgentConfigurationError(RuntimeError):
    """Agent API 配置缺失。"""


class AgentExecutionError(RuntimeError):
    """Agent 调用或工具循环失败。"""


@dataclass(frozen=True)
class AgentConfig:
    api_key: str = field(repr=False)
    base_url: str
    model: str

    @classmethod
    def from_environment(cls) -> "AgentConfig":
        settings = read_llm_settings()
        api_key = settings["LLM_API_KEY"]
        base_url = settings["LLM_BASE_URL"]
        model = settings["LLM_MODEL"]
        missing = [
            name
            for name, value in (
                ("LLM_API_KEY", api_key),
                ("LLM_BASE_URL", base_url),
                ("LLM_MODEL", model),
            )
            if not value
        ]
        if missing:
            raise AgentConfigurationError(
                "缺少 API 配置：" + "、".join(missing)
            )
        return cls(api_key=api_key, base_url=base_url.rstrip("/"), model=model)


def get_agent_config_status() -> dict[str, object]:
    settings = read_llm_settings()
    values = {name: bool(value) for name, value in settings.items()}
    return {
        "configured": all(values.values()),
        "variables": values,
        "model": settings["LLM_MODEL"] or None,
        "base_url": settings["LLM_BASE_URL"] or None,
    }


def _build_dataset_context(dataframe: pd.DataFrame, adapter=None) -> str:
    numeric_columns = dataframe.select_dtypes(include="number").columns.tolist()
    adapter = adapter if adapter is not None else describe_dataset(dataframe)
    supported_anomaly_metrics = adapter["analysis_columns"]
    context = {
        "row_count": int(dataframe.shape[0]),
        "column_count": int(dataframe.shape[1]),
        "fields": [str(column) for column in dataframe.columns[:100]],
        "numeric_fields": [str(column) for column in numeric_columns[:50]],
        "anomaly_rule_fields": supported_anomaly_metrics,
        "dataset_adapter": adapter,
    }
    return json.dumps(context, ensure_ascii=False)


def _create_client(config: AgentConfig) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AgentConfigurationError(
            "未安装 openai 依赖，请先运行 python -m pip install -r requirements.txt。"
        ) from exc
    return OpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
        max_retries=0,
        timeout=30.0,
    )


def _safe_api_error(exc: Exception, api_key: str) -> str:
    # 不把异常正文、HTTP响应或Header返回到公开网页。
    return "大模型 API 调用失败：模型服务暂时不可用，请稍后重试。本次不会自动重试。"


def _collect_knowledge_references(
    tool_records: list[dict[str, object]],
) -> tuple[bool, list[dict[str, object]]]:
    """从成功的知识工具结果中提取页面展示所需的可追溯条目。"""

    search_performed = False
    references: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for record in tool_records:
        if record["tool"] != "search_fault_knowledge" or record["status"] != "ok":
            continue
        search_performed = True
        tool_payload = record["result"]
        search_result = tool_payload["result"]
        for item in search_result["results"]:
            item_id = str(item["id"])
            if item_id not in seen_ids:
                references.append(item)
                seen_ids.add(item_id)
    return search_performed, references


def run_diagnosis(
    dataframe: pd.DataFrame,
    task: str,
    *,
    config: AgentConfig | None = None,
    client: Any | None = None,
    execution_trace: dict[str, object] | None = None,
    schema_confirmations: dict[str, str | None] | None = None,
) -> dict[str, object]:
    """完成一次至多三工具、两次模型请求的诊断流程。"""

    if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
        raise AgentExecutionError("当前没有可供 Agent 分析的数据。")
    if not isinstance(task, str) or not task.strip():
        raise AgentExecutionError("诊断任务不能为空。")
    if len(task.strip()) > MAX_TASK_CHARS:
        raise AgentExecutionError(f"诊断任务不能超过 {MAX_TASK_CHARS} 个字符。")

    active_config = config or AgentConfig.from_environment()
    active_client = client or _create_client(active_config)
    toolbox = DatasetToolbox(dataframe, confirmations=schema_confirmations)
    mapping_notes = schema_uncertainties(toolbox.adapter)
    lcore = toolbox.adapter["source_type"] == "lcore_r1"
    instructions = SYSTEM_INSTRUCTIONS
    if lcore:
        instructions += "\n当前为LCORE-D兼容字段的公开GNS3仿真ISP监控数据，不是校园生产网。H/F语义未获官方明确映射，不要展开为健康/故障，不计算标签指标。单位和-1编码未确认，不换算。detect_anomalies仅使用IQR，统计异常不等于故障。优先在anomaly_rule_fields的8个原字段中选择统计和检测指标，最多3工具。"
    requirements = task_requirements(task)
    input_items: list[Any] = [
        {
            "role": "user",
            "content": (
                f"用户任务：{task.strip()}\n"
                f"当前数据集元信息：{_build_dataset_context(dataframe, toolbox.adapter)}\n"
                f"明确任务要求：{json.dumps(requirements, ensure_ascii=False)}"
            ),
        }
    ]
    tool_records: list[dict[str, object]] = []
    model_records: list[dict[str, object]] = []
    if execution_trace is not None:
        execution_trace.update({"tool_records": tool_records, "model_records": model_records, "task_requirements": requirements})

    def record_response(response: Any) -> None:
        usage = getattr(response, "usage", None)
        model_records.append({
            "order": len(model_records) + 1,
            "response_id": getattr(response, "id", None),
            "status": getattr(response, "status", None),
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
        })

    try:
        first_response = active_client.responses.create(
            model=active_config.model,
            instructions=instructions,
            input=input_items,
            tools=TOOL_DEFINITIONS,
            max_output_tokens=PLANNING_OUTPUT_TOKENS,
            reasoning={"effort": "none"},
        )
    except Exception as exc:
        raise AgentExecutionError(_safe_api_error(exc, active_config.api_key)) from exc

    record_response(first_response)
    input_items.extend(first_response.output)
    function_calls = [
        item for item in first_response.output if item.type == "function_call"
    ]
    if not function_calls:
        raise AgentExecutionError("模型未选择任何分析工具，诊断流程已停止。")

    def execute_call(function_call: Any, origin: str = "llm") -> None:
        index = len(tool_records)
        if index >= MAX_TOOL_CALLS:
            tool_result = {
                "ok": False,
                "error": {
                    "type": "tool_call_limit_exceeded",
                    "message": f"每个任务最多执行 {MAX_TOOL_CALLS} 次工具。",
                },
            }
            status = "blocked"
            arguments: dict[str, object] = {}
        else:
            try:
                decoded_arguments = json.loads(function_call.arguments)
                arguments = (
                    decoded_arguments
                    if isinstance(decoded_arguments, dict)
                    else {"_invalid": decoded_arguments}
                )
            except json.JSONDecodeError:
                arguments = {"_invalid_json": function_call.arguments}
            effective_arguments = dict(arguments)
            evidence_orders: list[int] = []
            if (
                function_call.name == "search_fault_knowledge"
                and set(arguments) == {"query"}
                and isinstance(arguments.get("query"), str)
                and arguments["query"].strip()
                and len(arguments["query"]) <= 500
            ):
                detections = [record for record in tool_records if record["tool"] == "detect_anomalies" and record["status"] == "ok"]
                if detections:
                    evidence_orders = [record["order"] for record in detections]
                    metrics = list(dict.fromkeys(
                        item["metric"] for record in detections
                        for item in record["result"]["result"]["anomalies"]
                    ))
                    semantic_metrics = [m for m in metrics if m in toolbox.adapter["semantic_columns"]]
                    if metrics:
                        # 真实异常指标优先于模型提出的检索词，不接收任意路径。
                        semantics = {item["source_column"]: item["canonical_name"] for item in toolbox.adapter["schema_mapping"]}
                        concepts = {"latency": "时延", "packet_loss": "丢包", "cpu_usage": "CPU", "temperature": "温度", "traffic_received": "监控数据", "traffic_sent": "监控数据", "jitter": "抖动", "error_count": "接口错误", "drop_count": "丢弃"}
                        query_fields = [m if m in DEFAULT_THRESHOLD_RULES else m + " " + concepts[semantics[m]] for m in semantic_metrics]
                        effective_arguments["query"] = (" ".join(query_fields) + " 网络异常")[:500]
                        if lcore:
                            concepts = []
                            if any(name.startswith("ICMP loss") for name in semantic_metrics):
                                concepts.append("丢包")
                            if any(name.startswith("ICMP response time") for name in semantic_metrics):
                                concepts.append("时延")
                            if any("Bits" in name for name in semantic_metrics):
                                concepts.append("监控数据")
                            effective_arguments["query"] = (" ".join(concepts) + " " + " ".join(semantic_metrics))[:500]
                    else:
                        effective_arguments["query"] = "监控数据 证据不足"
                if not detections:
                    tool_result = {"ok": False, "error": {"type": "evidence_required", "message": "知识辅助诊断前需先成功执行 detect_anomalies。"}}
                elif (metrics and not semantic_metrics) or not any(
                    m in toolbox.adapter["semantic_columns"] for record in detections
                    for m in record["result"]["result"]["analyzed_metrics"]
                ):
                    tool_result = {"ok": False, "error": {"type": "semantic_evidence_required", "message": "检测仅涉及未知语义字段，只允许通用统计异常分析，不执行网络故障知识诊断。"}}
                else:
                    tool_result = toolbox.execute(function_call.name, effective_arguments)
            else:
                tool_result = toolbox.execute(function_call.name, arguments)
            status = "ok" if tool_result["ok"] else "error"

        tool_records.append(
            {
                "tool": function_call.name,
                "arguments": arguments,
                "status": status,
                "result": tool_result,
                "tool_name": function_call.name,
                "order": index + 1,
                "success": status == "ok",
                "input_summary": arguments,
                "effective_arguments": effective_arguments if index < MAX_TOOL_CALLS else {},
                "evidence_from_orders": evidence_orders if index < MAX_TOOL_CALLS else [],
                "output_summary": summarize_tool(function_call.name, tool_result),
                "origin": origin,
            }
        )
        if origin == "llm":
            input_items.append({
                "type": "function_call_output",
                "call_id": function_call.call_id,
                "output": json.dumps(
                    tool_result, ensure_ascii=False, allow_nan=False
                ),
            })
        else:
            input_items.append({"role": "user", "content": "任务完整性约束补充执行（真实Python结果，不是模型选择）：" + json.dumps(tool_records[-1], ensure_ascii=False, allow_nan=False)})

    for function_call in function_calls:
        execute_call(function_call)

    # 无额外模型请求：仅补齐明确要求，绝不固定执行所有工具。
    numeric_metrics = toolbox.adapter["analysis_columns"][:8]
    defaults = {
        "get_dataset_summary": {},
        "analyze_network_metrics": {"metrics": numeric_metrics},
        "detect_anomalies": {"metrics": numeric_metrics, "use_iqr": True, "max_results": 20},
        "search_fault_knowledge": {"query": "监控数据 证据不足"},
    }
    for name in requirements["required_tools"]:
        missing = completion_status(requirements, tool_records)["missing_tools"]
        if name not in missing or len(tool_records) >= MAX_TOOL_CALLS:
            continue
        execute_call(SimpleNamespace(name=name, arguments=json.dumps(defaults[name])), origin="requirement_guard")
    completion = completion_status(requirements, tool_records)
    if execution_trace is not None:
        execution_trace["task_completion"] = completion

    # 第二轮明确切换到报告生成，并给出与校验逻辑完全一致的标题模板。
    evidence = build_evidence(tool_records)
    evidence["dataset_adapter"] = toolbox.adapter
    evidence["uncertainties"].extend(mapping_notes)
    if lcore:
        evidence["dataset_adapter"] = toolbox.adapter
        evidence["uncertainties"].append("LCORE的H/F官方对应含义、单位、时间单位/时区和-1编码未确认；统计偏离不等于已确认故障。")
    evidence["task"] = {"input": task, "requirements": requirements, "completion": completion}
    if not completion["complete"]:
        evidence["uncertainties"].append(completion["message"])
    if execution_trace is not None:
        execution_trace["evidence_chain"] = evidence
    input_items.append({"role": "user", "content": "统一证据结构（仅公开事实与来源）：" + json.dumps(evidence, ensure_ascii=False, allow_nan=False)})
    input_items.append({"role": "user", "content": FINAL_REPORT_REQUEST})

    try:
        final_response = active_client.responses.create(
            model=active_config.model,
            instructions=instructions,
            input=input_items,
            max_output_tokens=REPORT_OUTPUT_TOKENS,
            reasoning={"effort": "none"},
        )
    except Exception as exc:
        raise AgentExecutionError(_safe_api_error(exc, active_config.api_key)) from exc

    record_response(final_response)
    if getattr(final_response, "status", None) == "incomplete":
        incomplete_details = getattr(final_response, "incomplete_details", None)
        reason = getattr(incomplete_details, "reason", None)
        if reason == "max_output_tokens":
            raise AgentExecutionError(
                "大模型诊断报告因达到输出长度上限而被截断，请缩短诊断任务后重试。"
            )
        raise AgentExecutionError("大模型返回了未完成的诊断报告，请稍后重试。")

    report = str(final_response.output_text or "").strip()
    if execution_trace is not None:
        execution_trace["report"] = report
    if not report:
        raise AgentExecutionError("大模型未返回诊断报告。")
    missing_sections = [
        section for section in REQUIRED_REPORT_SECTIONS if section not in report
    ]
    if missing_sections:
        raise AgentExecutionError(
            "大模型返回的诊断报告缺少必需部分：" + "、".join(missing_sections)
        )
    if "[实际检测结果]" not in report or "[模型推测]" not in report:
        raise AgentExecutionError(
            "大模型未明确区分实际检测结果与模型推测。"
        )
    knowledge_search_performed, knowledge_references = _collect_knowledge_references(
        tool_records
    )
    if knowledge_references and "[参考知识]" not in report:
        raise AgentExecutionError("大模型未将知识检索结果标注为参考知识。")
    uncertainty_section = report.split("无法确定的结论及其原因", 1)[1]
    if not re.search(r"无法(?:确认|确定|判断|判定|定位)(?:任何|具体|当前|故障|确切|真实|唯一|其)?根因", uncertainty_section):
        raise AgentExecutionError("报告未说明无法确认根因，请人工复核；本次不会自动重试。")
    if mapping_notes:
        report += "\n\n[字段适配局限] " + "；".join(mapping_notes)
    evidence = build_evidence(tool_records, report)
    evidence["dataset_adapter"] = toolbox.adapter
    evidence["uncertainties"].extend(mapping_notes)
    if lcore:
        evidence["dataset_adapter"] = toolbox.adapter
        evidence["uncertainties"].append("LCORE的H/F官方对应含义、单位、时间单位/时区和-1编码未确认；统计偏离不等于已确认故障。")
    evidence["task"] = {"input": task, "requirements": requirements, "completion": completion}
    if not completion["complete"]:
        report += "\n\n[任务完成度] " + completion["message"] + " 工具额度已用尽或执行失败，请人工复核。"
        evidence["uncertainties"].append(completion["message"])
    if execution_trace is not None:
        execution_trace["evidence_chain"] = evidence
        execution_trace["report"] = report
    return {
        "success": True,
        "mode": "real",
        "model": active_config.model,
        "model_calls": MAX_MODEL_CALLS,
        "tool_calls_executed": sum(
            record["status"] == "ok" for record in tool_records
        ),
        "tool_records": tool_records,
        "knowledge_search_performed": knowledge_search_performed,
        "knowledge_references": knowledge_references,
        "evidence_chain": evidence,
        "model_records": model_records,
        "task_requirements": requirements,
        "task_completion": completion,
        "report": report,
    }
