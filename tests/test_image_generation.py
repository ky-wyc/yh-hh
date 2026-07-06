from __future__ import annotations

import httpx
import pytest

from app.image_generation import ImageConfig, ImageGenerationService, image_reference_from_text


def image_config() -> ImageConfig:
    return ImageConfig(
        provider="openai_compatible",
        base_url="https://relay.example/v1",
        api_key="secret",
        model="image2",
        size="1024x1024",
        timeout_seconds=30,
    )


@pytest.mark.asyncio
async def test_image_generation_accepts_openai_images_url_response():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/images/generations"
        return httpx.Response(200, json={"data": [{"url": "https://img.example/cat.png"}]})

    service = ImageGenerationService(httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    result = await service.generate(image_config(), "cat")

    assert result.status == "success"
    assert result.url == "https://img.example/cat.png"
    assert "[CQ:image,file=https://img.example/cat.png]" in result.message


@pytest.mark.asyncio
async def test_image_generation_falls_back_to_chat_completions_markdown_image():
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/v1/images/generations":
            return httpx.Response(404, json={"error": "not found"})
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "![image](https://img.example/from-chat.png)",
                        }
                    }
                ]
            },
        )

    service = ImageGenerationService(httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    result = await service.generate(image_config(), "cat")

    assert calls == ["/v1/images/generations", "/v1/chat/completions"]
    assert result.status == "success"
    assert result.url == "https://img.example/from-chat.png"
    assert "[CQ:image,file=https://img.example/from-chat.png]" in result.message


def test_image_reference_from_text_accepts_nested_json_text():
    text = '{"data":[{"url":"https://img.example/json.png"}]}'

    assert image_reference_from_text(text) == "https://img.example/json.png"
