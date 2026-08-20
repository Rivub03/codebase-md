"""In-memory job registry.

A conversion runs in a worker thread while the request that started it returns
immediately with a job id. Progress is published to an asyncio queue per job so
the browser can stream it over server-sent events. Jobs age out on a TTL, and
the oldest are evicted once the registry is full, so a long-running server does
not accumulate megabytes of finished documents.
"""

from __future__ import annotations

import asyncio
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.models.schemas import ConversionStats, ProgressEvent


@dataclass
class Job:
    job_id: str
    source_label: str
    status: str = "queued"
    progress: float = 0.0
    message: str = "Queued"
    error: str | None = None
    markdown: str | None = None
    stats: ConversionStats | None = None
    filename: str | None = None
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    workspace: Path | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    _queues: list[asyncio.Queue] = field(default_factory=list)

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        # Replay everything already emitted so a late subscriber sees the
        # full history rather than joining mid-stream.
        for event in self.events:
            queue.put_nowait(event)
        self._queues.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._queues:
            self._queues.remove(queue)

    def publish(self, event: ProgressEvent) -> None:
        payload = event.model_dump()
        # Keep the replay buffer bounded; per-file events dominate the volume.
        if len(self.events) < 5000:
            self.events.append(payload)
        for queue in list(self._queues):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    def cleanup_workspace(self) -> None:
        if self.workspace and self.workspace.exists():
            shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace = None


class JobStore:
    """Registry of conversions, keyed by job id."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    def create(self, source_label: str) -> Job:
        self._sweep()
        job = Job(job_id=uuid.uuid4().hex[:16], source_label=source_label)
        self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        if self._is_expired(job):
            self.delete(job_id)
            return None
        return job

    def delete(self, job_id: str) -> None:
        job = self._jobs.pop(job_id, None)
        if job:
            job.cleanup_workspace()

    def all(self) -> list[Job]:
        self._sweep()
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def _is_expired(self, job: Job) -> bool:
        return (time.time() - job.created_at) > settings.job_ttl_seconds

    def _sweep(self) -> None:
        for job_id in [jid for jid, job in self._jobs.items() if self._is_expired(job)]:
            self.delete(job_id)

        while len(self._jobs) >= settings.max_jobs:
            oldest = min(self._jobs.values(), key=lambda j: j.created_at)
            self.delete(oldest.job_id)


store = JobStore()
