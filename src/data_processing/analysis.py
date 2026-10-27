"""两级分析路由，复用现有统计和IQR算法，不改写输入数据。"""

import numpy as np
import pandas as pd

from src.detection import DEFAULT_THRESHOLD_RULES, detect_anomalies
from src.tools import calculate_numeric_statistics

# 只复用现有阈值，语义和单位必须同时明确。
THRESHOLD_KEYS = {
    ("latency", "ms"): "latency_ms", ("packet_loss", "%"): "packet_loss_pct",
    ("cpu_usage", "%"): "cpu_usage_pct", ("temperature", "C"): "temperature_c",
}


def prepare_analysis(dataframe, adapter, metrics, mode="auto"):
    if mode not in {"auto", "generic", "semantic"}:
        raise ValueError("analysis_mode 必须是 auto、generic 或 semantic。")
    if not isinstance(metrics, list) or not metrics or any(not isinstance(m, str) for m in metrics):
        raise ValueError("请选择非空数值字段列表。")
    if len(set(metrics)) != len(metrics):
        raise ValueError("分析字段不能重复。")
    allowed = adapter["generic_numeric_columns"]
    if any(m not in allowed for m in metrics):
        raise ValueError("只能分析适配器识别的数值指标，不能使用标签、时间或状态编码。")
    mappings = {item["source_column"]: item for item in adapter["schema_mapping"]}
    if mode == "semantic" and any(not mappings[m]["semantic_enabled"] for m in metrics):
        raise ValueError("未确认语义的字段只能进入 Generic Analysis。")
    clean = dataframe[metrics].copy().replace([np.inf, -np.inf], np.nan)
    thresholds = {}
    for metric in metrics:
        item = mappings[metric]
        key = THRESHOLD_KEYS.get((item["canonical_name"], item["unit"]))
        # LCORE原有策略保持不变：只做原量纲IQR。
        enabled = mode != "generic" and item["semantic_enabled"] and adapter["source_type"] != "lcore_r1"
        thresholds[metric] = dict(DEFAULT_THRESHOLD_RULES[key]) if enabled and key else {}
    return clean, thresholds


def analyze_statistics(dataframe, adapter, metrics, mode="auto"):
    clean, _ = prepare_analysis(dataframe, adapter, metrics, mode)
    return calculate_numeric_statistics(clean)


def analyze_anomalies(dataframe, adapter, metrics, *, mode="auto", use_iqr=True):
    clean, thresholds = prepare_analysis(dataframe, adapter, metrics, mode)
    if not isinstance(use_iqr, bool):
        raise ValueError("use_iqr 必须是布尔值。")
    if not use_iqr and any(not rule for rule in thresholds.values()):
        raise ValueError("部分字段没有语义和单位兼容的固定阈值，必须启用IQR。")
    timestamp = adapter["timestamp_column"]
    if timestamp:
        clean["timestamp"] = dataframe[timestamp].replace([np.inf, -np.inf], np.nan)
    result = detect_anomalies(clean, thresholds=thresholds, use_iqr=use_iqr)
    result.update({
        "analysis_mode": mode,
        "fixed_threshold_fields": [name for name, rule in thresholds.items() if rule],
        "skipped_zero_iqr_metrics": [m for m in metrics if clean[m].quantile(.75) == clean[m].quantile(.25)] if use_iqr else [],
        "nonfinite_values_ignored": {m: int(np.isinf(dataframe[m].to_numpy(dtype=float, na_value=np.nan)).sum()) for m in metrics},
        "interpretation": "统计异常不等于已确认故障；未知语义/单位不使用固定专业阈值。IQR为0或有效样本不足4时不进行IQR检测，不代表健康。",
    })
    return result
