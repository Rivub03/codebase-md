"""Renders a :class:`Node` tree as the box-drawing listing used in the target format.

The reference document uses ``├──`` / ``└──`` connectors, ``│`` continuation
bars, a trailing slash on directories, and optional ``←`` notes aligned into a
comment column. All of that is reproduced here.
"""

from __future__ import annotations

from app.services.scanner import Node

TEE = "├── "
ELBOW = "└── "
PIPE = "│   "
BLANK = "    "

# Column where '←' notes begin. Lines longer than this push the note out by one
# space rather than wrapping, which keeps long paths readable.
NOTE_COLUMN = 36

# Well-known entries get a short description, the way a human would annotate a
# tree they were writing by hand.
KNOWN_NOTES: dict[str, str] = {
    # Backend
    "main.py": "Application entrypoint",
    "app.py": "Application entrypoint",
    "wsgi.py": "WSGI entrypoint",
    "asgi.py": "ASGI entrypoint",
    "manage.py": "Django management CLI",
    "requirements.txt": "Python dependencies",
    "pyproject.toml": "Project metadata + dependencies",
    "setup.py": "Package definition",
    "config.py": "Settings",
    "settings.py": "Settings",
    "router.py": "HTTP routes",
    "routes.py": "HTTP routes",
    "schemas.py": "Request/response schemas",
    "models.py": "ORM models",
    "service.py": "Business logic",
    "database.py": "Database connection",
    "session.py": "Session factory",
    "conftest.py": "Shared pytest fixtures",
    # Frontend
    "package.json": "Dependencies + scripts",
    "next.config.ts": "Next.js configuration",
    "next.config.js": "Next.js configuration",
    "vite.config.ts": "Vite configuration",
    "tsconfig.json": "TypeScript configuration",
    "layout.tsx": "Root layout",
    "page.tsx": "Route entry",
    "globals.css": "Global styles",
    "index.html": "HTML shell",
    "App.tsx": "Root component",
    "main.tsx": "Client entrypoint",
    # Tooling
    "Dockerfile": "Container image",
    "docker-compose.yml": "Local service topology",
    "Makefile": "Task shortcuts",
    ".env.example": "Template for required env vars",
    ".gitignore": "Ignored paths",
    "README.md": "Project overview",
}

KNOWN_DIR_NOTES: dict[str, str] = {
    "api": "Backend service",
    "web": "Frontend application",
    "app": "Application source",
    "src": "Application source",
    "components": "Reusable UI components",
    "component": "Reusable UI components",
    "pages": "Route components",
    "routers": "HTTP route modules",
    "routes": "HTTP route modules",
    "services": "Business logic",
    "models": "Data models",
    "schemas": "Validation schemas",
    "core": "Cross-cutting configuration",
    "db": "Database layer",
    "database": "Database layer",
    "migrations": "Schema migrations",
    "tests": "Test suite",
    "test": "Test suite",
    "hooks": "Shared React hooks",
    "lib": "Shared utilities",
    "utils": "Shared utilities",
    "static": "Static assets",
    "public": "Static assets",
    "assets": "Static assets",
    "scripts": "Operational scripts",
    "infra": "Infrastructure definitions",
    "docs": "Documentation",
}


def _note_for(node: Node, annotate: bool) -> str:
    if not annotate:
        return ""
    if node.is_dir:
        if not node.children:
            return "Placeholder" if node.empty_on_disk else "Empty after filtering"
        return KNOWN_DIR_NOTES.get(node.name.lower(), "")
    return KNOWN_NOTES.get(node.name, "")


def _label(node: Node) -> str:
    return f"{node.name}/" if node.is_dir else node.name


def render_tree(
    root: Node,
    *,
    root_label: str | None = None,
    annotate: bool = True,
    show_root: bool = True,
    max_entries: int = 4000,
) -> str:
    """Return the tree listing for ``root`` as a plain string (no fences)."""
    lines: list[str] = []
    emitted = 0

    if show_root:
        label = root_label or f"{root.name}/"
        if not label.endswith("/"):
            label = f"{label}/"
        lines.append(label)

    def walk(node: Node, prefix: str) -> None:
        nonlocal emitted
        children = node.children
        for index, child in enumerate(children):
            if emitted >= max_entries:
                lines.append(f"{prefix}└── … (listing truncated)")
                return
            last = index == len(children) - 1
            connector = ELBOW if last else TEE
            body = f"{prefix}{connector}{_label(child)}"

            note = _note_for(child, annotate)
            if note:
                pad = max(NOTE_COLUMN - len(body), 1)
                body = f"{body}{' ' * pad}← {note}"

            lines.append(body)
            emitted += 1

            if child.is_dir and child.children:
                walk(child, prefix + (BLANK if last else PIPE))

    walk(root, "" if show_root else "")
    return "\n".join(lines)


def render_subtree(
    node: Node,
    *,
    annotate: bool = True,
    max_entries: int = 4000,
) -> str:
    """Render a section's own subtree, rooted at ``node`` with its own name shown."""
    lines = [f"{TEE}{node.name}/"]
    emitted = 0

    def walk(current: Node, prefix: str) -> None:
        nonlocal emitted
        children = current.children
        for index, child in enumerate(children):
            if emitted >= max_entries:
                lines.append(f"{prefix}└── … (listing truncated)")
                return
            last = index == len(children) - 1
            connector = ELBOW if last else TEE
            body = f"{prefix}{connector}{_label(child)}"

            note = _note_for(child, annotate)
            if note:
                pad = max(NOTE_COLUMN - len(body), 1)
                body = f"{body}{' ' * pad}← {note}"

            lines.append(body)
            emitted += 1

            if child.is_dir and child.children:
                walk(child, prefix + (BLANK if last else PIPE))

    walk(node, PIPE)
    return "\n".join(lines)


def tree_lines_for_stream(root: Node, limit: int = 400) -> list[str]:
    """A compact, unannotated listing used for the live progress view."""
    text = render_tree(root, annotate=False, max_entries=limit)
    return text.splitlines()
