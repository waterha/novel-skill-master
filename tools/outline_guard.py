#!/usr/bin/env python3
"""Validate the book -> part -> volume -> chapter outline hierarchy."""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


MANIFEST_PATH = Path(".webnovel/outline_manifest.json")
MARKER_RE = re.compile(r"<!--\s*novel-structure:\s*([^;]+);(.*?)-->", re.DOTALL)
PLACEHOLDER_RE = re.compile(r"(?:待定|待补|占位|TODO|TBD|\.\.\.|……)", re.IGNORECASE)

MIN_CHARS = {
    "book": 500,
    "part": 500,
    "volume-direction": 180,
    "volume-detailed": 600,
    "chapter-index": 300,
    "chapter": 300,
}

REQUIRED_TERMS = {
    "book": ["故事承诺", "起点与终点", "核心冲突", "人物", "部方向", "完结标准"],
    "part": ["本部功能", "承接状态", "核心冲突", "人物", "卷方向", "收束"],
    "volume-direction": ["叙事任务", "起点", "核心冲突", "主要事件", "卷末结果", "下一卷钩子"],
    "volume-detailed": ["章节范围", "剧情单元", "递增", "人物", "伏笔", "高潮", "闭合"],
    "chapter-index": ["章号", "目标", "冲突", "结果", "章末钩子", "剧情单元", "伏笔动作"],
    "chapter": ["叙事任务", "承接点", "场景", "状态变化", "必须出现", "不可出现", "伏笔动作", "章末结果", "目标字数"],
}


def emit(data: dict, exit_code: int = 0) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))
    raise SystemExit(exit_code)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        emit({"ok": False, "error": f"文件不存在: {path}"}, 1)
    except json.JSONDecodeError as exc:
        emit({"ok": False, "error": f"JSON 解析失败: {path}: {exc}"}, 1)
    return {}


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_counts(raw: str) -> List[int]:
    try:
        counts = [int(item.strip()) for item in raw.split(",") if item.strip()]
    except ValueError:
        emit({"ok": False, "error": "--volumes-per-part 必须是逗号分隔的正整数"}, 2)
    if not counts or any(count < 1 for count in counts):
        emit({"ok": False, "error": "每一部至少需要 1 卷"}, 2)
    return counts


def build_parts(counts: List[int]) -> List[dict]:
    parts = []
    next_volume = 1
    for part_no, count in enumerate(counts, start=1):
        end = next_volume + count - 1
        parts.append({
            "part": part_no,
            "volume_start": next_volume,
            "volume_end": end,
            "volume_count": count,
        })
        next_volume = end + 1
    return parts


def parse_marker(text: str) -> Tuple[Optional[str], Dict[str, str]]:
    match = MARKER_RE.search(text[:2000])
    if not match:
        return None, {}
    kind = match.group(1).strip()
    fields = {}
    for item in match.group(2).split(";"):
        if ":" in item:
            key, value = item.split(":", 1)
            fields[key.strip()] = value.strip()
    return kind, fields


def content_size(text: str) -> int:
    without_marker = MARKER_RE.sub("", text, count=1)
    return len(re.sub(r"\s+", "", without_marker))


def inspect_file(
    path: Path,
    expected_kind: str,
    allowed_statuses: List[str],
    min_chars_key: str,
    expected_numbers: Optional[Dict[str, int]] = None,
) -> dict:
    result = {"path": str(path), "exists": path.is_file(), "ok": False, "issues": []}
    if not path.is_file():
        result["issues"].append("文件不存在")
        return result

    text = path.read_text(encoding="utf-8", errors="replace")
    kind, fields = parse_marker(text)
    result["kind"] = kind
    result["status"] = fields.get("status")
    result["content_chars"] = content_size(text)

    if kind != expected_kind:
        result["issues"].append(f"结构类型应为 {expected_kind}")
    if fields.get("status") not in allowed_statuses:
        result["issues"].append(f"状态应为 {'/'.join(allowed_statuses)}")
    if result["content_chars"] < MIN_CHARS[min_chars_key]:
        result["issues"].append(f"实质内容少于 {MIN_CHARS[min_chars_key]} 字符")
    missing_terms = [term for term in REQUIRED_TERMS[min_chars_key] if term not in text]
    if missing_terms:
        result["issues"].append(f"缺少必填结构: {', '.join(missing_terms)}")
    if PLACEHOLDER_RE.search(text):
        result["issues"].append("含有待定、占位或省略内容")

    for key, expected in (expected_numbers or {}).items():
        if fields.get(key) != str(expected):
            result["issues"].append(f"标记中的 {key} 应为 {expected}")

    result["ok"] = not result["issues"]
    return result


def manifest_for(root: Path) -> dict:
    return load_json(root / MANIFEST_PATH)


def book_path(root: Path) -> Path:
    return root / "大纲" / "00-总纲" / "全书总纲.md"


def part_path(root: Path, part: int) -> Path:
    return root / "大纲" / "01-部纲" / f"第{part:02d}部-部纲.md"


def volume_path(root: Path, part: int, volume: int) -> Path:
    return root / "大纲" / "02-卷纲" / f"第{part:02d}部" / f"第{volume:03d}卷-卷纲.md"


def chapter_dir(root: Path, part: int, volume: int) -> Path:
    return root / "大纲" / "03-章纲" / f"第{part:02d}部" / f"第{volume:03d}卷"


def expected_part(manifest: dict, volume: int) -> Optional[int]:
    for item in manifest.get("parts", []):
        if item["volume_start"] <= volume <= item["volume_end"]:
            return item["part"]
    return None


