import { apiClient } from "./axios";
import type {
  AgentBuildResponse,
  AgentBuildStatusResponse,
  AgentReleasesResponse,
  AlertDeliveryDetailResponse,
  AlertDeliveryHistoryResponse,
  AlertDispatchResponse,
  AlertEvaluationResponse,
  AlertPrioritizationResponse,
  AlertRule,
  AlertRulesResponse,
  AlertSilencesResponse,
  AiOperationsReportResponse,
  AnomalyAnalysisResponse,
  AuditEventsResponse,
  AutomationWorkflowExecutionResponse,
  AutomationWorkflowsResponse,
  BackupCreateResponse,
  BackupRestoreResponse,
  BackupsListResponse,
  CacheStatusResponse,
  CrashDumpAnalysisResponse,
  DatabaseOptimizeResponse,
  DashboardAggregateResponse,
  ConfidenceScoreResponse,
  DriverErrorsResponse,
  DriverMonitorResponse,
  ExceptionIdentificationResponse,
  IncidentDetailResponse,
  IncidentExplanationResponse,
  IncidentCommentsResponse,
  IncidentsResponse,
  LogsCorrelateResponse,
  LogsIngestResponse,
  LogEntriesResponse,
  LogInvestigationMutationResponse,
  LogInvestigationsResponse,
  LogEntryDetailResponse,
  LogSourceDetailResponse,
  LogSourcesResponse,
  LogsParseResponse,
  LogsQueryResponse,
  LogsStreamResponse,
  LogsSearchResponse,
  ManualSubmitResponse,
  MaintenanceJobsResponse,
  OperationsTimelineResponse,
  OidcProviderMutationResponse,
  OidcProvidersResponse,
  OllamaInferenceResponse,
  PatternDetectionResponse,
  PredictionAnalysisResponse,
  ReliabilityRunDetailResponse,
  ReliabilityReportResponse,
  ReliabilityRunsResponse,
  RecommendationsGenerationResponse,
  ReliabilityHistoryResponse,
  ReliabilityScoreResponse,
  ReleaseGuideResponse,
  ReleasePolicyResponse,
  RemoteExecResponse,
  RootCauseAnalysisResponse,
  ScheduledJobsResponse,
  SelfHealingResponse,
  ServiceStatusResponse,
  StackTraceAnalysisResponse,
  SystemDetailResponse,
  SystemsResponse,
  TenantMutationResponse,
  TenantControlsResponse,
  TenantCommercialResponse,
  TenantQuotasResponse,
  TenantSettingsResponse,
  TenantUsageResponse,
  TenantUsageReportResponse,
  TenantsResponse,
  TotpFactorStatusResponse,
  TrendAnalysisResponse,
  UpdatesMonitorResponse,
  UpdateRunDetailResponse,
  UpdateRunsResponse,
  UserRegistrationResponse,
  WorkflowRunDetailResponse,
  WorkflowRunsResponse,
  ApiStatusResponse,
} from "../types/api";

export async function getApiStatus() {
  const { data } = await apiClient.get<ApiStatusResponse>("/api/status");
  return data;
}

export async function getSystems() {
  const { data } = await apiClient.get<SystemsResponse>("/api/systems");
  return data;
}

export async function getSystem(systemId: number) {
  const { data } = await apiClient.get<SystemDetailResponse>(`/api/system/${systemId}`);
  return data;
}

export async function submitManualSystemData() {
  const { data } = await apiClient.post<ManualSubmitResponse>("/manual_submit");
  return data;
}

export async function getDashboardStatus(hostName: string) {
  const { data } = await apiClient.get<DashboardAggregateResponse>("/api/dashboard/status", {
    params: { host_name: hostName },
  });
  return data;
}

export async function getTenants() {
  const { data } = await apiClient.get<TenantsResponse>("/api/tenants");
  return data;
}

export async function createTenant(payload: { name: string; slug?: string; is_active?: boolean }) {
  const { data } = await apiClient.post<TenantMutationResponse>("/api/tenants", payload);
  return data;
}

export async function updateTenantStatus(tenantId: number, isActive: boolean) {
  const { data } = await apiClient.patch<TenantMutationResponse>(`/api/tenants/${tenantId}/status`, { is_active: isActive });
  return data;
}

