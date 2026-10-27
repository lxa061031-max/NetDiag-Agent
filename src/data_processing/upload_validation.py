"""在线演示资源边界；只读取上传CSV，不保存或执行文件。"""

from .csv_loader import read_csv


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_ROWS = 50_000
MAX_UPLOAD_COLUMNS = 100


def read_uploaded_csv(uploaded_file):
    if not str(getattr(uploaded_file, "name", "")).casefold().endswith(".csv"):
        raise ValueError("只接受CSV文件，请选择扩展名为.csv的文件。")
    if uploaded_file.size > MAX_UPLOAD_BYTES:
        raise ValueError("CSV超过10MB演示限制，请先抽样或拆分文件。")
    dataframe = read_csv(uploaded_file, encoding="utf-8-sig", nrows=MAX_UPLOAD_ROWS + 1,
                         low_memory=False)
    if len(dataframe) > MAX_UPLOAD_ROWS or len(dataframe.columns) > MAX_UPLOAD_COLUMNS:
        raise ValueError("数据超过演示资源限制（50,000行、100列），请先抽样或拆分文件。")
    return dataframe
