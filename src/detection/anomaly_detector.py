"""可解释的固定阈值与 IQR 异常检测。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from .config import DEFAULT_THRESHOLD_RULES


ThresholdRules = Mapping[str, Mapping[str, float]]


def _json_value(value: Any) -> int | float | str | bool | None:
    """将常见 Pandas/NumPy 标量转换为 JSON 兼容值。"""

    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (int, float, str, bool)):
        return value
    return str(value)


def detect_anomalies(
    dataframe: pd.DataFrame,
    thresholds: ThresholdRules | None = None,
    *,
    use_iqr: bool = True,
    iqr_multiplier: float = 1.5,
) -> dict[str, object]:
    """按集中阈值和可选 IQR 规则检测异常，返回 JSON 兼容结果。"""

    if iqr_multiplier <= 0:
        raise ValueError("iqr_multiplier 必须大于 0。")

    active_thresholds = DEFAULT_THRESHOLD_RULES if thresholds is None else thresholds
    result: dict[str, object] = {
        "anomaly_count": 0,
        "anomalous_row_count": 0,
        "analyzed_metrics": [],
        "missing_metrics": [],
        "anomalies": [],
    }
    if dataframe.empty:
        return result

    numeric_values: dict[str, pd.Series] = {}
    iqr_bounds: dict[str, tuple[float, float]] = {}
    analyzed_metrics: list[str] = []
    missing_metrics: list[str] = []

    for metric in active_thresholds:
        if metric not in dataframe.columns:
            missing_metrics.append(metric)
            continue

        values = pd.to_numeric(dataframe[metric], errors="coerce")
        if values.notna().sum() == 0:
            missing_metrics.append(metric)
            continue

        numeric_values[metric] = values
        analyzed_metrics.append(metric)
        if use_iqr and values.notna().sum() >= 4:
            first_quartile = float(values.quantile(0.25))
            third_quartile = float(values.quantile(0.75))
            iqr = third_quartile - first_quartile
            if iqr > 0:
                iqr_bounds[metric] = (
                    first_quartile - iqr_multiplier * iqr,
                    third_quartile + iqr_multiplier * iqr,
                )

    anomalies: list[dict[str, object]] = []
    anomalous_positions: set[int] = set()
    timestamp_available = "timestamp" in dataframe.columns
    for position, (row_index, row) in enumerate(dataframe.iterrows()):
        for metric in analyzed_metrics:
            value = numeric_values[metric].iloc[position]
            if pd.isna(value):
                continue

            triggered_rules: list[str] = []
            explanations: list[str] = []
            rule = active_thresholds[metric]
            minimum = rule.get("min")
            maximum = rule.get("max")

            if minimum is not None and value < minimum:
                triggered_rules.append(f"固定阈值: < {minimum:g}")
                explanations.append(f"低于下限 {minimum:g}，差值 {minimum - value:.2f}")
            if maximum is not None and value > maximum:
                triggered_rules.append(f"固定阈值: > {maximum:g}")
                explanations.append(f"高于上限 {maximum:g}，差值 {value - maximum:.2f}")

            if metric in iqr_bounds:
                lower_bound, upper_bound = iqr_bounds[metric]
                if value < lower_bound:
                    triggered_rules.append("IQR 下界")
                    explanations.append(
                        f"低于 IQR 下界 {lower_bound:.2f}，差值 {lower_bound - value:.2f}"
                    )
                elif value > upper_bound:
                    triggered_rules.append("IQR 上界")
                    explanations.append(
                        f"高于 IQR 上界 {upper_bound:.2f}，差值 {value - upper_bound:.2f}"
                    )

            if triggered_rules:
                anomalous_positions.add(position)
                anomalies.append(
                    {
                        "row_index": _json_value(row_index),
                        "timestamp": (
                            _json_value(row["timestamp"])
                            if timestamp_available
                            else None
                        ),
                        "metric": metric,
                        "value": float(value),
                        "trigger_rule": "；".join(triggered_rules),
                        "explanation": "；".join(explanations),
                    }
                )

    result.update(
        {
            "anomaly_count": len(anomalies),
            "anomalous_row_count": len(anomalous_positions),
            "analyzed_metrics": analyzed_metrics,
            "missing_metrics": missing_metrics,
            "anomalies": anomalies,
        }
    )
    return result
