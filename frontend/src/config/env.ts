export const APP_BASE_PATH = "/app";

export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() || "";

export const DEFAULT_TENANT_HEADER =
  (import.meta.env.VITE_TENANT_HEADER as string | undefined)?.trim() ||
  "X-Tenant-Slug";
