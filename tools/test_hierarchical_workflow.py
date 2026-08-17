#!/usr/bin/env python3

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.project_stats import count_chapter_files, count_words_in_dir


TOOLS = Path(__file__).resolve().parent
OUTLINE_GUARD = TOOLS / "outline_guard.py"
MASTER_STATE = TOOLS / "master_state.py"
PROJECT_DOCTOR = TOOLS / "project_doctor.py"
FORESHADOWING_TRACKER = TOOLS / "foreshadowing_tracker.py"
CONTINUATION_SCANNER = TOOLS / "continuation_scanner.py"


def run(script: Path, root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def write_structure(path: Path, marker: str, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    required_terms = (
        "故事承诺 起点与终点 核心冲突 人物 部方向 完结标准 "
        "本部功能 承接状态 卷方向 收束 叙事任务 起点 主要事件 卷末结果 下一卷钩子 "
        "章节范围 剧情单元 递增 伏笔 伏笔动作 高潮 闭合 章号 目标 冲突 结果 章末钩子 "
        "承接点 场景 状态变化 必须出现 不可出现 章末结果 目标字数"
    )
    path.write_text(
        marker + "\n\n# 标题\n\n" + required_terms + "\n\n" + ("有效内容。" * size) + "\n",
        encoding="utf-8",
    )


class OutlineGuardTests(unittest.TestCase):
    def test_missing_future_part_blocks_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = run(
                OUTLINE_GUARD,
                root,
                "init", "--project-root", str(root),
                "--parts", "3", "--volumes-per-part", "2,2,2",
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            write_structure(
                root / "大纲/00-总纲/全书总纲.md",
                "<!-- novel-structure: book; status: confirmed -->",
                140,
            )
            for part in range(1, 4):
                write_structure(
                    root / f"大纲/01-部纲/第{part:02d}部-部纲.md",
                    f"<!-- novel-structure: part; part: {part}; status: confirmed -->",
                    140,
                )
            for volume in range(1, 7):
                part = ((volume - 1) // 2) + 1
                status = "detailed-confirmed" if volume == 1 else "direction-confirmed"
                write_structure(
                    root / f"大纲/02-卷纲/第{part:02d}部/第{volume:03d}卷-卷纲.md",
                    f"<!-- novel-structure: volume; part: {part}; volume: {volume}; status: {status} -->",
                    180 if volume == 1 else 60,
                )

            chapter_dir = root / "大纲/03-章纲/第01部/第001卷"
            write_structure(
                chapter_dir / "卷章节索引.md",
                "<!-- novel-structure: chapter-index; part: 1; volume: 1; status: confirmed -->",
                90,
            )
            write_structure(
                chapter_dir / "第0001章-章纲.md",
                "<!-- novel-structure: chapter; part: 1; volume: 1; chapter: 1; status: confirmed -->",
                90,
            )

            passed = run(
                OUTLINE_GUARD,
                root,
                "preflight", "--project-root", str(root),
                "--part", "1", "--volume", "1", "--chapter", "1",
            )
            self.assertEqual(passed.returncode, 0, passed.stdout)
            self.assertTrue(json.loads(passed.stdout)["ok"])

            (root / ".story-system").mkdir(parents=True, exist_ok=True)
            (root / ".story-system/MASTER_SETTING.json").write_text("{}\n", encoding="utf-8")
            (root / ".story-system/character_states.json").write_text("{}\n", encoding="utf-8")
            result = run(FORESHADOWING_TRACKER, root, "init", "--project-root", str(root))
            self.assertEqual(result.returncode, 0, result.stdout)
            doctor = run(
                PROJECT_DOCTOR,
                root,
                "preflight", "--project-root", str(root),
                "--part", "1", "--volume", "1", "--chapter", "1",
            )
            self.assertTrue(json.loads(doctor.stdout)["all_checks_pass"])

            (root / "大纲/01-部纲/第03部-部纲.md").unlink()
            blocked = run(
                OUTLINE_GUARD,
                root,
                "preflight", "--project-root", str(root),
                "--part", "1", "--volume", "1", "--chapter", "1",
            )
            self.assertNotEqual(blocked.returncode, 0)
            payload = json.loads(blocked.stdout)
            self.assertFalse(payload["ok"])
            self.assertFalse(payload["checks"]["all_parts_and_volume_directions"])

            doctor = run(
                PROJECT_DOCTOR,
                root,
                "preflight", "--project-root", str(root),
                "--part", "1", "--volume", "1", "--chapter", "1",
            )
            self.assertFalse(json.loads(doctor.stdout)["all_checks_pass"])


class MasterStateTests(unittest.TestCase):
    def test_part_closure_precedes_next_part(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = run(
                MASTER_STATE,
                root,
                "init", "--name", "测试小说", "--parts", "2", "--volumes-per-part", "2,1",
            )
            self.assertEqual(result.returncode, 0, result.stdout)

            for stage in ("topic", "settings", "tagline", "init", "book_outline"):
                result = run(MASTER_STATE, root, "done", "--stage", stage)
                self.assertEqual(result.returncode, 0, result.stdout)
            for part in (1, 2):
                result = run(MASTER_STATE, root, "done", "--stage", "part_outline", "--part", str(part))
                self.assertEqual(result.returncode, 0, result.stdout)

            for volume in (1, 2):
                for stage in ("plan", "arc", "chapter_outline"):
                    result = run(MASTER_STATE, root, "done", "--stage", stage, "--volume", str(volume))
                    self.assertEqual(result.returncode, 0, result.stdout)
                result = run(MASTER_STATE, root, "close", "--level", "volume", "--volume", str(volume))
                self.assertEqual(result.returncode, 0, result.stdout)

            next_step = run(MASTER_STATE, root, "next-step")
            payload = json.loads(next_step.stdout)
            self.assertEqual(payload["phase"], "finalization")
            self.assertIn("finish --level part --part 1", payload["action"])

            closed = run(MASTER_STATE, root, "close", "--level", "part", "--part", "1")
            self.assertEqual(closed.returncode, 0, closed.stdout)
            next_step = run(MASTER_STATE, root, "next-step")
            payload = json.loads(next_step.stdout)
            self.assertIn("plan --volume 3", payload["action"])


class NestedManuscriptTests(unittest.TestCase):
    def test_stats_find_chapters_inside_part_and_volume(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            content = Path(temp) / "正文"
            chapter = content / "第01部/第001卷/第0001章-开端.md"
            chapter.parent.mkdir(parents=True, exist_ok=True)
            chapter.write_text("故事" * 120, encoding="utf-8")
            self.assertEqual(count_chapter_files(content), 1)
            self.assertEqual(count_words_in_dir(content), 240)


class ForeshadowingTests(unittest.TestCase):
    def test_due_windows_and_nearby_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(run(FORESHADOWING_TRACKER, root, "init", "--project-root", str(root)).returncode, 0)
            payload = {
                "id": "FS-0001",
                "title": "旧钥匙缺口",
                "type": "object",
                "scope": "volume",
                "status": "planted",
                "purpose": "为密室开启方式提供公平条件",
                "setup": {
                    "part": 1,
                    "volume": 1,
                    "chapter": 3,
                    "scene": "门厅",
                    "evidence": "钥匙边缘缺了一角。",
                    "reader_impression": "普通磨损",
                    "intended_truth": "缺口对应密室机关"
                },
                "context": {"window": 2, "nearby_chapters": []},
                "payoff": {
                    "earliest_chapter": 18,
                    "target_chapter": 22,
                    "latest_chapter": 25,
                    "target_volume": 2,
                    "target_part": 1,
                    "conditions": ["进入地下层"],
                    "planned_method": "行动兑现"
                },
                "reinforcements": [],
                "actual_payoff": None,
                "dependencies": [],
                "history": [],
                "last_updated_chapter": 3
            }
            payload_path = root / "payload.json"
            payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            result = run(
                FORESHADOWING_TRACKER, root, "upsert", "--project-root", str(root),
                "--payload", str(payload_path),
            )
            self.assertEqual(result.returncode, 0, result.stdout)

            due = run(
                FORESHADOWING_TRACKER, root, "due", "--project-root", str(root),
                "--part", "1", "--volume", "1", "--chapter", "22",
            )
            self.assertEqual(json.loads(due.stdout)["needs_action"][0]["classification"], "due")
            overdue = run(
                FORESHADOWING_TRACKER, root, "due", "--project-root", str(root),
                "--part", "1", "--volume", "2", "--chapter", "26",
            )
            self.assertEqual(json.loads(overdue.stdout)["needs_action"][0]["classification"], "overdue")

            summary_dir = root / ".story-system/chapter_summaries"
            summary_dir.mkdir(parents=True, exist_ok=True)
            for chapter in range(1, 6):
                (summary_dir / f"第{chapter:04d}章.json").write_text(
                    json.dumps({"chapter": chapter, "summary": f"第{chapter}章事实"}, ensure_ascii=False),
                    encoding="utf-8",
                )
            refresh = run(
                FORESHADOWING_TRACKER, root, "refresh-context", "--project-root", str(root),
                "--chapter", "5", "--window", "2",
            )
            self.assertEqual(refresh.returncode, 0, refresh.stdout)
            ledger = json.loads((root / ".story-system/foreshadowing.json").read_text(encoding="utf-8"))
            nearby = ledger["items"][0]["context"]["nearby_chapters"]
            self.assertEqual([item["chapter"] for item in nearby], [1, 2, 3, 4, 5])


class ContinuationScannerTests(unittest.TestCase):
    def test_resume_requires_complete_summary_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(run(
                OUTLINE_GUARD, root, "init", "--project-root", str(root),
                "--parts", "1", "--volumes-per-part", "1",
            ).returncode, 0)
            (root / ".webnovel/master_state.json").write_text(
                json.dumps({"current_part": 1, "current_volume": 1, "current_chapter": 2}), encoding="utf-8"
            )
            write_structure(root / "大纲/00-总纲/全书总纲.md", "<!-- novel-structure: book; status: confirmed -->", 140)
            write_structure(root / "大纲/01-部纲/第01部-部纲.md", "<!-- novel-structure: part; part: 1; status: confirmed -->", 140)
            write_structure(root / "大纲/02-卷纲/第01部/第001卷-卷纲.md", "<!-- novel-structure: volume; part: 1; volume: 1; status: detailed-confirmed -->", 180)
            write_structure(root / "大纲/03-章纲/第01部/第001卷/卷章节索引.md", "<!-- novel-structure: chapter-index; part: 1; volume: 1; status: confirmed -->", 90)
            write_structure(root / "大纲/03-章纲/第01部/第001卷/第0003章-章纲.md", "<!-- novel-structure: chapter; part: 1; volume: 1; chapter: 3; status: confirmed -->", 90)
            for chapter in (1, 2):
                chapter_path = root / f"正文/第01部/第001卷/第{chapter:04d}章-正文.md"
                chapter_path.parent.mkdir(parents=True, exist_ok=True)
                chapter_path.write_text("正文内容" * 100, encoding="utf-8")
            for name in ("MASTER_SETTING.json", "character_states.json", "timeline.json"):
                path = root / ".story-system" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}\n", encoding="utf-8")
            self.assertEqual(run(FORESHADOWING_TRACKER, root, "init", "--project-root", str(root)).returncode, 0)

            summary_dir = root / ".story-system/chapter_summaries"
            summary_dir.mkdir(parents=True, exist_ok=True)
            (summary_dir / "第0001章.json").write_text('{"summary":"第一章事实"}\n', encoding="utf-8")
            (summary_dir / "第0002章.json").write_text('{}\n', encoding="utf-8")
            blocked = run(
                CONTINUATION_SCANNER, root, "scan", "--project-root", str(root), "--write-inventory"
            )
            self.assertNotEqual(blocked.returncode, 0)
            self.assertEqual(json.loads(blocked.stdout)["manuscript_summary"]["missing_summaries"], [2])

            (summary_dir / "第0002章.json").write_text('{"summary":"第二章事实"}\n', encoding="utf-8")
            ready = run(
                CONTINUATION_SCANNER, root, "scan", "--project-root", str(root), "--write-inventory"
            )
            self.assertEqual(ready.returncode, 0, ready.stdout)
            self.assertTrue(json.loads(ready.stdout)["resume_ready"])


if __name__ == "__main__":
    unittest.main()
