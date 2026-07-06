from __future__ import annotations

import json

from sqlalchemy import select

from app.embedding import EmbeddingConfig
from app.knowledge import EMBEDDING_DIMENSION, cosine_similarity, embed_text, knowledge_score
from app.models import KnowledgeChunk
from app.repository import Repository


class FakeEmbeddingService:
    def __init__(self, vector: list[float] | None = None, error: Exception | None = None):
        self.vector = vector or [1.0, 0.0, 0.0]
        self.error = error
        self.calls: list[tuple[EmbeddingConfig, str]] = []

    async def embed(self, config: EmbeddingConfig, text: str) -> list[float]:
        self.calls.append((config, text))
        if self.error is not None:
            raise self.error
        return self.vector


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


async def test_knowledge_search_uses_ai_map_keywords(repo):
    await repo.create_knowledge_document(
        group_id="10001",
        title="库存说明",
        content="这段正文只写普通库存注意事项。",
        enabled=True,
        created_by="admin",
        ai_summary="包含特殊物料的目录摘要",
        ai_keywords=["ZX-900", "冷链物料"],
        ai_questions=["ZX-900 应该如何处理？"],
        ai_index_status="local",
    )

    results = await repo.search_knowledge(group_id="10001", query="ZX-900", limit=3)

    assert results
    assert results[0].title == "库存说明"
    assert results[0].score > 0


def test_keyword_score_prioritizes_exact_identifiers():
    exact = knowledge_score("SKU-205", "Row 206\nSku: SKU-205\nName: Item 205")
    loose = knowledge_score("SKU-205", "Row 6\nSku: SKU-005\nName: Item 5")

    assert exact > loose + 100


async def test_knowledge_index_uses_configured_embedding_service(repo):
    fake = FakeEmbeddingService([0.5, 0.5])
    custom_repo = Repository(repo.session, repo.settings, fake)
    await custom_repo.update_embedding_config(
        {
            "provider": "openai_compatible",
            "base_url": "https://embed.example/v1",
            "api_key": "secret",
            "model": "embed-model",
            "dimensions": 2,
        }
    )

    document = await custom_repo.create_knowledge_document(
        group_id="10001",
        title="外部向量",
        content="这段文字将使用外部 embedding。",
        enabled=True,
        created_by="admin",
    )
    result = await repo.session.execute(
        select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)
    )
    chunk = result.scalar_one()

    assert document.index_status == "vectorized"
    assert json.loads(chunk.embedding_json) == [0.5, 0.5]
    assert fake.calls[0][0].provider == "openai_compatible"
    assert fake.calls[0][0].model == "embed-model"


async def test_knowledge_index_records_embedding_degradation(repo):
    fake = FakeEmbeddingService(error=RuntimeError("embedding unavailable"))
    custom_repo = Repository(repo.session, repo.settings, fake)
    await custom_repo.update_embedding_config({"provider": "openai_compatible", "api_key": "secret"})

    document = await custom_repo.create_knowledge_document(
        group_id="10001",
        title="失败索引",
        content="这段文字会索引失败。",
        enabled=True,
        created_by="admin",
    )

    assert document.index_status == "completed"
    assert document.chunk_count >= 1
    assert "embedding unavailable" in document.index_error
