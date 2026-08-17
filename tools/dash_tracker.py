#!/usr/bin/env python3
"""
dash_tracker.py — 破折号「——」使用追踪器

扫描章节正文中的破折号使用情况，维护趋势数据，计算下一章预算。

触发条件（由 Claude 在写章流程中调用）：
  novel-write Step 1 (Context Agent 生成任务书前)
    → python dash_tracker.py trend --project-root <路径>
      输出当前趋势状态 + 推荐预算，注入任务书

  novel-write Step 4 (Anti-AI 检测环节)
    → python dash_tracker.py check --chapter <路径/第XX章.md> [--genre 题材]
      输出逐项检查结果（每项 pass/fail + 违规详情）

  novel-write Step 5 (Commit 后更新趋势)
    → python dash_tracker.py update --project-root <路径> --chapter <路径/第XX章.md>

  每 10 章 / 卷结束时
    → python dash_tracker.py analyze --project-root <路径>
      输出密度趋势报告

返回值：JSON 到 stdout，Claude 解析后展示或决策。
"""

import json
import sys
import re
import os
from pathlib import Path
from typing import Optional


# ─── 常量 ──────────────────────────────────────────────────────────────────

# 每章硬上限
MAX_DASH_PER_CHAPTER = 5

# 各题材上限
GENRE_LIMITS = {
    "都市": 3, "现实": 3,
    "悬疑": 4, "推理": 4,
    "言情": 4, "甜宠": 4,
    "玄幻": 5, "仙侠": 5,
    "科幻": 3,
    "历史": 5,
    "搞笑": 3, "轻松": 3,
}

# 合法用途正则（用于区分合法 vs 滥用）
# 注意：仅用于统计，最终判断由 Claude 结合上下文做

# 需要标记的滥用模式
ABUSE_PATTERNS = [
    (r"意识到——", "万能「意识到——」"),
    (r"发现——", "万能「发现——」"),
    (r"看到——", "万能「看到——」"),
    (r"听到——", "万能「听到——」"),
    (r"那就是——", "万能「那就是——」"),
    (r"这意味着——", "万能「这意味着——」"),
    (r"——但", "「——但」结构"),
    (r"——可", "「——可」结构"),
    (r"——然而", "「——然而」结构"),
]

# 章末悬空破折号模式（段落末尾的 ——）
TRAILING_DASH_RE = re.compile(r'——\s*$', re.MULTILINE)

# 密度校准
DENSITY_CALIBRATION = {
    "下降": 5,
    "持平": 4,
    "上升": 3,
    "密集": 2,
}

DENSITY_LABELS = {
    "下降": "趋势下降（密度在收敛）",
    "持平": "趋势持平",
    "上升": "趋势上升（密度在扩散）",
    "密集": "密集区（单章 > 8 次）",
}


# ─── 工具函数 ───────────────────────────────────────────────────────────────

def count_dashes(text: str) -> int:
    """统计全文中 —— 出现的次数（4个连续破折号=2个标准破折号联合使用仍算1处）"""
    # 标准中文破折号：——（2个em dash连用）
    # 也匹配 ————（4个连用）
    return len(re.findall(r'——', text))


def classify_dash_usage(text: str) -> dict:
    """分类统计各类破折号用法"""
    result = {
        "total": count_dashes(text),
        "trailing": len(TRAILING_DASH_RE.findall(text)),
        "abuse_patterns": {},
    }
    for pattern, label in ABUSE_PATTERNS:
        count = len(re.findall(pattern, text))
        if count > 0:
            result["abuse_patterns"][label] = count
    return result


def check_chapter_paragraph_density(text: str) -> list:
    """检查连续3段内破折号密度"""
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    issues = []
    for i in range(len(paragraphs) - 2):
        trio = paragraphs[i:i+3]
        total = sum(count_dashes(p) for p in trio)
        if total > 2:
            issues.append({
                "paragraphs": i+1,
                "total_in_3_paragraphs": total,
                "warning": "连续3段内破折号密集",
            })
    return issues


def load_trend_data(project_root: Path) -> dict:
    """加载趋势数据文件"""
    path = project_root / ".story-system" / "dash_trend.json"
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"windows": [], "current_budget": 5, "total_chapters_analyzed": 0}
    return {"windows": [], "current_budget": 5, "total_chapters_analyzed": 0}


