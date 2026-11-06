"""Shared pytest isolation from developer-machine secrets and services."""

from __future__ import annotations

import pytest

from src.storage.configuration import DATABASE_CONFIG_NAMES


@pytest.fixture(autouse=True)
def isolate_mssql_environment(monkeypatch):
    """Keep Streamlit UI tests independent of a locally configured MSSQL."""
    for name in DATABASE_CONFIG_NAMES:
        monkeypatch.delenv(name, raising=False)

