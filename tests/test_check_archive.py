import zipfile
from datetime import datetime
from pathlib import Path

from utils.check_archive import (
    CheckFile,
    build_archives,
    extract_filename,
    resolve_check_files,
    split_by_size,
)


def make_operation(operation_id: str, filename: str | None, timestamp: datetime) -> dict:
    description = "Плательщик: Иванов. Зачислено: 100.00 ₽. Тип: фото."
    if filename is not None:
        description += f" Файл: {filename}"
    return {
        "operation_id": operation_id,
        "timestamp": timestamp,
        "description": description,
    }


def make_file(root: Path, name: str, size: int = 10) -> Path:
    path = root / name
    path.write_bytes(b"x" * size)
    return path


def test_extract_filename():
    assert (
        extract_filename("Плательщик: Иванов. Тип: фото. Файл: check_-1_20260902_120000.jpg")
        == "check_-1_20260902_120000.jpg"
    )
    assert extract_filename("Файл:  scan.pdf  ") == "scan.pdf"
    assert extract_filename("Плательщик: Иванов") is None
    assert extract_filename(None) is None


def test_date_comes_from_the_operation_not_from_the_file_name(tmp_path):
    """Чеку поменяли дату вручную — файл должен уехать в выгрузку за новую дату."""
    make_file(tmp_path, "check_-1_20260830_120000.jpg")
    moved = make_operation("aaaa1111", "check_-1_20260830_120000.jpg", datetime(2026, 9, 2, 10, 0))

    selection = resolve_check_files([moved], tmp_path)

    assert selection.missing == []
    assert [item.check_date for item in selection.files] == [datetime(2026, 9, 2, 10, 0)]


def test_files_are_ordered_by_operation_date(tmp_path):
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        make_file(tmp_path, name)
    operations = [
        make_operation("op1", "a.jpg", datetime(2026, 9, 2, 18, 0)),
        make_operation("op2", "b.jpg", datetime(2026, 9, 2, 9, 0)),
        make_operation("op3", "c.jpg", datetime(2026, 9, 2, 12, 0)),
    ]

    selection = resolve_check_files(operations, tmp_path)

    assert [item.path.name for item in selection.files] == ["b.jpg", "c.jpg", "a.jpg"]


def test_operations_without_file_on_disk_are_reported(tmp_path):
    make_file(tmp_path, "there.jpg")
    operations = [
        make_operation("op1", "there.jpg", datetime(2026, 9, 2, 9, 0)),
        make_operation("op2", "gone.jpg", datetime(2026, 9, 2, 10, 0)),
        make_operation("op3", None, datetime(2026, 9, 2, 11, 0)),
    ]

    selection = resolve_check_files(operations, tmp_path)

    assert [item.path.name for item in selection.files] == ["there.jpg"]
    assert selection.missing == ["op2", "op3"]


def test_same_file_referenced_twice_is_packed_once(tmp_path):
    make_file(tmp_path, "one.jpg")
    operations = [
        make_operation("op1", "one.jpg", datetime(2026, 9, 2, 9, 0)),
        make_operation("op2", "one.jpg", datetime(2026, 9, 2, 10, 0)),
    ]

    selection = resolve_check_files(operations, tmp_path)

    assert len(selection.files) == 1
    assert selection.missing == []


def test_path_outside_the_checks_directory_is_rejected(tmp_path):
    checks = tmp_path / "checks"
    checks.mkdir()
    make_file(tmp_path, "secret.env")

    selection = resolve_check_files(
        [make_operation("op1", "../secret.env", datetime(2026, 9, 2, 9, 0))], checks
    )

    assert selection.files == []
    assert selection.missing == ["op1"]


def test_split_keeps_parts_within_the_limit():
    files = [CheckFile(Path(f"check_{i}.jpg"), 40, datetime(2026, 9, 2)) for i in range(5)]

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
    operations = []
    for i in range(3):
        name = f"check_-1_2026090{i + 1}_120000.jpg"
        make_file(checks, name, size=40)
        operations.append(make_operation(f"op{i}", name, datetime(2026, 9, i + 1, 12, 0)))

    files = resolve_check_files(operations, checks).files
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
    make_file(checks, "check_-1_20260902_120000.jpg")
    operations = [
        make_operation("op1", "check_-1_20260902_120000.jpg", datetime(2026, 9, 2, 12, 0))
    ]

    files = resolve_check_files(operations, checks).files
    archives = build_archives(files, checks, tmp_path, "checks_02.09.2026")

    assert len(archives) == 1
    assert archives[0].path.name == "checks_02.09.2026.zip"
