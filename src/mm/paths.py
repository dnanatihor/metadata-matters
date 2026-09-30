"""Locate the repository root from an installed or source checkout."""

from pathlib import Path


def repo_root() -> Path:
    """Return the directory that contains ``pyproject.toml`` and ``src/mm``."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src" / "mm").is_dir():
            return parent
    message = "Could not find the metadata-matters repository root from " + str(here)
    raise FileNotFoundError(message)
