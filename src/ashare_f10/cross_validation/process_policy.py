from __future__ import annotations

import os
import tempfile
from importlib.resources import files
from pathlib import Path

POLICY_FILE_NAME = "通用高效率任务执行_标准化流程.md"


def _valid(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return bool(text.strip() and "通用高效率任务执行" in text and "薄切片" in text and "四层验证" in text)


def find_process_policy(start: Path | str | None = None) -> Path | None:
    override = os.getenv("ASHARE_F10_PROCESS_POLICY")
    if override:
        path = Path(override).expanduser().resolve()
        return path if _valid(path) else None
    current = Path(start or Path.cwd()).resolve()
    for base in (current, *current.parents):
        candidate = base / "docs" / "process" / POLICY_FILE_NAME
        if _valid(candidate):
            return candidate
    try:
        resource = files("ashare_f10.resources").joinpath(POLICY_FILE_NAME)
        text = resource.read_text(encoding="utf-8")
        if "通用高效率任务执行" in text and "薄切片" in text and "四层验证" in text:
            cached = Path(tempfile.gettempdir()) / "ashare_f10" / POLICY_FILE_NAME
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(text, encoding="utf-8")
            return cached
    except (FileNotFoundError, ModuleNotFoundError):
        return None
    return None


def ensure_process_policy(start: Path | str | None = None) -> Path:
    path = find_process_policy(start)
    if path is None:
        raise RuntimeError(
            "PROCESS_POLICY_MISSING：长任务启动前必须能够读取 "
            f"docs/process/{POLICY_FILE_NAME}；可用 ASHARE_F10_PROCESS_POLICY 指定路径"
        )
    return path
