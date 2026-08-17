#!/usr/bin/env python3
"""
pacing_tracker.py — 章节节奏追踪与配额检查

防止 AI 写作中的"剧情加速"问题——即过度推进主线、过早解决冲突。
核心机制：

1. 节奏三档制：慢档（铺垫） / 中档（升温） / 快档（突破）
   - 每卷快档 ≤ 2-3 次，快档后必须有慢档/中档缓冲
2. A/B/C 配额检查：
   - A: 主线矛盾实质推进
   - B: 主要关系决定性升级
   - C: 核心秘密完整揭露
   - ⛔ 每章至多触发 1 项
3. 章末悬念强制检查
4. 每 5 章节奏分布审计

子命令：
  init       — 初始化节奏状态
  status     — 查看当前节奏状态
  check      — 检查单章的节奏合规性
  record     — 记录本章的节奏数据
  audit      — 审计近 N 章的节奏分布

调用示例：
  python tools/pacing_tracker.py init --project-root <路径>
  python tools/pacing_tracker.py check --chapter 15 --pacing fast --has-hook true --triggers A
  python tools/pacing_tracker.py record --chapter 15 --pacing fast --triggers A

返回值：JSON 到 stdout。
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from novel_common import (
    ensure_dir, load_json, save_json, get_pacing_path,
)


# ── 常量 ─────────────────────────────────────────────────────────────────────

# 节奏档位
PACING_TIERS = ["slow", "medium", "fast"]
PACING_LABELS = {
    "slow": "慢档（铺垫/羁绊）",
    "medium": "中档（升温/酝酿）",
    "fast": "快档（突破/高潮）",
}

# 配额类型
QUOTA_TYPES = ["A", "B", "C"]
QUOTA_LABELS = {
    "A": "主线矛盾实质推进",
    "B": "主要关系决定性升级",
    "C": "核心秘密完整揭露",
}

# 档位密度要求（每 N 章至少 1 章为慢档）
SLOW_DENSITY_WINDOW = 4

# 卷内快档上限（每卷最多 N 次）
MAX_FAST_PER_VOLUME = 3

# 快档后需要至少 N 章缓冲
FAST_COOLDOWN_CHAPTERS = 1

# 默认配置
DEFAULT_CONFIG = {
    "slow_density_window": SLOW_DENSITY_WINDOW,
    "max_fast_per_volume": MAX_FAST_PER_VOLUME,
    "fast_cooldown_chapters": FAST_COOLDOWN_CHAPTERS,
}


def _empty_state() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "config": dict(DEFAULT_CONFIG),
        "updated_at": datetime.now().isoformat(),
        "chapters": [],        # 每章的节奏记录
        "violations": [],      # 违规记录
        "volume_fast_count": {},  # {卷号: 快档次数}
    }


def _load_state(path: Path) -> Dict[str, Any]:
    st = load_json(path, default=_empty_state())
    for key in ("chapters", "violations"):
        if not isinstance(st.get(key), list):
            st[key] = []
    if not isinstance(st.get("volume_fast_count"), dict):
        st["volume_fast_count"] = {}
    st.setdefault("config", dict(DEFAULT_CONFIG))
    return st


def _chapter_key(chapter: int, volume: int) -> str:
    return f"vol{volume}_ch{chapter}"


# ── 子命令 ───────────────────────────────────────────────────────────────────

def cmd_init(args: argparse.Namespace) -> Dict[str, Any]:
    path = get_pacing_path(Path(args.project_root))
    ensure_dir(path.parent)

    if path.exists() and not args.force:
        st = _load_state(path)
        return {
            "ok": True, "command": "init",
            "pacing_file": str(path), "created": False,
            "chapter_count": len(st.get("chapters", [])),
            "message": "节奏状态已存在；如需重置请加 --force",
        }

    st = _empty_state()
    if args.config:
        try:
            custom = json.loads(args.config)
            if isinstance(custom, dict):
                st["config"].update(custom)
        except json.JSONDecodeError:
            return {"ok": False, "error": "config 格式错误，需要 JSON 对象"}

    ok = save_json(path, st)
    return {
        "ok": ok, "command": "init",
        "pacing_file": str(path), "created": ok,
        "config": st["config"],
    }


def cmd_check(args: argparse.Namespace) -> Dict[str, Any]:
    """检查单章的节奏合规性。返回检查结果和违规列表。"""
    path = get_pacing_path(Path(args.project_root))
    st = _load_state(path)
    config = st.get("config", DEFAULT_CONFIG)

    chapter = args.chapter
    volume = args.volume or 1
    pacing = args.pacing
    triggers = args.triggers.upper().strip() if args.triggers else ""
    has_hook = args.has_hook

    violations: List[str] = []
    warnings: List[str] = []

    # 校验参数
    if pacing not in PACING_TIERS:
        return {"ok": False, "error": f"无效节奏档位: {pacing}，可选: {', '.join(PACING_TIERS)}"}

    trigger_list = [t for t in triggers if t in QUOTA_TYPES]

    # 检查1: A/B/C 配额（每章至多触发 1 项）
    if len(trigger_list) > 1:
        violations.append(f"配额违规：同时触发 {', '.join(trigger_list)} 共 {len(trigger_list)} 项（限额 1 项）")

    # 检查2: 章末钩子（快档必须有钩子，慢档可以没有）
    if pacing == "fast" and not has_hook:
        violations.append("快档章节必须保留章末悬念钩子")

    # 检查3: 快档后缓冲
    if pacing != "fast":
        # 检查上一章是否是快档
        prev_chapter = None
        for c in reversed(st.get("chapters", [])):
            if isinstance(c, dict) and c.get("chapter") == chapter - 1 and c.get("volume") == volume:
                prev_chapter = c
                break
        if prev_chapter and prev_chapter.get("pacing") == "fast":
            # 快档后至少要有 fast_cooldown 章缓冲，当前不是快档没问题
            pass  # OK

    # 检查4: 快档后的下一章如果是快档就违规
    if pacing == "fast":
        prev_chapter = None
        for c in reversed(st.get("chapters", [])):
            if isinstance(c, dict) and c.get("chapter") == chapter - 1 and c.get("volume") == volume:
                prev_chapter = c
                break
        if prev_chapter and prev_chapter.get("pacing") == "fast":
            violations.append("连续两章快档，违反快档后缓冲规则")

    # 检查5: 卷内快档上限
    volume_key = str(volume)
    current_fast_in_volume = st.get("volume_fast_count", {}).get(volume_key, 0)
    if pacing == "fast":
        if current_fast_in_volume >= config.get("max_fast_per_volume", 3):
            violations.append(f"卷{volume} 快档已达上限 {config['max_fast_per_volume']} 次")

    # 检查6: 慢档密度（每 N 章至少 1 章慢档）
    window = config.get("slow_density_window", 4)
    recent_chapters = [
        c for c in st.get("chapters", [])
        if isinstance(c, dict) and c.get("volume") == volume
        and c.get("chapter", 0) > chapter - window
        and c.get("chapter", 0) < chapter
    ]
    has_recent_slow = any(c.get("pacing") == "slow" for c in recent_chapters)
    if not has_recent_slow and pacing != "slow":
        recent_count = len(recent_chapters)
        if recent_count >= window - 1:
            warnings.append(f"近 {window} 章内无慢档章节，建议本章或下一章使用慢档")

    return {
        "ok": len(violations) == 0,
        "command": "check",
        "pacing_file": str(path),
        "chapter": chapter,
        "volume": volume,
        "pacing": pacing,
        "pacing_label": PACING_LABELS.get(pacing, pacing),
        "triggers": trigger_list,
        "has_hook": has_hook,
        "violations": violations,
        "warnings": warnings,
        "passed": len(violations) == 0,
    }


def cmd_record(args: argparse.Namespace) -> Dict[str, Any]:
    """记录本章的节奏数据。"""
    path = get_pacing_path(Path(args.project_root))
    st = _load_state(path)

    chapter = args.chapter
    volume = args.volume or 1
    pacing = args.pacing
    triggers = args.triggers.upper().strip() if args.triggers else ""
    has_hook = args.has_hook

    if pacing not in PACING_TIERS:
        return {"ok": False, "error": f"无效节奏档位: {pacing}"}

    trigger_list = [t for t in triggers if t in QUOTA_TYPES]

    # 创建记录
    record = {
        "chapter": chapter,
        "volume": volume,
        "pacing": pacing,
        "triggers": trigger_list,
        "has_hook": has_hook,
        "recorded_at": datetime.now().isoformat(),
    }

    # 更新（避免重复）
    st["chapters"] = [c for c in st.get("chapters", [])
                      if not (isinstance(c, dict) and c.get("chapter") == chapter and c.get("volume") == volume)]
    st["chapters"].append(record)

    # 更新卷内快档计数
    if pacing == "fast":
        volume_fast = st.setdefault("volume_fast_count", {})
        vkey = str(volume)
        volume_fast[vkey] = volume_fast.get(vkey, 0) + 1

    ok = save_json(path, st)
    return {
        "ok": ok,
        "command": "record",
        "pacing_file": str(path),
        "chapter": chapter,
        "volume": volume,
        "pacing": pacing,
        "pacing_label": PACING_LABELS.get(pacing, pacing),
        "triggers": trigger_list,
        "has_hook": has_hook,
        "chapters_recorded": len(st["chapters"]),
    }


def cmd_status(args: argparse.Namespace) -> Dict[str, Any]:
    """查看当前节奏状态。"""
    path = get_pacing_path(Path(args.project_root))
    st = _load_state(path)
    chapters = st.get("chapters", [])

    # 统计
    total = len(chapters)
    pacing_counts = {"slow": 0, "medium": 0, "fast": 0}
    vol_fast = st.get("volume_fast_count", {})
    recent_10 = sorted(chapters, key=lambda c: c.get("chapter", 0), reverse=True)[:10]

    for c in chapters:
        if isinstance(c, dict):
            p = c.get("pacing", "")
            if p in pacing_counts:
                pacing_counts[p] += 1

    recent_summary = []
    for c in reversed(recent_10):
        recent_summary.append({
            "chapter": c.get("chapter"),
            "volume": c.get("volume"),
            "pacing": c.get("pacing"),
            "triggers": c.get("triggers", []),
        })

    return {
        "ok": True,
        "command": "status",
        "pacing_file": str(path),
        "total_chapters_recorded": total,
        "pacing_distribution": {
            "slow": pacing_counts["slow"],
            "medium": pacing_counts["medium"],
            "fast": pacing_counts["fast"],
        },
        "volume_fast_count": vol_fast,
        "recent_10": recent_summary,
        "last_recorded": recent_summary[0] if recent_summary else None,
    }


def cmd_audit(args: argparse.Namespace) -> Dict[str, Any]:
    """审计近 N 章的节奏分布。"""
    path = get_pacing_path(Path(args.project_root))
    st = _load_state(path)
    chapters = st.get("chapters", [])
    config = st.get("config", DEFAULT_CONFIG)
    n = args.recent or 20

    recent = sorted(
        [c for c in chapters if isinstance(c, dict)],
        key=lambda c: c.get("chapter", 0),
        reverse=True,
    )[:n]
    recent = list(reversed(recent))

    issues: List[str] = []

    # 检查快档比例
    fast_count = sum(1 for c in recent if c.get("pacing") == "fast")
    if fast_count > config.get("max_fast_per_volume", 3):
        issues.append(f"近 {n} 章快档 {fast_count} 次，建议控制")

    # 检查慢档比例
    slow_count = sum(1 for c in recent if c.get("pacing") == "slow")
    if slow_count == 0 and len(recent) >= config.get("slow_density_window", 4):
        issues.append(f"近 {n} 章无慢档章节，建议加入铺垫章节")

    # 检查连续快档
    for i in range(len(recent) - 1):
        if recent[i].get("pacing") == "fast" and recent[i + 1].get("pacing") == "fast":
            issues.append(f"第{recent[i]['chapter']}章和第{recent[i+1]['chapter']}章连续快档")
            break

    # 检查配额违规
    trig_records = [c for c in recent if len(c.get("triggers", [])) > 1]
    if trig_records:
        for c in trig_records:
            issues.append(f"第{c['chapter']}章触发多项配额: {', '.join(c['triggers'])}")

    summary = {
        "total_in_window": len(recent),
        "slow": f"{sum(1 for c in recent if c.get('pacing') == 'slow')}/{len(recent)}",
        "medium": f"{sum(1 for c in recent if c.get('pacing') == 'medium')}/{len(recent)}",
        "fast": f"{sum(1 for c in recent if c.get('pacing') == 'fast')}/{len(recent)}",
    }

    return {
        "ok": True,
        "command": "audit",
        "window_chapters": n,
        "summary": summary,
        "issues": issues,
        "has_issues": len(issues) > 0,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description="章节节奏追踪器")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="初始化节奏状态")
    s.add_argument("--project-root", required=True)
    s.add_argument("--force", action="store_true", help="覆盖已有状态")
    s.add_argument("--config", default="", help='配置 JSON，如 \'{"max_fast_per_volume":2}\'')

    s = sub.add_parser("check", help="检查单章节奏合规性（写前检查）")
    s.add_argument("--project-root", required=True)
    s.add_argument("--chapter", required=True, type=int)
    s.add_argument("--volume", type=int, default=1)
    s.add_argument("--pacing", required=True, choices=PACING_TIERS,
                   help="本章节奏档位")
    s.add_argument("--triggers", default="",
                   help="触发的配额类型（A/B/C，多个用逗号分隔，如 'A,B'）")
    s.add_argument("--has-hook", action="store_true",
                   help="本章是否有章末悬念钩子")

    s = sub.add_parser("record", help="记录本章节奏数据（写后记录）")
    s.add_argument("--project-root", required=True)
    s.add_argument("--chapter", required=True, type=int)
    s.add_argument("--volume", type=int, default=1)
    s.add_argument("--pacing", required=True, choices=PACING_TIERS)
    s.add_argument("--triggers", default="")
    s.add_argument("--has-hook", action="store_true")

    s = sub.add_parser("status", help="查看节奏状态")
    s.add_argument("--project-root", required=True)

    s = sub.add_parser("audit", help="节奏分布审计")
    s.add_argument("--project-root", required=True)
    s.add_argument("--recent", type=int, default=20, help="检查最近多少章")

    args = p.parse_args()

    dispatch = {
        "init": cmd_init,
        "check": cmd_check,
        "record": cmd_record,
        "status": cmd_status,
        "audit": cmd_audit,
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
