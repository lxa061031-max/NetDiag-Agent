"""MSSQL与设备绑定配置，兼容环境变量和Streamlit Secrets。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


DATABASE_CONFIG_NAMES = (
    "MSSQL_SERVER",
    "MSSQL_DATABASE",
    "MSSQL_USERNAME",
    "MSSQL_PASSWORD",
    "MSSQL_DRIVER",
    "MSSQL_TRUSTED_CONNECTION",
    "MSSQL_ENCRYPT",
    "MSSQL_TRUST_SERVER_CERTIFICATE",
    "AUTH_DEVICE_SECRET",
)


def _read_streamlit_secrets() -> dict[str, str]:
    try:
        import streamlit as st
        from streamlit.errors import StreamlitSecretNotFoundError

        try:
            return {
                name: str(st.secrets.get(name, "") or "").strip()
                for name in DATABASE_CONFIG_NAMES
            }
        except (FileNotFoundError, KeyError, StreamlitSecretNotFoundError):
            return {}
    except ImportError:
        return {}


def read_database_settings() -> dict[str, str]:
    values = {name: os.getenv(name, "").strip() for name in DATABASE_CONFIG_NAMES}
    secrets = _read_streamlit_secrets() if not all(values.values()) else {}
    for name in DATABASE_CONFIG_NAMES:
        if not values[name]:
            values[name] = secrets.get(name, "")
    values["MSSQL_DRIVER"] = values["MSSQL_DRIVER"] or "ODBC Driver 18 for SQL Server"
    values["MSSQL_TRUSTED_CONNECTION"] = values["MSSQL_TRUSTED_CONNECTION"] or "false"
    values["MSSQL_ENCRYPT"] = values["MSSQL_ENCRYPT"] or "yes"
    values["MSSQL_TRUST_SERVER_CERTIFICATE"] = values["MSSQL_TRUST_SERVER_CERTIFICATE"] or "no"
    return values


def _enabled(value: str) -> bool:
    return value.casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class MSSQLConfig:
    server: str
    database: str
    username: str = ""
    password: str = field(default="", repr=False)
    driver: str = "ODBC Driver 18 for SQL Server"
    trusted_connection: bool = False
    encrypt: str = "yes"
    trust_server_certificate: str = "no"
    device_secret: str = field(default="", repr=False)

    @classmethod
    def from_settings(cls) -> "MSSQLConfig":
        settings = read_database_settings()
        config = cls(
            server=settings["MSSQL_SERVER"],
            database=settings["MSSQL_DATABASE"],
            username=settings["MSSQL_USERNAME"],
            password=settings["MSSQL_PASSWORD"],
            driver=settings["MSSQL_DRIVER"],
            trusted_connection=_enabled(settings["MSSQL_TRUSTED_CONNECTION"]),
            encrypt=settings["MSSQL_ENCRYPT"],
            trust_server_certificate=settings["MSSQL_TRUST_SERVER_CERTIFICATE"],
            device_secret=settings["AUTH_DEVICE_SECRET"],
        )
        config.validate()
        return config

    def validate(self) -> None:
        missing = []
        if not self.server:
            missing.append("MSSQL_SERVER")
        if not self.database:
            missing.append("MSSQL_DATABASE")
        if not self.device_secret:
            missing.append("AUTH_DEVICE_SECRET")
        if not self.trusted_connection and (not self.username or not self.password):
            missing.extend(name for name, value in (("MSSQL_USERNAME", self.username), ("MSSQL_PASSWORD", self.password)) if not value)
        if missing:
            raise ValueError("缺少数据库配置：" + "、".join(dict.fromkeys(missing)))
        if len(self.device_secret) < 24:
            raise ValueError("AUTH_DEVICE_SECRET至少需要24个字符。")

    def connection_string(self) -> str:
        parts = [
            f"DRIVER={{{self.driver}}}",
            f"SERVER={self.server}",
            f"DATABASE={self.database}",
            f"Encrypt={self.encrypt}",
            f"TrustServerCertificate={self.trust_server_certificate}",
        ]
        if self.trusted_connection:
            parts.append("Trusted_Connection=yes")
        else:
            parts.extend((f"UID={self.username}", f"PWD={self.password}"))
        return ";".join(parts) + ";"


def get_database_config_status() -> dict[str, object]:
    settings = read_database_settings()
    trusted = _enabled(settings["MSSQL_TRUSTED_CONNECTION"])
    required = ["MSSQL_SERVER", "MSSQL_DATABASE", "AUTH_DEVICE_SECRET"]
    if not trusted:
        required.extend(("MSSQL_USERNAME", "MSSQL_PASSWORD"))
    configured = all(settings[name] for name in required) and len(settings["AUTH_DEVICE_SECRET"]) >= 24
    return {
        "configured": configured,
        "trusted_connection": trusted,
        "variables": {name: bool(settings[name]) for name in required},
        "driver": settings["MSSQL_DRIVER"],
    }
