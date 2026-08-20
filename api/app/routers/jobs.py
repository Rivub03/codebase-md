"""Endpoints for reading a conversion's progress and result."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, Response, StreamingResponse

from app.models.schemas import JobStatus
from app.services.job_store import store

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Sent every 15 s so proxies do not close an idle stream.
HEARTBEAT_SECONDS = 15


def _to_status(job) -> JobStatus:
    return JobStatus(
        job_id=job.job_id,
        status=job.status,  # type: ignore[arg-type]
        source_label=job.source_label,
        created_at=job.created_at,
        finished_at=job.finished_at,
        progress=job.progress,
        message=job.message,
        error=job.error,
        stats=job.stats,
        filename=job.filename,
    )


def _require(job_id: str):
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "That job has expired or never existed.")
    return job


@router.get("", response_model=list[JobStatus])
async def list_jobs() -> list[JobStatus]:
    """Recent conversions, newest first."""
    return [_to_status(job) for job in store.all()]


@router.get("/{job_id}", response_model=JobStatus)
async def get_job(job_id: str) -> JobStatus:
    return _to_status(_require(job_id))


@router.get("/{job_id}/events")
async def stream_events(job_id: str) -> StreamingResponse:
    """Server-sent events carrying scan progress, then the final result."""
    job = _require(job_id)
    queue = job.subscribe()

    async def generator() -> AsyncIterator[str]:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=HEARTBEAT_SECONDS
                    )
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    if job.status in {"done", "error"}:
                        break
                    continue

                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in {"done", "error"}:
                    break
        finally:
            job.unsubscribe(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{job_id}/markdown", response_class=PlainTextResponse)
async def get_markdown(job_id: str) -> PlainTextResponse:
    """The generated document as plain text."""
    job = _require(job_id)
    if job.status == "error":
        raise HTTPException(409, job.error or "Conversion failed.")
    if job.markdown is None:
        raise HTTPException(409, "Still converting. Try again in a moment.")
    return PlainTextResponse(job.markdown, media_type="text/markdown; charset=utf-8")


@router.get("/{job_id}/download")
async def download_markdown(job_id: str) -> Response:
    """The generated document as a file attachment."""
    job = _require(job_id)
    if job.markdown is None:
        raise HTTPException(409, "Still converting. Try again in a moment.")
    filename = job.filename or "codebase.md"
    return Response(
        content=job.markdown.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: str) -> Response:
    _require(job_id)
    store.delete(job_id)
    return Response(status_code=204)
