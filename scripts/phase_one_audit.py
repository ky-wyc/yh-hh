from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SENSITIVE_SUFFIXES = (
    ".env",
    ".pem",
    ".key",
    ".p12",
    ".crt",
    ".csr",
    ".jks",
    ".keystore",
)

ALLOWED_SENSITIVE_FILES = {
    ".env.example",
    ".env.production.example",
}


@dataclass(frozen=True)
class Evidence:
    path: str
    markers: tuple[str, ...]


def read_text(project_dir: Path, relative_path: str) -> str:
    path = project_dir / relative_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def evidence_exists(project_dir: Path, evidence: Evidence) -> bool:
    content = read_text(project_dir, evidence.path)
    return bool(content) and all(marker in content for marker in evidence.markers)


def check_evidence(
    project_dir: Path,
    name: str,
    category: str,
    evidences: list[Evidence],
    *,
    required: bool = True,
    message: str = "",
) -> dict[str, Any]:
    passed = [item for item in evidences if evidence_exists(project_dir, item)]
    missing = [item for item in evidences if item not in passed]
    if missing and required:
        status = "failed"
    elif missing:
        status = "warning"
    else:
        status = "passed"

    return {
        "name": name,
        "category": category,
        "status": status,
        "required": required,
        "message": message,
        "passed_evidence": [
            {"path": item.path, "markers": list(item.markers)}
            for item in passed
        ],
        "missing_evidence": [
            {"path": item.path, "markers": list(item.markers)}
            for item in missing
        ],
    }


