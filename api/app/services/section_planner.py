"""Decides how the document is split into ``##`` sections.

The reference document groups the repository into ``## Backend`` and
``## Frontend``. That grouping is not arbitrary — it comes from what each
top-level directory actually contains. This module reproduces that judgement:
first by directory name, and when the name is uninformative, by looking at the
marker files and file extensions inside.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from app.models.schemas import SectionMode
from app.services.scanner import Node

# ── Name-based hints ────────────────────────────────────────────────────────
NAME_ROLES: dict[str, str] = {
    "api": "Backend", "backend": "Backend", "server": "Backend",
    "service": "Backend", "services": "Backend", "srv": "Backend",
    "core": "Backend", "worker": "Backend", "workers": "Backend",

    "web": "Frontend", "frontend": "Frontend", "client": "Frontend",
    "ui": "Frontend", "app": "Frontend", "www": "Frontend",
    "dashboard": "Frontend", "site": "Frontend", "portal": "Frontend",

    "mobile": "Mobile", "ios": "Mobile", "android": "Mobile",
    "infra": "Infrastructure", "infrastructure": "Infrastructure",
    "deploy": "Infrastructure", "deployment": "Infrastructure",
    "terraform": "Infrastructure", "k8s": "Infrastructure",
    "kubernetes": "Infrastructure", "helm": "Infrastructure",
    "ops": "Infrastructure", "devops": "Infrastructure",

    "docs": "Documentation", "doc": "Documentation", "documentation": "Documentation",
    "scripts": "Scripts", "script": "Scripts", "tools": "Scripts",
    "bin": "Scripts", "job": "Jobs", "jobs": "Jobs",
    "tests": "Tests", "test": "Tests", "e2e": "Tests",
    "packages": "Packages", "libs": "Libraries", "lib": "Libraries",
    "shared": "Shared", "common": "Shared", "database": "Database",
    "db": "Database", "migrations": "Database", "sql": "Database",
    "mcp": "Integrations", "integrations": "Integrations",
}

# Names that appear in both stacks. For these, what the directory *contains*
# decides the role; the name is only a fallback. Without this, an ``api/app``
# folder full of Python would be filed under Frontend purely because "app" is
# a common frontend directory name.
AMBIGUOUS_NAMES: frozenset[str] = frozenset({
    "app", "src", "core", "lib", "libs", "service", "services",
    "client", "server", "packages", "shared", "common", "main",
})

# ── Marker files that identify a stack regardless of directory name ─────────
BACKEND_MARKERS = {
    "requirements.txt", "pyproject.toml", "setup.py", "Pipfile", "manage.py",
    "pom.xml", "build.gradle", "build.gradle.kts", "go.mod", "Cargo.toml",
    "Gemfile", "composer.json", "main.py", "app.py", "wsgi.py", "asgi.py",
}
FRONTEND_MARKERS = {
    "next.config.ts", "next.config.js", "next.config.mjs",
    "vite.config.ts", "vite.config.js", "angular.json", "svelte.config.js",
    "nuxt.config.ts", "remix.config.js", "astro.config.mjs", "index.html",
    "tailwind.config.ts", "tailwind.config.js",
}
INFRA_MARKERS = {
    "Chart.yaml", "main.tf", "variables.tf", "Pulumi.yaml",
    "docker-compose.yml", "docker-compose.yaml", "skaffold.yaml",
}

BACKEND_EXTENSIONS = {".py", ".java", ".go", ".rb", ".rs", ".php", ".cs", ".kt", ".ex"}
FRONTEND_EXTENSIONS = {".tsx", ".jsx", ".vue", ".svelte", ".css", ".scss", ".astro"}
INFRA_EXTENSIONS = {".tf", ".tfvars", ".hcl"}


@dataclass
class Section:
    """One ``##`` block of the generated document."""

    name: str
    root: Node | None            # None for the synthetic root-files section
    loose_files: list[Node] = field(default_factory=list)

    @property
    def is_loose(self) -> bool:
        return self.root is None

    def files(self) -> list[Node]:
        if self.root is not None:
            return list(self.root.iter_files())
        return self.loose_files


