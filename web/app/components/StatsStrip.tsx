"use client";

import type { ConversionStats } from "../lib/types";

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}

function formatDuration(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.max(1, ms)}ms`;
}

export default function StatsStrip({ stats }: { stats: ConversionStats }) {
  return (
    <div className="stats enter enter-1">
      <div className="stat">
        <div className="stat-value">{stats.files_included.toLocaleString()}</div>
        <div className="stat-label">Files in</div>
      </div>
      <div className="stat">
        <div className="stat-value stat-value-accent">1</div>
        <div className="stat-label">Document out</div>
      </div>
      <div className="stat">
        <div className="stat-value">{stats.total_lines.toLocaleString()}</div>
        <div className="stat-label">Lines</div>
      </div>
      <div className="stat">
        <div className="stat-value">{stats.directories.toLocaleString()}</div>
        <div className="stat-label">Folders</div>
      </div>
      <div className="stat">
        <div className="stat-value">{formatBytes(stats.markdown_bytes)}</div>
        <div className="stat-label">Markdown</div>
      </div>
      <div className="stat">
        <div className="stat-value">{formatDuration(stats.duration_ms)}</div>
        <div className="stat-label">Elapsed</div>
      </div>
    </div>
  );
}