export async function setTenantStatus(tenantId: number, isActive: boolean) {
  return updateTenantStatus(tenantId, isActive);
}

export async function getTenantControls() {
  const { data } = await apiClient.get<TenantControlsResponse>("/api/tenant-controls");
  return data;
}

export async function updateTenantControls(payload: Record<string, unknown>) {
  const { data } = await apiClient.patch<TenantControlsResponse>("/api/tenant-controls", payload);
  return data;
}

export async function getTenantQuotas() {
  const { data } = await apiClient.get<TenantQuotasResponse>("/api/tenant-quotas");
  return data;
}

export async function updateTenantQuotas(payload: Record<string, unknown>) {
  const { data } = await apiClient.patch<TenantQuotasResponse>("/api/tenant-quotas", payload);
  return data;
}

export async function getTenantUsage() {
  const { data } = await apiClient.get<TenantUsageResponse>("/api/tenant-usage");
  return data;
}

export async function getTenantUsageReport(limit = 10) {
  const { data } = await apiClient.get<TenantUsageReportResponse>("/api/tenant-usage/report", {
    params: { limit },
  });
  return data;
}

export async function getTenantCommercial() {
  const { data } = await apiClient.get<TenantCommercialResponse>("/api/tenant-commercial");
  return data;
}

export async function updateTenantCommercial(payload: Record<string, unknown>) {
  const { data } = await apiClient.patch<TenantCommercialResponse>("/api/tenant-commercial", payload);
  return data;
}

export async function getTenantSettings() {
  const { data } = await apiClient.get<TenantSettingsResponse>("/api/tenant-settings");
  return data;
}

export async function updateTenantSettings(payload: Record<string, unknown>) {
  const { data } = await apiClient.patch<TenantSettingsResponse>("/api/tenant-settings", payload);
  return data;
}

export async function getOidcProviders() {
  const { data } = await apiClient.get<OidcProvidersResponse>("/api/auth/oidc/providers");
  return data;
}

export async function createOidcProvider(payload: Record<string, unknown>) {
  const { data } = await apiClient.post<OidcProviderMutationResponse>("/api/auth/oidc/providers", payload);
  return data;
}

export async function updateOidcProvider(providerId: number, payload: Record<string, unknown>) {
  const { data } = await apiClient.patch<OidcProviderMutationResponse>(`/api/auth/oidc/providers/${providerId}`, payload);
  return data;
}

export async function discoverOidcProvider(providerId: number) {
  const { data } = await apiClient.post<OidcProviderMutationResponse>(`/api/auth/oidc/providers/${providerId}/discover`);
  return data;
}

export async function getTotpStatus() {
  const { data } = await apiClient.get<TotpFactorStatusResponse>("/api/auth/mfa/totp");
  return data;
}

export async function enrollTotp() {
  const { data } = await apiClient.post<TotpFactorStatusResponse>("/api/auth/mfa/totp/enroll");
  return data;
}

export async function activateTotp(code: string) {
  const { data } = await apiClient.post<TotpFactorStatusResponse>("/api/auth/mfa/totp/activate", { code });
  return data;
}

export async function disableTotp(currentPassword: string) {
  const { data } = await apiClient.post<TotpFactorStatusResponse>("/api/auth/mfa/totp/disable", {
    current_password: currentPassword,
  });
  return data;
}

export async function registerUser(payload: { email: string; full_name: string; password: string }) {
  const { data } = await apiClient.post<UserRegistrationResponse>("/api/users", payload);
  return data;
}

export async function getAgentReleases() {
  const { data } = await apiClient.get<AgentReleasesResponse>("/api/agent/releases");
  return data;
}

export async function getAgentBuildStatus() {
  const { data } = await apiClient.get<AgentBuildStatusResponse>("/api/agent/build/status");
  return data;
}

export async function buildAgentBinary() {
  const { data } = await apiClient.post<AgentBuildResponse>("/api/agent/build", {});
  return data;
}

export async function downloadBuiltAgentBinary() {
  const response = await apiClient.get("/api/agent/build/download", { responseType: "blob" });
  return response.data as Blob;
}

export async function getAgentReleasePolicy() {
  const { data } = await apiClient.get<ReleasePolicyResponse>("/api/agent/releases/policy");
  return data;
}

