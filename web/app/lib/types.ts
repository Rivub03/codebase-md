export type SectionMode = "auto" | "toplevel" | "single";
export type PathStyle = "section" | "full";
export type JobState = "queued" | "running" | "done" | "error";
export type SourceKind = "upload" | "path" | "remote";

export interface ConvertOptions {
  title?: string | null;
  preamble?: string | null;
  section_mode: SectionMode;
  path_style: PathStyle;
  use_gitignore: boolean;
  include_hidden: boolean;
  include_lockfiles: boolean;
  include_tests: boolean;
  include_tree_only: boolean;
  max_file_kb: number;
  max_lines_per_file: number;
  truncate_long_files: boolean;
  include_extensions: string[];
  exclude_globs: string[];
  annotate_tree: boolean;
  include_stats: boolean;
  collapse_empty_dirs: boolean;
}

export interface LanguageStat {
  language: string;
  files: number;
  lines: number;
  bytes: number;
}

export interface SectionSummary {
  name: string;
  root: string;
  files: number;
  lines: number;
}

export interface ConversionStats {
  root_name: string;
  total_files_seen: number;
  files_included: number;
  files_skipped_binary: number;
  files_skipped_ignored: number;
  files_skipped_too_large: number;
  files_truncated: number;
  directories: number;
  total_lines: number;
  total_bytes: number;
  markdown_bytes: number;
  markdown_lines: number;
  duration_ms: number;
  languages: LanguageStat[];
  sections: SectionSummary[];
}

export interface JobStatus {
  job_id: string;
  status: JobState;
  source_label: string;
  created_at: number;
  finished_at: number | null;
  progress: number;
  message: string;
  error: string | null;
  stats: ConversionStats | null;
  filename: string | null;
}

export interface ProgressEvent {
  type: "status" | "tree" | "file" | "done" | "error";
  message: string;
  progress: number;
  payload?: {
    path?: string;
    kind?: "file" | "dir";
    lines?: string[];
    stats?: ConversionStats;
    filename?: string;
    preview?: string;
  } | null;
}

export interface Capabilities {
  allow_local_path: boolean;
  allow_remote_fetch: boolean;
  max_archive_mb: number;
  max_files: number;
  max_file_kb_default: number;
  max_file_kb_ceiling: number;
  has_github_token: boolean;
}

export const DEFAULT_OPTIONS: ConvertOptions = {
  title: null,
  preamble: null,
  section_mode: "auto",
  path_style: "section",
  use_gitignore: true,
  include_hidden: false,
  include_lockfiles: false,
  include_tests: true,
  include_tree_only: false,
  max_file_kb: 400,
  max_lines_per_file: 4000,
  truncate_long_files: true,
  include_extensions: [],
  exclude_globs: [],
  annotate_tree: true,
  include_stats: true,
  collapse_empty_dirs: true,
};
