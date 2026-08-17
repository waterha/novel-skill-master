#!/usr/bin/env python3
"""
project_stats.py — 创作数据统计与时间线

读取项目状态文件和正文内容，生成写作统计、趋势预测、时间线。

触发条件（由 Claude 在统计命令下调用）：
  master stats
    → python project_stats.py stats --project-root <路径> [--recent N]
      输出完整统计看板（字数/日均/趋势/预测/质量）

  master timeline
    → python project_stats.py timeline --project-root <路径>
      输出项目时间线

  master status (嵌入统计摘要)
    → python project_stats.py summary --project-root <路径>
      输出简短统计摘要

返回值：JSON 到 stdout，Claude 解析后格式化展示。
"""

import json
import sys
import re
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


# ─── 工具函数 ────────────────────────────────────────────────────────────────

def count_words_in_file(path: Path) -> int:
    """统计文件中的中文字数（不含空白/标点）"""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    # 只统计中文字符
    chinese_chars = re.findall(r'[一-鿿㐀-䶿豈-﫿]', text)
    return len(chinese_chars)


def count_words_in_dir(dir_path: Path) -> int:
    """统计目录下所有章节文件的总字数"""
    total = 0
    if not dir_path.exists():
        return 0
    for f in list_chapter_paths(dir_path):
        total += count_words_in_file(f)
    return total


def list_chapter_paths(dir_path: Path) -> list:
    """递归列出新旧目录结构中的章节正文。"""
    files = list(dir_path.rglob("第*章*.md")) + list(dir_path.rglob("第*章*.txt"))
    return sorted(set(files), key=lambda path: (parse_chapter_number(path.name), str(path)))


def count_chapter_files(dir_path: Path) -> int:
    """统计章节文件数"""
    if not dir_path.exists():
        return 0
    return len(list_chapter_paths(dir_path))


def list_chapter_files(dir_path: Path) -> list:
    """列出章节文件（带字数）"""
    if not dir_path.exists():
        return []
    files = list_chapter_paths(dir_path)
    result = []
    for f in files:
        result.append({
            "name": f.stem,
            "path": str(f),
            "words": count_words_in_file(f),
        })
    return result


def parse_chapter_number(filename: str) -> int:
    """从文件名解析章节号"""
    m = re.search(r'(\d+)', filename)
    return int(m.group(1)) if m else 0


def estimate_completion_date(current_words: int, target_words: int,
                             daily_avg: float, start_date: Optional[str] = None) -> dict:
    """预估完结日期"""
    if daily_avg <= 0 or target_words <= 0:
        return {"eta": "未知", "days_remaining": 0}

    remaining = max(0, target_words - current_words)
    days_needed = remaining / daily_avg
    eta = datetime.now() + timedelta(days=days_needed)

    return {
        "remaining_words": remaining,
        "days_needed": round(days_needed, 1),
        "eta_date": eta.strftime("%Y-%m-%d"),
        "eta_label": f"{eta.month}月{eta.day}日",
    }


# ─── 评分计算 ────────────────────────────────────────────────────────────────

