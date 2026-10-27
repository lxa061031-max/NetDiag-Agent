"""复现本地异常检测与知识检索实验，不调用大模型 API。"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_processing.synthetic_data import generate_synthetic_network_data
from src.detection import DEFAULT_THRESHOLD_RULES, detect_anomalies
from src.knowledge import search_fault_knowledge


DATA_PATH = ROOT / "data" / "demo" / "synthetic_network.csv"
OUTPUT_DIR = ROOT / "docs" / "experiments"
QUERIES = [
    ("网络时延明显升高应该排查什么？", "latency-high"),
    ("网络丢包率持续升高的常见原因有哪些？", "packet-loss-high"),
    ("设备CPU使用率过高可能对网络造成什么影响？", "device-high-cpu"),
    ("DNS解析失败应该如何排查？", "dns-servfail"),
    ("量子网络光源漂移如何处理？", None),
]


def row_predictions(row_count: int, anomalies: list[dict[str, object]]) -> list[int]:
    """输入为重置为 RangeIndex 的数据检测结果，按行合并多个指标。"""
    if row_count < 0:
        raise ValueError("行数不能为负。")
    predictions = [0] * row_count
    for anomaly in anomalies:
        index = anomaly["row_index"]
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < row_count:
            raise ValueError("异常行索引超出数据范围。")
        predictions[index] = 1
    return predictions


def evaluate(labels: list[int], predictions: list[int]) -> dict[str, int | float]:
    if not labels or len(labels) != len(predictions):
        raise ValueError("标签和预测必须非空且长度一致。")
    if any(value not in (0, 1) for value in labels + predictions):
        raise ValueError("标签和预测必须是二元值。")
    tp = sum(a == 1 and b == 1 for a, b in zip(labels, predictions))
    fp = sum(a == 0 and b == 1 for a, b in zip(labels, predictions))
    tn = sum(a == 0 and b == 0 for a, b in zip(labels, predictions))
    fn = sum(a == 1 and b == 0 for a, b in zip(labels, predictions))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"TP": tp, "FP": fp, "TN": tn, "FN": fn, "precision": precision, "recall": recall, "f1": f1}


def anomaly_experiment() -> str:
    raw = DATA_PATH.read_bytes()
    data = pd.read_csv(DATA_PATH).reset_index(drop=True)
    generated = generate_synthetic_network_data()
    generated["timestamp"] = generated["timestamp"].astype(str)
    if not data.equals(generated):
        raise ValueError("CSV 与固定种子生成器不一致，不能自动确认标签语义。")
    metrics = list(DEFAULT_THRESHOLD_RULES)
    labels = data["anomaly_label"].tolist()
    variants = [
        ("固定阈值", DEFAULT_THRESHOLD_RULES, False),
        ("IQR", {metric: {} for metric in metrics}, True),
        ("固定阈值 + IQR", DEFAULT_THRESHOLD_RULES, True),
    ]
    lines = ["# 实验1：行级异常检测比较", "", f"数据：`data/demo/synthetic_network.csv`；SHA-256：`{hashlib.sha256(raw).hexdigest()}`。", f"样本 {len(data)} 行；人工注入异常 {sum(labels)} 行，正常 {len(labels)-sum(labels)} 行。已与固定种子生成器完整比对一致。", "", "使用现有 `detect_anomalies`：IQR 单独运行时为相同四个指标传入空阈值字典，IQR 倍数使用现有默认值 1.5；组合方法采用两类规则的并集。任一指标触发即判为异常行。未按标签调整阈值。", "", "| 方法 | Precision | Recall | F1 | TP | FP | TN | FN |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    matrices = []
    for name, thresholds, use_iqr in variants:
        result = detect_anomalies(data, thresholds=thresholds, use_iqr=use_iqr)
        scores = evaluate(labels, row_predictions(len(data), result["anomalies"]))
        lines.append(f"| {name} | {scores['precision']:.4f} | {scores['recall']:.4f} | {scores['f1']:.4f} | {scores['TP']} | {scores['FP']} | {scores['TN']} | {scores['FN']} |")
        matrices.append(f"- {name}：`[[{scores['TN']}, {scores['FP']}], [{scores['FN']}, {scores['TP']}]]`")
    lines += ["", "混淆矩阵的行依次为实际正常、异常，列依次为预测正常、异常：", "", *matrices, ""]
    lines += ["数据是模拟网络数据，`anomaly_label` 是模拟生成过程中的人工注入标签。固定阈值 F1=1.0 来自当前模拟数据；模拟异常生成机制与固定阈值规则具有较强一致性，实验主要用于验证检测模块功能正确性和分析流程可复现性，不能推广到真实校园网络。IQR 可能将未人工注入的统计偏离点判为异常。指标分母为 0 时记为 0。", "", "复现：在项目根目录运行 `python scripts/run_experiments.py`。", ""]
    return "\n".join(lines)


def knowledge_experiment() -> str:
    lines = ["# 实验3：本地知识检索", "", "固定查询使用现有 `search_fault_knowledge` 直接运行；相关性依据预先指定的目标条目是否出现，属于简单规则检查。", "", "| 查询 | 返回条目 | 目标条目命中/无匹配正确 | 来源 |", "|---|---|---|---|"]
    valid, no_match, sourced, total = 0, False, 0, 0
    for query, expected in QUERIES:
        response = search_fault_knowledge(query)
        items = response["results"]
        hit = any(item["id"] == expected for item in items) if expected else not items
        if expected:
            valid += int(hit)
        else:
            no_match = hit and "没有匹配" in response["message"]
        names = "、".join(item["title"] for item in items) or response["message"]
        sources = []
        for item in items:
            total += 1
            source = item["source"]
            if source["name"] and source["url"]:
                sourced += 1
            sources.append(f"[{source['name']}]({source['url']})")
        lines.append(f"| {query} | {names} | {'是' if hit else '否'} | {'；'.join(sources) or '无'} |")
    lines += ["", f"查询数量：{len(QUERIES)}；4 个有目标查询中目标命中：{valid}/4；无匹配提示正确：{'是' if no_match else '否'}；来源完整率：{sourced}/{total}（{sourced / total:.1%}）。", "", "来源名称与 URL 来自知识库返回值；完整率只检查非空，不代表链接永久可访问或内容能证明现场根因。知识条目仅为排查参考，本实验未运行模型，无法验证真实报告中事实与推测的区分。", "", "复现：`python scripts/run_experiments.py`。", ""]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, content in (("experiment_1_anomaly_detection.md", anomaly_experiment()), ("experiment_3_knowledge_retrieval.md", knowledge_experiment())):
        (OUTPUT_DIR / filename).write_text(content, encoding="utf-8")
        print(f"已生成 {filename}")


if __name__ == "__main__":
    main()
