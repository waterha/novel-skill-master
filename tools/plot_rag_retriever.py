#!/usr/bin/env python3
"""
plot_rag_retriever.py — 轻量剧情检索器（RAG 风格，零外部依赖）

写新章节前，自动分析 query 判断是否需要检索历史章节，
返回最相关的 Top-K 章节片段供写前回读。

两级检索：粗筛（关键词匹配）→ 精排（语义相关度评分）

子命令：
  build   — 从已写章节构建检索索引
  query   — 检索与 query 最相关的章节片段
  status  — 查看索引状态

调用示例：
  python tools/plot_rag_retriever.py build --project-root <路径>
  python tools/plot_rag_retriever.py query --project-root <路径> --query "主角突破金丹期"
  python tools/plot_rag_retriever.py status --project-root <路径>

返回值：JSON 到 stdout。
"""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from novel_common import (
    ensure_dir, load_json, read_text, save_json, slugify,
    chapter_no_from_name, normalize_text, count_chars,
    get_retrieval_dir,
)


# ── 配置 ─────────────────────────────────────────────────────────────────────

STOPWORDS: Set[str] = {
    "我们", "你们", "他们", "她们", "它们", "这个", "那个", "一种",
    "已经", "因为", "所以", "如果", "但是", "然后", "自己", "不是",
    "不会", "就是", "还是", "一个", "一些", "可以", "时候", "什么",
    "怎么", "这样", "那样", "起来", "一下", "一样", "以及", "并且",
    "或者", "这里", "那里", "这些", "那些", "如此", "真的", "没有",
    "可能", "大概", "也许", "不过", "只是", "还是", "就是", "但是",
    "而且", "于是", "然后", "虽然", "因为", "所以",
}

# 触发检索的关键词（命中任一就触发检索）
TRIGGER_KEYWORDS: Set[str] = {
    "冲突", "反转", "伏笔", "回收", "真相", "背叛", "联盟",
    "新角色", "时间线", "回忆", "穿越", "死亡", "复活",
    "势力", "升级", "突破", "决战", "危机", "转折", "悬念",
    "揭露", "身份", "秘密", "阴谋", "复仇", "救赎", "牺牲",
    "传承", "觉醒", "封印", "决战", "追查", "身世",
}

# 轻场景关键词（命中这些且没有触发关键词就跳过检索）
LIGHT_SCENE_KEYWORDS: Set[str] = {
    "日常", "过渡", "环境描写", "吃饭", "赶路", "休整",
    "闲聊", "铺垫", "修炼", "冥想", "休息", "准备",
    "整理", "收拾", "散步", "观光", "平淡",
}


def tokenize(text: str) -> List[str]:
    """中文 2~4 字 n-gram + 英文词分词。"""
    tokens: List[str] = []
    # 中文 2~4 字 n-gram
    chars = [c for c in text if "一" <= c <= "鿿"]
    for n in range(2, 5):
        for i in range(len(chars) - n + 1):
            gram = "".join(chars[i:i + n])
            if gram not in STOPWORDS:
                tokens.append(gram)
    # 英文词
    for word in re.findall(r"[A-Za-z]{3,}", text):
        tokens.append(word.lower())
    return tokens


def extract_keywords(text: str, top_n: int = 20) -> List[str]:
    """提取文本的关键词。"""
    tokens = tokenize(text)
    if not tokens:
        return []
    counter = Counter(tokens)
    return [k for k, _ in counter.most_common(top_n)]


def load_character_names(project_root: Path) -> List[str]:
    """从设定契约和知识图谱加载角色名列表。"""
    names: Set[str] = set()

    # 从 MASTER_SETTING.json 加载
    ms_path = project_root / ".story-system" / "MASTER_SETTING.json"
    ms = load_json(ms_path, {})
    chars = ms.get("characters", {})
    if isinstance(chars, dict):
        for name in chars.keys():
            if len(name) >= 2:
                names.add(name)

    # 从知识图谱加载
    graph_path = project_root / ".story-system" / "story_graph.json"
    graph = load_json(graph_path, {})
    for n in graph.get("nodes", []):
        if isinstance(n, dict) and n.get("type") == "character":
            cname = n.get("name", "")
            if len(cname) >= 2:
                names.add(cname)

    return sorted(names)


def load_location_names(project_root: Path) -> List[str]:
    """从知识图谱加载地点名列表。"""
    locs: Set[str] = set()
    graph_path = project_root / ".story-system" / "story_graph.json"
    graph = load_json(graph_path, {})
    for n in graph.get("nodes", []):
        if isinstance(n, dict) and n.get("type") == "location":
            lname = n.get("name", "")
            if len(lname) >= 2:
                locs.add(lname)
    return sorted(locs)


