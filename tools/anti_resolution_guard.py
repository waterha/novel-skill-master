#!/usr/bin/env python3
"""
anti_resolution_guard.py — 反向刹车校验器

防止 AI "过度帮助解决问题"的核心机制。
强制非终局章节不得解决主线核心冲突，并确保章末留有悬念。

核心检查：
1. 非终局章节禁止解决主线核心冲突
2. 每章必须新增至少一个未解决的次要问题或悬念
3. 章末必须留下悬念钩子（疑问/危机/转折型）
4. 检测"剧情加速"信号词（一年后、转眼间等概括推进）

子命令：
  check       — 校验单章是否违反反向刹车规则
  constraint  — 为即将写的章节生成约束 prompt

调用示例：
  python tools/anti_resolution_guard.py check --project-root <路径> --chapter 15
  python tools/anti_resolution_guard.py constraint --project-root <路径> --chapter 16

返回值：JSON 到 stdout。
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

from novel_common import (
    ensure_dir, load_json, read_text, get_pacing_path,
)


# ── 配置 ─────────────────────────────────────────────────────────────────────

# 章末悬念关键词（命中任一即认为有悬念钩子）
SUSPENSE_KEYWORDS: List[str] = [
    "？", "?", "……", "却", "突然", "竟", "谁知", "不料",
    "正要", "忽然", "然而", "可是", "怎料", "殊不知",
    "这才发现", "心中一凛", "暗道不好", "变了脸色",
    "一道身影", "来人竟是", "门外传来", "信封里",
    "倒吸一口凉气", "背后一凉", "毛骨悚然",
]

# 核心矛盾解决信号（出现多项可能意味着提前收束）
RESOLUTION_SIGNALS: List[str] = [
    "终于解决", "大功告成", "从此天下太平", "一切尘埃落定",
    "所有问题迎刃而解", "心中的石头终于落地", "再也不用担心",
    "彻底击败", "完全消灭", "一劳永逸", "最终胜利",
    "天下无敌", "再无对手", "圆满解决", "皆大欢喜",
    "危机解除", "问题解决了", "终于可以放心",
]

# 剧情加速信号（概括性跳过）
SKIP_SIGNALS: List[str] = [
    "转眼间", "一晃", "没过多久", "几个月后", "数日后",
    "几天后", "又过了", "经过一番", "苦修多日",
    "就这样", "不知不觉", "一晃就是",
    "在接下来的日子里", "时间飞逝",
]

# A/B/C 配额信号
QUOTA_A_SIGNALS: List[str] = [  # 主线矛盾实质推进
    "格局大变", "局面逆转", "关键突破", "核心矛盾激化", "决定性",
    "彻底扭转", "正面对决", "一举击破", "实质推进", "重大转折",
    "扭转乾坤", "形势骤变", "大局已定",
]
QUOTA_B_SIGNALS: List[str] = [  # 主要关系决定性升级
    "结为", "盟誓", "彻底决裂", "宣战", "告白", "成婚",
    "不共戴天", "反目成仇", "彻底翻脸", "情定终身",
    "生死与共", "誓死不渝", "割袍断义",
]
QUOTA_C_SIGNALS: List[str] = [  # 核心秘密完整揭露
    "真相大白", "秘密终于", "真实身份", "原来竟是",
    "全部揭露", "真正面目", "彻底曝光", "一切都是",
    "谜底揭开", "终于真相", "身份暴露",
]


def _extract_core_conflicts(project_root: Path) -> List[str]:
    """从设定契约和节奏状态中提取核心冲突列表。"""
    conflicts: List[str] = []

    # 从节奏状态中读取 forbidden_reveals
    pacing_path = get_pacing_path(project_root)
    st = load_json(pacing_path, {})
    chapters = st.get("chapters", [])
    if chapters:
        # 取最后一章的 constraints
        last = chapters[-1] if isinstance(chapters, list) and chapters else {}
        if isinstance(last, dict):
            cons = last.get("constraints", [])
            if isinstance(cons, list):
                conflicts.extend(str(c) for c in cons)

    # 从 MASTER_SETTING.json 读取 info_barriers
    ms_path = project_root / ".story-system" / "MASTER_SETTING.json"
    ms = load_json(ms_path, {})
    barriers = ms.get("info_barriers", [])
    if isinstance(barriers, list):
        for b in barriers:
            if isinstance(b, dict):
                hint = b.get("hint", "") or b.get("description", "")
                if hint:
                    conflicts.append(hint)
            elif isinstance(b, str):
                conflicts.append(b)

    return conflicts


# ── 子命令 ───────────────────────────────────────────────────────────────────

def cmd_check(args: argparse.Namespace) -> Dict[str, Any]:
    """检查单章是否违反反向刹车规则。"""
    project_root = Path(args.project_root)
    chapter = args.chapter

    # 找到章节文件
    chapter_file = None
    for d in [project_root / "正文", project_root / "03_manuscript"]:
        if d.exists():
            for f in d.glob("*.md"):
                m = re.search(rf"第{chapter}章", f.name)
                if m:
                    chapter_file = f
                    break
        if chapter_file:
            break

    if not chapter_file:
        return {"ok": False, "error": f"未找到第 {chapter} 章的正文文件"}

    text = read_text(chapter_file)
    if not text.strip():
        return {"ok": False, "error": "章节内容为空"}

    issues: List[str] = []
    checks_passed: List[str] = []

    # 检查1: 核心冲突解决检测
    core_conflicts = _extract_core_conflicts(project_root)
    resolution_hits = [s for s in RESOLUTION_SIGNALS if s in text]
    if resolution_hits:
        issues.append(f"检测到冲突解决信号: {', '.join(resolution_hits[:4])}")
        # 检查是否命中核心冲突
        for cc in core_conflicts:
            if cc and cc in text:
                issues.append(f"核心冲突「{cc}」可能在非终局章节被解决")
    else:
        checks_passed.append("无过早解决核心冲突")

    # 检查2: 章末悬念检测
    tail = text[-500:] if len(text) > 500 else text
    has_suspense = any(kw in tail for kw in SUSPENSE_KEYWORDS)
    if has_suspense:
        checks_passed.append("章末存在悬念钩子")
    else:
        issues.append("章末缺少悬念钩子（未命中任何悬念关键词）")

    # 检查3: 剧情加速检测
    skip_hits = [s for s in SKIP_SIGNALS if s in text]
    if skip_hits:
        issues.append(f"检测到剧情加速信号: {', '.join(skip_hits[:4])}（注意适度使用）")
    else:
        checks_passed.append("无剧情加速信号")

    # 检查4: A/B/C 配额触发检测
    quota_a_hits = [s for s in QUOTA_A_SIGNALS if s in text]
    quota_b_hits = [s for s in QUOTA_B_SIGNALS if s in text]
    quota_c_hits = [s for s in QUOTA_C_SIGNALS if s in text]

    triggers = []
    if quota_a_hits:
        triggers.append("A")
    if quota_b_hits:
        triggers.append("B")
    if quota_c_hits:
        triggers.append("C")

    if len(triggers) > 1:
        issues.append(f"配额违规：同时触发 {'/'.join(triggers)} 共 {len(triggers)} 项（限额 1 项）")
    elif len(triggers) == 1:
        checks_passed.append(f"触发配额: {triggers[0]}")
    else:
        checks_passed.append("未触发任何配额（可接受的推进节奏）")

    # 检查5: 章尾检测 — 是否以"完美结局"式的句子结尾
    last_sentence = ""
    for m in re.finditer(r"[^。！？\n]+[。！？]", tail):
        last_sentence = m.group(0)
    if last_sentence:
        finality_words = ["好了", "够了", "行了", "结束了", "成功了", "完成了"]
        if any(w in last_sentence for w in finality_words):
            issues.append(f"章末收束感过强: 「{last_sentence.strip()[:40]}」")
    else:
        checks_passed.append("章末无明显收束感")

    return {
        "ok": len(issues) == 0,
        "command": "check",
        "chapter": chapter,
        "chapter_file": str(chapter_file),
        "checks_passed": checks_passed,
        "issues": issues,
        "quota_triggers": triggers,
        "has_suspense": has_suspense,
        "has_resolution_signals": len(resolution_hits) > 0,
        "has_skip_signals": len(skip_hits) > 0,
        "verdict": "通过" if len(issues) == 0 else "失败",
    }


def cmd_constraint(args: argparse.Namespace) -> Dict[str, Any]:
    """为即将写的章节生成反刹车约束 prompt。"""
    project_root = Path(args.project_root)
    chapter = args.chapter

    # 检查上一章的数据
    pacing_path = get_pacing_path(project_root)
    st = load_json(pacing_path, {})
    chapters = st.get("chapters", [])

    prev_chapter = None
    for c in chapters:
        if isinstance(c, dict) and c.get("chapter") == chapter - 1:
            prev_chapter = c
            break

    core_conflicts = _extract_core_conflicts(project_root)

    # 构建约束 prompt
    constraints: List[str] = [
        "## 反刹车约束（Anti-Resolution Guard）",
        "",
        "### 硬性规则（不可违反）",
        "1. 🔴 非终局章节禁止解决主线核心冲突",
        "2. 🔴 每章至多触发 A/B/C 配额中的 1 项",
        "3. 🟡 章末必须留下悬念钩子（疑问/危机/转折型）",
        "4. 🟡 避免使用时间概括推进（转眼/一晃/几个月后）",
    ]

    if core_conflicts:
        constraints.append("")
        constraints.append("### 核心冲突（本章不得解决）")
        for cc in core_conflicts:
            constraints.append(f"- 🔒 {cc}")

    if prev_chapter:
        prev_pacing = prev_chapter.get("pacing", "")
        if prev_pacing == "fast":
            constraints.append("")
            constraints.append("### 节奏提示")
            constraints.append("- 上一章为快档，本章建议使用慢档或中档缓冲")
        prev_triggers = prev_chapter.get("triggers", [])
        if prev_triggers:
            constraints.append(f"- 上一章触发配额: {', '.join(prev_triggers)}，本章注意换挡")

    constraints.append("")
    constraints.append("### 推荐写法")
    constraints.append("- 聚焦场景细节和人物互动，而非快速推进剧情")
    constraints.append("- 章末以 '突然/却/然而/谁知' 等词制造悬念")
    constraints.append("- 让配角有独立于主线的行动和情感")

    constraint_prompt = "\n".join(constraints)

    return {
        "ok": True,
        "command": "constraint",
        "chapter": chapter,
        "constraint_prompt": constraint_prompt,
        "core_conflicts": core_conflicts,
        "prev_chapter_pacing": prev_chapter.get("pacing") if prev_chapter else None,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description="反向刹车校验器")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("check", help="校验单章是否违反反向刹车规则")
    s.add_argument("--project-root", required=True)
    s.add_argument("--chapter", required=True, type=int, help="章节号")

    s = sub.add_parser("constraint", help="生成本章约束 prompt")
    s.add_argument("--project-root", required=True)
    s.add_argument("--chapter", required=True, type=int, help="即将写的章节号")

    args = p.parse_args()

    dispatch = {
        "check": cmd_check,
        "constraint": cmd_constraint,
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
