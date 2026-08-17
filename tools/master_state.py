#!/usr/bin/env python3
"""State manager for the hierarchical novel workflow."""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


PHASES = ["ideation", "setting", "planning", "creation", "finalization", "maintenance"]
STAGES_BY_PHASE = {
    "ideation": ["topic"],
    "setting": ["settings", "tagline"],
    "planning": ["init", "book_outline", "part_outline", "plan", "arc"],
    "creation": ["chapter_outline", "writing", "review", "cover"],
    "finalization": ["finish"],
    "maintenance": ["maintain"],
}
STAGE_LABELS = {
    "topic": "选题策划",
    "settings": "核心设定",
    "tagline": "标签简介",
    "init": "项目初始化",
    "book_outline": "全书总纲",
    "part_outline": "部纲与卷方向",
    "plan": "卷纲规划",
    "arc": "剧情单元",
    "chapter_outline": "分章大纲",
    "writing": "正文创作",
    "review": "质量审查",
    "cover": "封面设计",
    "finish": "分层收尾",
    "maintain": "日常维护",
}
PHASE_LABELS = {
    "ideation": "构思期",
    "setting": "设定期",
    "planning": "规划期",
    "creation": "创作期",
    "finalization": "收尾期",
    "maintenance": "维护期",
}
PER_PART_STAGES = {"part_outline"}
PER_VOLUME_STAGES = {"plan", "arc", "chapter_outline"}
PROGRESS_KEYS = {
    "part_outline": "parts_done",
    "plan": "plans_done",
    "arc": "arcs_done",
    "chapter_outline": "chapters_done",
}


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def all_stages() -> List[str]:
    return [stage for phase in PHASES for stage in STAGES_BY_PHASE[phase]]


def default_progress() -> dict:
    return {
        "book_outline_done": False,
        "parts_done": [],
        "volume_directions_done": [],
        "plans_done": [],
        "arcs_done": [],
        "chapters_done": [],
    }


def default_state(project_name: str = "未命名项目") -> dict:
    return {
        "version": 3,
        "project_name": project_name,
        "current_phase": "ideation",
        "current_stage": "topic",
        "phase_status": {phase: "pending" for phase in PHASES},
        "stage_status": {stage: "pending" for stage in all_stages()},
        "current_part": 1,
        "current_volume": 1,
        "current_chapter": 0,
        "target_chapter": 0,
        "total_parts": 0,
        "total_volumes": 0,
        "target_words": 0,
        "total_words": 0,
        "structure": {"parts": []},
        "outline_progress": default_progress(),
        "writing_progress": {"chapters_written": [], "chapters_reviewed": []},
        "closure_progress": {"volumes_closed": [], "parts_closed": [], "book_closed": False},
        "blockers": [],
        "pending_decisions": [],
        "last_command": "",
        "last_executed_at": now(),
    }


def find_project_root() -> Path:
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".webnovel" / "master_state.json").exists():
            return parent
    return cwd


def state_path() -> Path:
    return find_project_root() / ".webnovel" / "master_state.json"


def migrate_state(state: dict) -> dict:
    state.setdefault("version", 3)
    state.setdefault("total_parts", 0)
    state.setdefault("total_volumes", 0)
    state.setdefault("current_part", 1)
    state.setdefault("current_volume", 1)
    state.setdefault("structure", {"parts": []})
    state.setdefault("phase_status", {})
    state.setdefault("stage_status", {})
    for phase in PHASES:
        state["phase_status"].setdefault(phase, "pending")
    for stage in all_stages():
        state["stage_status"].setdefault(stage, "pending")
    progress = state.setdefault("outline_progress", {})
    for key, value in default_progress().items():
        progress.setdefault(key, value)
    state.setdefault("writing_progress", {"chapters_written": [], "chapters_reviewed": []})
    state.setdefault("closure_progress", {"volumes_closed": [], "parts_closed": [], "book_closed": False})
    state.setdefault("blockers", [])
    state.setdefault("pending_decisions", [])
    return state


