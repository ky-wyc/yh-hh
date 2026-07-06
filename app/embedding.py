from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.knowledge import EMBEDDING_DIMENSION, embed_text


@dataclass(slots=True)
class EmbeddingConfig:
    provider: str
    base_url: str
    api_key: str
    model: str
    dimensions: int
    timeout_seconds: float


class EmbeddingError(RuntimeError):
    pass


class EmbeddingService:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client

    async def embed(self, config: EmbeddingConfig, text: str) -> list[float]:
        provider = config.provider.strip().lower()
        if provider in {"", "local", "deterministic"}:
            return embed_text(text, dimensions=max(1, config.dimensions or EMBEDDING_DIMENSION))
        if provider == "openai_compatible":
            return await self._call_openai_compatible(config, text)
        raise EmbeddingError(f"unsupported embedding provider: {config.provider}")

    async def _call_openai_compatible(self, config: EmbeddingConfig, text: str) -> list[float]:
        if not config.api_key:
            raise EmbeddingError("embedding api key is not configured")
        if not config.model:
            raise EmbeddingError("embedding model is not configured")

        close_client = False
        client = self.client
        if client is None:
            client = httpx.AsyncClient(timeout=config.timeout_seconds)
            close_client = True
        try:
            body: dict[str, object] = {"model": config.model, "input": text}
            if config.dimensions > 0:
                body["dimensions"] = config.dimensions
            response = await client.post(
                f"{config.base_url.rstrip('/')}/embeddings",
                headers={"Authorization": f"Bearer {config.api_key}"},
                json=body,
            )
            response.raise_for_status()
            payload = response.json()
            vector = payload["data"][0]["embedding"]
            if not isinstance(vector, list):
                raise EmbeddingError("embedding response is missing vector data")
            return normalize_vector([float(value) for value in vector])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise EmbeddingError("invalid embedding response") from exc
        finally:
            if close_client:
                await client.aclose()


def normalize_vector(vector: list[float]) -> list[float]:
    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0:
        return vector
    return [round(value / norm, 6) for value in vector]