def analyze_query_trigger(query: str, names: List[str], locs: List[str]) -> Dict[str, Any]:
    """分析 query 是否需要触发检索。"""
    q = normalize_text(query)
    entities = [n for n in names if n in q]
    locations = [l for l in locs if l in q]
    keyword_hits = sorted([k for k in TRIGGER_KEYWORDS if k in q])
    light_hits = sorted([k for k in LIGHT_SCENE_KEYWORDS if k in q])
    long_query = len(q) >= 15

    should = bool(entities or keyword_hits or locations or (long_query and not light_hits))
    reason = []
    if entities:
        reason.append(f"命中角色: {', '.join(entities[:4])}")
    if locations:
        reason.append(f"命中地点: {', '.join(locations[:3])}")
    if keyword_hits:
        reason.append(f"命中剧情关键词: {', '.join(keyword_hits[:4])}")
    if long_query and not light_hits:
        reason.append("查询描述较长，判定为复杂剧情")
    if light_hits and not entities and not keyword_hits:
        reason.append(f"仅命中轻场景关键词: {', '.join(light_hits)}，跳过检索")
    if not reason:
        reason.append("未命中角色/剧情关键词，判定为可跳过检索")

    return {
        "should_trigger": should,
        "entities": entities,
        "locations": locations,
        "keyword_hits": keyword_hits,
        "light_hits": light_hits,
        "query_length": len(q),
        "reason": reason,
    }


# ── 索引构建 ──────────────────────────────────────────────────────────────────

def build_index(project_root: Path, incremental: bool = True) -> Dict[str, Any]:
    """从已写章节构建检索索引。"""
    # 查找正文目录
    manuscript_dirs = [
        project_root / "正文",
        project_root / "03_manuscript",
        project_root,
    ]
    manuscript_dir = None
    for d in manuscript_dirs:
        if d.exists() and any(f.is_file() for f in d.rglob("第*章*.md")):
            manuscript_dir = d
            break

    if not manuscript_dir:
        return {"ok": False, "error": "未找到章节正文目录（检查 正文/ 或 03_manuscript/ 目录）"}

    retrieval_dir = get_retrieval_dir(project_root)
    ensure_dir(retrieval_dir)
    index_file = retrieval_dir / "story_index.json"

    chapters = sorted(
        [f for f in manuscript_dir.rglob("*.md") if re.search(r"第\d+章", f.name)],
        key=lambda p: (chapter_no_from_name(p.name), p.name),
    )
    names = load_character_names(project_root)
    locs = load_location_names(project_root)
    all_known = set(names) | set(locs)

    # 增量构建
    existing: Dict[str, Dict[str, Any]] = {}
    if incremental and index_file.exists():
        try:
            old = load_json(index_file, {})
            for d in old.get("docs", []):
                if isinstance(d, dict) and d.get("chapter_file"):
                    existing[d["chapter_file"]] = d
        except Exception:
            existing = {}

    docs = []
    reused = 0
    rebuilt = 0

    for path in chapters:
        mtime = path.stat().st_mtime
        cached = existing.get(path.name)

        # 如果文件没变且角色名没变，复用旧索引
        if cached and float(cached.get("mtime", -1)) == mtime:
            docs.append(cached)
            reused += 1
            continue

        text = read_text(path)
        flat = re.sub(r"\s+", " ", text).strip()
        summary = flat[:260]
        keywords = extract_keywords(text)
        entities = sorted([n for n in all_known if n in text])
        wc = count_chars(text)

        doc = {
            "chapter_file": path.name,
            "chapter_path": str(path),
            "chapter_no": chapter_no_from_name(path.name),
            "mtime": mtime,
            "summary": summary,
            "keywords": keywords,
            "entities": entities,
            "word_count": wc,
        }
        docs.append(doc)
        rebuilt += 1

    docs.sort(key=lambda d: (int(d.get("chapter_no", 0)), str(d.get("chapter_file", ""))))

    # 实体-章节映射
    entity_map: Dict[str, List[str]] = {}
    for d in docs:
        for e in d.get("entities", []):
            entity_map.setdefault(e, []).append(str(d.get("chapter_file", "")))

    index = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "project_root": str(project_root),
        "chapter_count": len(docs),
        "reused_docs": reused,
        "rebuilt_docs": rebuilt,
        "character_count": len(names),
        "location_count": len(locs),
        "docs": docs,
    }

    save_json(index_file, index)
    em_path = retrieval_dir / "entity_chapter_map.json"
    save_json(em_path, entity_map)

    return {
        "ok": True,
        "command": "build",
        "index_file": str(index_file),
        "chapter_count": len(docs),
        "reused_docs": reused,
        "rebuilt_docs": rebuilt,
    }


# ── 检索 ──────────────────────────────────────────────────────────────────────