def load_state() -> dict:
    path = state_path()
    try:
        return migrate_state(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        emit({"error": f"master_state.json 不存在于 {path.parent}", "suggest": "运行 master init"}, 1)
    except json.JSONDecodeError as exc:
        emit({"error": f"master_state.json 解析失败: {exc}"}, 1)
    return {}


def save_state(state: dict) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    state["version"] = 3
    state["last_executed_at"] = now()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def emit(data: dict, code: int = 0) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))
    raise SystemExit(code)


def value_after(args: List[str], flag: str, default: Optional[str] = None) -> Optional[str]:
    if flag in args:
        index = args.index(flag)
        if index + 1 < len(args):
            return args[index + 1]
    return default


def int_after(args: List[str], flag: str, default: Optional[int] = None) -> Optional[int]:
    raw = value_after(args, flag)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        emit({"error": f"{flag} 必须是整数"}, 2)
    return default


def parse_counts(raw: Optional[str], parts: Optional[int]) -> List[int]:
    if raw is None:
        emit({"error": "缺少 --volumes-per-part，例如 12,10,8"}, 2)
    try:
        counts = [int(item.strip()) for item in raw.split(",") if item.strip()]
    except ValueError:
        emit({"error": "--volumes-per-part 必须是逗号分隔的正整数"}, 2)
    if not counts or any(count < 1 for count in counts):
        emit({"error": "每部至少需要一卷"}, 2)
    if parts is not None and len(counts) != parts:
        emit({"error": f"部数为 {parts}，卷数配置却有 {len(counts)} 组"}, 2)
    return counts


def configure_structure(state: dict, counts: List[int]) -> None:
    parts = []
    next_volume = 1
    for part_no, count in enumerate(counts, start=1):
        end = next_volume + count - 1
        parts.append({
            "part": part_no,
            "volume_start": next_volume,
            "volume_end": end,
            "volume_count": count,
        })
        next_volume = end + 1
    state["total_parts"] = len(parts)
    state["total_volumes"] = sum(counts)
    state["structure"] = {"parts": parts}
    state["current_part"] = 1
    state["current_volume"] = 1


def expected_parts(state: dict) -> List[int]:
    return list(range(1, state.get("total_parts", 0) + 1))


def expected_volumes(state: dict) -> List[int]:
    return list(range(1, state.get("total_volumes", 0) + 1))


def part_for_volume(state: dict, volume: int) -> Optional[int]:
    for item in state.get("structure", {}).get("parts", []):
        if item["volume_start"] <= volume <= item["volume_end"]:
            return item["part"]
    return None


def volumes_for_part(state: dict, part: int) -> List[int]:
    for item in state.get("structure", {}).get("parts", []):
        if item["part"] == part:
            return list(range(item["volume_start"], item["volume_end"] + 1))
    return []


def missing(expected: List[int], done: List[int]) -> List[int]:
    return [item for item in expected if item not in done]


def validate_state(state: dict) -> List[str]:
    issues = []
    if state.get("current_phase") not in PHASES:
        issues.append(f"未知阶段: {state.get('current_phase')}")
    total_parts = state.get("total_parts", 0)
    total_volumes = state.get("total_volumes", 0)
    structure_parts = state.get("structure", {}).get("parts", [])
    if total_parts < 1 or total_volumes < 1:
        issues.append("部卷结构尚未配置")
    elif len(structure_parts) != total_parts:
        issues.append("structure.parts 与 total_parts 不一致")
    progress = state.get("outline_progress", {})
    for key in default_progress():
        if key not in progress:
            issues.append(f"outline_progress 缺少 {key}")
    for key in ("parts_done",):
        invalid = [item for item in progress.get(key, []) if item not in expected_parts(state)]
        if invalid:
            issues.append(f"{key} 含无效编号: {invalid}")
    for key in ("volume_directions_done", "plans_done", "arcs_done", "chapters_done"):
        invalid = [item for item in progress.get(key, []) if item not in expected_volumes(state)]
        if invalid:
            issues.append(f"{key} 含无效编号: {invalid}")
    return issues