def _infer_role(node: Node) -> str | None:
    """Classify a directory by inspecting what is inside it."""
    names = set()
    extension_counts: Counter[str] = Counter()

    for file_node in node.iter_files():
        names.add(file_node.name)
        suffix = "." + file_node.name.rsplit(".", 1)[-1] if "." in file_node.name else ""
        extension_counts[suffix.lower()] += 1

    if names & FRONTEND_MARKERS:
        return "Frontend"
    if names & BACKEND_MARKERS:
        return "Backend"
    if names & INFRA_MARKERS:
        return "Infrastructure"

    frontend_score = sum(extension_counts[ext] for ext in FRONTEND_EXTENSIONS)
    backend_score = sum(extension_counts[ext] for ext in BACKEND_EXTENSIONS)
    infra_score = sum(extension_counts[ext] for ext in INFRA_EXTENSIONS)

    best = max(
        (("Frontend", frontend_score), ("Backend", backend_score), ("Infrastructure", infra_score)),
        key=lambda pair: pair[1],
    )
    return best[0] if best[1] > 0 else None


def _title_case(name: str) -> str:
    cleaned = name.replace("-", " ").replace("_", " ").strip()
    if not cleaned:
        return name
    return " ".join(word[:1].upper() + word[1:] for word in cleaned.split())


def _worth_a_section(directory: Node) -> bool:
    """False for a directory with nothing under it at all.

    ``directory.children`` still holds an entry for every file the scanner
    kept, even ones whose content was skipped or omitted (binary, oversized,
    tree-only mode) — only files removed by ignore rules disappear entirely.
    So "no children at all" reliably means "genuinely nothing here", and a
    placeholder directory like ``mcp/`` (empty, or holding only a
    ``.gitkeep``) shouldn't get a heading of its own; it already appears,
    correctly, in the top overview tree.
    """
    return bool(directory.children)


def plan_sections(root: Node, mode: SectionMode) -> list[Section]:
    """Return the ordered list of sections for the document."""
    directories = [
        child for child in root.children if child.is_dir and _worth_a_section(child)
    ]
    loose_files = [child for child in root.children if not child.is_dir]

    if mode is SectionMode.SINGLE:
        sections = [Section(name="Codebase", root=root)]
        return sections

    sections: list[Section] = []

    if mode is SectionMode.TOP_LEVEL:
        for directory in directories:
            sections.append(Section(name=_title_case(directory.name), root=directory))
    else:  # AUTO
        assigned: list[tuple[str, Node]] = []
        for directory in directories:
            lowered = directory.name.lower()
            if lowered in AMBIGUOUS_NAMES:
                # Content first — the name carries no reliable signal here.
                role = _infer_role(directory) or NAME_ROLES.get(lowered)
            else:
                role = NAME_ROLES.get(lowered) or _infer_role(directory)
            if role is None:
                role = _title_case(directory.name)
            assigned.append((role, directory))

        # A role used by exactly one directory keeps the role name. A role used
        # by several gets disambiguated by directory name so headings stay unique.
        role_counts = Counter(role for role, _ in assigned)
        for role, directory in assigned:
            if role_counts[role] > 1:
                name = f"{role} — {directory.name}"
            else:
                name = role
            sections.append(Section(name=name, root=directory))

        # Order: Backend, Frontend, then everything else alphabetically, with
        # boilerplate roles pushed to the end.
        priority = {
            "Backend": 0, "Frontend": 1, "Mobile": 2, "Database": 3,
            "Shared": 4, "Libraries": 5, "Packages": 6, "Integrations": 7,
            "Jobs": 8, "Scripts": 9, "Tests": 10,
            "Infrastructure": 11, "Documentation": 12,
        }
        sections.sort(
            key=lambda section: (
                priority.get(section.name.split(" — ")[0], 50),
                section.name.lower(),
            )
        )

    if loose_files:
        sections.append(
            Section(name="Root Files", root=None, loose_files=loose_files)
        )

    return [s for s in sections if s.is_loose or s.root is not None]
