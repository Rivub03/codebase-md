"use client";

import type { ConvertOptions, PathStyle, SectionMode } from "../lib/types";

interface Props {
  options: ConvertOptions;
  onChange: (patch: Partial<ConvertOptions>) => void;
  maxFileKbCeiling: number;
  disabled: boolean;
}

function Toggle({
  label,
  note,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  note: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled: boolean;
}) {
  return (
    <label className="toggle-row">
      <span className="toggle-text">
        {label}
        <span className="toggle-note">{note}</span>
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        className={`switch${checked ? " switch-on" : ""}`}
        onClick={() => onChange(!checked)}
        disabled={disabled}
      />
    </label>
  );
}

export default function OptionsPanel({
  options,
  onChange,
  maxFileKbCeiling,
  disabled,
}: Props) {
  return (
    <section>
      <div className="rail-label">Options</div>

      <Toggle
        label="Respect .gitignore"
        note="Skip whatever the repo already ignores"
        checked={options.use_gitignore}
        onChange={(value) => onChange({ use_gitignore: value })}
        disabled={disabled}
      />
      <Toggle
        label="Include hidden files"
        note="Dotfiles and dot-directories"
        checked={options.include_hidden}
        onChange={(value) => onChange({ include_hidden: value })}
        disabled={disabled}
      />
      <Toggle
        label="Include tests"
        note="Test directories and *.test.* files"
        checked={options.include_tests}
        onChange={(value) => onChange({ include_tests: value })}
        disabled={disabled}
      />
      <Toggle
        label="Include lockfiles"
        note="package-lock, poetry.lock, and friends"
        checked={options.include_lockfiles}
        onChange={(value) => onChange({ include_lockfiles: value })}
        disabled={disabled}
      />
      <Toggle
        label="Annotate the tree"
        note="Add ← notes beside familiar filenames"
        checked={options.annotate_tree}
        onChange={(value) => onChange({ annotate_tree: value })}
        disabled={disabled}
      />
      <Toggle
        label="Structure only"
        note="Directory tree with no file contents"
        checked={options.include_tree_only}
        onChange={(value) => onChange({ include_tree_only: value })}
        disabled={disabled}
      />

      <div className="field">
        <label className="field-label" htmlFor="section-mode">
          Section grouping
        </label>
        <select
          id="section-mode"
          className="select"
          value={options.section_mode}
          onChange={(event) =>
            onChange({ section_mode: event.target.value as SectionMode })
          }
          disabled={disabled}
        >
          <option value="auto">Detect roles — Backend, Frontend, …</option>
          <option value="toplevel">One per top-level folder</option>
          <option value="single">One section for everything</option>
        </select>
      </div>

      <div className="field">
        <label className="field-label" htmlFor="path-style">
          File headings
        </label>
        <select
          id="path-style"
          className="select"
          value={options.path_style}
          onChange={(event) =>
            onChange({ path_style: event.target.value as PathStyle })
          }
          disabled={disabled}
        >
          <option value="section">Relative to the section — app/core/config.py</option>
          <option value="full">Full path — api/app/core/config.py</option>
        </select>
      </div>

      <div className="field">
        <div className="range-head">
          <label className="field-label" htmlFor="max-kb" style={{ margin: 0 }}>
            Largest file inlined
          </label>
          <span className="range-value">{options.max_file_kb} KB</span>
        </div>
        <input
          id="max-kb"
          className="range"
          type="range"
          min={16}
          max={Math.min(2048, maxFileKbCeiling)}
          step={16}
          value={options.max_file_kb}
          onChange={(event) =>
            onChange({ max_file_kb: Number(event.target.value) })
          }
          disabled={disabled}
        />
      </div>

      <div className="field">
        <div className="range-head">
          <label className="field-label" htmlFor="max-lines" style={{ margin: 0 }}>
            Line cap per file
          </label>
          <span className="range-value">
            {options.max_lines_per_file.toLocaleString()}
          </span>
        </div>
        <input
          id="max-lines"
          className="range"
          type="range"
          min={100}
          max={10000}
          step={100}
          value={options.max_lines_per_file}
          onChange={(event) =>
            onChange({ max_lines_per_file: Number(event.target.value) })
          }
          disabled={disabled}
        />
      </div>

      <div className="field">
        <label className="field-label" htmlFor="only-ext">
          Only these extensions — optional
        </label>
        <input
          id="only-ext"
          className="input"
          placeholder=".py, .ts, .tsx"
          value={options.include_extensions.join(", ")}
          onChange={(event) =>
            onChange({
              include_extensions: event.target.value
                .split(",")
                .map((item) => item.trim())
                .filter(Boolean),
            })
          }
          disabled={disabled}
          spellCheck={false}
        />
      </div>

      <div className="field">
        <label className="field-label" htmlFor="exclude">
          Also ignore — gitignore patterns
        </label>
        <input
          id="exclude"
          className="input"
          placeholder="docs/**, *.snap"
          value={options.exclude_globs.join(", ")}
          onChange={(event) =>
            onChange({
              exclude_globs: event.target.value
                .split(",")
                .map((item) => item.trim())
                .filter(Boolean),
            })
          }
          disabled={disabled}
          spellCheck={false}
        />
      </div>

      <div className="field">
        <label className="field-label" htmlFor="preamble">
          Opening line — optional
        </label>
        <input
          id="preamble"
          className="input"
          placeholder="This is the current implemented codebase…"
          value={options.preamble ?? ""}
          onChange={(event) => onChange({ preamble: event.target.value || null })}
          disabled={disabled}
        />
      </div>
    </section>
  );
}
