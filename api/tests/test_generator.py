"""Tests for the scanning and markdown-generation pipeline.

Run with:  python -m pytest api/tests -q
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.core.languages import language_for, looks_binary
from app.models.schemas import ConvertOptions, PathStyle, SectionMode
from app.services.ignore_rules import IgnoreSet, build_ignore_set
from app.services.markdown_builder import build_markdown
from app.services.scanner import ScanOptions, scan_directory


# ── fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A miniature two-stack repository."""
    (tmp_path / "api/app/core").mkdir(parents=True)
    (tmp_path / "api/app/main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    (tmp_path / "api/app/core/config.py").write_text("DEBUG = True\n")
    (tmp_path / "api/requirements.txt").write_text("fastapi\n")

    (tmp_path / "web/app/components").mkdir(parents=True)
    (tmp_path / "web/app/page.tsx").write_text("export default function Page() {}\n")
    (tmp_path / "web/app/components/Button.tsx").write_text("export const Button = () => null\n")
    (tmp_path / "web/package.json").write_text('{"name":"web"}\n')

    (tmp_path / "README.md").write_text("# Demo\n")
    (tmp_path / ".gitignore").write_text("*.log\nprivate/\n")
    (tmp_path / "api/server.log").write_text("noise\n")
    (tmp_path / "private").mkdir()
    (tmp_path / "private/secret.txt").write_text("hidden\n")
    (tmp_path / "node_modules/left-pad").mkdir(parents=True)
    (tmp_path / "node_modules/left-pad/index.js").write_text("module.exports = 1\n")
    return tmp_path


def generate(root: Path, **overrides) -> str:
    options = ConvertOptions(**overrides)
    ignore_set = build_ignore_set(
        include_hidden=options.include_hidden,
        include_lockfiles=options.include_lockfiles,
        include_tests=options.include_tests,
        extra_globs=options.exclude_globs,
    )
    scan = scan_directory(
        root,
        ScanOptions(
            ignore_set=ignore_set,
            use_gitignore=options.use_gitignore,
            include_extensions=options.include_extensions,
            max_file_bytes=options.max_file_kb * 1024,
            max_lines_per_file=options.max_lines_per_file,
            tree_only=options.include_tree_only,
            collapse_empty_dirs=options.collapse_empty_dirs,
        ),
    )
    return build_markdown(scan, options).markdown


def headings(markdown: str) -> list[str]:
    """Markdown headings only — ignoring '#' lines inside code fences."""
    found, in_fence = [], False
    for line in markdown.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and re.match(r"^#{1,6} ", line):
            found.append(line)
    return found


# ── language detection ──────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "path,expected",
    [
        ("app/main.py", "python"),
        ("web/page.tsx", "tsx"),
        ("web/util.ts", "typescript"),
        ("types/index.d.ts", "typescript"),
        ("Dockerfile", "dockerfile"),
        ("Dockerfile.prod", "dockerfile"),
        ("Makefile", "makefile"),
        (".env.example", "env"),
        ("db/001_init.sql", "sql"),
        ("infra/main.tf", "hcl"),
        ("go.mod", "go"),
        ("unknown.zzz", "text"),
    ],
)
def test_language_detection(path: str, expected: str) -> None:
    assert language_for(path) == expected


def test_binary_sniffing() -> None:
    assert looks_binary(b"\x00\x01\x02binary")
    assert not looks_binary(b"def main():\n    return 1\n")
    assert not looks_binary(b"")


# ── ignore rules ────────────────────────────────────────────────────────────
def test_gitignore_semantics() -> None:
    rules = IgnoreSet.from_patterns(["*.log", "build/", "/root-only.txt", "!keep.log"])
    assert rules.is_ignored("app/server.log", False)
    assert not rules.is_ignored("keep.log", False)
    assert rules.is_ignored("build", True)
    assert not rules.is_ignored("build.py", False)
    assert rules.is_ignored("root-only.txt", False)
    assert not rules.is_ignored("nested/root-only.txt", False)


def test_double_star_matches_any_depth() -> None:
    rules = IgnoreSet.from_patterns(["**/generated/**", "docs/**/*.tmp"])
    assert rules.is_ignored("a/b/generated/file.ts", False)
    assert rules.is_ignored("docs/x/y/note.tmp", False)
    assert not rules.is_ignored("docs/note.md", False)


# ── scanning ────────────────────────────────────────────────────────────────
def test_default_ignores_and_gitignore(project: Path) -> None:
    markdown = generate(project)
    assert "node_modules" not in markdown
    assert "server.log" not in markdown
    assert "secret.txt" not in markdown
    assert "main.py" in markdown


