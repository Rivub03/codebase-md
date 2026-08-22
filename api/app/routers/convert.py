"""Endpoints that start a conversion."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from app.core.config import settings
from app.models.schemas import (
    ConvertOptions,
    JobCreated,
    PathConvertRequest,
    RemoteConvertRequest,
)
from app.services.archive import ArchiveError, extract_archive
from app.services.converter import run_conversion
from app.services.github import RemoteFetchError, download_repository
from app.services.job_store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/convert", tags=["convert"])

CHUNK = 1 << 20  # 1 MB


def _normalize_path(path_str: str) -> str:
    """
    Normalize a path string for cross-platform compatibility.
    
    Handles Windows paths with backslashes and converts them to forward slashes
    for consistent processing across Linux and Windows.
    
    Note: When running in Docker, Windows absolute paths (e.g., A:\path\to\dir)
    must be mapped as volumes. Use the container path instead (e.g., /mnt/windows-repos).
    """
    # Convert backslashes to forward slashes (Windows path normalization)
    normalized = path_str.replace("\\", "/")
    return normalized


def _validate_windows_path_usage(path_str: str) -> str:
    """
    Check if a Windows absolute path was provided and return helpful guidance.
    
    Returns an error message if the path looks like a Windows drive letter path,
    since those need to be mounted as Docker volumes first.
    """
    normalized = path_str.replace("\\", "/")
    
    # Check for Windows drive letter pattern (e.g., A:, C:, etc.)
    if len(normalized) >= 2 and normalized[1] == ':':
        drive_letter = normalized[0].upper()
        # Map common drive letters to their likely mount points
        mount_point = f"/mnt/{drive_letter.lower()}"
        
        # Extract the path without the drive letter
        remainder = normalized[2:].lstrip('/')
        suggested_path = f"{mount_point}/{remainder}"
        
        return (
            f"Windows absolute paths (like {path_str}) cannot be accessed directly in Docker. "
            f"The Windows {drive_letter}: drive needs to be mounted as a volume. "
            f"Try using the container path instead: {suggested_path}"
        )
    
    return ""


def _start(job, root: Path, options: ConvertOptions, tasks: BackgroundTasks) -> None:
    loop = asyncio.get_running_loop()
    tasks.add_task(
        asyncio.to_thread, run_conversion, job, root, options, loop
    )


def _parse_options(raw: str | None) -> ConvertOptions:
    if not raw:
        return ConvertOptions()
    try:
        return ConvertOptions.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(422, f"Invalid options: {exc}") from exc


@router.post("/upload", response_model=JobCreated)
async def convert_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="A .zip or .tar archive of the codebase."),
    options: str | None = Form(default=None, description="JSON-encoded ConvertOptions."),
) -> JobCreated:
    """Convert an uploaded archive."""
    parsed = _parse_options(options)
    name = Path(file.filename or "upload.zip").name
    label = Path(name).stem or "codebase"

    job = store.create(label)
    workspace = settings.work_dir / job.job_id
    workspace.mkdir(parents=True, exist_ok=True)
    job.workspace = workspace

    archive_path = workspace / name
    limit = settings.max_archive_mb * 1024 * 1024
    written = 0

    try:
        with open(archive_path, "wb") as handle:
            while chunk := await file.read(CHUNK):
                written += len(chunk)
                if written > limit:
                    raise HTTPException(
                        413,
                        f"Archive is larger than {settings.max_archive_mb} MB.",
                    )
                handle.write(chunk)

        if written == 0:
            raise HTTPException(400, "The uploaded file is empty.")

        root = extract_archive(
            archive_path,
            workspace / "extracted",
            settings.max_extracted_mb * 1024 * 1024,
        )
    except ArchiveError as exc:
        store.delete(job.job_id)
        raise HTTPException(400, str(exc)) from exc
    except HTTPException:
        store.delete(job.job_id)
        raise
    finally:
        await file.close()

    _start(job, root, parsed, background_tasks)
    return JobCreated(job_id=job.job_id, status="queued", source_label=label)


@router.post("/path", response_model=JobCreated)
async def convert_path(
    payload: PathConvertRequest, background_tasks: BackgroundTasks
) -> JobCreated:
    """Convert a directory that already exists on the server's filesystem."""
    if not settings.allow_local_path:
        raise HTTPException(403, "Reading local paths is disabled on this server.")

    # Normalize the path to handle Windows backslashes
    normalized_path = _normalize_path(payload.path)
    
    # Check if this looks like a Windows absolute path and provide helpful guidance
    windows_path_error = _validate_windows_path_usage(normalized_path)
    
    root = Path(normalized_path).expanduser().resolve()

    try:
        if not root.exists():
            # If the path doesn't exist and looks like a Windows path, provide better guidance
            if windows_path_error:
                raise HTTPException(400, windows_path_error)
            raise HTTPException(404, f"Path not found: {payload.path}")
        if not root.is_dir():
            raise HTTPException(400, "That path is a file. Point at a directory instead.")
    except PermissionError as exc:
        raise HTTPException(403, f"Permission denied accessing: {payload.path}") from exc

    if settings.local_path_roots:
        allowed = [Path(p).expanduser().resolve() for p in settings.local_path_roots]
        if not any(root == base or base in root.parents for base in allowed):
            raise HTTPException(
                403, "That directory is outside the allowed roots for this server."
            )

    job = store.create(root.name)
    _start(job, root, payload.options, background_tasks)
    return JobCreated(job_id=job.job_id, status="queued", source_label=root.name)


@router.post("/remote", response_model=JobCreated)
async def convert_remote(
    payload: RemoteConvertRequest, background_tasks: BackgroundTasks
) -> JobCreated:
    """Convert a public GitHub repository."""
    if not settings.allow_remote_fetch:
        raise HTTPException(403, "Remote fetching is disabled on this server.")

    job = store.create(payload.url.rstrip("/").split("/")[-1] or "repository")
    workspace = settings.work_dir / job.job_id
    workspace.mkdir(parents=True, exist_ok=True)
    job.workspace = workspace

    try:
        archive_path, label = await asyncio.to_thread(
            download_repository, payload.url, payload.ref, workspace / "repo.zip"
        )
        job.source_label = label.replace("/", "-")
        root = extract_archive(
            archive_path,
            workspace / "extracted",
            settings.max_extracted_mb * 1024 * 1024,
        )
    except (RemoteFetchError, ArchiveError) as exc:
        store.delete(job.job_id)
        raise HTTPException(400, str(exc)) from exc

    _start(job, root, payload.options, background_tasks)
    return JobCreated(
        job_id=job.job_id, status="queued", source_label=job.source_label
    )
