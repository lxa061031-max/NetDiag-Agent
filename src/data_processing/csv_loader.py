"""CSV 数据读取与基础校验逻辑，与 Streamlit 界面解耦。"""

from __future__ import annotations

from os import PathLike
from typing import IO, Any, Sequence

import pandas as pd


class EmptyCSVError(ValueError):
    """CSV 不含可用数据。"""


class MissingColumnsError(ValueError):
    """CSV 缺少调用方要求的字段。"""


CSVSource = str | PathLike[str] | IO[str] | IO[bytes]


def read_csv(source: CSVSource, **kwargs: Any) -> pd.DataFrame:
    """读取 CSV；为空文件或仅含表头时给出统一、清晰的异常。"""

    try:
        dataframe = pd.read_csv(source, **kwargs)
    except pd.errors.EmptyDataError as exc:
        raise EmptyCSVError("CSV 文件为空，未检测到表头或数据行。") from exc

    if dataframe.empty:
        raise EmptyCSVError("CSV 文件没有数据行，请上传包含记录的文件。")
    return dataframe


def validate_required_columns(
    dataframe: pd.DataFrame, required_columns: Sequence[str]
) -> None:
    """校验必需字段；成功时无返回值，失败时列出缺失字段。"""

    missing = [column for column in required_columns if column not in dataframe.columns]
    if missing:
        raise MissingColumnsError(f"缺少必需字段：{', '.join(missing)}")


def get_numeric_columns(dataframe: pd.DataFrame) -> list[str]:
    """返回可用于趋势图的数值列名。"""

    return dataframe.select_dtypes(include="number").columns.tolist()


def build_data_summary(dataframe: pd.DataFrame) -> dict[str, object]:
    """生成可 JSON 序列化的基础数据概况。"""

    numeric_columns = get_numeric_columns(dataframe)
    return {
        "row_count": int(dataframe.shape[0]),
        "column_count": int(dataframe.shape[1]),
        "missing_value_count": int(dataframe.isna().sum().sum()),
        "duplicate_row_count": int(dataframe.duplicated().sum()),
        "numeric_column_count": len(numeric_columns),
        "numeric_columns": numeric_columns,
    }
