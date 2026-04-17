export const APP_BASE_PATH = "/app";

const rawApiBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() || "";
const normalizedApiBaseUrl = rawApiBaseUrl.replace(/\/+$/, "").replace(/\/api$/, "");

export const API_BASE_URL = normalizedApiBaseUrl;

export const DEFAULT_TENANT_HEADER =
  (import.meta.env.VITE_TENANT_HEADER as string | undefined)?.trim() ||
  "X-Tenant-Slug";
