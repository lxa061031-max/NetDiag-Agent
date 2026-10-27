"""保留原始列的本地语义映射；值分布只用于否决，不用于猜测单位。"""

from __future__ import annotations

import re
from collections.abc import Mapping

import numpy as np
import pandas as pd

# 统一注册原有语义和别名，保留匹配置信度及未知单位策略。
SEMANTIC_REGISTRY = {
    "latency": {"exact": {"latency_ms": "ms"}, "strong": ("latency", "rtt", "response time", "icmp response time"), "weak": ("delay",)},
    "packet_loss": {"exact": {"packet_loss_pct": "%"}, "strong": ("packet loss", "packet loss rate", "loss rate", "icmp loss", "packet loss percentage"), "weak": ("loss",)},
    "cpu_usage": {"exact": {"cpu_usage_pct": "%"}, "strong": ("device cpu", "cpu usage", "cpu utilization"), "weak": ("cpu",)},
    "temperature": {"exact": {"temperature_c": "C"}, "strong": ("temperature",), "weak": ("temp",)},
    "traffic_received": {"exact": {}, "strong": ("traffic received", "bits received", "bytes received", "rx bytes", "rx bits"), "weak": ()},
    "traffic_sent": {"exact": {}, "strong": ("traffic sent", "bits sent", "bytes sent", "tx bytes", "tx bits"), "weak": ()},
    "jitter": {"exact": {"jitter_ms": "ms"}, "strong": ("jitter", "delay variation", "packet delay variation"), "weak": ()},
    "error_count": {"exact": {"error_count": "count"}, "strong": ("errors", "error count", "interface errors", "rx errors"), "weak": ()},
    "drop_count": {"exact": {"drop_count": "count"}, "strong": ("drops", "drop count", "interface discards", "rx dropped"), "weak": ()},
    "throughput": {"exact": {}, "strong": ("throughput", "network throughput", "data throughput", "throughput bps", "throughput mbps"), "weak": ()},
    "signal_strength": {"exact": {}, "strong": ("signal strength", "signal strength dbm", "rssi"), "weak": ()},
    "snr": {"exact": {}, "strong": ("snr", "signal to noise ratio", "snr db"), "weak": ()},
}
CANONICAL_NAMES = tuple(SEMANTIC_REGISTRY)
SAFE_CONFIDENCE = 0.9
EXACT_ALIASES = {alias: (name, unit) for name, entry in SEMANTIC_REGISTRY.items() for alias, unit in entry["exact"].items()}
STRONG_ALIASES = {alias: name for name, entry in SEMANTIC_REGISTRY.items() for alias in entry["strong"]}
WEAK_ALIASES = {alias: name for name, entry in SEMANTIC_REGISTRY.items() for alias in entry["weak"]}


def _normalize(name: str) -> str:
    return " ".join(re.sub(r"[_\W]+", " ", name.casefold()).split())


def build_schema_mapping(dataframe: pd.DataFrame, *, confirmations=None,
                         excluded_columns=()) -> list[dict[str, object]]:
    """确认只接受当前可分析数值列与白名单语义；None 表示人工保留通用。"""
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("输入必须是 DataFrame。")
    if not dataframe.columns.is_unique or any(not isinstance(c, str) for c in dataframe.columns):
        raise ValueError("字段名必须是唯一字符串。")
    confirmations = {} if confirmations is None else confirmations
    if not isinstance(confirmations, Mapping):
        raise ValueError("人工确认必须是字段到标准语义的映射。")
    eligible = {c for c in dataframe if c not in excluded_columns
                and pd.api.types.is_numeric_dtype(dataframe[c])
                and not pd.api.types.is_bool_dtype(dataframe[c])
                and not pd.api.types.is_complex_dtype(dataframe[c])}
    for name, semantic in confirmations.items():
        if name not in eligible or (semantic is not None and semantic not in CANONICAL_NAMES):
            raise ValueError("人工确认包含未知字段、非数值字段或非法标准语义。")
    rows = []
    for name in dataframe:
        canonical, unit, confidence, origin = None, None, 0.0, "unknown"
        normalized = _normalize(name)
        if name in eligible:
            if name.casefold() in EXACT_ALIASES:
                canonical, unit = EXACT_ALIASES[name.casefold()]
                confidence, origin = 1.0, "exact_alias"
            elif normalized in STRONG_ALIASES:
                canonical = STRONG_ALIASES[normalized]
                confidence, origin = 0.9, "strong_alias"
            elif normalized in WEAK_ALIASES:
                canonical = WEAK_ALIASES[normalized]
                confidence, origin = 0.6, "weak_alias"
            elif re.fullmatch(r"(?:u|b1|p1) bits (received|sent)", normalized):
                canonical = "traffic_received" if normalized.endswith("received") else "traffic_sent"
                confidence, origin = 0.9, "strong_alias"
        finite = pd.to_numeric(dataframe[name], errors="coerce") if name in eligible else pd.Series(dtype=float)
        finite = finite.replace([np.inf, -np.inf], np.nan).dropna()
        warnings = []
        if canonical and (finite.empty or (
            unit == "%" and not finite.between(0, 100).all()
        ) or (unit in {"ms", "count"} and (finite < 0).any())):
            confidence = min(confidence, 0.6)
            warnings.append("值分布与已声明单位不一致或无有效数值，请复核；不自动换算。")
        if name in confirmations:
            canonical = confirmations[name]
            confidence, origin = (1.0 if canonical else 0.0), "user_confirmation"
            # 选择语义不等于确认单位；改成另一语义时原单位不再适用。
            if name.casefold() not in EXACT_ALIASES or EXACT_ALIASES[name.casefold()][0] != canonical:
                unit = None
        semantic_enabled = name in eligible and canonical is not None and confidence >= SAFE_CONFIDENCE
        rows.append({
            "source_column": name, "dtype": str(dataframe[name].dtype),
            "canonical_name": canonical, "unit": unit, "confidence": confidence,
            "mapping_source": origin,
            "needs_confirmation": name in eligible and not semantic_enabled and origin != "user_confirmation",
            "semantic_enabled": semantic_enabled,
            "analysis_type": "semantic_network" if semantic_enabled else ("generic_numeric" if name in eligible else "non_metric"),
            "warnings": warnings,
        })
    return rows


def schema_uncertainties(adapter: dict) -> list[str]:
    notes = []
    for item in adapter["schema_mapping"]:
        if item["analysis_type"] == "generic_numeric":
            notes.append(f"字段 {item['source_column']} 单位和语义尚未确认（或选择保持通用），仅进行统计与IQR分析，不使用网络专业阈值或故障解释。")
        elif item["semantic_enabled"] and item["unit"] is None:
            notes.append(f"字段 {item['source_column']} 已映射为 {item['canonical_name']}，但单位尚未确认，不使用固定专业阈值。")
    return notes
