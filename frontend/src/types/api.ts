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

export type TenantControlsResponse = {
  status: string;
  tenant_controls: {
    defaults: Record<string, unknown>;
    effective: {
      entitlements: Record<string, { enabled: boolean; limit_value?: number | null; metadata?: Record<string, unknown> }>;
      feature_flags: Record<string, { enabled: boolean; description?: string | null }>;
    };
    entitlement_rows: Record<string, unknown>[];
    feature_flag_rows: Record<string, unknown>[];
  };
};

export type TenantQuotasResponse = {
  status: string;
  tenant_quotas: {
    defaults: Record<string, { limit_value?: number | null; is_enforced: boolean; metadata?: Record<string, unknown> }>;
    effective: Record<string, { limit_value?: number | null; is_enforced: boolean; metadata?: Record<string, unknown> }>;
    quota_rows: Record<string, unknown>[];
  };
};

export type TenantUsageResponse = {
  status: string;
  tenant_usage: {
    measured_at: string;
    metrics: Array<{
      id: number;
      metric_key: string;
      current_value: number;
      metadata?: Record<string, unknown>;
      measured_at?: string | null;
    }>;
    current: Record<string, { current_value: number; metadata?: Record<string, unknown> }>;
  };
};

export type TenantUsageReportResponse = {
  status: string;
  tenant_usage_report: {
    generated_at: string;
    summary: {
      quota_count: number;
      enforced_count: number;
      over_limit_count: number;
      near_limit_count: number;
      recent_enforcement_count: number;
    };
    quotas: Array<{
      quota_key: string;
      current_value: number;
      limit_value?: number | null;
      is_enforced: boolean;
      percent_used?: number | null;
      status: string;
      metadata?: Record<string, unknown>;
      usage_metadata?: Record<string, unknown>;
    }>;
    recent_enforcement_events: Array<{
      id: number;
      created_at?: string | null;
      quota_key?: string | null;
      details?: Record<string, unknown> | null;
      metadata?: Record<string, unknown> | null;
    }>;
  };
};

export type TenantCommercialResponse = {
  status: string;
  tenant_commercial: {
    plan: {
      plan_key: string;
      display_name: string;
      status: string;
      billing_cycle?: string | null;
      external_customer_ref?: string | null;
      external_subscription_ref?: string | null;
      metadata?: Record<string, unknown>;
    };
    billing_profile: {
      billing_email?: string | null;
      billing_name?: string | null;
      contact_email?: string | null;
      country_code?: string | null;
      provider_name?: string | null;
      provider_customer_ref?: string | null;
      tax_id_hint?: string | null;
      metadata?: Record<string, unknown>;
    };
    license: {
      license_status: string;
      license_key_hint?: string | null;
      seat_limit?: number | null;
      enforcement_mode: string;
      expires_at?: string | null;
      metadata?: Record<string, unknown>;
      };
      contract_boundaries: Record<string, string>;
      provider_boundary: {
        current_provider: string;
        provider_capabilities: Record<string, unknown>;
        supported_providers: Record<string, Record<string, unknown>>;
        sync_readiness: {
          customer_ready: boolean;
          subscription_ready: boolean;
          license_ready: boolean;
          can_sync_customer: boolean;
          can_sync_subscription: boolean;
          can_sync_license: boolean;
        };
        outbound_contract_preview: {
          customer: Record<string, unknown>;
          subscription: Record<string, unknown>;
          license: Record<string, unknown>;
        };
      };
      lifecycle_semantics: {
        allowed_plan_statuses: string[];
        allowed_billing_cycles: string[];
        allowed_license_statuses: string[];
        allowed_enforcement_modes: string[];
      };
    };
  };

export type TenantCommercialProviderBoundaryResponse = {
  status: string;
  provider_boundary: {
    current_provider: string;
    provider_capabilities: Record<string, unknown>;
    supported_providers: Record<string, Record<string, unknown>>;
    sync_readiness: Record<string, boolean>;
    outbound_contract_preview: Record<string, Record<string, unknown>>;
  };
};

export type TenantSettingsResponse = {
  status: string;
  tenant_settings: {
    notification_settings: Record<string, unknown>;
    retention_settings: Record<string, unknown>;
    branding_settings: Record<string, unknown>;
    auth_policy: {
      min_password_length: number;
      require_uppercase: boolean;
      require_lowercase: boolean;
      require_number: boolean;
      require_symbol: boolean;
      lockout_threshold: number;
      lockout_minutes: number;
      session_max_age_minutes: number;
      totp_mfa_enabled: boolean;
      oidc_enabled: boolean;
      local_admin_fallback_enabled: boolean;
      [key: string]: unknown;
    };
    feature_flags: Record<string, unknown>;
  };
};

