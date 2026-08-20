import type {
  Capabilities,
  ConvertOptions,
  JobStatus,
  ProgressEvent,
} from "./types";

// Blank means "same origin" — requests go through the Next.js proxy defined in
// next.config.ts. Set NEXT_PUBLIC_API_URL to bypass it and call FastAPI direct.
const BASE = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/+$/, "");

const url = (path: string) => `${BASE}${path}`;

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail)) {
      return body.detail.map((d: { msg?: string }) => d.msg ?? "").join("; ");
    }
  } catch {
    /* fall through to the status text */
  }
  return response.statusText || `Request failed (${response.status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url(path), init);
  if (!response.ok) {
    throw new ApiError(await readError(response), response.status);
  }
  return (await response.json()) as T;
}

export function getCapabilities(): Promise<Capabilities> {
  return request<Capabilities>("/api/capabilities");
}

export function convertUpload(
  file: File,
  options: ConvertOptions,
): Promise<{ job_id: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("options", JSON.stringify(options));
  return request<{ job_id: string }>("/api/convert/upload", {
    method: "POST",
    body: form,
  });
}

export function convertPath(
  path: string,
  options: ConvertOptions,
): Promise<{ job_id: string }> {
  return request<{ job_id: string }>("/api/convert/path", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, options }),
  });
}

export function convertRemote(
  repoUrl: string,
  ref: string | null,
  options: ConvertOptions,
): Promise<{ job_id: string }> {
  return request<{ job_id: string }>("/api/convert/remote", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: repoUrl, ref: ref || null, options }),
  });
}

export function getJob(jobId: string): Promise<JobStatus> {
  return request<JobStatus>(`/api/jobs/${jobId}`);
}

export async function getMarkdown(jobId: string): Promise<string> {
  const response = await fetch(url(`/api/jobs/${jobId}/markdown`));
  if (!response.ok) throw new ApiError(await readError(response), response.status);
  return response.text();
}

export function downloadUrl(jobId: string): string {
  return url(`/api/jobs/${jobId}/download`);
}

/**
 * Subscribe to a job's progress stream.
 *
 * EventSource is used rather than a fetch/ReadableStream loop because it
 * reconnects on its own and the endpoint is a plain GET. Returns a function
 * that closes the connection.
 */
export function streamProgress(
  jobId: string,
  handlers: {
    onEvent: (event: ProgressEvent) => void;
    onError?: (message: string) => void;
  },
): () => void {
  const source = new EventSource(url(`/api/jobs/${jobId}/events`));
  let finished = false;

  source.onmessage = (message) => {
    try {
      const event = JSON.parse(message.data) as ProgressEvent;
      handlers.onEvent(event);
      if (event.type === "done" || event.type === "error") {
        finished = true;
        source.close();
      }
    } catch {
      /* ignore malformed frames — the next one usually arrives fine */
    }
  };

  source.onerror = () => {
    // A close after the terminal event is expected, not a failure.
    if (finished) return;
    source.close();
    handlers.onError?.("Lost the connection to the server.");
  };

  return () => {
    finished = true;
    source.close();
  };
}
