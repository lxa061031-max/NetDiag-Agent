import json

import pytest

from src.knowledge import (
    KnowledgeValidationError,
    load_knowledge_base,
    search_fault_knowledge,
)


def test_knowledge_file_loads_with_traceable_sources() -> None:
    entries = load_knowledge_base()

    assert 10 <= len(entries) <= 20
    assert len({entry["id"] for entry in entries}) == len(entries)
    assert all(entry["source_name"] for entry in entries)
    assert all(str(entry["source_url"]).startswith("https://") for entry in entries)
    assert all(isinstance(entry["source_verified"], bool) for entry in entries)


def test_keyword_search_returns_at_most_three_json_results() -> None:
    result = search_fault_knowledge("latency_ms 延迟升高，同时出现丢包率异常")

    assert 1 <= result["match_count"] <= 3
    assert result["results"][0]["id"] == "latency-high"
    assert "延迟" in result["results"][0]["matched_keywords"]
    json.dumps(result, ensure_ascii=False, allow_nan=False)


def test_knowledge_search_handles_no_match() -> None:
    result = search_fault_knowledge("量子密钥分发设备校准")

    assert result["match_count"] == 0
    assert result["results"] == []
    assert "没有匹配" in result["message"]


@pytest.mark.parametrize("query", ["", None, 42, "x" * 501])
def test_knowledge_search_rejects_invalid_input(query: object) -> None:
    with pytest.raises(KnowledgeValidationError):
        search_fault_knowledge(query)
