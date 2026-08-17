#!/usr/bin/env python3
"""Validate and query the novel's foreshadowing ledger."""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


LEDGER_RELATIVE = Path(".story-system/foreshadowing.json")
STATUSES = {"planned", "planted", "reinforced", "due", "deferred", "recovered", "cancelled"}
CLOSED_STATUSES = {"recovered", "cancelled"}
PLANT_SIGNALS = ["不对劲", "奇怪", "异样", "暗暗记下", "留了个心眼", "没有回答", "避而不谈", "欲言又止"]
PAYOFF_SIGNALS = ["原来", "果然", "应验", "这才明白", "终于知道", "真相", "谜底", "早在"]
SENTENCE_RE = re.compile(r"[^。！？\n]{0,50}(?:%s)[^。！？\n]{0,80}[。！？]?" % "|".join(
    re.escape(signal) for signal in PLANT_SIGNALS + PAYOFF_SIGNALS
))


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def emit(payload: dict, code: int = 0) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(code)


def ledger_path(root: Path) -> Path:
    return root / LEDGER_RELATIVE


def empty_ledger() -> dict:
    return {"version": 1, "items": [], "updated_at": now()}


def load_ledger(root: Path, create: bool = False) -> dict:
    path = ledger_path(root)
    if not path.exists():
        if create:
            ledger = empty_ledger()
            save_ledger(root, ledger)
            return ledger
        emit({"ok": False, "error": f"伏笔账本不存在: {path}", "suggest": "运行 init"}, 1)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        emit({"ok": False, "error": f"伏笔账本 JSON 无效: {exc}"}, 1)
    return data


def save_ledger(root: Path, ledger: dict) -> None:
    path = ledger_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger["updated_at"] = now()
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def positive_int(value: Any) -> Optional[int]:
    if isinstance(value, int) and value > 0:
        return value
    return None


def validate_item(item: dict) -> List[str]:
    issues = []
    for key in ("id", "title", "status", "purpose", "setup", "payoff", "context"):
        if key not in item:
            issues.append(f"缺少字段 {key}")
    if item.get("status") not in STATUSES:
        issues.append(f"未知状态 {item.get('status')}")
    if not str(item.get("purpose", "")).strip():
        issues.append("purpose 必须说明为何留下该伏笔")

    setup = item.get("setup", {})
    if item.get("status") not in {"planned", "cancelled"}:
        if not positive_int(setup.get("chapter")):
            issues.append("已埋设伏笔必须记录 setup.chapter")
        if not str(setup.get("evidence", "")).strip():
            issues.append("已埋设伏笔必须记录原文 evidence")
        if not str(setup.get("reader_impression", "")).strip():
            issues.append("必须记录读者初读时会如何理解该细节")

    payoff = item.get("payoff", {})
    has_schedule = any(positive_int(payoff.get(key)) for key in (
        "earliest_chapter", "target_chapter", "latest_chapter", "target_volume", "target_part"
    )) or bool(payoff.get("conditions"))
    if item.get("status") not in CLOSED_STATUSES and not has_schedule:
        issues.append("活跃伏笔必须有回收章节/卷/部窗口或触发条件")
    earliest = positive_int(payoff.get("earliest_chapter"))
    target = positive_int(payoff.get("target_chapter"))
    latest = positive_int(payoff.get("latest_chapter"))
    if earliest and target and earliest > target:
        issues.append("earliest_chapter 不能晚于 target_chapter")
    if target and latest and target > latest:
        issues.append("target_chapter 不能晚于 latest_chapter")

    if item.get("status") == "recovered":
        actual = item.get("actual_payoff")
        if not isinstance(actual, dict):
            issues.append("已回收伏笔必须有 actual_payoff")
        else:
            for key in ("chapter", "method", "evidence", "effect"):
                if not actual.get(key):
                    issues.append(f"actual_payoff 缺少 {key}")
    if item.get("status") == "deferred" and not str(payoff.get("defer_reason", "")).strip():
        issues.append("延期伏笔必须记录 payoff.defer_reason")
    if item.get("status") == "cancelled" and not str(item.get("cancel_reason", "")).strip():
        issues.append("取消伏笔必须记录 cancel_reason")

    context = item.get("context", {})
    if not isinstance(context.get("nearby_chapters", []), list):
        issues.append("context.nearby_chapters 必须是列表")
    if not isinstance(item.get("history", []), list):
        issues.append("history 必须是列表")
    return issues


def validate_ledger(ledger: dict) -> List[dict]:
    issues = []
    items = ledger.get("items")
    if not isinstance(items, list):
        return [{"id": None, "issues": ["items 必须是列表"]}]
    seen = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            issues.append({"id": None, "index": index, "issues": ["条目必须是对象"]})
            continue
        item_id = item.get("id")
        item_issues = validate_item(item)
        if not item_id:
            item_issues.append("缺少 id")
        elif item_id in seen:
            item_issues.append("id 重复")
        seen.add(item_id)
        if item_issues:
            issues.append({"id": item_id, "index": index, "issues": item_issues})
    return issues


