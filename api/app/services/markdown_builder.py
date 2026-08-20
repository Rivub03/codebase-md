"""Assembles the final markdown document.

Format reproduced (matching the supplied reference):

    <preamble sentence>
    ## Project Directory Structure

    ```
    root/
    ├── api/
    │   └── app/
    ```

    ## Backend

    ```
    ├── api/
    │   └── app/
    ```

    ##### `app/main.py`

    ```python
    ...
    ```

    ### `/core`

    ##### `app/core/config.py`

    ```python
    ...
    ```

Heading levels follow the depth of the entry relative to its section root:

* section root                     → ``##``
* directory at relative depth *d*  → ``#`` × min(d + 2, 6), written ``/name``
* file at relative depth *d*       → ``#`` × min(d + 3, 6), written as a path

Which is exactly the progression the reference uses:
``## Frontend`` → ``### /app`` → ``#### /component`` → ``##### /auth`` →
``###### web/app/component/auth/AuthProvider.tsx``.
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from dataclasses import dataclass

from app.models.schemas import (
    ConversionStats,
    ConvertOptions,
    LanguageStat,
    PathStyle,
    SectionSummary,
)
from app.services.scanner import Node, ScanResult
from app.services.section_planner import Section, plan_sections
from app.services.tree_renderer import render_subtree, render_tree

MAX_HEADING_LEVEL = 6

SKIP_LABELS: dict[str, str] = {
    "binary": "binary file — contents omitted",
    "too-large": "exceeds the size limit — contents omitted",
    "extension": "filtered out by the extension list",
    "tree-only": "tree-only mode — contents omitted",
    "unreadable": "could not be read",
    "ignored": "ignored",
}


def _fence_for(content: str) -> str:
    """Pick a fence long enough to survive backticks inside ``content``.

    A file containing a ``` sequence would otherwise close the block early and
    corrupt the rest of the document.
    """
    longest = 0
    for match in re.finditer(r"`+", content):
        longest = max(longest, len(match.group()))
    return "`" * max(3, longest + 1)


def _heading(level: int, text: str) -> str:
    return f"{'#' * min(level, MAX_HEADING_LEVEL)} {text}"


def _relative_to_section(node: Node, section: Section, style: PathStyle) -> str:
    """Path shown in a file heading."""
    if style is PathStyle.FULL or section.root is None:
        return node.relative_path
    prefix = section.root.relative_path
    if prefix and node.relative_path.startswith(prefix + "/"):
        return node.relative_path[len(prefix) + 1:]
    return node.relative_path


def _depth_within_section(node: Node, section: Section) -> int:
    """How many path segments separate ``node`` from its section root."""
    if section.root is None:
        return 1
    prefix = section.root.relative_path
    remainder = node.relative_path
    if prefix and remainder.startswith(prefix + "/"):
        remainder = remainder[len(prefix) + 1:]
    return len([part for part in remainder.split("/") if part])


@dataclass
class BuildResult:
    markdown: str
    stats: ConversionStats


