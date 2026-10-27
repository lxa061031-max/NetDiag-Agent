from io import BytesIO

import pandas as pd
import pytest

from src.data_processing.csv_loader import (
    EmptyCSVError,
    MissingColumnsError,
    build_data_summary,
    read_csv,
    validate_required_columns,
)


def test_read_csv_success() -> None:
    dataframe = read_csv(BytesIO(b"timestamp,latency_ms\n2026-10-01,12.5\n"))

    assert dataframe.shape == (1, 2)
    assert dataframe.loc[0, "latency_ms"] == 12.5


def test_empty_csv_raises_clear_error() -> None:
    with pytest.raises(EmptyCSVError, match="CSV 文件为空"):
        read_csv(BytesIO(b""))


def test_missing_required_columns() -> None:
    dataframe = pd.DataFrame({"timestamp": ["2026-10-01"]})

    with pytest.raises(MissingColumnsError, match="latency_ms"):
        validate_required_columns(dataframe, ["timestamp", "latency_ms"])


def test_data_summary_is_json_compatible() -> None:
    dataframe = pd.DataFrame({"value": [1.0, None], "device": ["A", "A"]})

    assert build_data_summary(dataframe) == {
        "row_count": 2,
        "column_count": 2,
        "missing_value_count": 1,
        "duplicate_row_count": 0,
        "numeric_column_count": 1,
        "numeric_columns": ["value"],
    }
