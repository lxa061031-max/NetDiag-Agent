"""逐个运行固定真实实验；每个任务只允许一次，失败不重试。

示例：python scripts/run_real_agent_experiment.py --task A
仅渲染已有记录：python scripts/run_real_agent_experiment.py --render
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent import AgentConfig, run_diagnosis


TASKS = {
    "A": "请告诉我当前数据集的基本情况，包括数据规模、字段和缺失值情况。",
    "B": "请分析当前网络指标，并检查是否存在异常，给出实际数据依据。",
    "C": "请根据当前检测到的网络异常分析可能原因，并检索相关故障知识给出排查建议。如果现有证据不足以确定根因，请明确说明。",
    "D": "根据当前数据，能否确定导致网络异常的唯一根因？如果不能，请说明还需要哪些额外数据，不要把可能原因描述成已确认事实。",
}
OUTPUT_DIR = ROOT / "docs" / "experiments"
RECORDS_DIR = OUTPUT_DIR / "real_agent_records" / "stage_5c"
DATA_PATH = ROOT / "data" / "demo" / "synthetic_network.csv"


def now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def render() -> None:
    lines = [
        "# 实验2：任务驱动工具选择", "", "**DeepSeek真实API运行记录**", "",
        "每个任务仅执行一次；SDK 自动重试关闭。无 Mock 响应。",
        "本表为第5C阶段新实验；历史首次记录保留在real_agent_records根目录，历史报告保存在experiment_2_agent_tool_selection_stage_5b.md。",
        "模型首次选择工具，业务完整性检查可在剩余额度内补齐明确需求；origin字段区分llm与requirement_guard。知识查询只来自实际检测指标。",
        "保留两次模型请求、最多三次工具执行。证据链仅包含公开事实与结论，不保存隐藏推理。", "",
        "| 任务 | 首次运行状态 | 实际工具顺序及执行状态 | 真实 Python 结果 | 知识来源 |",
        "|---|---|---|---|---|",
    ]
    records = []
    for task_id in TASKS:
        path = RECORDS_DIR / f"task_{task_id}.json"
        if not path.exists():
            lines.append(f"| {task_id} | 尚未运行 | — | — | — |")
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        records.append(record)
        trace = record.get("result") or record.get("trace", {})
        calls = trace.get("tool_records", [])
        tools = " → ".join(f"{item['tool']}({item['status']})" for item in calls) or "无"
        python_ok = any(item["status"] == "ok" and item["tool"] != "search_fault_knowledge" for item in calls)
        references = trace.get("evidence_chain", {}).get("knowledge_evidence", [])
        lines.append(f"| {record['task_id']} | {record['status']} | {tools} | {'有' if python_ok else '无'} | {len(references)} 条 |")
    for record in records:
        trace = record.get("result") or record.get("trace", {})
        lines += ["", f"## 任务 {record['task_id']}", "", f"用户输入：{record['task']}", "",
                  f"开始时间（北京时间）：{record['started_at']}；状态：{record['status']}。",
                  f"数据 SHA-256：`{record['data_sha256']}`；代码指纹：`{record['code_sha256']}`。",
                  f"原始结构化记录：`real_agent_records/stage_5c/task_{record['task_id']}.json`。", ""]
        if record.get("error"):
            lines += [f"首次运行错误：{record['error']}", ""]
        lines += ["### 工具输入与输出摘要", "", "```json", json.dumps([
            {key: item.get(key) for key in ("order", "tool_name", "origin", "success", "input_summary", "effective_arguments", "output_summary", "evidence_from_orders")}
            for item in trace.get("tool_records", [])
        ], ensure_ascii=False, indent=2), "```", "", "### 首次模型报告", "",
                  trace.get("report", "未返回可见报告。"), "", "### 公开证据链", "",
                  "```json", json.dumps(trace.get("evidence_chain", {}), ensure_ascii=False, indent=2), "```", ""]
    review_path = OUTPUT_DIR / "experiment_2_agent_tool_selection_stage_5c_review.md"
    if review_path.exists():
        lines += ["", review_path.read_text(encoding="utf-8")]
    report_path = OUTPUT_DIR / "experiment_2_agent_tool_selection_real.md"
    history_path = OUTPUT_DIR / "experiment_2_agent_tool_selection_stage_5b.md"
    if not history_path.exists() and report_path.exists():
        with history_path.open("x", encoding="utf-8") as stream:
            stream.write(report_path.read_text(encoding="utf-8"))
    report_path.write_text("\n".join(lines), encoding="utf-8")


def run_once(task_id: str) -> None:
    # 配置仅在进程中使用；不输出密钥或完整环境变量。
    config = AgentConfig.from_environment()
    parsed = urlparse(config.base_url)
    if parsed.scheme != "https" or parsed.hostname != "api.deepseek.com" or parsed.username or parsed.password:
        raise ValueError("真实实验仅允许安全的 DeepSeek 官方 HTTPS 地址。")
    data = pd.read_csv(DATA_PATH)
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    path = RECORDS_DIR / f"task_{task_id}.json"
    core_paths = [ROOT / "src" / "agent" / filename for filename in ("single_agent.py", "tools.py", "evidence.py", "requirements.py")]
    record = {
        "task_id": task_id, "task": TASKS[task_id], "mode": "real_api",
        "model": config.model, "started_at": now(), "status": "started",
        "data_sha256": hashlib.sha256(DATA_PATH.read_bytes()).hexdigest(),
        "code_sha256": hashlib.sha256(b"".join(item.read_bytes() for item in core_paths)).hexdigest(),
    }
    # 独占创建防止重复付费；进程中断后也不得自动再跑同一任务。
    with path.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
    trace: dict[str, object] = {}
    try:
        result = run_diagnosis(data, TASKS[task_id], config=config, execution_trace=trace)
        record.update({"status": "success", "result": result})
    except Exception as exc:
        record.update({"status": "failed", "error": f"{type(exc).__name__}: {str(exc).replace(config.api_key, '***')[:500]}", "trace": trace})
    record["finished_at"] = now()
    serialized = json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False).replace(config.api_key, "***")
    path.write_text(serialized, encoding="utf-8")
    render()
    print(f"task={task_id}; status={record['status']}; record={path.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--task", choices=list(TASKS))
    group.add_argument("--render", action="store_true")
    args = parser.parse_args()
    if args.render:
        render()
    else:
        run_once(args.task)
