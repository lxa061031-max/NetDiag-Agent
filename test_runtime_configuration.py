import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.agent import AgentConfig, AgentConfigurationError, run_diagnosis
from src.agent.configuration import SUPPORTED_MODELS
from src.agent.tools import DatasetToolbox
from src.data_processing.adapters import describe_dataset
from src.data_processing.analysis import analyze_anomalies
from src.data_processing.schema import build_schema_mapping, SEMANTIC_REGISTRY
from src.detection.config import DEFAULT_THRESHOLD_RULES, detection_config

REPORT = """## 数据分析摘要
[实际检测结果] 数据工具已运行。
## 检测到的异常
[实际检测结果] 已执行检查。
## 相关数据证据
[实际检测结果] 数据来源于工具。
## 可能的故障原因
[模型推测] 暂不确定。
## 建议的排查步骤
人工复核。
## 无法确定的结论及其原因
无法确认根因，需要其他证据。"""


def test_defaults_are_independent_and_match_existing_rules():
    first = detection_config()
    assert first["iqr_multiplier"] == 1.5
    assert first["thresholds"] == {k: v["max"] for k, v in DEFAULT_THRESHOLD_RULES.items()}
    first["thresholds"]["latency_ms"] = 999
    assert detection_config()["thresholds"]["latency_ms"] == 80


def test_default_and_override_model_requests_use_same_agent():
    data = pd.DataFrame({"latency_ms": [10.0, 12.0, 100.0]})
    for override, expected in [(None, "deepseek-flash"), ("deepseek-v4-pro", "deepseek-v4-pro")]:
        client = MagicMock()
        client.responses.create.side_effect = [SimpleNamespace(output=[SimpleNamespace(type="function_call", name="get_dataset_summary", arguments="{}", call_id="s")]), SimpleNamespace(output=[], output_text=REPORT)]
        result = run_diagnosis(data, "数据概览", config=AgentConfig("dummy", "https://example.invalid", "deepseek-flash"), client=client, model_override=override)
        assert result["model"] == expected
        assert all(call.kwargs["model"] == expected for call in client.responses.create.call_args_list)


def test_invalid_model_never_calls_client():
    client = MagicMock()
    with pytest.raises(AgentConfigurationError, match="不支持"):
        run_diagnosis(pd.DataFrame({"latency_ms": [1]}), "概览", config=AgentConfig("dummy", "https://example.invalid", "deepseek-flash"), client=client, model_override="unknown")
    client.responses.create.assert_not_called()
    assert set(SUPPORTED_MODELS.values()) == {"deepseek-flash", "deepseek-v4-pro"}


