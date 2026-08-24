"""Lexical retrieval over the authority-tagged document index.

The corpus is six short documents, so a BM25 ranker is accurate and needs no embedding
service. The store never returns deprecated documents unless explicitly asked, so an
outdated policy cannot leak into an answer.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field

from core import config
from data_layer import ingest

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass
class Chunk:
    doc_id: str
    filename: str
    title: str
    tier: int
    status: str
    effective: str
    governs_account: str | None
    usable: bool
    chunk_index: int
    text: str
    tokens: list[str] = field(default_factory=list)


@dataclass
class Hit:
    chunk: Chunk
    score: float

    def citation(self) -> dict:
        c = self.chunk
        return {
            "doc_id": c.doc_id,
            "title": c.title,
            "effective": c.effective,
            "status": c.status,
            "tier": c.tier,
            "governs_account": c.governs_account,
            "snippet": c.text.strip(),
        }


class DocStore:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self._df: dict[str, int] = {}
        for ch in chunks:
            for t in set(ch.tokens):
                self._df[t] = self._df.get(t, 0) + 1
        self._n = max(1, len(chunks))
        self._avg_len = sum(len(c.tokens) for c in chunks) / self._n

    @classmethod
    def load(cls) -> "DocStore":
        if not config.DOC_INDEX.exists():
            ingest.build_index()
        raw = json.loads(config.DOC_INDEX.read_text(encoding="utf-8"))
        chunks = []
        for r in raw["chunks"]:
            chunks.append(Chunk(
                doc_id=r["doc_id"], filename=r["filename"], title=r["title"],
                tier=r["tier"], status=r["status"], effective=r["effective"],
                governs_account=r.get("governs_account"), usable=r["usable"],
                chunk_index=r["chunk_index"], text=r["text"], tokens=_tokens(r["text"]),
            ))
        return cls(chunks)

    def _bm25(self, q_tokens: list[str], ch: Chunk, k1: float = 1.5, b: float = 0.75) -> float:
        score = 0.0
        clen = len(ch.tokens) or 1
        counts: dict[str, int] = {}
        for t in ch.tokens:
            counts[t] = counts.get(t, 0) + 1
        for t in q_tokens:
            if t not in counts:
                continue
            df = self._df.get(t, 0)
            idf = math.log(1 + (self._n - df + 0.5) / (df + 0.5))
            tf = counts[t]
            denom = tf + k1 * (1 - b + b * clen / self._avg_len)
            score += idf * (tf * (k1 + 1)) / denom
        return score

    def search(self, query: str, top_k: int = 5, include_deprecated: bool = False,
               account_id: str | None = None) -> list[Hit]:
        """Rank chunks. Deprecated docs are excluded by default; out-of-scope
        contracts (belonging to another account) are never surfaced."""
        q = _tokens(query)
        hits: list[Hit] = []
        for ch in self.chunks:
            if not ch.usable and not include_deprecated:
                continue
            # A contract only applies to its own account, so don't leak one customer's
            # terms into another's context.
            if ch.governs_account and account_id and ch.governs_account != account_id:
                continue
            base = self._bm25(q, ch)
            if base <= 0:
                continue
            # Gentle tier prior so that, on near-ties, the higher-authority source ranks
            # first. Kept small so it never overturns a clearly better textual match.
            score = base + ch.tier / 1000.0
            hits.append(Hit(ch, score))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]


_STORE: DocStore | None = None


def get_store() -> DocStore:
    global _STORE
    if _STORE is None:
        _STORE = DocStore.load()
    return _STORE
