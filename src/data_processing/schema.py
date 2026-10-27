"""保留原始列的本地语义映射；值分布只用于否决，不用于猜测单位。"""

from __future__ import annotations

import re
from collections.abc import Mapping

import numpy as np
import pandas as pd

CANONICAL_NAMES = (
    "latency", "packet_loss", "cpu_usage", "temperature", "traffic_received",
    "traffic_sent", "jitter", "error_count", "drop_count",
)
SAFE_CONFIDENCE = 0.9
# 单位仅来自明确列名，不根据数值范围推断。LCORE 单位仍待官方确认。
EXACT_ALIASES = {
    "latency_ms": ("latency", "ms"),
    "packet_loss_pct": ("packet_loss", "%"),
    "cpu_usage_pct": ("cpu_usage", "%"),
    "temperature_c": ("temperature", "C"),
    "jitter_ms": ("jitter", "ms"),
    "error_count": ("error_count", "count"),
    "drop_count": ("drop_count", "count"),
}
STRONG_ALIASES = {
    "latency": "latency", "packet loss": "packet_loss",
    "rtt": "latency", "response time": "latency", "icmp response time": "latency",
    "loss rate": "packet_loss", "icmp loss": "packet_loss",
    "device cpu": "cpu_usage", "cpu usage": "cpu_usage",
    "temperature": "temperature", "jitter": "jitter",
    "traffic received": "traffic_received", "traffic sent": "traffic_sent",
    "bits received": "traffic_received", "bits sent": "traffic_sent",
    "errors": "error_count", "drops": "drop_count",
    "error count": "error_count", "drop count": "drop_count",
}
WEAK_ALIASES = {"delay": "latency", "loss": "packet_loss", "cpu": "cpu_usage", "temp": "temperature"}


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
