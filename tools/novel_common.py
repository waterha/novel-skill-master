#!/usr/bin/env python3
"""
novel_common.py — 小说创作工具共享模块

为 knowledge graph、RAG 检索、节奏控制等工具提供统一的文件/JSON/字符串工具函数。
零外部依赖。
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── 文件系统操作 ──────────────────────────────────────────────────────────────

def ensure_dir(path: Path) -> None:
    """确保目录存在，不存在则递归创建。"""
    path.mkdir(parents=True, exist_ok=True)


def read_text(path: Path, default: str = "") -> str:
    """安全读取文本文件。"""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, PermissionError):
        return default


def write_text(path: Path, content: str) -> bool:
    """安全写入文本文件。"""
    try:
        ensure_dir(path.parent)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        return True
    except (IOError, PermissionError) as e:
        print(f"[ERROR] 写入失败 {path}: {e}")
        return False


def load_json(path: Path, default: Optional[Any] = None) -> Any:
    """安全加载 JSON 文件。"""
    if default is None:
        default = {}
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError, OSError):
        pass
    return default


def save_json(path: Path, data: Any, indent: int = 2) -> bool:
    """安全保存 JSON 文件。"""
    try:
        ensure_dir(path.parent)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
        return True
    except (IOError, OSError) as e:
        print(f"[ERROR] 保存失败 {path}: {e}")
        return False


# ── 字符串处理 ────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """将文本转为适合做 ID 的 slug。"""
    slug = re.sub(r"[^0-9A-Za-z一-鿿_-]+", "-", text).strip("-")
    if slug:
        return slug
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:8]


def chapter_no_from_name(filename: str) -> int:
    """从文件名提取章节号，如 '第15章-觉醒.md' → 15。"""
    m = re.search(r"第(\d+)章", filename)
    if m:
        return int(m.group(1))
    return 0


def normalize_text(text: str) -> str:
    """标准化文本：去掉多余空白和特殊字符。"""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[^一-鿿A-Za-z0-9，。！？、；：""''（）《》【】\-\n]", "", text)
    return text


def count_chars(text: str) -> int:
    """统计中文字符数。"""
    return len(re.findall(r"[一-鿿]", text))


# ── 正则预编译 ────────────────────────────────────────────────────────────────

CHAPTER_FILE_RE = re.compile(r"^第\d+章.*\.md$")
CJK_RE = re.compile(r"[一-鿿]")


# ── 配置路径模板 ─────────────────────────────────────────────────────────────

def get_story_graph_path(project_root: Path) -> Path:
    """知识图谱文件路径。"""
    return project_root / ".story-system" / "story_graph.json"


def get_retrieval_dir(project_root: Path) -> Path:
    """RAG 检索目录路径。"""
    return project_root / ".webnovel" / "retrieval"


def get_pacing_path(project_root: Path) -> Path:
    """节奏控制状态文件路径。"""
    return project_root / ".story-system" / "pacing_state.json"


def get_event_matrix_path(project_root: Path) -> Path:
    """事件矩阵状态文件路径。"""
    return project_root / ".story-system" / "event_matrix.json"
