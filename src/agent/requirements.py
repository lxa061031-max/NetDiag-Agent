"""轻量业务需求检查；模型仍负责第一轮自主工具选择。"""


def task_requirements(task: str) -> dict[str, object]:
    text = task.casefold()
    uncertainty = (
        any(term in text for term in ("唯一根因", "能否确定", "能否确认"))
        and any(term in text for term in ("额外数据", "补充数据", "还需要", "不能"))
    )
    explicit_knowledge = any(term in text for term in ("知识", "参考来源"))
    diagnosis = explicit_knowledge or (
        not uncertainty and any(term in text for term in ("原因", "为什么", "排查", "建议"))
    )
    required = []
    intents = []
    if not diagnosis and not uncertainty and any(term in text for term in ("规模", "字段", "缺失", "基本情况", "多少行", "概览")):
        intents.append("overview")
        required.append("get_dataset_summary")
    if not uncertainty and any(term in text for term in ("指标", "均值", "p95", "利用率")):
        intents.append("metrics")
        required.append("analyze_network_metrics")
    asks_detection = "异常" in text and any(term in text for term in ("是否", "检查", "检测", "哪些", "有没有"))
    if diagnosis or uncertainty or asks_detection:
        intents.append("uncertainty" if uncertainty and not diagnosis else "anomaly")
        required.append("detect_anomalies")
    if diagnosis:
        intents.append("diagnostic")
        required.append("search_fault_knowledge")
    return {"intents": intents, "required_tools": list(dict.fromkeys(required)), "knowledge_required": diagnosis}


def completion_status(requirements: dict[str, object], records: list[dict[str, object]]) -> dict[str, object]:
    successful = {record["tool"] for record in records if record["status"] == "ok"}
    missing = [name for name in requirements["required_tools"] if name not in successful]
    return {
        "complete": not missing,
        "missing_tools": missing,
        "message": "必需工具已执行；报告质量仍需校验。" if not missing else (
            "知识检索未完成。" if "search_fault_knowledge" in missing else "必要数据工具未完成。"
        ),
    }
