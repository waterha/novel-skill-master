#!/usr/bin/env python3
"""
anti_ai_check.py — Anti-AI 文本痕迹检测器

识别和统计 AI 生成文本的典型特征，输出结构化检查结果。

触发条件（由 Claude 在写章/审查流程中调用）：
  novel-write Step 4 (润色与 Anti-AI 终检)
    → python anti_ai_check.py check --chapter <路径/第XX章.md>
      输出所有检测项的 pass/fail + 违规详情

  novel-review Step 4 (审查时作为文笔维度参考)
    → python anti_ai_check.py score --chapter <路径/第XX章.md>
      输出 Anti-AI 评分（0-100）

  批量/定时扫描
    → python anti_ai_check.py batch --dir <正文目录>
      扫描目录下所有章节，输出汇总报告

返回值：JSON 到 stdout，Claude 解析后展示或自动修复。
"""

import json
import sys
import re
from pathlib import Path
from typing import Optional

# ─── AI 高频词汇表 ─────────────────────────────────────────────────────────

BANNED_WORDS = {
    "此外": {"action": "删除或不用", "severity": "minor"},
    "另外": {"action": "删除或不用", "severity": "minor"},
    "值得注意的是": {"action": "直接删除", "severity": "major"},
    "需要强调的是": {"action": "直接删除", "severity": "major"},
    "彰显": {"action": "换成具体动作描述", "severity": "major"},
    "诠释": {"action": "换成具体动作描述", "severity": "major"},
    "赋能": {"action": "换成具体动作描述", "severity": "major"},
    "不禁": {"action": "改为具体反应", "severity": "minor"},
    "不由得": {"action": "改为具体反应", "severity": "minor"},
    "油然而生": {"action": "改为具体感受", "severity": "major"},
    "心潮澎湃": {"action": "改为具体动作", "severity": "major"},
    "这一刻": {"action": "删除或改为具体时间", "severity": "minor"},
    "璀璨": {"action": "改为具象描述", "severity": "minor"},
    "瑰丽": {"action": "改为具象描述", "severity": "minor"},
    "绚烂": {"action": "改为具象描述", "severity": "minor"},
}

# 可保留一定比例的词语
HIGH_FREQ_WORDS = {
    "仿佛": {"keep_ratio": 0.3, "action": "删掉70%，保留30%"},
    "宛如": {"keep_ratio": 0.3, "action": "删掉70%，保留30%"},
    "如同": {"keep_ratio": 0.3, "action": "删掉70%，保留30%"},
    "似乎": {"action": "尽量明确肯定表述", "severity": "minor"},
    "好像": {"action": "尽量明确肯定表述", "severity": "minor"},
}

# 情感标签词
EMOTION_LABELS = [
    "他感到", "她感到", "他心中涌起", "她心中涌起",
    "他内心", "她内心", "一股", "一阵",
]


# ─── 正则模式 ──────────────────────────────────────────────────────────────

# 三段式结构
THREE_PART_RE = re.compile(
    r'(首先|第一|其一)[^。]*。\s*(其次|第二|其二)[^。]*。\s*(最后|第三|其三)[^。]*。',
    re.MULTILINE
)

# 总结式结尾
SUMMARY_END_RE = re.compile(
    r'(总而言之|综上所述|由此可见|总的来说|言而总之|总的来说)',
)

# 「是……的」句式
SHI_DE_RE = re.compile(r'是[^。，！？\n]{2,20}的')

# 连续四字成语
FOUR_CHAR_IDIOM_RE = re.compile(r'[一-鿿]{4}(?:[，、][一-鿿]{4})+')

# 破折号滥用（调用 dash_tracker.py，这里做基础统计）
DASH_RE = re.compile(r'——')

# 「的」字密度
DE_CHAR_RE = re.compile(r'的')

# 模糊修饰词
VAGUE_WORDS_RE = re.compile(r'像是|仿佛|某种|一种(?![^。，！？\n]{0,5}是)')

# 场景后解释句（"这意味着""这让他明白了""从此以后"）
OVER_EXPLAIN_RE = re.compile(r'这意味着[^。！？\n]{0,30}[。！？]|这让他(明白|知道|意识)[^。！？\n]{0,20}[。！？]|从此[^。！？\n]{0,30}[。！？]')