def test_extension_filter(project: Path) -> None:
    markdown = generate(project, include_extensions=[".py"])
    assert "app/main.py" in markdown
    assert "export default function Page" not in markdown


def test_tree_only_mode_omits_content(project: Path) -> None:
    markdown = generate(project, include_tree_only=True)
    assert "## Project Directory Structure" in markdown
    assert "from fastapi import FastAPI" not in markdown


def test_truncation_is_reported(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/big.py").write_text("\n".join(f"x = {i}" for i in range(500)))
    markdown = generate(tmp_path, max_lines_per_file=50)
    assert "Truncated after 50 lines" in markdown
    assert "x = 400" not in markdown


def test_oversized_file_is_skipped_but_listed(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/huge.py").write_text("y = 1\n" * 200_000)
    markdown = generate(tmp_path, max_file_kb=1)
    assert "huge.py" in markdown
    assert "exceeds the size limit" in markdown


# ── document structure ──────────────────────────────────────────────────────
def test_sections_are_detected(project: Path) -> None:
    found = headings(generate(project))
    assert "## Project Directory Structure" in found
    assert "## Backend" in found
    assert "## Frontend" in found
    assert "## Root Files" in found


def test_heading_depth_progression(project: Path) -> None:
    """Directory at depth d → h(d+2); file at depth d → h(d+3), capped at 6."""
    found = headings(generate(project))
    assert "### `/app`" in found                    # depth 1 directory
    assert "##### `app/page.tsx`" in found          # depth 2 file
    assert "#### `/components`" in found            # depth 2 directory
    assert "###### `app/components/Button.tsx`" in found  # depth 3 file


def test_tree_uses_box_drawing_characters(project: Path) -> None:
    markdown = generate(project)
    assert "├── " in markdown
    assert "└── " in markdown
    assert "│   " in markdown


def test_full_path_style(project: Path) -> None:
    markdown = generate(project, path_style=PathStyle.FULL)
    assert "`api/app/main.py`" in markdown


def test_single_section_mode(project: Path) -> None:
    found = headings(generate(project, section_mode=SectionMode.SINGLE))
    assert "## Codebase" in found
    assert "## Backend" not in found


def test_fence_escapes_nested_backticks(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/guide.md").write_text("Intro\n\n```js\nconsole.log(1)\n```\n")
    markdown = generate(tmp_path)
    assert "````markdown" in markdown  # outer fence grew to survive the inner one


def test_generated_document_has_balanced_fences(project: Path) -> None:
    markdown = generate(project)
    opens: list[str] = []
    for line in markdown.splitlines():
        match = re.match(r"^(`{3,})", line)
        if not match:
            continue
        fence = match.group(1)
        if opens and opens[-1] == fence:
            opens.pop()
        else:
            opens.append(fence)
    assert opens == [], "every code fence should be closed"


def test_statistics_section(project: Path) -> None:
    markdown = generate(project)
    assert "## Statistics" in markdown
    assert "**Files included:**" in markdown
    assert "| Language | Files | Lines |" in markdown


def test_custom_preamble_and_title(project: Path) -> None:
    markdown = generate(project, preamble="Snapshot for review.", title="Layout")
    assert markdown.startswith("Snapshot for review.")
    assert "## Layout" in markdown


def test_placeholder_directories_shown_but_not_sectioned(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.py").write_text("x = 1\n")
    (tmp_path / "infra").mkdir()  # truly empty
    (tmp_path / "job").mkdir()
    (tmp_path / "job/.gitkeep").write_text("")  # dotfile-only counts as empty too

    markdown = generate(tmp_path)

    assert "infra/" in markdown and "Placeholder" in markdown
    assert "## Infra" not in markdown
    assert "## Job" not in markdown
    found = headings(markdown)
    assert not any("Infra" in h or "Job" in h for h in found)


def test_directory_emptied_by_filters_respects_collapse(tmp_path: Path) -> None:
    """A directory that's empty only because every file inside it got ignored
    is NOT a placeholder — it should still respect collapse_empty_dirs, and
    should never be mislabeled with the Placeholder note. Uses a directory
    name with no ignore pattern of its own (unlike 'tests/', which is pruned
    as a whole subtree before per-file filtering even runs) so the file
    inside is what triggers the emptiness, not the directory itself.
    """
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs/app.log").write_text("boot ok\n")  # *.log is default-ignored
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.py").write_text("x = 1\n")

    collapsed = generate(tmp_path)
    assert "app.log" not in collapsed
    assert "logs" not in collapsed  # collapsed away by default

    kept = generate(tmp_path, collapse_empty_dirs=False)
    assert "app.log" not in kept  # still not inlined — it's an ignored file
    assert "Placeholder" not in kept  # it's filtered, not a genuine placeholder
    assert "Empty after filtering" in kept

