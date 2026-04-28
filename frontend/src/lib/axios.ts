import axios from "axios";
import type { AxiosError, InternalAxiosRequestConfig } from "axios";
import { API_BASE_URL, DEFAULT_TENANT_HEADER } from "../config/env";
import { ROUTES } from "../config/routes";
import { useAuthStore } from "../store/authStore";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
});

type RetryableRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
  _sessionRetry?: boolean;
  _skipAuthHeader?: boolean;
};

apiClient.interceptors.request.use((config) => {
  const { tokens, tenantSlug } = useAuthStore.getState();
  const retryableConfig = config as RetryableRequestConfig;

  if (typeof config.url === "string") {
    config.url = config.url.replace(/^\/api\/api\//, "/api/");
    if (typeof config.baseURL === "string" && config.baseURL.endsWith("/api") && config.url.startsWith("/api/")) {
      config.url = config.url.replace(/^\/api/, "");
    }
  }

  if (tokens?.access_token && !retryableConfig._skipAuthHeader) {
    config.headers.Authorization = `Bearer ${tokens.access_token}`;
  }

  if (tenantSlug) {
    config.headers[DEFAULT_TENANT_HEADER] = tenantSlug;
  }

  return config;
});

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const { tokens, user, setAuth, clearAuth } = useAuthStore.getState();
  if (!tokens?.refresh_token || !user) {
    return null;
  }

  try {
    const response = await apiClient.post<{ tokens: typeof tokens }>(
      "/api/auth/refresh",
      {},
      {
        headers: {
          Authorization: `Bearer ${tokens.refresh_token}`,
        },
      }
    );

    setAuth(response.data.tokens, user);
    return response.data.tokens.access_token;
  } catch {
    clearAuth();
    return null;
  }
}

function redirectToLogin() {
  if (typeof window !== "undefined") {
    window.location.assign(`${window.location.origin}/app${ROUTES.LOGIN}`);
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetryableRequestConfig | undefined;
    const responseStatus = error.response?.status;
    const requestUrl = originalRequest?.url || "";
    const hasAuthorizationHeader = Boolean(originalRequest?.headers?.Authorization);

    if (
      originalRequest &&
      responseStatus === 403 &&
      hasAuthorizationHeader &&
      !originalRequest._sessionRetry &&
      !requestUrl.includes("/api/auth/")
    ) {
      const nextRequest: RetryableRequestConfig = {
        ...originalRequest,
        _sessionRetry: true,
        _skipAuthHeader: true,
        headers: { ...originalRequest.headers },
      };

      delete nextRequest.headers.Authorization;
      return apiClient(nextRequest);
    }

    if (!originalRequest || responseStatus !== 401 || originalRequest._retry) {
      if (responseStatus === 401 && requestUrl.includes("/api/auth/")) {
        useAuthStore.getState().clearAuth();
        redirectToLogin();
      }
      return Promise.reject(error);
    }

    if (requestUrl.includes("/api/auth/login") || requestUrl.includes("/api/auth/refresh")) {
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    if (!refreshPromise) {
      refreshPromise = refreshAccessToken().finally(() => {
        refreshPromise = null;
      });
    }

    const nextAccessToken = await refreshPromise;
    if (!nextAccessToken) {
      redirectToLogin();
      return Promise.reject(error);
    }

    originalRequest.headers = originalRequest.headers || {};
    originalRequest.headers.Authorization = `Bearer ${nextAccessToken}`;
    return apiClient(originalRequest);
  }
);
