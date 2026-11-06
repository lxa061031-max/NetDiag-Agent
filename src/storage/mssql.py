"""SQL Server账户与诊断日志持久化。"""

from __future__ import annotations

import json
import math
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterator, Mapping

from .configuration import MSSQLConfig


class DatabaseUnavailableError(RuntimeError):
    """数据库驱动、连接或查询不可用。"""


class DatabaseConflictError(RuntimeError):
    """唯一键冲突。"""


def _load_pyodbc():
    try:
        import pyodbc
    except ImportError as exc:
        raise DatabaseUnavailableError("未安装pyodbc，请先安装requirements.txt中的依赖。") from exc
    return pyodbc


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except (TypeError, ValueError):
            pass
    return str(value)


def _json_text(value: Any) -> str:
    return json.dumps(_json_safe(value), ensure_ascii=False, allow_nan=False)


class MSSQLRepository:
    def __init__(self, config: MSSQLConfig):
        self.config = config

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        pyodbc = _load_pyodbc()
        try:
            connection = pyodbc.connect(self.config.connection_string(), timeout=8)
        except pyodbc.Error as exc:
            raise DatabaseUnavailableError("无法连接MSSQL，请检查SQL Server、数据库、ODBC驱动和账号配置。") from exc
        try:
            yield connection
            connection.commit()
        except pyodbc.IntegrityError:
            connection.rollback()
            raise
        except pyodbc.Error as exc:
            connection.rollback()
            raise DatabaseUnavailableError("MSSQL操作失败，请检查表结构、权限和连接状态。") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def ensure_schema(self) -> None:
        statements = (
            """
            IF OBJECT_ID(N'dbo.netdiag_users', N'U') IS NULL
            BEGIN
                CREATE TABLE dbo.netdiag_users (
                    user_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_netdiag_users PRIMARY KEY DEFAULT NEWID(),
                    username NVARCHAR(32) NOT NULL,
                    password_hash VARBINARY(32) NOT NULL,
                    password_salt VARBINARY(16) NOT NULL,
                    password_scheme NVARCHAR(64) NOT NULL,
                    device_hash CHAR(64) NOT NULL,
                    created_at_utc DATETIME2(3) NOT NULL CONSTRAINT DF_netdiag_users_created DEFAULT SYSUTCDATETIME(),
                    last_login_at_utc DATETIME2(3) NULL,
                    CONSTRAINT UQ_netdiag_users_username UNIQUE (username),
                    CONSTRAINT UQ_netdiag_users_device UNIQUE (device_hash)
                );
            END
            """,
            """
            IF OBJECT_ID(N'dbo.netdiag_diagnosis_logs', N'U') IS NULL
            BEGIN
                CREATE TABLE dbo.netdiag_diagnosis_logs (
                    log_id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_netdiag_diagnosis_logs PRIMARY KEY,
                    user_id UNIQUEIDENTIFIER NOT NULL,
                    username_snapshot NVARCHAR(32) NOT NULL,
                    device_hash CHAR(64) NOT NULL,
                    created_at_utc DATETIME2(3) NOT NULL CONSTRAINT DF_netdiag_logs_created DEFAULT SYSUTCDATETIME(),
                    status NVARCHAR(16) NOT NULL,
                    dataset_source NVARCHAR(260) NULL,
                    dataset_fingerprint CHAR(64) NULL,
                    dataset_rows INT NULL,
                    dataset_columns INT NULL,
                    model NVARCHAR(128) NULL,
                    task NVARCHAR(2000) NOT NULL,
                    tool_records_json NVARCHAR(MAX) NULL,
                    evidence_json NVARCHAR(MAX) NULL,
                    report NVARCHAR(MAX) NULL,
                    error_message NVARCHAR(1000) NULL,
                    CONSTRAINT FK_netdiag_logs_user FOREIGN KEY (user_id) REFERENCES dbo.netdiag_users(user_id),
                    CONSTRAINT CK_netdiag_logs_status CHECK (status IN (N'success', N'error'))
                );
                CREATE INDEX IX_netdiag_logs_user_time
                    ON dbo.netdiag_diagnosis_logs(user_id, created_at_utc DESC);
            END
            """,
        )
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                for statement in statements:
                    cursor.execute(statement)
            except Exception as exc:
                raise DatabaseUnavailableError("MSSQL表结构初始化失败，请确认当前账号具有建表权限。") from exc

    @staticmethod
    def _user_row(row: Any) -> dict[str, object] | None:
        if row is None:
            return None
        return {
            "user_id": str(row.user_id),
            "username": str(row.username),
            "password_hash": bytes(row.password_hash),
            "password_salt": bytes(row.password_salt),
            "password_scheme": str(row.password_scheme),
            "device_hash": str(row.device_hash),
        }

    def get_user_by_username(self, username: str) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.cursor().execute(
                """SELECT user_id, username, password_hash, password_salt, password_scheme, device_hash
                   FROM dbo.netdiag_users WHERE username = ?""",
                username,
            ).fetchone()
        return self._user_row(row)

    def get_user_by_device(self, device_hash: str) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.cursor().execute(
                """SELECT user_id, username, password_hash, password_salt, password_scheme, device_hash
                   FROM dbo.netdiag_users WHERE device_hash = ?""",
                device_hash,
            ).fetchone()
        return self._user_row(row)

    def create_user(
        self,
        *,
        username: str,
        password_hash: bytes,
        password_salt: bytes,
        password_scheme: str,
        device_hash: str,
    ) -> dict[str, object]:
        pyodbc = _load_pyodbc()
        try:
            with self._connection() as connection:
                row = connection.cursor().execute(
                    """INSERT INTO dbo.netdiag_users
                       (username, password_hash, password_salt, password_scheme, device_hash)
                       OUTPUT inserted.user_id, inserted.username, inserted.device_hash
                       VALUES (?, ?, ?, ?, ?)""",
                    username,
                    pyodbc.Binary(password_hash),
                    pyodbc.Binary(password_salt),
                    password_scheme,
                    device_hash,
                ).fetchone()
        except pyodbc.IntegrityError as exc:
            raise DatabaseConflictError("账号或设备唯一约束冲突。") from exc
        return {"user_id": str(row.user_id), "username": str(row.username), "device_hash": str(row.device_hash)}

    def update_last_login(self, user_id: str) -> None:
        with self._connection() as connection:
            connection.cursor().execute(
                "UPDATE dbo.netdiag_users SET last_login_at_utc = SYSUTCDATETIME() WHERE user_id = ?",
                user_id,
            )

    def log_diagnosis(
        self,
        *,
        user_id: str,
        username: str,
        device_hash: str,
        status: str,
        task: str,
        dataset_source: str | None,
        dataset_fingerprint: str | None,
        dataset_rows: int | None,
        dataset_columns: int | None,
        model: str | None,
        tool_records: Any = None,
        evidence: Any = None,
        report: str | None = None,
        error_message: str | None = None,
    ) -> int:
        if status not in {"success", "error"}:
            raise ValueError("日志状态必须是success或error。")
        with self._connection() as connection:
            row = connection.cursor().execute(
                """INSERT INTO dbo.netdiag_diagnosis_logs
                   (user_id, username_snapshot, device_hash, status, dataset_source,
                    dataset_fingerprint, dataset_rows, dataset_columns, model, task,
                    tool_records_json, evidence_json, report, error_message)
                   OUTPUT inserted.log_id
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                user_id,
                username,
                device_hash,
                status,
                dataset_source[:260] if dataset_source else None,
                dataset_fingerprint,
                dataset_rows,
                dataset_columns,
                model[:128] if model else None,
                task[:2000],
                _json_text(tool_records) if tool_records is not None else None,
                _json_text(evidence) if evidence is not None else None,
                report,
                error_message[:1000] if error_message else None,
            ).fetchone()
        return int(row.log_id)

    def list_diagnosis_logs(self, user_id: str, limit: int = 20) -> list[dict[str, object]]:
        safe_limit = max(1, min(int(limit), 100))
        with self._connection() as connection:
            rows = connection.cursor().execute(
                f"""SELECT TOP {safe_limit} log_id, created_at_utc, status, dataset_source,
                    model, task, report, error_message
                    FROM dbo.netdiag_diagnosis_logs
                    WHERE user_id = ? ORDER BY created_at_utc DESC, log_id DESC""",
                user_id,
            ).fetchall()
        return [
            {
                "log_id": int(row.log_id),
                "created_at_utc": row.created_at_utc.isoformat(sep=" ") if row.created_at_utc else None,
                "status": str(row.status),
                "dataset_source": row.dataset_source,
                "model": row.model,
                "task": str(row.task),
                "report": row.report,
                "error_message": row.error_message,
            }
            for row in rows
        ]
