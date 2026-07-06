from __future__ import annotations

import json

from scripts.backup_restore_drill import build_report, safe_identifier, write_report


def test_safe_identifier_accepts_ops_script_identifiers():
    assert safe_identifier("qqbot")
    assert safe_identifier("qqbot_2026")
    assert not safe_identifier("qqbot-prod")
    assert not safe_identifier("qqbot.prod")
    assert not safe_identifier("")


def test_backup_restore_drill_report_passes_with_sql_backup(tmp_path):
    project_dir = tmp_path
    env_file = project_dir / ".env"
    backup_dir = project_dir / "data" / "backups"
    napcat_config = project_dir / "data" / "napcat" / "config"
    napcat_qq = project_dir / "data" / "napcat" / "qq"
    backup_dir.mkdir(parents=True)
    napcat_config.mkdir(parents=True)
    napcat_qq.mkdir(parents=True)
    env_file.write_text("POSTGRES_USER=qqbot\nPOSTGRES_DB=qqbot\n", encoding="utf-8")
    backup_file = backup_dir / "postgres-20260706-120000.sql"
    backup_file.write_text("-- PostgreSQL database dump\nCREATE TABLE users(id integer);\n", encoding="utf-8")

    report = build_report(project_dir, env_file, backup_file)

    assert report["status"] == "passed"
    assert report["restore_executed"] is False
    assert report["failed_count"] == 0
    assert "restore_postgres.sh" in report["restore_command"]
    assert str(backup_file) in report["restore_command"]


def test_backup_restore_drill_report_fails_without_backup(tmp_path):
    project_dir = tmp_path
    env_file = project_dir / ".env"
    (project_dir / "data").mkdir()
    env_file.write_text("POSTGRES_USER=qqbot\nPOSTGRES_DB=qqbot\n", encoding="utf-8")

    report = build_report(project_dir, env_file)

    assert report["status"] == "failed"
    assert any(item["name"] == "backup_dir_exists" for item in report["checks"])
    assert any(item["name"] == "backup_file_selected" and item["status"] == "failed" for item in report["checks"])


def test_write_report_creates_private_json_report(tmp_path):
    report_path = tmp_path / "reports" / "backup-drill.json"
    report = {"status": "passed", "restore_executed": False}

    write_report(report_path, report)

    assert json.loads(report_path.read_text(encoding="utf-8")) == report
