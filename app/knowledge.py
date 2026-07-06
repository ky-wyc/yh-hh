from __future__ import annotations

import re


def chunk_text(text: str, *, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunks.append(normalized[start:end].strip())
        if end == len(normalized):
            break
        start = max(end - overlap, start + 1)
    return [chunk for chunk in chunks if chunk]


def knowledge_score(query: str, content: str) -> float:
    normalized_query = query.strip().lower()
    normalized_content = content.lower()
    if not normalized_query or not normalized_content:
        return 0.0

    score = 0.0
    if normalized_query in normalized_content:
        score += 100.0

    terms = [term for term in re.split(r"\s+", normalized_query) if term]
    if len(terms) <= 1 and len(normalized_query) > 1:
        terms.extend(char for char in normalized_query if not char.isspace())

    seen_terms = set()
    for term in terms:
        if term in seen_terms:
            continue
        seen_terms.add(term)
        if term and term in normalized_content:
            score += 1.0 + min(normalized_content.count(term), 10) * 0.2
    return score
