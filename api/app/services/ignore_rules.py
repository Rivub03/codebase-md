"""Gitignore-compatible pattern matching.

Python's :mod:`fnmatch` is not enough here: gitignore has directory-anchored
patterns, leading-slash anchoring, ``**`` segments, and negation with ``!``.
This module implements those rules by compiling each pattern to a regex once,
then matching posix-style relative paths against the stack of rule sets that
apply at a given depth.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

# Directories that are noise in essentially every codebase. These are applied
# before .gitignore so the scan never even descends into them.
DEFAULT_IGNORES: tuple[str, ...] = (
    ".git/", ".hg/", ".svn/", ".bzr/",
    "node_modules/", "bower_components/", "jspm_packages/",
    "__pycache__/", ".pytest_cache/", ".mypy_cache/", ".ruff_cache/",
    ".tox/", ".nox/", ".eggs/", "*.egg-info/",
    "venv/", ".venv/", "env/", ".env/", "virtualenv/",
    "dist/", "build/", "out/", "target/", "bin/", "obj/",
    ".next/", ".nuxt/", ".svelte-kit/", ".astro/", ".turbo/", ".vercel/",
    ".parcel-cache/", ".cache/", ".output/",
    "coverage/", "htmlcov/", ".nyc_output/",
    ".idea/", ".vs/", ".gradle/", ".terraform/",
    "vendor/", "Pods/", "DerivedData/",
    "*.pyc", "*.pyo", "*.class", "*.o", "*.so", "*.dylib", "*.dll",
    ".DS_Store", "Thumbs.db", "desktop.ini",
    "*.log", "*.tmp", "*.swp", "*.swo", "*~",
)

# Lockfiles are enormous, machine-written, and say nothing a reader needs.
LOCKFILE_PATTERNS: tuple[str, ...] = (
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
    "poetry.lock", "Pipfile.lock", "pdm.lock", "uv.lock",
    "composer.lock", "Gemfile.lock", "Cargo.lock", "go.sum",
    "mix.lock", "pubspec.lock", "packages.lock.json",
)

TEST_PATTERNS: tuple[str, ...] = (
    "test/", "tests/", "__tests__/", "spec/", "__mocks__/",
    "*_test.py", "test_*.py", "*.test.ts", "*.test.tsx", "*.test.js",
    "*.test.jsx", "*.spec.ts", "*.spec.tsx", "*.spec.js", "*.spec.jsx",
    "*Test.java", "*Tests.java", "*_test.go",
)


def _translate(pattern: str) -> str:
    """Compile one gitignore glob body into a regex fragment.

    Handles ``*`` (no separator), ``**`` (any depth), ``?``, and ``[...]``
    classes the way git does.
    """
    out: list[str] = []
    index = 0
    length = len(pattern)

    while index < length:
        char = pattern[index]

        if char == "*":
            # Count the run of stars.
            star_run = 0
            while index < length and pattern[index] == "*":
                star_run += 1
                index += 1
            if star_run >= 2:
                # "**/" swallows any number of leading directories.
                if index < length and pattern[index] == "/":
                    index += 1
                    out.append("(?:.*/)?")
                else:
                    out.append(".*")
            else:
                out.append("[^/]*")
            continue

        if char == "?":
            out.append("[^/]")
            index += 1
            continue

        if char == "[":
            close = pattern.find("]", index + 1)
            if close == -1:
                out.append(re.escape(char))
                index += 1
                continue
            body = pattern[index + 1:close]
            if body.startswith("!"):
                body = "^" + body[1:]
            out.append(f"[{body}]")
            index = close + 1
            continue

        out.append(re.escape(char))
        index += 1

    return "".join(out)


@dataclass(slots=True)
class Rule:
    """A single compiled ignore pattern."""

    regex: re.Pattern[str]
    negated: bool
    directory_only: bool
    source: str

    def matches(self, relative_path: str, is_dir: bool) -> bool:
        if self.directory_only and not is_dir:
            return False
        return self.regex.match(relative_path) is not None


def compile_rule(raw: str) -> Rule | None:
    """Turn one gitignore line into a :class:`Rule`, or ``None`` if it is inert."""
    line = raw.rstrip("\n").rstrip("\r")
    if not line.strip() or line.lstrip().startswith("#"):
        return None

    # An escaped leading '#' or '!' is a literal.
    if line.startswith("\\"):
        line = line[1:]

    negated = line.startswith("!")
    if negated:
        line = line[1:]

    line = line.strip()
    if not line:
        return None

    directory_only = line.endswith("/")
    if directory_only:
        line = line[:-1]

    anchored = line.startswith("/") or "/" in line.rstrip("/")
    if line.startswith("/"):
        line = line[1:]

    body = _translate(line)
    if anchored:
        pattern = f"^{body}(?:/.*)?$"
    else:
        # Unanchored patterns match at any depth.
        pattern = f"^(?:.*/)?{body}(?:/.*)?$"

    return Rule(
        regex=re.compile(pattern),
        negated=negated,
        directory_only=directory_only,
        source=raw.strip(),
    )


@dataclass
class IgnoreSet:
    """An ordered stack of rules; later rules win, matching git's semantics."""

    rules: list[Rule] = field(default_factory=list)

    @classmethod
    def from_patterns(cls, patterns: list[str] | tuple[str, ...]) -> IgnoreSet:
        compiled = [rule for rule in (compile_rule(p) for p in patterns) if rule]
        return cls(rules=compiled)

    def extend_from_text(self, text: str, base_dir: str = "") -> None:
        """Add rules parsed from a .gitignore file living at ``base_dir``."""
        for raw in text.splitlines():
            rule = compile_rule(raw)
            if rule is None:
                continue
            if base_dir:
                # Re-anchor the pattern beneath the directory holding the file.
                prefix = re.escape(base_dir.strip("/") + "/")
                rule.regex = re.compile(
                    rule.regex.pattern.replace("^", f"^{prefix}", 1)
                )
            self.rules.append(rule)

    def merged_with(self, other: IgnoreSet) -> IgnoreSet:
        return IgnoreSet(rules=[*self.rules, *other.rules])

    def is_ignored(self, relative_path: str, is_dir: bool) -> bool:
        """Return whether ``relative_path`` should be skipped."""
        path = PurePosixPath(relative_path).as_posix().strip("/")
        if not path:
            return False

        decision = False
        for rule in self.rules:
            if rule.matches(path, is_dir):
                decision = not rule.negated
        return decision

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self.rules)


def build_ignore_set(
    *,
    include_hidden: bool,
    include_lockfiles: bool,
    include_tests: bool,
    extra_globs: list[str],
) -> IgnoreSet:
    """Assemble the base rule stack from the caller's options."""
    patterns: list[str] = list(DEFAULT_IGNORES)

    if not include_hidden:
        # Hide dot-entries, but keep the ones that carry real configuration.
        patterns.append(".*")
        patterns.extend(
            f"!{keep}"
            for keep in (
                ".env.example", ".env.sample", ".gitignore", ".dockerignore",
                ".editorconfig", ".eslintrc*", ".prettierrc*", ".babelrc*",
                ".nvmrc", ".python-version", ".ruby-version", ".tool-versions",
                ".github/", ".gitlab-ci.yml", ".gitattributes",
            )
        )
        # …then re-hide the heavyweight dot-directories the allowances re-opened.
        patterns.extend((".github/workflows/*.svg", ".git/"))

    if not include_lockfiles:
        patterns.extend(LOCKFILE_PATTERNS)

    if not include_tests:
        patterns.extend(TEST_PATTERNS)

    patterns.extend(extra_globs)
    return IgnoreSet.from_patterns(patterns)
