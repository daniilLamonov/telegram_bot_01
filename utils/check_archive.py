"""Сбор файлов чеков за период в zip-архивы для отправки в чат."""

from __future__ import annotations

import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

# Имя, под которым /check сохраняет файл: check_{chat_id}_{YYYYMMDD_HHMMSS}.{ext}
_CHECK_NAME_RE = re.compile(r"^check_-?\d+_(\d{8}_\d{6})\.")

# Bot API не принимает документы больше 50 МБ, оставляем запас на служебные данные
MAX_PART_SIZE = 45 * 1024 * 1024


class CheckFile(NamedTuple):
    path: Path
    size: int
    created_at: datetime


class CheckArchive(NamedTuple):
    path: Path
    files_count: int
    size: int


def get_file_datetime(path: Path) -> datetime:
    """Дата чека: из имени файла, а для нестандартных имён — из времени изменения."""
    match = _CHECK_NAME_RE.match(path.name)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S")
        except ValueError:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime)


def collect_check_files(
    files_dir: str | Path, start_date: datetime, end_date: datetime
) -> list[CheckFile]:
    """Вернуть чеки, сохранённые в интервале [start_date, end_date]."""
    root = Path(files_dir)
    if not root.is_dir():
        return []

    found: list[CheckFile] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        created_at = get_file_datetime(path)
        if start_date <= created_at <= end_date:
            found.append(CheckFile(path, path.stat().st_size, created_at))

    found.sort(key=lambda item: item.created_at)
    return found


def split_by_size(
    files: list[CheckFile], max_part_size: int = MAX_PART_SIZE
) -> list[list[CheckFile]]:
    """Разбить чеки на части, каждая из которых влезает в один документ Telegram."""
    chunks: list[list[CheckFile]] = []
    current: list[CheckFile] = []
    current_size = 0

    for item in files:
        if current and current_size + item.size > max_part_size:
            chunks.append(current)
            current, current_size = [], 0
        current.append(item)
        current_size += item.size

    if current:
        chunks.append(current)
    return chunks


def build_archives(
    files: list[CheckFile],
    root: str | Path,
    dest_dir: str | Path,
    base_name: str,
    max_part_size: int = MAX_PART_SIZE,
) -> list[CheckArchive]:
    """Упаковать чеки в zip-архивы в ``dest_dir`` и вернуть описание частей."""
    root = Path(root)
    dest = Path(dest_dir)
    archives: list[CheckArchive] = []

    chunks = split_by_size(files, max_part_size)
    for index, chunk in enumerate(chunks, start=1):
        name = base_name if len(chunks) == 1 else f"{base_name}_part{index}"
        archive_path = dest / f"{name}.zip"

        with zipfile.ZipFile(
            archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=1
        ) as archive:
            for item in chunk:
                try:
                    arcname = str(item.path.relative_to(root))
                except ValueError:
                    arcname = item.path.name
                archive.write(item.path, arcname=arcname)

        archives.append(
            CheckArchive(archive_path, len(chunk), archive_path.stat().st_size)
        )

    return archives
