from io import BytesIO
import json
from pathlib import Path
import tomllib

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.agent import AgentConfig, AgentConfigurationError, get_agent_config_status
from src.agent.configuration import CONFIG_NAMES
from src.agent.single_agent import _safe_api_error
from src.data_processing import EmptyCSVError
from src.data_processing.upload_validation import MAX_UPLOAD_BYTES, read_uploaded_csv


def clear_config(monkeypatch):
    for name in CONFIG_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_secrets_fallback_and_environment_priority(monkeypatch):
    clear_config(monkeypatch)
    monkeypatch.setattr(st, "secrets", {"LLM_API_KEY": "cloud-test", "LLM_BASE_URL": "https://example.invalid", "LLM_MODEL": "mock"})
    assert AgentConfig.from_environment().api_key == "cloud-test"
    monkeypatch.setenv("LLM_API_KEY", "env-test")
    config = AgentConfig.from_environment()
    assert config.api_key == "env-test" and config.model == "mock"
    assert "env-test" not in repr(config)
    assert get_agent_config_status()["variables"]["LLM_API_KEY"] is True


def test_missing_secrets_do_not_break_configuration_status(monkeypatch):
    clear_config(monkeypatch)

    class MissingSecrets:
        def get(self, *args):
            raise FileNotFoundError("do-not-display")

    monkeypatch.setattr(st, "secrets", MissingSecrets())
    assert get_agent_config_status()["configured"] is False
    with pytest.raises(AgentConfigurationError, match="LLM_API_KEY"):
        AgentConfig.from_environment()


def test_api_response_headers_and_keys_are_not_exposed():
    message = _safe_api_error(RuntimeError("Authorization: Bearer private-value; response-body-private"), "private-value")
    assert "private-value" not in message and "Authorization" not in message and "response-body" not in message
    assert "模型服务暂时不可用" in message


def upload(content=b"latency_ms\n10\n", name="test.csv", size=None):
    file = BytesIO(content)
    file.name = name
    file.size = len(content) if size is None else size
    return file


@pytest.mark.parametrize("file,error", [
    (upload(name="data.py"), "只接受CSV"),
    (upload(size=MAX_UPLOAD_BYTES + 1), "10MB"),
    (upload(("metric_a\n" + "1\n" * 50001).encode()), "50,000行"),
    (upload((",".join(f"c{i}" for i in range(101)) + "\n" + ",".join(["1"] * 101)).encode()), "100列"),
])
def test_upload_limits(file, error):
    with pytest.raises(ValueError, match=error):
        read_uploaded_csv(file)


def test_csv_empty_encoding_and_unknown_fields():
    with pytest.raises(EmptyCSVError):
        read_uploaded_csv(upload(b""))
    with pytest.raises(UnicodeDecodeError):
        read_uploaded_csv(upload(b"metric\n\xff"))
    data = read_uploaded_csv(upload(b"metric_a,metric_b\n1,2\n3,4\n"))
    assert data.shape == (2, 2)


def test_unconfigured_page_and_no_dataset_stay_usable(monkeypatch):
    clear_config(monkeypatch)
    monkeypatch.setattr(st, "secrets", {})
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=30)
    assert not app.exception
    assert any("数据分析功能仍可使用" in w.value for w in app.warning)
    assert app.button[0].disabled
    app.checkbox[0].uncheck().run(timeout=30)
    assert not app.exception
    assert any("请上传" in w.value for w in app.warning)


def test_deployment_configuration_and_package_allowlist():
    from scripts.prepare_deployment import deployment_files, secret_container, KEY_PATTERN

    root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((root / ".streamlit/config.toml").read_text(encoding="utf-8"))
    assert config["server"]["maxUploadSize"] == 10
    assert config["client"]["showErrorDetails"] == "none"
    paths = [p.relative_to(root).as_posix() for p in deployment_files()]
    assert ".env" not in paths and ".streamlit/secrets.toml" not in paths
    assert all(not p.startswith("data/raw/") and "LCORE-D R1.csv" not in p for p in paths)
    assert "data/demo/synthetic_network.csv" in paths
    assert "data/knowledge/network_faults.json" in paths
    assert secret_container(Path(".env.local"))
    assert not secret_container(Path(".env.example"))
    assert KEY_PATTERN.search("sk-" + "a" * 40)
    json.dumps(paths)
