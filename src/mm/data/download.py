"""Fetch the public BIRD dev zip and expand it into the layout the loader reads.

The dataset is never committed. ``data/bird/`` is gitignored. Confirm BIRD's
licence at https://bird-bench.github.io/ before publishing results that use it.

The SHA-256 below is the published checksum of the 2024-06-27 official
``dev.zip`` (the bundle that contains ``dev.json`` and a nested
``dev_databases.zip``).
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

from mm.paths import repo_root

DEV_ZIP_URL = "https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip"
DEV_ZIP_SHA256 = "cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630"
LICENCE_NOTICE = (
    "BIRD dev is downloaded separately and is not part of this repository. "
    "Confirm the dataset licence at https://bird-bench.github.io/ before "
    "publishing results that use it. Do not commit the downloaded files."
)

Fetcher = Callable[[str, Path], None]


class ChecksumMismatchError(Exception):
    """The downloaded archive does not match the pinned SHA-256."""


class UnsafeZipError(ValueError):
    """A zip member would extract outside the destination directory."""


def default_dest() -> Path:
    """Return the gitignored BIRD directory for this checkout."""
    return repo_root() / "data" / "bird"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if chunk == b"":
                break
            digest.update(chunk)
    return digest.hexdigest()


def download(
    dest: Path,
    *,
    url: str = DEV_ZIP_URL,
    expected_sha256: str = DEV_ZIP_SHA256,
    fetcher: Fetcher | None = None,
) -> Path:
    """Download ``url``, check ``expected_sha256``, and extract into ``dest``.

    ``fetcher`` defaults to an HTTP GET. Tests pass a local writer so no
    network is used.
    """
    if dest.exists() and any(dest.iterdir()):
        message = f"Destination is not empty: {dest}"
        raise FileExistsError(message)
    fetch = fetcher if fetcher is not None else _urllib_fetch
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "dev.zip"
        fetch(url, archive)
        actual = file_sha256(archive)
        if actual != expected_sha256:
            message = f"SHA-256 mismatch for {url}: expected {expected_sha256}, got {actual}"
            raise ChecksumMismatchError(message)
        return extract_bird_dev(archive, dest)


def extract_bird_dev(archive: Path, dest: Path) -> Path:
    """Expand an official ``dev.zip`` into ``dest/dev.json`` and ``dev_databases/``.

    The official bundle nests the databases in ``dev_databases.zip``. That
    inner archive is expanded before the layout is copied into ``dest``.
    """
    if dest.exists() and any(dest.iterdir()):
        message = f"Destination is not empty: {dest}"
        raise FileExistsError(message)
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw"
        _safe_extract(archive, raw)
        source = _find_dev_root(raw)
        nested = source / "dev_databases.zip"
        if nested.is_file():
            _safe_extract(nested, source)
        dev_json = source / "dev.json"
        databases = source / "dev_databases"
        if not dev_json.is_file() or not databases.is_dir():
            message = f"Archive is not a BIRD dev bundle: {archive}"
            raise FileNotFoundError(message)
        shutil.copy2(dev_json, dest / "dev.json")
        shutil.copytree(databases, dest / "dev_databases")
        tables = source / "dev_tables.json"
        if tables.is_file():
            shutil.copy2(tables, dest / "dev_tables.json")
    return dest


def main(argv: list[str] | None = None) -> int:
    """CLI for ``scripts/download_bird.py``."""
    import argparse

    parser = argparse.ArgumentParser(description="Download the BIRD dev set into data/bird.")
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="Directory to write (default: data/bird under the repository root).",
    )
    args = parser.parse_args(argv)
    dest = default_dest() if args.dest is None else args.dest
    print(LICENCE_NOTICE)
    download(dest)
    print(f"Wrote BIRD dev layout to {dest}")
    return 0


def _urllib_fetch(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=120) as response, dest.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _find_dev_root(raw: Path) -> Path:
    if (raw / "dev.json").is_file():
        return raw
    candidates = [path for path in raw.iterdir() if path.is_dir() and (path / "dev.json").is_file()]
    if len(candidates) == 1:
        return candidates[0]
    message = f"dev.json not found in extracted archive under {raw}"
    raise FileNotFoundError(message)


def _safe_extract(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    with zipfile.ZipFile(archive) as zipped:
        for info in zipped.infolist():
            target = _member_target(root, info.filename)
            if info.is_dir() or info.filename.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(info, "r") as source, target.open("wb") as handle:
                shutil.copyfileobj(source, handle)


def _member_target(root: Path, name: str) -> Path:
    parts = Path(name).parts
    if not parts or Path(name).is_absolute() or ".." in parts:
        message = f"zip member escapes destination: {name}"
        raise UnsafeZipError(message)
    target = root.joinpath(*parts).resolve()
    if not target.is_relative_to(root):
        message = f"zip member escapes destination: {name}"
        raise UnsafeZipError(message)
    return target
