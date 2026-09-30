"""Phase 0: the download script extracts a BIRD dev zip without using the network."""

from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from mm.data.bird import load_bird_layout
from mm.data.download import (
    DEV_ZIP_SHA256,
    ChecksumMismatchError,
    UnsafeZipError,
    default_dest,
    download,
    extract_bird_dev,
    file_sha256,
    main,
)
from mm.paths import repo_root


def test_default_dest_is_gitignored_data_dir() -> None:
    assert default_dest() == repo_root() / "data" / "bird"


def test_extract_nested_dev_zip_loads(tmp_path: Path) -> None:
    archive = tmp_path / "dev.zip"
    _write_official_zip(archive)
    dest = tmp_path / "out"
    extract_bird_dev(archive, dest)
    dataset = load_bird_layout(dest)
    assert dataset.examples[0].db_id == "demo"
    assert dataset.database("demo").sqlite_path.is_file()
    assert (dest / "dev_tables.json").is_file()
    with pytest.raises(FileExistsError):
        extract_bird_dev(archive, dest)


def test_checksum_mismatch_raises_and_writes_nothing(tmp_path: Path) -> None:
    dest = tmp_path / "out"

    def fetch(_url: str, target: Path) -> None:
        target.write_bytes(b"not a zip")

    with pytest.raises(ChecksumMismatchError):
        download(dest, expected_sha256=DEV_ZIP_SHA256, fetcher=fetch)
    assert not dest.exists()


def test_download_with_injected_fetcher(tmp_path: Path) -> None:
    archive = tmp_path / "dev.zip"
    _write_official_zip(archive)
    digest = file_sha256(archive)
    payload = archive.read_bytes()
    dest = tmp_path / "bird"

    def fetch(_url: str, target: Path) -> None:
        target.write_bytes(payload)

    download(dest, url="https://example.test/dev.zip", expected_sha256=digest, fetcher=fetch)
    assert load_bird_layout(dest).examples[0].question_id == 1


def test_zip_slip_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "slip.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("../evil.txt", "nope")
    with pytest.raises(UnsafeZipError):
        extract_bird_dev(archive, tmp_path / "out")


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["--help"])
    assert caught.value.code == 0
    captured = capsys.readouterr()
    assert "data/bird" in captured.out


def _write_official_zip(archive: Path) -> None:
    """Build a zip shaped like the official bundle: nested dev_databases.zip."""
    inner_dir = archive.parent / "inner"
    db_dir = inner_dir / "dev_databases" / "demo"
    desc = db_dir / "database_description"
    desc.mkdir(parents=True)
    sqlite_path = db_dir / "demo.sqlite"
    connection = sqlite3.connect(sqlite_path)
    connection.execute("CREATE TABLE t (id INTEGER)")
    connection.execute("INSERT INTO t (id) VALUES (1)")
    connection.commit()
    connection.close()
    (desc / "t.csv").write_text(
        "original_column_name,column_name,column_description,data_format,value_description\n"
        "id,id,identifier,integer,\n",
        encoding="utf-8",
    )
    (inner_dir / "dev.json").write_text(
        json.dumps(
            [
                {
                    "question_id": 1,
                    "db_id": "demo",
                    "question": "Count rows",
                    "evidence": "count t",
                    "SQL": "SELECT COUNT(*) FROM t",
                    "difficulty": "simple",
                }
            ]
        ),
        encoding="utf-8",
    )
    (inner_dir / "dev_tables.json").write_text("[]", encoding="utf-8")
    nested = inner_dir / "dev_databases.zip"
    with zipfile.ZipFile(nested, "w") as zipped:
        for path in (inner_dir / "dev_databases").rglob("*"):
            if path.is_file():
                zipped.write(path, path.relative_to(inner_dir).as_posix())
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.write(inner_dir / "dev.json", "dev.json")
        zipped.write(inner_dir / "dev_tables.json", "dev_tables.json")
        zipped.write(nested, "dev_databases.zip")
