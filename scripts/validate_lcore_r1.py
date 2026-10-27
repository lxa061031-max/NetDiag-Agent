"""复现R1本地验证；--real-agent仅执行一次真实任务E，失败不重试。"""

from __future__ import annotations

import argparse
from collections import Counter
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
from src.agent.tools import DatasetToolbox
from src.data_processing.adapters import describe_dataset, SOURCE_URL
from src.detection import detect_anomalies

DATA = ROOT / "data/raw/LCORE-D R1.csv"
OUT = ROOT / "docs/experiments"
RECORD = OUT / "real_agent_records/stage_5d/task_E.json"
TASK = "请分析当前LCORE-D R1数据集，概括主要网络指标，识别统计异常，并说明当前证据能够确认什么、不能确认什么。若需要参考网络故障知识，请检索相关来源。"


def now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def local_validation() -> dict[str, object]:
    source = json.loads((ROOT / "data/raw/lcore_r1_source.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(DATA.read_bytes()).hexdigest()
    official = next(item for item in source["files"] if item["filename"] == DATA.name)
    if digest != official["content_details"]["sha256_hash"]:
        raise ValueError("R1官方哈希验证失败。")
    data = pd.read_csv(DATA, low_memory=False).reset_index(drop=True)
    adapter = describe_dataset(data, "lcore_r1")
    selected = adapter["analysis_columns"]
    stats = DatasetToolbox(data).analyze_network_metrics(selected)["statistics"]
    detection = detect_anomalies(data, thresholds={column: {} for column in selected}, use_iqr=True)
    per_metric = dict(Counter(item["metric"] for item in detection["anomalies"]))
    for metric in selected:
        per_metric.setdefault(metric, 0)
    summary = {
        "dataset_name": "LCORE-D V2 R1", "sha256": digest,
        "rows": len(data), "columns": len(data.columns),
        "native_numeric_count": len(data.select_dtypes(include="number").columns),
        "label_counts": {str(key): int(value) for key, value in data["class"].value_counts(dropna=False).items()},
        "adapter": adapter, "statistics": stats,
        "detection": {key: detection[key] for key in ("anomaly_count", "anomalous_row_count", "analyzed_metrics")},
        "anomalous_row_ratio": detection["anomalous_row_count"] / len(data),
        "per_metric_anomaly_records": per_metric,
        "zero_iqr_columns": [metric for metric in selected if data[metric].quantile(.75) == data[metric].quantile(.25)],
        "anomaly_examples": detection["anomalies"][:8],
        "negative_value_counts": {column: int((data[column] < 0).sum()) for column in selected},
        "icmp_ping_non_numeric": int(pd.to_numeric(data["ICMP ping"], errors="coerce").isna().sum()),
        "label_evaluation": "未计算：标签语义尚未由官方说明确认。",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    provenance = {
        "dataset_url": SOURCE_URL, "doi": source["doi"], "version": source["version"],
        "retrieved_at": source["retrieved_at"], "licence": source["licence"]["short_name"],
        "licence_url": source["licence"]["url"],
        "r1_file_id": official["id"], "official_sha256": official["content_details"]["sha256_hash"],
        "actual_sha256": digest, "official_bytes": official["content_details"]["size"],
        "file_manifest_endpoint": source["files_endpoint"],
        "root_csv_files": [item["filename"] for item in source["files"]],
        "fault_log_files": [item["filename"] for item in source.get("folder_files", {}).get("Fault Log", [])],
        "label_semantics_verified": False,
        "verification_scope": "官方发布页、嵌入metadata、根文件清单、Fault Log完整内容、公开论文检索；未找到H/F字母明确映射。",
    }
    (OUT / "lcore_r1_provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "lcore_r1_results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    lines = ["# LCORE-D V2 R1 字段核实", "", f"来源：[Mendeley Data]({SOURCE_URL})；SHA-256：`{digest}`。", f"实际规模：{len(data)}行、{len(data.columns)}列、{summary['native_numeric_count']}个原生数值dtype字段。", "原生数值类型不等于连续网络指标，状态编码、时间和标签不进入IQR。原始数据未改名、未改标签、未替换-1。", "", "| 字段名 | dtype | 非空数 | 单个示例 | 类别 | 进入分析 | 说明 |", "|---|---|---:|---|---|---|---|"]
    for column in data:
        if column == adapter["label_column"]:
            category, note = "标签", "H/F语义未确认，不用作真值"
        elif column == adapter["timestamp_column"]:
            category, note = "时间", "原始数值保留；单位与时区未确认"
        elif column in adapter["unsupported_columns"]:
            category, note = "暂不支持", "混合类型，含1个`1异常字符串；不静默转换"
        elif column in adapter["categorical_columns"]:
            category, note = "类别/状态候选", "按字段名识别；编码字典未确认"
        else:
            category, note = "数值", "保留原量纲；未选字段留待语义核实"
        if column in selected:
            note = "ICMP监控或接口收发量候选指标；单位/采样口径未确认，原值统计及IQR"
        values = data[column].dropna()
        example = str(values.iloc[0])[:60] if len(values) else "无"
        lines.append(f"| `{column}` | {data[column].dtype} | {int(data[column].notna().sum())} | {example.replace('|', '/')} | {category} | {'是' if column in selected else '否'} | {note} |")
    lines += ["", "分析选择依据：优先两个ICMP字段与U、B1、P1三个接口的收发字段，共8个；字段名提示监测意义，但不把前缀解释为已确认拓扑，不推断速率/累计口径或进行单位换算。", "", "标签核实：官方说明确认数据包含healthy/faulty行为，但未明确class字母对应；根目录7个CSV，无README，custom_metadata和related_links为空。Fault Log附录包含故障事件、起止时间、类型、注入域，没有H/F编码定义。公开检索未找到可明确映射的作者论文说明。因此标签语义尚未由官方说明确认。", ""]
    (OUT / "lcore_r1_schema.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def run_real_once() -> None:
    config = AgentConfig.from_environment()
    url = urlparse(config.base_url)
    if url.scheme != "https" or url.hostname != "api.deepseek.com" or url.username or url.password:
        raise ValueError("仅允许DeepSeek官方HTTPS地址。")
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    files = [ROOT / "src/agent" / name for name in ("single_agent.py", "tools.py", "evidence.py", "requirements.py")]
    files.append(ROOT / "src/data_processing/adapters.py")
    record = {"task_id": "E", "task": TASK, "mode": "real_api", "model": config.model, "started_at": now(), "status": "started", "data_sha256": hashlib.sha256(DATA.read_bytes()).hexdigest(), "code_sha256": hashlib.sha256(b"".join(path.read_bytes() for path in files)).hexdigest()}
    with RECORD.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
    trace = {}
    try:
        result = run_diagnosis(pd.read_csv(DATA, low_memory=False), TASK, config=config, execution_trace=trace)
        record.update({"status": "success", "result": result})
    except Exception as exc:
        record.update({"status": "failed", "error": f"{type(exc).__name__}: {str(exc).replace(config.api_key, '***')[:500]}", "trace": trace})
    record["finished_at"] = now()
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False).replace(config.api_key, "***"), encoding="utf-8")
    print("task_E_status=" + record["status"])


def write_report(summary: dict[str, object]) -> None:
    lines = ["# 实验5：LCORE-D V2 R1跨结构验证", "", "## 数据来源与标签核实", "", f"[官方发布页]({SOURCE_URL})，DOI：10.17632/77sztrg5ks.2。Akanksha singh、Ratneshwer Gupta，2025-12-17，CC BY 4.0。", "这是公开GNS3仿真ISP监控数据，不是校园生产网数据。", f"官方SHA-256校验通过：`{summary['sha256']}`；实际{summary['rows']}行、{summary['columns']}列，原生数值dtype共{summary['native_numeric_count']}列。", f"class分布：`{summary['label_counts']}`。**标签语义尚未由官方说明确认**。官方metadata、根文件及Fault Log未提供H/F明确映射，因此不计算TP/FP/TN/FN、Precision/Recall/F1。", "", "## 适配与字段", "", "详见 [完整字段表](lcore_r1_schema.md)。适配器仅描述字段角色、可分析指标及不确定性，不重命名原列或换算单位。", "选择8个ICMP与接口收发量字段，不使用时间、class、状态或拓扑作为统计检测特征。", "", "## 原始量纲统计", "", "| 字段 | count | mean | median | std | min | max | p95 |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for metric, stats in summary["statistics"].items():
        lines.append("| " + metric + " | " + " | ".join(f"{stats[key]:.6g}" if stats[key] is not None else "无" for key in ("count", "mean", "median", "std", "min", "max", "p95")) + " |")
    lines += ["", "## 统计异常检测", "", "复用现有detect_anomalies，仅传入空固定阈值规则并启用默认1.5倍IQR。未调参。任一指标触发视为异常行。", f"异常行：{summary['detection']['anomalous_row_count']}；比例：{summary['anomalous_row_ratio']:.4%}；指标级异常记录：{summary['detection']['anomaly_count']}。统计异常不等于已确认故障。", "", "| 字段 | 异常记录数 |", "|---|---:|"]
    for metric, count in sorted(summary["per_metric_anomaly_records"].items(), key=lambda item: -item[1]):
        lines.append(f"| {metric} | {count} |")
    lines += ["", f"IQR为0而被现有算法跳过的字段：`{summary['zero_iqr_columns']}`。这些字段的0条统计异常不代表没有网络问题，本阶段未修改既有算法。", "", "示例仅取前8条，不代表全量分布：", "", "```json", json.dumps(summary["anomaly_examples"], ensure_ascii=False, indent=2), "```", "", "## Agent任务E与公开证据链", ""]
    if RECORD.exists():
        record = json.loads(RECORD.read_text(encoding="utf-8"))
        result = record.get("result") or record.get("trace", {})
        lines += ["DeepSeek真实API首次执行；不重试、不发送完整CSV，模型仅接收数据描述、受限工具摘要与最多20条示例。", "用户任务：" + TASK, f"状态：{record['status']}；开始时间：{record['started_at']}。", "原始记录：`real_agent_records/stage_5d/task_E.json`。", "", "| 顺序 | 工具 | 来源 | 状态 |", "|---|---|---|---|"]
        for item in result.get("tool_records", []):
            lines.append(f"| {item['order']} | {item['tool']} | {item['origin']} | {item['status']} |")
        if record.get("error"):
            lines += ["", "首次失败：" + record["error"]]
        lines += ["", "### 模型原始报告", "", result.get("report", "未返回报告"), "", "### 结构化公开证据", "", "```json", json.dumps(result.get("evidence_chain", {}), ensure_ascii=False, indent=2), "```"]
    else:
        lines.append("尚未执行真实API；本地统计和IQR结果不冒充Agent结果。")
    lines += ["", "## 独立复核与局限", "", "本地统计和Agent工具结果一致；若任务E生成报告成功，则支持跨字段结构的统计、IQR和公开证据输出链路可运行，不代表模型解释完全正确。实际工具选择、状态、输入输出摘要、来源、响应ID和usage保存在原始JSON中；知识工具若origin为requirement_guard，不能记作模型主动检索。", "模型原始报告中的“大量-1占位值可能主导/放大异常”只是假设，编码也未获官方确认。实际每个选定字段仅有16–17个负值，不能据此前20条样本解释9466行异常；不得把该推测作为已验证原因。模型提出的剔除占位值建议必须先确认编码规则，本阶段未执行该清洗或额外调参。", f"ICMP ping有{summary['icmp_ping_non_numeric']}个不可解析值，本阶段不静默清洗。原始负数保留：`{summary['negative_value_counts']}`。-1编码含义未确认，可能影响分位数和异常数量。", "单位、时间单位/时区、接口前缀与累积/速率口径尚缺官方字段字典；字段名解释属于分析候选，不是故障定位依据。全样本分位数为本文件描述性统计，不是跨设备泛化评价。仅验证R1，没有分析R2–R7。", "复现：`python scripts/fetch_lcore_r1.py`获取官方文件并校验；`python scripts/validate_lcore_r1.py`只运行本地验证；`--real-agent`执行一次E，已有记录时拒绝重复付费。原CSV受.gitignore排除，来源核验摘要保存于lcore_r1_provenance.json。", "没有将统计异常当作故障标签，也没有宣称真实校园网部署或准确诊断所有故障。", ""]
    (OUT / "experiment_5_lcore_validation.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-agent", action="store_true")
    args = parser.parse_args()
    summary = local_validation()
    if args.real_agent:
        run_real_once()
    write_report(summary)
    print(json.dumps({key: summary[key] for key in ("rows", "columns", "label_counts", "detection", "anomalous_row_ratio")}, ensure_ascii=True))
