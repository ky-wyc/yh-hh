from __future__ import annotations

import json

from scripts.smoke_check import (
    REQUIRED_ADMIN_LITE_AUDIT_ACTIONS,
    REQUIRED_MVP_CORE_LOG_REASONS,
    missing_audit_actions,
    missing_message_reasons,
    write_report,
)


def test_missing_audit_actions_reports_absent_admin_lite_actions():
    records = [{"action": "warn"}]

    assert missing_audit_actions(records, REQUIRED_ADMIN_LITE_AUDIT_ACTIONS) == {"banword_add"}


def test_missing_audit_actions_accepts_complete_admin_lite_actions():
    records = [{"action": "warn"}, {"action": "banword_add"}, {"action": "group_update"}]

    assert missing_audit_actions(records, REQUIRED_ADMIN_LITE_AUDIT_ACTIONS) == set()


def test_missing_message_reasons_reports_absent_mvp_core_logs():
    records = [{"drop_reason": "command:ping"}, {"drop_reason": "command:help"}]

    assert missing_message_reasons(records, REQUIRED_MVP_CORE_LOG_REASONS) == {
        "command:ai",
        "command:dice",
    }


def test_missing_message_reasons_accepts_complete_mvp_core_logs():
    records = [
        {"drop_reason": "command:ping"},
        {"drop_reason": "command:help"},
        {"drop_reason": "command:dice"},
        {"drop_reason": "command:ai"},
        {"drop_reason": "command:warn"},
    ]

    assert missing_message_reasons(records, REQUIRED_MVP_CORE_LOG_REASONS) == set()


def test_write_report_creates_utf8_json_file(tmp_path):
    report_path = tmp_path / "nested" / "smoke-report.json"

    write_report(str(report_path), {"status": "passed", "message": "中文正常"})

    assert json.loads(report_path.read_text(encoding="utf-8")) == {
        "status": "passed",
        "message": "中文正常",
    }
