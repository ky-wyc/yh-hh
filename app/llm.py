from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from app.repository import LLMConfig, Repository


SYSTEM_PROMPT_TEMPLATE = """你在 QQ 群里聊天。
你的名字是「{bot_name}」。
群友也可能用这些名字称呼你：{bot_aliases}。
要求：
1. 回复简洁、友好、具体。
2. 不确定时说明不确定，不要编造。
3. 不参与骚扰、诈骗、绕过平台限制、泄露隐私或危险行为。
4. 群聊里避免刷屏，长答案先给摘要。
5. 当介绍自己或被问到你是谁时，使用「{bot_name}」这个名字。
6. 不要自称“机器人”“AI”“语言模型”或“助手”，除非用户明确询问技术实现。
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
        prompt = await self._with_approved_memories(repo, prompt, group_id=group_id, user_id=user_id)
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
            bot_settings = await repo.get_bot_settings()
            system_prompt = build_system_prompt(bot_settings.bot_nickname_list)
            text, prompt_tokens, completion_tokens = await self._call_openai_compatible(
                config,
                prompt,
                system_prompt,
            )
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

    async def complete(
        self,
        repo: Repository,
        prompt: str,
        *,
        system_prompt: str,
        group_id: str = "",
        user_id: str = "",
        skill_name: str = "llm_complete",
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
            return LLMResult(text="", model=config.model, status="missing_api_key")

        started = time.perf_counter()
        try:
            text, prompt_tokens, completion_tokens = await self._call_openai_compatible(
                config,
                prompt,
                system_prompt,
            )
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
            return LLMResult(text="", model=config.model, status="failed")

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

    async def _call_openai_compatible(
        self,
        config: LLMConfig,
        prompt: str,
        system_prompt: str,
    ) -> tuple[str, int, int]:
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
                        {"role": "system", "content": system_prompt},
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

    async def _with_approved_memories(
        self,
        repo: Repository,
        prompt: str,
        *,
        group_id: str,
        user_id: str,
    ) -> str:
        memories = await repo.approved_memories_for_context(group_id=group_id, user_id=user_id)
        if not memories:
            return prompt
        memory_text = "\n".join(f"- {memory.content}" for memory in reversed(memories))
        return f"已确认记忆：\n{memory_text}\n\n当前问题：{prompt}"


def build_system_prompt(bot_nicknames: list[str]) -> str:
    names = [name.strip() for name in bot_nicknames if name.strip()]
    bot_name = names[0] if names else "助手"
    bot_aliases = "、".join(names) if names else bot_name
    return SYSTEM_PROMPT_TEMPLATE.format(bot_name=bot_name, bot_aliases=bot_aliases)
