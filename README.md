# Codebase → Markdown

Point this at a codebase — an uploaded archive, a folder on disk, or a public
GitHub repository — and get back a single markdown document: the full
directory tree, then every source file inlined under its own heading and
fenced with the right language tag.

```
28 files, 6 languages, 12 directories
              │
              ▼
        one document
```

## Stack

- **`api/`** — FastAPI (Python 3.11+). Does the actual scanning, filtering,
  and markdown generation. Fully usable on its own via its HTTP API or `/docs`.
- **`web/`** — Next.js 16 + React 19 (TypeScript). A UI for the API: pick a
  source, tune options, watch the directory tree stream in live, read or
  download the result.

Either can run independently. The frontend just calls the backend over HTTP.

## Quick start

### Option A — Docker Compose (easiest)

```bash
docker compose up --build
```

Then open **http://localhost:3000**. The API is on **http://localhost:8080**
(`/docs` for the OpenAPI schema). The compose file mounts the repo root
read-only into the API container so "Folder" mode has something to browse —
point `LOCAL_PATH_ROOTS` in `docker-compose.yml` at wherever your own projects
live if you want to convert those instead.

### Option B — run each side directly

**Backend:**

```bash
cd api
./run.sh          # creates a venv, installs deps, starts on :8080 with reload
```

Or manually:

```bash
cd api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8080
```

**Frontend** (in a second terminal):

```bash
cd web
npm install
cp .env.example .env.local     # BACKEND_URL defaults to localhost:8080
npm run dev                    # http://localhost:3000
```

The frontend proxies `/api/*` to `BACKEND_URL` (see `next.config.ts`), so the
browser never needs to know the API's address directly, and there's nothing
to configure for CORS in normal use.

## Using it

1. **Pick a source** — drop a `.zip`/`.tar` archive, point at a directory on
   the machine running the API, or paste a GitHub URL.
2. **Adjust options** if you want — which files to skip, size/line limits,
   how sections are grouped, whether the tree gets annotated.
3. **Convert.** The directory tree streams in live as the server walks it.
4. **Read, copy, or download** the result. The document view is a live
   preview (capped for browser performance on huge repos); the download
   always contains the complete file.

## What the backend actually does

```
scan → filter → classify → render
```

- **Scan**: walks the tree, reads every file it's going to inline, sniffs
  binaries by content (not just extension), never follows symlinks.
- **Filter**: a real `.gitignore`-compatible engine (anchoring, `**`,
  negation, directory-only patterns) plus sensible defaults for
  `node_modules`, `__pycache__`, `.next`, build output, lockfiles, and OS
  cruft. A directory containing nothing (or only a `.gitkeep`) is treated as
  an intentional placeholder — shown in the tree, annotated, but not given a
  pointless section of its own.
- **Classify**: groups top-level directories into sections (Backend,
  Frontend, Infrastructure, …) by marker files and file-extension mix, not
  just directory name — so `api/app/` full of Python lands under Backend even
  though `app/` alone is an ambiguous name.
- **Render**: emits the tree with box-drawing connectors, then each file
  under a heading whose depth reflects its position in the tree, fenced with
  a language tag inferred from ~150 extensions and well-known filenames
  (`Dockerfile`, `Makefile`, `.env`, …). Fences grow past ```` ``` ```` when a
  file's own content contains a fence, so nothing downstream ever breaks.

Three sources, one pipeline: uploaded archives are extracted with zip-slip and
decompression-bomb guards; local paths are read directly; GitHub repos are
pulled as a zipball (no `git` binary required) and unwrapped from their
`repo-branch/` wrapper folder automatically.

## API reference

Full interactive docs at `/docs` once the backend is running. The shape:

| Endpoint | Method | What it does |
|---|---|---|
| `/api/convert/upload` | POST | Start a conversion from an uploaded archive |
| `/api/convert/path` | POST | Start a conversion from a server-local directory |
| `/api/convert/remote` | POST | Start a conversion from a GitHub repo |
| `/api/jobs/{id}` | GET | Poll a job's status and stats |
| `/api/jobs/{id}/events` | GET | Server-sent events: live progress |
| `/api/jobs/{id}/markdown` | GET | The result as plain text |
| `/api/jobs/{id}/download` | GET | The result as a file download |
| `/api/capabilities` | GET | What this deployment allows (used by the UI) |

Every conversion accepts an `options` object — see `ConvertOptions` in
`api/app/models/schemas.py` for the full set (section grouping, path style,
size/line limits, extension allowlist, extra ignore globs, and more).

## Configuration

Both sides read from a `.env` file (see the `.env.example` in each folder).
Notable backend settings:

- `ALLOW_LOCAL_PATH` / `LOCAL_PATH_ROOTS` — reading arbitrary server paths is
  convenient locally and a real risk in a shared deployment; turn it off or
  pin it to specific roots before deploying this publicly.
- `ALLOW_REMOTE_FETCH` / `GITHUB_TOKEN` — set a token to raise GitHub's rate
  limit and allow private repositories.
- `MAX_ARCHIVE_MB`, `MAX_EXTRACTED_MB`, `MAX_FILES`, `MAX_FILE_KB_CEILING` —
  guard rails against a runaway upload or repository.

## Testing

```bash
cd api
pip install -r requirements.txt pytest
python -m pytest tests -q
```

Covers language detection, gitignore semantics (including `**` and
negation), binary sniffing, truncation, extension filtering, section
detection, heading-depth progression, fence-escaping for files that contain
their own code fences, and placeholder-directory handling.

## Notes on the format

The heading depth for a directory at relative depth *d* within its section is
`#` × (*d* + 2); a file at relative depth *d* is `#` × (*d* + 3), capped at
`######`. That reproduces a progression like:

```
## Frontend
### /app
#### /component
##### /auth
###### web/app/component/auth/AuthProvider.tsx
```

`path_style` controls whether file headings are written relative to their
section (`app/core/config.py`) or as the full repo-relative path
(`api/app/core/config.py`).
