from __future__ import annotations

import hashlib
import json
from typing import Any

from .fab_ready import KnowledgeItem, KnowledgeType


class KnowledgeStore:
    """Append-only recursive knowledge substrate (K).

    K accumulates across generations. Search learns from verified successes
    and failures. Append-only: items are never modified or deleted.
    """
    def __init__(self) -> None:
        self._items: list[KnowledgeItem] = []
        self._index: dict[str, int] = {}  # knowledge_id -> position

    def append(self, item: KnowledgeItem) -> str:
        """Append a knowledge item. Returns the knowledge_id."""
        if not item.knowledge_id:
            item.knowledge_id = self._make_id(item)
        if not item.content_hash:
            item.content_hash = self._hash_content(item.content)
        self._index[item.knowledge_id] = len(self._items)
        self._items.append(item)
        return item.knowledge_id

    def _make_id(self, item: KnowledgeItem) -> str:
        blob = json.dumps({
            "type": item.knowledge_type.value,
            "candidate": item.source_candidate,
            "gen": item.generation,
            "content": item.content,
        }, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    def _hash_content(self, content: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]

    def get(self, knowledge_id: str) -> KnowledgeItem | None:
        pos = self._index.get(knowledge_id)
        return self._items[pos] if pos is not None else None

    def by_type(self, ktype: KnowledgeType) -> list[KnowledgeItem]:
        return [i for i in self._items if i.knowledge_type == ktype]

    def by_candidate(self, candidate_id: str) -> list[KnowledgeItem]:
        return [i for i in self._items if i.source_candidate == candidate_id]

    def verified_solutions(self) -> list[KnowledgeItem]:
        return self.by_type(KnowledgeType.VERIFIED_SOLUTION)

    def verified_failures(self) -> list[KnowledgeItem]:
        return self.by_type(KnowledgeType.VERIFIED_FAILURE)

    def verified_primitives(self) -> list[KnowledgeItem]:
        return self.by_type(KnowledgeType.VERIFIED_PRIMITIVE)

    def failure_signatures(self) -> list[dict[str, Any]]:
        return [i.content for i in self.by_type(KnowledgeType.FAILURE_SIGNATURE)]

    def all(self) -> list[KnowledgeItem]:
        return list(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def is_append_only(self) -> bool:
        """Verify store integrity: items unchanged since append."""
        for item in self._items:
            if item.content_hash != self._hash_content(item.content):
                return False
        return True