export async function setAgentReleasePolicy(payload: { target_version: string; notes: string }) {
  const { data } = await apiClient.put<ReleasePolicyResponse>("/api/agent/releases/policy", payload);
  return data;
}

export async function getAgentReleaseGuide(currentVersion: string) {
  const { data } = await apiClient.get<ReleaseGuideResponse>("/api/agent/releases/guide", {
    params: { current_version: currentVersion },
  });
  return data;
}

export async function uploadAgentRelease(file: File, version: string) {
  const formData = new FormData();
  formData.append("version", version);
  formData.append("release_file", file);

  const { data } = await apiClient.post("/api/agent/releases/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return data;
}

// Alert APIs
export async function getAlertRules() {
  const { data } = await apiClient.get<AlertRulesResponse>("/api/alerts/rules");
  return data;
}

export async function getAlertSilences() {
  const { data } = await apiClient.get<AlertSilencesResponse>("/api/alerts/silences");
  return data;
}

export async function createAlertRule(payload: {
  name: string;
  metric: string;
  operator: string;
  threshold: number;
  severity: string;
}) {
  const { data } = await apiClient.post<AlertRulesResponse>("/api/alerts/rules", payload);
  return data;
}

export async function evaluateAlerts(payload: Record<string, unknown> = {}) {
  const { data } = await apiClient.post<AlertEvaluationResponse>("/api/alerts/evaluate", payload);
  return data;
}

export async function dispatchAlerts(payload: Record<string, unknown>) {
  const { data } = await apiClient.post<AlertDispatchResponse>("/api/alerts/dispatch", payload);
  return data;
}

export async function prioritizeAlerts(payload: { alerts: AlertRule[]; top_n?: number }) {
  const { data } = await apiClient.post<AlertPrioritizationResponse>("/api/alerts/prioritize", payload);
  return data;
}

export async function getAlertDeliveryHistory(status?: string) {
  const { data } = await apiClient.get<AlertDeliveryHistoryResponse>("/api/alerts/delivery-history", {
    params: status ? { status } : {},
  });
  return data;
}

export async function getAlertDelivery(deliveryId: number) {
  const { data } = await apiClient.get<AlertDeliveryDetailResponse>(`/api/alerts/delivery-history/${deliveryId}`);
  return data;
}

export async function redeliverAlertDelivery(deliveryId: number) {
  const { data } = await apiClient.post<AlertDispatchResponse>(`/api/alerts/delivery-history/${deliveryId}/redeliver`);
  return data;
}

// Automation APIs
export async function getAutomationWorkflows() {
  const { data } = await apiClient.get<AutomationWorkflowsResponse>("/api/automation/workflows");
  return data;
}

export async function createAutomationWorkflow(payload: Record<string, unknown>) {
  const { data } = await apiClient.post<AutomationWorkflowsResponse>("/api/automation/workflows", payload);
  return data;
}

export async function executeAutomationWorkflow(workflowId: number, payload: Record<string, unknown>) {
  const { data } = await apiClient.post<AutomationWorkflowExecutionResponse>(`/api/automation/workflows/${workflowId}/execute`, payload);
  return data;
}

export async function getWorkflowRuns(params?: { workflowId?: number; status?: string }) {
  const { data } = await apiClient.get<WorkflowRunsResponse>("/api/automation/workflow-runs", {
    params: {
      workflow_id: params?.workflowId,
      status: params?.status,
    },
  });
  return data;
}

export async function getWorkflowRun(runId: number) {
  const { data } = await apiClient.get<WorkflowRunDetailResponse>(`/api/automation/workflow-runs/${runId}`);
  return data;
}

export async function getScheduledJobs() {
  const { data } = await apiClient.get<ScheduledJobsResponse>("/api/automation/scheduled-jobs");
  return data;
}

export async function getAutomationServiceStatus(serviceName?: string) {
  const { data } = await apiClient.post<ServiceStatusResponse>("/api/automation/services/status", serviceName ? { service_name: serviceName } : {});
  return data;
}

export async function triggerSelfHealing(payload: { alerts: AlertRule[]; dry_run?: boolean }) {
  const { data } = await apiClient.post<SelfHealingResponse>("/api/automation/self-heal", payload);
  return data;
}

// Logs APIs
export async function ingestLogs(sourceName: string) {
  const { data } = await apiClient.post<LogsIngestResponse>("/api/logs/ingest", { source_name: sourceName });
  return data;
}

export async function getLogSources(params?: { isActive?: boolean; searchText?: string }) {
  const { data } = await apiClient.get<LogSourcesResponse>("/api/logs/sources", {
    params: {
      is_active: params?.isActive,
      search_text: params?.searchText,
    },
  });
  return data;
}

export async function getLogSource(sourceId: number, recentLimit = 10) {
  const { data } = await apiClient.get<LogSourceDetailResponse>(`/api/logs/sources/${sourceId}`, {
    params: { recent_limit: recentLimit },
  });
  return data;
}

export async function updateLogSource(
  sourceId: number,
  payload: {
    description?: string;
    host_name?: string;
    is_active?: boolean;
    source_metadata?: Record<string, unknown>;
  }
) {
  const { data } = await apiClient.patch<LogSourceDetailResponse>(`/api/logs/sources/${sourceId}`, payload);
  return data;
}

export async function getLogEntries(params?: {
  sourceId?: number;
  sourceName?: string;
  severity?: string;
  captureKind?: string;
  eventId?: string;
  queryText?: string;
  page?: number;
  perPage?: number;
}) {
  const { data } = await apiClient.get<LogEntriesResponse>("/api/logs/entries", {
    params: {
      source_id: params?.sourceId,
      source_name: params?.sourceName,
      severity: params?.severity,
      capture_kind: params?.captureKind,
      event_id: params?.eventId,
      query_text: params?.queryText,
      page: params?.page,
      per_page: params?.perPage,
    },
  });
  return data;
}

export async function getLogEntry(entryId: number) {
  const { data } = await apiClient.get<LogEntryDetailResponse>(`/api/logs/entries/${entryId}`);
  return data;
}

export async function getLogInvestigations(status?: string) {
  const { data } = await apiClient.get<LogInvestigationsResponse>("/api/logs/investigations", {
    params: { status },
  });
  return data;
}

export async function createLogInvestigation(payload: Record<string, unknown>) {
  const { data } = await apiClient.post<LogInvestigationMutationResponse>("/api/logs/investigations", payload);
  return data;
}

export async function updateLogInvestigation(investigationId: number, payload: Record<string, unknown>) {
  const { data } = await apiClient.patch<LogInvestigationMutationResponse>(`/api/logs/investigations/${investigationId}`, payload);
  return data;
}

export async function queryEventLogs(sourceName: string) {
  const { data } = await apiClient.post<LogsQueryResponse>("/api/logs/events/query", { source_name: sourceName });
  return data;
}

export async function parseLogEntries(entries: Record<string, unknown>[]) {
  const { data } = await apiClient.post<LogsParseResponse>("/api/logs/parse", { entries });
  return data;
}

export async function correlateEvents(
  events: Record<string, unknown>[],
  payload?: { allowedSeverities?: string[]; minGroupSize?: number }
) {
  const { data } = await apiClient.post<LogsCorrelateResponse>("/api/logs/events/correlate", {
    events,
    allowed_severities: payload?.allowedSeverities ?? [],
    min_group_size: payload?.minGroupSize,
  });
  return data;
}

export async function monitorDriverInventory(hostName: string) {
  const { data } = await apiClient.post<DriverMonitorResponse>("/api/logs/drivers/monitor", { host_name: hostName });
  return data;
}

export async function detectDriverErrors(hostName: string) {
  const { data } = await apiClient.post<DriverErrorsResponse>("/api/logs/drivers/errors", { host_name: hostName });
  return data;
}

export async function streamLogEvents(sourceName: string) {
  const { data } = await apiClient.post<LogsStreamResponse>("/api/logs/events/stream", { source_name: sourceName });
  return data;
}

export async function searchLogs(sourceName: string, queryText: string) {
  const { data } = await apiClient.post<LogsSearchResponse>("/api/logs/search", {
    source_name: sourceName,
    query_text: queryText,
  });
  return data;
}

// Reliability APIs
export async function collectReliabilityHistory(hostName: string) {
  const { data } = await apiClient.post<ReliabilityHistoryResponse>("/api/reliability/history", { host_name: hostName });
  return data;
}

export async function getReliabilityRuns(params?: { hostName?: string; diagnosticType?: string; status?: string; dumpName?: string; errorReason?: string; latestPerType?: boolean }) {
  const { data } = await apiClient.get<ReliabilityRunsResponse>("/api/reliability/runs", {
    params: {
      host_name: params?.hostName,
      diagnostic_type: params?.diagnosticType,
      status: params?.status,
      dump_name: params?.dumpName,
      error_reason: params?.errorReason,
      latest_per_type: params?.latestPerType,
    },
  });
  return data;
}

export async function getReliabilityRun(runId: number) {
  const { data } = await apiClient.get<ReliabilityRunDetailResponse>(`/api/reliability/runs/${runId}`);
  return data;
}

export async function getReliabilityReport(hostName?: string) {
  const { data } = await apiClient.get<ReliabilityReportResponse>("/api/reliability/report", {
    params: { host_name: hostName },
  });
  return data;
}

export async function scoreReliability(hostName: string) {
  const { data } = await apiClient.post<ReliabilityScoreResponse>("/api/reliability/score", { host_name: hostName });
  return data;
}

export async function analyzeReliabilityTrend(hostName: string) {
  const { data } = await apiClient.post<TrendAnalysisResponse>("/api/reliability/trends/analyze", { host_name: hostName });
  return data;
}

export async function predictReliability(hostName: string) {
  const { data } = await apiClient.post<PredictionAnalysisResponse>("/api/reliability/predictions/analyze", { host_name: hostName });
  return data;
}

export async function parseCrashDumps(hostName: string, dumpName: string) {
  const { data } = await apiClient.post<CrashDumpAnalysisResponse>("/api/reliability/crash-dumps/parse", {
    host_name: hostName,
    dump_name: dumpName,
  });
  return data;
}

export async function identifyExceptions(hostName: string, dumpName: string) {
  const { data } = await apiClient.post<ExceptionIdentificationResponse>("/api/reliability/exceptions/identify", {
    host_name: hostName,
    dump_name: dumpName,
  });
  return data;
}

export async function analyzeStackTraces(hostName: string, dumpName: string) {
  const { data } = await apiClient.post<StackTraceAnalysisResponse>("/api/reliability/stack-traces/analyze", {
    host_name: hostName,
    dump_name: dumpName,
  });
  return data;
}

export async function detectPatterns(hostName: string) {
  const { data } = await apiClient.post<PatternDetectionResponse>("/api/reliability/patterns/detect", { host_name: hostName });
  return data;
}

// AI APIs
export async function runOllamaInference(prompt: string) {
  const { data } = await apiClient.post<OllamaInferenceResponse>("/api/ai/ollama/infer", { prompt });
  return data;
}

export async function analyzeRootCause(symptomSummary: string, evidencePoints: string[]) {
  const { data } = await apiClient.post<RootCauseAnalysisResponse>("/api/ai/root-cause/analyze", {
    symptom_summary: symptomSummary,
    evidence_points: evidencePoints,
  });
  return data;
}

export async function generateAiRecommendations(symptomSummary: string, probableCause: string, evidencePoints: string[]) {
  const { data } = await apiClient.post<RecommendationsGenerationResponse>("/api/ai/recommendations/generate", {
    symptom_summary: symptomSummary,
    probable_cause: probableCause,
    evidence_points: evidencePoints,
  });
  return data;
}

export async function getAiOperationsReport(limit = 10) {
  const { data } = await apiClient.get<AiOperationsReportResponse>("/api/ai/operations/report", {
    params: { limit },
  });
  return data;
}

export async function analyzeAnomaly(description: string) {
  const { data } = await apiClient.post<AnomalyAnalysisResponse>("/api/ai/anomaly/analyze", { description });
  return data;
}

export async function explainIncident(description: string) {
  const { data } = await apiClient.post<IncidentExplanationResponse>("/api/ai/incident/explain", { description });
  return data;
}

// Updates APIs
export async function monitorUpdates(hostName: string) {
  const { data } = await apiClient.post<UpdatesMonitorResponse>("/api/updates/monitor", { host_name: hostName });
  return data;
}

export async function getUpdateRuns(params?: { hostName?: string; status?: string }) {
  const { data } = await apiClient.get<UpdateRunsResponse>("/api/updates/runs", {
    params: {
      host_name: params?.hostName,
      status: params?.status,
    },
  });
  return data;
}

export async function getUpdateRun(runId: number) {
  const { data } = await apiClient.get<UpdateRunDetailResponse>(`/api/updates/runs/${runId}`);
  return data;
}

export async function scoreUpdateConfidence(
  hostName: string,
  updates: Record<string, unknown>[],
  reliabilityScore: number,
  updateRunId?: number | null
) {
  const { data } = await apiClient.post<ConfidenceScoreResponse>("/api/ai/confidence/score", {
    host_name: hostName,
    updates,
    reliability_score: reliabilityScore,
    update_run_id: updateRunId,
  });
  return data;
}

// Remote APIs
export async function executeRemoteCommand(host: string, command: string) {
  const { data } = await apiClient.post<RemoteExecResponse>("/api/remote/exec", { host, command });
  return data;
}

// Platform APIs
export async function getCacheStatus() {
  const { data } = await apiClient.get<CacheStatusResponse>("/api/performance/cache/status");
  return data;
}

export async function optimizeDatabase(payload?: Record<string, unknown>) {
  const { data } = await apiClient.post<DatabaseOptimizeResponse>("/api/database/optimize", payload ?? {});
  return data;
}

export async function queueMaintenanceJob(job: string) {
  const { data } = await apiClient.post<MaintenanceJobsResponse>("/api/jobs/maintenance", { job });
  return data;
}

// Backup APIs
export async function getBackups() {
  const { data } = await apiClient.get<BackupsListResponse>("/api/backups");
  return data;
}

export async function createBackup() {
  const { data } = await apiClient.post<BackupCreateResponse>("/api/backups");
  return data;
}

export async function restoreBackup(filename: string) {
  const { data } = await apiClient.post<BackupRestoreResponse>(`/api/backups/${filename}/restore`);
  return data;
}

// Audit APIs
export async function getAuditEvents(filters?: {
  offset?: number;
  limit?: number;
  eventType?: string;
  userId?: number;
  searchText?: string;
  dateFrom?: string;
  dateTo?: string;
}) {
  const { data } = await apiClient.get<AuditEventsResponse>("/api/audit-events", {
    params: {
      offset: filters?.offset ?? 0,
      limit: filters?.limit ?? 50,
      event_type: filters?.eventType,
      user_id: filters?.userId,
      search: filters?.searchText,
      date_from: filters?.dateFrom,
      date_to: filters?.dateTo,
    },
  });
  return data;
}

export async function getOperationsTimeline(limit = 25) {
  const { data } = await apiClient.get<OperationsTimelineResponse>("/api/operations/timeline", {
    params: { limit },
  });
  return data;
}

export function openEventStream<T>(
  path: string,
  handlers: {
    event: string;
    onMessage: (payload: T) => void;
    onOpen?: () => void;
    onError?: () => void;
  },
) {
  const stream = new EventSource(path, { withCredentials: true });
  stream.addEventListener(handlers.event, (event) => {
    const payload = JSON.parse((event as MessageEvent<string>).data) as T;
    handlers.onMessage(payload);
  });
  if (handlers.onOpen) {
    stream.onopen = handlers.onOpen;
  }
  if (handlers.onError) {
    stream.onerror = handlers.onError;
  }
  return stream;
}

export async function getIncidents(status?: string) {
  const { data } = await apiClient.get<IncidentsResponse>("/api/incidents", {
    params: status ? { status } : {},
  });
  return data;
}

export async function getIncident(incidentId: number) {
  const { data } = await apiClient.get<IncidentDetailResponse>(`/api/incidents/${incidentId}`);
  return data;
}

export async function updateIncident(
  incidentId: number,
  payload: { status?: "open" | "acknowledged" | "resolved"; assigned_to_user_id?: number | null; resolution_summary?: string }
) {
  const { data } = await apiClient.patch<IncidentDetailResponse>(`/api/incidents/${incidentId}`, payload);
  return data;
}

export async function getIncidentComments(incidentId: number) {
  const { data } = await apiClient.get<IncidentCommentsResponse>(`/api/incidents/${incidentId}/comments`);
  return data;
}

export async function createIncidentComment(
  incidentId: number,
  payload: { body: string; comment_type?: "note" | "update" | "resolution" | "handoff" }
) {
  const { data } = await apiClient.post<IncidentCommentsResponse>(`/api/incidents/${incidentId}/comments`, payload);
  return data;
}