def classify(item: dict, chapter: int, volume: int, part: int, lookahead: int) -> Tuple[str, str]:
    status = item.get("status")
    if status in CLOSED_STATUSES:
        return "closed", f"状态为 {status}"
    if status == "planned":
        return "planned", "尚未写入正文"

    payoff = item.get("payoff", {})
    latest = positive_int(payoff.get("latest_chapter"))
    target = positive_int(payoff.get("target_chapter"))
    earliest = positive_int(payoff.get("earliest_chapter"))
    target_volume = positive_int(payoff.get("target_volume"))
    target_part = positive_int(payoff.get("target_part"))

    if latest and chapter > latest:
        return "overdue", f"已超过最迟回收章 {latest}"
    if target and chapter >= target:
        return "due", f"已到目标回收章 {target}"
    if target and target - chapter <= lookahead:
        return "due_soon", f"距目标回收章 {target} 还有 {target - chapter} 章"
    if earliest and chapter >= earliest:
        return "available", f"已进入可回收窗口，目标章为 {target or '未定'}"
    if target_volume and volume > target_volume:
        return "overdue", f"已超过目标回收卷 {target_volume}"
    if target_volume and volume == target_volume:
        return "due", f"已进入目标回收卷 {target_volume}"
    if target_part and part > target_part:
        return "overdue", f"已超过目标回收部 {target_part}"
    if target_part and part == target_part:
        return "due", f"已进入目标回收部 {target_part}"
    if payoff.get("conditions"):
        return "conditional", "需结合回收条件判断是否触发"
    return "not_due", "尚未进入回收窗口"


def chapter_number(path: Path) -> int:
    match = re.search(r"第(\d+)章", path.name)
    return int(match.group(1)) if match else 0


def find_summary(root: Path, chapter: int) -> Optional[Path]:
    summary_dir = root / ".story-system" / "chapter_summaries"
    if not summary_dir.exists():
        return None
    matches = [path for path in summary_dir.rglob("*.json") if chapter_number(path) == chapter]
    return sorted(matches)[0] if matches else None


def find_chapter(root: Path, chapter: int) -> Optional[Path]:
    content_dir = root / "正文"
    if not content_dir.exists():
        return None
    matches = [path for path in content_dir.rglob("第*章*.md") if chapter_number(path) == chapter]
    return sorted(matches)[0] if matches else None


def summary_text(data: Any) -> str:
    if isinstance(data, dict):
        for key in ("summary", "chapter_summary", "facts", "content"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:1500]
            if isinstance(value, list) and value:
                return "；".join(str(item) for item in value)[:1500]
        return json.dumps(data, ensure_ascii=False)[:1500]
    return str(data)[:1500]


