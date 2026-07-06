from __future__ import annotations

from app.knowledge_map import build_local_knowledge_map, parse_map_json


def test_local_knowledge_map_extracts_identifiers_and_questions():
    knowledge_map = build_local_knowledge_map(
        "Inventory FAQ",
        "Row 2\nSku: SKU-205\nName: Item 205\nNote: Use cold storage",
        "Sheet Inventory rows 2-2",
    )

    assert knowledge_map.status == "local"
    assert "Inventory FAQ" in knowledge_map.summary
    assert "sku-205" in knowledge_map.keywords
    assert knowledge_map.questions


def test_parse_map_json_accepts_fenced_json():
    parsed = parse_map_json(
        """```json
{"summary":"部署说明","keywords":["Docker","Compose"],"questions":["如何部署？"]}
```"""
    )

    assert parsed is not None
    assert parsed.status == "ai"
    assert parsed.summary == "部署说明"
    assert parsed.keywords == ["Docker", "Compose"]
