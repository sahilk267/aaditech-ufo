import { ROUTE_PERMISSIONS } from "./routePermissions";
import { ROUTES } from "./routes";

export type NavItem = {
  label: string;
  route: string;
  permission: string;
};

export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", route: ROUTES.DASHBOARD, permission: ROUTE_PERMISSIONS[ROUTES.DASHBOARD] },
  { label: "Systems", route: ROUTES.SYSTEMS, permission: ROUTE_PERMISSIONS[ROUTES.SYSTEMS] },
  { label: "History", route: ROUTES.HISTORY, permission: ROUTE_PERMISSIONS[ROUTES.HISTORY] },
  { label: "Tenants", route: ROUTES.TENANTS, permission: ROUTE_PERMISSIONS[ROUTES.TENANTS] },
  { label: "Users", route: ROUTES.USERS, permission: ROUTE_PERMISSIONS[ROUTES.USERS] },
  { label: "Alerts", route: ROUTES.ALERTS, permission: ROUTE_PERMISSIONS[ROUTES.ALERTS] },
  { label: "Automation", route: ROUTES.AUTOMATION, permission: ROUTE_PERMISSIONS[ROUTES.AUTOMATION] },
  { label: "Logs", route: ROUTES.LOGS, permission: ROUTE_PERMISSIONS[ROUTES.LOGS] },
  { label: "Reliability", route: ROUTES.RELIABILITY, permission: ROUTE_PERMISSIONS[ROUTES.RELIABILITY] },
  { label: "AI Ops", route: ROUTES.AI, permission: ROUTE_PERMISSIONS[ROUTES.AI] },
  { label: "Releases", route: ROUTES.RELEASES, permission: ROUTE_PERMISSIONS[ROUTES.RELEASES] },
  { label: "Updates", route: ROUTES.UPDATES, permission: ROUTE_PERMISSIONS[ROUTES.UPDATES] },
  { label: "Remote", route: ROUTES.REMOTE, permission: ROUTE_PERMISSIONS[ROUTES.REMOTE] },
  { label: "Platform", route: ROUTES.PLATFORM, permission: ROUTE_PERMISSIONS[ROUTES.PLATFORM] },
  { label: "Backup", route: ROUTES.BACKUP, permission: ROUTE_PERMISSIONS[ROUTES.BACKUP] },
  { label: "Audit", route: ROUTES.AUDIT, permission: ROUTE_PERMISSIONS[ROUTES.AUDIT] },
];
