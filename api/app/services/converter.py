"""Orchestrates a single conversion, publishing progress as it goes."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from app.core.config import settings
from app.models.schemas import ConvertOptions, ProgressEvent
from app.services.ignore_rules import build_ignore_set
from app.services.job_store import Job
from app.services.markdown_builder import build_markdown
from app.services.scanner import ScanOptions, scan_directory
from app.services.tree_renderer import tree_lines_for_stream

logger = logging.getLogger(__name__)

# Progress is split across the three phases so the bar moves at a believable rate.
SCAN_SHARE = 0.70
BUILD_SHARE = 0.25


def safe_filename(label: str) -> str:
    """Turn a source label into a download-safe ``.md`` filename."""
    cleaned = re.sub(r"[^\w.\-]+", "-", label).strip("-_.") or "codebase"
    return f"{cleaned[:80]}.md"


def _emit(job: Job, loop: asyncio.AbstractEventLoop, event: ProgressEvent) -> None:
    """Publish from the worker thread onto the event loop that owns the queues."""
    loop.call_soon_threadsafe(job.publish, event)


def run_conversion(
    job: Job,
    root: Path,
    options: ConvertOptions,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Blocking conversion body — executed in a worker thread."""
    try:
        job.status = "running"
        job.message = "Reading the directory tree"
        _emit(job, loop, ProgressEvent(
            type="status", message="Reading the directory tree", progress=0.02
        ))

        ignore_set = build_ignore_set(
            include_hidden=options.include_hidden,
            include_lockfiles=options.include_lockfiles,
            include_tests=options.include_tests,
            extra_globs=options.exclude_globs,
        )

        scan_options = ScanOptions(
            ignore_set=ignore_set,
            use_gitignore=options.use_gitignore,
            include_extensions=options.include_extensions,
            max_file_bytes=min(options.max_file_kb, settings.max_file_kb_ceiling) * 1024,
            max_lines_per_file=options.max_lines_per_file,
            truncate_long_files=options.truncate_long_files,
            tree_only=options.include_tree_only,
            max_files=settings.max_files,
            collapse_empty_dirs=options.collapse_empty_dirs,
        )

        seen = 0
        # Files-per-progress-tick. Recalculated implicitly: we do not know the
        # total up front, so the bar approaches SCAN_SHARE asymptotically.
        def on_progress(relative_path: str, kind: str) -> None:
            nonlocal seen
            seen += 1
            if kind == "file" and seen % 5 != 0 and seen > 20:
                return
            fraction = SCAN_SHARE * (1 - 1 / (1 + seen / 120))
            _emit(job, loop, ProgressEvent(
                type="file",
                message=relative_path,
                progress=round(fraction, 4),
                payload={"path": relative_path, "kind": kind},
            ))

        scan = scan_directory(root, scan_options, on_progress=on_progress)

        if scan.files_included == 0 and scan.files_seen == 0:
            raise ValueError(
                "No readable files found. Check the path, or loosen the filters "
                "under Options."
            )

        _emit(job, loop, ProgressEvent(
            type="tree",
            message="Directory tree resolved",
            progress=SCAN_SHARE,
            payload={"lines": tree_lines_for_stream(scan.root, limit=600)},
        ))

        job.message = "Writing the document"
        _emit(job, loop, ProgressEvent(
            type="status",
            message="Writing the document",
            progress=SCAN_SHARE + BUILD_SHARE / 2,
        ))

        result = build_markdown(scan, options)

        job.markdown = result.markdown
        job.stats = result.stats
        job.filename = safe_filename(job.source_label or scan.root_name)
        job.status = "done"
        job.progress = 1.0
        job.message = "Document ready"

        _emit(job, loop, ProgressEvent(
            type="done",
            message="Document ready",
            progress=1.0,
            payload={
                "stats": result.stats.model_dump(),
                "filename": job.filename,
                "preview": result.markdown[:4000],
            },
        ))

        if scan.hit_file_cap:
            logger.warning("Job %s hit the file cap of %d", job.job_id, settings.max_files)

    except Exception as exc:  # noqa: BLE001 — surfaced to the client verbatim
        logger.exception("Conversion failed for job %s", job.job_id)
        job.status = "error"
        job.error = str(exc) or exc.__class__.__name__
        job.message = "Conversion failed"
        _emit(job, loop, ProgressEvent(
            type="error", message=job.error, progress=1.0
        ))
    finally:
        import time

        job.finished_at = time.time()
        job.cleanup_workspace()