def _score_doc(
    doc: Dict[str, Any],
    query_tokens: List[str],
    query_token_set: Set[str],
    query_entities: List[str],
    query_text: str,
    max_no: int,
) -> Tuple[float, Dict[str, int]]:
    """对单篇文档打分。"""
    kw = set(doc.get("keywords", []))
    ent = set(doc.get("entities", []))
    summary = str(doc.get("summary", ""))

    token_overlap = len(query_token_set & kw)
    entity_overlap = len(set(query_entities) & ent)
    summary_overlap = len(query_token_set & set(extract_keywords(summary, 10)))

    chapter_no = int(doc.get("chapter_no", 0))
    recency = (chapter_no / max_no) if max_no > 0 else 0.0
    # 越新权重略高
    recency_bonus = recency * 0.3

    score = (
        entity_overlap * 4.0        # 角色重叠权重最高
        + token_overlap * 1.5       # 关键词重叠
        + summary_overlap * 0.8     # 摘要重叠
        + recency_bonus             # 近因性
    )
    detail = {
        "entity_overlap": entity_overlap,
        "token_overlap": token_overlap,
        "summary_overlap": summary_overlap,
    }
    return score, detail


def retrieve(
    index: Dict[str, Any],
    project_root: Path,
    query: str,
    top_k: int = 4,
) -> Dict[str, Any]:
    """两级检索：先粗筛再精排。"""
    docs: List[Dict[str, Any]] = index.get("docs", [])
    query_tokens = extract_keywords(query, 30)
    query_token_set = set(query_tokens)
    names = load_character_names(project_root)
    query_entities = [n for n in names if n in query]

    max_no = max((int(d.get("chapter_no", 0)) for d in docs), default=0)

    # 粗筛：对每篇算分
    candidate_k = 12  # 取 Top 12 进入精排
    all_scored: List[Tuple[float, Dict[str, int], Dict[str, Any]]] = []
    for d in docs:
        s, detail = _score_doc(d, query_tokens, query_token_set, query_entities, query, max_no)
        all_scored.append((s, detail, d))

    all_scored.sort(key=lambda x: x[0], reverse=True)

    # 取候选池
    candidate_pool = [x for x in all_scored if x[0] > 0][:candidate_k]
    if not candidate_pool:
        candidate_pool = all_scored[:candidate_k]

    # 精排：对候选池做更精确的片段级评分
    fine_scored: List[Tuple[float, Dict[str, int], Dict[str, Any]]] = []
    for s, detail, d in candidate_pool:
        # 精排时检查实体的密集度
        text = read_text(Path(str(d.get("chapter_path", ""))))
        entity_in_text = sum(1 for e in query_entities if e in text)
        fine_score = s + entity_in_text * 0.5
        detail["entity_in_text"] = entity_in_text
        fine_scored.append((fine_score, detail, d))

    fine_scored.sort(key=lambda x: x[0], reverse=True)

    # 取 Top-K
    picked = [x for x in fine_scored if x[0] > 0][:top_k]
    if not picked:
        picked = fine_scored[:top_k]

    retrieved = []
    for s, detail, d in picked:
        retrieved.append({
            "score": round(s, 2),
            "detail": detail,
            "chapter_no": d.get("chapter_no"),
            "chapter_file": d.get("chapter_file"),
            "summary": d.get("summary", ""),
            "entities": d.get("entities", []),
            "word_count": d.get("word_count", 0),
        })

    return {
        "query": query,
        "query_entities": query_entities,
        "retrieved": retrieved,
        "stats": {
            "total_docs": len(docs),
            "candidate_pool": min(len(candidate_pool), candidate_k),
            "top_k": len(retrieved),
        },
    }


# ── 生成上下文文件 ────────────────────────────────────────────────────────────

def write_context_md(project_root: Path, result: Dict[str, Any]) -> Path:
    """将检索结果写入 next_plot_context.md。"""
    retrieval_dir = get_retrieval_dir(project_root)
    ensure_dir(retrieval_dir)
    out = retrieval_dir / "next_plot_context.md"

    lines = ["# 📖 新剧情写前上下文建议（RAG 检索）", ""]
    lines.append(f"- 查询：{result.get('query', '')}")
    entities = result.get("query_entities", [])
    lines.append(f"- 命中角色：{', '.join(entities) if entities else '无'}")
    if result.get("skipped"):
        lines.append("- **跳过检索**：判定为轻场景或信息不足")
        out.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return out

    stats = result.get("retrieve_result", {}).get("stats", {})
    if stats:
        lines.append(f"- 检索统计：候选 {stats.get('candidate_pool', 0)} / 总计 {stats.get('total_docs', 0)} 章")
    lines.append("")

    lines.append("## 📌 必须读取的文件")
    lines.append("- `.webnovel/master_state.json` — 项目当前状态")
    lines.append("- `.story-system/MASTER_SETTING.json` — 设定契约")
    lines.append("")

    retrieved = result.get("retrieve_result", {}).get("retrieved", [])
    if retrieved:
        lines.append("## 📄 建议回读章节（按相关度排序）")
        lines.append("")
        for i, r in enumerate(retrieved, 1):
            lines.append(f"### {i}. 第{r['chapter_no']}章 · `{r['chapter_file']}`  (评分: {r['score']})")
            lines.append(f"**摘要**: {r['summary'][:120]}...")
            if r.get("entities"):
                lines.append(f"**涉及角色**: {', '.join(r['entities'][:6])}")
            lines.append(f"**字数**: {r['word_count']}")
            lines.append("")
    else:
        lines.append("无可用章节匹配当前 query。")
        lines.append("")

    lines.append("## 💡 写作前建议")
    lines.append("1. 先读取上述建议章节，确认角色状态和伏笔进度")
    lines.append("2. 检查设定契约中的能力阶段约束")
    lines.append("3. 写作后执行门禁流程：更新记忆 → 一致性审查 → 风格校准 → 校稿 → 门禁检查")

    out.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return out


