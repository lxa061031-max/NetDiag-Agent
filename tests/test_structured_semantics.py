import pandas as pd
import pytest

from src.data_processing.adapters import describe_dataset
from src.data_processing.analysis import analyze_anomalies
from src.data_processing.schema import build_schema_mapping


@pytest.mark.parametrize("field,semantic,unit", [
    ("rtt_avg_ms", "latency", "ms"), ("rtt_median_ms", "latency", "ms"),
    ("gateway_rtt_avg_ms", "latency", "ms"), ("jitter_ms", "jitter", "ms"),
    ("gateway_jitter_ms", "jitter", "ms"), ("packet_loss_pct", "packet_loss", "%"),
    ("gateway_packet_loss_pct", "packet_loss", "%"), ("wifi_rssi_dbm", "signal_strength", "dBm"),
    ("wifi_rx_mbps", "traffic_received", "Mbps"), ("wifi_tx_mbps", "traffic_sent", "Mbps"),
    ("download_mbps", "throughput", "Mbps"), ("upload_mbps", "throughput", "Mbps"),
    ("speedtest_ping_ms", "latency", "ms"), ("lan_throughput_mbps", "throughput", "Mbps"),
    ("Gateway RTT Avg MS", "latency", "ms"), ("interface_rx_bytes", "traffic_received", "bytes"),
    ("interface_tx_bits", "traffic_sent", "bits"), ("wifi_signal_percent", "signal_strength", "%"),
    ("download_rx_mbps", "traffic_received", "Mbps"), ("upload_tx_mbps", "traffic_sent", "Mbps"),
    ("interface_in_errors", "error_count", None), ("interface_out_discards", "drop_count", None),
])
def test_structured_field(field, semantic, unit):
    item = build_schema_mapping(pd.DataFrame({field: [1., 2., 3., 4.]}))[0]
    assert (item["canonical_name"], item["unit"]) == (semantic, unit)
    assert item["semantic_enabled"] and item["confidence"] >= .9
    assert item["mapping_source"] in {"exact_alias", "structured_pattern", "strong_alias"}


def test_metadata_labels_and_ambiguous_fields_not_semantic():
    names = ["label_packet_loss", "label_high_latency", "label_high_jitter", "timestamp_utc",
             "epoch_s", "elapsed_s", "sample_index", "run_id", "target", "notes"]
    df = pd.DataFrame({name: [1., 2., 3., 4.] for name in names})
    df["custom_metric"] = [1., 2., 3., 100.]
    df["application_ping_error_ms"] = [1., 2., 3., 4.]
    df["interface_rx_tx_mbps"] = [1., 2., 3., 4.]
    adapter = describe_dataset(df)
    mapping = {item["source_column"]: item for item in adapter["schema_mapping"]}
    assert all(mapping[name]["analysis_type"] == "non_metric" for name in names)
    assert all(name not in adapter["generic_numeric_columns"] for name in names)
    assert not mapping["application_ping_error_ms"]["semantic_enabled"]
    assert not mapping["interface_rx_tx_mbps"]["semantic_enabled"]
    assert mapping["custom_metric"]["analysis_type"] == "generic_numeric"
    assert analyze_anomalies(df, adapter, ["custom_metric"], mode="generic")["analysis_mode"] == "generic"
    with pytest.raises(ValueError):
        describe_dataset(df, confirmations={"label_packet_loss": "packet_loss"})


def test_weak_and_missing_values_require_confirmation():
    df = pd.DataFrame({"gateway_jitter": [1., 2.], "lan_throughput_mbps": [float("nan"), float("nan")]})
    mapping = {item["source_column"]: item for item in build_schema_mapping(df)}
    assert mapping["gateway_jitter"]["confidence"] <= .75
    assert mapping["lan_throughput_mbps"]["confidence"] <= .75
    assert all(item["needs_confirmation"] for item in mapping.values())


def test_synthetic_and_lcore_existing_mappings_are_unchanged():
    df = pd.DataFrame({"latency_ms": [1., 2.], "packet_loss_pct": [1., 2.],
                       "cpu_usage_pct": [1., 2.], "temperature_c": [1., 2.]})
    assert len(describe_dataset(df)["semantic_columns"]) == 4
    lcore = pd.DataFrame({"ICMP loss": [1., 2.], "ICMP response time": [1., 2.],
                          "B1_Bits_ received": [1., 2.], "P1_ Bits_ sent": [1., 2.]})
    assert len(describe_dataset(lcore)["semantic_columns"]) == 4


def test_streamlit_renders_mapping_and_excludes_label(monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest

    df = pd.DataFrame({"rtt_avg_ms": [1., 2., 3., 4.], "wifi_rx_mbps": [1., 2., 3., 4.],
                       "label_high_latency": [0, 1, 0, 1], "unknown_metric": [1., 2., 3., 4.]})
    monkeypatch.setattr("src.data_processing.read_csv", lambda *args, **kwargs: df.copy())
    monkeypatch.setattr("src.agent.get_agent_config_status", lambda: {"configured": False, "variables": {"LLM_API_KEY": False}, "model": "deepseek-flash", "base_url": None})
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=30)
    assert not app.exception
    schema = next(table.value for table in app.dataframe if "原始字段" in table.value.columns)
    rows = schema.set_index("原始字段")
    assert rows.loc["rtt_avg_ms", "推测/确认语义"] == "latency"
    assert rows.loc["wifi_rx_mbps", "推测/确认语义"] == "traffic_received"
    assert not rows.loc["label_high_latency", "参与专业分析"]
    assert rows.loc["unknown_metric", "分析级别"] == "generic_numeric"
