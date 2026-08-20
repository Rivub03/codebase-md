"""Maps a file to the language tag that opens its fenced code block.

The tag drives syntax highlighting wherever the generated markdown is read, so
getting it right is most of what makes the output pleasant. Extension lookup
covers the common cases; exact-filename lookup covers the many build files that
have no extension at all (``Dockerfile``, ``Makefile``, ``.gitignore``).
"""

from __future__ import annotations

from pathlib import PurePosixPath

# ── Exact filename → fence tag ──────────────────────────────────────────────
FILENAME_LANGUAGES: dict[str, str] = {
    "dockerfile": "dockerfile",
    "containerfile": "dockerfile",
    "makefile": "makefile",
    "gnumakefile": "makefile",
    "justfile": "makefile",
    "rakefile": "ruby",
    "gemfile": "ruby",
    "brewfile": "ruby",
    "vagrantfile": "ruby",
    "procfile": "yaml",
    "cmakelists.txt": "cmake",
    ".gitignore": "gitignore",
    ".dockerignore": "gitignore",
    ".npmignore": "gitignore",
    ".env": "env",
    ".env.example": "env",
    ".env.local": "env",
    ".env.sample": "env",
    ".editorconfig": "ini",
    ".babelrc": "json",
    ".prettierrc": "json",
    ".eslintrc": "json",
    ".nvmrc": "text",
    "go.mod": "go",
    "go.sum": "text",
    "cargo.lock": "toml",
    "requirements.txt": "text",
    "pipfile": "toml",
    "license": "text",
}

# ── Extension → fence tag ───────────────────────────────────────────────────
EXTENSION_LANGUAGES: dict[str, str] = {
    # Python
    ".py": "python", ".pyi": "python", ".pyw": "python", ".ipynb": "json",
    # JavaScript / TypeScript
    ".js": "javascript", ".jsx": "jsx", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "tsx", ".mts": "typescript", ".cts": "typescript",
    # Web
    ".html": "html", ".htm": "html", ".xhtml": "html", ".vue": "vue",
    ".svelte": "svelte", ".astro": "astro",
    ".css": "css", ".scss": "scss", ".sass": "sass", ".less": "less",
    # JVM
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin", ".groovy": "groovy",
    ".scala": "scala", ".gradle": "groovy",
    # Systems
    ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
    ".hpp": "cpp", ".hh": "cpp", ".hxx": "cpp",
    ".rs": "rust", ".go": "go", ".zig": "zig", ".swift": "swift",
    ".m": "objectivec", ".mm": "objectivec",
    # Other languages
    ".rb": "ruby", ".php": "php", ".cs": "csharp", ".fs": "fsharp",
    ".ex": "elixir", ".exs": "elixir", ".erl": "erlang", ".hrl": "erlang",
    ".hs": "haskell", ".clj": "clojure", ".cljs": "clojure", ".edn": "clojure",
    ".lua": "lua", ".pl": "perl", ".pm": "perl", ".r": "r", ".jl": "julia",
    ".dart": "dart", ".nim": "nim", ".sol": "solidity", ".vb": "vbnet",
    # Shell / config
    ".sh": "bash", ".bash": "bash", ".zsh": "bash", ".fish": "fish",
    ".ps1": "powershell", ".psm1": "powershell", ".bat": "batch", ".cmd": "batch",
    ".json": "json", ".jsonc": "jsonc", ".json5": "json5",
    ".yaml": "yaml", ".yml": "yaml", ".toml": "toml", ".ini": "ini",
    ".cfg": "ini", ".conf": "ini", ".properties": "properties",
    ".xml": "xml", ".xsd": "xml", ".xsl": "xml", ".plist": "xml",
    ".env": "env", ".tf": "hcl", ".tfvars": "hcl", ".hcl": "hcl",
    # Data / query
    ".sql": "sql", ".psql": "sql", ".prisma": "prisma", ".graphql": "graphql",
    ".gql": "graphql", ".proto": "protobuf", ".csv": "csv", ".tsv": "text",
    # Docs
    ".md": "markdown", ".mdx": "mdx", ".rst": "rst", ".txt": "text",
    ".tex": "latex", ".adoc": "asciidoc", ".org": "org",
    # Misc
    ".svg": "xml", ".patch": "diff", ".diff": "diff", ".lock": "text",
    ".gitattributes": "gitattributes", ".http": "http", ".rest": "http",
}

# Extensions we never inline — the bytes would be meaningless in a document.
BINARY_EXTENSIONS: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff", ".avif",
    ".mp3", ".mp4", ".wav", ".ogg", ".flac", ".avi", ".mov", ".mkv", ".webm",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".jar", ".war",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".so", ".dll", ".dylib", ".exe", ".bin", ".o", ".a", ".obj", ".class",
    ".pyc", ".pyo", ".pyd", ".wasm", ".db", ".sqlite", ".sqlite3", ".mdb",
    ".pkl", ".npy", ".npz", ".parquet", ".arrow", ".feather", ".h5", ".pb",
    ".psd", ".ai", ".sketch", ".fig", ".blend", ".dmg", ".iso", ".img",
})


def language_for(path: str) -> str:
    """Return the fence tag for ``path`` (posix-style, any depth)."""
    name = PurePosixPath(path).name
    lowered = name.lower()

    if lowered in FILENAME_LANGUAGES:
        return FILENAME_LANGUAGES[lowered]

    # Dockerfile.prod, Dockerfile.dev, .env.production, …
    for stem, tag in (("dockerfile", "dockerfile"), (".env", "env")):
        if lowered.startswith(stem):
            return tag

    suffixes = PurePosixPath(lowered).suffixes
    if suffixes:
        # Try the compound suffix first (".d.ts" → typescript) then the last.
        if len(suffixes) >= 2 and "".join(suffixes[-2:]) == ".d.ts":
            return "typescript"
        last = suffixes[-1]
        if last in EXTENSION_LANGUAGES:
            return EXTENSION_LANGUAGES[last]

    return "text"


def is_probably_binary_name(path: str) -> bool:
    """Cheap pre-filter before reading bytes off disk."""
    suffix = PurePosixPath(path.lower()).suffix
    return suffix in BINARY_EXTENSIONS


def looks_binary(sample: bytes) -> bool:
    """Heuristic used after reading: NUL byte, or a high share of non-text."""
    if not sample:
        return False
    if b"\x00" in sample:
        return True
    textish = bytes(range(0x20, 0x7F)) + b"\n\r\t\f\b\x1b"
    non_text = sum(1 for byte in sample if byte not in textish and byte < 0x80)
    return non_text / len(sample) > 0.30
