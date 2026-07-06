from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.phase_one_audit import (
    Evidence,
    build_report,
    check_evidence,
    sensitive_file_check,
    write_report,
)


PROJECT_DIR = Path(__file__).resolve().parents[1]


def test_check_evidence_reports_missing_markers(tmp_path):
    source = tmp_path / "sample.py"
    source.write_text("class Example:\n    pass\n", encoding="utf-8")

    report = check_evidence(
        tmp_path,
        "sample",
        "unit",
        [Evidence("sample.py", ("class Example", "missing_marker"))],
    )

    assert report["status"] == "failed"
    assert report["missing_evidence"][0]["path"] == "sample.py"


def test_phase_one_audit_passes_required_current_repo_evidence():
    report = build_report(PROJECT_DIR)

    assert report["status"] == "passed_with_manual_gates"
    assert report["failed_count"] == 0
    assert report["required_passed"] == report["required_total"]
    assert report["manual_required_count"] == 2
    assert {item["name"] for item in report["checks"] if item["status"] == "manual_required"} == {
        "one_week_real_group_operation",
        "real_restore_drill_evidence",
    }


def test_phase_one_audit_does_not_allow_tracked_sensitive_files():
    report = sensitive_file_check(PROJECT_DIR)

    assert report["status"] == "passed"
    assert report["missing_evidence"] == []


def test_phase_one_audit_cli_writes_report(tmp_path):
    report_path = tmp_path / "phase-one-audit.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/phase_one_audit.py",
            "--project-dir",
            str(PROJECT_DIR),
            "--report-file",
            str(report_path),
        ],
        cwd=PROJECT_DIR,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert "status=passed_with_manual_gates" in result.stdout
    assert report["failed_count"] == 0
    assert report["manual_required_count"] == 2


def test_write_report_creates_parent_directory(tmp_path):
    report_path = tmp_path / "nested" / "phase-one-audit.json"
    report = {"status": "passed_with_manual_gates"}

    write_report(report_path, report)

    assert json.loads(report_path.read_text(encoding="utf-8")) == report
