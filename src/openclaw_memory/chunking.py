from __future__ import annotations

from typing import List

from .models import MemoryChunk


def split_text(text: str, chunk_chars: int = 1000, overlap_chars: int = 150) -> List[str]:
    if chunk_chars <= 0:
        raise ValueError("chunk_chars must be > 0")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must be >= 0")
    if not text:
        return []
    out: List[str] = []
    step = max(1, chunk_chars - overlap_chars)
    start = 0
    while start < len(text):
        out.append(text[start : start + chunk_chars])
        start += step
    return out


def chunk_entity_text(entity_id: str, text: str, chunk_chars: int = 1000, overlap_chars: int = 150) -> List[MemoryChunk]:
    return [
        MemoryChunk.from_text(entity_id, idx, part)
        for idx, part in enumerate(split_text(text, chunk_chars=chunk_chars, overlap_chars=overlap_chars))
    ]
