import { describe, expect, it } from "vitest";
import { NAV_ITEMS } from "../navigation";
import { PERMISSIONS } from "../permissions";
import { ROUTE_PERMISSIONS } from "../routePermissions";
import { ROUTES } from "../routes";

describe("route permission matrix", () => {
  it("keeps route guards aligned with API-backed module requirements", () => {
    expect(ROUTE_PERMISSIONS[ROUTES.RELIABILITY]).toBe(PERMISSIONS.AUTOMATION_MANAGE);
    expect(ROUTE_PERMISSIONS[ROUTES.AUDIT]).toBe(PERMISSIONS.TENANT_MANAGE);
    expect(ROUTE_PERMISSIONS[ROUTES.HISTORY]).toBe(PERMISSIONS.AUTOMATION_MANAGE);
    expect(ROUTE_PERMISSIONS[ROUTES.RELEASES]).toBe(PERMISSIONS.DASHBOARD_VIEW);
    expect(ROUTE_PERMISSIONS[ROUTES.BACKUP]).toBe(PERMISSIONS.BACKUP_MANAGE);
  });

  it("keeps navigation permissions sourced from the shared route matrix", () => {
    for (const item of NAV_ITEMS) {
      expect(item.permission).toBe(ROUTE_PERMISSIONS[item.route]);
    }
  });
});
