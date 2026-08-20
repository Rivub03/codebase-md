"use client";

import { useEffect, useMemo, useRef } from "react";
import { IconTree } from "./Icons";

interface Props {
  /** Paths discovered so far, in the order the scanner found them. */
  discovered: string[];
  /** Authoritative tree lines from the server, once the scan completes. */
  finalLines: string[] | null;
  rootName: string;
  running: boolean;
  progress: number;
  currentPath: string;
}

interface TreeNode {
  name: string;
  isDir: boolean;
  children: Map<string, TreeNode>;
}

/** Rebuild a tree from the flat paths streamed over SSE. */
function buildTree(paths: string[]): TreeNode {
  const root: TreeNode = { name: "", isDir: true, children: new Map() };

  for (const raw of paths) {
    const isDir = raw.endsWith("/");
    const parts = raw.replace(/\/+$/, "").split("/").filter(Boolean);
    let cursor = root;

    parts.forEach((part, index) => {
      const last = index === parts.length - 1;
      let next = cursor.children.get(part);
      if (!next) {
        next = { name: part, isDir: !last || isDir, children: new Map() };
        cursor.children.set(part, next);
      }
      // A path seen first as a parent segment is a directory regardless of
      // whether the scanner has emitted its own entry yet.
      if (!last) next.isDir = true;
      cursor = next;
    });
  }

  return root;
}

function renderTree(node: TreeNode, prefix: string, out: string[]): void {
  const children = [...node.children.values()].sort((a, b) => {
    if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
    return a.name.toLowerCase().localeCompare(b.name.toLowerCase());
  });

  children.forEach((child, index) => {
    const last = index === children.length - 1;
    out.push(`${prefix}${last ? "└── " : "├── "}${child.name}${child.isDir ? "/" : ""}`);
    if (child.children.size > 0) {
      renderTree(child, prefix + (last ? "    " : "│   "), out);
    }
  });
}

/**
 * Split a tree line into its connector glyphs, its name, and any '←' note, so
 * each part can be tinted separately. Reading the shape of a tree depends on
 * the connectors standing apart from the names.
 */
function TreeLine({ text, isLast }: { text: string; isLast: boolean }) {
  const match = text.match(/^([│├└─\s|+`]*)(.*)$/);
  const glyphs = match?.[1] ?? "";
  const rest = match?.[2] ?? text;

  const noteAt = rest.indexOf("←");
  const body = noteAt >= 0 ? rest.slice(0, noteAt) : rest;
  const note = noteAt >= 0 ? rest.slice(noteAt) : "";
  const isDir = body.trimEnd().endsWith("/");

  return (
    <span className="tree-line">
      <span className="tree-glyph">{glyphs}</span>
      <span className={isDir ? "tree-dir" : "tree-file"}>{body}</span>
      {note && <span className="tree-note">{note}</span>}
      {isLast && <span className="tree-caret" aria-hidden="true" />}
    </span>
  );
}

export default function LiveTree({
  discovered,
  finalLines,
  rootName,
  running,
  progress,
  currentPath,
}: Props) {
  const bodyRef = useRef<HTMLDivElement>(null);

  const lines = useMemo(() => {
    if (finalLines && finalLines.length > 0) return finalLines;
    if (discovered.length === 0) return [];
    const out: string[] = [`${rootName || "codebase"}/`];
    renderTree(buildTree(discovered), "", out);
    return out;
  }, [discovered, finalLines, rootName]);

  // Follow the frontier while the scan streams, then return to the root once
  // the final tree lands so the reader starts where the structure starts.
  useEffect(() => {
    if (!bodyRef.current) return;
    if (running) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    } else if (finalLines) {
      bodyRef.current.scrollTop = 0;
    }
  }, [lines.length, running, finalLines]);

  const fileCount = useMemo(
    () => lines.filter((line) => !line.trimEnd().endsWith("/")).length,
    [lines],
  );

  return (
    <div className="tree-panel">
      <div className="tree-head">
        <span className="tree-head-title">
          <IconTree />
          Directory structure
        </span>
        <span className="tree-counter">
          {running ? (
            <>
              <span className="pulse pulse-live" style={{ display: "inline-block", marginRight: 7 }} />
              scanning… {lines.length.toLocaleString()} entries
            </>
          ) : lines.length > 0 ? (
            `${fileCount.toLocaleString()} files · ${(lines.length - fileCount).toLocaleString()} folders`
          ) : (
            "idle"
          )}
        </span>
      </div>

      <div className="tree-body" ref={bodyRef} aria-live="polite" aria-atomic="false">
        {lines.length === 0 ? (
          <div className="tree-empty">
            The tree appears here as the scan walks your codebase.
          </div>
        ) : (
          lines.map((line, index) => (
            <TreeLine
              key={`${index}-${line}`}
              text={line}
              isLast={running && index === lines.length - 1}
            />
          ))
        )}
      </div>

      {running && (
        <>
          <div className="progress">
            <div
              className="progress-fill"
              style={{ width: `${Math.round(progress * 100)}%` }}
            />
          </div>
          <div className="progress-path" title={currentPath}>
            {currentPath || "…"}
          </div>
        </>
      )}
    </div>
  );
}