def collect_context(root: Path, setup_chapter: int, current_chapter: int, window: int) -> List[dict]:
    records = []
    start = max(1, setup_chapter - window)
    end = min(current_chapter, setup_chapter + window)
    for number in range(start, end + 1):
        summary = find_summary(root, number)
        chapter = find_chapter(root, number)
        record = {
            "chapter": number,
            "relation": "setup" if number == setup_chapter else ("before" if number < setup_chapter else "after"),
            "chapter_file": str(chapter.relative_to(root)) if chapter else None,
            "summary_file": str(summary.relative_to(root)) if summary else None,
            "summary_status": "available" if summary else "missing",
        }
        if summary:
            try:
                record["summary"] = summary_text(json.loads(summary.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                record["summary_status"] = "invalid"
        records.append(record)
    return records


def cmd_init(args: argparse.Namespace) -> None:
    path = ledger_path(args.project_root)
    if path.exists() and not args.force:
        emit({"ok": True, "status": "exists", "ledger": str(path)})
    ledger = empty_ledger()
    save_ledger(args.project_root, ledger)
    emit({"ok": True, "status": "created", "ledger": str(path)})


def cmd_validate(args: argparse.Namespace) -> None:
    ledger = load_ledger(args.project_root)
    issues = validate_ledger(ledger)
    emit({"ok": not issues, "issues": issues, "count": len(ledger.get("items", []))}, 0 if not issues else 1)


def cmd_status(args: argparse.Namespace) -> None:
    ledger = load_ledger(args.project_root)
    issues = validate_ledger(ledger)
    counts: Dict[str, int] = {}
    for item in ledger.get("items", []):
        status = str(item.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    emit({"ok": not issues, "ledger": str(ledger_path(args.project_root)), "counts": counts, "issues": issues, "items": ledger.get("items", [])}, 0 if not issues else 1)


def cmd_due(args: argparse.Namespace) -> None:
    ledger = load_ledger(args.project_root)
    issues = validate_ledger(ledger)
    if issues:
        emit({"ok": False, "error": "伏笔账本校验失败", "issues": issues}, 1)
    buckets: Dict[str, List[dict]] = {}
    for item in ledger.get("items", []):
        classification, reason = classify(item, args.chapter, args.volume, args.part, args.lookahead)
        entry = {"id": item.get("id"), "title": item.get("title"), "classification": classification, "reason": reason, "item": item}
        buckets.setdefault(classification, []).append(entry)
    needs_action = buckets.get("overdue", []) + buckets.get("due", []) + buckets.get("conditional", [])
    emit({
        "ok": True,
        "position": {"part": args.part, "volume": args.volume, "chapter": args.chapter},
        "needs_action": needs_action,
        "due_soon": buckets.get("due_soon", []),
        "available": buckets.get("available", []),
        "not_due": buckets.get("not_due", []),
        "planned": buckets.get("planned", []),
        "closed": buckets.get("closed", []),
    })


def cmd_upsert(args: argparse.Namespace) -> None:
    ledger = load_ledger(args.project_root, create=True)
    try:
        payload = json.loads(args.payload.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        emit({"ok": False, "error": f"无法读取 payload: {exc}"}, 2)
    item = payload.get("item", payload) if isinstance(payload, dict) else payload
    if not isinstance(item, dict):
        emit({"ok": False, "error": "payload 必须是伏笔对象或包含 item 的对象"}, 2)
    issues = validate_item(item)
    if issues:
        emit({"ok": False, "error": "伏笔条目不完整", "issues": issues}, 1)

    existing_index = next((i for i, value in enumerate(ledger["items"]) if value.get("id") == item.get("id")), None)
    old_status = None
    if existing_index is not None:
        old_status = ledger["items"][existing_index].get("status")
        old_history = ledger["items"][existing_index].get("history", [])
        item.setdefault("history", old_history)
        ledger["items"][existing_index] = item
        action = "updated"
    else:
        item.setdefault("history", [])
        ledger["items"].append(item)
        action = "created"
    item["updated_at"] = now()
    item["history"].append({"at": now(), "action": action, "from_status": old_status, "to_status": item.get("status"), "chapter": item.get("last_updated_chapter")})
    save_ledger(args.project_root, ledger)
    emit({"ok": True, "action": action, "id": item.get("id"), "ledger": str(ledger_path(args.project_root))})


def cmd_refresh_context(args: argparse.Namespace) -> None:
    ledger = load_ledger(args.project_root)
    updated = []
    missing_summaries = []
    for item in ledger.get("items", []):
        setup_chapter = positive_int(item.get("setup", {}).get("chapter"))
        if not setup_chapter or setup_chapter > args.chapter:
            continue
        context = item.setdefault("context", {})
        window = positive_int(context.get("window")) or args.window
        nearby = collect_context(args.project_root, setup_chapter, args.chapter, window)
        context["window"] = window
        context["nearby_chapters"] = nearby
        context["refreshed_at_chapter"] = args.chapter
        updated.append(item.get("id"))
        missing_summaries.extend(record["chapter"] for record in nearby if record["summary_status"] != "available")
    save_ledger(args.project_root, ledger)
    emit({"ok": True, "updated": updated, "missing_summaries": sorted(set(missing_summaries)), "ledger": str(ledger_path(args.project_root))})


def cmd_detect(args: argparse.Namespace) -> None:
    try:
        text = args.chapter_file.read_text(encoding="utf-8")
    except OSError as exc:
        emit({"ok": False, "error": str(exc)}, 2)
    candidates = []
    for match in SENTENCE_RE.finditer(text):
        sentence = match.group(0).strip()
        kind = "payoff_candidate" if any(signal in sentence for signal in PAYOFF_SIGNALS) else "plant_candidate"
        candidates.append({"kind": kind, "evidence": sentence})
    emit({"ok": True, "chapter_file": str(args.chapter_file), "candidates": candidates[:20], "note": "候选句必须结合大纲和语义人工确认，不能自动写入账本"})


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="伏笔账本与回收窗口管理")
    sub = p.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--project-root", type=Path, required=True)
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    for name, func in (("validate", cmd_validate), ("status", cmd_status)):
        command = sub.add_parser(name)
        command.add_argument("--project-root", type=Path, required=True)
        command.set_defaults(func=func)

    due = sub.add_parser("due")
    due.add_argument("--project-root", type=Path, required=True)
    due.add_argument("--part", type=int, required=True)
    due.add_argument("--volume", type=int, required=True)
    due.add_argument("--chapter", type=int, required=True)
    due.add_argument("--lookahead", type=int, default=3)
    due.set_defaults(func=cmd_due)

    upsert = sub.add_parser("upsert")
    upsert.add_argument("--project-root", type=Path, required=True)
    upsert.add_argument("--payload", type=Path, required=True)
    upsert.set_defaults(func=cmd_upsert)

    refresh = sub.add_parser("refresh-context")
    refresh.add_argument("--project-root", type=Path, required=True)
    refresh.add_argument("--chapter", type=int, required=True)
    refresh.add_argument("--window", type=int, default=2)
    refresh.set_defaults(func=cmd_refresh_context)

    detect = sub.add_parser("detect")
    detect.add_argument("--chapter-file", type=Path, required=True)
    detect.set_defaults(func=cmd_detect)
    return p


def main() -> None:
    args = parser().parse_args()
    args.project_root = args.project_root.resolve() if hasattr(args, "project_root") else None
    args.func(args)


if __name__ == "__main__":
    main()
