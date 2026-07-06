from __future__ import annotations

import json
import re
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


IMAGE_INTENT_MARKERS = (
    "\u753b",
    "\u753b\u4e00\u5f20",
    "\u753b\u4e2a",
    "\u751f\u6210\u56fe",
    "\u751f\u6210\u56fe\u7247",
    "\u751f\u56fe",
    "\u505a\u5f20\u56fe",
    "\u505a\u4e00\u5f20\u56fe",
    "\u6765\u5f20\u56fe",
    "\u56fe\u7247",
    "draw",
    "image",
    "generate image",
)


def should_auto_image_generation(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    if normalized.startswith(("/image", "/draw", "/\u751f\u56fe")):
        return True
    return any(marker in normalized for marker in IMAGE_INTENT_MARKERS)


def extract_image_prompt(text: str, bot_qq: str = "", bot_nicknames: list[str] | None = None) -> str:
    prompt = text.strip()
    if bot_qq:
        prompt = prompt.replace(f"[CQ:at,qq={bot_qq}]", "")
    for name in bot_nicknames or []:
        if name:
            prompt = prompt.replace(name, "")
    prompt = re.sub(r"^/(image|draw|\u751f\u56fe)\s*", "", prompt, flags=re.IGNORECASE)
    for pattern in (
        r"^\s*\u8bf7?\s*\u5e2e\u6211\s*",
        r"^\s*\u5e2e\u6211\s*",
        r"^\s*\u7ed9\u6211\s*",
        r"^\s*\u8bf7\s*",
    ):
        prompt = re.sub(pattern, "", prompt)
    for marker in sorted(IMAGE_INTENT_MARKERS, key=len, reverse=True):
        prompt = re.sub(rf"^\s*{re.escape(marker)}\s*", "", prompt, flags=re.IGNORECASE)
    prompt = prompt.strip(" \t\r\n:：，,。.")
    return prompt or text.strip()


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
            return ImageResult(message="生图模型还没有配置。", model=config.model, status="failed")

        close_client = False
        client = self.client
        if client is None:
            client = httpx.AsyncClient(timeout=config.timeout_seconds)
            close_client = True
        try:
            last_error = ""
            try:
                payload = await self._call_images_generations(config, prompt, client)
                image_ref = extract_image_reference(payload)
                if image_ref:
                    return image_result(config.model, image_ref)
                last_error = "images/generations response missing image data"
            except httpx.HTTPStatusError as exc:
                last_error = f"images/generations HTTP {exc.response.status_code}"
                if exc.response.status_code not in {400, 404, 405, 422}:
                    raise

            payload = await self._call_chat_completions(config, prompt, client)
            image_ref = extract_image_reference(payload)
            if image_ref:
                return image_result(config.model, image_ref)
            raise ImageGenerationError(f"{last_error}; chat/completions response missing image data")
        except Exception as exc:
            return ImageResult(
                message=f"生图失败：{str(exc)[:200]}",
                model=config.model,
                status="failed",
            )
        finally:
            if close_client:
                await client.aclose()

    async def _call_images_generations(
        self,
        config: ImageConfig,
        prompt: str,
        client: httpx.AsyncClient,
    ) -> dict:
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
        return response.json()

    async def _call_chat_completions(
        self,
        config: ImageConfig,
        prompt: str,
        client: httpx.AsyncClient,
    ) -> dict:
        response = await client.post(
            f"{config.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {config.api_key}"},
            json={
                "model": config.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            },
        )
        response.raise_for_status()
        return response.json()


def image_result(model: str, image_ref: str) -> ImageResult:
    if image_ref.startswith("data:image/"):
        _, _, encoded = image_ref.partition(",")
        image_ref = f"base64://{encoded}"
    return ImageResult(
        message=f"已生成图片：\n[CQ:image,file={image_ref}]",
        model=model,
        url="base64" if image_ref.startswith("base64://") else image_ref,
    )


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
    return f"base64://{b64_json}" if isinstance(b64_json, str) else ""


def extract_image_reference(payload: dict) -> str:
    direct = extract_image_url(payload) or extract_image_b64(payload)
    if direct:
        return direct
    for text in extract_text_candidates(payload):
        found = image_reference_from_text(text)
        if found:
            return found
    return ""


def extract_text_candidates(value) -> list[str]:
    texts: list[str] = []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        for item in value:
            texts.extend(extract_text_candidates(item))
        return texts
    if not isinstance(value, dict):
        return texts

    for key in ("output_text", "text", "content", "url", "b64_json"):
        item = value.get(key)
        if isinstance(item, str):
            texts.append(item)
        elif isinstance(item, list):
            texts.extend(extract_text_candidates(item))

    image_url = value.get("image_url")
    if isinstance(image_url, dict):
        url = image_url.get("url")
        if isinstance(url, str):
            texts.append(url)
    elif isinstance(image_url, str):
        texts.append(image_url)

    for key in ("choices", "message", "output", "data"):
        texts.extend(extract_text_candidates(value.get(key)))
    return texts


def image_reference_from_text(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            payload = None
        if payload is not None:
            found = extract_image_reference(payload)
            if found:
                return found

    data_uri = re.search(r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+", stripped)
    if data_uri:
        return re.sub(r"\s+", "", data_uri.group(0))
    markdown = re.search(r"!\[[^\]]*]\((https?://[^)\s]+)\)", stripped)
    if markdown:
        return markdown.group(1)
    cq_image = re.search(r"\[CQ:image,file=([^\]]+)]", stripped)
    if cq_image:
        return cq_image.group(1)
    url = re.search(r"https?://\S+", stripped)
    if url:
        return url.group(0).rstrip("),.，。")
    return ""
