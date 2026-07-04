from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from app.repository import LLMConfig, Repository


SYSTEM_PROMPT = """你是一个 QQ 群机器人助手。
要求：
1. 回复简洁、友好、具体。
2. 不确定时说明不确定，不要编造。
3. 不参与骚扰、诈骗、绕过平台限制、泄露隐私或危险行为。
4. 群聊里避免刷屏，长答案先给摘要。
"""


@dataclass(slots=True)
class LLMResult:
    text: str
    model: str = ""
    status: str = "success"


class LLMService:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client

    async def chat(
        self,
        repo: Repository,
        prompt: str,
        *,
        group_id: str = "",
        user_id: str = "",
        skill_name: str = "ai",
    ) -> LLMResult:
        config = await repo.get_llm_config()
        if not config.api_key:
            await repo.save_llm_usage(
                config=config,
                group_id=group_id,
                user_id=user_id,
                skill_name=skill_name,
                status="missing_api_key",
            )
            return LLMResult(text="大模型还没配置好：请先在后台设置 API Key。", model=config.model)

        started = time.perf_counter()
        try:
            text, prompt_tokens, completion_tokens = await self._call_openai_compatible(config, prompt)
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            await repo.save_llm_usage(
                config=config,
                group_id=group_id,
                user_id=user_id,
                skill_name=skill_name,
                latency_ms=latency_ms,
                status="failed",
                error_message=str(exc),
            )
            return LLMResult(text="大模型调用失败，请稍后再试。", model=config.model, status="failed")

        latency_ms = int((time.perf_counter() - started) * 1000)
        await repo.save_llm_usage(
            config=config,
            group_id=group_id,
            user_id=user_id,
            skill_name=skill_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
        )
        return LLMResult(text=text, model=config.model)

    async def _call_openai_compatible(self, config: LLMConfig, prompt: str) -> tuple[str, int, int]:
        close_client = False
        client = self.client
        if client is None:
            client = httpx.AsyncClient(timeout=config.timeout_seconds)
            close_client = True
        try:
            response = await client.post(
                f"{config.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {config.api_key}"},
                json={
                    "model": config.model,
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"].get("content") or ""
            usage = payload.get("usage") or {}
            return content or "我这边没有生成出有效回复。", int(
                usage.get("prompt_tokens") or 0
            ), int(usage.get("completion_tokens") or 0)
        finally:
            if close_client:
                await client.aclose()

