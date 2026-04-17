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
  { label: "Incidents", route: ROUTES.INCIDENTS, permission: ROUTE_PERMISSIONS[ROUTES.INCIDENTS] },
  { label: "Automation", route: ROUTES.AUTOMATION, permission: ROUTE_PERMISSIONS[ROUTES.AUTOMATION] },
  { label: "Logs", route: ROUTES.LOGS, permission: ROUTE_PERMISSIONS[ROUTES.LOGS] },
  { label: "Reliability", route: ROUTES.RELIABILITY, permission: ROUTE_PERMISSIONS[ROUTES.RELIABILITY] },
  { label: "AI Ops", route: ROUTES.AI, permission: ROUTE_PERMISSIONS[ROUTES.AI] },
  { label: "Releases", route: ROUTES.RELEASES, permission: ROUTE_PERMISSIONS[ROUTES.RELEASES] },
  { label: "Updates", route: ROUTES.UPDATES, permission: ROUTE_PERMISSIONS[ROUTES.UPDATES] },
  { label: "Remote", route: ROUTES.REMOTE, permission: ROUTE_PERMISSIONS[ROUTES.REMOTE] },
  { label: "Platform", route: ROUTES.PLATFORM, permission: ROUTE_PERMISSIONS[ROUTES.PLATFORM] },
  { label: "Backup Drill", route: ROUTES.BACKUP_DRILL, permission: ROUTE_PERMISSIONS[ROUTES.BACKUP_DRILL] },
  { label: "Tenant Settings", route: ROUTES.TENANT_SETTINGS, permission: ROUTE_PERMISSIONS[ROUTES.TENANT_SETTINGS] },
  { label: "Tenant Controls", route: ROUTES.TENANT_CONTROLS, permission: ROUTE_PERMISSIONS[ROUTES.TENANT_CONTROLS] },
  { label: "Tenant Quotas", route: ROUTES.TENANT_QUOTAS, permission: ROUTE_PERMISSIONS[ROUTES.TENANT_QUOTAS] },
  { label: "Tenant Commercial", route: ROUTES.TENANT_COMMERCIAL, permission: ROUTE_PERMISSIONS[ROUTES.TENANT_COMMERCIAL] },
  { label: "OIDC Providers", route: ROUTES.OIDC_PROVIDERS, permission: ROUTE_PERMISSIONS[ROUTES.OIDC_PROVIDERS] },
  { label: "Tenant Secrets", route: ROUTES.TENANT_SECRETS, permission: ROUTE_PERMISSIONS[ROUTES.TENANT_SECRETS] },
  { label: "Agent Enrollment", route: ROUTES.AGENT_ENROLLMENT, permission: ROUTE_PERMISSIONS[ROUTES.AGENT_ENROLLMENT] },
  { label: "Backup", route: ROUTES.BACKUP, permission: ROUTE_PERMISSIONS[ROUTES.BACKUP] },
  { label: "Audit", route: ROUTES.AUDIT, permission: ROUTE_PERMISSIONS[ROUTES.AUDIT] },
];
