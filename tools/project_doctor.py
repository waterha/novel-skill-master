#!/usr/bin/env python3
"""
project_doctor.py — 项目健康诊断（只读）

检查项目目录/文件完整性、JSON/SQLite 数据有效性。不写入任何文件。

触发条件（由 Claude 在诊断命令下调用）：
  master doctor / novel-doctor
    → python project_doctor.py check --project-root <路径>
      输出完整体检报告（目录/文件/JSON/SQLite/RAG 依赖）

  master doctor --deep
    → python project_doctor.py check --deep --project-root <路径>
      深度体检（全量检查 + MASTER_SETTING 契约校验）

  master status (健康摘要)
    → python project_doctor.py quick --project-root <路径>
      输出快速健康状态摘要

  novel-write Step 1 (前置验证)
    → python project_doctor.py preflight --project-root <路径>
      检查写章前置条件是否满足

返回值：JSON 到 stdout，Claude 解析后展示。
"""

import json
import sys
import os
import sqlite3
import subprocess
from pathlib import Path
from typing import Optional


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


# ─── 检查清单 ──────────────────────────────────────────────────────────────

REQUIRED_STRUCTURE = {
    ".webnovel/master_state.json": {
        "required": True,
        "phase": "any",
        "label": "项目状态文件",
        "impact": "项目无法定位",
    },
    ".webnovel/outline_manifest.json": {
        "required": True,
        "phase": "init",
        "label": "部卷结构清单",
        "impact": "无法校验部卷完整性",
    },
    "设定/": {
        "required": True,
        "phase": "setting",
        "label": "核心设定目录",
        "impact": "核心设定丢失",
    },
    ".story-system/": {
        "required": True,
        "phase": "init",
        "label": "Story System 目录",
        "impact": "Story System 不可用",
    },
    ".story-system/MASTER_SETTING.json": {
        "required": True,
        "phase": "init",
        "label": "设定契约主文件",
        "impact": "无法进行设定验证",
    },
    ".story-system/foreshadowing.json": {
        "required": True,
        "phase": "init",
        "label": "伏笔统一账本",
        "impact": "无法检查伏笔回收窗口",
    },
    "大纲/": {
        "required": False,
        "phase": "planning",
        "label": "大纲目录",
        "impact": "无法规划",
    },
    "正文/": {
        "required": False,
        "phase": "creation",
        "label": "正文目录",
        "impact": "无正文",
    },
    ".story-system/story_graph.json": {
        "required": False,
        "phase": "creation",
        "label": "知识图谱文件（v2.0）",
        "impact": "无法使用图谱上下文/一致性验证",
    },
    ".story-system/pacing_state.json": {
        "required": False,
        "phase": "creation",
        "label": "节奏状态文件（v2.0）",
        "impact": "无法进行节奏合规检查",
    },
    ".story-system/event_matrix.json": {
        "required": False,
        "phase": "creation",
        "label": "事件矩阵文件（v2.0）",
        "impact": "无法进行事件冷却管理",
    },
    ".webnovel/retrieval/next_plot_context.md": {
        "required": False,
        "phase": "creation",
        "label": "RAG写前上下文文件（v2.0）",
        "impact": "写前无法获得RAG检索建议",
    },
}

INDEX_DB_EXPECTED_TABLES = [
    "review_metrics",
    "chapter_meta",
    "entity_state",
    "foreshadowing",
]

MASTER_SETTING_SCHEMA = {
    "power_system": ["levels", "rules", "elements"],
    "characters": ["protagonist", "antagonist"],
    "world_rules": ["hard_rules", "soft_rules"],
    "timeline": ["current_year", "calendar_system"],
}


# ─── 检查函数 ────────────────────────────────────────────────────────────────

def check_file_structure(project_root: Path, current_phase: str = "any") -> dict:
    """检查目录/文件完整性"""
    results = {}
    for path_spec, info in REQUIRED_STRUCTURE.items():
        is_dir = path_spec.endswith("/")
        clean_path = path_spec.rstrip("/")
        full = project_root / clean_path

        exists = full.is_dir() if is_dir else full.exists()
        results[clean_path] = {
            "exists": exists,
            "required": info["required"],
            "phase": info["phase"],
            "label": info["label"],
            "impact": info["impact"],
            "status": "ok" if exists else ("warning" if not info["required"] else "error"),
        }

    return {
        "total": len(results),
        "ok": sum(1 for r in results.values() if r["status"] == "ok"),
        "warning": sum(1 for r in results.values() if r["status"] == "warning"),
        "error": sum(1 for r in results.values() if r["status"] == "error"),
        "items": results,
    }


