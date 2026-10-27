"""本地网络故障知识库读取与关键词检索。"""

from .repository import (
    MAX_KNOWLEDGE_QUERY_CHARS,
    KnowledgeValidationError,
    load_knowledge_base,
    search_fault_knowledge,
)

__all__ = [
    "MAX_KNOWLEDGE_QUERY_CHARS",
    "KnowledgeValidationError",
    "load_knowledge_base",
    "search_fault_knowledge",
]
