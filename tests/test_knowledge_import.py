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


def large_workbook_bytes(row_count: int = 205) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Inventory"
    sheet.append(["Sku", "Name"])
    for index in range(1, row_count + 1):
        sheet.append([f"SKU-{index:03d}", f"Item {index}"])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def test_parse_xlsx_import_extracts_sheet_rows():
    imported = parse_imported_knowledge("faq.xlsx", workbook_bytes())

    assert imported.title == "faq / Sheet FAQ / rows 2-2"
    assert imported.file_type == "xlsx"
    assert imported.report.source_count == 1
    assert imported.report.imported_row_count == 1
    assert imported.report.document_count == 1
    assert "Source: Sheet FAQ" in imported.content
    assert "Question: Deploy" in imported.content
    assert "Answer: Use Docker Compose" in imported.content


def test_parse_xlsx_import_splits_large_sheets():
    imported = parse_imported_knowledge("inventory.xlsx", large_workbook_bytes())

    assert imported.report.imported_row_count == 205
    assert imported.report.document_count == 5
    assert len(imported.documents) == 5
    assert imported.documents[0].title.endswith("rows 2-51")
    assert imported.documents[-1].title.endswith("rows 202-206")
    assert "SKU-205" in imported.documents[-1].content


def test_parse_csv_import_extracts_rows():
    imported = parse_imported_knowledge("rules.csv", b"Keyword,Action\nAds,Block\n")

    assert imported.title == "rules / CSV / rows 2-2"
    assert imported.file_type == "csv"
    assert imported.report.imported_row_count == 1
    assert "Keyword: Ads" in imported.content
    assert "Action: Block" in imported.content


def test_parse_import_rejects_unsupported_file_type():
    with pytest.raises(ValueError, match="unsupported"):
        parse_imported_knowledge("archive.zip", b"hello")