def broad_structure_report(root: Path, manifest: dict) -> dict:
    book = inspect_file(book_path(root), "book", ["confirmed"], "book")
    parts = []
    volumes = []
    for item in manifest.get("parts", []):
        part_no = item["part"]
        parts.append(inspect_file(
            part_path(root, part_no), "part", ["confirmed"], "part", {"part": part_no}
        ))
        for volume_no in range(item["volume_start"], item["volume_end"] + 1):
            volume_file = volume_path(root, part_no, volume_no)
            volume_text = volume_file.read_text(encoding="utf-8", errors="replace") if volume_file.is_file() else ""
            _, volume_fields = parse_marker(volume_text)
            is_detailed = volume_fields.get("status") == "detailed-confirmed"
            volume_report = inspect_file(
                volume_path(root, part_no, volume_no),
                "volume",
                ["direction-confirmed", "detailed-confirmed"],
                "volume-direction",
                {"part": part_no, "volume": volume_no},
            )
            if is_detailed:
                missing_detail = [term for term in REQUIRED_TERMS["volume-detailed"] if term not in volume_text]
                if missing_detail:
                    volume_report["issues"].append(f"详纲缺少必填结构: {', '.join(missing_detail)}")
                    volume_report["ok"] = False
            volumes.append(volume_report)
    ok = book["ok"] and all(item["ok"] for item in parts + volumes)
    return {"ok": ok, "book": book, "parts": parts, "volume_directions": volumes}


def cmd_init(args: argparse.Namespace) -> None:
    root = args.project_root.resolve()
    counts = parse_counts(args.volumes_per_part)
    if len(counts) != args.parts:
        emit({
            "ok": False,
            "error": f"部数为 {args.parts}，但卷数配置给出了 {len(counts)} 组",
        }, 2)

    path = root / MANIFEST_PATH
    if path.exists() and not args.force:
        emit({"ok": False, "error": f"结构清单已存在: {path}", "suggest": "确认后使用 --force 重建"}, 1)

    now = datetime.now().isoformat(timespec="seconds")
    manifest = {
        "version": 1,
        "parts_count": args.parts,
        "volumes_count": sum(counts),
        "parts": build_parts(counts),
        "created_at": now,
        "updated_at": now,
    }
    save_json(path, manifest)
    emit({"ok": True, "manifest": str(path), "structure": manifest})


def cmd_status(args: argparse.Namespace) -> None:
    root = args.project_root.resolve()
    manifest = manifest_for(root)
    report = broad_structure_report(root, manifest)
    missing = []
    invalid = []
    for item in [report["book"]] + report["parts"] + report["volume_directions"]:
        if not item["exists"]:
            missing.append(item["path"])
        elif not item["ok"]:
            invalid.append({"path": item["path"], "issues": item["issues"]})
    emit({
        "ok": report["ok"],
        "parts": manifest.get("parts_count"),
        "volumes": manifest.get("volumes_count"),
        "missing": missing,
        "invalid": invalid,
        "report": report,
    }, 0 if report["ok"] else 1)


def cmd_preflight(args: argparse.Namespace) -> None:
    root = args.project_root.resolve()
    manifest = manifest_for(root)
    mapped_part = expected_part(manifest, args.volume)
    if mapped_part is None:
        emit({"ok": False, "error": f"卷 {args.volume} 不在结构清单中"}, 2)
    if mapped_part != args.part:
        emit({"ok": False, "error": f"第 {args.volume} 卷属于第 {mapped_part} 部，不是第 {args.part} 部"}, 2)

    broad = broad_structure_report(root, manifest)
    target_volume = inspect_file(
        volume_path(root, args.part, args.volume),
        "volume",
        ["detailed-confirmed"],
        "volume-detailed",
        {"part": args.part, "volume": args.volume},
    )
    cdir = chapter_dir(root, args.part, args.volume)
    chapter_index = inspect_file(
        cdir / "卷章节索引.md",
        "chapter-index",
        ["confirmed"],
        "chapter-index",
        {"part": args.part, "volume": args.volume},
    )
    chapter = inspect_file(
        cdir / f"第{args.chapter:04d}章-章纲.md",
        "chapter",
        ["confirmed"],
        "chapter",
        {"part": args.part, "volume": args.volume, "chapter": args.chapter},
    )

    checks = {
        "all_parts_and_volume_directions": broad["ok"],
        "target_volume_detailed": target_volume["ok"],
        "chapter_index_confirmed": chapter_index["ok"],
        "chapter_outline_confirmed": chapter["ok"],
    }
    ok = all(checks.values())
    emit({
        "ok": ok,
        "checks": checks,
        "target_volume": target_volume,
        "chapter_index": chapter_index,
        "chapter": chapter,
        "broad_structure": broad,
        "suggest": "可以开始写章" if ok else "先补齐或确认报告中的结构文件",
    }, 0 if ok else 1)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="小说部/卷/章结构完整性校验")
    sub = p.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="建立部卷映射清单，不创建空大纲")
    init.add_argument("--project-root", type=Path, required=True)
    init.add_argument("--parts", type=int, required=True)
    init.add_argument("--volumes-per-part", required=True)
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    status = sub.add_parser("status", help="检查全书总纲、全部部纲和全部卷方向")
    status.add_argument("--project-root", type=Path, required=True)
    status.set_defaults(func=cmd_status)

    preflight = sub.add_parser("preflight", help="检查指定章节的完整写前记忆栈")
    preflight.add_argument("--project-root", type=Path, required=True)
    preflight.add_argument("--part", type=int, required=True)
    preflight.add_argument("--volume", type=int, required=True)
    preflight.add_argument("--chapter", type=int, required=True)
    preflight.set_defaults(func=cmd_preflight)
    return p


def main() -> None:
    args = parser().parse_args()
    if getattr(args, "parts", 1) < 1:
        emit({"ok": False, "error": "--parts 必须大于 0"}, 2)
    args.func(args)


if __name__ == "__main__":
    main()
