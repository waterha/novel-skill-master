#!/usr/bin/env python3
"""Build an inventory that a fresh session must read before continuing a novel."""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


CHAPTER_RE = re.compile(r"第(\d+)章")
PART_RE = re.compile(r"第(\d+)部")
VOLUME_RE = re.compile(r"第(\d+)卷")


def chapter_no(path: Path) -> int:
    match = CHAPTER_RE.search(path.name)
    return int(match.group(1)) if match else 0


def enclosing_number(path: Path, pattern: re.Pattern) -> Optional[int]:
    for part in reversed(path.parts):
        match = pattern.search(part)
        if match:
            return int(match.group(1))
    return None


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def summary_text(data: Any) -> str:
    if isinstance(data, dict):
        for key in ("summary", "chapter_summary", "facts", "content"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:2000]
            if isinstance(value, list) and value:
                return "；".join(str(item) for item in value)[:2000]
        return ""
    return str(data)[:2000] if data is not None else ""


def find_summaries(root: Path) -> Dict[int, Path]:
    summary_dir = root / ".story-system" / "chapter_summaries"
    summaries: Dict[int, Path] = {}
    if summary_dir.exists():
        for path in sorted(summary_dir.rglob("*.json")):
            number = chapter_no(path)
            if number and number not in summaries:
                summaries[number] = path
    return summaries


def relative_paths(root: Path, paths: List[Path]) -> List[str]:
    return [str(path.relative_to(root)) for path in sorted(paths)]


