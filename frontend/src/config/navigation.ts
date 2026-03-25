import { PERMISSIONS } from "./permissions";
import { ROUTES } from "./routes";

export type NavItem = {
  label: string;
  route: string;
  permission: string;
};

export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", route: ROUTES.DASHBOARD, permission: PERMISSIONS.DASHBOARD_VIEW },
  { label: "Systems", route: ROUTES.SYSTEMS, permission: PERMISSIONS.DASHBOARD_VIEW },
  { label: "History", route: ROUTES.HISTORY, permission: PERMISSIONS.AUTOMATION_MANAGE },
  { label: "Tenants", route: ROUTES.TENANTS, permission: PERMISSIONS.TENANT_MANAGE },
  { label: "Users", route: ROUTES.USERS, permission: PERMISSIONS.TENANT_MANAGE },
  { label: "Alerts", route: ROUTES.ALERTS, permission: PERMISSIONS.AUTOMATION_MANAGE },
  { label: "Automation", route: ROUTES.AUTOMATION, permission: PERMISSIONS.AUTOMATION_MANAGE },
  { label: "Logs", route: ROUTES.LOGS, permission: PERMISSIONS.AUTOMATION_MANAGE },
  { label: "Reliability", route: ROUTES.RELIABILITY, permission: PERMISSIONS.DASHBOARD_VIEW },
  { label: "AI Ops", route: ROUTES.AI, permission: PERMISSIONS.AUTOMATION_MANAGE },
  { label: "Releases", route: ROUTES.RELEASES, permission: PERMISSIONS.DASHBOARD_VIEW },
  { label: "Updates", route: ROUTES.UPDATES, permission: PERMISSIONS.AUTOMATION_MANAGE },
  { label: "Remote", route: ROUTES.REMOTE, permission: PERMISSIONS.AUTOMATION_MANAGE },
  { label: "Platform", route: ROUTES.PLATFORM, permission: PERMISSIONS.TENANT_MANAGE },
  { label: "Backup", route: ROUTES.BACKUP, permission: PERMISSIONS.BACKUP_MANAGE },
  { label: "Audit", route: ROUTES.AUDIT, permission: PERMISSIONS.AUTOMATION_MANAGE },
];