def calc_quality_scores(review_files: list) -> dict:
    """汇总审查评分"""
    if not review_files:
        return {"available": False}

    scores = {
        "设定一致性": [], "文笔质量": [], "逻辑链条": [],
        "节奏控制": [], "商业化": [],
    }

    for rf in review_files:
        try:
            data = json.loads(rf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        dimensions = data.get("dimensions", data.get("scores", {}))
        for dim, score in dimensions.items():
            if dim in scores and isinstance(score, (int, float)):
                scores[dim].append(score)

    avg_scores = {}
    for dim, vals in scores.items():
        if vals:
            avg_scores[dim] = round(sum(vals) / len(vals), 1)
        else:
            avg_scores[dim] = 0

    if avg_scores:
        weights = {"设定一致性": 0.3, "文笔质量": 0.2, "逻辑链条": 0.2, "节奏控制": 0.15, "商业化": 0.15}
        weighted = sum(avg_scores.get(d, 0) * w for d, w in weights.items())
    else:
        weighted = 0

    return {
        "available": True,
        "dimensions": avg_scores,
        "composite": round(weighted, 1),
    }


# ─── 命令实现 ────────────────────────────────────────────────────────────────

def cmd_summary(args: list):
    """project_stats.py summary — 简短统计摘要"""
    project_root = None
    for i, a in enumerate(args):
        if a in ("--project-root", "--project_root", "--root") and i + 1 < len(args):
            project_root = Path(args[i + 1])
    if not project_root:
        project_root = Path.cwd()

    state = {}
    state_file = project_root / ".webnovel" / "master_state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except:
            pass

    # 字数统计
    content_dir = project_root / "正文"
    total_words = count_words_in_dir(content_dir)
    chapter_count = count_chapter_files(content_dir)

    target_words = state.get("target_words", 0) or 0
    target_chapters = state.get("target_chapter", 0) or 0

    result = {
        "chapter_progress": f"{state.get('current_chapter', chapter_count)}/{target_chapters or '?'}",
        "word_count": total_words,
        "target_words": target_words,
        "word_progress_pct": round(total_words / target_words * 100, 1) if target_words > 0 else 0,
    }

    print(json.dumps(result, ensure_ascii=False))


def cmd_stats(args: list):
    """project_stats.py stats — 完整统计看板"""
    project_root = None
    recent_n = 10
    for i, a in enumerate(args):
        if a in ("--project-root", "--project_root", "--root") and i + 1 < len(args):
            project_root = Path(args[i + 1])
        if a == "--recent" and i + 1 < len(args):
            try:
                recent_n = int(args[i + 1])
            except ValueError:
                pass

    if not project_root:
        project_root = Path.cwd()

    # 加载状态
    state = {}
    state_file = project_root / ".webnovel" / "master_state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except:
            pass

    # 正文统计
    content_dir = project_root / "正文"
    total_words = 0
    chapter_count = 0
    per_volume = {}

    if content_dir.exists():
        # 兼容“正文/部/卷/章”和旧的“正文/卷/章”结构
        volume_dirs = [path for path in content_dir.rglob("第*卷") if path.is_dir()]
        for vol_dir in sorted(volume_dirs):
            v_words = count_words_in_dir(vol_dir)
            v_chapters = count_chapter_files(vol_dir)
            total_words += v_words
            chapter_count += v_chapters
            if v_chapters > 0:
                key = str(vol_dir.relative_to(content_dir))
                per_volume[key] = {"words": v_words, "chapters": v_chapters}

        # 如果不在卷目录结构中，统计直接文件
        if chapter_count == 0:
            total_words = count_words_in_dir(content_dir)
            chapter_count = count_chapter_files(content_dir)

    target_words = state.get("target_words", 0) or 0
    target_chapters = state.get("target_chapter", 0) or 0
    current_chapter = state.get("current_chapter", chapter_count)
    total_volumes = state.get("total_volumes", 1)

    # 日均字数（从 state.json 的 last_executed_at 推算）
    daily_avg = 0
    streak_days = 0
    if state.get("total_words", 0) and state.get("last_executed_at"):
        try:
            first_date_str = state.get("created_at", state["last_executed_at"])
            first_date = datetime.fromisoformat(first_date_str)
            days_elapsed = max(1, (datetime.now() - first_date).days)
            daily_avg = round(state.get("total_words", total_words) / days_elapsed)
        except:
            daily_avg = 0

    # 最近章节详情
    recent_chapters = []
    if content_dir.exists():
        all_files = list_chapter_paths(content_dir)
        all_files.sort(key=lambda f: parse_chapter_number(f.stem), reverse=True)
        for f in all_files[:recent_n]:
            recent_chapters.append({
                "name": f.stem,
                "words": count_words_in_file(f),
            })

    # 预估完结
    eta = estimate_completion_date(
        state.get("total_words", total_words),
        target_words,
        daily_avg or 2000,
    )

    # 质量评分
    review_dir = project_root / ".story-system" / "reviews"
    review_files = sorted(review_dir.glob("*-review.json")) if review_dir.exists() else []
    quality = calc_quality_scores(review_files)

    # 卷大纲进度
    op = state.get("outline_progress", {})
    outline_status = {
        "total_parts": state.get("total_parts", 0),
        "total_volumes": total_volumes,
        "book_outline_done": bool(op.get("book_outline_done")),
        "parts_done": len(op.get("parts_done", [])),
        "volume_directions_done": len(op.get("volume_directions_done", [])),
        "plans_done": len(op.get("plans_done", [])),
        "arcs_done": len(op.get("arcs_done", [])),
        "chapters_done": len(op.get("chapters_done", [])),
    }

    result = {
        "summary": {
            "chapter_progress": f"{current_chapter}/{target_chapters or '?'}",
            "word_count": state.get("total_words", total_words),
            "target_words": target_words,
            "word_progress_pct": round(state.get("total_words", total_words) / max(target_words, 1) * 100, 1),
        },
        "per_volume": per_volume,
        "daily_stats": {
            "daily_avg_words": daily_avg,
            "streak_days": streak_days,
            "recent_avg_words": round(sum(c["words"] for c in recent_chapters[:5]) / max(len(recent_chapters[:5]), 1)),
        },
        "eta": eta,
        "outline_progress": outline_status,
        "quality": quality,
        "recent_chapters": recent_chapters[:5],
    }

    print(json.dumps(result, ensure_ascii=False))


def cmd_timeline(args: list):
    """project_stats.py timeline — 项目时间线"""
    project_root = None
    for i, a in enumerate(args):
        if a in ("--project-root", "--project_root", "--root") and i + 1 < len(args):
            project_root = Path(args[i + 1])
    if not project_root:
        project_root = Path.cwd()

    state = {}
    state_file = project_root / ".webnovel" / "master_state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except:
            pass

    # 从 state 提取时间信息
    events = []

    # 项目创建时间
    created = state.get("created_at") or state.get("last_executed_at")
    if created:
        events.append({
            "date": created[:10],
            "category": "project",
            "event": "项目创建",
            "detail": state.get("project_name", ""),
        })

    # 阶段完成时间（从 stage_status 和 phase_status 反推 - 简化版）
    # 实际情况需要更复杂的时间追踪，这里只展示当前状态
    phase_labels = {
        "ideation": "构思期", "setting": "设定期", "planning": "规划期",
        "creation": "创作期", "finalization": "收尾期", "maintenance": "维护期",
    }
    for phase, status in state.get("phase_status", {}).items():
        if status == "completed":
            events.append({
                "date": state.get("last_executed_at", "未知")[:10],
                "category": "phase",
                "event": f"{phase_labels.get(phase, phase)} 完成",
            })

    # 当前状态
    events.append({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "category": "current",
        "event": f"当前: {phase_labels.get(state.get('current_phase', ''), '')} - "
                 f"{state.get('current_stage', '')}",
        "detail": f"已写 {state.get('current_chapter', 0)} 章 / {state.get('total_words', 0)} 字",
    })

    result = {
        "project_name": state.get("project_name", "未命名"),
        "events": events,
        "current_phase": state.get("current_phase"),
        "current_stage": state.get("current_stage"),
    }

    print(json.dumps(result, ensure_ascii=False))


# ─── CLI 入口 ──────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("用法: project_stats.py <command> [args...]", file=sys.stderr)
        print("命令: summary, stats, timeline", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "summary": cmd_summary,
        "stats": cmd_stats,
        "timeline": cmd_timeline,
    }

    if command not in commands:
        print(f"未知命令: {command}", file=sys.stderr)
        sys.exit(1)

    commands[command](args)


if __name__ == "__main__":
    main()
