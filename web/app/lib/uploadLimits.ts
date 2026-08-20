export const BYTES_PER_MB = 1024 * 1024;
export const LARGE_ARCHIVE_WARNING_MB = 20;
export const LARGE_ARCHIVE_WARNING_BYTES = LARGE_ARCHIVE_WARNING_MB * BYTES_PER_MB;

export function bytesFromMegabytes(megabytes: number): number {
  return megabytes * BYTES_PER_MB;
}

export function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * BYTES_PER_MB) {
    return `${(bytes / 1024 / BYTES_PER_MB).toFixed(2)} GB`;
  }

  if (bytes >= BYTES_PER_MB) {
    return `${(bytes / BYTES_PER_MB).toFixed(1)} MB`;
  }

  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
