export const PERMISSIONS = {
  DASHBOARD_VIEW: "dashboard.view",
  TENANT_MANAGE: "tenant.manage",
  SYSTEM_SUBMIT: "system.submit",
  BACKUP_MANAGE: "backup.manage",
  AUTOMATION_MANAGE: "automation.manage",
} as const;

export type PermissionCode = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];
