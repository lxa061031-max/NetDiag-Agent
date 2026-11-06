import json

import pandas as pd

from src.data_processing.adapters import describe_dataset
from src.data_processing.semantic_labels import build_semantic_label_map, build_semantic_value_frame


def test_semantic_labels_preserve_sources_and_values():
    data = pd.DataFrame(
        {
            "timestamp": ["2026-01-01 00:00", "2026-01-01 00:01"],
            "rtt_avg_ms": [10.0, 20.0],
            "gateway_rtt_avg_ms": [11.0, 21.0],
            "metric_unknown": [1.0, 2.0],
            "label_high_latency": [0, 1],
        }
    )
    original = data.copy(deep=True)
    adapter = describe_dataset(data)
    labels = build_semantic_label_map(adapter["schema_mapping"])
    assert [item["semantic_label"] for item in labels] == ["latency", "latency"]
    assert {item["source_column"] for item in labels} == {"rtt_avg_ms", "gateway_rtt_avg_ms"}
    assert "metric_unknown" not in {item["source_column"] for item in labels}
    assert "label_high_latency" not in {item["source_column"] for item in labels}
    values = build_semantic_value_frame(data, adapter)
    assert len(values) == 4
    assert set(values["semantic_label"]) == {"latency"}
    assert set(values["value"]) == {10.0, 11.0, 20.0, 21.0}
    json.dumps(labels, ensure_ascii=False, allow_nan=False)
    pd.testing.assert_frame_equal(data, original)


def test_unknown_data_returns_empty_semantic_value_frame():
    data = pd.DataFrame({"metric_a": [1.0, 2.0]})
    adapter = describe_dataset(data)
    result = build_semantic_value_frame(data, adapter, source_row_limit=1)
    assert result.empty
    assert "semantic_label" in result.columns
