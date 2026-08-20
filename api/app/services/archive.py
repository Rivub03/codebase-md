"""Archive extraction with the usual traps closed off.

Uploaded archives are untrusted input. Three things are guarded here: path
traversal ("zip slip"), decompression bombs, and archives that wrap everything
in a single top-level folder (which would otherwise show up as a pointless
extra level in the tree).
"""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path


class ArchiveError(Exception):
    """Raised when an archive cannot be safely extracted."""


def _is_within(base: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _check_zip_budget(archive: zipfile.ZipFile, max_bytes: int) -> None:
    total = sum(info.file_size for info in archive.infolist())
    if total > max_bytes:
        raise ArchiveError(
            f"Archive expands to {total / 1024 / 1024:,.0f} MB, over the "
            f"{max_bytes / 1024 / 1024:,.0f} MB limit."
        )


def extract_zip(source: Path, destination: Path, max_bytes: int) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(source) as archive:
            _check_zip_budget(archive, max_bytes)
            for info in archive.infolist():
                name = info.filename
                if name.startswith("/") or ".." in Path(name).parts:
                    continue
                target = destination / name
                if not _is_within(destination, target):
                    continue
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, open(target, "wb") as dst:
                    dst.write(src.read())
    except zipfile.BadZipFile as exc:
        raise ArchiveError("That file is not a readable .zip archive.") from exc

    return collapse_single_root(destination)


def extract_tar(source: Path, destination: Path, max_bytes: int) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(source) as archive:
            total = 0
            members = []
            for member in archive.getmembers():
                if member.issym() or member.islnk():
                    continue
                if member.name.startswith("/") or ".." in Path(member.name).parts:
                    continue
                target = destination / member.name
                if not _is_within(destination, target):
                    continue
                total += member.size
                if total > max_bytes:
                    raise ArchiveError(
                        f"Archive expands past the "
                        f"{max_bytes / 1024 / 1024:,.0f} MB limit."
                    )
                members.append(member)
            archive.extractall(destination, members=members)
    except tarfile.TarError as exc:
        raise ArchiveError("That file is not a readable tar archive.") from exc

    return collapse_single_root(destination)


def extract_archive(source: Path, destination: Path, max_bytes: int) -> Path:
    """Dispatch on the archive's suffix."""
    name = source.name.lower()
    if name.endswith(".zip"):
        return extract_zip(source, destination, max_bytes)
    if name.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz")):
        return extract_tar(source, destination, max_bytes)
    raise ArchiveError(
        "Unsupported archive format. Upload a .zip, .tar, .tar.gz, or .tar.xz file."
    )


def collapse_single_root(directory: Path) -> Path:
    """Descend through wrapper folders like ``repo-main/``.

    GitHub archives and most hand-made zips nest the project one level down.
    Keeping that level would put a meaningless directory at the top of every
    generated tree.
    """
    current = directory
    for _ in range(4):
        entries = [item for item in current.iterdir() if item.name != "__MACOSX"]
        if len(entries) == 1 and entries[0].is_dir():
            current = entries[0]
            continue
        break
    return current
