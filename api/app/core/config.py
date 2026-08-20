"""Application settings, read from the environment (or a local .env file)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader so the API runs with zero extra dependencies."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(key: str, default: list[str]) -> list[str]:
    raw = os.environ.get(key)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    """Runtime configuration. Instantiated once via :func:`get_settings`."""

    def __init__(self) -> None:
        self.app_name: str = os.environ.get("APP_NAME", "Codebase to Markdown")
        self.host: str = os.environ.get("HOST", "0.0.0.0")
        self.port: int = _env_int("PORT", 8080)

        # CORS — the Next.js dev server by default.
        self.cors_origins: list[str] = _env_list(
            "CORS_ORIGINS",
            ["http://localhost:3000", "http://127.0.0.1:3000"],
        )

        # Upload / scan limits. These are guard rails, not preferences: they
        # stop a runaway repository from exhausting memory.
        self.max_archive_mb: int = _env_int("MAX_ARCHIVE_MB", 5120)
        self.max_extracted_mb: int = _env_int("MAX_EXTRACTED_MB", 600)
        self.max_files: int = _env_int("MAX_FILES", 8000)
        self.max_file_kb_default: int = _env_int("MAX_FILE_KB_DEFAULT", 400)
        self.max_file_kb_ceiling: int = _env_int("MAX_FILE_KB_CEILING", 4096)

        # Jobs are held in memory and swept once they age out.
        self.job_ttl_seconds: int = _env_int("JOB_TTL_SECONDS", 3600)
        self.max_jobs: int = _env_int("MAX_JOBS", 64)

        # Reading a directory straight off the server's disk is handy locally
        # and dangerous when deployed, so it is opt-out.
        self.allow_local_path: bool = _env_bool("ALLOW_LOCAL_PATH", True)
        self.local_path_roots: list[str] = _env_list("LOCAL_PATH_ROOTS", [])

        # Fetching a public repository archive over HTTPS.
        self.allow_remote_fetch: bool = _env_bool("ALLOW_REMOTE_FETCH", True)
        self.github_token: str = os.environ.get("GITHUB_TOKEN", "")
        self.remote_timeout_seconds: int = _env_int("REMOTE_TIMEOUT_SECONDS", 60)

        self.work_dir: Path = Path(
            os.environ.get("WORK_DIR", "")
            or (Path(__file__).resolve().parents[2] / ".work")
        )
        self.work_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
