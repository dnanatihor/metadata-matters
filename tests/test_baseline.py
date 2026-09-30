"""Phase 0 repository baseline from SPEC.md Appendix B.1 and the §3 layout."""

from __future__ import annotations

from mm.paths import repo_root

LAYOUT = (
    "configs/rq1.yaml",
    "configs/rq2.yaml",
    "configs/rq3.yaml",
    "configs/rq4.yaml",
    "configs/models.yaml",
    "configs/prices.yaml",
    "prompts/text_to_sql.v1.md",
    "templates/embedding/t0.j2",
    "templates/embedding/t1.j2",
    "templates/embedding/t2.j2",
    "templates/embedding/t3.j2",
    "templates/embedding/t4.j2",
    "scripts/download_bird.py",
    "src/mm/data/bird.py",
    "src/mm/data/fixture.py",
    "src/mm/context/ddl.py",
    "src/mm/context/levels.py",
    "src/mm/decoys.py",
    "src/mm/llm/runner.py",
    "src/mm/llm/cache.py",
    "src/mm/llm/budget.py",
    "src/mm/llm/extract_sql.py",
    "src/mm/evaluate/execution.py",
    "src/mm/evaluate/relevance.py",
    "src/mm/evaluate/retrieval_metrics.py",
    "src/mm/evaluate/stats.py",
    "src/mm/retrieval/corpus.py",
    "src/mm/retrieval/embed.py",
    "src/mm/retrieval/index.py",
    "src/mm/report/tables.py",
    "src/mm/report/plots.py",
    "src/mm/report/readme.py",
    "src/mm/cli.py",
    "pyproject.toml",
    ".pre-commit-config.yaml",
    ".github/workflows/ci.yml",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    ".gitignore",
    "docs/adr/0000-template.md",
)


def test_layout_paths_exist() -> None:
    root = repo_root()
    missing = [relative for relative in LAYOUT if not (root / relative).is_file()]
    assert missing == []


def test_readme_stub_has_required_sections() -> None:
    text = (repo_root() / "README.md").read_text(encoding="utf-8")
    assert text.startswith("# Metadata Matters — ")
    assert "## Why" in text
    assert "## Quickstart" in text
    assert "ci.yml" in text
    changelog = (repo_root() / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [Unreleased]" in changelog


def test_ci_workflow_runs_tooling() -> None:
    text = (repo_root() / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "uv sync --frozen" in text
    assert "ruff check" in text
    assert "ruff format --check" in text
    assert "mypy src" in text
    assert "pytest" in text
