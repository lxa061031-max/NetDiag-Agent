"""跨数据源分析描述；保留原列名、原始数值和标签。"""

from __future__ import annotations

import json

import pandas as pd

from src.detection.config import DEFAULT_THRESHOLD_RULES
from .schema import build_schema_mapping


LCORE_METRICS = {
    "ICMP loss": "icmp_loss",
    "ICMP response time": "icmp_response_time",
    "U_ Bits_ received": "interface_u_receive",
    "U_ Bits_ sent": "interface_u_send",
    "B1_Bits_ received": "interface_b1_receive",
    "B1_Bits_ sent": "interface_b1_send",
    "P1_ Bits_ received": "interface_p1_receive",
    "P1_Bits _sent": "interface_p1_send",
}
SOURCE_URL = "https://data.mendeley.com/datasets/77sztrg5ks/2"


def describe_dataset(dataframe: pd.DataFrame, source_type: str | None = None, *, confirmations=None) -> dict[str, object]:
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("输入必须是DataFrame。")
    if source_type is None:
        source_type = ("lcore_r1" if {"ICMP loss", "ICMP response time"}.issubset(dataframe.columns)
                       else "synthetic" if set(DEFAULT_THRESHOLD_RULES).intersection(dataframe.columns) else "generic")
    if source_type not in {"synthetic", "lcore_r1", "generic"}:
        raise ValueError("不支持的数据源类型。")
    label_candidates = ("class", "anomaly_label", "label") if source_type == "lcore_r1" else ("anomaly_label", "class", "label")
    label = next((c for c in label_candidates if c in dataframe), None)
    timestamp = next((c for c in dataframe if str(c).casefold() in {"timestamp", "datetime", "time", "date"}
                      or pd.api.types.is_datetime64_any_dtype(dataframe[c])), None)
    numeric, categorical, unsupported = [], [], []
    for column in dataframe:
        if column in (label, timestamp):
            continue
        name = str(column)
        if source_type == "lcore_r1" and any(token in name.casefold() for token in ("status", "type", "availability", "path_up")):
            categorical.append(name)
        elif (pd.api.types.is_numeric_dtype(dataframe[column])
              and not pd.api.types.is_bool_dtype(dataframe[column])
              and not pd.api.types.is_complex_dtype(dataframe[column])):
            numeric.append(name)
        elif source_type == "lcore_r1" and name == "ICMP ping":
            unsupported.append(name)
        else:
            categorical.append(name)
    mapping = LCORE_METRICS if source_type == "lcore_r1" else {name: name for name in DEFAULT_THRESHOLD_RULES}
    selected = [name for name in mapping if name in numeric]
    schema = build_schema_mapping(dataframe, confirmations=confirmations,
                                  excluded_columns=[label, timestamp, *categorical, *unsupported])
    if source_type != "lcore_r1":
        selected = numeric[:8]
    metadata = {
        "label_semantics_verified": source_type == "synthetic" and label == "anomaly_label",
        "label_meanings": {"0": "正常模拟样本", "1": "人工注入异常模拟样本"} if source_type == "synthetic" and label == "anomaly_label" else {},
        "label_semantics_note": "标签语义尚未由官方说明确认" if source_type == "lcore_r1" else ("兼容模拟生成字段；外部CSV标签含义需人工核实" if source_type == "synthetic" else "外部标签语义未确认"),
        "source_url": SOURCE_URL if source_type == "lcore_r1" else None,
        "source_description": "GNS3仿真ISP网络公开监控数据，不是校园生产网数据" if source_type == "lcore_r1" else "根据字段识别的兼容结构；上传数据真实性和标签含义需由用户核实，不代表真实校园网络数据",
        "units_and_timestamp_timezone": "未由官方字段字典确认；不换算单位",
        "negative_values": "保留负数原值；-1编码含义未确认，可能影响统计和IQR",
        "selection_basis": "优先ICMP丢包/响应及三个接口收发量；不使用标签、时间、状态编码或拓扑字段作为检测特征。",
    }
    result = {
        "source_type": source_type,
        "dataset_name": "LCORE-D V2 R1-compatible schema" if source_type == "lcore_r1" else ("synthetic-compatible schema" if source_type == "synthetic" else "uploaded_csv"),
        "row_count": int(len(dataframe)), "numeric_columns": numeric,
        "categorical_columns": categorical, "timestamp_column": timestamp,
        "label_column": label, "metric_mapping": {name: mapping.get(name, name) for name in selected},
        "analysis_columns": selected, "unsupported_columns": unsupported,
        "metadata": metadata,
        "schema_mapping": schema,
        "semantic_columns": [item["source_column"] for item in schema if item["semantic_enabled"]],
        "generic_numeric_columns": numeric,
    }
    json.dumps(result, ensure_ascii=False, allow_nan=False)
    return result
