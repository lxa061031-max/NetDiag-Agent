import json

import pandas as pd
import pytest

from src.detection import detect_anomalies
from src.tools import calculate_numeric_statistics


def test_numeric_statistics_for_normal_data() -> None:
    dataframe = pd.DataFrame(
        {"latency_ms": [10.0, 20.0, 30.0], "device": ["A", "B", "C"]}
    )

    result = calculate_numeric_statistics(dataframe)

    assert list(result) == ["latency_ms"]
    assert result["latency_ms"]["count"] == 3
    assert result["latency_ms"]["mean"] == 20.0
    assert result["latency_ms"]["median"] == 20.0
    assert result["latency_ms"]["p95"] == pytest.approx(29.0)


def test_numeric_statistics_handles_empty_data() -> None:
    assert calculate_numeric_statistics(pd.DataFrame()) == {}


def test_numeric_statistics_ignores_missing_values() -> None:
    dataframe = pd.DataFrame(
        {
            "latency_ms": [10.0, None, 30.0],
            "temperature_c": pd.Series([None, None, None], dtype="float64"),
        }
    )

    result = calculate_numeric_statistics(dataframe)

    assert result["latency_ms"]["count"] == 2
    assert result["latency_ms"]["mean"] == 20.0
    assert result["temperature_c"]["count"] == 0
    assert result["temperature_c"]["p95"] is None


def test_detect_anomalies_reports_threshold_and_iqr_reason() -> None:
    dataframe = pd.DataFrame(
        {
            "timestamp": ["t1", "t2", "t3", "t4", "t5"],
            "latency_ms": [10.0, 11.0, 12.0, 13.0, 100.0],
        }
    )

    result = detect_anomalies(
        dataframe,
        thresholds={"latency_ms": {"max": 80.0}},
        use_iqr=True,
    )

    assert result["anomaly_count"] == 1
    anomaly = result["anomalies"][0]
    assert anomaly["row_index"] == 4
    assert anomaly["timestamp"] == "t5"
    assert anomaly["metric"] == "latency_ms"
    assert anomaly["value"] == 100.0
    assert "固定阈值" in anomaly["trigger_rule"]
    assert "IQR" in anomaly["trigger_rule"]


def test_detection_skips_missing_values_and_is_json_compatible() -> None:
    dataframe = pd.DataFrame(
        {"latency_ms": [10.0, None, 100.0], "device": ["A", "B", "C"]}
    )

    result = detect_anomalies(
        dataframe,
        thresholds={"latency_ms": {"max": 80.0}},
        use_iqr=False,
    )

    assert result["anomaly_count"] == 1
    assert json.loads(json.dumps(result, ensure_ascii=False))["anomaly_count"] == 1
    json.dumps(calculate_numeric_statistics(dataframe), ensure_ascii=False)
    assert detect_anomalies(dataframe, thresholds={})["anomaly_count"] == 0
