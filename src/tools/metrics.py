"""网络数值指标的基础统计工具。"""

from __future__ import annotations

import math

import pandas as pd


def _json_number(value: float) -> float | None:
    """将 Pandas/NumPy 数值转换为 JSON 兼容的 Python 数值。"""

    number = float(value)
    return number if math.isfinite(number) else None


def calculate_numeric_statistics(
    dataframe: pd.DataFrame,
) -> dict[str, dict[str, int | float | None]]:
    """计算数值列统计量；非数值列被忽略，空数据返回空字典。"""

    if dataframe.empty:
        return {}

    statistics: dict[str, dict[str, int | float | None]] = {}
    for column in dataframe.select_dtypes(include="number").columns:
        values = dataframe[column].dropna()
        count = int(values.count())
        statistics[column] = {
            "count": count,
            "mean": _json_number(values.mean()) if count else None,
            "min": _json_number(values.min()) if count else None,
            "max": _json_number(values.max()) if count else None,
            "std": _json_number(values.std()) if count > 1 else None,
            "median": _json_number(values.median()) if count else None,
            "p95": _json_number(values.quantile(0.95)) if count else None,
        }
    return statistics
