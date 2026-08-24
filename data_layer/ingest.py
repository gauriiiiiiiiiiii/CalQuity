"""Parse the supplied PDFs into a chunked, authority-tagged index.

Run once (``python -m data_layer.ingest``) to (re)build ``data/doc_index.json``.
The index is committed so the app boots without re-parsing PDFs.
"""
from __future__ import annotations

import json
import re

from pypdf import PdfReader

from core import config
from core.authority import SOURCE_REGISTRY


def _extract_text(path) -> str:
    reader = PdfReader(str(path))
    parts = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(parts)


def _chunk(text: str, max_chars: int = 700) -> list[str]:
    """Split into section-ish chunks. Prefer numbered headings, then paragraphs."""
    text = re.sub(r"[ \t]+", " ", text).strip()
    # Split on blank lines first.
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        if len(buf) + len(p) + 1 <= max_chars:
            buf = f"{buf}\n{p}".strip()
        else:
            if buf:
                chunks.append(buf)
            # A single very long paragraph gets hard-split.
            while len(p) > max_chars:
                chunks.append(p[:max_chars])
                p = p[max_chars:]
            buf = p
    if buf:
        chunks.append(buf)
    return chunks


def build_index() -> dict:
    records = []
    for filename, meta in SOURCE_REGISTRY.items():
        path = config.PACK_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing supplied document: {path}")
        text = _extract_text(path)
        for i, chunk in enumerate(_chunk(text)):
            records.append({
                "doc_id": meta.doc_id,
                "filename": meta.filename,
                "title": meta.title,
                "tier": meta.tier,
                "status": meta.status,
                "effective": meta.effective,
                "governs_account": meta.governs_account,
                "usable": meta.usable,
                "chunk_index": i,
                "text": chunk,
            })
    index = {"snapshot_source": "SOURCE_REGISTRY", "chunks": records}
    config.DOC_INDEX.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    return index


if __name__ == "__main__":
    idx = build_index()
    print(f"Built {config.DOC_INDEX} with {len(idx['chunks'])} chunks "
          f"from {len(SOURCE_REGISTRY)} documents.")