def git_ls_files(project_dir: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def tracked_sensitive_files(project_dir: Path) -> list[str]:
    tracked = git_ls_files(project_dir)
    findings: list[str] = []
    for path in tracked:
        basename = Path(path).name
        if basename in ALLOWED_SENSITIVE_FILES:
            continue
        if basename.endswith(SENSITIVE_SUFFIXES):
            findings.append(path)
    return findings


def sensitive_file_check(project_dir: Path) -> dict[str, Any]:
    findings = tracked_sensitive_files(project_dir)
    return {
        "name": "tracked_sensitive_files",
        "category": "security",
        "status": "failed" if findings else "passed",
        "required": True,
        "message": "Git must not track runtime env files, private keys, or certificates.",
        "passed_evidence": [] if findings else [{"path": ".gitignore", "markers": ["*.pem", ".env"]}],
        "missing_evidence": [{"path": item, "markers": ["should_not_be_tracked"]} for item in findings],
    }


def manual_gate(
    name: str,
    category: str,
    message: str,
    evidence_hint: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "category": category,
        "status": "manual_required",
        "required": False,
        "message": message,
        "passed_evidence": [],
        "missing_evidence": [{"path": evidence_hint, "markers": ["manual_evidence_required"]}],
    }


def build_report(project_dir: Path) -> dict[str, Any]:
    checks = [
        check_evidence(
            project_dir,
            "memory_minimum",
            "memory",
            [
                Evidence("app/models.py", ("class MemoryRecord", "source", "confidence", "status")),
                Evidence("app/skills.py", ("remember", "forget", "memory_create_pending")),
                Evidence("app/admin_api.py", ("/memories", "memory_create", "memory_delete")),
                Evidence("web-admin/src/views/MemoriesView.vue", ("/memories", "/groups", "confidence")),
                Evidence("tests/test_admin_api.py", ("test_memories", "/api/memories")),
                Evidence("tests/test_router.py", ("pending", "approved", "memory")),
            ],
            message="Manual memory, admin memory management, and approved-only AI context evidence.",
        ),
        check_evidence(
            project_dir,
            "knowledge_minimum",
            "knowledge",
            [
                Evidence("app/models.py", ("class KnowledgeDocument", "source_file_name", "ai_summary", "class KnowledgeChunk")),
                Evidence("app/migrations.py", ("embedding_vector vector(64)", "knowledge_embedding_json")),
                Evidence("app/knowledge.py", ("knowledge_score", "keyword_terms", "strong_identifier_terms")),
                Evidence("app/knowledge_map.py", ("build_knowledge_map", "build_local_knowledge_map", "parse_map_json")),
                Evidence("app/knowledge_import.py", ("parse_imported_knowledge", "parse_workbook_documents", "ROWS_PER_DOCUMENT")),
                Evidence("app/embedding.py", ("EmbeddingService", "openai_compatible", "/embeddings")),
                Evidence("app/skills.py", ("kb", "kb_answer", "search_knowledge")),
                Evidence("app/admin_api.py", ("save_knowledge_file", "/knowledge-docs/import", "knowledge_doc_map_rebuild")),
                Evidence("web-admin/src/views/LlmSettingsView.vue", ("知识库 Embedding 设置", "/settings/embedding")),
                Evidence("web-admin/src/views/KnowledgeView.vue", ("导入文档", "AI目录", "重建目录")),
                Evidence("tests/test_knowledge_map.py", ("test_local_knowledge_map_extracts_identifiers_and_questions", "test_parse_map_json_accepts_fenced_json")),
                Evidence("tests/test_knowledge.py", ("embedding_json", "test_knowledge_search_uses_ai_map_keywords")),
                Evidence("tests/test_admin_api.py", ("test_knowledge_import_keeps_large_xlsx_as_single_original_file_preview", "test_knowledge_doc_map_can_be_rebuilt_from_admin")),
                Evidence("tests/test_knowledge_import.py", ("test_parse_xlsx_import_keeps_single_original_file_preview", "test_parse_csv_import_extracts_rows")),
                Evidence("tests/test_scheduler.py", ("knowledge_reindex", "test_knowledge_reindex_task_rebuilds_documents_and_records_history")),
                Evidence("tests/test_embedding.py", ("test_openai_compatible_embedding_request_shape", "api key")),
            ],
            message="Text knowledge base, chunking, vectorized search, group scope, and admin search evidence.",
        ),
        check_evidence(
            project_dir,
            "scheduled_tasks_and_daily_summary",
            "scheduler",
            [
                Evidence("app/models.py", ("class ScheduledTask", "class TaskRun")),
                Evidence("app/scheduler.py", ("daily_summary", "memory_summarize", "build_memory_candidate")),
                Evidence("app/admin_api.py", ("/scheduled-tasks", "scheduled_task_create", "scheduled_task_delete")),
                Evidence("web-admin/src/views/ScheduledTasksView.vue", ("/scheduled-tasks", "memory_summarize", "daily_summary")),
                Evidence("tests/test_scheduler.py", ("test_memory_summary_task_creates_pending_memory", "list_task_runs")),
                Evidence("tests/test_admin_api.py", ("test_scheduled_tasks_can_be_managed_from_admin", "/api/scheduled-tasks")),
            ],
            message="Once reminders, daily summary, cleanup tasks, and task run history evidence.",
        ),
        check_evidence(
            project_dir,
            "persistent_guess_game",
            "game",
            [
                Evidence("app/models.py", ("class GameState", "game_states")),
                Evidence("app/skills.py", ("guess", "start", "stop")),
                Evidence("app/repository.py", ("active_game", "create_guess_game", "expire_game_states")),
                Evidence("tests/test_router.py", ("test_guess_game_lifecycle_without_llm", "test_guess_game_persists_between_repositories")),
                Evidence("docs/一期开发状态.md", ("重启后可继续", "猜数字命令不调用大模型")),
            ],
            message="Group-scoped persisted guess game and expiration evidence.",
        ),
        check_evidence(
            project_dir,
            "admin_phase_one_management",
            "admin",
            [
                Evidence("web-admin/src/router.ts", ("KnowledgeView", "MemoriesView", "ScheduledTasksView", "SkillsView")),
                Evidence("web-admin/src/App.vue", ("index=\"/skills\"", "index=\"/knowledge\"", "index=\"/logs\"")),
                Evidence("web-admin/src/views/GroupsView.vue", ("skill", "welcome_enabled", "flood_enabled")),
                Evidence("web-admin/src/views/SkillsView.vue", ("private_supported", "risk_level", "toggleGroup")),
                Evidence("app/router.py", ("handle_private", "private_user_not_allowed", "PRIVATE_SUPPORTED_SKILLS")),
                Evidence("tests/test_router.py", ("test_private_command_replies_to_whitelisted_user", "test_private_unsupported_skill_is_rejected")),
                Evidence("web-admin/src/views/LogsView.vue", ("审计日志", "llm")),
                Evidence("app/admin_api.py", ("skill_setting_update", "onebot_status_out", "recovery_hint")),
                Evidence("web-admin/src/views/DashboardView.vue", ("activity_state", "恢复提示")),
                Evidence("tests/test_admin_api.py", ("test_onebot_status_exposes_offline_recovery_hint", "api_key")),
            ],
            message="Admin pages for group detail, skills, memory, knowledge, scheduled tasks, logs, and masking evidence.",
        ),
        check_evidence(
            project_dir,
            "moderation_controls",
            "moderation",
            [
                Evidence("app/skills.py", ("banword", "mute", "unmute")),
                Evidence("app/router.py", ("welcome_new_member", "flood_mute", "escalation_enabled")),
                Evidence("web-admin/src/views/KeywordRulesView.vue", ("/keyword-rules", "keyword", "response")),
                Evidence("web-admin/src/views/GroupsView.vue", ("近期违规", "moderationTemplates", "观察模式")),
                Evidence("web-admin/src/views/LogsView.vue", ("auditFilters", "target_id", "detail_json")),
                Evidence("tests/test_router.py", ("test_admin_can_mute_and_unmute_user", "test_flood_control_escalates_repeat_violations")),
                Evidence("tests/test_admin_api.py", ("welcome_enabled", "test_audit_logs_can_be_filtered_for_moderation_history")),
            ],
            message="Warnings, keyword rules, mute/unmute, welcome, flood control, escalation, permission and audit evidence.",
        ),
        check_evidence(
            project_dir,
            "backup_restore_drill_tooling",
            "ops",
            [
                Evidence("scripts/backup.sh", ("pg_dump", "BACKUP_DIR")),
                Evidence("scripts/restore_postgres.sh", ("FORCE", "psql")),
                Evidence("scripts/backup_restore_drill.py", ("restore_executed", "False")),
                Evidence("tests/test_backup_restore_drill.py", ("restore_executed", "backup_file_selected")),
                Evidence("docs/运维说明.md", ("备份恢复演练", "restore_executed")),
            ],
            message="Backup script, restore script, non-destructive drill report, tests, and ops docs evidence.",
        ),
        check_evidence(
            project_dir,
            "phase_one_docs",
            "docs",
            [
                Evidence("docs/一期产品蓝图.md", ("一期完成定义", "长期记忆", "知识库", "定时任务")),
                Evidence("docs/一期开发状态.md", ("当前进度", "已完成", "暂不纳入当前完成判定")),
                Evidence("docs/二期能力池.md", ("二期不是一次性完成的阶段", "一期")),
                Evidence("docs/QQ机器人系统设计方案.md", ("一期产品蓝图", "二期能力池")),
            ],
            message="Phase documents are split and cross-linked.",
        ),
        sensitive_file_check(project_dir),
        manual_gate(
            "one_week_real_group_operation",
            "acceptance",
            "Phase-one completion definition still needs one week of real target-group operation evidence.",
            "docs/一期完成定义证据清单.md",
        ),
        manual_gate(
            "real_restore_drill_evidence",
            "acceptance",
            "A true restore drill output and post-restore smoke result must be retained before claiming full completion.",
            "docs/一期完成定义证据清单.md",
        ),
    ]

    required_checks = [item for item in checks if item["required"]]
    failed = [item for item in required_checks if item["status"] == "failed"]
    warnings = [item for item in checks if item["status"] == "warning"]
    manual_required = [item for item in checks if item["status"] == "manual_required"]
    passed_required = [item for item in required_checks if item["status"] == "passed"]
    completion_percent = round((len(passed_required) / len(required_checks)) * 100, 2) if required_checks else 0

    if failed:
        status = "failed"
    elif manual_required:
        status = "passed_with_manual_gates"
    else:
        status = "passed"

    return {
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "project_dir": str(project_dir),
        "completion_percent_required_evidence": completion_percent,
        "required_total": len(required_checks),
        "required_passed": len(passed_required),
        "failed_count": len(failed),
        "warning_count": len(warnings),
        "manual_required_count": len(manual_required),
        "checks": checks,
        "notes": [
            "This audit is static and non-destructive; it does not connect to QQ, databases, or cloud services.",
            "Manual gates are intentionally not treated as local failures, but they block full phase-one completion claims.",
        ],
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a static phase-one completion evidence audit.")
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--report-file", default="")
    parser.add_argument("--strict-manual-gates", action="store_true")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    report = build_report(project_dir)
    if args.report_file:
        report_file = Path(args.report_file)
        if not report_file.is_absolute():
            report_file = project_dir / report_file
        write_report(report_file, report)
        print(f"Phase-one audit report written to {report_file}")
    print(
        "status={status} required={passed}/{total} failed={failed} manual_required={manual}".format(
            status=report["status"],
            passed=report["required_passed"],
            total=report["required_total"],
            failed=report["failed_count"],
            manual=report["manual_required_count"],
        )
    )
    if report["failed_count"] > 0:
        return 1
    if args.strict_manual_gates and report["manual_required_count"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
