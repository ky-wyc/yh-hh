from __future__ import annotations

import json

from sqlalchemy import select

from app.knowledge import EMBEDDING_DIMENSION, cosine_similarity, embed_text
from app.models import KnowledgeChunk


def test_embedding_is_normalized_and_deterministic():
    first = embed_text("部署 测试")
    second = embed_text("部署 测试")

    assert first == second
    assert len(first) == EMBEDDING_DIMENSION
    assert 0.99 <= cosine_similarity(first, first) <= 1.01


async def test_knowledge_chunks_store_embeddings(repo):
    document = await repo.create_knowledge_document(
        group_id="10001",
        title="部署手册",
        content="部署前需要执行 preflight 检查。",
        enabled=True,
        created_by="admin",
    )
    result = await repo.session.execute(
        select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)
    )
    chunk = result.scalar_one()
    embedding = json.loads(chunk.embedding_json)

    assert document.index_status == "vectorized"
    assert len(embedding) == EMBEDDING_DIMENSION
    assert cosine_similarity(embed_text("preflight"), embedding) > 0


async def test_knowledge_search_uses_vectorized_chunks(repo):
    await repo.create_knowledge_document(
        group_id="10001",
        title="部署手册",
        content="preflight check should run before deployment.",
        enabled=True,
        created_by="admin",
    )

    results = await repo.search_knowledge(group_id="10001", query="preflight", limit=3)

    assert results
    assert results[0].title == "部署手册"
    assert results[0].score > 0
