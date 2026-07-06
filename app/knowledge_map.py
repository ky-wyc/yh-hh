from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.knowledge import keyword_terms, strong_identifier_terms


@dataclass(slots=True)
class KnowledgeMap:
    summary: str
    keywords: list[str]
    questions: list[str]
    status: str


def build_local_knowledge_map(title: str, content: str, source_locator: str = "") -> KnowledgeMap:
    text = " ".join(part for part in (title, source_locator, content[:3000]) if part)
    keywords = unique_terms(strong_identifier_terms(text) + keyword_terms(text), limit=20)
    return KnowledgeMap(
        summary=summarize_locally(title, content, source_locator),
        keywords=keywords,
        questions=infer_questions(keywords),
        status="local",
    )


async def build_knowledge_map(repo, llm, *, title: str, content: str, source_locator: str = "") -> KnowledgeMap:
    config = await repo.get_llm_config()
    if llm is None or not config.api_key:
        return build_local_knowledge_map(title, content, source_locator)

    prompt = "\n".join(
        [
            "把下面的知识库文档整理成结构化目录索引。",
            "只输出 JSON，不要 Markdown，不要解释。",
            "JSON 字段：summary 字符串，keywords 字符串数组，questions 字符串数组。",
            "summary 用一句话说明资料主要内容。",
            "keywords 提取适合检索的关键词、编号、字段名、实体名，最多 20 个。",
            "questions 写这段资料适合回答的问题类型，最多 8 个。",
            "",
            f"标题：{title}",
            f"位置：{source_locator}",
            "原文：",
            content[:6000],
        ]
    )
    result = await llm.complete(
        repo,
        prompt,
        system_prompt="你是知识库文档索引器，只负责生成可检索目录 JSON。",
        skill_name="knowledge_map",
    )
    if result.status != "success":
        fallback = build_local_knowledge_map(title, content, source_locator)
        fallback.status = result.status or "local"
        return fallback
    parsed = parse_map_json(result.text)
    if parsed is None:
        fallback = build_local_knowledge_map(title, content, source_locator)
        fallback.status = "parse_failed"
        return fallback
    return parsed


def parse_map_json(text: str) -> KnowledgeMap | None:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.S)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict):
        return None

    summary = str(payload.get("summary") or "").strip()
    keywords = clean_string_list(payload.get("keywords"), limit=20)
    questions = clean_string_list(payload.get("questions"), limit=8)
    if not summary and not keywords and not questions:
        return None
    return KnowledgeMap(
        summary=summary[:1000],
        keywords=keywords,
        questions=questions,
        status="ai",
    )


def clean_string_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        text = str(item).strip()
        if text and text not in items:
            items.append(text[:100])
        if len(items) >= limit:
            break
    return items


def unique_terms(values: list[str], *, limit: int) -> list[str]:
    terms = []
    for value in values:
        text = value.strip()
        if len(text) < 2:
            continue
        if text not in terms:
            terms.append(text[:100])
        if len(terms) >= limit:
            break
    return terms


def summarize_locally(title: str, content: str, source_locator: str) -> str:
    first_lines = [line.strip() for line in content.splitlines() if line.strip()]
    sample = "；".join(first_lines[:3])
    prefix = title
    if source_locator:
        prefix = f"{prefix}（{source_locator}）"
    if sample:
        return f"{prefix}：{sample}"[:1000]
    return prefix[:1000]


def infer_questions(keywords: list[str]) -> list[str]:
    return [f"查询 {keyword} 相关信息" for keyword in keywords[:5]]
