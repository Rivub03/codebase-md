"use client";

import { useCallback, useRef, useState } from "react";
import type { Capabilities, SourceKind } from "../lib/types";
import {
  IconArchive,
  IconClose,
  IconFolder,
  IconGit,
  IconUpload,
} from "./Icons";

const ARCHIVE_TYPES = ".zip,.tar,.tar.gz,.tgz,.tar.bz2,.tar.xz";

interface Props {
  kind: SourceKind;
  onKindChange: (kind: SourceKind) => void;
  file: File | null;
  onFileChange: (file: File | null) => void;
  localPath: string;
  onLocalPathChange: (value: string) => void;
  repoUrl: string;
  onRepoUrlChange: (value: string) => void;
  repoRef: string;
  onRepoRefChange: (value: string) => void;
  capabilities: Capabilities | null;
  disabled: boolean;
}

export default function SourcePanel({
  kind,
  onKindChange,
  file,
  onFileChange,
  localPath,
  onLocalPathChange,
  repoUrl,
  onRepoUrlChange,
  repoRef,
  onRepoRefChange,
  capabilities,
  disabled,
}: Props) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      setDragging(false);
      const dropped = event.dataTransfer.files?.[0];
      if (dropped) onFileChange(dropped);
    },
    [onFileChange],
  );

  const sizeLabel = file
    ? file.size > 1024 * 1024
      ? `${(file.size / 1024 / 1024).toFixed(1)} MB`
      : `${Math.max(1, Math.round(file.size / 1024))} KB`
    : "";

  return (
    <section>
      <div className="rail-label">Source</div>

      <div className="tabs" role="tablist" aria-label="Where the codebase comes from">
        <button
          type="button"
          role="tab"
          aria-selected={kind === "upload"}
          className={`tab${kind === "upload" ? " tab-active" : ""}`}
          onClick={() => onKindChange("upload")}
          disabled={disabled}
        >
          <IconArchive size={14} />
          Archive
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={kind === "path"}
          className={`tab${kind === "path" ? " tab-active" : ""}`}
          onClick={() => onKindChange("path")}
          disabled={disabled || capabilities?.allow_local_path === false}
          title={
            capabilities?.allow_local_path === false
              ? "Local paths are turned off on this server"
              : undefined
          }
        >
          <IconFolder size={14} />
          Folder
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={kind === "remote"}
          className={`tab${kind === "remote" ? " tab-active" : ""}`}
          onClick={() => onKindChange("remote")}
          disabled={disabled || capabilities?.allow_remote_fetch === false}
          title={
            capabilities?.allow_remote_fetch === false
              ? "Remote fetching is turned off on this server"
              : undefined
          }
        >
          <IconGit size={14} />
          Repo
        </button>
      </div>

      {kind === "upload" && (
        <>
          <input
            ref={inputRef}
            type="file"
            accept={ARCHIVE_TYPES}
            hidden
            onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
          />
          <div
            className={`dropzone${dragging ? " dropzone-over" : ""}`}
            role="button"
            tabIndex={0}
            onClick={() => !disabled && inputRef.current?.click()}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                inputRef.current?.click();
              }
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
          >
            {file ? (
              <div className="dropzone-file">
                <IconArchive size={17} className="dropzone-icon" />
                <div>
                  <div className="dropzone-file-name">{file.name}</div>
                  <div className="dropzone-hint">{sizeLabel}</div>
                </div>
                <button
                  type="button"
                  className="tab"
                  aria-label="Remove the selected archive"
                  onClick={(event) => {
                    event.stopPropagation();
                    onFileChange(null);
                    if (inputRef.current) inputRef.current.value = "";
                  }}
                >
                  <IconClose />
                </button>
              </div>
            ) : (
              <>
                <IconUpload className="dropzone-icon" />
                <div className="dropzone-title">Drop an archive, or browse</div>
                <div className="dropzone-hint">
                  zip · tar · tar.gz
                  {capabilities ? ` · up to ${capabilities.max_archive_mb} MB` : ""}
                </div>
              </>
            )}
          </div>
        </>
      )}

      {kind === "path" && (
        <div className="field">
          <label className="field-label" htmlFor="local-path">
            Directory on the machine running the API
          </label>
          <input
            id="local-path"
            className="input"
            placeholder="/home/you/projects/my-app"
            value={localPath}
            onChange={(event) => onLocalPathChange(event.target.value)}
            disabled={disabled}
            spellCheck={false}
            autoComplete="off"
          />
          <p className="field-hint">
            Fastest option when the API runs on your own machine — nothing is
            uploaded or copied.
          </p>
        </div>
      )}

      {kind === "remote" && (
        <>
          <div className="field">
            <label className="field-label" htmlFor="repo-url">
              GitHub repository
            </label>
            <input
              id="repo-url"
              className="input"
              placeholder="https://github.com/owner/repo"
              value={repoUrl}
              onChange={(event) => onRepoUrlChange(event.target.value)}
              disabled={disabled}
              spellCheck={false}
              autoComplete="off"
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="repo-ref">
              Branch, tag, or commit — optional
            </label>
            <input
              id="repo-ref"
              className="input"
              placeholder="main"
              value={repoRef}
              onChange={(event) => onRepoRefChange(event.target.value)}
              disabled={disabled}
              spellCheck={false}
              autoComplete="off"
            />
            <p className="field-hint">
              {capabilities?.has_github_token
                ? "A token is configured, so private repositories work too."
                : "Public repositories only. Set GITHUB_TOKEN on the API to raise the rate limit."}
            </p>
          </div>
        </>
      )}
    </section>
  );
}
