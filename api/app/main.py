"""Application entrypoint: ``uvicorn app.main:app``."""

from __future__ import annotations

import logging
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routers import convert, health, jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("codebase-to-markdown")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Clear anything a previous process left behind — every workspace is
    # scratch space tied to a job that no longer exists.
    if settings.work_dir.exists():
        for leftover in settings.work_dir.iterdir():
            shutil.rmtree(leftover, ignore_errors=True)
    logger.info("%s listening on %s:%s", settings.app_name, settings.host, settings.port)
    yield
    shutil.rmtree(settings.work_dir, ignore_errors=True)


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Converts a codebase — uploaded archive, local directory, or public "
        "GitHub repository — into a single markdown document with a rendered "
        "directory tree and every source file inlined."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(convert.router)
app.include_router(jobs.router)


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something failed on the server. Check the API logs."},
    )


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "docs": "/docs", "health": "/api/health"}