# ── Index 签名（用于缓存键） ───────────────────────────────────────────────

def index_signature(index_file: Path) -> str:
    """计算索引签名，用于缓存键。"""
    idx = load_json(index_file, {})
    docs = idx.get("docs", [])
    raw = "|".join(
        f"{d.get('chapter_file','')}:{d.get('mtime',0)}"
        for d in docs
    )
    return f"{len(docs)}-{hashlib.sha1(raw.encode()).hexdigest()[:12]}"


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description="剧情检索器 (RAG)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("build", help="构建检索索引")
    s.add_argument("--project-root", required=True)
    s.add_argument("--full-rebuild", action="store_true", help="全量重建索引")

    s = sub.add_parser("query", help="检索相关章节")
    s.add_argument("--project-root", required=True)
    s.add_argument("--query", required=True, help="本章要写的剧情描述")
    s.add_argument("--top-k", type=int, default=4, help="返回多少章")
    s.add_argument("--auto-build", action="store_true", help="检索前自动构建索引")
    s.add_argument("--force", action="store_true", help="强制检索（不跳过轻场景）")

    s = sub.add_parser("status", help="查看索引状态")
    s.add_argument("--project-root", required=True)

    args = p.parse_args()
    project_root = Path(args.project_root)

    try:
        if args.cmd == "build":
            payload = build_index(project_root, incremental=not args.full_rebuild)

        elif args.cmd == "query":
            retrieval_dir = get_retrieval_dir(project_root)
            index_file = retrieval_dir / "story_index.json"

            if args.auto_build or not index_file.exists():
                build_result = build_index(project_root)
                if not build_result.get("ok"):
                    payload = build_result
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                    return 1

            if not index_file.exists():
                payload = {"ok": False, "error": "索引不存在，请先运行 build 子命令"}
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                return 1

            index = load_json(index_file, {})
            names = load_character_names(project_root)
            locs = load_location_names(project_root)

            trigger = analyze_query_trigger(args.query, names, locs)
            if not args.force and not trigger["should_trigger"]:
                result = {
                    "query": args.query,
                    "query_entities": trigger.get("entities", []),
                    "skipped": True,
                    "trigger_reason": trigger.get("reason", []),
                    "retrieve_result": {"retrieved": [], "stats": {"total_docs": len(index.get("docs", []))}},
                }
                md_out = write_context_md(project_root, result)
                payload = {
                    "ok": True,
                    "command": "query",
                    "skipped": True,
                    "context_file": str(md_out),
                    "result": result,
                }
            else:
                retrieve_result = retrieve(index, project_root, args.query, top_k=args.top_k)
                result = {
                    "query": args.query,
                    "query_entities": retrieve_result["query_entities"],
                    "skipped": False,
                    "trigger_reason": trigger.get("reason", []),
                    "retrieve_result": retrieve_result,
                }
                md_out = write_context_md(project_root, result)
                payload = {
                    "ok": True,
                    "command": "query",
                    "skipped": False,
                    "context_file": str(md_out),
                    "result": result,
                }

        elif args.cmd == "status":
            retrieval_dir = get_retrieval_dir(project_root)
            index_file = retrieval_dir / "story_index.json"
            if not index_file.exists():
                payload = {"ok": False, "error": "索引尚未构建，请先运行 build"}
            else:
                idx = load_json(index_file, {})
                payload = {
                    "ok": True,
                    "command": "status",
                    "index_file": str(index_file),
                    "chapter_count": idx.get("chapter_count", 0),
                    "generated_at": idx.get("generated_at", ""),
                    "entity_chapter_map": str(retrieval_dir / "entity_chapter_map.json"),
                }

        else:
            payload = {"ok": False, "error": f"未知命令: {args.cmd}"}

    except Exception as exc:
        payload = {"ok": False, "command": args.cmd, "error": repr(exc)}

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