def find_next_step(state: dict) -> Tuple[str, str]:
    if state.get("blockers"):
        blocker = state["blockers"][0]
        return "blocked", blocker.get("description", str(blocker))
    if state.get("pending_decisions"):
        return "decide", f"有 {len(state['pending_decisions'])} 项待决策"

    for stage in ("topic", "settings", "tagline", "init"):
        if state["stage_status"].get(stage) != "completed":
            phase = next(p for p, stages in STAGES_BY_PHASE.items() if stage in stages)
            return phase, stage

    if state.get("total_parts", 0) < 1 or state.get("total_volumes", 0) < 1:
        return "planning", "configure --parts N --volumes-per-part A,B"

    progress = state["outline_progress"]
    if not progress.get("book_outline_done"):
        return "planning", "book_outline"

    remaining_parts = missing(expected_parts(state), progress.get("parts_done", []))
    if remaining_parts:
        return "planning", f"part_outline --part {remaining_parts[0]}"

    closed_volumes = state["closure_progress"].get("volumes_closed", [])
    closed_parts = state["closure_progress"].get("parts_closed", [])
    for part in expected_parts(state):
        if part not in closed_parts and not missing(volumes_for_part(state, part), closed_volumes):
            return "finalization", f"finish --level part --part {part}"

    open_volumes = missing(expected_volumes(state), closed_volumes)
    if open_volumes:
        volume = open_volumes[0]
        part = part_for_volume(state, volume) or 1
        state["current_part"] = part
        state["current_volume"] = volume
        if volume not in progress.get("plans_done", []):
            return "planning", f"plan --volume {volume}"
        if volume not in progress.get("arcs_done", []):
            return "planning", f"arc --volume {volume}"
        if volume not in progress.get("chapters_done", []):
            return "creation", f"chapter_outline --volume {volume}"
        return "creation", f"writing --part {part} --volume {volume}"

    remaining_part_closures = missing(expected_parts(state), closed_parts)
    if remaining_part_closures:
        return "finalization", f"finish --level part --part {remaining_part_closures[0]}"
    if not state["closure_progress"].get("book_closed"):
        return "finalization", "finish --level book"
    return "completed", "all_done"


def refresh_current(state: dict) -> None:
    phase, action = find_next_step(state)
    if phase in PHASES:
        state["current_phase"] = phase
        state["current_stage"] = action.split()[0]
        for name in PHASES:
            if state["phase_status"].get(name) != "completed":
                state["phase_status"][name] = "active" if name == phase else "pending"
        if state["current_stage"] in state["stage_status"]:
            state["stage_status"][state["current_stage"]] = "active"
    elif phase == "completed":
        state["current_phase"] = "maintenance"
        state["current_stage"] = "maintain"
        state["phase_status"]["finalization"] = "completed"
        state["phase_status"]["maintenance"] = "active"


def cmd_init(args: List[str]) -> None:
    force = "--force" in args
    path = state_path()
    if path.exists() and not force:
        emit({"status": "exists", "message": f"项目状态已存在: {path}"})
    state = default_state(value_after(args, "--name", "未命名项目") or "未命名项目")
    raw_counts = value_after(args, "--volumes-per-part")
    if raw_counts:
        parts = int_after(args, "--parts")
        configure_structure(state, parse_counts(raw_counts, parts))
    save_state(state)
    emit({"status": "ok", "message": f"项目「{state['project_name']}」初始化成功", "state": state})


