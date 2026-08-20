"""Walks a directory into an in-memory tree of :class:`Node` objects.

The scanner makes every include/exclude decision and reads every byte it is
going to need, so the writers downstream deal only with resolved data. Skipped
files stay in the tree (flagged) because the directory structure is more honest
when it shows what exists, even where the contents are omitted.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

from app.core.languages import (
    is_probably_binary_name,
    language_for,
    looks_binary,
)
from app.services.ignore_rules import IgnoreSet

SkipReason = str  # "ignored" | "binary" | "too-large" | "extension" | "unreadable"


@dataclass
class Node:
    """One entry in the scanned tree."""

    name: str
    relative_path: str          # posix, relative to the scan root
    is_dir: bool
    size_bytes: int = 0
    children: list["Node"] = field(default_factory=list)

    # File-only fields.
    content: str | None = None
    language: str = "text"
    line_count: int = 0
    truncated: bool = False
    truncated_at: int = 0
    skipped: SkipReason | None = None

    # Directory-only: true when the directory had zero entries on disk (not
    # merely zero entries after filtering). Drives the "← Placeholder" note.
    empty_on_disk: bool = False

    @property
    def depth(self) -> int:
        return len(self.relative_path.split("/")) if self.relative_path else 0

    def iter_files(self) -> Iterator["Node"]:
        for child in self.children:
            if child.is_dir:
                yield from child.iter_files()
            else:
                yield child

    def iter_dirs(self) -> Iterator["Node"]:
        for child in self.children:
            if child.is_dir:
                yield child
                yield from child.iter_dirs()

    def has_included_file(self) -> bool:
        """True when this subtree contains at least one file with content."""
        return any(f.content is not None for f in self.iter_files())


@dataclass
class ScanResult:
    root: Node
    root_name: str
    files_seen: int = 0
    files_included: int = 0
    skipped_binary: int = 0
    skipped_ignored: int = 0
    skipped_too_large: int = 0
    truncated: int = 0
    directories: int = 0
    total_lines: int = 0
    total_bytes: int = 0
    hit_file_cap: bool = False


@dataclass
class ScanOptions:
    ignore_set: IgnoreSet
    use_gitignore: bool = True
    include_extensions: list[str] = field(default_factory=list)
    max_file_bytes: int = 400 * 1024
    max_lines_per_file: int = 4000
    truncate_long_files: bool = True
    tree_only: bool = False
    max_files: int = 8000
    collapse_empty_dirs: bool = True


def _looks_like_placeholder(path: Path) -> bool:
    """A directory is a placeholder if it has nothing but marker dotfiles.

    An empty directory can't be committed to git, so the common way to keep
    one around on purpose is a lone ``.gitkeep``. That should read the same
    as a truly empty directory — both are "nothing here yet" — rather than
    being treated as content that got filtered out.
    """
    try:
        entries = list(os.scandir(path))
    except OSError:
        return False
    return all(entry.name.startswith(".") for entry in entries)


def _read_text(path: Path, max_bytes: int) -> tuple[str | None, SkipReason | None]:
    """Read a file as text, or report why it could not be inlined."""
    try:
        size = path.stat().st_size
    except OSError:
        return None, "unreadable"

    if size > max_bytes:
        return None, "too-large"

    try:
        raw = path.read_bytes()
    except OSError:
        return None, "unreadable"

    if looks_binary(raw[:4096]):
        return None, "binary"

    for encoding in ("utf-8", "utf-8-sig", "utf-16", "latin-1"):
        try:
            return raw.decode(encoding), None
        except (UnicodeDecodeError, LookupError):
            continue

    return None, "binary"


def _sort_key(entry: os.DirEntry[str]) -> tuple[int, str]:
    """Directories first, then files, each alphabetical and case-insensitive."""
    return (0 if entry.is_dir(follow_symlinks=False) else 1, entry.name.lower())


def scan_directory(
    root: Path,
    options: ScanOptions,
    *,
    on_progress: Callable[[str, str], None] | None = None,
) -> ScanResult:
    """Walk ``root`` and return the populated tree.

    ``on_progress`` is invoked as ``(relative_path, kind)`` for each entry so a
    caller can stream the scan to a client while it happens.
    """
    root = root.resolve()
    root_node = Node(name=root.name or "codebase", relative_path="", is_dir=True)
    result = ScanResult(root=root_node, root_name=root_node.name)

    # .gitignore contents discovered along the way, keyed by the directory they
    # sit in. Merged into a single stack because rules apply to subtrees.
    active_ignores = options.ignore_set

    if options.use_gitignore:
        collected = IgnoreSet(rules=list(active_ignores.rules))
        for gitignore in sorted(root.rglob(".gitignore")):
            try:
                relative_dir = gitignore.parent.relative_to(root).as_posix()
            except ValueError:
                continue
            if relative_dir == ".":
                relative_dir = ""
            # Skip .gitignore files that live inside already-ignored trees.
            if relative_dir and active_ignores.is_ignored(relative_dir, True):
                continue
            try:
                collected.extend_from_text(
                    gitignore.read_text(encoding="utf-8", errors="replace"),
                    base_dir=relative_dir,
                )
            except OSError:
                continue
        active_ignores = collected

    allowed_extensions = {ext.lower() for ext in options.include_extensions}

    def walk(directory: Path, parent: Node) -> None:
        if result.files_seen >= options.max_files:
            result.hit_file_cap = True
            return

        try:
            entries = sorted(os.scandir(directory), key=_sort_key)
        except OSError:
            return

        for entry in entries:
            if result.files_seen >= options.max_files:
                result.hit_file_cap = True
                return

            # Never follow symlinks — they invite cycles and escape the root.
            if entry.is_symlink():
                continue

            entry_path = Path(entry.path)
            try:
                relative = entry_path.relative_to(root).as_posix()
            except ValueError:
                continue

            is_dir = entry.is_dir(follow_symlinks=False)

            if active_ignores.is_ignored(relative, is_dir):
                if not is_dir:
                    result.files_seen += 1
                    result.skipped_ignored += 1
                continue

            if is_dir:
                child = Node(
                    name=entry.name, relative_path=relative, is_dir=True
                )
                # A directory with literally nothing in it on disk is a
                # placeholder the author left on purpose — always shown,
                # regardless of collapse_empty_dirs. A directory that only
                # *ends up* empty because every entry inside it was filtered
                # (ignored, wrong extension, tests excluded, …) is different:
                # that emptiness is an artifact of the options chosen for this
                # run, so it still respects collapse_empty_dirs like before.
                try:
                    disk_is_empty = _looks_like_placeholder(entry_path)
                except OSError:
                    disk_is_empty = False

                walk(entry_path, child)
                if not child.children and not disk_is_empty:
                    if options.collapse_empty_dirs:
                        continue
                if not child.children:
                    child.empty_on_disk = disk_is_empty
                parent.children.append(child)
                result.directories += 1
                if on_progress:
                    on_progress(relative + "/", "dir")
                continue

            # ── File ────────────────────────────────────────────────────────
            result.files_seen += 1
            try:
                size = entry.stat(follow_symlinks=False).st_size
            except OSError:
                size = 0

            node = Node(
                name=entry.name,
                relative_path=relative,
                is_dir=False,
                size_bytes=size,
                language=language_for(relative),
            )

            suffix = entry_path.suffix.lower()
            if allowed_extensions and suffix not in allowed_extensions:
                node.skipped = "extension"
                result.skipped_ignored += 1
            elif options.tree_only:
                node.skipped = "tree-only"
            elif is_probably_binary_name(relative):
                node.skipped = "binary"
                result.skipped_binary += 1
            else:
                text, reason = _read_text(entry_path, options.max_file_bytes)
                if reason == "too-large":
                    node.skipped = "too-large"
                    result.skipped_too_large += 1
                elif reason is not None:
                    node.skipped = reason
                    result.skipped_binary += 1
                elif text is not None:
                    lines = text.splitlines()
                    if (
                        options.truncate_long_files
                        and len(lines) > options.max_lines_per_file
                    ):
                        node.truncated = True
                        node.truncated_at = len(lines)
                        lines = lines[: options.max_lines_per_file]
                        result.truncated += 1
                    node.content = "\n".join(lines)
                    node.line_count = len(lines)
                    result.files_included += 1
                    result.total_lines += node.line_count
                    result.total_bytes += size

            parent.children.append(node)
            if on_progress:
                on_progress(relative, "file")

    walk(root, root_node)
    return result
