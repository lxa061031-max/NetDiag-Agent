import json
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.agent import AgentConfig, run_diagnosis
from src.agent.tools import DatasetToolbox
from src.data_processing.adapters import describe_dataset
from src.data_processing.analysis import analyze_anomalies, analyze_statistics
from src.data_processing.schema import build_schema_mapping


def csv_data(names):
    # 三类CSV均从内存重新读取，保留真实CSV类型推断路径。
    text = ",".join(names) + "\n" + "\n".join(
        ",".join([str(value)] * len(names)) for value in [10, 11, 12, 13, 100]
    )
    return pd.read_csv(StringIO(text))


@pytest.mark.parametrize("names,semantics,confidence", [
    (["latency_ms", "packet_loss_pct", "cpu_usage_pct"], ["latency", "packet_loss", "cpu_usage"], 1.0),
    (["rtt", "loss_rate", "device_cpu"], ["latency", "packet_loss", "cpu_usage"], .9),
])
def test_standard_and_alias_csv(names, semantics, confidence):
    data = csv_data(names)
    before = data.copy(deep=True)
    schema = describe_dataset(data)["schema_mapping"]
    assert [m["canonical_name"] for m in schema] == semantics
    assert all(m["confidence"] == confidence and m["semantic_enabled"] for m in schema)
    if names[0] == "rtt":
        assert all(m["unit"] is None for m in schema)
    json.dumps(schema, allow_nan=False)
    pd.testing.assert_frame_equal(data, before)


def test_unknown_csv_generic_only():
    data = csv_data(["metric_a", "metric_b"])
    adapter = describe_dataset(data)
    assert adapter["source_type"] == "generic"
    assert adapter["semantic_columns"] == []
    assert all(m["canonical_name"] is None and m["needs_confirmation"] for m in adapter["schema_mapping"])
    stats = analyze_statistics(data, adapter, ["metric_a"])
    assert stats["metric_a"]["count"] == 5
    assert stats["metric_a"]["max"] == 100
    result = analyze_anomalies(data, adapter, ["metric_a", "metric_b"], mode="generic")
    assert result["anomalous_row_count"] == 1
    assert result["fixed_threshold_fields"] == []
    assert all("IQR" in a["trigger_rule"] for a in result["anomalies"])
    json.dumps([adapter, stats, result], allow_nan=False)
    with pytest.raises(ValueError, match="Generic"):
        analyze_statistics(data, adapter, ["metric_a"], "semantic")
    assert not DatasetToolbox(data).execute("search_fault_knowledge", {"query": "丢包"})["ok"]


def test_weak_alias_confirmation_does_not_confirm_unit_or_mutate():
    data = csv_data(["delay"])
    assert build_schema_mapping(data)[0]["confidence"] == .6
    assert build_schema_mapping(data)[0]["needs_confirmation"]
    confirmed = describe_dataset(data, confirmations={"delay": "latency"})
    item = confirmed["schema_mapping"][0]
    assert item["semantic_enabled"] and item["mapping_source"] == "user_confirmation"
    assert item["unit"] is None
    assert analyze_anomalies(data, confirmed, ["delay"], mode="semantic")["fixed_threshold_fields"] == []
    kept = describe_dataset(data, confirmations={"delay": None})
    assert kept["schema_mapping"][0]["analysis_type"] == "generic_numeric"
    assert not kept["schema_mapping"][0]["needs_confirmation"]
    assert build_schema_mapping(data)[0]["needs_confirmation"]  # 不保存到数据或全局


@pytest.mark.parametrize("confirmation", [{"no_column": "latency"}, {"metric_a": "dns"}, {"metric_a": 4}, [], {"name": "latency"}])
def test_invalid_confirmation(confirmation):
    with pytest.raises(ValueError):
        describe_dataset(pd.DataFrame({"metric_a": [1], "name": ["abc"]}), confirmations=confirmation)


def test_distribution_only_downgrades_never_guesses_unit():
    data = pd.DataFrame({"cpu_usage_pct": [10, 200], "loss_rate": [.01, .02]})
    mapping = {i["source_column"]: i for i in build_schema_mapping(data)}
    assert mapping["cpu_usage_pct"]["needs_confirmation"]
    assert mapping["cpu_usage_pct"]["warnings"]
    assert mapping["loss_rate"]["unit"] is None
    result = analyze_anomalies(data, describe_dataset(data), ["cpu_usage_pct"], use_iqr=True)
    assert result["fixed_threshold_fields"] == []


