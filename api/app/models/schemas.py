"""Request and response shapes for the HTTP layer."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class SectionMode(str, Enum):
    """How the document is split into ``##`` sections."""

    AUTO = "auto"          # Group top-level dirs by detected role (Backend/Frontend/…)
    TOP_LEVEL = "toplevel"  # One section per top-level directory
    SINGLE = "single"       # One "Codebase" section for everything


class PathStyle(str, Enum):
    """How file headings are written."""

    SECTION = "section"  # Relative to the section root: `app/core/config.py`
    FULL = "full"        # Relative to the repo root:   `api/app/core/config.py`


class ConvertOptions(BaseModel):
    """Everything the generator lets a caller tune."""

    title: str | None = Field(
        default=None,
        description="Heading written above the directory structure.",
    )
    preamble: str | None = Field(
        default=None,
        description="Sentence placed at the very top of the document.",
    )

    section_mode: SectionMode = SectionMode.AUTO
    path_style: PathStyle = PathStyle.SECTION

    use_gitignore: bool = Field(
        default=True, description="Honour .gitignore rules found in the tree."
    )
    include_hidden: bool = Field(
        default=False, description="Include dotfiles and dot-directories."
    )
    include_lockfiles: bool = Field(
        default=False,
        description="Include package-lock.json, yarn.lock, poetry.lock, and friends.",
    )
    include_tests: bool = Field(default=True)
    include_tree_only: bool = Field(
        default=False,
        description="Emit the directory structure and skip all file contents.",
    )

    max_file_kb: int = Field(default=400, ge=1, le=4096)
    max_lines_per_file: int = Field(default=4000, ge=10, le=100_000)
    truncate_long_files: bool = True

    include_extensions: list[str] = Field(
        default_factory=list,
        description="If non-empty, only these extensions are inlined (e.g. ['.py', '.ts']).",
    )
    exclude_globs: list[str] = Field(
        default_factory=list,
        description="Extra ignore patterns, gitignore syntax.",
    )

    annotate_tree: bool = Field(
        default=True,
        description="Append '← note' comments to notable tree entries.",
    )
    include_stats: bool = Field(
        default=True, description="Append a statistics section at the end."
    )
    collapse_empty_dirs: bool = True

    @field_validator("include_extensions", mode="before")
    @classmethod
    def _normalise_extensions(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        cleaned: list[str] = []
        for item in value:
            text = str(item).strip().lower()
            if not text:
                continue
            cleaned.append(text if text.startswith(".") else f".{text}")
        return cleaned


class PathConvertRequest(BaseModel):
    path: str = Field(min_length=1, description="Absolute directory path on the server.")
    options: ConvertOptions = Field(default_factory=ConvertOptions)


class RemoteConvertRequest(BaseModel):
    url: str = Field(min_length=1, description="GitHub repository URL or owner/repo.")
    ref: str | None = Field(default=None, description="Branch, tag, or commit SHA.")
    options: ConvertOptions = Field(default_factory=ConvertOptions)


class JobCreated(BaseModel):
    job_id: str
    status: str
    source_label: str


class LanguageStat(BaseModel):
    language: str
    files: int
    lines: int
    bytes: int


class SectionSummary(BaseModel):
    name: str
    root: str
    files: int
    lines: int


class ConversionStats(BaseModel):
    root_name: str
    total_files_seen: int
    files_included: int
    files_skipped_binary: int
    files_skipped_ignored: int
    files_skipped_too_large: int
    files_truncated: int
    directories: int
    total_lines: int
    total_bytes: int
    markdown_bytes: int
    markdown_lines: int
    duration_ms: int
    languages: list[LanguageStat]
    sections: list[SectionSummary]


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "error"]
    source_label: str
    created_at: float
    finished_at: float | None = None
    progress: float = 0.0
    message: str = ""
    error: str | None = None
    stats: ConversionStats | None = None
    filename: str | None = None


class ProgressEvent(BaseModel):
    """One server-sent event during a conversion."""

    type: Literal["status", "tree", "file", "done", "error"]
    message: str = ""
    progress: float = 0.0
    payload: dict[str, Any] | None = None