def check_json_validity(project_root: Path) -> dict:
    """检查 JSON 文件格式"""
    json_files = [
        ".webnovel/master_state.json",
        ".webnovel/outline_manifest.json",
        ".story-system/foreshadowing.json",
        ".webnovel/idea_bank.json",
        ".story-system/MASTER_SETTING.json",
        ".story-system/contract_schema.json",
    ]

    results = {}
    for rel_path in json_files:
        full = project_root / rel_path
        result = {"exists": full.exists(), "valid": False, "error": None, "size": 0}
        if full.exists():
            result["size"] = full.stat().st_size
            try:
                data = json.loads(full.read_text(encoding="utf-8"))
                result["valid"] = True
                result["keys"] = list(data.keys()) if isinstance(data, dict) else []
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                result["error"] = str(e)
        results[rel_path] = result

    return results


def check_master_setting_integrity(project_root: Path) -> list:
    """★ MASTER_SETTING.json 设定契约完整性校验"""
    issues = []
    path = project_root / ".story-system" / "MASTER_SETTING.json"
    if not path.exists():
        return [{"severity": "error", "message": "MASTER_SETTING.json 不存在"}]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return [{"severity": "error", "message": f"MASTER_SETTING.json 解析失败: {e}"}]

    for section, required_fields in MASTER_SETTING_SCHEMA.items():
        section_data = data.get(section, {})
        missing = [f for f in required_fields if f not in section_data]
        if missing:
            issues.append({
                "severity": "warning",
                "section": section,
                "missing_fields": missing,
                "message": f"{section} 缺少字段: {', '.join(missing)}",
            })

    # 检查 power_system.levels 中的 limits
    levels = data.get("power_system", {}).get("levels", [])
    for i, level in enumerate(levels):
        if isinstance(level, dict) and "limits" not in level:
            issues.append({
                "severity": "warning",
                "section": f"power_system.levels[{i}]",
                "message": f"等级「{level.get('name', '未命名')}」缺少 limits 字段",
            })
        if isinstance(level, dict) and "capabilities" not in level:
            issues.append({
                "severity": "warning",
                "section": f"power_system.levels[{i}]",
                "message": f"等级「{level.get('name', '未命名')}」缺少 capabilities 字段",
            })

    return issues