def save_trend_data(project_root: Path, data: dict):
    path = project_root / ".story-system" / "dash_trend.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── 命令实现 ────────────────────────────────────────────────────────────────

def cmd_check(args: list):
    """dash_tracker.py check — 单章检查"""
    chapter_path = None
    genre = None
    for i, a in enumerate(args):
        if a == "--chapter" and i + 1 < len(args):
            chapter_path = args[i + 1]
        if a == "--genre" and i + 1 < len(args):
            genre = args[i + 1]

    if not chapter_path:
        print(json.dumps({"error": "请指定 --chapter <路径>"}, ensure_ascii=False))
        sys.exit(1)

    p = Path(chapter_path)
    if not p.exists():
        print(json.dumps({"error": f"文件不存在: {chapter_path}"}, ensure_ascii=False))
        sys.exit(1)

    text = p.read_text(encoding="utf-8")
    analysis = classify_dash_usage(text)
    density_issues = check_chapter_paragraph_density(text)

    limit = GENRE_LIMITS.get(genre, MAX_DASH_PER_CHAPTER) if genre else MAX_DASH_PER_CHAPTER

    checks = []

    # 1. 总数检查
    checks.append({
        "check": "全章破折号总数",
        "count": analysis["total"],
        "limit": limit,
        "pass": analysis["total"] <= limit,
    })

    # 2. 模式滥用检查
    for label, count in analysis["abuse_patterns"].items():
        checks.append({
            "check": label,
            "count": count,
            "limit": 0,
            "pass": False,
            "detail": f"发现 {count} 处，需要替换为逗号/冒号",
        })

    # 3. 段落末尾悬空
    checks.append({
        "check": "段落末尾悬空破折号",
        "count": analysis["trailing"],
        "limit": 1,
        "pass": analysis["trailing"] <= 1,
    })

    # 4. 连续3段密度
    checks.append({
        "check": "连续3段内破折号密度",
        "issues": density_issues,
        "pass": len(density_issues) == 0,
    })

    # 5. ——但 结构
    dan_count = len(re.findall(r'——但', text))
    checks.append({
        "check": "「——但」结构",
        "count": dan_count,
        "limit": 1,
        "pass": dan_count <= 1,
    })

    all_pass = all(c.get("pass", True) for c in checks)

    print(json.dumps({
        "chapter": str(p),
        "genre": genre,
        "all_pass": all_pass,
        "checks": checks,
        "summary": f"{'✅ 通过' if all_pass else '❌ 需要修复'} — {analysis['total']} 处破折号",
    }, ensure_ascii=False))


def cmd_trend(args: list):
    """dash_tracker.py trend — 输出当前趋势状态 + 推荐预算"""
    project_root = None
    for i, a in enumerate(args):
        if a == "--project-root" and i + 1 < len(args):
            project_root = Path(args[i + 1])

    if not project_root:
        project_root = Path.cwd()

    data = load_trend_data(project_root)
    windows = data.get("windows", [])

    trend = "持平"
    if len(windows) >= 2:
        last = windows[-1].get("total", 0) if windows[-1] else 0
        prev = windows[-2].get("total", 0) if windows[-2] else 0
        if last > prev * 1.1:
            trend = "上升"
        elif last < prev * 0.9:
            trend = "下降"
        else:
            trend = "持平"

    last_chapter_count = windows[-1].get("total", 0) if windows else 0
    if last_chapter_count > 8:
        trend = "密集"

    budget = DENSITY_CALIBRATION.get(trend, 5)
    data["current_budget"] = budget
    save_trend_data(project_root, data)

    result = {
        "trend": trend,
        "trend_label": DENSITY_LABELS.get(trend, "正常"),
        "recommended_budget": budget,
        "windows_analyzed": len(windows),
        "total_chapters_analyzed": data.get("total_chapters_analyzed", 0),
        "recent_windows": windows[-3:] if windows else [],
    }
    if windows:
        last_w = windows[-1]
        result["last_10_chapters_total"] = last_w.get("total", 0)
        result["last_10_chapters_avg"] = round(last_w.get("total", 0) / max(last_w.get("chapters", 1), 1), 1)

    print(json.dumps(result, ensure_ascii=False))