def cmd_configure(args: List[str]) -> None:
    state = load_state()
    progress = state.get("outline_progress", {})
    has_progress = progress.get("book_outline_done") or any(
        progress.get(key) for key in ("parts_done", "plans_done", "arcs_done", "chapters_done")
    )
    if has_progress and "--force" not in args:
        emit({"error": "已有大纲进度，重新配置会使编号失效", "suggest": "确认影响后使用 --force"}, 1)
    parts = int_after(args, "--parts")
    counts = parse_counts(value_after(args, "--volumes-per-part"), parts)
    configure_structure(state, counts)
    if has_progress:
        state["outline_progress"] = default_progress()
        state["closure_progress"] = {"volumes_closed": [], "parts_closed": [], "book_closed": False}
    state["last_command"] = "master configure " + " ".join(args)
    save_state(state)
    emit({"status": "ok", "total_parts": state["total_parts"], "total_volumes": state["total_volumes"], "structure": state["structure"]})


def cmd_status(args: List[str]) -> None:
    state = load_state()
    phase, action = find_next_step(state)
    emit({
        "status": "ok" if not validate_state(state) else "warning",
        "project_name": state["project_name"],
        "current": {"phase": state["current_phase"], "stage": state["current_stage"], "part": state["current_part"], "volume": state["current_volume"], "chapter": state["current_chapter"]},
        "structure": state["structure"],
        "outline_progress": state["outline_progress"],
        "writing_progress": state["writing_progress"],
        "closure_progress": state["closure_progress"],
        "next": {"phase": phase, "action": action},
        "validation_issues": validate_state(state),
        "blockers": state["blockers"],
        "pending_decisions": state["pending_decisions"],
    })


def add_done(items: List[int], value: int) -> None:
    if value not in items:
        items.append(value)
        items.sort()


def cmd_done(args: List[str]) -> None:
    state = load_state()
    stage = value_after(args, "--stage", state.get("current_stage"))
    part = int_after(args, "--part")
    volume = int_after(args, "--volume")
    chapter = int_after(args, "--chapter")
    force = "--force" in args
    progress = state["outline_progress"]

    if stage == "book_outline":
        progress["book_outline_done"] = True
        state["stage_status"][stage] = "completed"
    elif stage in PER_PART_STAGES:
        if part not in expected_parts(state):
            emit({"error": "--part 缺失或超出结构范围"}, 2)
        if not progress.get("book_outline_done") and not force:
            emit({"error": "全书总纲尚未完成"}, 1)
        add_done(progress["parts_done"], part)
        for item in volumes_for_part(state, part):
            add_done(progress["volume_directions_done"], item)
    elif stage in PER_VOLUME_STAGES:
        if volume not in expected_volumes(state):
            emit({"error": "--volume 缺失或超出结构范围"}, 2)
        if missing(expected_parts(state), progress.get("parts_done", [])) and not force:
            emit({"error": "仍有部纲或卷方向未完成，不能深化单卷"}, 1)
        add_done(progress[PROGRESS_KEYS[stage]], volume)
    elif stage == "writing" and chapter is not None:
        add_done(state["writing_progress"]["chapters_written"], chapter)
        state["current_chapter"] = max(state.get("current_chapter", 0), chapter)
    elif stage == "review" and chapter is not None:
        add_done(state["writing_progress"]["chapters_reviewed"], chapter)
    elif stage in state["stage_status"]:
        state["stage_status"][stage] = "completed"
    else:
        emit({"error": f"未知 stage: {stage}"}, 2)

    state["last_command"] = "master done " + " ".join(args)
    refresh_current(state)
    save_state(state)
    phase, action = find_next_step(state)
    emit({"status": "ok", "completed": {"stage": stage, "part": part, "volume": volume, "chapter": chapter}, "next": {"phase": phase, "action": action}})


