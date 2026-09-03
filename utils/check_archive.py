"""Сбор файлов чеков за период в zip-архивы для отправки в чат."""

from __future__ import annotations

import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable, NamedTuple

# В описании операции файл чека хранится как "... Файл: check_-100_20260902_143000.jpg"
_FILENAME_RE = re.compile(r"Файл:\s*(.+?)\s*$")

# Bot API не принимает документы больше 50 МБ, оставляем запас на служебные данные
MAX_PART_SIZE = 45 * 1024 * 1024


class CheckFile(NamedTuple):
    path: Path
    size: int
    check_date: datetime


class CheckArchive(NamedTuple):
    path: Path
    files_count: int
    size: int


class CheckSelection(NamedTuple):
    files: list[CheckFile]
    missing: list[str]  # operation_id чеков, файл которых не найден на сервере


def extract_filename(description: str | None) -> str | None:
    """Достать имя файла чека из описания операции."""
    if not description:
        return None
    match = _FILENAME_RE.search(description)
    return match.group(1) if match else None


def resolve_check_files(
    operations: Iterable[dict], files_dir: str | Path
) -> CheckSelection:
    """Сопоставить операции из БД с файлами чеков на диске.

    Дата чека берётся из записи операции, а не из имени файла или его
    метаданных: дату могли изменить вручную, и чек должен попадать
    в выгрузку за ту дату, которая указана в записи.
    """
    root = Path(files_dir).resolve()
    files: dict[Path, CheckFile] = {}
    missing: list[str] = []

    for operation in operations:
        filename = extract_filename(operation.get("description"))
        path = (root / filename).resolve() if filename else None

        if path is None or not path.is_relative_to(root) or not path.is_file():
            missing.append(operation["operation_id"])
            continue

        if path in files:
            continue

        files[path] = CheckFile(path, path.stat().st_size, operation["timestamp"])

    ordered = sorted(files.values(), key=lambda item: item.check_date)
    return CheckSelection(ordered, missing)


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
    root = Path(root).resolve()
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
