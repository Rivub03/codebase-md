"use client";

import { useMemo, useState } from "react";
import type { ConversionStats } from "../lib/types";
import { IconCheck, IconCopy, IconDoc, IconDownload } from "./Icons";

type View = "document" | "outline" | "breakdown";

interface Props {
  markdown: string;
  stats: ConversionStats | null;
  downloadHref: string;
  filename: string;
  onCopied: (message: string) => void;
}

/**
 * Classify one line of the generated document for tinting. This is deliberately
 * not a markdown parser — it only needs to make the structure scannable, and a
 * real parser would fight the fenced source code inside every section.
 */
function classify(line: string, insideFence: boolean): string {
  if (/^`{3,}/.test(line)) return "doc-fence";
  if (insideFence) {
    return /^[│├└─\s]*[├└]── /.test(line) || /^[\w.\-]+\/$/.test(line)
      ? "doc-tree"
      : "doc-code";
  }
  if (/^#{1,6}\s/.test(line)) return "doc-h";
  if (/^>\s/.test(line)) return "doc-quote";
  return "";
}

function useOutline(markdown: string) {
  return useMemo(() => {
    const entries: { level: number; text: string }[] = [];
    let insideFence = false;

    for (const line of markdown.split("\n")) {
      if (/^`{3,}/.test(line)) {
        insideFence = !insideFence;
        continue;
      }
      if (insideFence) continue;
      const match = line.match(/^(#{1,6})\s+(.*)$/);
      if (match) {
        entries.push({
          level: match[1].length,
          text: match[2].replace(/`/g, ""),
        });
      }
    }
    return entries;
  }, [markdown]);
}

export default function ResultPanel({
  markdown,
  stats,
  downloadHref,
  filename,
  onCopied,
}: Props) {
  const [view, setView] = useState<View>("document");
  const [copied, setCopied] = useState(false);

  const outline = useOutline(markdown);

  // Rendering 20k+ lines as separate nodes stalls the browser, so the preview
  // is capped and the full document stays one click away via Download.
  const PREVIEW_LIMIT = 3000;
  const allLines = useMemo(() => markdown.split("\n"), [markdown]);
  const lines = useMemo(() => allLines.slice(0, PREVIEW_LIMIT), [allLines]);

  const classified = useMemo(() => {
    let insideFence = false;
    return lines.map((line) => {
      const className = classify(line, insideFence);
      if (/^`{3,}/.test(line)) insideFence = !insideFence;
      return className;
    });
  }, [lines]);

  const maxLangLines = stats?.languages[0]?.lines ?? 1;

  async function copy() {
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      onCopied("Markdown copied to the clipboard");
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      onCopied("Your browser blocked clipboard access — use Download instead");
    }
  }

  return (
    <div className="panel enter enter-3">
      <div className="panel-head">
        <div className="view-tabs" role="tablist" aria-label="Result view">
          <button
            type="button"
            role="tab"
            aria-selected={view === "document"}
            className={`view-tab${view === "document" ? " view-tab-active" : ""}`}
            onClick={() => setView("document")}
          >
            Document
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={view === "outline"}
            className={`view-tab${view === "outline" ? " view-tab-active" : ""}`}
            onClick={() => setView("outline")}
          >
            Outline
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={view === "breakdown"}
            className={`view-tab${view === "breakdown" ? " view-tab-active" : ""}`}
            onClick={() => setView("breakdown")}
          >
            Breakdown
          </button>
        </div>

        <div className="actions">
          <button type="button" className="btn" onClick={copy}>
            {copied ? <IconCheck /> : <IconCopy />}
            {copied ? "Copied" : "Copy"}
          </button>
          <a className="btn btn-primary" href={downloadHref} download={filename}>
            <IconDownload />
            Download {filename}
          </a>
        </div>
      </div>

      {view === "document" && (
        <div className="doc">
          {lines.map((line, index) => (
            <div className="doc-line" key={index}>
              <span className="doc-num">{index + 1}</span>
              <span className={`doc-text ${classified[index]}`}>
                {line || "\u00A0"}
              </span>
            </div>
          ))}
          {allLines.length > PREVIEW_LIMIT && (
            <div className="doc-line">
              <span className="doc-num">…</span>
              <span className="doc-text doc-quote">
                Preview stops at {PREVIEW_LIMIT.toLocaleString()} lines.
                Download the file for all {allLines.length.toLocaleString()}.
              </span>
            </div>
          )}
        </div>
      )}

      {view === "outline" && (
        <div className="outline">
          {outline.map((entry, index) => (
            <div
              className={`outline-item outline-h${entry.level}`}
              key={index}
              style={{ paddingLeft: 20 + (entry.level - 2) * 16 }}
            >
              <span className="outline-level">H{entry.level}</span>
              <span className="outline-text">{entry.text}</span>
            </div>
          ))}
        </div>
      )}

      {view === "breakdown" && stats && (
        <div className="panel-body">
          <div className="lang-list">
            {stats.languages.slice(0, 12).map((language) => (
              <div className="lang-row" key={language.language}>
                <span className="lang-name">{language.language}</span>
                <span className="lang-track">
                  <span
                    className="lang-fill"
                    style={{
                      width: `${Math.max(2, (language.lines / maxLangLines) * 100)}%`,
                    }}
                  />
                </span>
                <span className="lang-count">
                  {language.lines.toLocaleString()} ln
                </span>
              </div>
            ))}
          </div>

          {stats.sections.length > 0 && (
            <div className="chips">
              {stats.sections.map((section) => (
                <span className="chip" key={section.name}>
                  <IconDoc size={12} />
                  {section.name}
                  <span className="chip-count">{section.files} files</span>
                </span>
              ))}
            </div>
          )}

          {(stats.files_skipped_binary > 0
            || stats.files_skipped_too_large > 0
            || stats.files_truncated > 0) && (
            <p
              style={{
                marginTop: 18,
                fontSize: 12.5,
                color: "var(--muted)",
                lineHeight: 1.6,
              }}
            >
              Left out: {stats.files_skipped_binary.toLocaleString()} binary,{" "}
              {stats.files_skipped_too_large.toLocaleString()} over the size limit,{" "}
              {stats.files_skipped_ignored.toLocaleString()} filtered by rules.{" "}
              {stats.files_truncated.toLocaleString()} truncated at the line cap.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
