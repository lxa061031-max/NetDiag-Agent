"""把已确认字段映射转换为可追溯的标准语义标签和值视图。"""

from __future__ import annotations

import json

import pandas as pd


SEMANTIC_VALUE_COLUMNS = (
    "row_index",
    "timestamp",
    "source_column",
    "semantic_label",
    "value",
    "unit",
    "confidence",
    "mapping_source",
)


def build_semantic_label_map(schema_mapping: list[dict[str, object]]) -> list[dict[str, object]]:
    """为高置信度字段生成稳定标签；未知字段不强制语义化。"""

    if not isinstance(schema_mapping, list):
        raise TypeError("schema_mapping必须是列表。")
    labels = []
    for item in schema_mapping:
        if item.get("semantic_enabled") and item.get("canonical_name"):
            labels.append(
                {
                    "source_column": str(item["source_column"]),
                    "semantic_label": str(item["canonical_name"]),
                    "unit": item.get("unit"),
                    "confidence": float(item["confidence"]),
                    "mapping_source": str(item["mapping_source"]),
                }
            )
    json.dumps(labels, ensure_ascii=False, allow_nan=False)
    return labels


def build_semantic_value_frame(
    dataframe: pd.DataFrame,
    adapter: dict[str, object],
    *,
    source_row_limit: int | None = None,
) -> pd.DataFrame:
    """生成长表标签值视图，保留原字段名并允许多个字段映射同一语义。"""

    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("输入必须是DataFrame。")
    if source_row_limit is not None and (not isinstance(source_row_limit, int) or source_row_limit <= 0):
        raise ValueError("source_row_limit必须是正整数或None。")
    label_map = build_semantic_label_map(adapter.get("schema_mapping", []))
    if not label_map:
        return pd.DataFrame(columns=SEMANTIC_VALUE_COLUMNS)
    source = dataframe.head(source_row_limit) if source_row_limit is not None else dataframe
    timestamp_column = adapter.get("timestamp_column")
    frames = []
    for label in label_map:
        column = label["source_column"]
        if column not in source.columns:
            continue
        frame = pd.DataFrame(
            {
                "row_index": source.index.map(str),
                "timestamp": source[timestamp_column].astype("string") if timestamp_column in source.columns else None,
                "source_column": column,
                "semantic_label": label["semantic_label"],
                "value": pd.to_numeric(source[column], errors="coerce"),
                "unit": label["unit"],
                "confidence": label["confidence"],
                "mapping_source": label["mapping_source"],
            }
        )
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=SEMANTIC_VALUE_COLUMNS)
    result = pd.concat(frames, ignore_index=True)
    return result.loc[:, SEMANTIC_VALUE_COLUMNS]