# 连续主语检测（连续2句以上以"他""她""它"开头）
CONSECUTIVE_SUBJECT_PATTERN = re.compile(
    r'(?:^|\n\n)(?:他|她|它)[^。！？]{5,50}。[。！？\n]*(?:他|她|它)[^。！？]{5,50}。[。！？\n]*(?:他|她|它)[^。！？]{5,50}[。！？]',
    re.MULTILINE
)


# ─── 检查函数 ───────────────────────────────────────────────────────────────

def check_banned_words(text: str) -> list:
    """检查禁用词"""
    issues = []
    for word, info in BANNED_WORDS.items():
        count = text.count(word)
        if count > 0:
            issues.append({
                "check": "禁用高频词",
                "word": word,
                "count": count,
                "action": info["action"],
                "severity": info["severity"],
                "positions": find_positions(text, word),
            })
    return issues


def check_high_freq_words(text: str) -> list:
    """检查高频可保留词（标记但不算违规）"""
    issues = []
    for word, info in HIGH_FREQ_WORDS.items():
        count = text.count(word)
        if count > 0:
            issues.append({
                "check": "高频词（可保留部分）",
                "word": word,
                "count": count,
                "action": info.get("action", ""),
                "note": f"建议保留比例 {info.get('keep_ratio', 0.3)}",
            })
    return issues


def check_three_part_structure(text: str) -> list:
    """检查三段式论证结构"""
    matches = THREE_PART_RE.findall(text)
    issues = []
    if matches:
        issues.append({
            "check": "三段式结构",
            "count": len(matches),
            "severity": "blocking",
            "action": "必须重构，用自然过渡代替",
        })
    return issues


def check_summary_ending(text: str) -> list:
    """检查总结式结尾"""
    matches = SUMMARY_END_RE.findall(text)
    issues = []
    if matches:
        issues.append({
            "check": "总结式结尾词",
            "words": matches,
            "count": len(matches),
            "severity": "blocking",
            "action": "必须删除，改为行动/对话结尾",
        })
    return issues


def check_emotion_labels(text: str) -> list:
    """检查抽象情感标签"""
    issues = []
    for label in EMOTION_LABELS:
        count = text.count(label)
        if count > 1:
            issues.append({
                "check": f"情感标签「{label}」",
                "count": count,
                "limit": 1,
                "severity": "major",
                "action": "改为行为暗示（握拳/发抖/沉默等动作）",
            })
    return issues


def check_shide_pattern(text: str) -> list:
    """检查「是……的」句式密度"""
    matches = SHI_DE_RE.findall(text)
    count = len(matches)
    issues = []
    if count > 3:
        issues.append({
            "check": "「是……的」句式",
            "count": count,
            "limit": 3,
            "severity": "minor",
            "action": "建议简化，改为直接陈述",
            "examples": matches[:3],
        })
    return issues


def check_four_char_idioms(text: str) -> list:
    """检查连续四字成语"""
    matches = FOUR_CHAR_IDIOM_RE.findall(text)
    issues = []
    if matches:
        total_words = sum(len(m) for m in matches)
        issues.append({
            "check": "连续四字成语",
            "count": len(matches),
            "total_chars": total_words,
            "severity": "major" if total_words > 12 else "minor",
            "action": "拆分连用成语，替换为口语化表达",
            "examples": matches[:3],
        })
    return issues


def check_de_density(text: str) -> list:
    """检查「的」字密度"""
    sentences = re.split(r'[。！？\n]', text)
    issues = []
    for i, sent in enumerate(sentences):
        de_count = len(DE_CHAR_RE.findall(sent))
        if de_count > 3 and len(sent) > 10:
            issues.append({
                "check": "「的」字密集",
                "sentence": i + 1,
                "count": de_count,
                "limit": 3,
                "severity": "minor",
                "action": "每句「的」不超过2个",
                "snippet": sent[:50],
            })
    return issues


def check_first_last_structure(text: str) -> list:
    """检查「首先…其次…最后」结构"""
    # 更宽松的检测
    patterns = [
        (r'首先[^。]*。\s*其次', "首先…其次模式"),
        (r'其一[^。]*。\s*其二', "其一…其二模式"),
    ]
    issues = []
    for pat, label in patterns:
        if re.search(pat, text):
            issues.append({
                "check": label,
                "severity": "blocking",
                "action": "必须重构为自然叙述",
            })
    return issues