def test_semantic_rules_require_units_and_preserve_original_names():
    data = csv_data(["latency_ms", "rtt", "metric_a"])
    adapter = describe_dataset(data)
    result = analyze_anomalies(data, adapter, ["latency_ms"], mode="semantic", use_iqr=False)
    assert result["fixed_threshold_fields"] == ["latency_ms"]
    assert result["anomalies"][0]["metric"] == "latency_ms"
    with pytest.raises(ValueError, match="IQR"):
        analyze_anomalies(data, adapter, ["rtt"], mode="semantic", use_iqr=False)
    with pytest.raises(ValueError, match="Generic"):
        analyze_anomalies(data, adapter, ["metric_a"], mode="semantic")
    generic = analyze_anomalies(data, adapter, ["latency_ms"], mode="generic")
    assert generic["fixed_threshold_fields"] == []


def test_empty_missing_nonfinite_and_metadata_columns():
    empty = pd.DataFrame({"metric_a": pd.Series(dtype=float)})
    adapter = describe_dataset(empty)
    assert analyze_statistics(empty, adapter, ["metric_a"]) == {}
    assert analyze_anomalies(empty, adapter, ["metric_a"])["anomaly_count"] == 0
    data = pd.DataFrame({"metric_a": [1, 2, 3, 4, 100, np.nan, np.inf], "timestamp": range(7), "anomaly_label": [0] * 7})
    original = data.copy(deep=True)
    adapter = describe_dataset(data)
    assert analyze_statistics(data, adapter, ["metric_a"])["metric_a"]["count"] == 5
    result = analyze_anomalies(data, adapter, ["metric_a"])
    assert result["nonfinite_values_ignored"] == {"metric_a": 1}
    json.dumps(result, allow_nan=False)
    pd.testing.assert_frame_equal(data, original)
    for name in ["timestamp", "anomaly_label"]:
        with pytest.raises(ValueError):
            analyze_statistics(data, adapter, [name])


def test_generic_tool_modes_and_invalid_mode():
    toolbox = DatasetToolbox(csv_data(["metric_a"]))
    for name, args in [("analyze_network_metrics", {"metrics": ["metric_a"]}),
                       ("detect_anomalies", {"metrics": ["metric_a"], "use_iqr": True, "max_results": 5})]:
        result = toolbox.execute(name, {**args, "analysis_mode": "generic"})
        assert result["ok"]
        json.dumps(result, allow_nan=False)
        assert not toolbox.execute(name, {**args, "analysis_mode": "invalid"})["ok"]
        assert not toolbox.execute(name, {**args, "analysis_mode": "semantic"})["ok"]


def test_synthetic_demo_regression():
    data = pd.read_csv(Path(__file__).resolve().parents[1] / "data/demo/synthetic_network.csv")
    adapter = describe_dataset(data)
    result = analyze_anomalies(data, adapter, adapter["analysis_columns"])
    assert len(data) == 240
    assert result["anomalous_row_count"] == 22
    assert result["anomaly_count"] == 79
    assert len(adapter["semantic_columns"]) == 4


def test_lcore_schema_compatibility_without_unit_guess():
    data = pd.DataFrame({"ICMP loss": [0, 1, 2, 3, 100], "ICMP response time": [1, 2, 3, 4, 100],
                         "U_ Bits_ received": [1, 2, 3, 4, 100], "class": ["H"] * 5})
    adapter = describe_dataset(data)
    assert adapter["source_type"] == "lcore_r1"
    assert len(adapter["semantic_columns"]) == 3
    assert all(i["unit"] is None for i in adapter["schema_mapping"])
    result = analyze_anomalies(data, adapter, adapter["analysis_columns"])
    assert result["fixed_threshold_fields"] == []
    assert result["anomalous_row_count"] == 1


REPORT = """## 数据分析摘要
[实际检测结果] 使用当前工具返回数据。
## 检测到的异常
[实际检测结果] 存在统计偏离。
## 相关数据证据
[实际检测结果] 仅依据Python计算。
## 可能的故障原因
[模型推测] 证据不足。
## 建议的排查步骤
补充单位、设备日志和接口状态。
## 无法确定的结论及其原因
无法确认根因，需要人工复核。"""


