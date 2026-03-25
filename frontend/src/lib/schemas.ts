import { z } from "zod";

/**
 * Zod Validation Schemas for Form Validation
 * All schemas use client-side validation integrated with React Hook Form
 */

// ============================================================================
// AUTH & USERS
// ============================================================================

export const loginSchema = z.object({
  tenantSlug: z.string().min(1, "Tenant slug is required").max(100),
  email: z.string().email("Invalid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

export type LoginInput = z.infer<typeof loginSchema>;

export const createUserSchema = z.object({
  email: z.string()
    .email("Invalid email address")
    .max(255, "Email must be less than 255 characters"),
  fullName: z.string()
    .min(2, "Full name must be at least 2 characters")
    .max(255, "Full name must be less than 255 characters"),
  password: z.string()
    .min(8, "Password must be at least 8 characters")
    .regex(/[A-Z]/, "Password must contain uppercase letter")
    .regex(/[0-9]/, "Password must contain number")
    .regex(/[!@#$%^&*]/, "Password must contain special character"),
});

export type CreateUserInput = z.infer<typeof createUserSchema>;

export const updateUserSchema = createUserSchema.omit({ password: true }).extend({
  password: z.string()
    .min(8, "Password must be at least 8 characters")
    .regex(/[A-Z]/, "Password must contain uppercase letter")
    .regex(/[0-9]/, "Password must contain number")
    .regex(/[!@#$%^&*]/, "Password must contain special character")
    .optional(),
});

export type UpdateUserInput = z.infer<typeof updateUserSchema>;

// ============================================================================
// TENANTS
// ============================================================================

export const createTenantSchema = z.object({
  name: z.string()
    .min(2, "Tenant name must be at least 2 characters")
    .max(255, "Tenant name must be less than 255 characters"),
  slug: z.string()
    .min(3, "Slug must be at least 3 characters")
    .max(100, "Slug must be less than 100 characters")
    .regex(/^[a-z0-9-]+$/, "Slug can only contain lowercase letters, numbers, and hyphens")
    .optional()
    .or(z.literal("")),
  isActive: z.boolean().default(true),
});

export type CreateTenantInput = z.infer<typeof createTenantSchema>;

export const updateTenantSchema = createTenantSchema.extend({
  tenantId: z.number().positive("Invalid tenant ID"),
});

export type UpdateTenantInput = z.infer<typeof updateTenantSchema>;

// ============================================================================
// ALERTS
// ============================================================================

export const createAlertRuleSchema = z.object({
  name: z.string()
    .min(2, "Rule name must be at least 2 characters")
    .max(255, "Rule name must be less than 255 characters"),
  metric: z.string()
    .min(1, "Metric is required")
    .max(100, "Metric must be less than 100 characters"),
  operator: z.enum([">", "<", ">=", "<=", "==", "!="]),
  threshold: z.coerce.number()
    .min(0, "Threshold must be non-negative")
    .max(1000000, "Threshold is too large"),
  severity: z.enum(["info", "warning", "critical"]),
  description: z.string()
    .max(1000, "Description must be less than 1000 characters")
    .optional()
    .or(z.literal("")),
});

export type CreateAlertRuleInput = z.infer<typeof createAlertRuleSchema>;

export const updateAlertRuleSchema = createAlertRuleSchema.extend({
  ruleId: z.number().positive("Invalid rule ID"),
});

export type UpdateAlertRuleInput = z.infer<typeof updateAlertRuleSchema>;

export const createAlertSilenceSchema = z.object({
  ruleId: z.coerce.number().positive("Rule is required"),
  durationMinutes: z.coerce.number()
    .min(1, "Duration must be at least 1 minute")
    .max(10080, "Duration cannot exceed 7 days (10080 minutes)"),
  reason: z.string()
    .max(1000, "Reason must be less than 1000 characters")
    .optional()
    .or(z.literal("")),
});

export type CreateAlertSilenceInput = z.infer<typeof createAlertSilenceSchema>;

// ============================================================================
// AUTOMATION
// ============================================================================

export const createAutomationWorkflowSchema = z.object({
  name: z.string()
    .min(2, "Workflow name must be at least 2 characters")
    .max(255, "Workflow name must be less than 255 characters"),
  description: z.string()
    .max(2000, "Description must be less than 2000 characters")
    .optional()
    .or(z.literal("")),
  triggerType: z.enum(["alert", "schedule", "manual"]),
  triggerMatch: z.record(z.string(), z.any()).optional().default({}),
  steps: z.array(
    z.object({
      action: z.string().min(1, "Action is required"),
      service: z.string().max(255).optional(),
      params: z.record(z.string(), z.any()).optional(),
    }) as any
  ).min(1, "At least one step is required"),
  isActive: z.boolean().default(true),
});

export type CreateAutomationWorkflowInput = z.infer<typeof createAutomationWorkflowSchema>;

export const updateAutomationWorkflowSchema = createAutomationWorkflowSchema.extend({
  workflowId: z.number().positive("Invalid workflow ID"),
});

export type UpdateAutomationWorkflowInput = z.infer<typeof updateAutomationWorkflowSchema>;

export const createScheduledJobSchema = z.object({
  workflowId: z.coerce.number().positive("Workflow is required"),
  cronExpression: z.string()
    .min(1, "Cron expression is required")
    .regex(/^(\*|([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])|\*\/([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])) /, "Invalid cron expression"),
  isActive: z.boolean().default(true),
  description: z.string()
    .max(1000, "Description must be less than 1000 characters")
    .optional()
    .or(z.literal("")),
});

export type CreateScheduledJobInput = z.infer<typeof createScheduledJobSchema>;

// ============================================================================
// BACKUPS
// ============================================================================

export const restoreBackupSchema = z.object({
  filename: z.string()
    .min(1, "Backup file is required")
    .max(255, "Filename must be less than 255 characters"),
  dryRun: z.boolean().default(false),
  verifyIntegrity: z.boolean().default(true),
});

export type RestoreBackupInput = z.infer<typeof restoreBackupSchema>;

export const createBackupSchema = z.object({
  includeAuditLog: z.boolean().default(true),
  compress: z.boolean().default(true),
  encryptionPassword: z.string()
    .min(8, "Encryption password must be at least 8 characters")
    .optional()
    .or(z.literal("")),
});

export type CreateBackupInput = z.infer<typeof createBackupSchema>;

// ============================================================================
// AUDIT & FILTERS
// ============================================================================

export const auditFilterSchema = z.object({
  eventType: z.string()
    .max(100, "Event type must be less than 100 characters")
    .optional()
    .or(z.literal("")),
  userId: z.preprocess(
    (value) => (value === "" || value == null ? undefined : value),
    z.coerce.number().positive().optional()
  ),
  dateFrom: z.string().optional().or(z.literal("")),
  dateTo: z.string().optional().or(z.literal("")),
  searchText: z.string()
    .max(500, "Search text must be less than 500 characters")
    .optional()
    .or(z.literal("")),
  limit: z.coerce.number()
    .min(10, "Limit must be at least 10")
    .max(1000, "Limit cannot exceed 1000")
    .default(50),
});

export type AuditFilterInput = z.infer<typeof auditFilterSchema>;

// ============================================================================
// SYSTEM & PLATFORM
// ============================================================================

export const databaseOptimizeSchema = z.object({
  dryRun: z.boolean().default(true),
  analyzeStatistics: z.boolean().default(true),
  rebuildIndexes: z.boolean().default(false),
  vacuumFull: z.boolean().default(false),
});

export type DatabaseOptimizeInput = z.infer<typeof databaseOptimizeSchema>;

export const cacheManagementSchema = z.object({
  action: z.enum(["clear", "warm", "stats"]),
  keyPattern: z.string()
    .max(255, "Key pattern must be less than 255 characters")
    .optional()
    .or(z.literal("")),
});

export type CacheManagementInput = z.infer<typeof cacheManagementSchema>;

export const remoteCommandSchema = z.object({
  hostname: z.string()
    .min(1, "Hostname is required")
    .max(255, "Hostname must be less than 255 characters"),
  command: z.string()
    .min(1, "Command is required")
    .max(5000, "Command must be less than 5000 characters"),
  timeout: z.coerce.number()
    .min(5, "Timeout must be at least 5 seconds")
    .max(3600, "Timeout cannot exceed 1 hour")
    .default(30),
  dryRun: z.boolean().default(false),
});

export type RemoteCommandInput = z.infer<typeof remoteCommandSchema>;

// ============================================================================
// RELEASE MANAGEMENT
// ============================================================================

export const updateReleasePolicySchema = z.object({
  targetVersion: z.string()
    .min(1, "Target version is required")
    .regex(/^\d+\.\d+\.\d+$/, "Version must be in format X.Y.Z"),
  autoUpdate: z.boolean().default(false),
  rollbackOnFailure: z.boolean().default(true),
  notificationEmail: z.string()
    .email("Invalid email address")
    .optional()
    .or(z.literal("")),
});

export type UpdateReleasePolicyInput = z.infer<typeof updateReleasePolicySchema>;

export const uploadReleaseSchema = z.object({
  targetVersion: z.string()
    .min(1, "Target version is required")
    .regex(/^\d+\.\d+\.\d+$/, "Version must be in format X.Y.Z"),
  releaseFile: z.instanceof(File)
    .refine((file) => file.size > 0, "File must not be empty")
    .refine((file) => file.size < 1024 * 1024 * 500, "File must be less than 500MB")
    .refine(
      (file) => file.name.endsWith(".exe") || file.name.endsWith(".zip"),
      "File must be .exe or .zip"
    ),
  releaseNotes: z.string()
    .max(5000, "Release notes must be less than 5000 characters")
    .optional()
    .or(z.literal("")),
});

export type UploadReleaseInput = z.infer<typeof uploadReleaseSchema>;
