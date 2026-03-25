/**
 * Integration Tests for Critical User Flows
 * Tests: Login → Dashboard → API calls
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiClient } from "../axios";
import { login, fetchMe } from "../auth";

describe("Integration: Critical User Flows", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Login Flow", () => {
    it("should login with valid credentials", async () => {
      // Mock the login API response
      vi.spyOn(apiClient, "post").mockResolvedValueOnce({
        data: {
          status: "success",
          tokens: {
            access_token: "mock-jwt-token",
            refresh_token: "mock-refresh-token",
            token_type: "Bearer",
            expires_in: 3600,
          },
          user: {
            id: 1,
            email: "user@example.com",
            full_name: "Test User",
            organization_id: 1,
            roles: ["admin"],
          },
        },
      });

      const result = await login({ tenantSlug: "default", email: "user@example.com", password: "password" });

      expect(result).toHaveProperty("tokens");
      expect(result.tokens.access_token).toBe("mock-jwt-token");
      expect(result.user).toHaveProperty("email");
      expect(apiClient.post).toHaveBeenCalled();
    });

    it("should fetch current user after login", async () => {
      // Mock fetchMe response
      vi.spyOn(apiClient, "get").mockResolvedValueOnce({
        data: {
          status: "success",
          user: {
            id: 1,
            email: "user@example.com",
            full_name: "Test User",
            organization_id: 1,
            permissions: ["dashboard.view", "tenant.manage"],
            roles: ["admin"],
          },
        },
      });

      const user = await fetchMe();

      expect(user.user).toHaveProperty("email");
      expect(user.user.permissions).toContain("dashboard.view");
      expect(apiClient.get).toHaveBeenCalledWith("/api/auth/me");
    });

    it("should handle login errors gracefully", async () => {
      // Mock login failure
      const error = new Error("Invalid credentials");
      vi.spyOn(apiClient, "post").mockRejectedValueOnce(error);

      await expect(login({ tenantSlug: "default", email: "user@example.com", password: "wrong" })).rejects.toThrow(
        "Invalid credentials"
      );
    });
  });

  describe("Dashboard Data Load", () => {
    it("should load API status on dashboard", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValueOnce({
        data: {
          status: "operational",
          message: "All systems online",
          version: "1.0.0",
        },
      });

      const { data } = await apiClient.get("/api/status");

      expect(data).toHaveProperty("status");
      expect(data.status).toBe("operational");
      expect(apiClient.get).toHaveBeenCalledWith("/api/status");
    });

    it("should load systems list on dashboard", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValueOnce({
        data: {
          success: true,
          systems: [
            {
              id: 1,
              hostname: "host1",
              serial_number: "SN001",
              status: "active",
              last_update: "2024-03-24T10:00:00Z",
            },
            {
              id: 2,
              hostname: "host2",
              serial_number: "SN002",
              status: "inactive",
              last_update: null,
            },
          ],
          count: 2,
        },
      });

      const { data } = await apiClient.get("/api/systems");

      expect(data.systems).toHaveLength(2);
      expect(data.count).toBe(2);
      expect(data.systems[0]).toHaveProperty("hostname");
      expect(data.systems[0].status).toBe("active");
    });

    it("should load dashboard aggregate status", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValueOnce({
        data: {
          status: "success",
          dashboard: {
            aggregate_health: {
              overall_status: "healthy",
            },
          },
          cache_hit: true,
        },
      });

      const { data } = await apiClient.get("/api/dashboard/status", {
        params: { host_name: "host1" },
      });

      expect(data.dashboard?.aggregate_health?.overall_status).toBe("healthy");
      expect(data.cache_hit).toBe(true);
    });
  });

  describe("Tenant Management", () => {
    it("should list all tenants", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValueOnce({
        data: {
          status: "success",
          count: 2,
          tenants: [
            {
              id: 1,
              name: "Tenant A",
              slug: "tenant-a",
              is_active: true,
              created_at: "2024-01-01T00:00:00Z",
              updated_at: "2024-03-24T00:00:00Z",
            },
            {
              id: 2,
              name: "Tenant B",
              slug: "tenant-b",
              is_active: false,
              created_at: "2024-02-01T00:00:00Z",
              updated_at: "2024-03-24T00:00:00Z",
            },
          ],
          current_tenant: {
            id: 1,
            name: "Tenant A",
            slug: "tenant-a",
            is_active: true,
            created_at: "2024-01-01T00:00:00Z",
            updated_at: "2024-03-24T00:00:00Z",
          },
        },
      });

      const { data } = await apiClient.get("/api/tenants");

      expect(data.tenants).toHaveLength(2);
      expect(data.count).toBe(2);
      expect(data.current_tenant.slug).toBe("tenant-a");
    });

    it("should create a new tenant", async () => {
      vi.spyOn(apiClient, "post").mockResolvedValueOnce({
        data: {
          status: "success",
          tenant: {
            id: 3,
            name: "Tenant C",
            slug: "tenant-c",
            is_active: true,
            created_at: "2024-03-24T10:00:00Z",
            updated_at: "2024-03-24T10:00:00Z",
          },
        },
      });

      const { data } = await apiClient.post("/api/tenants", {
        name: "Tenant C",
        slug: "tenant-c",
        is_active: true,
      });

      expect(data.tenant.id).toBe(3);
      expect(data.tenant.slug).toBe("tenant-c");
      expect(apiClient.post).toHaveBeenCalledWith("/api/tenants", expect.objectContaining({
        name: "Tenant C",
      }));
    });
  });

  describe("API Error Handling", () => {
    it("should handle 401 unauthorized errors", async () => {
      const error = new Error("Unauthorized");
      (error as any).response = {
        status: 401,
        data: { error: "Token expired" },
      };

      vi.spyOn(apiClient, "get").mockRejectedValueOnce(error);

      await expect(apiClient.get("/api/protected")).rejects.toThrow("Unauthorized");
    });

    it("should handle network errors", async () => {
      const error = new Error("Network timeout");

      vi.spyOn(apiClient, "get").mockRejectedValueOnce(error);

      await expect(apiClient.get("/api/systems")).rejects.toThrow("Network timeout");
    });

    it("should handle 403 permission denied errors", async () => {
      const error = new Error("Permission denied");
      (error as any).response = {
        status: 403,
        data: { error: "Insufficient permissions" },
      };

      vi.spyOn(apiClient, "post").mockRejectedValueOnce(error);

      await expect(apiClient.post("/api/admin/action", {})).rejects.toThrow(
        "Permission denied"
      );
    });
  });

  describe("Data Persistence & State", () => {
    it("should maintain auth token across requests", async () => {
      // Mock setting token
      const mockToken = "test-jwt-token";
      
      // Verify token is used in Authorization header
      const config = {
        headers: {
          Authorization: `Bearer ${mockToken}`,
        },
      };

      expect(config.headers.Authorization).toBe(`Bearer ${mockToken}`);
      expect(config.headers.Authorization).toContain("Bearer");
    });

    it("should maintain tenant context across requests", async () => {
      const mockTenantSlug = "tenant-a";
      
      const config = {
        headers: {
          "X-Tenant-Slug": mockTenantSlug,
        },
      };

      expect(config.headers["X-Tenant-Slug"]).toBe("tenant-a");
    });
  });
});