def test_agent_generic_evidence_cannot_become_network_knowledge():
    data = csv_data(["metric_a", "latency_ms"])
    client = MagicMock()
    client.responses.create.side_effect = [SimpleNamespace(output=[
        SimpleNamespace(type="function_call", name="detect_anomalies", arguments=json.dumps({"metrics": ["metric_a"], "use_iqr": True, "max_results": 5}), call_id="d"),
        SimpleNamespace(type="function_call", name="search_fault_knowledge", arguments='{"query":"丢包"}', call_id="k"),
    ]), SimpleNamespace(output=[], output_text=REPORT)]
    result = run_diagnosis(data, "解释异常", config=AgentConfig("mock", "https://example.invalid", "mock"), client=client)
    assert result["tool_records"][1]["result"]["error"]["type"] == "semantic_evidence_required"
    assert not result["knowledge_references"]
    assert "metric_a" in result["report"] and "不使用网络专业阈值" in result["report"]
    assert result["evidence_chain"]["dataset_adapter"]["schema_mapping"]
    assert any("generic_numeric" in item.get("content", "") for item in client.responses.create.call_args_list[1].kwargs["input"] if isinstance(item, dict))
    json.dumps(result, allow_nan=False)


def test_agent_receives_session_confirmation():
    client = MagicMock()
    client.responses.create.side_effect = [SimpleNamespace(output=[SimpleNamespace(type="function_call", name="get_dataset_summary", arguments="{}", call_id="s")]), SimpleNamespace(output=[], output_text=REPORT)]
    result = run_diagnosis(csv_data(["delay"]), "概览规模", schema_confirmations={"delay": "latency"}, config=AgentConfig("mock", "https://example.invalid", "mock"), client=client)
    item = result["evidence_chain"]["dataset_adapter"]["schema_mapping"][0]
    assert item["mapping_source"] == "user_confirmation" and item["semantic_enabled"]
    assert "单位尚未确认" in result["report"]


@pytest.mark.parametrize("names", [["latency_ms", "packet_loss_pct", "cpu_usage_pct"],
                                   ["rtt", "loss_rate", "device_cpu"], ["metric_a", "metric_b"]])
def test_streamlit_adaptation_and_modes(monkeypatch, names):
    from streamlit.testing.v1 import AppTest

    data = csv_data(names)
    monkeypatch.setattr("src.data_processing.read_csv", lambda *args, **kwargs: data.copy(deep=True))
    monkeypatch.setattr("src.agent.get_agent_config_status", lambda: {
        "configured": False, "variables": {"LLM_API_KEY": False}, "model": None, "base_url": None,
    })
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=30)
    assert not app.exception
    assert any(s.value == "数据适配结果" for s in app.subheader)
    assert app.button[0].disabled  # 无任何真实API调用入口
    if names[0] == "metric_a":
        confirmation = next(s for s in app.selectbox if s.label == "metric_a → 标准语义")
        confirmation.select("latency").run(timeout=30)
        assert not app.exception
        table = next(d.value for d in app.dataframe if "原始字段" in d.value.columns)
        row = table.loc[table["原始字段"] == "metric_a"].iloc[0]
        assert row["映射来源"] == "user_confirmation"
        assert row["参与专业分析"]
        assert pd.isna(row["已知单位"])
    app.radio[0].set_value("Generic Analysis（通用数值分析）").run(timeout=30)
    assert not app.exception
    pd.testing.assert_frame_equal(data, csv_data(names))


def test_local_lcore_r1_regression_if_available():
    path = Path(__file__).resolve().parents[1] / "data/raw/LCORE-D R1.csv"
    if not path.exists():
        pytest.skip("本地R1未分发；其他LCORE结构测试仍执行")
    data = pd.read_csv(path, low_memory=False)
    assert data.shape == (24240, 42)
    assert data["class"].value_counts().to_dict() == {"H": 23811, "F": 429}
    adapter = describe_dataset(data)
    assert len(adapter["analysis_columns"]) == 8
    assert len(adapter["semantic_columns"]) == 8
    result = analyze_anomalies(data, adapter, adapter["analysis_columns"])
    assert result["fixed_threshold_fields"] == []
    assert result["anomalous_row_count"] == 9466
    assert result["anomaly_count"] == 21473
    json.dumps(result, allow_nan=False)
