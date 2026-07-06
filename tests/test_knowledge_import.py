from __future__ import annotations

from io import BytesIO

import pytest
from openpyxl import Workbook

from app.knowledge_import import parse_imported_knowledge


def workbook_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "FAQ"
    sheet.append(["Question", "Answer"])
    sheet.append(["Deploy", "Use Docker Compose"])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def test_parse_xlsx_import_extracts_sheet_rows():
    imported = parse_imported_knowledge("faq.xlsx", workbook_bytes())

    assert imported.title == "faq"
    assert imported.file_type == "xlsx"
    assert "Sheet: FAQ" in imported.content
    assert "Deploy | Use Docker Compose" in imported.content


def test_parse_csv_import_extracts_rows():
    imported = parse_imported_knowledge("rules.csv", b"Keyword,Action\nAds,Block\n")

    assert imported.title == "rules"
    assert imported.file_type == "csv"
    assert "Ads | Block" in imported.content


def test_parse_import_rejects_unsupported_file_type():
    with pytest.raises(ValueError, match="unsupported"):
        parse_imported_knowledge("archive.zip", b"hello")
