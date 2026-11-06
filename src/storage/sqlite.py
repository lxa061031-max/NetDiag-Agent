"""Streamlit Community Cloud临时演示用SQLite仓储。"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from .configuration import SQLiteConfig
from .mssql import DatabaseConflictError, DatabaseUnavailableError, _json_text


class SQLiteRepository:
    """与mssql仓储保持相同接口；云端本地文件不保证持久化。"""

    def __init__(self, config: SQLiteConfig):
        self.config = config

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        try:
            self.config.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.config.path, timeout=8)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 8000")
            connection.execute("PRAGMA journal_mode = WAL")
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseUnavailableError("SQLite临时数据库无法打开。") from exc
        try:
            yield connection
            connection.commit()
        except sqlite3.IntegrityError:
            connection.rollback()
            raise
        except sqlite3.Error as exc:
            connection.rollback()
            raise DatabaseUnavailableError("SQLite临时数据库操作失败。") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def ensure_schema(self) -> None:
        statements = (
            """CREATE TABLE IF NOT EXISTS netdiag_users (
                user_id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash BLOB NOT NULL,
                password_salt BLOB NOT NULL,
                password_scheme TEXT NOT NULL,
                device_hash TEXT NOT NULL UNIQUE,
                created_at_utc TEXT NOT NULL,
                last_login_at_utc TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS netdiag_diagnosis_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                username_snapshot TEXT NOT NULL,
                device_hash TEXT NOT NULL,
                created_at_utc TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('success', 'error')),
                dataset_source TEXT,
                dataset_fingerprint TEXT,
                dataset_rows INTEGER,
                dataset_columns INTEGER,
                model TEXT,
                task TEXT NOT NULL,
                tool_records_json TEXT,
                evidence_json TEXT,
                report TEXT,
                error_message TEXT,
                FOREIGN KEY(user_id) REFERENCES netdiag_users(user_id)
            )""",
            """CREATE INDEX IF NOT EXISTS ix_netdiag_logs_user_time
               ON netdiag_diagnosis_logs(user_id, created_at_utc DESC)""",
        )
        with self._connection() as connection:
            for statement in statements:
                connection.execute(statement)

    @staticmethod
    def _user_row(row: sqlite3.Row | None) -> dict[str, object] | None:
        if row is None:
            return None
        return {
            "user_id": str(row["user_id"]),
            "username": str(row["username"]),
            "password_hash": bytes(row["password_hash"]),
            "password_salt": bytes(row["password_salt"]),
            "password_scheme": str(row["password_scheme"]),
            "device_hash": str(row["device_hash"]),
        }

    def get_user_by_username(self, username: str) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT user_id, username, password_hash, password_salt, password_scheme, device_hash "
                "FROM netdiag_users WHERE username = ?",
                (username,),
            ).fetchone()
        return self._user_row(row)

    def get_user_by_device(self, device_hash: str) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT user_id, username, password_hash, password_salt, password_scheme, device_hash "
                "FROM netdiag_users WHERE device_hash = ?",
                (device_hash,),
            ).fetchone()
        return self._user_row(row)

    def create_user(self, **values: Any) -> dict[str, object]:
        user_id = str(uuid.uuid4())
        try:
            with self._connection() as connection:
                connection.execute(
                    """INSERT INTO netdiag_users
                       (user_id, username, password_hash, password_salt, password_scheme,
                        device_hash, created_at_utc)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        user_id,
                        values["username"],
                        sqlite3.Binary(values["password_hash"]),
                        sqlite3.Binary(values["password_salt"]),
                        values["password_scheme"],
                        values["device_hash"],
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise DatabaseConflictError("账号或设备唯一约束冲突。") from exc
        return {"user_id": user_id, "username": values["username"], "device_hash": values["device_hash"]}

    def update_last_login(self, user_id: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE netdiag_users SET last_login_at_utc = ? WHERE user_id = ?",
                (datetime.now(timezone.utc).isoformat(), user_id),
            )

    def log_diagnosis(self, **values: Any) -> int:
        if values["status"] not in {"success", "error"}:
            raise ValueError("日志状态必须是success或error。")
        with self._connection() as connection:
            cursor = connection.execute(
                """INSERT INTO netdiag_diagnosis_logs
                   (user_id, username_snapshot, device_hash, created_at_utc, status,
                    dataset_source, dataset_fingerprint, dataset_rows, dataset_columns,
                    model, task, tool_records_json, evidence_json, report, error_message)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    values["user_id"], values["username"], values["device_hash"],
                    datetime.now(timezone.utc).isoformat(), values["status"],
                    values.get("dataset_source")[:260] if values.get("dataset_source") else None,
                    values.get("dataset_fingerprint"), values.get("dataset_rows"),
                    values.get("dataset_columns"),
                    values.get("model")[:128] if values.get("model") else None,
                    values["task"][:2000],
                    _json_text(values.get("tool_records")) if values.get("tool_records") is not None else None,
                    _json_text(values.get("evidence")) if values.get("evidence") is not None else None,
                    values.get("report"),
                    values.get("error_message")[:1000] if values.get("error_message") else None,
                ),
            )
            return int(cursor.lastrowid)

    def list_diagnosis_logs(self, user_id: str, limit: int = 20) -> list[dict[str, object]]:
        safe_limit = max(1, min(int(limit), 100))
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT log_id, created_at_utc, status, dataset_source, model, task,
                          report, error_message
                   FROM netdiag_diagnosis_logs WHERE user_id = ?
                   ORDER BY created_at_utc DESC, log_id DESC LIMIT ?""",
                (user_id, safe_limit),
            ).fetchall()
        return [dict(row) for row in rows]
