from __future__ import annotations

import csv
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import PurePath

from openpyxl import load_workbook


SUPPORTED_EXTENSIONS = {".txt", ".md", ".csv", ".xlsx", ".xlsm"}
MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_CONTENT_CHARS = 200_000


@dataclass(slots=True)
class ImportedKnowledge:
    title: str
    content: str
    file_type: str


def parse_imported_knowledge(filename: str, data: bytes, title: str = "") -> ImportedKnowledge:
    if len(data) > MAX_IMPORT_BYTES:
        raise ValueError("file is larger than 5MB")
    suffix = PurePath(filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError("unsupported knowledge file type")

    if suffix in {".txt", ".md"}:
        content = decode_text(data)
    elif suffix == ".csv":
        content = parse_csv(data)
    else:
        content = parse_workbook(data)

    content = normalize_content(content)
    if not content:
        raise ValueError("imported file has no readable text")
    if len(content) > MAX_CONTENT_CHARS:
        content = content[:MAX_CONTENT_CHARS].rstrip()

    fallback_title = PurePath(filename or "imported-document").stem[:255] or "imported-document"
    return ImportedKnowledge(
        title=(title.strip() or fallback_title)[:255],
        content=content,
        file_type=suffix.lstrip("."),
    )


def decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def parse_csv(data: bytes) -> str:
    text = decode_text(data)
    reader = csv.reader(StringIO(text))
    lines = []
    for row in reader:
        values = [str(cell).strip() for cell in row if str(cell).strip()]
        if values:
            lines.append(" | ".join(values))
    return "\n".join(lines)


def parse_workbook(data: bytes) -> str:
    workbook = load_workbook(BytesIO(data), read_only=True, data_only=True)
    sections = []
    for sheet in workbook.worksheets:
        rows = []
        for row in sheet.iter_rows(values_only=True):
            values = [format_cell(value) for value in row]
            values = [value for value in values if value]
            if values:
                rows.append(" | ".join(values))
        if rows:
            sections.append("\n".join([f"Sheet: {sheet.title}", *rows]))
    workbook.close()
    return "\n\n".join(sections)


def format_cell(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_content(content: str) -> str:
    lines = [line.strip() for line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()
