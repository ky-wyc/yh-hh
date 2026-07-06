from __future__ import annotations

import json

import httpx
import pytest

from app.embedding import EmbeddingConfig, EmbeddingError, EmbeddingService


def config(**overrides) -> EmbeddingConfig:
    values = {
        "provider": "openai_compatible",
        "base_url": "https://embed.example/v1",
        "api_key": "secret",
        "model": "embed-model",
        "dimensions": 64,
        "timeout_seconds": 30.0,
    }
    values.update(overrides)
    return EmbeddingConfig(**values)


async def test_local_embedding_provider_is_deterministic():
    service = EmbeddingService()
    local_config = config(provider="local", api_key="", dimensions=32)

    first = await service.embed(local_config, "部署 测试")
    second = await service.embed(local_config, "部署 测试")

    assert first == second
    assert len(first) == 32


async def test_openai_compatible_embedding_request_shape():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"data": [{"embedding": [3.0, 4.0]}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = EmbeddingService(client)

    vector = await service.embed(config(), "hello")

    assert vector == [0.6, 0.8]
    assert requests[0].url == "https://embed.example/v1/embeddings"
    assert requests[0].headers["authorization"] == "Bearer secret"
    body = json.loads(requests[0].content)
    assert body == {"model": "embed-model", "input": "hello", "dimensions": 64}
    await client.aclose()


async def test_openai_compatible_embedding_requires_api_key():
    service = EmbeddingService()

    with pytest.raises(EmbeddingError, match="api key"):
        await service.embed(config(api_key=""), "hello")