def count_total_dashes(text: str) -> int:
    """统计破折号总数"""
    return len(DASH_RE.findall(text))


def find_positions(text: str, word: str) -> list:
    """查找所有出现位置（行号）"""
    positions = []
    for i, line in enumerate(text.split('\n'), 1):
        if word in line:
            positions.append(i)
    return positions[:10]  # 最多返回10个


def check_vague_modifiers(text: str) -> list:
    """检查模糊修饰词（像是/仿佛/某种/一种）"""
    matches = VAGUE_WORDS_RE.findall(text)
    count = len(matches)
    issues = []
    if count > 3:
        issues.append({
            "check": "模糊修饰词过密",
            "count": count,
            "limit": 3,
            "severity": "major",
            "action": "删除不必要的模糊修饰词，换用明确表述",
        })
    return issues


def check_over_explain(text: str) -> list:
    """检查场景后的过度解释句"""
    matches = OVER_EXPLAIN_RE.findall(text)
    issues = []
    if matches:
        issues.append({
            "check": "场景后过度解释",
            "count": len(matches),
            "severity": "major",
            "action": "直接删除解释句，让场景本身说话",
            "examples": [m[:40] for m in matches[:3]],
        })
    return issues


def check_consecutive_subjects(text: str) -> list:
    """检查连续3句以上同一主语"""
    matches = CONSECUTIVE_SUBJECT_PATTERN.findall(text)
    issues = []
    if matches:
        issues.append({
            "check": "连续同一主语开头",
            "count": len(matches),
            "severity": "minor",
            "action": "合并主语或换主语，避免连续3句以他/她/它开头",
        })
    return issues


# ─── 评分 ───────────────────────────────────────────────────────────────────

def calculate_score(issues: dict, text: str) -> dict:
    """根据问题计算 Anti-AI 评分"""
    deductions = 0

    # blocking 问题：每个扣 20 分
    for issue_list in issues.values():
        for i in issue_list:
            if i.get("severity") == "blocking":
                deductions += 20
            elif i.get("severity") == "major":
                deductions += 10
            elif i.get("severity") == "minor":
                deductions += 3

    score = max(0, min(100, 100 - deductions))
    rating = "优秀" if score >= 90 else "良好" if score >= 75 else "合格" if score >= 60 else "需修改"

    return {
        "score": score,
        "deductions": deductions,
        "rating": rating,
    }


# ─── 命令实现 ────────────────────────────────────────────────────────────────

def cmd_check(args: list):
    """anti_ai_check.py check — 单章完整检测"""
    chapter_path = None
    for i, a in enumerate(args):
        if a == "--chapter" and i + 1 < len(args):
            chapter_path = args[i + 1]
        if a == "--file" and i + 1 < len(args):
            chapter_path = args[i + 1]

    if not chapter_path:
        print(json.dumps({"error": "请指定 --chapter <路径>"}, ensure_ascii=False))
        sys.exit(1)

    p = Path(chapter_path)
    if not p.exists():
        print(json.dumps({"error": f"文件不存在: {chapter_path}"}, ensure_ascii=False))
        sys.exit(1)

    text = p.read_text(encoding="utf-8")

    all_issues = {
        "banned_words": check_banned_words(text),
        "high_freq_words": check_high_freq_words(text),
        "three_part": check_three_part_structure(text),
        "first_last": check_first_last_structure(text),
        "summary_ending": check_summary_ending(text),
        "emotion_labels": check_emotion_labels(text),
        "shide_pattern": check_shide_pattern(text),
        "four_char_idioms": check_four_char_idioms(text),
        "de_density": check_de_density(text),
        "vague_modifiers": check_vague_modifiers(text),
        "over_explain": check_over_explain(text),
        "consecutive_subjects": check_consecutive_subjects(text),
    }

    dash_count = count_total_dashes(text)
    if dash_count > 8:
        all_issues["dash_overuse"] = [{
            "check": "破折号总数超标",
            "count": dash_count,
            "limit": 8,
            "severity": "major",
            "action": "减少破折号使用，参考 dash_tracker.py 的详细分析",
        }]
    elif dash_count > 5:
        all_issues["dash_overuse"] = [{
            "check": "破折号偏多",
            "count": dash_count,
            "limit": 5,
            "severity": "minor",
            "action": "建议将部分破折号替换为句号/逗号/冒号",
        }]

    score = calculate_score(all_issues, text)

    # 标准化输出
    flat_issues = []
    for category, items in all_issues.items():
        for item in items:
            item["category"] = category
            flat_issues.append(item)

    blocking = [i for i in flat_issues if i.get("severity") == "blocking"]
    major = [i for i in flat_issues if i.get("severity") == "major"]
    minor = [i for i in flat_issues if i.get("severity") == "minor"]

    print(json.dumps({
        "chapter": str(p),
        "total_issues": len(flat_issues),
        "blocking": len(blocking),
        "major": len(major),
        "minor": len(minor),
        "score": score,
        "blocking_issues": blocking,
        "major_issues": major,
        "minor_issues": minor,
        "all_issues": flat_issues,
        "pass": score["score"] >= 60,
        "anti_ai_force_check": "pass" if score["score"] >= 60 else "fail",
    }, ensure_ascii=False))


