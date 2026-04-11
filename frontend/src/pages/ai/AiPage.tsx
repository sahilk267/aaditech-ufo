import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { JsonViewer } from "../../components/common/JsonViewer";
import { MutationFeedback } from "../../components/common/MutationFeedback";
import { StatCard } from "../../components/common/StatCard";
import {
  analyzeRootCause,
  getAiOperationsReport,
  generateAiRecommendations,
  runOllamaInference,
} from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";

function formatActionLabel(action: string) {
  return action.replace(/^ai\./, "").replaceAll(".", " ");
}

export function AiPage() {
  const [prompt, setPrompt] = useState("Summarize possible root causes for high CPU spikes");
  const [symptomSummary, setSymptomSummary] = useState("CPU usage spikes above 95% every 5 minutes");
  const [probableCause, setProbableCause] = useState("Scheduled task overloading worker service");
  const [evidenceText, setEvidenceText] = useState("task scheduler logs show repeating trigger\nservice restart loop");
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  const onOk = (data: unknown) => { setLatestResult(data); setActionError(null); };
  const onErr = (err: unknown) => setActionError(err);

  const aiOperationsQuery = useQuery({
    queryKey: queryKeys.aiOperationsReport,
    queryFn: () => getAiOperationsReport(8),
  });

  const inferenceMutation = useMutation({ mutationFn: () => runOllamaInference(prompt), onSuccess: onOk, onError: onErr });
  const rootCauseMutation = useMutation({ mutationFn: () => analyzeRootCause(symptomSummary, evidenceText.split("\n").filter(Boolean)), onSuccess: onOk, onError: onErr });
  const recommendationsMutation = useMutation({
    mutationFn: () => generateAiRecommendations(symptomSummary, probableCause, evidenceText.split("\n").filter(Boolean)),
    onSuccess: onOk,
    onError: onErr,
  });

  const isPending = inferenceMutation.isPending || rootCauseMutation.isPending || recommendationsMutation.isPending;
  const report = aiOperationsQuery.data?.report;
  const latestObservability = useMemo(() => {
    if (!latestResult || typeof latestResult !== "object") {
      return null;
    }

    const result = latestResult as Record<string, unknown>;
    const candidate =
      (result.ollama as Record<string, unknown> | undefined)?.observability ??
      (result.analysis as Record<string, unknown> | undefined)?.observability ??
      (result.recommendations as Record<string, unknown> | undefined)?.observability ??
      (result.assistant as Record<string, unknown> | undefined)?.observability ??
      (result.learning_feedback as Record<string, unknown> | undefined)?.observability ??
      (result.anomaly_analysis as Record<string, unknown> | undefined)?.observability ??
      (result.incident_explanation as Record<string, unknown> | undefined)?.observability;

    return candidate && typeof candidate === "object" ? (candidate as Record<string, unknown>) : null;
  }, [latestResult]);
  const recentOperations = report?.recent_operations ?? [];
  const recentFailures = report?.recent_failures ?? [];
  const topAction = Object.entries(report?.counts.by_action ?? {}).sort((a, b) => b[1] - a[1])[0];
  const topAdapter = Object.entries(report?.counts.by_adapter ?? {}).sort((a, b) => b[1] - a[1])[0];
  const topError = Object.entries(report?.counts.by_primary_error_reason ?? {}).sort((a, b) => b[1] - a[1])[0];

  return (
    <ModulePage
      title="AI Operations"
      description="Inference, root-cause analysis, recommendations, and operator diagnostics using /api/ai/* endpoints."
      isLoading={aiOperationsQuery.isLoading}
      error={aiOperationsQuery.isError ? "Unable to load AI operations report." : undefined}
    >
      <div className="stats-grid">
        <StatCard
          label="AI events"
          value={report?.summary.total_events ?? 0}
          detail={topAction ? `Top action: ${formatActionLabel(topAction[0])}` : "No AI activity yet"}
          status="neutral"
        />
        <StatCard
          label="Success rate"
          value={report?.summary.success_rate != null ? `${report.summary.success_rate}%` : "n/a"}
          detail={`${report?.summary.success_count ?? 0} success / ${report?.summary.failure_count ?? 0} failure`}
          status={(report?.summary.failure_count ?? 0) > 0 ? "warn" : "ok"}
        />
        <StatCard
          label="Fallback usage"
          value={report?.summary.fallback_count ?? 0}
          detail={topAdapter ? `Primary adapter: ${topAdapter[0]}` : "No adapter data yet"}
          status={(report?.summary.fallback_count ?? 0) > 0 ? "warn" : "ok"}
        />
        <StatCard
          label="Avg duration"
          value={report?.summary.avg_duration_ms != null ? `${report.summary.avg_duration_ms} ms` : "n/a"}
          detail={topError ? `Recent error: ${topError[0]}` : "No recent error reasons"}
          status={topError ? "warn" : "ok"}
        />
      </div>

      <ActionPanel title="Inputs">
        <div className="module-grid">
          <input value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Inference prompt" />
          <input value={symptomSummary} onChange={(e) => setSymptomSummary(e.target.value)} placeholder="Symptom summary" />
          <input value={probableCause} onChange={(e) => setProbableCause(e.target.value)} placeholder="Probable cause" />
          <input value={evidenceText} onChange={(e) => setEvidenceText(e.target.value)} placeholder="Evidence (one per line)" />
        </div>
        <div className="row-between" style={{ marginTop: 12 }}>
          <button onClick={() => inferenceMutation.mutate()} disabled={isPending}>Run Inference</button>
          <button onClick={() => rootCauseMutation.mutate()} disabled={isPending}>Analyze Root Cause</button>
          <button onClick={() => recommendationsMutation.mutate()} disabled={isPending}>Generate Recommendations</button>
        </div>
        <MutationFeedback error={actionError} />
        {latestResult ? (
          <JsonViewer data={latestResult} title="Last response" />
        ) : (
          <div className="module-status loading">Run an AI operation to inspect the latest inference or recommendation payload.</div>
        )}
      </ActionPanel>

      <ActionPanel title="Runtime Diagnostics">
        {latestObservability ? (
          <div className="stats-grid">
            <StatCard
              label="Requested adapter"
              value={String(latestObservability.requested_adapter ?? "n/a")}
              detail={`Fallback used: ${String(latestObservability.fallback_used ?? false)}`}
              status={latestObservability.fallback_used ? "warn" : "ok"}
            />
            <StatCard
              label="Duration"
              value={latestObservability.duration_ms != null ? `${String(latestObservability.duration_ms)} ms` : "n/a"}
              detail={String(latestObservability.primary_error_reason ?? "No primary error")}
              status={latestObservability.primary_error_reason ? "warn" : "ok"}
            />
          </div>
        ) : (
          <div className="module-status loading">Run an AI operation to inspect live adapter, fallback, and duration diagnostics.</div>
        )}
      </ActionPanel>

      <ActionPanel title="Recent AI Operations">
        {recentOperations.length ? (
          <div className="table-card">
            <table>
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Outcome</th>
                  <th>Adapter</th>
                  <th>Fallback</th>
                  <th>Duration</th>
                </tr>
              </thead>
              <tbody>
                {recentOperations.map((item) => (
                  <tr key={item.id}>
                    <td>{formatActionLabel(item.action)}</td>
                    <td>{item.outcome}</td>
                    <td>{item.adapter ?? "n/a"}</td>
                    <td>{item.fallback_used ? "yes" : "no"}</td>
                    <td>{item.duration_ms != null ? `${item.duration_ms} ms` : "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="module-status loading">No AI operations recorded yet for this tenant.</div>
        )}
      </ActionPanel>

      <ActionPanel title="Recent Failures">
        {recentFailures.length ? (
          <div className="table-card">
            <table>
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Reason</th>
                  <th>Adapter</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {recentFailures.map((item) => (
                  <tr key={item.id}>
                    <td>{formatActionLabel(item.action)}</td>
                    <td>{item.primary_error_reason ?? item.reason ?? "unknown"}</td>
                    <td>{item.adapter ?? "n/a"}</td>
                    <td>{item.created_at ?? "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="module-status loading">No recent AI failures recorded.</div>
        )}
      </ActionPanel>
    </ModulePage>
  );
}
