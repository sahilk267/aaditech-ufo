export type ApiStatusResponse = {
  status: string;
  message: string;
  version: string;
  queue?: {
    enabled?: boolean;
    [key: string]: unknown;
  };
  cache?: {
    backend?: string;
    [key: string]: unknown;
  };
};

export type SystemSummary = {
  id: number;
  serial_number: string;
  hostname: string;
  last_update: string | null;
  status: string;
};

export type SystemsResponse = {
  success: boolean;
  systems: SystemSummary[];
  count: number;
};

export type SystemDetailResponse = {
  success: boolean;
  system?: {
    id: number;
    serial_number: string;
    hostname: string;
    system_info: unknown;
    performance_metrics: unknown;
    benchmark_results: unknown;
    last_update: string | null;
    status: string;
  };
  error?: string;
};

export type ManualSubmitResponse = {
  status: string;
  message: string;
  system_id?: number;
};

export type Tenant = {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type TenantsResponse = {
  status: string;
  count: number;
  tenants: Tenant[];
  current_tenant: Tenant;
};

export type TenantMutationResponse = {
  status: string;
  tenant: Tenant;
};

export type AgentRelease = {
  version: string;
  filename: string;
  size_bytes: number;
  modified_at: string;
  download_url?: string;
};

export type AgentReleasesResponse = {
  status: string;
  count: number;
  releases: AgentRelease[];
};

export type AgentBuildStatusResponse = {
  status: string;
  build: {
    binary_available: boolean;
    binary_name: string;
  };
};

export type AgentBuildResponse = {
  status: string;
  build: {
    success?: boolean;
    reason?: string;
    details?: string;
    returncode?: number;
    binary_available?: boolean;
    binary_path?: string;
    stdout_tail?: string;
    stderr_tail?: string;
  };
};

export type ReleasePolicy = {
  target_version: string;
  notes: string;
  updated_at: string | null;
};

export type ReleasePolicyResponse = {
  status: string;
  policy: ReleasePolicy;
};

export type ReleaseGuide = {
  status: string;
  current_version: string;
  recommended_version: string | null;
  action: "upgrade" | "downgrade" | "none";
  latest_version: string | null;
  downgrade_candidates: AgentRelease[];
  releases: AgentRelease[];
  policy: ReleasePolicy;
  recommended_download_url?: string | null;
};

export type ReleaseGuideResponse = {
  status: string;
  guide: ReleaseGuide;
};

export type DashboardAggregateResponse = {
  status: string;
  dashboard?: {
    aggregate_health?: {
      overall_status?: string;
      [key: string]: unknown;
    };
    [key: string]: unknown;
  };
  cache_hit?: boolean;
  error?: string;
};

// Alert types
export type AlertRule = {
  id: number;
  name: string;
  metric: string;
  operator: string;
  threshold: number;
  severity: string;
  enabled?: boolean;
};

export type AlertRulesResponse = {
  status: string;
  rules: AlertRule[];
};

export type AlertSilence = {
  id: number;
  name: string;
  until?: string;
};

export type AlertSilencesResponse = {
  status: string;
  silences: AlertSilence[];
};

export type AlertEvaluationResponse = {
  status: string;
  triggered?: AlertRule[];
  [key: string]: unknown;
};

export type AlertDispatchResponse = {
  status: string;
  message?: string;
  [key: string]: unknown;
};

export type AlertPrioritizationResponse = {
  status: string;
  alerts: AlertRule[];
  [key: string]: unknown;
};

// Automation types
export type AutomationWorkflow = {
  id: number;
  name: string;
  description?: string;
  service_name?: string;
  enabled?: boolean;
};

export type AutomationWorkflowsResponse = {
  status: string;
  workflows: AutomationWorkflow[];
};

export type AutomationWorkflowExecutionResponse = {
  status: string;
  result?: Record<string, unknown>;
  [key: string]: unknown;
};

export type ScheduledJob = {
  id: number;
  name: string;
  schedule?: string;
  enabled?: boolean;
};

export type ScheduledJobsResponse = {
  status: string;
  scheduled_jobs?: ScheduledJob[];
  jobs?: ScheduledJob[];
};

export type ServiceStatusResponse = {
  status: string;
  service_status?: Record<string, unknown>;
  [key: string]: unknown;
};

export type SelfHealingResponse = {
  status: string;
  result?: Record<string, unknown>;
  [key: string]: unknown;
};

// Logs types
export type LogsIngestResponse = {
  status: string;
  count?: number;
  [key: string]: unknown;
};

export type LogsQueryResponse = {
  status: string;
  events?: Record<string, unknown>[];
  [key: string]: unknown;
};

export type LogsParseResponse = {
  status: string;
  parsed?: Record<string, unknown>[];
  [key: string]: unknown;
};

export type LogsCorrelateResponse = {
  status: string;
  correlations?: Record<string, unknown>[];
  [key: string]: unknown;
};

export type LogsStreamResponse = {
  status: string;
  stream?: Record<string, unknown>;
  [key: string]: unknown;
};

export type DriverMonitorResponse = {
  status: string;
  drivers?: Record<string, unknown>;
  [key: string]: unknown;
};

export type DriverErrorsResponse = {
  status: string;
  driver_errors?: Record<string, unknown>;
  [key: string]: unknown;
};

export type LogsSearchResponse = {
  status: string;
  search?: Record<string, unknown>;
  results?: Record<string, unknown>[];
  total?: number;
  [key: string]: unknown;
};

// Reliability types
export type ReliabilityHistoryResponse = {
  status: string;
  history?: Record<string, unknown>[];
  [key: string]: unknown;
};

export type CrashDumpAnalysisResponse = {
  status: string;
  analysis?: Record<string, unknown>;
  [key: string]: unknown;
};

export type ExceptionIdentificationResponse = {
  status: string;
  exceptions?: Record<string, unknown>[];
  [key: string]: unknown;
};

export type StackTraceAnalysisResponse = {
  status: string;
  analysis?: Record<string, unknown>;
  [key: string]: unknown;
};

export type ReliabilityScoreResponse = {
  status: string;
  score?: number;
  [key: string]: unknown;
};

export type TrendAnalysisResponse = {
  status: string;
  trends?: Record<string, unknown>;
  [key: string]: unknown;
};

export type PredictionAnalysisResponse = {
  status: string;
  predictions?: Record<string, unknown>;
  [key: string]: unknown;
};

export type PatternDetectionResponse = {
  status: string;
  patterns?: Record<string, unknown>[];
  [key: string]: unknown;
};

// AI types
export type OllamaInferenceResponse = {
  status: string;
  response?: string;
  [key: string]: unknown;
};

export type RootCauseAnalysisResponse = {
  status: string;
  analysis?: Record<string, unknown>;
  [key: string]: unknown;
};

export type RecommendationsGenerationResponse = {
  status: string;
  recommendations?: Record<string, unknown>[];
  [key: string]: unknown;
};

export type AnomalyAnalysisResponse = {
  status: string;
  analysis?: Record<string, unknown>;
  [key: string]: unknown;
};

export type IncidentExplanationResponse = {
  status: string;
  explanation?: Record<string, unknown>;
  [key: string]: unknown;
};

export type ConfidenceScoreResponse = {
  status: string;
  score?: number;
  [key: string]: unknown;
};

// Platform types
export type CacheStatusResponse = {
  status: string;
  cache?: Record<string, unknown>;
  [key: string]: unknown;
};

export type DatabaseOptimizeResponse = {
  status: string;
  message?: string;
  [key: string]: unknown;
};

export type MaintenanceJobsResponse = {
  status: string;
  message?: string;
  [key: string]: unknown;
};

// Updates types
export type UpdatesMonitorResponse = {
  status: string;
  updates?: Record<string, unknown>;
  [key: string]: unknown;
};

// Remote types
export type RemoteExecResponse = {
  status: string;
  output?: string;
  result?: Record<string, unknown>;
  [key: string]: unknown;
};

// Backup types
export type BackupsListResponse = {
  status: string;
  backups?: Record<string, unknown>[];
  [key: string]: unknown;
};

export type BackupCreateResponse = {
  status: string;
  backup?: Record<string, unknown>;
  [key: string]: unknown;
};

export type BackupRestoreResponse = {
  status: string;
  message?: string;
  [key: string]: unknown;
};

// Audit types
export type AuditEvent = {
  id: number;
  actor_id?: number;
  action?: string;
  resource_type?: string;
  timestamp?: string;
  details?: Record<string, unknown>;
};

export type AuditEventsResponse = {
  status: string;
  events?: AuditEvent[];
  total?: number;
  [key: string]: unknown;
};

// User types
export type User = {
  id: number;
  email: string;
  full_name?: string;
  permissions: string[];
  roles?: string[];
};

export type UsersResponse = {
  status: string;
  users: User[];
};

export type UserRegistrationResponse = {
  status: string;
  user?: User;
};

// Generic response wrapper
export type GenericResponse<T = Record<string, unknown>> = {
  status: string;
  data?: T;
  message?: string;
  [key: string]: unknown;
};
