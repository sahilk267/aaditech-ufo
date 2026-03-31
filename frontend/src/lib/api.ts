import { apiClient } from "./axios";
import type {
  AgentBuildResponse,
  AgentBuildStatusResponse,
  AgentReleasesResponse,
  AlertDispatchResponse,
  AlertEvaluationResponse,
  AlertPrioritizationResponse,
  AlertRule,
  AlertRulesResponse,
  AlertSilencesResponse,
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
  DriverErrorsResponse,
  DriverMonitorResponse,
  ExceptionIdentificationResponse,
  IncidentExplanationResponse,
  LogsCorrelateResponse,
  LogsIngestResponse,
  LogsParseResponse,
  LogsQueryResponse,
  LogsStreamResponse,
  LogsSearchResponse,
  ManualSubmitResponse,
  MaintenanceJobsResponse,
  OllamaInferenceResponse,
  PatternDetectionResponse,
  PredictionAnalysisResponse,
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
  TenantsResponse,
  TrendAnalysisResponse,
  UpdatesMonitorResponse,
  UserRegistrationResponse,
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

export async function parseCrashDumps(hostName: string) {
  const { data } = await apiClient.post<CrashDumpAnalysisResponse>("/api/reliability/crash-dumps/parse", { host_name: hostName });
  return data;
}

export async function identifyExceptions(hostName: string) {
  const { data } = await apiClient.post<ExceptionIdentificationResponse>("/api/reliability/exceptions/identify", { host_name: hostName });
  return data;
}

export async function analyzeStackTraces(hostName: string) {
  const { data } = await apiClient.post<StackTraceAnalysisResponse>("/api/reliability/stack-traces/analyze", { host_name: hostName });
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

export async function scoreUpdateConfidence(hostName: string, updates: Record<string, unknown>[], reliabilityScore: number) {
  const { data } = await apiClient.post("/api/ai/confidence/score", { host_name: hostName, updates, reliability_score: reliabilityScore });
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
