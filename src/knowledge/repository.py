"""读取固定本地 JSON，并执行轻量级关键词检索。"""

from __future__ import annotations

import json
from pathlib import Path


KNOWLEDGE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "knowledge" / "network_faults.json"
)
MAX_KNOWLEDGE_QUERY_CHARS = 500
MAX_KNOWLEDGE_RESULTS = 3
REQUIRED_FIELDS = {
    "id", "title", "keywords", "symptom", "possible_causes",
    "troubleshooting_steps", "limitations", "source_name", "source_url",
    "source_verified",
}


class KnowledgeValidationError(ValueError):
    """知识库内容或查询不符合约束。"""


def load_knowledge_base() -> list[dict[str, object]]:
    """只读取项目内固定知识文件，不接受外部路径。"""

    with KNOWLEDGE_PATH.open("r", encoding="utf-8") as knowledge_file:
        entries = json.load(knowledge_file)
    if not isinstance(entries, list):
        raise KnowledgeValidationError("知识库根节点必须是数组。")
    seen_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or not REQUIRED_FIELDS.issubset(entry):
            raise KnowledgeValidationError("知识条目缺少必需字段。")
        entry_id = entry["id"]
        if not isinstance(entry_id, str) or not entry_id or entry_id in seen_ids:
            raise KnowledgeValidationError("知识条目 id 必须是唯一非空字符串。")
        seen_ids.add(entry_id)
        for field in ("keywords", "possible_causes", "troubleshooting_steps"):
            value = entry[field]
            if not isinstance(value, list) or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                raise KnowledgeValidationError(
                    f"知识条目字段 {field} 必须是非空字符串数组。"
                )
    return entries


def search_fault_knowledge(query: object) -> dict[str, object]:
    """按标题、关键词和症状匹配，最多返回三条可追溯知识。"""

    if not isinstance(query, str) or not query.strip():
        raise KnowledgeValidationError("query 必须是非空字符串。")
    normalized_query = query.strip().casefold()
    if len(normalized_query) > MAX_KNOWLEDGE_QUERY_CHARS:
        raise KnowledgeValidationError(
            f"query 不能超过 {MAX_KNOWLEDGE_QUERY_CHARS} 个字符。"
        )

    ranked: list[tuple[int, str, dict[str, object], list[str]]] = []
    for entry in load_knowledge_base():
        matched_keywords = [
            keyword
            for keyword in entry["keywords"]
            if keyword.casefold() in normalized_query
        ]
        score = len(matched_keywords) * 5
        if str(entry["title"]).casefold() in normalized_query:
            score += 3
        if str(entry["symptom"]).casefold() in normalized_query:
            score += 1
        if score:
            ranked.append((score, str(entry["id"]), entry, matched_keywords))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    results = []
    for _, _, entry, matched_keywords in ranked[:MAX_KNOWLEDGE_RESULTS]:
        results.append(
            {
                "id": entry["id"],
                "title": entry["title"],
                "matched_keywords": matched_keywords,
                "troubleshooting_steps": list(entry["troubleshooting_steps"]),
                "limitations": entry["limitations"],
                "source": {
                    "name": entry["source_name"],
                    "url": entry["source_url"],
                    "verified": bool(entry["source_verified"]),
                },
            }
        )

    payload: dict[str, object] = {
        "query": query.strip(),
        "match_count": len(results),
        "results": results,
        "message": (
            f"找到 {len(results)} 条相关知识。"
            if results
            else "本地知识库中没有匹配条目，不能提供知识来源。"
        ),
    }
    json.dumps(payload, ensure_ascii=False, allow_nan=False)
    return payload