export type OidcProvider = {
  id: number;
  organization_id: number;
  name: string;
  issuer: string;
  client_id: string;
  discovery_endpoint?: string | null;
  authorization_endpoint: string;
  token_endpoint?: string | null;
  userinfo_endpoint?: string | null;
  jwks_uri?: string | null;
  end_session_endpoint?: string | null;
  scopes: string[];
  claim_mappings: Record<string, unknown>;
  role_mappings: Record<string, unknown>;
  test_mode: boolean;
  test_claim_codes: string[];
  is_enabled: boolean;
  is_default: boolean;
  has_client_secret: boolean;
  client_secret_secret_name?: string | null;
  last_discovery_status?: string | null;
  last_auth_status?: string | null;
  last_error?: string | null;
  last_discovery_at?: string | null;
  last_auth_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type OidcProvidersResponse = {
  status: string;
  count: number;
  providers: OidcProvider[];
};

export type OidcProviderMutationResponse = {
  status: string;
  provider: OidcProvider;
};

export type TotpFactorStatusResponse = {
  status: string;
  totp: {
    enabled: boolean;
    status: string;
    factor?: {
      id: number;
      status: string;
      enrolled_at?: string | null;
      verified_at?: string | null;
      last_used_at?: string | null;
      disabled_at?: string | null;
    } | null;
    secret?: string;
    provisioning_uri?: string;
  };
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

export type AlertDeliveryRecord = {
  id: number;
  status: string;
  delivery_scope?: string;
  channels_requested?: string[];
  delivered_channels?: string[];
  failure_count?: number;
  created_at?: string | null;
  [key: string]: unknown;
};

export type AlertDeliveryHistoryResponse = {
  status: string;
  deliveries: AlertDeliveryRecord[];
  total: number;
  pages: number;
  page: number;
  per_page: number;
};

export type AlertDeliveryDetailResponse = {
  status: string;
  delivery: AlertDeliveryRecord;
};

// Automation types
export type AutomationWorkflow = {
  id: number;
  name: string;
  description?: string;
  trigger_type?: string;
  action_type?: string;
  action_config?: Record<string, unknown>;
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

export type WorkflowRunRecord = {
  id: number;
  workflow_id: number;
  status: string;
  trigger_source?: string;
  dry_run?: boolean;
  executed_at?: string | null;
  error_reason?: string | null;
  [key: string]: unknown;
};

export type WorkflowRunsResponse = {
  status: string;
  workflow_runs: WorkflowRunRecord[];
  total: number;
  pages: number;
  page: number;
  per_page: number;
};

export type WorkflowRunDetailResponse = {
  status: string;
  workflow_run: WorkflowRunRecord;
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

export type LogSourceRecord = {
  id: number;
  organization_id: number;
  name: string;
  adapter: string;
  description?: string | null;
  host_name?: string | null;
  is_active: boolean;
  source_metadata?: Record<string, unknown>;
  last_ingested_at?: string | null;
  last_entry_at?: string | null;
  latest_message?: string | null;
  entry_count?: number;
  severity_breakdown?: Record<string, number>;
  capture_kinds?: Record<string, number>;
  created_at?: string | null;
  updated_at?: string | null;
};

export type LogEntryRecord = {
  id: number;
  organization_id: number;
  log_source_id?: number | null;
  source_name: string;
  adapter: string;
  capture_kind: string;
  observed_at?: string | null;
  severity?: string | null;
  event_id?: string | null;
  message: string;
  raw_entry: string;
  entry_metadata?: Record<string, unknown>;
  created_at?: string | null;
};

export type LogSourcesResponse = {
  status: string;
  count: number;
  sources: LogSourceRecord[];
};

export type LogSourceDetailResponse = {
  status: string;
  log_source: LogSourceRecord;
  recent_entries?: LogEntryRecord[];
};

export type LogEntriesResponse = {
  status: string;
  page: number;
  per_page: number;
  total: number;
  pages: number;
  entries: LogEntryRecord[];
};

export type LogEntryDetailResponse = {
  status: string;
  entry: LogEntryRecord;
};

export type LogInvestigationRecord = {
  id: number;
  name: string;
  status: string;
  source_name?: string | null;
  pinned_source_id?: number | null;
  pinned_entry_id?: number | null;
  filter_snapshot: Record<string, unknown>;
  notes?: string | null;
  last_result_count: number;
  last_matched_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type LogInvestigationsResponse = {
  status: string;
  count: number;
  investigations: LogInvestigationRecord[];
};

export type LogInvestigationMutationResponse = {
  status: string;
  investigation: LogInvestigationRecord;
};

// Reliability types
export type ReliabilityHistoryResponse = {
  status: string;
  history?: Record<string, unknown>;
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
  reliability?: Record<string, unknown>;
  [key: string]: unknown;
};

export type ReliabilityRunRecord = {
  id: number;
  organization_id: number;
  diagnostic_type: string;
  host_name: string;
  dump_name?: string | null;
  adapter?: string | null;
  status: string;
  error_reason?: string | null;
  request_payload?: Record<string, unknown>;
  result_payload?: Record<string, unknown>;
  summary?: Record<string, unknown>;
  created_at?: string | null;
};

export type ReliabilityRunsResponse = {
  status: string;
  page: number;
  per_page: number;
  total: number;
  pages: number;
  reliability_runs: ReliabilityRunRecord[];
};

export type ReliabilityRunDetailResponse = {
  status: string;
  reliability_run: ReliabilityRunRecord & {
    related_runs?: ReliabilityRunRecord[];
  };
};

export type ReliabilityReportResponse = {
  status: string;
  report: {
    status_counts: Record<string, number>;
    diagnostic_counts: Record<string, number>;
    failure_reasons: Record<string, number>;
    host_counts: Record<string, number>;
    latest_by_type: Record<string, ReliabilityRunRecord>;
    latest_score?: Record<string, unknown>;
    latest_trend?: Record<string, unknown>;
    latest_prediction?: Record<string, unknown>;
    crash_related_runs: ReliabilityRunRecord[];
    recent_failures: ReliabilityRunRecord[];
    total_runs_considered: number;
  };
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

export type AiOperationReportItem = {
  id: number;
  created_at: string | null;
  action: string;
  outcome: string;
  adapter?: string | null;
  model?: string | null;
  fallback_used?: boolean;
  duration_ms?: number | null;
  primary_error_reason?: string | null;
  reason?: string | null;
  metadata?: Record<string, unknown> | null;
};

export type AiOperationsReportResponse = {
  status: string;
  report: {
    summary: {
      total_events: number;
      success_count: number;
      failure_count: number;
      fallback_count: number;
      success_rate: number | null;
      avg_duration_ms: number | null;
    };
    counts: {
      by_action: Record<string, number>;
      by_adapter: Record<string, number>;
      by_primary_error_reason: Record<string, number>;
    };
    recent_operations: AiOperationReportItem[];
    recent_failures: AiOperationReportItem[];
  };
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
  confidence?: Record<string, unknown>;
  update_run_id?: number | null;
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

export type UpdateRunRecord = {
  id: number;
  organization_id: number;
  host_name: string;
  adapter?: string | null;
  status: string;
  error_reason?: string | null;
  update_count: number;
  latest_installed_on?: string | null;
  updates_payload?: Record<string, unknown>;
  summary?: Record<string, unknown>;
  confidence_score?: number | null;
  confidence_payload?: Record<string, unknown>;
  created_at?: string | null;
};

export type UpdateRunsResponse = {
  status: string;
  page: number;
  per_page: number;
  total: number;
  pages: number;
  update_runs: UpdateRunRecord[];
};

export type UpdateRunDetailResponse = {
  status: string;
  update_run: UpdateRunRecord;
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

export type IncidentRecordSummary = {
  id: number;
  title: string;
  status: string;
  severity: string;
  hostname?: string | null;
  assigned_to_user_id?: number | null;
  resolution_summary?: string | null;
  last_seen_at?: string | null;
  [key: string]: unknown;
};

export type IncidentsResponse = {
  status: string;
  incidents: IncidentRecordSummary[];
  total: number;
  pages: number;
  page: number;
  per_page: number;
};

export type IncidentDetailResponse = {
  status: string;
  incident: IncidentRecordSummary;
};

export type IncidentCaseComment = {
  id: number;
  incident_id: number;
  author_user_id?: number | null;
  comment_type: string;
  body: string;
  created_at?: string | null;
};

export type IncidentCommentsResponse = {
  status: string;
  count: number;
  comments: IncidentCaseComment[];
};

export type OperationsTimelineResponse = {
  status: string;
  count: number;
  timeline: {
    kind: string;
    id: number;
    timestamp?: string | null;
    title: string;
    status: string;
    details?: Record<string, unknown>;
  }[];
};

export type AlertsStreamSnapshot = {
  generated_at?: string;
  deliveries: AlertDeliveryRecord[];
  incidents: IncidentRecordSummary[];
  counts?: {
    deliveries: number;
    incidents_total: number;
    incidents_open: number;
  };
};

export type OperationsTimelineStreamSnapshot = {
  generated_at?: string;
  count: number;
  timeline: OperationsTimelineResponse["timeline"];
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
