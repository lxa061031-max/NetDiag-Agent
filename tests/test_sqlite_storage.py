from __future__ import annotations

from src.authentication import AuthenticationService
from src.storage import SQLiteConfig, SQLiteRepository


def test_sqlite_account_login_and_diagnosis_log(tmp_path):
    repository = SQLiteRepository(SQLiteConfig(tmp_path / "netdiag.db", "x" * 24))
    repository.ensure_schema()
    service = AuthenticationService(repository)
    user = service.register(
        username="sqlite_user",
        password="Net_1!",
        password_confirmation="Net_1!",
        device_hash="device-one",
    )
    assert service.authenticate(
        username="sqlite_user", password="Net_1!", device_hash="device-one"
    ) == user

    log_id = repository.log_diagnosis(
        user_id=user.user_id,
        username=user.username,
        device_hash=user.device_hash,
        status="success",
        task="检查异常",
        dataset_source="demo.csv",
        dataset_fingerprint="a" * 64,
        dataset_rows=10,
        dataset_columns=4,
        model="mock",
        tool_records=[{"tool_name": "detect_anomalies"}],
        evidence={"observations": ["10行"]},
        report="诊断报告",
    )
    logs = repository.list_diagnosis_logs(user.user_id)
    assert logs[0]["log_id"] == log_id
    assert logs[0]["task"] == "检查异常"


def test_sqlite_configuration_status(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_BACKEND", "sqlite")
    monkeypatch.setenv("AUTH_DEVICE_SECRET", "s" * 24)
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "cloud.db"))
    from src.storage.configuration import get_database_config_status

    status = get_database_config_status()
    assert status["configured"] is True
    assert status["backend"] == "sqlite"
    assert status["temporary"] is True
