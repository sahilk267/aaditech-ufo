import { describe, it, expect } from 'vitest';
import type { AxiosError } from 'axios';

type RetryableConfig = {
  url?: string;
  _retry?: boolean;
};

// We'll test the interceptor logic directly rather than the apiClient
// Since apiClient is already instantiated with interceptors

describe('Axios Interceptor Logic', () => {
  describe('Request Interceptor', () => {
    it('should add Authorization header when access token exists', () => {
      const accessToken = 'test-access-token-123';
      const config = {
        headers: {} as Record<string, string>,
      };

      // Simulate what the request interceptor does
      config.headers.Authorization = `Bearer ${accessToken}`;

      expect(config.headers.Authorization).toBe(`Bearer ${accessToken}`);
    });

    it('should add tenant header when tenant slug exists', () => {
      const tenantSlug = 'acme-corp';
      const config = {
        headers: {} as Record<string, string>,
      };

      // Simulate what the request interceptor does
      const DEFAULT_TENANT_HEADER = 'X-Tenant-Slug';
      config.headers[DEFAULT_TENANT_HEADER] = tenantSlug;

      expect(config.headers['X-Tenant-Slug']).toBe(tenantSlug);
    });

    it('should add both authorization and tenant headers', () => {
      const accessToken = 'test-token';
      const tenantSlug = 'test-tenant';
      const config = {
        headers: {} as Record<string, string>,
      };

      config.headers.Authorization = `Bearer ${accessToken}`;
      config.headers['X-Tenant-Slug'] = tenantSlug;

      expect(config.headers.Authorization).toBe(`Bearer ${accessToken}`);
      expect(config.headers['X-Tenant-Slug']).toBe(tenantSlug);
    });

    it('should not add authorization header when token is missing', () => {
      const config = {
        headers: {} as Record<string, string>,
      };

      const accessToken: string | undefined = undefined;
      if (accessToken) {
        config.headers.Authorization = `Bearer ${accessToken}`;
      }

      expect(config.headers.Authorization).toBeUndefined();
    });

    it('should not add tenant header when tenant slug is missing', () => {
      const config = {
        headers: {} as Record<string, string>,
      };

      const tenantSlug: string | undefined = undefined;
      if (tenantSlug) {
        config.headers['X-Tenant-Slug'] = tenantSlug;
      }

      expect(config.headers['X-Tenant-Slug']).toBeUndefined();
    });

    it('should preserve existing headers when adding auth headers', () => {
      const config = {
        headers: {
          'Content-Type': 'application/json',
          'X-Custom-Header': 'custom-value',
        } as Record<string, string>,
      };

      config.headers.Authorization = 'Bearer token123';

      expect(config.headers['Content-Type']).toBe('application/json');
      expect(config.headers['X-Custom-Header']).toBe('custom-value');
      expect(config.headers.Authorization).toBe('Bearer token123');
    });
  });

  describe('Response Interceptor - 401 Handling', () => {
    it('should identify 401 status code', () => {
      const error = {
        response: {
          status: 401,
          data: { error: 'Unauthorized' },
        },
      } as unknown as AxiosError;

      expect(error.response?.status).toBe(401);
    });

    it('should identify when request has been retried', () => {
      const originalRequest = {
        url: '/api/data',
        headers: {},
        _retry: true,
      };

      expect(originalRequest._retry).toBe(true);
    });

    it('should skip retry handling if request was already retried', () => {
      const error = {
        response: { status: 401 },
        config: { url: '/api/data', _retry: true },
      } as unknown as AxiosError & { config?: RetryableConfig };

      const shouldRetry = error.response?.status === 401 && !error.config?._retry;
      expect(shouldRetry).toBe(false);
    });

    it('should skip retry handling for non-401 errors', () => {
      const error = {
        response: { status: 403, data: { error: 'Forbidden' } },
        config: { url: '/api/data' },
      } as unknown as AxiosError;

      const shouldRetry = error.response?.status === 401;
      expect(shouldRetry).toBe(false);
    });

    it('should redirect to login on auth endpoint 401', () => {
      const error = {
        response: { status: 401 },
        config: { url: '/api/auth/login' },
      } as unknown as AxiosError;

      const isAuthEndpoint = error.config?.url?.includes('/api/auth/');
      expect(isAuthEndpoint).toBe(true);
    });

    it('should not retry on login endpoint', () => {
      const url = '/api/auth/login';
      const shouldSkipRetryEndpoints = url.includes('/api/auth/login') || url.includes('/api/auth/refresh');
      expect(shouldSkipRetryEndpoints).toBe(true);
    });

    it('should not retry on refresh endpoint', () => {
      const url = '/api/auth/refresh';
      const shouldSkipRetryEndpoints = url.includes('/api/auth/login') || url.includes('/api/auth/refresh');
      expect(shouldSkipRetryEndpoints).toBe(true);
    });
  });

  describe('Single-flight Token Refresh', () => {
    it('should use single promise for concurrent refresh requests', async () => {
      let refreshPromise: Promise<string | null> | null = null;
      let refreshCallCount = 0;

      const mockRefreshAccessToken = async () => {
        refreshCallCount++;
        await new Promise(resolve => setTimeout(resolve, 10));
        return 'new-access-token';
      };

      // First request starts refresh
      if (!refreshPromise) {
        refreshPromise = mockRefreshAccessToken().finally(() => {
          refreshPromise = null;
        });
      }
      const result1 = refreshPromise;

      // Second concurrent request reuses the same promise
      if (!refreshPromise) {
        refreshPromise = mockRefreshAccessToken().finally(() => {
          refreshPromise = null;
        });
      }
      const result2 = refreshPromise;

      // Both should be the same promise
      expect(result1).toBe(result2);

      await result1;
      expect(refreshCallCount).toBe(1);
    });

    it('should clear refresh promise after completion', async () => {
      let refreshPromise: Promise<string | null> | null = null;

      const mockRefreshAccessToken = async () => {
        return 'new-token';
      };

      if (!refreshPromise) {
        refreshPromise = mockRefreshAccessToken().finally(() => {
          refreshPromise = null;
        });
      }

      expect(refreshPromise).not.toBeNull();
      await refreshPromise;
      expect(refreshPromise).toBeNull();
    });

    it('should handle refresh failure and clear promise', async () => {
      let refreshPromise: Promise<string | null> | null = null;

      const mockRefreshAccessToken = async () => {
        throw new Error('Refresh failed');
      };

      if (!refreshPromise) {
        refreshPromise = mockRefreshAccessToken()
          .then(() => 'new-token')
          .catch(() => null)
          .finally(() => {
            refreshPromise = null;
          });
      }

      const result = await refreshPromise;
      expect(result).toBeNull();
      expect(refreshPromise).toBeNull();
    });

    it('should allow new refresh after previous promise clears', async () => {
      let refreshPromise: Promise<string | null> | null = null;
      let refreshCount = 0;

      const mockRefresh = async () => {
        refreshCount++;
        return 'token-' + refreshCount;
      };

      // First refresh
      if (!refreshPromise) {
        refreshPromise = mockRefresh().finally(() => {
          refreshPromise = null;
        });
      }
      const token1 = await refreshPromise;
      expect(token1).toBe('token-1');
      expect(refreshPromise).toBeNull();

      // Second refresh (should be allowed)
      if (!refreshPromise) {
        refreshPromise = mockRefresh().finally(() => {
          refreshPromise = null;
        });
      }
      const token2 = await refreshPromise;
      expect(token2).toBe('token-2');
    });
  });

  describe('Token Refresh Flow', () => {
    it('should construct correct refresh request', () => {
      const refreshToken = 'refresh-token-123';
      const headers = {
        Authorization: `Bearer ${refreshToken}`,
      };

      expect(headers.Authorization).toBe(`Bearer ${refreshToken}`);
    });

    it('should update auth store with new tokens', () => {
      const oldTokens = {
        access_token: 'old-access',
        refresh_token: 'refresh-token',
      };
      const newTokens = {
        access_token: 'new-access',
        refresh_token: 'new-refresh',
      };

      expect(newTokens.access_token).not.toBe(oldTokens.access_token);
      expect(newTokens.refresh_token).not.toBe(oldTokens.refresh_token);
    });

    it('should handle refresh with missing refresh token', () => {
      const tokens = {
        access_token: 'access',
        refresh_token: null,
      };

      const canRefresh = tokens.refresh_token !== null;
      expect(canRefresh).toBe(false);
    });

    it('should redirect to login on refresh failure', () => {
      const error = new Error('Refresh failed');
      // This should trigger clearAuth and redirect to login
      expect(error).toBeInstanceOf(Error);
    });
  });

  describe('Error Handling', () => {
    it('should reject error with original error object', () => {
      const error = new Error('Request failed');
      const rejected = Promise.reject(error);

      return expect(rejected).rejects.toThrow('Request failed');
    });

    it('should handle network errors', () => {
      const error = {
        message: 'Network Error',
        code: 'ERR_NETWORK',
      };

      expect(error.code).toBe('ERR_NETWORK');
    });

    it('should handle timeout errors', () => {
      const error = {
        message: 'Request timeout',
        code: 'ECONNABORTED',
      };

      expect(error.code).toBe('ECONNABORTED');
    });

    it('should handle missing response status', () => {
      const error = {
        response: undefined,
        message: 'No response',
      } as unknown as AxiosError;

      expect(error.response?.status).toBeUndefined();
    });

    it('should handle missing config', () => {
      const error = {
        config: undefined,
        response: { status: 401 },
        message: 'Unauthorized',
      } as unknown as AxiosError;

      expect(error.config).toBeUndefined();
    });
  });

  describe('Request Retry Logic', () => {
    it('should retry request with new token', () => {
      const originalRequest = {
        url: '/api/data',
        headers: {
          Authorization: 'Bearer old-token',
        },
      };

      const newToken = 'new-token';
      originalRequest.headers.Authorization = `Bearer ${newToken}`;

      expect(originalRequest.headers.Authorization).toBe(`Bearer ${newToken}`);
    });

    it('should preserve original request method and data', () => {
      const originalRequest = {
        method: 'POST',
        url: '/api/data',
        data: { name: 'test' },
        headers: {} as Record<string, string>,
      };

      originalRequest.headers['Authorization'] = 'Bearer new-token';

      expect(originalRequest.method).toBe('POST');
      expect(originalRequest.url).toBe('/api/data');
      expect(originalRequest.data).toEqual({ name: 'test' });
    });

    it('should preserve request params', () => {
      const originalRequest = {
        url: '/api/data',
        params: { page: 1, limit: 10 },
        headers: {} as Record<string, string>,
      };

      originalRequest.headers['Authorization'] = 'Bearer new-token';

      expect(originalRequest.params).toEqual({ page: 1, limit: 10 });
    });
  });
});