def cmd_close(args: List[str]) -> None:
    state = load_state()
    level = value_after(args, "--level")
    part = int_after(args, "--part")
    volume = int_after(args, "--volume")
    closure = state["closure_progress"]

    if level == "volume":
        if volume not in expected_volumes(state):
            emit({"error": "--volume 缺失或超出结构范围"}, 2)
        if volume not in state["outline_progress"].get("chapters_done", []) and "--force" not in args:
            emit({"error": f"第 {volume} 卷的章节规划尚未完成，不能收尾"}, 1)
        add_done(closure["volumes_closed"], volume)
    elif level == "part":
        if part not in expected_parts(state):
            emit({"error": "--part 缺失或超出结构范围"}, 2)
        remaining = missing(volumes_for_part(state, part), closure["volumes_closed"])
        if remaining and "--force" not in args:
            emit({"error": f"第 {part} 部仍有未收尾卷: {remaining}"}, 1)
        add_done(closure["parts_closed"], part)
    elif level == "book":
        remaining = missing(expected_parts(state), closure["parts_closed"])
        if remaining and "--force" not in args:
            emit({"error": f"仍有未收尾部: {remaining}"}, 1)
        closure["book_closed"] = True
        state["stage_status"]["finish"] = "completed"
    else:
        emit({"error": "--level 必须是 volume、part 或 book"}, 2)

    state["last_command"] = "master close " + " ".join(args)
    refresh_current(state)
    save_state(state)
    phase, action = find_next_step(state)
    emit({"status": "ok", "closed": {"level": level, "part": part, "volume": volume}, "next": {"phase": phase, "action": action}})


def cmd_next_step(args: List[str]) -> None:
    state = load_state()
    phase, action = find_next_step(state)
    emit({
        "action": "all_done" if phase == "completed" else f"run:{action}",
        "phase": phase,
        "phase_label": PHASE_LABELS.get(phase, phase),
        "stage_label": STAGE_LABELS.get(action.split()[0], action),
    })


def cmd_back(args: List[str]) -> None:
    state = load_state()
    target = value_after(args, "--to")
    if target not in all_stages():
        emit({"error": "--to 必须指定有效 stage；此命令只回退状态，不删除文件"}, 2)
    state["stage_status"][target] = "active"
    state["current_stage"] = target
    state["current_phase"] = next(p for p, stages in STAGES_BY_PHASE.items() if target in stages)
    state["last_command"] = "master back " + " ".join(args)
    save_state(state)
    emit({"status": "ok", "warning": "仅回退状态；请人工核对并更新受影响文件", "current_stage": target})


def cmd_reset(args: List[str]) -> None:
    state = load_state()
    target = value_after(args, "--to")
    if target == "planning":
        state["outline_progress"] = default_progress()
        state["closure_progress"] = {"volumes_closed": [], "parts_closed": [], "book_closed": False}
    elif target == "creation":
        state["outline_progress"]["chapters_done"] = []
        state["writing_progress"] = {"chapters_written": [], "chapters_reviewed": []}
        state["closure_progress"] = {"volumes_closed": [], "parts_closed": [], "book_closed": False}
    else:
        emit({"error": "--to 仅支持 planning 或 creation；文件不会被删除"}, 2)
    state["last_command"] = "master reset " + " ".join(args)
    refresh_current(state)
    save_state(state)
    emit({"status": "ok", "warning": "状态已重置，现有文件未删除", "target": target})


def main() -> None:
    if len(sys.argv) < 2:
        emit({"error": "用法: master_state.py <init|configure|status|done|close|next-step|back|reset>"}, 2)
    command, args = sys.argv[1], sys.argv[2:]
    commands = {
        "init": cmd_init,
        "configure": cmd_configure,
        "status": cmd_status,
        "done": cmd_done,
        "close": cmd_close,
        "next-step": cmd_next_step,
        "back": cmd_back,
        "reset": cmd_reset,
    }
    if command not in commands:
        emit({"error": f"未知命令: {command}"}, 2)
    commands[command](args)


if __name__ == "__main__":
    main()
