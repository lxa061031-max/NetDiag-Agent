"""仅面向当前内存数据集的 Agent 分析工具。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pandas as pd

from src.data_processing import build_data_summary
from src.data_processing.adapters import describe_dataset
from src.data_processing.analysis import analyze_statistics, analyze_anomalies
from src.detection.config import detection_config
from src.knowledge import (
    MAX_KNOWLEDGE_QUERY_CHARS,
    search_fault_knowledge as run_knowledge_search,
)


MAX_METRICS_PER_CALL = 8
MAX_ANOMALIES_PER_CALL = 20


class ToolValidationError(ValueError):
    """工具参数不符合安全约束。"""


TOOL_DEFINITIONS: list[dict[str, object]] = [
    {
        "type": "function",
        "name": "get_dataset_summary",
        "description": "获取当前已加载数据集的行数、列数、字段类型和缺失值情况。",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "analyze_network_metrics",
        "description": "计算当前数据集中指定数值字段的 count、mean、min、max、std、median 和 p95。",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": MAX_METRICS_PER_CALL,
                    "description": "需要分析的数值字段名。",
                }
            },
            "required": ["metrics"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "detect_anomalies",
        "description": "使用现有固定阈值和可选 IQR 规则检测当前数据集中的异常。",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 8,
                    "description": "当前数据源支持的指标名；LCORE仅原始量纲IQR，不使用模拟固定阈值。",
                },
                "use_iqr": {
                    "type": "boolean",
                    "description": "是否同时使用 IQR 统计规则。",
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_ANOMALIES_PER_CALL,
                    "description": "返回给模型的异常明细上限。",
                },
            },
            "required": ["metrics", "use_iqr", "max_results"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_fault_knowledge",
        "description": (
            "当任务需要解释可能原因或给出排查建议时，按用户任务、异常指标或检测现象"
            "检索本地网络故障知识；应在 detect_anomalies 成功之后调用。"
            "查询会结合已检测的真实异常指标；纯统计任务不必调用。"
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": MAX_KNOWLEDGE_QUERY_CHARS,
                    "description": "用于检索的简短故障现象、异常指标和任务关键词。",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
]

# 保持原工具名称和旧调用兼容；模型可明确选择通用或语义分析。
for _definition in TOOL_DEFINITIONS:
    if _definition["name"] in {"analyze_network_metrics", "detect_anomalies"}:
        _definition["parameters"]["properties"]["analysis_mode"] = {
            "type": "string", "enum": ["auto", "generic", "semantic"],
            "description": "generic仅统计/IQR；semantic要求字段语义可靠；auto逐字段安全路由。使用原始列名，未知单位禁止固定阈值。",
        }
        _definition["parameters"]["required"].append("analysis_mode")


def _validate_exact_arguments(
    arguments: Mapping[str, Any], expected_keys: set[str]
) -> None:
    if not isinstance(arguments, Mapping):
        raise ToolValidationError("工具参数必须是 JSON 对象。")
    actual_keys = set(arguments)
    if actual_keys != expected_keys:
        raise ToolValidationError(
            f"参数字段必须为 {sorted(expected_keys)}，实际为 {sorted(actual_keys)}。"
        )


class DatasetToolbox:
    """封装当前 DataFrame，禁止工具接收路径或执行外部操作。"""

    def __init__(self, dataframe: pd.DataFrame, *, confirmations=None, settings=None) -> None:
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("dataframe 必须是 pandas.DataFrame。")
        self._dataframe = dataframe
        self.adapter = describe_dataset(dataframe, confirmations=confirmations)
        self.settings = detection_config(settings)

    def get_dataset_summary(self) -> dict[str, object]:
        summary = build_data_summary(self._dataframe)
        row_count = int(summary["row_count"])
        fields = []
        for column in self._dataframe.columns:
            missing_count = int(self._dataframe[column].isna().sum())
            fields.append(
                {
                    "name": str(column),
                    "dtype": str(self._dataframe[column].dtype),
                    "missing_count": missing_count,
                    "missing_pct": (
                        round(missing_count / row_count * 100, 4)
                        if row_count
                        else None
                    ),
                }
            )
        return {
            "row_count": row_count,
            "column_count": int(summary["column_count"]),
            "missing_value_count": int(summary["missing_value_count"]),
            "numeric_columns": list(summary["numeric_columns"]),
            "fields": fields,
            "dataset_adapter": self.adapter,
        }

    def analyze_network_metrics(self, metrics: list[str], analysis_mode: str = "auto") -> dict[str, object]:
        allowed = set(self.adapter["analysis_columns"]) if self.adapter["source_type"] == "lcore_r1" and analysis_mode == "auto" else None
        validated_metrics = self._validate_metrics(metrics, numeric_only=True, allowed_metrics=allowed)
        statistics = analyze_statistics(self._dataframe, self.adapter, validated_metrics, analysis_mode)
        return {"metrics": validated_metrics, "statistics": statistics, "analysis_mode": analysis_mode}

    def detect_anomalies(
        self, metrics: list[str], use_iqr: bool, max_results: int, analysis_mode: str = "auto"
    ) -> dict[str, object]:
        lcore = self.adapter["source_type"] == "lcore_r1"
        allowed = set(self.adapter["analysis_columns"]) if lcore and analysis_mode == "auto" else None
        validated_metrics = self._validate_metrics(metrics, allowed_metrics=allowed, numeric_only=True)
        if not isinstance(use_iqr, bool):
            raise ToolValidationError("use_iqr 必须是布尔值。")
        if (
            isinstance(max_results, bool)
            or not isinstance(max_results, int)
            or not 1 <= max_results <= MAX_ANOMALIES_PER_CALL
        ):
            raise ToolValidationError(
                f"max_results 必须是 1 到 {MAX_ANOMALIES_PER_CALL} 的整数。"
            )

        if lcore and not use_iqr:
            raise ToolValidationError("LCORE-R1只支持现有IQR统计检测，请设置use_iqr=true。")
        detection = analyze_anomalies(self._dataframe, self.adapter, validated_metrics, mode=analysis_mode, use_iqr=use_iqr, settings=self.settings)
        anomalies = list(detection["anomalies"])
        result = {
            "anomaly_count": int(detection["anomaly_count"]),
            "anomalous_row_count": int(detection["anomalous_row_count"]),
            "analyzed_metrics": list(detection["analyzed_metrics"]),
            "anomalies_returned": min(len(anomalies), max_results),
            "is_truncated": len(anomalies) > max_results,
            "anomalies": anomalies[:max_results],
            "analysis_mode": analysis_mode,
            "fixed_threshold_fields": detection["fixed_threshold_fields"],
            "detection_config": detection["detection_config"],
            "interpretation": detection["interpretation"],
            "nonfinite_values_ignored": detection["nonfinite_values_ignored"],
            "skipped_zero_iqr_metrics": detection["skipped_zero_iqr_metrics"],
        }
        if lcore:
            result.update({"method": f"IQR only; multiplier={self.settings['iqr_multiplier']:g}", "interpretation": "统计异常不等于已确认故障；原值保留，单位/-1编码和H/F语义未确认。IQR为0时现有算法跳过该字段，不表示健康。"})
        return result

    def search_fault_knowledge(self, query: object) -> dict[str, object]:
        if not self.adapter["semantic_columns"]:
            raise ToolValidationError("没有已确认或高置信度网络语义，不能对未知字段进行专业故障知识诊断。")
        return run_knowledge_search(query)

    def execute(self, tool_name: str, arguments: Mapping[str, Any]) -> dict[str, object]:
        """验证并执行一个已注册工具，所有错误都转换为 JSON 结果。"""

        try:
            if tool_name == "get_dataset_summary":
                _validate_exact_arguments(arguments, set())
                result = self.get_dataset_summary()
            elif tool_name == "analyze_network_metrics":
                _validate_exact_arguments(arguments, {"metrics", "analysis_mode"} if isinstance(arguments, Mapping) and "analysis_mode" in arguments else {"metrics"})
                result = self.analyze_network_metrics(arguments["metrics"], arguments.get("analysis_mode", "auto"))
            elif tool_name == "detect_anomalies":
                _validate_exact_arguments(
                    arguments, {"metrics", "use_iqr", "max_results", "analysis_mode"} if isinstance(arguments, Mapping) and "analysis_mode" in arguments else {"metrics", "use_iqr", "max_results"}
                )
                result = self.detect_anomalies(
                    arguments["metrics"],
                    arguments["use_iqr"],
                    arguments["max_results"],
                    arguments.get("analysis_mode", "auto"),
                )
            elif tool_name == "search_fault_knowledge":
                _validate_exact_arguments(arguments, {"query"})
                result = self.search_fault_knowledge(arguments["query"])
            else:
                return {
                    "ok": False,
                    "error": {
                        "type": "unknown_tool",
                        "message": f"未知工具：{tool_name}",
                    },
                }
        except (KeyError, TypeError, ToolValidationError, ValueError) as exc:
            return {
                "ok": False,
                "error": {
                    "type": "invalid_parameters",
                    "message": str(exc),
                },
            }

        payload = {"ok": True, "result": result}
        json.dumps(payload, ensure_ascii=False, allow_nan=False)
        return payload

    def _validate_metrics(
        self,
        metrics: object,
        *,
        numeric_only: bool = False,
        allowed_metrics: set[str] | None = None,
        maximum: int = MAX_METRICS_PER_CALL,
    ) -> list[str]:
        if not isinstance(metrics, list) or not metrics:
            raise ToolValidationError("metrics 必须是非空字符串列表。")
        if len(metrics) > maximum:
            raise ToolValidationError(f"单次最多分析 {maximum} 个指标。")
        if any(not isinstance(metric, str) or not metric.strip() for metric in metrics):
            raise ToolValidationError("metrics 中的每一项都必须是非空字符串。")

        unique_metrics = list(dict.fromkeys(metric.strip() for metric in metrics))
        missing = [
            metric for metric in unique_metrics if metric not in self._dataframe.columns
        ]
        if missing:
            raise ToolValidationError(f"当前数据集不存在字段：{', '.join(missing)}")
        if allowed_metrics is not None:
            unsupported = [
                metric for metric in unique_metrics if metric not in allowed_metrics
            ]
            if unsupported:
                raise ToolValidationError(
                    f"尚未配置异常规则的字段：{', '.join(unsupported)}"
                )
        if numeric_only:
            non_numeric = [
                metric
                for metric in unique_metrics
                if not pd.api.types.is_numeric_dtype(self._dataframe[metric])
            ]
            if non_numeric:
                raise ToolValidationError(
                    f"统计工具仅支持数值字段：{', '.join(non_numeric)}"
                )
        return unique_metrics
