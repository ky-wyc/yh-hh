from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class ImageConfig:
    provider: str
    base_url: str
    api_key: str
    model: str
    size: str
    timeout_seconds: float


@dataclass(slots=True)
class ImageResult:
    message: str
    model: str
    status: str = "success"
    url: str = ""


class ImageGenerationError(RuntimeError):
    pass


class ImageGenerationService:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client

    async def generate(self, config: ImageConfig, prompt: str) -> ImageResult:
        provider = config.provider.strip().lower()
        if provider != "openai_compatible":
            return ImageResult(
                message=f"不支持的生图 Provider：{config.provider}",
                model=config.model,
                status="failed",
            )
        if not config.api_key:
            return ImageResult(
                message="生图 API Key 还没有配置，请先在后台设置。",
                model=config.model,
                status="missing_api_key",
            )
        if not config.model:
            return ImageResult(
                message="生图模型还没有配置。",
                model=config.model,
                status="failed",
            )

        close_client = False
        client = self.client
        if client is None:
            client = httpx.AsyncClient(timeout=config.timeout_seconds)
            close_client = True
        try:
            response = await client.post(
                f"{config.base_url.rstrip('/')}/images/generations",
                headers={"Authorization": f"Bearer {config.api_key}"},
                json={
                    "model": config.model,
                    "prompt": prompt,
                    "n": 1,
                    "size": config.size,
                },
            )
            response.raise_for_status()
            payload = response.json()
            image_url = extract_image_url(payload)
            if image_url:
                return ImageResult(
                    message=f"已生成图片：\n[CQ:image,file={image_url}]",
                    model=config.model,
                    url=image_url,
                )
            b64_json = extract_image_b64(payload)
            if b64_json:
                return ImageResult(
                    message=f"已生成图片：\n[CQ:image,file=base64://{b64_json}]",
                    model=config.model,
                    url="base64",
                )
            raise ImageGenerationError("image response is missing url or b64_json")
        except Exception as exc:
            return ImageResult(
                message=f"生图失败：{str(exc)[:200]}",
                model=config.model,
                status="failed",
            )
        finally:
            if close_client:
                await client.aclose()


def extract_image_url(payload: dict) -> str:
    try:
        url = payload["data"][0].get("url")
    except (KeyError, IndexError, TypeError, AttributeError):
        return ""
    return url if isinstance(url, str) else ""


def extract_image_b64(payload: dict) -> str:
    try:
        b64_json = payload["data"][0].get("b64_json")
    except (KeyError, IndexError, TypeError, AttributeError):
        return ""
    return b64_json if isinstance(b64_json, str) else ""