class MarkdownBuilder:
    """Turns a :class:`ScanResult` into the finished document."""

    def __init__(self, scan: ScanResult, options: ConvertOptions) -> None:
        self.scan = scan
        self.options = options
        self.lines: list[str] = []

    # ── low-level emitters ─────────────────────────────────────────────────
    def _write(self, text: str = "") -> None:
        self.lines.append(text)

    def _blank(self) -> None:
        if self.lines and self.lines[-1] != "":
            self.lines.append("")

    def _code_block(self, content: str, language: str = "") -> None:
        fence = _fence_for(content)
        self._write(f"{fence}{language}")
        self._write(content)
        self._write(fence)

    # ── document parts ─────────────────────────────────────────────────────
    def _emit_preamble(self) -> None:
        preamble = self.options.preamble
        if preamble is None:
            preamble = (
                "This is the current implemented codebase, which will be "
                "updated periodically as the codebase evolves."
            )
        if preamble.strip():
            self._write(preamble.strip())

    def _emit_directory_structure(self) -> None:
        title = self.options.title or "Project Directory Structure"
        self._write(f"## {title}")
        self._blank()
        tree = render_tree(
            self.scan.root,
            root_label=self.scan.root_name,
            annotate=self.options.annotate_tree,
        )
        self._code_block(tree)
        self._blank()

    def _emit_section_tree(self, section: Section) -> None:
        if section.root is None:
            last = len(section.loose_files) - 1
            listing = "\n".join(
                f"{'└── ' if index == last else '├── '}{node.name}"
                for index, node in enumerate(section.loose_files)
            )
        else:
            listing = render_subtree(
                section.root, annotate=self.options.annotate_tree
            )
        if listing.strip():
            self._code_block(listing)
            self._blank()

    def _emit_file(self, node: Node, section: Section, level: int) -> None:
        path = _relative_to_section(node, section, self.options.path_style)
        self._write(_heading(level, f"`{path}`"))
        self._blank()

        if node.content is None:
            reason = SKIP_LABELS.get(node.skipped or "", "contents omitted")
            size_kb = node.size_bytes / 1024
            self._write(f"> _{reason} ({size_kb:,.1f} KB)_")
            self._blank()
            return

        self._code_block(node.content, node.language)

        if node.truncated:
            remaining = node.truncated_at - node.line_count
            self._write(
                f"> _Truncated after {node.line_count:,} lines "
                f"({remaining:,} more in the original file)._"
            )
        self._blank()

    def _emit_directory_walk(self, node: Node, section: Section) -> None:
        """Depth-first walk emitting directory headings then file blocks."""
        files = [child for child in node.children if not child.is_dir]
        directories = [child for child in node.children if child.is_dir]

        for child in files:
            if child.content is None and self.options.include_tree_only:
                continue
            depth = _depth_within_section(child, section)
            self._emit_file(child, section, min(depth + 3, MAX_HEADING_LEVEL))

        for child in directories:
            if not child.has_included_file() and self.options.collapse_empty_dirs:
                continue
            depth = _depth_within_section(child, section)
            self._write(_heading(min(depth + 2, MAX_HEADING_LEVEL), f"`/{child.name}`"))
            self._blank()
            self._emit_directory_walk(child, section)

    def _emit_section(self, section: Section) -> None:
        self._write(f"## {section.name}")
        self._blank()
        self._emit_section_tree(section)

        if self.options.include_tree_only:
            return

        if section.root is None:
            for node in section.loose_files:
                self._emit_file(node, section, 4)
            return

        self._emit_directory_walk(section.root, section)

    def _emit_stats(self, stats: ConversionStats) -> None:
        self._write("## Statistics")
        self._blank()
        self._write(f"- **Files included:** {stats.files_included:,}")
        self._write(f"- **Directories:** {stats.directories:,}")
        self._write(f"- **Lines of code:** {stats.total_lines:,}")
        self._write(f"- **Source size:** {stats.total_bytes / 1024:,.1f} KB")
        if stats.files_skipped_binary:
            self._write(f"- **Binary files skipped:** {stats.files_skipped_binary:,}")
        if stats.files_skipped_too_large:
            self._write(f"- **Oversized files skipped:** {stats.files_skipped_too_large:,}")
        if stats.files_skipped_ignored:
            self._write(f"- **Ignored by rules:** {stats.files_skipped_ignored:,}")
        if stats.files_truncated:
            self._write(f"- **Files truncated:** {stats.files_truncated:,}")
        self._blank()

        if stats.languages:
            self._write("| Language | Files | Lines |")
            self._write("| --- | ---: | ---: |")
            for entry in stats.languages[:15]:
                self._write(
                    f"| {entry.language} | {entry.files:,} | {entry.lines:,} |"
                )
            self._blank()

    # ── public API ─────────────────────────────────────────────────────────
    def build(self) -> BuildResult:
        started = time.perf_counter()

        self._emit_preamble()
        self._blank()
        self._emit_directory_structure()

        sections = plan_sections(self.scan.root, self.options.section_mode)
        for section in sections:
            self._emit_section(section)

        stats = self._collect_stats(sections, started)
        if self.options.include_stats:
            self._emit_stats(stats)

        markdown = "\n".join(self.lines).rstrip() + "\n"
        markdown = re.sub(r"\n{4,}", "\n\n\n", markdown)

        stats.markdown_bytes = len(markdown.encode("utf-8"))
        stats.markdown_lines = markdown.count("\n")
        stats.duration_ms = int((time.perf_counter() - started) * 1000)

        return BuildResult(markdown=markdown, stats=stats)

    def _collect_stats(
        self, sections: list[Section], started: float
    ) -> ConversionStats:
        by_language: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
        for node in self.scan.root.iter_files():
            if node.content is None:
                continue
            bucket = by_language[node.language]
            bucket[0] += 1
            bucket[1] += node.line_count
            bucket[2] += node.size_bytes

        languages = [
            LanguageStat(language=name, files=data[0], lines=data[1], bytes=data[2])
            for name, data in by_language.items()
        ]
        languages.sort(key=lambda entry: entry.lines, reverse=True)

        summaries = [
            SectionSummary(
                name=section.name,
                root=section.root.relative_path if section.root else "/",
                files=sum(1 for f in section.files() if f.content is not None),
                lines=sum(f.line_count for f in section.files()),
            )
            for section in sections
        ]

        return ConversionStats(
            root_name=self.scan.root_name,
            total_files_seen=self.scan.files_seen,
            files_included=self.scan.files_included,
            files_skipped_binary=self.scan.skipped_binary,
            files_skipped_ignored=self.scan.skipped_ignored,
            files_skipped_too_large=self.scan.skipped_too_large,
            files_truncated=self.scan.truncated,
            directories=self.scan.directories,
            total_lines=self.scan.total_lines,
            total_bytes=self.scan.total_bytes,
            markdown_bytes=0,
            markdown_lines=0,
            duration_ms=int((time.perf_counter() - started) * 1000),
            languages=languages,
            sections=summaries,
        )


def build_markdown(scan: ScanResult, options: ConvertOptions) -> BuildResult:
    return MarkdownBuilder(scan, options).build()