def scan(root: Path) -> dict:
    manifest = load_json(root / ".webnovel" / "outline_manifest.json", {})
    state = load_json(root / ".webnovel" / "master_state.json", {})

    book = root / "大纲" / "00-总纲" / "全书总纲.md"
    part_files = list((root / "大纲" / "01-部纲").glob("第*部-部纲.md")) if (root / "大纲" / "01-部纲").exists() else []
    volume_files = list((root / "大纲" / "02-卷纲").rglob("第*卷-卷纲.md")) if (root / "大纲" / "02-卷纲").exists() else []
    chapter_indexes = list((root / "大纲" / "03-章纲").rglob("卷章节索引.md")) if (root / "大纲" / "03-章纲").exists() else []
    chapter_outlines = list((root / "大纲" / "03-章纲").rglob("第*章-章纲.md")) if (root / "大纲" / "03-章纲").exists() else []

    content_dir = root / "正文"
    chapter_files = sorted(
        [path for path in content_dir.rglob("第*章*.md") if chapter_no(path)] if content_dir.exists() else [],
        key=lambda path: (chapter_no(path), str(path)),
    )
    summaries = find_summaries(root)
    chapter_records = []
    number_to_paths: Dict[int, List[str]] = {}
    for path in chapter_files:
        number = chapter_no(path)
        number_to_paths.setdefault(number, []).append(str(path.relative_to(root)))
        summary_path = summaries.get(number)
        record = {
            "chapter": number,
            "part": enclosing_number(path, PART_RE),
            "volume": enclosing_number(path, VOLUME_RE),
            "chapter_file": str(path.relative_to(root)),
            "summary_file": str(summary_path.relative_to(root)) if summary_path else None,
            "summary_status": "missing",
        }
        if summary_path:
            loaded_summary = load_json(summary_path, None)
            rendered_summary = summary_text(loaded_summary).strip() if loaded_summary is not None else ""
            if rendered_summary and rendered_summary not in {"{}", "[]", "null", "None"}:
                record["summary_status"] = "available"
                record["summary"] = rendered_summary
            else:
                record["summary_status"] = "invalid"
        chapter_records.append(record)

    numbers = sorted(number_to_paths)
    gaps = [number for number in range(numbers[0], numbers[-1] + 1) if number not in number_to_paths] if numbers else []
    duplicates = {str(number): paths for number, paths in number_to_paths.items() if len(paths) > 1}
    missing_summaries = sorted(record["chapter"] for record in chapter_records if record["summary_status"] != "available")
    latest_chapter = numbers[-1] if numbers else None
    next_chapter = latest_chapter + 1 if latest_chapter is not None else None
    next_outline = next((path for path in chapter_outlines if chapter_no(path) == next_chapter), None) if next_chapter else None

    expected_parts = int(manifest.get("parts_count", 0) or 0)
    expected_volumes = int(manifest.get("volumes_count", 0) or 0)
    manifest_exists = (root / ".webnovel" / "outline_manifest.json").is_file()
    written_volumes = sorted({record["volume"] for record in chapter_records if record["volume"] is not None})
    indexed_volumes = sorted({
        number for number in (enclosing_number(path, VOLUME_RE) for path in chapter_indexes)
        if number is not None
    })
    missing_written_volume_indexes = [volume for volume in written_volumes if volume not in indexed_volumes]
    structure_complete = (
        manifest_exists
        and expected_parts > 0
        and expected_volumes > 0
        and book.is_file()
        and len(part_files) == expected_parts
        and len(volume_files) == expected_volumes
        and not missing_written_volume_indexes
    )

    ledger = load_json(root / ".story-system" / "foreshadowing.json", {"items": []})
    open_foreshadows = [item for item in ledger.get("items", []) if item.get("status") not in {"recovered", "cancelled"}]
    memory_files = {
        "master_state": root / ".webnovel" / "master_state.json",
        "outline_manifest": root / ".webnovel" / "outline_manifest.json",
        "master_setting": root / ".story-system" / "MASTER_SETTING.json",
        "character_states": root / ".story-system" / "character_states.json",
        "timeline": root / ".story-system" / "timeline.json",
        "foreshadowing": root / ".story-system" / "foreshadowing.json",
        "project_memory": root / ".webnovel" / "project_memory.json",
    }
    memory_status = {key: {"path": str(path.relative_to(root)), "exists": path.is_file()} for key, path in memory_files.items()}

    blockers = []
    if not structure_complete:
        blockers.append("全书结构文件与 outline_manifest 不一致")
    if not chapter_files:
        blockers.append("未找到可续写的正文")
    if missing_summaries:
        blockers.append(f"有 {len(missing_summaries)} 章缺少事实摘要，需回读正文补齐")
    if gaps:
        blockers.append(f"正文章号存在缺口: {gaps}")
    if duplicates:
        blockers.append("存在重复章号")
    state_chapter = state.get("current_chapter")
    if latest_chapter is not None and state_chapter != latest_chapter:
        blockers.append(f"状态文件 current_chapter={state_chapter}，实际最大正文章号={latest_chapter}")
    if next_chapter is not None and next_outline is None:
        blockers.append(f"下一章第 {next_chapter} 章的独立章纲不存在")
    for key in ("master_state", "outline_manifest", "master_setting", "character_states", "timeline", "foreshadowing"):
        if not memory_status[key]["exists"]:
            blockers.append(f"缺少动态记忆文件: {memory_status[key]['path']}")

    return {
        "version": 1,
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "project_root": str(root),
        "resume_ready": not blockers,
        "blockers": blockers,
        "state_position": {
            "part": state.get("current_part"),
            "volume": state.get("current_volume"),
            "chapter": state.get("current_chapter"),
        },
        "structure": {
            "complete": structure_complete,
            "expected_parts": expected_parts,
            "actual_parts": len(part_files),
            "expected_volumes": expected_volumes,
            "actual_volumes": len(volume_files),
            "book": str(book.relative_to(root)) if book.is_file() else None,
            "part_files": relative_paths(root, part_files),
            "volume_files": relative_paths(root, volume_files),
            "chapter_indexes": relative_paths(root, chapter_indexes),
            "chapter_outlines": relative_paths(root, chapter_outlines),
            "written_volumes": written_volumes,
            "missing_written_volume_indexes": missing_written_volume_indexes,
            "next_chapter": next_chapter,
            "next_chapter_outline": str(next_outline.relative_to(root)) if next_outline else None,
        },
        "manuscript": {
            "chapter_count": len(chapter_files),
            "latest_chapter": latest_chapter,
            "latest_chapter_file": number_to_paths[latest_chapter][0] if latest_chapter else None,
            "gaps": gaps,
            "duplicates": duplicates,
            "summary_coverage": round((len(chapter_files) - len(missing_summaries)) / max(len(chapter_files), 1) * 100, 1),
            "missing_summaries": missing_summaries,
            "chapters": chapter_records,
        },
        "memory": memory_status,
        "foreshadowing": {"open_count": len(open_foreshadows), "open_items": open_foreshadows},
        "closure_files": {
            "volumes": relative_paths(root, list((root / "收尾" / "卷").glob("*.md"))) if (root / "收尾" / "卷").exists() else [],
            "parts": relative_paths(root, list((root / "收尾" / "部").glob("*.md"))) if (root / "收尾" / "部").exists() else [],
            "book": str((root / "收尾" / "全书收尾.md").relative_to(root)) if (root / "收尾" / "全书收尾.md").is_file() else None,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="新会话续写前的全书扫描")
    sub = parser.add_subparsers(dest="command", required=True)
    scan_parser = sub.add_parser("scan", help="扫描全书结构、正文和摘要覆盖率")
    scan_parser.add_argument("--project-root", type=Path, required=True)
    scan_parser.add_argument("--write-inventory", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()
    inventory = scan(root)
    inventory_path = root / ".webnovel" / "continuation_inventory.json"
    if args.write_inventory:
        inventory_path.parent.mkdir(parents=True, exist_ok=True)
        inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output = {
        "ok": inventory["resume_ready"],
        "resume_ready": inventory["resume_ready"],
        "blockers": inventory["blockers"],
        "inventory": str(inventory_path) if args.write_inventory else None,
        "structure": inventory["structure"],
        "manuscript_summary": {key: value for key, value in inventory["manuscript"].items() if key != "chapters"},
        "open_foreshadows": inventory["foreshadowing"]["open_count"],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    raise SystemExit(0 if inventory["resume_ready"] else 1)


if __name__ == "__main__":
    main()
