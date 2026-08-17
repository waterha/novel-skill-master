#!/usr/bin/env python3
"""
story_graph_builder.py — 知识图谱构建器

将小说设定从平面文件转化为图结构（节点+边+版本），实现：
1. 角色/地点/势力/事件/伏笔的关系网络化管理
2. 每章写后自动回写图谱（配合 story_graph_updater.py）
3. 改纲时级联标记受影响节点
4. 写前生成上下文摘要注入写作流程

子命令：
  init              — 初始化空图谱
  add-node          — 添加节点
  update-node       — 更新节点字段
  add-edge          — 添加关系边
  delete-node       — 删除节点（及其关联边）
  export            — 导出 Mermaid 关系图
  generate-context  — 生成写前上下文摘要
  validate          — 校验图谱一致性

调用示例：
  python tools/story_graph_builder.py init --project-root <路径>
  python tools/story_graph_builder.py add-node --project-root <路径> --type character --name "李承乾"
  python tools/story_graph_builder.py add-edge --project-root <路径> --type ally --source char_李承乾 --target char_魏征
  python tools/story_graph_builder.py export --project-root <路径>
  python tools/story_graph_builder.py generate-context --project-root <路径> --chapter 15

返回值：JSON 到 stdout，Claude 解析后做决策。
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# 导入共享工具
from novel_common import (
    ensure_dir, load_json, save_json, slugify,
    get_story_graph_path,
)

# ── 节点类型 ──────────────────────────────────────────────────────────────────

NODE_TYPES: Set[str] = {
    "character",     # 角色
    "location",      # 地点
    "faction",       # 势力/组织
    "event",         # 事件
    "foreshadow",    # 伏笔
    "worldrule",     # 世界观规则
    "item",          # 重要物品
}

NODE_TYPE_LABELS: Dict[str, str] = {
    "character": "角色",
    "location": "地点",
    "faction": "势力",
    "event": "事件",
    "foreshadow": "伏笔",
    "worldrule": "规则",
    "item": "物品",
}

# ── 边类型 ────────────────────────────────────────────────────────────────────

EDGE_TYPES: Set[str] = {
    "ally",           # 同盟
    "enemy",          # 敌对
    "mentor",         # 师徒
    "romantic",       # 情感
    "subordinate",    # 从属
    "belongs_to",     # 归属
    "located_at",     # 位于
    "triggers",       # 引发
    "foreshadows",    # 铺垫
    "owns",           # 持有
}

EDGE_TYPE_LABELS: Dict[str, str] = {
    "ally": "同盟",
    "enemy": "敌对",
    "mentor": "师徒",
    "romantic": "情感",
    "subordinate": "从属",
    "belongs_to": "归属",
    "located_at": "位于",
    "triggers": "引发",
    "foreshadows": "铺垫",
    "owns": "持有",
}


def _empty_graph() -> Dict[str, Any]:
    return {
        "version": "2.0",
        "last_updated_chapter": 0,
        "updated_at": datetime.now().isoformat(),
        "nodes": [],
        "edges": [],
        "timeline": [],
    }


def _load_graph(path: Path) -> Dict[str, Any]:
    g = load_json(path, default=_empty_graph())
    for key in ("nodes", "edges", "timeline"):
        if not isinstance(g.get(key), list):
            g[key] = []
    g.setdefault("version", "2.0")
    return g


def _save_graph(path: Path, graph: Dict[str, Any]) -> bool:
    graph["updated_at"] = datetime.now().isoformat()
    return save_json(path, graph)


def _make_node_id(node_type: str, name: str) -> str:
    return f"{node_type}_{slugify(name)}"


def _make_edge_id(edge_type: str, source: str, target: str) -> str:
    return f"{edge_type}_{slugify(source)}_{slugify(target)}"


def _index_nodes(graph: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(n["id"]): n
        for n in graph.get("nodes", [])
        if isinstance(n, dict) and n.get("id")
    }


# ── 子命令：init ─────────────────────────────────────────────────────────────

def cmd_init(args: argparse.Namespace) -> Dict[str, Any]:
    path = get_story_graph_path(Path(args.project_root))
    ensure_dir(path.parent)

    if path.exists() and not args.force:
        graph = _load_graph(path)
        return {
            "ok": True, "command": "init",
            "graph_file": str(path), "created": False,
            "node_count": len(graph["nodes"]),
            "edge_count": len(graph["edges"]),
            "message": "图谱已存在；如需覆盖请加 --force",
        }

    graph = _empty_graph()
    ok = _save_graph(path, graph)
    return {"ok": ok, "command": "init", "graph_file": str(path), "created": ok}


# ── 子命令：add-node ──────────────────────────────────────────────────────────

def cmd_add_node(args: argparse.Namespace) -> Dict[str, Any]:
    path = get_story_graph_path(Path(args.project_root))
    graph = _load_graph(path)

    if args.type not in NODE_TYPES:
        return {"ok": False, "command": "add-node", "error": f"非法节点类型: {args.type}，可选: {', '.join(sorted(NODE_TYPES))}"}

    try:
        attrs = json.loads(args.attrs) if args.attrs else {}
    except json.JSONDecodeError:
        return {"ok": False, "command": "add-node", "error": "attrs 不是合法的 JSON"}

    node_id = args.id or _make_node_id(args.type, args.name)

    if any(str(n.get("id")) == node_id for n in graph["nodes"] if isinstance(n, dict)):
        return {"ok": False, "command": "add-node", "error": f"节点已存在: {node_id}（如需更新请用 update-node）"}

    node: Dict[str, Any] = {
        "id": node_id,
        "type": args.type,
        "name": args.name,
        "type_label": NODE_TYPE_LABELS.get(args.type, args.type),
        "created_at": datetime.now().isoformat(),
        "last_updated": args.last_updated or 0,
    }
    node.update(attrs)
    graph["nodes"].append(node)
    ok = _save_graph(path, graph)
    return {
        "ok": ok, "command": "add-node",
        "graph_file": str(path), "node": node,
        "node_count": len(graph["nodes"]),
    }


# ── 子命令：update-node ───────────────────────────────────────────────────────

def cmd_update_node(args: argparse.Namespace) -> Dict[str, Any]:
    path = get_story_graph_path(Path(args.project_root))
    graph = _load_graph(path)

    target = None
    for n in graph["nodes"]:
        if isinstance(n, dict) and str(n.get("id")) == args.node_id:
            target = n
            break

    if target is None:
        return {"ok": False, "command": "update-node", "error": f"节点不存在: {args.node_id}"}

    try:
        updates = json.loads(args.attrs) if args.attrs else {}
    except json.JSONDecodeError:
        return {"ok": False, "command": "update-node", "error": "attrs 不是合法的 JSON"}

    if not updates:
        return {"ok": False, "command": "update-node", "error": "未提供更新字段"}

    # id 和 type 不允许修改
    updates.pop("id", None)
    updates.pop("type", None)

    target.update(updates)
    target["last_updated"] = args.chapter or target.get("last_updated", 0)
    ok = _save_graph(path, graph)
    return {
        "ok": ok, "command": "update-node",
        "graph_file": str(path), "node": target,
    }


# ── 子命令：delete-node ──────────────────────────────────────────────────────

def cmd_delete_node(args: argparse.Namespace) -> Dict[str, Any]:
    path = get_story_graph_path(Path(args.project_root))
    graph = _load_graph(path)

    node_id = args.node_id
    before_count = len(graph["nodes"])

    graph["nodes"] = [n for n in graph["nodes"] if isinstance(n, dict) and str(n.get("id")) != node_id]
    after_count = len(graph["nodes"])

    if before_count == after_count:
        return {"ok": False, "command": "delete-node", "error": f"节点不存在: {node_id}"}

    # 同时删除关联边
    edge_before = len(graph["edges"])
    graph["edges"] = [
        e for e in graph["edges"]
        if isinstance(e, dict)
        and str(e.get("source", "")) != node_id
        and str(e.get("target", "")) != node_id
    ]
    edge_removed = edge_before - len(graph["edges"])

    ok = _save_graph(path, graph)
    return {
        "ok": ok, "command": "delete-node",
        "graph_file": str(path),
        "nodes_removed": before_count - after_count,
        "edges_removed": edge_removed,
        "node_count": after_count,
        "edge_count": len(graph["edges"]),
    }


# ── 子命令：add-edge ──────────────────────────────────────────────────────────

def cmd_add_edge(args: argparse.Namespace) -> Dict[str, Any]:
    path = get_story_graph_path(Path(args.project_root))
    graph = _load_graph(path)
    node_index = _index_nodes(graph)

    if args.type not in EDGE_TYPES:
        return {"ok": False, "command": "add-edge", "error": f"非法边类型: {args.type}，可选: {', '.join(sorted(EDGE_TYPES))}"}
    if args.source not in node_index:
        return {"ok": False, "command": "add-edge", "error": f"源节点不存在: {args.source}"}
    if args.target not in node_index:
        return {"ok": False, "command": "add-edge", "error": f"目标节点不存在: {args.target}"}

    try:
        attrs = json.loads(args.attrs) if args.attrs else {}
    except json.JSONDecodeError:
        return {"ok": False, "command": "add-edge", "error": "attrs 不是合法的 JSON"}

    edge_id = args.id or _make_edge_id(args.type, args.source, args.target)

    if any(str(e.get("id")) == edge_id for e in graph["edges"] if isinstance(e, dict)):
        return {"ok": False, "command": "add-edge", "error": f"边已存在: {edge_id}"}

    edge: Dict[str, Any] = {
        "id": edge_id,
        "type": args.type,
        "type_label": EDGE_TYPE_LABELS.get(args.type, args.type),
        "source": args.source,
        "target": args.target,
        "since_chapter": args.since_chapter or 0,
        "description": args.description or "",
    }
    edge.update(attrs)
    graph["edges"].append(edge)
    ok = _save_graph(path, graph)
    return {
        "ok": ok, "command": "add-edge",
        "graph_file": str(path), "edge": edge,
        "edge_count": len(graph["edges"]),
    }


# ── 子命令：export ────────────────────────────────────────────────────────────

def cmd_export(args: argparse.Namespace) -> Dict[str, Any]:
    path = get_story_graph_path(Path(args.project_root))
    graph = _load_graph(path)
    node_index = _index_nodes(graph)

    direction = args.direction or "LR"
    lines: List[str] = [f"flowchart {direction}"]

    for n in graph["nodes"]:
        if not isinstance(n, dict) or not n.get("id"):
            continue
        nid = str(n["id"])
        label = str(n.get("name") or nid).replace('"', "'")
        ntype = n.get("type", "")
        lines.append(f'  {nid}["{label} ({NODE_TYPE_LABELS.get(ntype, ntype)})"]')

    for e in graph["edges"]:
        if not isinstance(e, dict):
            continue
        src, tgt = str(e.get("source", "")), str(e.get("target", ""))
        et = EDGE_TYPE_LABELS.get(str(e.get("type", "")), str(e.get("type", "")))
        if src in node_index and tgt in node_index:
            lines.append(f"  {src} -- {et} --> {tgt}")

    mermaid = "\n".join(lines) + "\n"

    output_path: Optional[Path] = None
    if args.output:
        output_path = Path(args.output).resolve()
        ensure_dir(output_path.parent)
        output_path.write_text(mermaid, encoding="utf-8")

    return {
        "ok": True, "command": "export",
        "graph_file": str(path),
        "output_file": str(output_path) if output_path else "",
        "node_count": len(graph["nodes"]),
        "edge_count": len(graph["edges"]),
        "format": "mermaid",
        "content": mermaid if args.inline else "",
    }


# ── 子命令：generate-context ───────────────────────────────────────────────

def cmd_generate_context(args: argparse.Namespace) -> Dict[str, Any]:
    """生成写作上下文摘要，供写前注入写作 query。"""
    path = get_story_graph_path(Path(args.project_root))
    graph = _load_graph(path)
    nodes = graph.get("nodes", [])

    chapter = args.chapter or 0

    # 1. 角色当前状态
    characters = [n for n in nodes if isinstance(n, dict) and n.get("type") == "character"]
    char_lines = []
    for c in characters:
        name = c.get("name", c.get("id", "未知"))
        loc = c.get("location", "未知")
        status = c.get("status", "正常")
        if status.lower() in {"dead", "deceased", "死亡"}:
            continue
        char_lines.append(f"- {name}：当前位于「{loc}」，状态={status}")

    # 2. 未解决伏笔
    foreshadows = [
        n for n in nodes
        if isinstance(n, dict) and n.get("type") == "foreshadow"
        and not n.get("resolved", False)
    ]
    foreshadows_sorted = sorted(
        foreshadows,
        key=lambda n: int(n.get("planted_chapter") or n.get("last_updated") or 0),
    )[:args.max_foreshadows]
    foreshadow_lines = [
        "- [{id}] {desc}（埋于第{planted}章，截止第{deadline}章）".format(
            id=n.get("id", ""),
            desc=n.get("description") or n.get("hint") or n.get("name", ""),
            planted=n.get("planted_chapter") or n.get("last_updated", "?"),
            deadline=n.get("target_chapter") or n.get("deadline", "?"),
        )
        for n in foreshadows_sorted
    ]

    # 3. 近期事件
    events = [
        n for n in nodes
        if isinstance(n, dict) and n.get("type") == "event"
        and (chapter == 0 or int(n.get("chapter", 0) or 0) <= chapter)
    ]
    events_recent = sorted(
        events,
        key=lambda n: int(n.get("chapter", 0) or 0),
        reverse=True,
    )[:args.max_events]
    event_lines = []
    for n in events_recent:
        desc = n.get("description") or n.get("name", "")
        participants = n.get("participants", [])
        p_str = (
            "（参与角色：" + "、".join(str(p) for p in participants if str(p).strip()) + "）"
            if isinstance(participants, list) and participants
            else ""
        )
        event_lines.append(f"- 第{n.get('chapter', '')}章：{desc}{p_str}")

    # 4. 当前场景地点
    locations = [n for n in nodes if isinstance(n, dict) and n.get("type") == "location"]
    loc_lines = ["- {name}：{desc}".format(name=n.get("name", ""), desc=n.get("description", "")[:80])
                 for n in locations if n.get("description")]
    loc_lines = loc_lines[:5]

    # 组合上下文
    sections = []
    if char_lines:
        sections.append("【角色状态】\n" + "\n".join(char_lines))
    if foreshadow_lines:
        sections.append("【待回收伏笔】\n" + "\n".join(foreshadow_lines))
    if event_lines:
        sections.append("【近期事件】\n" + "\n".join(event_lines))
    if loc_lines:
        sections.append("【场景地点】\n" + "\n".join(loc_lines))

    context_prompt = "\n\n".join(sections) if sections else ""

    return {
        "ok": True,
        "command": "generate-context",
        "context_prompt": context_prompt,
        "character_count": len(char_lines),
        "foreshadow_count": len(foreshadow_lines),
        "event_count": len(event_lines),
        "graph_nodes_total": len(nodes),
        "message": "图谱上下文已生成" if context_prompt else "图谱为空，无上下文可注入",
    }


# ── 子命令：validate ─────────────────────────────────────────────────────────

def cmd_validate(args: argparse.Namespace) -> Dict[str, Any]:
    path = get_story_graph_path(Path(args.project_root))
    graph = _load_graph(path)
    node_index = _index_nodes(graph)

    errors: List[str] = []
    warnings: List[str] = []

    # 节点校验
    for n in graph["nodes"]:
        if not isinstance(n, dict):
            errors.append("节点不是对象")
            continue
        nid = str(n.get("id", ""))
        ntype = str(n.get("type", ""))
        if not nid:
            errors.append("节点缺少 id")
        if ntype not in NODE_TYPES:
            errors.append(f"非法节点类型: {nid}:{ntype}")

    # 边校验
    for e in graph["edges"]:
        if not isinstance(e, dict):
            errors.append("边不是对象")
            continue
        eid = str(e.get("id", ""))
        etype = str(e.get("type", ""))
        src = str(e.get("source", ""))
        tgt = str(e.get("target", ""))
        if not eid:
            errors.append("边缺少 id")
        if etype not in EDGE_TYPES:
            errors.append(f"非法边类型: {eid}:{etype}")
        if src not in node_index:
            errors.append(f"边的源节点不存在: {eid}:{src}")
        if tgt not in node_index:
            errors.append(f"边的目标节点不存在: {eid}:{tgt}")

    # 已死亡角色不能参与新事件
    for n in graph["nodes"]:
        if not isinstance(n, dict) or n.get("type") != "event":
            continue
        ev_id = str(n.get("id", ""))
        ev_chapter = int(n.get("chapter", 0) or 0)
        participants = n.get("participants", [])
        if not isinstance(participants, list):
            continue
        for pid in participants:
            pid_str = str(pid).strip() if pid else ""
            if not pid_str:
                continue
            pn = node_index.get(pid_str)
            if not pn:
                # 按名字回退查找
                pn = next(
                    (nd for nd in graph["nodes"]
                     if isinstance(nd, dict) and nd.get("type") == "character"
                     and str(nd.get("name", "")).strip() == pid_str),
                    None,
                )
            if not pn:
                errors.append(f"事件参与者不存在: {ev_id}:{pid}")
                continue
            status = str(pn.get("status", "")).lower()
            death_ch = int(pn.get("death_chapter", 0) or 0)
            if status in {"dead", "deceased", "死亡"} and death_ch > 0 and ev_chapter >= death_ch:
                errors.append(f"已死亡角色参与事件: {pid}:死亡于{death_ch}章:事件在{ev_chapter}章:{ev_id}")

    # 伏笔时间窗校验
    for n in graph["nodes"]:
        if not isinstance(n, dict) or n.get("type") != "foreshadow":
            continue
        nid = str(n.get("id", ""))
        planted = int(n.get("planted_chapter") or 0)
        target = int(n.get("target_chapter", 0) or 0)
        fstatus = str(n.get("status", ""))
        if planted > 0 and target > 0 and target < planted:
            errors.append(f"伏笔回收章节早于埋设章节: {nid}")
        if fstatus == "expired":
            warnings.append(f"伏笔已过期未回收: {nid}")

    return {
        "ok": len(errors) == 0,
        "command": "validate",
        "graph_file": str(path),
        "node_count": len(graph["nodes"]),
        "edge_count": len(graph["edges"]),
        "errors": errors,
        "warnings": warnings,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description="知识图谱构建器（小说设定图结构管理）")
    sub = p.add_subparsers(dest="cmd", required=True)

    # init
    s = sub.add_parser("init", help="初始化空图谱")
    s.add_argument("--project-root", required=True)
    s.add_argument("--force", action="store_true", help="覆盖已有图谱")

    # add-node
    s = sub.add_parser("add-node", help="添加节点")
    s.add_argument("--project-root", required=True)
    s.add_argument("--type", required=True, choices=sorted(NODE_TYPES),
                   help=f"节点类型: {', '.join(sorted(NODE_TYPES))}")
    s.add_argument("--name", required=True, help="节点名称")
    s.add_argument("--id", default="", help="节点 ID（默认自动生成）")
    s.add_argument("--last-updated", type=int, default=0, help="最后更新章节号")
    s.add_argument("--attrs", default="{}", help='额外字段 JSON，如 \'{"role":"主角","location":"长安"}\'')

    # update-node
    s = sub.add_parser("update-node", help="更新节点字段")
    s.add_argument("--project-root", required=True)
    s.add_argument("--node-id", required=True, help="节点 ID")
    s.add_argument("--chapter", type=int, default=0, help="触发更新的章节号")
    s.add_argument("--attrs", required=True, help='更新字段 JSON，如 \'{"status":"受伤"}\'')

    # delete-node
    s = sub.add_parser("delete-node", help="删除节点及关联边")
    s.add_argument("--project-root", required=True)
    s.add_argument("--node-id", required=True, help="要删除的节点 ID")

    # add-edge
    s = sub.add_parser("add-edge", help="添加关系边")
    s.add_argument("--project-root", required=True)
    s.add_argument("--type", required=True, choices=sorted(EDGE_TYPES),
                   help=f"边类型: {', '.join(sorted(EDGE_TYPES))}")
    s.add_argument("--source", required=True, help="源节点 ID")
    s.add_argument("--target", required=True, help="目标节点 ID")
    s.add_argument("--id", default="", help="边 ID（默认自动生成）")
    s.add_argument("--since-chapter", type=int, default=0, help="关系开始的章节")
    s.add_argument("--description", default="", help="关系描述")
    s.add_argument("--attrs", default="{}", help="额外字段 JSON")

    # export
    s = sub.add_parser("export", help="导出 Mermaid 关系图")
    s.add_argument("--project-root", required=True)
    s.add_argument("--direction", default="LR", choices=["LR", "TD", "RL", "BT"])
    s.add_argument("--output", default="", help="输出文件路径（可选）")
    s.add_argument("--inline", action="store_true", help="在 JSON 中内联 Mermaid 文本")

    # generate-context
    s = sub.add_parser("generate-context", help="生成写前上下文摘要")
    s.add_argument("--project-root", required=True)
    s.add_argument("--chapter", type=int, default=0, help="当前章节号")
    s.add_argument("--max-foreshadows", type=int, default=5, help="最多展示未解决伏笔数")
    s.add_argument("--max-events", type=int, default=5, help="最多展示近期事件数")

    # validate
    s = sub.add_parser("validate", help="校验图谱一致性")
    s.add_argument("--project-root", required=True)

    args = p.parse_args()

    dispatch = {
        "init": cmd_init,
        "add-node": cmd_add_node,
        "update-node": cmd_update_node,
        "delete-node": cmd_delete_node,
        "add-edge": cmd_add_edge,
        "export": cmd_export,
        "generate-context": cmd_generate_context,
        "validate": cmd_validate,
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
