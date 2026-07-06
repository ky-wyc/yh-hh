from __future__ import annotations

import hashlib
import math
import re


EMBEDDING_DIMENSION = 64


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


def text_terms(text: str) -> list[str]:
    normalized = text.strip().lower()
    return [term for term in re.split(r"\s+", normalized) if term]


def keyword_terms(text: str) -> list[str]:
    normalized = text.strip().lower()
    base_terms = [term for term in re.split(r"[\s,，。；;:：/\\|()（）\[\]{}<>《》\"'`]+", normalized) if term]
    terms: list[str] = []
    for term in base_terms:
        if term not in terms:
            terms.append(term)
        if re.search(r"[\u4e00-\u9fff]", term):
            for size in (3, 2):
                for index in range(0, max(0, len(term) - size + 1)):
                    ngram = term[index : index + size]
                    if ngram not in terms:
                        terms.append(ngram)
    if not terms and len(normalized) > 1:
        terms.append(normalized)
    return terms


def strong_identifier_terms(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{1,}", text.lower())


def embed_text(text: str, *, dimensions: int = EMBEDDING_DIMENSION) -> list[float]:
    vector = [0.0] * dimensions
    terms = text_terms(text)
    if not terms:
        return vector

    for term in terms:
        digest = hashlib.sha256(term.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [round(value / norm, 6) for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"


def knowledge_score(query: str, content: str) -> float:
    normalized_query = query.strip().lower()
    normalized_content = content.lower()
    if not normalized_query or not normalized_content:
        return 0.0

    score = 0.0
    if normalized_query in normalized_content:
        score += 300.0

    seen_terms = set()
    for term in keyword_terms(normalized_query):
        if term in seen_terms:
            continue
        seen_terms.add(term)
        if term and term in normalized_content:
            weight = 4.0 if len(term) >= 3 else 1.0
            score += weight + min(normalized_content.count(term), 10) * 0.5
    for term in strong_identifier_terms(normalized_query):
        if term and term in normalized_content:
            score += 80.0 + min(normalized_content.count(term), 10) * 2.0
            if re.search(rf"(^|[^a-zA-Z0-9._:-]){re.escape(term)}([^a-zA-Z0-9._:-]|$)", normalized_content):
                score += 120.0
    return score