def test_unsupported_environment_default_is_rejected(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(AgentConfig, "from_environment", classmethod(lambda cls: cls("dummy", "https://example.invalid", "unknown")))
    with pytest.raises(AgentConfigurationError):
        run_diagnosis(pd.DataFrame({"latency_ms": [1]}), "overview", client=client)
    client.responses.create.assert_not_called()


def test_iqr_multiplier_and_fixed_threshold_change_results():
    data = pd.DataFrame({"latency_ms": [1., 2., 3., 4., 100.], "metric_a": [1., 2., 3., 4., 10.]})
    adapter = describe_dataset(data)
    default = analyze_anomalies(data, adapter, ["metric_a"], mode="generic")
    relaxed = analyze_anomalies(data, adapter, ["metric_a"], mode="generic", settings={"iqr_multiplier": 5})
    assert default["anomalous_row_count"] == 1 and relaxed["anomalous_row_count"] == 0
    normal = analyze_anomalies(data, adapter, ["latency_ms"], use_iqr=False)
    changed = analyze_anomalies(data, adapter, ["latency_ms"], use_iqr=False, settings={"thresholds": {"latency_ms": 120}})
    assert normal["anomalous_row_count"] == 1 and changed["anomalous_row_count"] == 0
    assert changed["detection_config"]["fixed_thresholds"]["latency_ms"]["max"] == 120


@pytest.mark.parametrize("bad", [
    {"iqr_multiplier": 0}, {"iqr_multiplier": None}, {"iqr_multiplier": float("nan")},
    {"thresholds": {"packet_loss_pct": 101}}, {"thresholds": {"cpu_usage_pct": -1}},
    {"thresholds": {"latency_ms": "bad"}}, {"thresholds": {"latency_ms": None}},
    {"thresholds": {"not_a_metric": 1}},
])
def test_bad_detection_settings_rejected(bad):
    with pytest.raises(ValueError):
        detection_config(bad)


def test_tool_reports_effective_configuration_as_json():
    toolbox = DatasetToolbox(pd.DataFrame({"latency_ms": [1., 2., 3., 4., 100.]}), settings={"thresholds": {"latency_ms": 120}, "iqr_multiplier": 3})
    result = toolbox.execute("detect_anomalies", {"metrics": ["latency_ms"], "use_iqr": True, "max_results": 5})
    config = result["result"]["detection_config"]
    assert config["fixed_thresholds"]["latency_ms"]["max"] == 120
    assert config["iqr_multiplier"] == 3 and config["use_iqr"]
    json.dumps(result, allow_nan=False)


def test_registry_aliases_and_unknown():
    data = pd.DataFrame({"rtt": [1, 2], "loss_rate": [1, 2], "rx_bytes": [1, 2], "tx_bits": [1, 2], "metric_a": [1, 2]})
    mapping = {m["source_column"]: m for m in build_schema_mapping(data)}
    for field, semantic in [("rtt", "latency"), ("loss_rate", "packet_loss"), ("rx_bytes", "traffic_received"), ("tx_bits", "traffic_sent")]:
        assert mapping[field]["canonical_name"] == semantic and mapping[field]["confidence"] == .9
        assert mapping[field]["unit"] is None
    assert mapping["metric_a"]["canonical_name"] is None and not mapping["metric_a"]["semantic_enabled"]
    assert len(SEMANTIC_REGISTRY) == 12


def test_requested_semantic_alias_ranges_and_new_fields():
    from src.data_processing.schema import _normalize
    bounds = {"latency": (6, 8), "packet_loss": (5, 7), "jitter": (3, 5),
              "traffic_received": (5, 7), "traffic_sent": (5, 7),
              "error_count": (4, 6), "drop_count": (4, 6),
              "cpu_usage": (3, 5), "temperature": (2, 4),
              "throughput": (5, 7), "signal_strength": (3, 5), "snr": (2, 4)}
    for semantic, (minimum, maximum) in bounds.items():
        entry = SEMANTIC_REGISTRY[semantic]
        aliases = {_normalize(alias) for group in (entry["exact"], entry["strong"], entry["weak"]) for alias in group}
        assert minimum <= len(aliases) <= maximum, (semantic, aliases)
    data = pd.DataFrame({name: [1., 2.] for name in ("delay_variation", "throughput_mbps", "rssi", "snr_db")})
    mapping = {item["source_column"]: item for item in build_schema_mapping(data)}
    for field, semantic in [("delay_variation", "jitter"), ("throughput_mbps", "throughput"), ("rssi", "signal_strength"), ("snr_db", "snr")]:
        assert mapping[field]["canonical_name"] == semantic
        assert mapping[field]["semantic_enabled"] and mapping[field]["unit"] is None


def test_ui_session_model_and_restore_defaults(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr("src.agent.get_agent_config_status", lambda: {"configured": False, "variables": {"LLM_API_KEY": False}, "model": "deepseek-flash", "base_url": None})
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=30)
    assert not app.exception
    preview = next(d.value.copy() for d in app.dataframe if "latency_ms" in d.value.columns)
    assert app.selectbox(key="diagnosis_model").value == "deepseek-flash"
    app.selectbox(key="diagnosis_model").select("deepseek-v4-pro").run(timeout=30)
    assert not app.exception and app.selectbox(key="diagnosis_model").value == "deepseek-v4-pro"
    pd.testing.assert_frame_equal(preview, next(d.value for d in app.dataframe if "latency_ms" in d.value.columns))
    app.number_input(key="threshold_latency_ms").set_value(120.0).run(timeout=30)
    assert app.number_input(key="threshold_latency_ms").value == 120
    app.checkbox(key="reset_detection_defaults").check().run(timeout=30)
    assert not app.exception and app.number_input(key="threshold_latency_ms").value == 80


def test_lcore_custom_configuration_never_adds_fixed_thresholds():
    data = pd.DataFrame({"ICMP loss": [1., 2., 3., 4., 100.], "ICMP response time": [1., 2., 3., 4., 100.]})
    toolbox = DatasetToolbox(data, settings={"thresholds": {"latency_ms": 1}, "iqr_multiplier": 3})
    result = toolbox.execute("detect_anomalies", {"metrics": ["ICMP loss"], "use_iqr": True, "max_results": 5})
    assert result["ok"] and not result["result"]["fixed_threshold_fields"]
    assert result["result"]["detection_config"]["iqr_multiplier"] == 3


def test_agent_passes_user_settings_to_actual_tool_result():
    data = pd.DataFrame({"latency_ms": [1., 2., 3., 4., 100.]})
    client = MagicMock()
    client.responses.create.side_effect = [SimpleNamespace(output=[SimpleNamespace(type="function_call", name="detect_anomalies", arguments='{"metrics":["latency_ms"],"use_iqr":false,"max_results":5}', call_id="d")]), SimpleNamespace(output=[], output_text=REPORT)]
    result = run_diagnosis(data, "检查是否异常", config=AgentConfig("dummy", "https://example.invalid", "deepseek-flash"), client=client, detection_settings={"thresholds": {"latency_ms": 120}, "iqr_multiplier": 4})
    tool = result["tool_records"][0]["result"]["result"]
    assert tool["anomalous_row_count"] == 0
    assert tool["detection_config"]["fixed_thresholds"]["latency_ms"]["max"] == 120
    assert tool["detection_config"]["use_iqr"] is False
