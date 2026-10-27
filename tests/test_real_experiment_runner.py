from io import StringIO
from unittest.mock import MagicMock

import pytest

from scripts import run_real_agent_experiment as experiment
from src.agent import AgentConfig


def test_real_runner_refuses_second_paid_task_and_records_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    records_dir = MagicMock()
    record_file = records_dir.__truediv__.return_value
    record_file.name = "task_A.json"
    record_file.open.side_effect = [StringIO(), FileExistsError()]
    monkeypatch.setattr(experiment, "RECORDS_DIR", records_dir)
    monkeypatch.setattr(experiment, "render", lambda: None)
    monkeypatch.setattr(experiment.AgentConfig, "from_environment", lambda: AgentConfig(api_key="test-key", base_url="https://api.deepseek.com", model="test-model"))

    def fail(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("test-key error")

    monkeypatch.setattr(experiment, "run_diagnosis", fail)
    experiment.run_once("A")
    saved = record_file.write_text.call_args.args[0]
    assert '"status": "failed"' in saved
    assert "test-key" not in saved
    with pytest.raises(FileExistsError):
        experiment.run_once("A")
    assert len(calls) == 1
