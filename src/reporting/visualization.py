"""Plotly 图表构建逻辑。"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
import plotly.graph_objects as go


def create_trend_figure(
    dataframe: pd.DataFrame,
    y_columns: Sequence[str],
    x_column: str | None = "timestamp",
) -> go.Figure:
    """创建多指标趋势图，不依赖 Streamlit。"""

    if not y_columns:
        raise ValueError("请至少选择一个数值列。")

    missing = [column for column in y_columns if column not in dataframe.columns]
    if missing:
        raise KeyError(f"趋势图字段不存在：{', '.join(missing)}")

    non_numeric = [
        column
        for column in y_columns
        if not pd.api.types.is_numeric_dtype(dataframe[column])
    ]
    if non_numeric:
        raise TypeError(f"趋势图仅支持数值列：{', '.join(non_numeric)}")

    if x_column is not None and x_column not in dataframe.columns:
        raise KeyError(f"横轴字段不存在：{x_column}")

    figure = go.Figure()
    x_values = dataframe.index if x_column is None else dataframe[x_column]
    for column in y_columns:
        figure.add_trace(
            go.Scatter(x=x_values, y=dataframe[column], mode="lines", name=column)
        )

    figure.update_layout(
        title="网络指标趋势",
        xaxis_title=x_column or "数据行序号",
        yaxis_title="指标值",
        hovermode="x unified",
        template="plotly_white",
        legend_title_text="指标",
    )
    return figure
