"""Downloads a public repository as a zipball.

Uses the codeload archive endpoint rather than shelling out to ``git``, so the
API has no binary dependency and never fetches history it will not read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.core.config import settings

GITHUB_URL_PATTERN = re.compile(
    r"""^
    (?:https?://)?
    (?:www\.)?
    github\.com/
    (?P<owner>[\w.\-]+)/
    (?P<repo>[\w.\-]+?)
    (?:\.git)?
    (?:/(?:tree|blob)/(?P<ref>[^/\s]+))?
    /?$
    """,
    re.VERBOSE,
)

SHORTHAND_PATTERN = re.compile(r"^(?P<owner>[\w.\-]+)/(?P<repo>[\w.\-]+?)(?:\.git)?$")


class RemoteFetchError(Exception):
    """Raised when a repository cannot be downloaded."""


@dataclass(frozen=True)
class RepoRef:
    owner: str
    repo: str
    ref: str | None = None

    @property
    def label(self) -> str:
        suffix = f"@{self.ref}" if self.ref else ""
        return f"{self.owner}/{self.repo}{suffix}"


def parse_repo_url(value: str) -> RepoRef:
    """Accept a full GitHub URL or ``owner/repo`` shorthand."""
    text = value.strip()
    if not text:
        raise RemoteFetchError("Enter a repository URL.")

    match = GITHUB_URL_PATTERN.match(text)
    if match:
        return RepoRef(
            owner=match.group("owner"),
            repo=match.group("repo"),
            ref=match.group("ref"),
        )

    match = SHORTHAND_PATTERN.match(text)
    if match:
        return RepoRef(owner=match.group("owner"), repo=match.group("repo"))

    raise RemoteFetchError(
        "That does not look like a GitHub repository. "
        "Use https://github.com/owner/repo or owner/repo."
    )


def _candidate_urls(ref: RepoRef, explicit_ref: str | None) -> list[str]:
    base = f"https://codeload.github.com/{ref.owner}/{ref.repo}/zip"
    chosen = explicit_ref or ref.ref
    if chosen:
        return [f"{base}/refs/heads/{chosen}", f"{base}/{chosen}"]
    return [f"{base}/refs/heads/main", f"{base}/refs/heads/master"]


def download_repository(
    url: str, ref: str | None, destination: Path
) -> tuple[Path, str]:
    """Download the repo archive to ``destination``; return the path and a label."""
    if not settings.allow_remote_fetch:
        raise RemoteFetchError("Remote repository fetching is disabled on this server.")

    repo = parse_repo_url(url)
    destination.parent.mkdir(parents=True, exist_ok=True)

    headers = {"User-Agent": "codebase-to-markdown"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    last_error = ""
    limit = settings.max_archive_mb * 1024 * 1024

    for candidate in _candidate_urls(repo, ref):
        try:
            with httpx.stream(
                "GET",
                candidate,
                headers=headers,
                follow_redirects=True,
                timeout=settings.remote_timeout_seconds,
            ) as response:
                if response.status_code == 404:
                    last_error = "Repository or branch not found."
                    continue
                if response.status_code == 403:
                    raise RemoteFetchError(
                        "GitHub rejected the request (rate limit or private repo). "
                        "Set GITHUB_TOKEN to raise the limit."
                    )
                response.raise_for_status()

                written = 0
                with open(destination, "wb") as handle:
                    for chunk in response.iter_bytes(chunk_size=1 << 16):
                        written += len(chunk)
                        if written > limit:
                            raise RemoteFetchError(
                                f"Repository archive is larger than "
                                f"{settings.max_archive_mb} MB."
                            )
                        handle.write(chunk)

            return destination, repo.label

        except httpx.HTTPStatusError as exc:
            last_error = f"GitHub returned HTTP {exc.response.status_code}."
        except httpx.RequestError as exc:
            last_error = f"Could not reach GitHub: {exc.__class__.__name__}."

    raise RemoteFetchError(last_error or "Could not download that repository.")
