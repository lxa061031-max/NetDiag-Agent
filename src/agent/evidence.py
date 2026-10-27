"""公开证据整理：仅保存事实、来源和报告结论，不保存模型内部推理。"""

from __future__ import annotations

import re


def summarize_tool(tool_name: str, payload: dict[str, object]) -> dict[str, object]:
    """追踪使用短摘要，完整结果仍由原有 result 字段提供。"""
    if not payload.get("ok"):
        return {"error": payload.get("error")}
    result = payload["result"]
    fields = {
        "get_dataset_summary": ("row_count", "column_count", "missing_value_count"),
        "analyze_network_metrics": ("metrics", "statistics"),
        "detect_anomalies": ("anomaly_count", "anomalous_row_count", "analyzed_metrics", "is_truncated", "method", "interpretation", "skipped_zero_iqr_metrics"),
        "search_fault_knowledge": ("match_count", "message"),
    }.get(tool_name, ())
    return {field: result[field] for field in fields if field in result}


def build_evidence(records: list[dict[str, object]], report: str = "") -> dict[str, object]:
    evidence: dict[str, object] = {
        "observations": [], "tool_evidence": [], "knowledge_evidence": [],
        "inferences": [], "uncertainties": [],
    }
    for record in records:
        if record["status"] != "ok":
            evidence["uncertainties"].append(f"工具 {record['tool']} 未成功，不能据此形成结论。")
            continue
        tool = record["tool"]
        result = record["result"]["result"]
        if tool == "search_fault_knowledge":
            for item in result["results"]:
                evidence["knowledge_evidence"].append({
                    "id": item["id"], "title": item["title"], "source": item["source"],
                    "limitations": item["limitations"], "tool_order": record["order"],
                    "detection_orders": record.get("evidence_from_orders", []),
                    "query": record.get("effective_arguments", {}).get("query"),
                    "selection_origin": record.get("origin", "llm"),
                })
            if not result["results"]:
                evidence["uncertainties"].append("本地知识库无匹配条目，不能据此引用来源。")
        else:
            evidence["tool_evidence"].append({
                "tool": tool, "order": record["order"],
                "selection_origin": record.get("origin", "llm"),
                "result": summarize_tool(tool, record["result"]),
            })
            if tool == "get_dataset_summary":
                facts = {key: result[key] for key in ("row_count", "column_count", "missing_value_count")}
            elif tool == "analyze_network_metrics":
                facts = result["statistics"]
            else:
                facts = {key: result[key] for key in ("anomaly_count", "anomalous_row_count")}
            evidence["observations"].append({"source_tool_order": record["order"], "facts": facts})
    evidence["uncertainties"].append(
        "当前工具不验证故障因果，无法确认根因；需要异常时间对应的链路利用率、接口队列/错误计数、设备日志和拓扑信息，由人工复核。"
    )
    if report:
        # 只提取公开报告中的标注结论；不访问任何 reasoning 输出。
        evidence["inferences"] = [
            {"type": "model_inference", "text": value.strip()}
            for value in re.findall(r"\[模型推测\]([^\n]+)", report)
        ]
        section = report.split("无法确定的结论及其原因", 1)
        if len(section) == 2:
            evidence["uncertainties"].append({"type": "model_statement", "text": section[1].strip()})
    return evidence