def cmd_update(args: list):
    """dash_tracker.py update — 写章后更新趋势数据"""
    project_root = None
    chapter_path = None
    for i, a in enumerate(args):
        if a == "--project-root" and i + 1 < len(args):
            project_root = Path(args[i + 1])
        if a == "--chapter" and i + 1 < len(args):
            chapter_path = args[i + 1]

    if not project_root:
        project_root = Path.cwd()
    if not chapter_path:
        print(json.dumps({"error": "请指定 --chapter <路径>"}, ensure_ascii=False))
        sys.exit(1)

    p = Path(chapter_path)
    if not p.exists():
        print(json.dumps({"error": f"文件不存在: {chapter_path}"}, ensure_ascii=False))
        sys.exit(1)

    text = p.read_text(encoding="utf-8")
    dash_count = count_dashes(text)

    data = load_trend_data(project_root)
    data["total_chapters_analyzed"] = data.get("total_chapters_analyzed", 0) + 1
    data.setdefault("windows", [])

    # 每10章归档为一个 window
    total = data["total_chapters_analyzed"]
    chunk_idx = (total - 1) // 10  # 0-based
    while len(data["windows"]) <= chunk_idx:
        data["windows"].append({"chapters": 0, "total": 0, "counts": []})

    data["windows"][chunk_idx]["chapters"] += 1
    data["windows"][chunk_idx]["total"] += dash_count
    data["windows"][chunk_idx].setdefault("counts", []).append(dash_count)

    # 自动更新预算
    trend_data = json.loads(json.dumps(data))  # shallow copy for trend analysis
    cmd_trend(["--project-root", str(project_root)])

    save_trend_data(project_root, data)
    print(json.dumps({
        "status": "ok",
        "chapter_dashes": dash_count,
        "total_chapters": total,
    }, ensure_ascii=False))


def cmd_analyze(args: list):
    """dash_tracker.py analyze — 完整密度趋势分析"""
    project_root = None
    for i, a in enumerate(args):
        if a == "--project-root" and i + 1 < len(args):
            project_root = Path(args[i + 1])
    if not project_root:
        project_root = Path.cwd()

    data = load_trend_data(project_root)
    windows = data.get("windows", [])

    if not windows:
        print(json.dumps({"status": "no_data", "message": "尚无足够的破折号趋势数据"}, ensure_ascii=False))
        return

    # 总体趋势
    totals = [w.get("total", 0) for w in windows]
    trend_direction = "持平"
    if len(totals) >= 2:
        if totals[-1] > totals[0] * 1.3:
            trend_direction = "上升 ↑"
        elif totals[-1] < totals[0] * 0.7:
            trend_direction = "下降 ↓"

    avg_per_chapter = sum(totals) / sum(w.get("chapters", 1) for w in windows)

    result = {
        "status": "ok",
        "trend_direction": trend_direction,
        "windows": [
            {
                "window": i + 1,
                "chapters": w.get("chapters", 0),
                "total_dashes": w.get("total", 0),
                "avg_per_chapter": round(w.get("total", 0) / max(w.get("chapters", 1), 1), 1),
            }
            for i, w in enumerate(windows)
        ],
        "overall_avg_per_chapter": round(avg_per_chapter, 1),
        "current_budget": data.get("current_budget", 5),
        "total_chapters_analyzed": data.get("total_chapters_analyzed", 0),
        "suggestion": "",
    }

    if trend_direction == "上升 ↑":
        result["suggestion"] = "⚠️ 破折号密度呈上升趋势，建议主动压低下一章预算至 3 次，并做一次全篇替换"
    elif avg_per_chapter > 4:
        result["suggestion"] = "📊 平均密度偏高，建议在后续章节中有意控制"
    else:
        result["suggestion"] = "✅ 破折号密度控制良好，继续保持"

    print(json.dumps(result, ensure_ascii=False))


# ─── CLI 入口 ──────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("用法: dash_tracker.py <command> [args...]", file=sys.stderr)
        print("命令: check, trend, update, analyze", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "check": cmd_check,
        "trend": cmd_trend,
        "update": cmd_update,
        "analyze": cmd_analyze,
    }

    if command not in commands:
        print(f"未知命令: {command}", file=sys.stderr)
        sys.exit(1)

    commands[command](args)


if __name__ == "__main__":
    main()
