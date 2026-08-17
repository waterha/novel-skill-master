#!/usr/bin/env python3
"""
event_matrix_scheduler.py — 事件矩阵调度器

防止剧情模式化（同样的冲突类型反复出现）。
核心机制：

1. 事件类型冷却：每类事件用完后进入冷却期，不得连续使用
2. 智能推荐：根据冷却状态和近期历史，推荐下一章的事件类型
3. 柔和事件强制：每 N 章至少出现一次"羁绊"或"风土人情"类事件

事件类型：
  - conflict_thrill:  冲突爽点（打脸/突破/逆转）
  - bond_deepening:   人物羁绊（互动/共患难）
  - faction_building: 势力经营（产业/人情/招揽）
  - world_painting:   风土人情（背景/民俗/技术细节）
  - tension_escalation: 危机升级（暗线推进/反派布局）

子命令：
  init       — 初始化事件矩阵
  status     — 查询冷却状态
  recommend  — 推荐下一章的事件类型
  record     — 记录本章已用事件类型

调用示例：
  python tools/event_matrix_scheduler.py init --project-root <路径>
  python tools/event_matrix_scheduler.py recommend --project-root <路径> --chapter 16
  python tools/event_matrix_scheduler.py record --project-root <路径> --chapter 16 --types conflict_thrill

返回值：JSON 到 stdout。
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from novel_common import ensure_dir, load_json, save_json, get_event_matrix_path


# ── 事件类型 ─────────────────────────────────────────────────────────────────

EVENT_TYPES: Set[str] = {
    "conflict_thrill",
    "bond_deepening",
    "faction_building",
    "world_painting",
    "tension_escalation",
}

EVENT_LABELS: Dict[str, str] = {
    "conflict_thrill": "冲突爽点",
    "bond_deepening": "人物羁绊",
    "faction_building": "势力经营",
    "world_painting": "风土人情",
    "tension_escalation": "危机升级",
}

# 冷却期（章）
COOLDOWNS: Dict[str, int] = {
    "conflict_thrill": 2,      # 冲突密集用会疲劳
    "bond_deepening": 1,       # 羁绊可以稍密
    "faction_building": 2,     # 势力需要间隔
    "world_painting": 3,       # 风土人情不能太频
    "tension_escalation": 2,   # 危机升级需要酝酿
}

# 配置
MAX_CONSECUTIVE_CONFLICT = 2   # 最多连续 2 章冲突爽点
GENTLE_WINDOW_SIZE = 5         # 每 5 章至少一次 bond/world
MAX_HISTORY = 500              # 最大历史记录


def _empty_state() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "updated_at": datetime.now().isoformat(),
        "types": {
            k: {"cooldown": v, "last_used_chapter": 0}
            for k, v in COOLDOWNS.items()
        },
        "history": [],
    }


def _load_state(path: Path) -> Dict[str, Any]:
    st = load_json(path, default=_empty_state())
    if not isinstance(st.get("types"), dict):
        st["types"] = _empty_state()["types"]
    if not isinstance(st.get("history"), list):
        st["history"] = []
    # 确保所有事件类型都存在
    for k, cd in COOLDOWNS.items():
        if k not in st["types"] or not isinstance(st["types"][k], dict):
            st["types"][k] = {"cooldown": cd, "last_used_chapter": 0}
        st["types"][k].setdefault("cooldown", cd)
        st["types"][k].setdefault("last_used_chapter", 0)
    return st


def _is_available(next_ch: int, last_used: int, cooldown: int) -> bool:
    if last_used <= 0:
        return True
    return (next_ch - last_used) > cooldown


def _recent_types(history: List[Dict], from_ch: int, to_ch: int) -> List[str]:
    types: List[str] = []
    for h in history:
        if not isinstance(h, dict):
            continue
        ch = int(h.get("chapter", 0) or 0)
        if from_ch <= ch <= to_ch:
            ts = h.get("types", [])
            if isinstance(ts, list):
                types.extend(str(t) for t in ts)
    return types


def _consecutive_conflict(history: List[Dict], next_ch: int) -> int:
    """计算连续冲突冲突次数。"""
    count = 0
    ch = next_ch - 1
    while ch > 0:
        rec = next(
            (x for x in history if isinstance(x, dict) and int(x.get("chapter", 0) or 0) == ch),
            None,
        )
        if not rec:
            break
        types = rec.get("types", [])
        if isinstance(types, list) and "conflict_thrill" in types:
            count += 1
            ch -= 1
        else:
            break
    return count


# ── 子命令 ───────────────────────────────────────────────────────────────────

def cmd_init(args: argparse.Namespace) -> Dict[str, Any]:
    path = get_event_matrix_path(Path(args.project_root))
    ensure_dir(path.parent)

    if path.exists() and not args.force:
        st = _load_state(path)
        return {
            "ok": True, "command": "init", "created": False,
            "state_file": str(path),
            "message": "事件矩阵已存在；如需覆盖请加 --force",
        }

    st = _empty_state()
    ok = save_json(path, st)
    return {"ok": ok, "command": "init", "state_file": str(path), "created": ok}


def cmd_status(args: argparse.Namespace) -> Dict[str, Any]:
    path = get_event_matrix_path(Path(args.project_root))
    st = _load_state(path)
    chapter = args.chapter or 0

    types_status: Dict[str, Any] = {}
    for et, meta in st.get("types", {}).items():
        cd = int(meta.get("cooldown", COOLDOWNS.get(et, 1)))
        last = int(meta.get("last_used_chapter", 0) or 0)
        available = _is_available(chapter, last, cd) if chapter > 0 else True
        remaining = max(0, cd - (chapter - last) + 1) if chapter > 0 and last > 0 else 0
        types_status[et] = {
            "label": EVENT_LABELS.get(et, et),
            "cooldown": cd,
            "last_used_chapter": last,
            "available": available,
            "remaining_cooldown": remaining if chapter > 0 else None,
        }

    return {
        "ok": True, "command": "status",
        "state_file": str(path),
        "current_chapter": chapter,
        "types": types_status,
        "history_size": len(st.get("history", [])),
    }


def cmd_recommend(args: argparse.Namespace) -> Dict[str, Any]:
    path = get_event_matrix_path(Path(args.project_root))
    st = _load_state(path)
    chapter = args.chapter

    types_meta = st.get("types", {})
    history = st.get("history", [])

    # 1. 计算可用池
    available: List[Tuple[str, int]] = []
    blocked: List[str] = []
    for et in sorted(EVENT_TYPES):
        meta = types_meta.get(et, {})
        last = int(meta.get("last_used_chapter", 0) or 0)
        cd = int(meta.get("cooldown", COOLDOWNS.get(et, 1)))
        if _is_available(chapter, last, cd):
            score = chapter - last if last > 0 else 10**6
            available.append((et, score))
        else:
            blocked.append(et)

    # 2. 冲突爽点连续限制
    if _consecutive_conflict(history, chapter) >= MAX_CONSECUTIVE_CONFLICT:
        available = [(et, sc) for et, sc in available if et != "conflict_thrill"]
        if "conflict_thrill" not in blocked:
            blocked.append("conflict_thrill")

    # 3. 柔和事件强制（每 N 章至少一次 bond/world）
    force_gentle = False
    win_start = max(1, chapter - GENTLE_WINDOW_SIZE + 1)
    recent = _recent_types(history, win_start, chapter - 1)
    if "bond_deepening" not in recent and "world_painting" not in recent:
        force_gentle = True
        gentle = [x for x in available if x[0] in {"bond_deepening", "world_painting"}]
        others = [x for x in available if x[0] not in {"bond_deepening", "world_painting"}]
        available = gentle + others if gentle else available

    # 4. 按久未使用排序（越久越优先）
    available.sort(key=lambda x: x[1], reverse=True)
    primary = available[0][0] if available else ""
    secondary = [x[0] for x in available[1:4]]

    recommended = [primary] if primary else []
    for s in secondary:
        if s and s not in recommended:
            recommended.append(s)

    return {
        "ok": True,
        "command": "recommend",
        "chapter": chapter,
        "primary_type": primary,
        "primary_label": EVENT_LABELS.get(primary, ""),
        "secondary_types": secondary,
        "recommended_types": recommended,
        "blocked_types": sorted(set(blocked)),
        "force_gentle_event": force_gentle,
        "notes": [
            f"冲突爽点不得连续超过 {MAX_CONSECUTIVE_CONFLICT} 章",
            f"每 {GENTLE_WINDOW_SIZE} 章至少出现一次人物羁绊或风土人情",
        ],
    }


def cmd_record(args: argparse.Namespace) -> Dict[str, Any]:
    path = get_event_matrix_path(Path(args.project_root))
    st = _load_state(path)
    chapter = args.chapter

    raw_types = [x.strip() for x in args.types.split(",") if x.strip()]
    if not raw_types:
        return {"ok": False, "error": "至少指定一个事件类型"}

    invalid = [x for x in raw_types if x not in EVENT_TYPES]
    if invalid:
        return {"ok": False, "error": f"非法事件类型: {', '.join(invalid)}，可选: {', '.join(sorted(EVENT_TYPES))}"}

    # 去重保序
    seen: Set[str] = set()
    uniq_types: List[str] = []
    for t in raw_types:
        if t not in seen:
            uniq_types.append(t)
            seen.add(t)

    # 更新 last_used
    for t in uniq_types:
        st["types"][t]["last_used_chapter"] = chapter

    # 更新历史（按章号 upsert）
    history: List[Dict] = []
    replaced = False
    for rec in st.get("history", []):
        if isinstance(rec, dict) and int(rec.get("chapter", 0) or 0) == chapter:
            history.append({"chapter": chapter, "types": uniq_types})
            replaced = True
        else:
            history.append(rec)
    if not replaced:
        history.append({"chapter": chapter, "types": uniq_types})

    # 排序+裁剪
    st["history"] = sorted(
        [h for h in history if isinstance(h, dict) and int(h.get("chapter", 0) or 0) > 0],
        key=lambda x: int(x["chapter"]),
    )[-MAX_HISTORY:]

    ok = save_json(path, st)
    return {
        "ok": ok, "command": "record",
        "chapter": chapter,
        "recorded_types": uniq_types,
        "recorded_labels": [EVENT_LABELS.get(t, t) for t in uniq_types],
        "history_size": len(st["history"]),
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description="事件矩阵调度器")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="初始化事件矩阵")
    s.add_argument("--project-root", required=True)
    s.add_argument("--force", action="store_true")

    s = sub.add_parser("status", help="查询冷却状态")
    s.add_argument("--project-root", required=True)
    s.add_argument("--chapter", type=int, default=0, help="当前章节号（计算冷却剩余）")

    s = sub.add_parser("recommend", help="推荐下一章事件类型")
    s.add_argument("--project-root", required=True)
    s.add_argument("--chapter", required=True, type=int, help="下一章章节号")

    s = sub.add_parser("record", help="记录本章已用事件类型")
    s.add_argument("--project-root", required=True)
    s.add_argument("--chapter", required=True, type=int)
    s.add_argument("--types", required=True, help="逗号分隔事件类型列表")

    args = p.parse_args()

    dispatch = {
        "init": cmd_init,
        "status": cmd_status,
        "recommend": cmd_recommend,
        "record": cmd_record,
    }

    handler = dispatch.get(args.cmd)
    if handler is None:
        payload: Dict[str, Any] = {"ok": False, "error": f"未知命令: {args.cmd}"}
    else:
        try:
            payload = handler(args)
        except Exception as exc:
            payload = {"ok": False, "command": args.cmd, "error": repr(exc)}

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
