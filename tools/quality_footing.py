#!/usr/bin/env python3
"""
quality_footing.py — 写作质量定锚触发器

每5章触发一次质量状态调整，防止长篇写作中质量随章节递增而持续下滑。

触发条件：
  novel-write Step 0（写前预检）中调用
    → python quality_footing.py check --chapter <N> --project-root <路径>
      如果 N 是5的倍数，返回 quality_reset_needed=true，附带质量定锚指令

手动重置：
    → python quality_footing.py reset --project-root <路径>
      重置质量定锚计数器（用于主动调整）

返回值：JSON 到 stdout。
"""

import json
import sys
import os
from pathlib import Path

QUALITY_CHECKLIST = {
    "action": "quality_reset",
    "title": "写作状态调整（每5章定锚）",
    "checks": [
        "填充检查A - 章节体量：最近5章字节数趋势。如果连续下降，下一章目标恢复到4,500字节以上\n"
        "   - 检查方式：每章写完后检查文件字节数，低于4,500的需要回看场景是否展开充分",

        "填充检查B - 对话密度：最近3章中如果有2章以上没有完整对话交换（一来一回≥4句），\n"
        "   下一章必须有至少一段有深度的对话。独行章可以用内心追问替代对话。",

        "填充检查C - 场景容量：最近3章中是否有章节只有1个场景？\n"
        "   如果是，下一章必须安排2-3个场景，确保内容量充实。",

        "1. 破折号控制：最近5章的破折号数量趋势是上升还是下降？"
           "如果是上升，下一章预算强制降到3次",

        "2. 句式回顾：快速浏览最近3章，有没有出现以下模式？\n"
           "   - 连续3句以同一主语开头 → 下一章注意主语变化\n"
           "   - 链式句堆积 → 下一章多用短句\n"
           "   - 场景后跟了解释句 → 下一章场景结束就停",

        "3. 模糊词检查：搜一下最近一章的'像是''仿佛''某种''一种'\n"
           "   如果超过3处，下一章刻意减少到1-2处",

        "4. 节奏调整：\n"
           "   - 如果连续5章都是高强度剧情推进，下一章安排一段慢节奏过渡\n"
           "   - 如果连续5章都是慢节奏铺垫，下一章必须出现一个事件推动剧情",

        "5. 设定一致性：快速回看MASTER_SETTING.json中当前阶段的\n"
           "   能力约束和信息障碍，确认没有写越界",

        "6. 伏笔检查：检查 active_foreshadowing 中是否有\n"
           "   接近计划回收章节的伏笔需要铺垫",
    ],
    "recommendation": "建议写完本章后做一次体量检查：字节数够不够4,500？对话够不够？场景够不够？"
                      "三项填充检查比削减检查更重要——内容写够了再考虑删减。"
}


def find_project_root(root_arg: str = None) -> Path:
    if root_arg:
        return Path(root_arg)
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        target = parent / ".webnovel" / "master_state.json"
        if target.exists():
            return parent
    return cwd


def load_state(project_root: Path) -> dict:
    sp = project_root / ".webnovel" / "master_state.json"
    if not sp.exists():
        return {}
    with open(sp, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(project_root: Path, state: dict):
    sp = project_root / ".webnovel" / "master_state.json"
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def cmd_check(args: list):
    """检查当前章节是否需要触发质量定锚"""
    chapter_n = None
    project_root = None

    for i, a in enumerate(args):
        if a == "--chapter" and i + 1 < len(args):
            chapter_n = int(args[i + 1])
        if a == "--project-root" and i + 1 < len(args):
            project_root = args[i + 1]

    if chapter_n is None:
        print(json.dumps({"error": "请指定 --chapter <章号>"}, ensure_ascii=False))
        sys.exit(1)

    root = find_project_root(project_root)
    state = load_state(root)

    # 读取章节计数器
    chapters_since_reset = state.get("chapters_since_quality_reset", 0)

    is_milestone = (chapter_n > 0 and chapter_n % 5 == 0)
    needs_reset = is_milestone or (chapters_since_reset >= 5)

    result = {
        "chapter": chapter_n,
        "is_milestone": is_milestone,
        "chapters_since_reset": chapters_since_reset,
        "needs_quality_reset": needs_reset,
    }

    if needs_reset:
        result["action"] = QUALITY_CHECKLIST
        # 重置计数器
        state["chapters_since_quality_reset"] = 0
        state["last_quality_reset"] = f"第{chapter_n}章"
        save_state(root, state)
    else:
        result["action"] = None
        # 递增计数器
        state["chapters_since_quality_reset"] = chapters_since_reset + 1
        save_state(root, state)

    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_reset(args: list):
    """手动重置质量定锚计数器"""
    project_root = None
    for i, a in enumerate(args):
        if a == "--project-root" and i + 1 < len(args):
            project_root = args[i + 1]

    root = find_project_root(project_root)
    state = load_state(root)
    state["chapters_since_quality_reset"] = 0
    state["last_quality_reset"] = "手动重置"
    save_state(root, state)

    print(json.dumps({
        "status": "ok",
        "message": "质量定锚计数器已重置",
        "action": QUALITY_CHECKLIST,
    }, ensure_ascii=False, indent=2))


def main():
    if len(sys.argv) < 2:
        print("用法: quality_footing.py <command> [args...]", file=sys.stderr)
        print("命令: check, reset", file=sys.stderr)
        sys.exit(1)

    commands = {"check": cmd_check, "reset": cmd_reset}
    command = sys.argv[1]
    args = sys.argv[2:]

    if command not in commands:
        print(f"未知命令: {command}", file=sys.stderr)
        sys.exit(1)

    commands[command](args)


if __name__ == "__main__":
    main()