def check_index_db(project_root: Path) -> dict:
    """检查 index.db SQLite 数据库"""
    path = project_root / ".webnovel" / "index.db"
    result = {"exists": path.exists(), "tables": {}, "error": None}

    if not path.exists():
        return result

    try:
        conn = sqlite3.connect(str(path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        for table in INDEX_DB_EXPECTED_TABLES:
            result["tables"][table] = {
                "exists": table in existing_tables,
                "status": "ok" if table in existing_tables else "missing",
            }

        # 检查 review_metrics 表结构
        if "review_metrics" in existing_tables:
            cursor.execute("PRAGMA table_info(review_metrics)")
            columns = [row[1] for row in cursor.fetchall()]
            result["tables"]["review_metrics"]["columns"] = columns

        conn.close()
    except sqlite3.Error as e:
        result["error"] = str(e)

    return result


def check_python_deps() -> dict:
    """检查 Python 依赖"""
    deps = {
        "flask": False,
    }
    try:
        import flask
        deps["flask"] = True
    except ImportError:
        pass

    # 检查 Dash 脚本可用性
    script_dir = Path(__file__).parent
    dash_script = script_dir / "dash_tracker.py"
    deps["dash_tracker"] = dash_script.exists()

    anti_ai_script = script_dir / "anti_ai_check.py"
    deps["anti_ai_check"] = anti_ai_script.exists()

    return deps


def check_rag_config(project_root: Path) -> dict:
    """检查 RAG 配置"""
    results = {
        "reference_search_py": False,
        "csv_files": [],
        "embedding_available": False,
    }

    ref_search = project_root / "references" / "search" / "reference_search.py"
    results["reference_search_py"] = ref_search.exists()

    csv_files = list(project_root.glob("**/*.csv"))
    results["csv_files"] = [str(f.relative_to(project_root)) for f in csv_files[:10]]

    # 简单检查 sentence-transformers
    try:
        import sentence_transformers
        results["embedding_available"] = True
    except ImportError:
        pass

    return results


def check_writing_preflight(
    project_root: Path,
    part: Optional[int] = None,
    volume: Optional[int] = None,
    chapter: Optional[int] = None,
) -> dict:
    """检查写章前置条件"""
    checks = {}

    # 1. MASTER_SETTING.json 存在
    ms = project_root / ".story-system" / "MASTER_SETTING.json"
    checks["master_setting_exists"] = ms.exists()

    # 2. 分层大纲必须通过结构校验；指定章节时检查完整写前记忆栈
    guard = Path(__file__).with_name("outline_guard.py")
    guard_args = [sys.executable, str(guard)]
    if part is not None and volume is not None and chapter is not None:
        guard_args.extend([
            "preflight", "--project-root", str(project_root),
            "--part", str(part), "--volume", str(volume), "--chapter", str(chapter),
        ])
    else:
        guard_args.extend(["status", "--project-root", str(project_root)])
    guard_result = subprocess.run(guard_args, capture_output=True, text=True, encoding="utf-8")
    checks["hierarchical_outline_valid"] = guard_result.returncode == 0
    try:
        outline_report = json.loads(guard_result.stdout)
    except json.JSONDecodeError:
        outline_report = {"error": guard_result.stderr.strip() or "结构校验无有效输出"}

    # 3. 角色状态快照存在
    char_states = project_root / ".story-system" / "character_states.json"
    checks["character_states_exists"] = char_states.exists()

    # 3.5 伏笔账本存在且格式有效
    foreshadow_tool = Path(__file__).with_name("foreshadowing_tracker.py")
    foreshadow_result = subprocess.run(
        [sys.executable, str(foreshadow_tool), "validate", "--project-root", str(project_root)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    checks["foreshadowing_ledger_valid"] = foreshadow_result.returncode == 0

    # 4. 有可用的 dash 趋势数据（如果没有也无妨）
    dash_trend = project_root / ".story-system" / "dash_trend.json"
    checks["dash_trend_exists"] = dash_trend.exists()

    # 5. 无 blocker
    state_file = project_root / ".webnovel" / "master_state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            checks["has_blockers"] = len(state.get("blockers", [])) > 0
            checks["blocker_count"] = len(state.get("blockers", []))
        except:
            checks["has_blockers"] = False
            checks["blocker_count"] = 0
    else:
        checks["has_blockers"] = False
        checks["blocker_count"] = 0

    all_pass = (
        checks["master_setting_exists"]
        and checks["hierarchical_outline_valid"]
        and checks["character_states_exists"]
        and checks["foreshadowing_ledger_valid"]
        and not checks["has_blockers"]
    )

    return {
        "all_checks_pass": all_pass,
        "checks": checks,
        "outline_report": outline_report,
    }


# ─── 命令实现 ────────────────────────────────────────────────────────────────

def cmd_check(args: list):
    """project_doctor.py check — 完整体检"""
    project_root = None
    deep = "--deep" in args

    for i, a in enumerate(args):
        if a in ("--project-root", "--project_root", "--root") and i + 1 < len(args):
            project_root = Path(args[i + 1])

    if not project_root:
        project_root = Path.cwd()

    if not project_root.exists():
        print(json.dumps({"error": f"项目根目录不存在: {project_root}"}, ensure_ascii=False))
        sys.exit(1)

    report = {}

    # 1. 文件结构
    report["file_structure"] = check_file_structure(project_root)

    # 2. JSON 有效性
    report["json_validity"] = check_json_validity(project_root)

    # 3. MASTER_SETTING 契约校验
    report["master_setting_integrity"] = check_master_setting_integrity(project_root)

    # 4. SQLite
    report["index_db"] = check_index_db(project_root)

    # 5. Python 依赖
    report["python_deps"] = check_python_deps()

    # 深度模式：额外检查
    if deep:
        report["rag_config"] = check_rag_config(project_root)
        report["writing_preflight"] = check_writing_preflight(project_root)
        # Dashboard 构建产物
        dashboard_dist = project_root / "dist"
        report["dashboard_build"] = {
            "exists": dashboard_dist.exists(),
            "index_html": (dashboard_dist / "index.html").exists() if dashboard_dist.exists() else False,
        }

    # 健康摘要
    errors = 0
    warnings = 0

    if "file_structure" in report:
        errors += report["file_structure"].get("error", 0)
        warnings += report["file_structure"].get("warning", 0)

    json_results = report.get("json_validity", {})
    for path, info in json_results.items():
        if info.get("exists") and not info.get("valid"):
            errors += 1

    ms_integrity = report.get("master_setting_integrity", [])
    for issue in ms_integrity:
        if issue.get("severity") == "error":
            errors += 1
        else:
            warnings += 1

    health = "ok" if errors == 0 else ("warning" if warnings > 0 else "error")

    report["summary"] = {
        "health": health,
        "errors": errors,
        "warnings": warnings,
        "status_icon": "🟢" if health == "ok" else ("🟡" if health == "warning" else "🔴"),
    }

    print(json.dumps(report, ensure_ascii=False))


def cmd_quick(args: list):
    """project_doctor.py quick — 快速健康摘要"""
    project_root = None
    for i, a in enumerate(args):
        if a in ("--project-root", "--project_root", "--root") and i + 1 < len(args):
            project_root = Path(args[i + 1])
    if not project_root:
        project_root = Path.cwd()

    # 只检查最核心的几项
    checks = {
        "file_integrity": check_file_structure(project_root).get("error", 0) == 0,
        "state_json_valid": False,
        "master_setting_valid": False,
    }

    state_file = project_root / ".webnovel" / "master_state.json"
    if state_file.exists():
        try:
            json.loads(state_file.read_text(encoding="utf-8"))
            checks["state_json_valid"] = True
        except:
            pass

    ms = project_root / ".story-system" / "MASTER_SETTING.json"
    if ms.exists():
        try:
            json.loads(ms.read_text(encoding="utf-8"))
            checks["master_setting_valid"] = True
        except:
            pass

    has_blockers = False
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            has_blockers = len(state.get("blockers", [])) > 0
        except:
            pass

    all_green = all(checks.values()) and not has_blockers
    print(json.dumps({
        "health": "ok" if all_green else "issues",
        "checks": checks,
        "has_blockers": has_blockers,
    }, ensure_ascii=False))


def cmd_preflight(args: list):
    """project_doctor.py preflight — 写章前置检查"""
    project_root = None
    for i, a in enumerate(args):
        if a in ("--project-root", "--project_root", "--root") and i + 1 < len(args):
            project_root = Path(args[i + 1])
    if not project_root:
        project_root = Path.cwd()

    part = None
    volume = None
    chapter = None
    for i, a in enumerate(args):
        if a == "--part" and i + 1 < len(args):
            part = int(args[i + 1])
        elif a == "--volume" and i + 1 < len(args):
            volume = int(args[i + 1])
        elif a == "--chapter" and i + 1 < len(args):
            chapter = int(args[i + 1])

    result = check_writing_preflight(project_root, part, volume, chapter)

    if result["all_checks_pass"]:
        result["suggest"] = "✅ 前置条件全部满足，可以开始写章"
    else:
        failed = [k for k, v in result["checks"].items() if v is False and k != "dash_trend_exists"]
        result["suggest"] = f"❌ 以下条件未满足: {', '.join(failed)}"

    print(json.dumps(result, ensure_ascii=False))


# ─── CLI 入口 ──────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("用法: project_doctor.py <command> [args...]", file=sys.stderr)
        print("命令: check, quick, preflight", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "check": cmd_check,
        "quick": cmd_quick,
        "preflight": cmd_preflight,
    }

    if command not in commands:
        print(f"未知命令: {command}", file=sys.stderr)
        sys.exit(1)

    commands[command](args)


if __name__ == "__main__":
    main()
