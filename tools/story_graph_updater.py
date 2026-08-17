#!/usr/bin/env python3
"""
story_graph_updater.py — 知识图谱自动更新器

每章写完后自动提取章节正文中的实体信息，回写知识图谱。
与 story_graph_builder.py 配合使用。

主要功能：
1. 从章节正文提取角色、地点、事件等信息
2. 自动更新图谱节点状态
3. 检测伏笔候选信号（正式状态由 foreshadowing.json 管理）
4. 生成改纲级联影响报告

子命令：
  update-from-chapter  — 从单章提取信息并更新图谱
  cascade-report       — 改纲后生成级联影响报告

调用示例：
  python tools/story_graph_updater.py update-from-chapter \
    --project-root <路径> --chapter-file 正文/第01部/第001卷/第0015章-章名.md

返回值：JSON 到 stdout。
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from novel_common import (
    ensure_dir, load_json, read_text, save_json, slugify,
    chapter_no_from_name, count_chars, get_story_graph_path,
)

# ── 常量 ─────────────────────────────────────────────────────────────────────

# 抽取用的正则模式
CHARACTER_NAME_RE = re.compile(r"[一-鿿㐀-䶿]{2,4}")
LOCATION_SUFFIX = re.compile(r"(城|镇|村|山|河|湖|海|宫|殿|楼|阁|堂|馆|园|府|庄|寨|谷|洞|岛|洲|关|门|街|巷|路|桥)$")

# 伏笔信号词
FORESHADOW_PLANT_SIGNALS = [
    "隐约", "似乎", "仿佛", "不对劲", "奇怪", "异样",
    "不祥的预感", "觉得哪里不对", "一丝", "莫名的",
    "似乎有什么事", "暗暗记下", "留了个心眼",
]

FORESHADOW_RECALL_SIGNALS = [
    "原来", "果然", "如他所料", "应验了", "这才明白",
    "恍然大悟", "一切联系在一起", "终于知道",
    "线索指向", "真相大白", "谜底揭晓",
]


# ── 核心函数 ──────────────────────────────────────────────────────────────────

def extract_characters(text: str, known_names: List[str]) -> List[str]:
    """从正文中提取出现的角色名。"""
    found: Set[str] = set()
    for name in known_names:
        if name in text:
            found.add(name)
    return sorted(found)


def extract_locations(text: str) -> List[str]:
    """从正文中提取出现的地点。"""
    found: Set[str] = set()
    for m in re.finditer(r"(?:在|到|从|回到|前往|来到|赶往|进入|离开)([一-鿿]{2,8}(?:城|镇|村|山|河|湖|海|宫|殿|楼|阁|堂|馆|园|府|庄|寨|谷|洞|岛|洲|关|门|街|巷|路|桥|庙|寺|塔|台))", text):
        found.add(m.group(1))
    # 纯地点名词匹配
    for m in re.finditer(r"([一-鿿]{2,6}(?:城|镇|村|宫|殿|楼|堂|馆|府|庄|寨|谷|洞|关|门|街|巷|路|桥|庙|寺))", text):
        found.add(m.group(1))
    return sorted(found)[:10]


def extract_foreshadow_signals(text: str) -> Dict[str, List[str]]:
    """检测伏笔信号。"""
    planted: List[str] = []
    recalled: List[str] = []
    for signal in FORESHADOW_PLANT_SIGNALS:
        if signal in text:
            # 提取信号附近的上下文
            for m in re.finditer(rf"[^。！？\n]{{0,20}}{signal}[^。！？\n]{{0,40}}", text):
                planted.append(m.group(0).strip())
    for signal in FORESHADOW_RECALL_SIGNALS:
        if signal in text:
            for m in re.finditer(rf"[^。！？\n]{{0,20}}{signal}[^。！？\n]{{0,40}}", text):
                recalled.append(m.group(0).strip())
    return {"planted": planted[:5], "recalled": recalled[:5]}


def extract_events(text: str, chapter_no: int) -> List[Dict[str, Any]]:
    """从正文提取关键事件。"""
    events: List[Dict[str, Any]] = []
    # 战斗/冲突信号
    conflict_signals = ["战斗", "对战", "厮杀", "冲突", "争执", "对峙", "决战", "追杀"]
    for signal in conflict_signals:
        if signal in text:
            for m in re.finditer(rf"[^。！？\n]{{0,30}}{signal}[^。！？\n]{{0,30}}", text):
                desc = m.group(0).strip()
                if desc and len(desc) > 4:
                    events.append({
                        "description": desc[:120],
                        "type": "conflict" if signal in {"战斗", "对战", "厮杀", "决战", "追杀"} else "interaction",
                    })
                if len(events) >= 3:
                    break
        if len(events) >= 3:
            break
    return events


def update_from_chapter(
    project_root: Path,
    chapter_file: str,
    chapter_no: int,
    known_names: List[str],
) -> Dict[str, Any]:
    """从单章提取信息并更新知识图谱。"""
    graph_path = get_story_graph_path(project_root)
    graph = load_json(graph_path, default={"version": "2.0", "nodes": [], "edges": [], "timeline": []})
    for key in ("nodes", "edges", "timeline"):
        if not isinstance(graph.get(key), list):
            graph[key] = []

    chapter_path = Path(chapter_file)
    if not chapter_path.exists():
        return {"ok": False, "error": f"章节文件不存在: {chapter_file}"}

    text = read_text(chapter_path)
    if not text.strip():
        return {"ok": False, "error": "章节内容为空"}

    extracted: Dict[str, Any] = {
        "chapter_no": chapter_no,
        "characters": [],
        "locations": [],
        "foreshadows": {"planted": [], "recalled": []},
        "events": [],
        "word_count": count_chars(text),
    }

    # 1. 提取角色
    found_chars = extract_characters(text, known_names)
    extracted["characters"] = found_chars

    # 更新角色节点状态（如已存在）
    node_index = {str(n.get("id")): n for n in graph["nodes"] if isinstance(n, dict)}
    for char_name in found_chars:
        char_id = f"character_{slugify(char_name)}"
        if char_id in node_index:
            node_index[char_id]["last_updated"] = chapter_no

    # 2. 提取地点
    found_locs = extract_locations(text)
    extracted["locations"] = found_locs

    # 3. 提取伏笔信号
    foreshadow_signals = extract_foreshadow_signals(text)
    extracted["foreshadows"] = foreshadow_signals

    # 信号词只能提供候选，不能证明某条伏笔已埋设或已回收。
    # 代理完成语义确认后，通过 foreshadowing_tracker.py 更新唯一账本。
    extracted["foreshadows"]["note"] = "候选信号未自动改写伏笔状态"

    # 4. 提取事件
    found_events = extract_events(text, chapter_no)
    extracted["events"] = found_events
    for i, evt in enumerate(found_events):
        evt_id = f"event_ch{chapter_no}_{i}"
        if evt_id not in node_index:
            graph["nodes"].append({
                "id": evt_id,
                "type": "event",
                "type_label": "事件",
                "name": evt["description"][:60],
                "description": evt["description"],
                "chapter": chapter_no,
                "participants": found_chars,
                "created_at": datetime.now().isoformat(),
                "last_updated": chapter_no,
            })

    # 5. 更新时间线
    graph["timeline"].append({
        "chapter": chapter_no,
        "event": f"第{chapter_no}章完成",
        "characters": found_chars,
        "locations": found_locs,
    })

    # 6. 更新版本标记
    graph["last_updated_chapter"] = chapter_no
    graph["updated_at"] = datetime.now().isoformat()

    ok = save_json(graph_path, graph)
    return {
        "ok": ok,
        "command": "update-from-chapter",
        "graph_file": str(graph_path),
        "chapter": chapter_no,
        "extracted": extracted,
        "graph_nodes": len(graph["nodes"]),
        "graph_edges": len(graph.get("edges", [])),
    }


def generate_cascade_report(
    project_root: Path,
    from_chapter: int,
    change_description: str,
) -> Dict[str, Any]:
    """改纲后生成级联影响报告。"""
    graph_path = get_story_graph_path(project_root)
    graph = load_json(graph_path, default={"nodes": []})

    affected_nodes: List[Dict[str, Any]] = []
    for n in graph.get("nodes", []):
        if not isinstance(n, dict):
            continue
        lu = int(n.get("last_updated", 0) or 0)
        if lu >= from_chapter:
            affected_nodes.append({
                "id": n.get("id"),
                "name": n.get("name"),
                "type": n.get("type"),
                "last_updated": lu,
            })

    # 标记级联待处理
    for n in graph.get("nodes", []):
        if isinstance(n, dict):
            lu = int(n.get("last_updated", 0) or 0)
            if lu >= from_chapter:
                n["cascade_pending"] = True

    save_json(graph_path, graph)

    return {
        "ok": True,
        "command": "cascade-report",
        "graph_file": str(graph_path),
        "from_chapter": from_chapter,
        "change_description": change_description,
        "affected_count": len(affected_nodes),
        "affected_nodes": affected_nodes,
        "recommendation": "请检查上述节点的信息是否需要更新以匹配新的主线方向",
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description="知识图谱自动更新器")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("update-from-chapter", help="从单章提取信息并更新图谱")
    s.add_argument("--project-root", required=True)
    s.add_argument("--chapter-file", required=True, help="章节文件路径")
    s.add_argument("--chapter-no", type=int, default=0, help="章节号（默认从文件名提取）")
    s.add_argument("--known-names", default="", help='已知角色名列表，逗号分隔，如 "李承乾,魏征,长孙无忌"')

    s = sub.add_parser("cascade-report", help="改纲后生成级联影响报告")
    s.add_argument("--project-root", required=True)
    s.add_argument("--from-chapter", required=True, type=int, help="改纲影响的起始章节号")
    s.add_argument("--change-description", default="", help="本次改纲的简要说明")

    args = p.parse_args()
    project_root = Path(args.project_root)

    try:
        if args.cmd == "update-from-chapter":
            chapter_no = args.chapter_no or chapter_no_from_name(args.chapter_file)
            known_names = [n.strip() for n in args.known_names.split(",") if n.strip()] if args.known_names else []
            # 尝试从 MASTER_SETTING.json 补全已知角色名
            if not known_names:
                ms_path = project_root / ".story-system" / "MASTER_SETTING.json"
                ms = load_json(ms_path, {})
                chars = ms.get("characters", {})
                if isinstance(chars, dict):
                    known_names = list(chars.keys())
            payload = update_from_chapter(project_root, args.chapter_file, chapter_no, known_names)

        elif args.cmd == "cascade-report":
            payload = generate_cascade_report(project_root, args.from_chapter, args.change_description)

        else:
            payload = {"ok": False, "error": f"未知命令: {args.cmd}"}

    except Exception as exc:
        payload = {"ok": False, "command": args.cmd, "error": repr(exc)}

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
