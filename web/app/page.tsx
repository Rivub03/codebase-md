"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import LiveTree from "./components/LiveTree";
import OptionsPanel from "./components/OptionsPanel";
import ResultPanel from "./components/ResultPanel";
import SourcePanel from "./components/SourcePanel";
import StatsStrip from "./components/StatsStrip";
import { IconAlert, IconCheck, IconPlay, IconSliders } from "./components/Icons";
import {
  convertPath,
  convertRemote,
  convertUpload,
  downloadUrl,
  getCapabilities,
  getMarkdown,
  streamProgress,
} from "./lib/api";
import {
  DEFAULT_OPTIONS,
  type Capabilities,
  type ConversionStats,
  type ConvertOptions,
  type SourceKind,
} from "./lib/types";
import {
  bytesFromMegabytes,
  formatFileSize,
} from "./lib/uploadLimits";

const EMPTY_GLYPH = `  repo/
  ├── api/
  │   └── app/
  │       └── main.py
  └── web/
      └── page.tsx`;

export default function Page() {
  // ── Source ───────────────────────────────────────────────────────────────
  const [kind, setKind] = useState<SourceKind>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [localPath, setLocalPath] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [repoRef, setRepoRef] = useState("");

  // ── Options ──────────────────────────────────────────────────────────────
  const [options, setOptions] = useState<ConvertOptions>(DEFAULT_OPTIONS);
  const patchOptions = useCallback(
    (patch: Partial<ConvertOptions>) =>
      setOptions((current) => ({ ...current, ...patch })),
    [],
  );

  // ── Job ──────────────────────────────────────────────────────────────────
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentPath, setCurrentPath] = useState("");
  const [discovered, setDiscovered] = useState<string[]>([]);
  const [finalLines, setFinalLines] = useState<string[] | null>(null);
  const [markdown, setMarkdown] = useState("");
  const [stats, setStats] = useState<ConversionStats | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [filename, setFilename] = useState("codebase.md");
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const closeStream = useRef<(() => void) | null>(null);

  useEffect(() => {
    getCapabilities()
      .then((caps) => {
        setCapabilities(caps);
        patchOptions({ max_file_kb: caps.max_file_kb_default });
      })
      .catch(() =>
        setError(
          "Cannot reach the API. Start it with `cd api && ./run.sh`, then reload.",
        ),
      );
  }, [patchOptions]);

  useEffect(() => () => closeStream.current?.(), []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const rootName =
    kind === "upload"
      ? file?.name.replace(/\.(zip|tar|tar\.gz|tgz|tar\.bz2|tar\.xz)$/i, "") ?? "codebase"
      : kind === "path"
        ? localPath.split("/").filter(Boolean).pop() ?? "codebase"
        : repoUrl.split("/").filter(Boolean).pop() ?? "repository";

  const maxArchiveBytes = capabilities
    ? bytesFromMegabytes(capabilities.max_archive_mb)
    : null;
  const selectedArchiveError =
    kind === "upload" && file && maxArchiveBytes !== null && file.size > maxArchiveBytes
      ? `Archive is ${formatFileSize(file.size)}, but this server allows up to ${formatFileSize(maxArchiveBytes)}.`
      : null;

  const ready =
    ((kind === "upload" && file !== null)
      || (kind === "path" && localPath.trim().length > 0)
      || (kind === "remote" && repoUrl.trim().length > 0))
    && selectedArchiveError === null;

  async function convert() {
    if (selectedArchiveError) {
      setError(selectedArchiveError);
      return;
    }

    if (!ready || running) return;

    closeStream.current?.();
    setRunning(true);
    setError(null);
    setProgress(0);
    setCurrentPath("");
    setDiscovered([]);
    setFinalLines(null);
    setMarkdown("");
    setStats(null);
    setJobId(null);

    try {
      const created =
        kind === "upload"
          ? await convertUpload(file as File, options)
          : kind === "path"
            ? await convertPath(localPath.trim(), options)
            : await convertRemote(repoUrl.trim(), repoRef.trim() || null, options);

      setJobId(created.job_id);

      closeStream.current = streamProgress(created.job_id, {
        onEvent: (event) => {
          if (event.progress) setProgress(event.progress);

          if (event.type === "file" && event.payload?.path) {
            const path = event.payload.path;
            setCurrentPath(path);
            setDiscovered((current) =>
              current.length > 3000 ? current : [...current, path],
            );
          }

          if (event.type === "tree" && event.payload?.lines) {
            setFinalLines(event.payload.lines);
          }

          if (event.type === "done") {
            if (event.payload?.stats) setStats(event.payload.stats);
            if (event.payload?.filename) setFilename(event.payload.filename);
            getMarkdown(created.job_id)
              .then((text) => {
                setMarkdown(text);
                setRunning(false);
                setProgress(1);
                setToast("Document ready");
              })
              .catch((cause: Error) => {
                setError(cause.message);
                setRunning(false);
              });
          }

          if (event.type === "error") {
            setError(event.message);
            setRunning(false);
          }
        },
        onError: (message) => {
          setError(message);
          setRunning(false);
        },
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The conversion failed.");
      setRunning(false);
    }
  }

  const showTree = running || finalLines !== null || discovered.length > 0;

  return (
    <div className="shell">
      {/* ── Source side ──────────────────────────────────────────────────── */}
      <aside className="rail">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <svg
              width="17"
              height="17"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M6 4v14a1 1 0 0 0 1 1h4M6 11h5" />
              <path d="M15 6h5M15 12h5M15 18h5" />
            </svg>
          </span>
          <span>
            <span className="brand-name">Codebase → Markdown</span>
            <span className="brand-sub">one repo, one document</span>
          </span>
        </div>

        <SourcePanel
          kind={kind}
          onKindChange={setKind}
          file={file}
          onFileChange={setFile}
          localPath={localPath}
          onLocalPathChange={setLocalPath}
          repoUrl={repoUrl}
          onRepoUrlChange={setRepoUrl}
          repoRef={repoRef}
          onRepoRefChange={setRepoRef}
          capabilities={capabilities}
          disabled={running}
        />

        <button type="button" className="run" onClick={convert} disabled={!ready || running}>
          {running ? (
            <>
              <span className="spinner" aria-hidden="true" />
              Converting…
            </>
          ) : (
            <>
              <IconPlay />
              Convert to markdown
            </>
          )}
        </button>

        <OptionsPanel
          options={options}
          onChange={patchOptions}
          maxFileKbCeiling={capabilities?.max_file_kb_ceiling ?? 2048}
          disabled={running}
        />

        <div className="rail-foot">
          <IconSliders size={13} /> API at <code>{"/api"}</code> — see{" "}
          <code>/docs</code> for the OpenAPI schema.
        </div>
      </aside>

      {/* ── Document side ────────────────────────────────────────────────── */}
      <main className="stage">
        <header className="enter enter-1">
          <div className="hero-eyebrow">Repository flattener</div>
          <h1 className="hero-title">
            Every file you wrote,
            <br />
            <em>one document</em> to read it.
          </h1>
          <p className="hero-lede">
            Point at a codebase and get back a single markdown file: the
            directory tree drawn in full, then each source file inlined under its
            own heading and fenced with the right language tag. Built for handing
            a project to a model, a reviewer, or your future self.
          </p>
        </header>

        {selectedArchiveError && (
          <div className="alert alert-error enter enter-2" role="alert">
            <IconAlert className="alert-icon" />
            <div>
              <div className="alert-title">Archive is too large</div>
              {selectedArchiveError}
            </div>
          </div>
        )}

        {error && (
          <div className="alert alert-error enter enter-2" role="alert">
            <IconAlert className="alert-icon" />
            <div>
              <div className="alert-title">That did not work</div>
              {error}
            </div>
          </div>
        )}

        {showTree && (
          <div className="enter enter-2">
            <LiveTree
              discovered={discovered}
              finalLines={finalLines}
              rootName={rootName}
              running={running}
              progress={progress}
              currentPath={currentPath}
            />
          </div>
        )}

        {stats && <StatsStrip stats={stats} />}

        {markdown && jobId ? (
          <ResultPanel
            markdown={markdown}
            stats={stats}
            downloadHref={downloadUrl(jobId)}
            filename={filename}
            onCopied={setToast}
          />
        ) : (
          !running
          && !showTree && (
            <div className="panel enter enter-3">
              <div className="empty">
                <div className="empty-glyph">{EMPTY_GLYPH}</div>
                <div className="empty-title">Nothing converted yet</div>
                <p className="empty-text">
                  Pick a source — an archive, a folder on this machine, or a
                  public repository — then run the conversion.
                </p>
              </div>
            </div>
          )
        )}
      </main>

      {toast && (
        <div className="toast" role="status">
          <IconCheck size={14} />
          {toast}
        </div>
      )}
    </div>
  );
}
