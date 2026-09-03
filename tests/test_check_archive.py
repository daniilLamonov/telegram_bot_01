import os
import zipfile
from datetime import datetime
from pathlib import Path

from utils.check_archive import (
    CheckFile,
    build_archives,
    collect_check_files,
    get_file_datetime,
    split_by_size,
)


def make_check(root: Path, name: str, size: int = 10, mtime: datetime | None = None) -> Path:
    path = root / name
    path.write_bytes(b"x" * size)
    if mtime:
        os.utime(path, (mtime.timestamp(), mtime.timestamp()))
    return path


def test_date_is_taken_from_file_name(tmp_path):
    path = make_check(tmp_path, "check_-100500_20260902_143000.jpg")
    assert get_file_datetime(path) == datetime(2026, 9, 2, 14, 30, 0)


def test_date_falls_back_to_mtime_for_foreign_names(tmp_path):
    mtime = datetime(2026, 9, 2, 8, 0, 0)
    path = make_check(tmp_path, "scan.pdf", mtime=mtime)
    assert get_file_datetime(path) == mtime


def test_collect_returns_only_files_of_the_period_sorted(tmp_path):
    make_check(tmp_path, "check_-1_20260901_235959.jpg")
    make_check(tmp_path, "check_-1_20260902_090000.jpg")
    make_check(tmp_path, "check_-2_20260902_010000.jpg")
    make_check(tmp_path, "check_-1_20260903_000000.jpg")

    found = collect_check_files(
        tmp_path,
        datetime(2026, 9, 2, 0, 0, 0),
        datetime(2026, 9, 2, 23, 59, 59),
    )

    assert [item.path.name for item in found] == [
        "check_-2_20260902_010000.jpg",
        "check_-1_20260902_090000.jpg",
    ]


def test_collect_on_missing_directory(tmp_path):
    assert collect_check_files(tmp_path / "nope", datetime(2026, 9, 2), datetime(2026, 9, 3)) == []


def test_split_keeps_parts_within_the_limit():
    files = [
        CheckFile(Path(f"check_{i}.jpg"), 40, datetime(2026, 9, 2))
        for i in range(5)
    ]

    chunks = split_by_size(files, max_part_size=100)

    assert [len(chunk) for chunk in chunks] == [2, 2, 1]


def test_oversized_file_goes_into_its_own_part():
    files = [
        CheckFile(Path("small.jpg"), 10, datetime(2026, 9, 2)),
        CheckFile(Path("huge.jpg"), 500, datetime(2026, 9, 2)),
    ]

    chunks = split_by_size(files, max_part_size=100)

    assert [len(chunk) for chunk in chunks] == [1, 1]


def test_build_archives_packs_every_file(tmp_path):
    checks = tmp_path / "checks"
    checks.mkdir()
    dest = tmp_path / "out"
    dest.mkdir()
    for i in range(3):
        make_check(checks, f"check_-1_2026090{i + 1}_120000.jpg", size=40)

    files = collect_check_files(checks, datetime(2026, 9, 1), datetime(2026, 9, 4))
    archives = build_archives(files, checks, dest, "checks_period", max_part_size=100)

    assert [archive.path.name for archive in archives] == [
        "checks_period_part1.zip",
        "checks_period_part2.zip",
    ]
    packed = []
    for archive in archives:
        with zipfile.ZipFile(archive.path) as zf:
            packed.extend(zf.namelist())
    assert sorted(packed) == sorted(item.path.name for item in files)
    assert sum(archive.files_count for archive in archives) == 3


def test_single_part_archive_keeps_plain_name(tmp_path):
    checks = tmp_path / "checks"
    checks.mkdir()
    make_check(checks, "check_-1_20260902_120000.jpg")

    files = collect_check_files(checks, datetime(2026, 9, 2), datetime(2026, 9, 3))
    archives = build_archives(files, checks, tmp_path, "checks_02.09.2026")

    assert len(archives) == 1
    assert archives[0].path.name == "checks_02.09.2026.zip"