def cmd_score(args: list):
    """anti_ai_check.py score — 输出评分"""
    chapter_path = None
    for i, a in enumerate(args):
        if a == "--chapter" and i + 1 < len(args):
            chapter_path = args[i + 1]
        if a == "--file" and i + 1 < len(args):
            chapter_path = args[i + 1]

    if not chapter_path:
        print(json.dumps({"error": "请指定 --chapter <路径>"}, ensure_ascii=False))
        sys.exit(1)

    p = Path(chapter_path)
    if not p.exists():
        print(json.dumps({"error": f"文件不存在: {chapter_path}"}, ensure_ascii=False))
        sys.exit(1)

    text = p.read_text(encoding="utf-8")

    all_issues = {
        "banned_words": check_banned_words(text),
        "high_freq_words": check_high_freq_words(text),
        "three_part": check_three_part_structure(text),
        "summary_ending": check_summary_ending(text),
        "emotion_labels": check_emotion_labels(text),
    }

    score = calculate_score(all_issues, text)

    print(json.dumps({
        "chapter": str(p),
        "score": score,
        "dimensions": {
            "banned_words": len(all_issues["banned_words"]),
            "three_part_structure": len(all_issues["three_part"]),
            "summary_ending": len(all_issues["summary_ending"]),
            "emotion_labels": len(all_issues["emotion_labels"]),
        },
    }, ensure_ascii=False))


def cmd_batch(args: list):
    """anti_ai_check.py batch — 批量扫描"""
    dir_path = None
    for i, a in enumerate(args):
        if a == "--dir" and i + 1 < len(args):
            dir_path = args[i + 1]

    if not dir_path:
        print(json.dumps({"error": "请指定 --dir <目录路径>"}, ensure_ascii=False))
        sys.exit(1)

    d = Path(dir_path)
    if not d.is_dir():
        print(json.dumps({"error": f"目录不存在: {dir_path}"}, ensure_ascii=False))
        sys.exit(1)

    md_files = sorted(d.rglob("第*章*.md")) + sorted(d.rglob("第*章*.txt"))
    if not md_files:
        md_files = sorted(d.glob("*.md"))

    results = []
    total_issues = 0
    passed = 0

    for f in md_files:
        text = f.read_text(encoding="utf-8")
        issues = {
            "banned_words": check_banned_words(text),
            "three_part": check_three_part_structure(text),
            "summary_ending": check_summary_ending(text),
        }
        flat = []
        for cat, items in issues.items():
            for item in items:
                item["category"] = cat
                flat.append(item)

        blocked = any(i.get("severity") == "blocking" for i in flat)
        issue_count = len(flat)
        total_issues += issue_count
        if not blocked:
            passed += 1

        results.append({
            "chapter": f.name,
            "issues": issue_count,
            "blocking": blocked,
            "pass": not blocked,
        })

    print(json.dumps({
        "directory": str(d),
        "total_chapters": len(md_files),
        "passed": passed,
        "failed": len(md_files) - passed,
        "total_issues": total_issues,
        "results": results,
    }, ensure_ascii=False))


# ─── CLI 入口 ──────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("用法: anti_ai_check.py <command> [args...]", file=sys.stderr)
        print("命令: check, score, batch", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "check": cmd_check,
        "score": cmd_score,
        "batch": cmd_batch,
    }

    if command not in commands:
        print(f"未知命令: {command}", file=sys.stderr)
        sys.exit(1)

    commands[command](args)


if __name__ == "__main__":
    main()
