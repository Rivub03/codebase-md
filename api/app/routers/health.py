"""Health and capability reporting."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@router.get("/capabilities")
async def capabilities() -> dict[str, object]:
    """What this deployment allows — the UI hides controls it cannot use."""
    return {
        "allow_local_path": settings.allow_local_path,
        "allow_remote_fetch": settings.allow_remote_fetch,
        "max_archive_mb": settings.max_archive_mb,
        "max_files": settings.max_files,
        "max_file_kb_default": settings.max_file_kb_default,
        "max_file_kb_ceiling": settings.max_file_kb_ceiling,
        "has_github_token": bool(settings.github_token),
    }
