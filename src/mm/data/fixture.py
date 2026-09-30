"""The committed tiny database, loaded through the BIRD layout loader."""

from pathlib import Path

from mm.data.bird import Dataset, load_bird_layout
from mm.paths import repo_root


def fixture_root() -> Path:
    """Return ``tests/fixtures/tiny_db``."""
    return repo_root() / "tests" / "fixtures" / "tiny_db"


def load_fixture() -> Dataset:
    """Load the hand-made fixture with the same loader used for BIRD."""
    return load_bird_layout(fixture_root())
