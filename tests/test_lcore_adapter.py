import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.agent import AgentConfig, run_diagnosis
from src.agent.tools import DatasetToolbox
from src.data_processing.adapters import describe_dataset


def sample() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": list(range(8)), "ICMP loss": [0., 1., 2., 3., 4., 5., 6., 100.],
        "ICMP response time": [1., 2., 3., 4., 5., 6., 7., 100.],
        "class": ["H"] * 7 + ["F"], "Device_name": ["R1"] * 8,
        "U_ Operational_ status": [1] * 8, "ICMP ping": ["0"] * 7 + ["`1"],
    })


def test_lcore_adapter_distinguishes_roles_and_preserves_input() -> None:
    data = sample()
    original = data.copy(deep=True)
    result = describe_dataset(data, "lcore_r1")
    assert result["row_count"] == 8
    assert result["label_column"] == "class"
    assert result["timestamp_column"] == "timestamp"
    assert result["analysis_columns"] == ["ICMP loss", "ICMP response time"]
    assert "U_ Operational_ status" in result["categorical_columns"]
    assert "ICMP ping" in result["unsupported_columns"]
    assert result["metadata"]["label_semantics_verified"] is False
    assert result["metadata"]["label_meanings"] == {}
    json.dumps(result, allow_nan=False)
    pd.testing.assert_frame_equal(data, original)


@pytest.mark.parametrize("column, result_key", [("timestamp", "timestamp_column"), ("class", "label_column")])
def test_optional_time_and_label(column: str, result_key: str) -> None:
    assert describe_dataset(sample().drop(columns=[column]), "lcore_r1")[result_key] is None


def test_lcore_statistics_use_original_fields() -> None:
    result = DatasetToolbox(sample()).execute("analyze_network_metrics", {"metrics": ["ICMP loss"]})
    assert result["ok"] is True
    assert result["result"]["statistics"]["ICMP loss"]["count"] == 8
    assert result["result"]["statistics"]["ICMP loss"]["max"] == 100


def test_lcore_iqr_has_no_synthetic_thresholds() -> None:
    result = DatasetToolbox(sample()).execute("detect_anomalies", {"metrics": ["ICMP loss"], "use_iqr": True, "max_results": 5})
    assert result["ok"] is True
    assert result["result"]["anomalous_row_count"] == 1
    assert all("IQR" in item["trigger_rule"] and "固定" not in item["trigger_rule"] for item in result["result"]["anomalies"])
    json.dumps(result, allow_nan=False)


def test_lcore_excludes_label_time_and_rejects_fixed_only() -> None:
    toolbox = DatasetToolbox(sample())
    for column in ("class", "timestamp", "U_ Operational_ status"):
        assert toolbox.execute("analyze_network_metrics", {"metrics": [column]})["ok"] is False
    assert toolbox.execute("detect_anomalies", {"metrics": ["ICMP loss"], "use_iqr": False, "max_results": 5})["ok"] is False


def test_synthetic_adapter_still_uses_original_rules() -> None:
    data = pd.DataFrame({"latency_ms": [10., 90.], "anomaly_label": [0, 1]})
    adapter = describe_dataset(data, "synthetic")
    assert adapter["metadata"]["label_semantics_verified"] is True
    result = DatasetToolbox(data).execute("detect_anomalies", {"metrics": ["latency_ms"], "use_iqr": False, "max_results": 5})
    assert result["result"]["anomalous_row_count"] == 1


def test_lcore_agent_uses_adapted_tools_with_mock_api() -> None:
    first = SimpleNamespace(output=[
        SimpleNamespace(type="function_call", name="analyze_network_metrics", arguments='{"metrics":["ICMP loss","ICMP response time"]}', call_id="stats"),
        SimpleNamespace(type="function_call", name="detect_anomalies", arguments='{"metrics":["ICMP loss","ICMP response time"],"use_iqr":true,"max_results":5}', call_id="iqr"),
    ])
    report = """## 数据分析摘要
[实际检测结果] 统计原始ICMP字段。
## 检测到的异常
[实际检测结果] IQR检出统计偏离，不等于故障。
## 相关数据证据
[参考知识] RFC 7680可供参考。
## 可能的故障原因
[模型推测] 需要进一步排查。
## 建议的排查步骤
补充链路利用率和接口队列数据。
## 无法确定的结论及其原因
无法确认根因，H/F语义未确认。"""
    client = MagicMock()
    client.responses.create.side_effect = [first, SimpleNamespace(output=[], output_text=report)]
    result = run_diagnosis(sample(), "分析LCORE-D网络指标和统计异常，参考相关知识", config=AgentConfig("test", "https://example.invalid", "test"), client=client)
    assert result["task_completion"]["complete"] is True
    assert result["tool_calls_executed"] == 3
    assert result["evidence_chain"]["dataset_adapter"]["source_type"] == "lcore_r1"
    assert client.responses.create.call_count == 2
    assert "IQR" in result["tool_records"][1]["result"]["result"]["method"]
