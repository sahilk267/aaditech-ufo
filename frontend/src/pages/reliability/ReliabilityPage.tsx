import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { JsonViewer } from "../../components/common/JsonViewer";
import { MutationFeedback } from "../../components/common/MutationFeedback";
import { StatCard } from "../../components/common/StatCard";
import {
  analyzeReliabilityTrend,
  analyzeStackTraces,
  collectReliabilityHistory,
  detectPatterns,
  getReliabilityReport,
  getReliabilityRun,
  getReliabilityRuns,
  identifyExceptions,
  parseCrashDumps,
  predictReliability,
  scoreReliability,
} from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";

export function ReliabilityPage() {
  const queryClient = useQueryClient();
  const [hostName, setHostName] = useState("localhost");
  const [dumpName, setDumpName] = useState("access-violation-app.dmp");
  const [diagnosticFilter, setDiagnosticFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [errorReasonFilter, setErrorReasonFilter] = useState("");
  const [latestPerType, setLatestPerType] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  const runsQuery = useQuery({
    queryKey: [...queryKeys.reliabilityRuns, hostName, diagnosticFilter, statusFilter, dumpName, errorReasonFilter, latestPerType],
    queryFn: () =>
      getReliabilityRuns({
        hostName: hostName || undefined,
        diagnosticType: diagnosticFilter || undefined,
        status: statusFilter || undefined,
        dumpName: dumpName || undefined,
        errorReason: errorReasonFilter || undefined,
        latestPerType,
      }),
    staleTime: 20_000,
  });

  const reportQuery = useQuery({
    queryKey: [...queryKeys.reliabilityRuns, "report", hostName],
    queryFn: () => getReliabilityReport(hostName || undefined),
    staleTime: 20_000,
  });

  const selectedRunQuery = useQuery({
    queryKey: selectedRunId != null ? queryKeys.reliabilityRun(selectedRunId) : [...queryKeys.reliabilityRuns, "none"],
    queryFn: () => getReliabilityRun(selectedRunId as number),
    enabled: selectedRunId != null,
  });

  const refreshReliabilityQueries = async () => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.reliabilityRuns });
    if (selectedRunId != null) {
      await queryClient.invalidateQueries({ queryKey: queryKeys.reliabilityRun(selectedRunId) });
    }
  };

  const onOk = async (data: unknown) => {
    setLatestResult(data);
    setActionError(null);
    await refreshReliabilityQueries();
  };
  const onErr = (err: unknown) => setActionError(err);

  const historyMutation = useMutation({ mutationFn: () => collectReliabilityHistory(hostName), onSuccess: onOk, onError: onErr });
  const scoreMutation = useMutation({ mutationFn: () => scoreReliability(hostName), onSuccess: onOk, onError: onErr });
  const trendMutation = useMutation({ mutationFn: () => analyzeReliabilityTrend(hostName), onSuccess: onOk, onError: onErr });
  const predictionMutation = useMutation({ mutationFn: () => predictReliability(hostName), onSuccess: onOk, onError: onErr });
  const patternMutation = useMutation({ mutationFn: () => detectPatterns(hostName), onSuccess: onOk, onError: onErr });
  const crashParseMutation = useMutation({ mutationFn: () => parseCrashDumps(hostName, dumpName), onSuccess: onOk, onError: onErr });
  const exceptionMutation = useMutation({ mutationFn: () => identifyExceptions(hostName, dumpName), onSuccess: onOk, onError: onErr });
  const stackMutation = useMutation({ mutationFn: () => analyzeStackTraces(hostName, dumpName), onSuccess: onOk, onError: onErr });

  const isPending =
    historyMutation.isPending ||
    scoreMutation.isPending ||
    trendMutation.isPending ||
    predictionMutation.isPending ||
    patternMutation.isPending ||
    crashParseMutation.isPending ||
    exceptionMutation.isPending ||
    stackMutation.isPending;

  const runs = Array.isArray(runsQuery.data?.reliability_runs) ? runsQuery.data.reliability_runs : [];
  const selectedRun = selectedRunQuery.data?.reliability_run;
  const successfulRuns = runs.filter((run) => run.status === "success").length;
  const failureRuns = runs.filter((run) => run.status !== "success").length;
  const report = reportQuery.data?.report;
  const latestScore = report?.latest_score || {};
  const latestTrend = report?.latest_trend || {};
  const latestPrediction = report?.latest_prediction || {};
  const recentFailures = Array.isArray(report?.recent_failures) ? report.recent_failures : [];
  const crashRelatedRuns = Array.isArray(report?.crash_related_runs) ? report.crash_related_runs : [];

  return (
    <ModulePage
      title="Reliability"
      description="Operator-facing reliability diagnostics with durable execution history, crash workflows, and drill-down detail."
    >
      <div className="module-grid">
        <StatCard label="Runs" value={report?.total_runs_considered ?? runs.length} detail="Persisted reliability diagnostic executions" />
        <StatCard label="Succeeded" value={successfulRuns} detail="Runs that completed successfully" status={successfulRuns > 0 ? "ok" : "neutral"} />
        <StatCard label="Failed" value={failureRuns} detail="Runs that need investigation" status={failureRuns > 0 ? "error" : "neutral"} />
        <StatCard label="Latest Score" value={String((latestScore as { current_score?: number }).current_score ?? "n/a")} detail={String((latestScore as { health_band?: string }).health_band ?? "No score yet")} status={failureRuns > 0 ? "error" : "ok"} />
      </div>

      <div className="module-grid" style={{ marginTop: 12 }}>
        <ActionPanel title="Operator Summary">
          {reportQuery.isLoading ? <div className="module-status loading">Loading reliability summary...</div> : null}
          {reportQuery.error ? <div className="module-status error-text">Failed to load reliability summary.</div> : null}
          {!reportQuery.isLoading && !reportQuery.error ? (
            <div className="stack-sm">
              <div>Trend: {String((latestTrend as { direction?: string }).direction ?? "n/a")}</div>
              <div>Predicted score: {String((latestPrediction as { predicted_score?: number }).predicted_score ?? "n/a")}</div>
              <div>Failure reasons: {Object.keys(report?.failure_reasons || {}).length ? JSON.stringify(report?.failure_reasons) : "None"}</div>
            </div>
          ) : null}
        </ActionPanel>
        <ActionPanel title="Recent Failures">
          {!recentFailures.length ? (
            <div className="module-status loading">No recent reliability failures recorded.</div>
          ) : (
            <table className="table-lite">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Type</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {recentFailures.map((run) => (
                  <tr key={run.id} onClick={() => setSelectedRunId(run.id)} style={{ cursor: "pointer" }}>
                    <td>{run.created_at || "n/a"}</td>
                    <td>{run.diagnostic_type}</td>
                    <td>{run.error_reason || "unknown"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </ActionPanel>
      </div>

      <ActionPanel title="Diagnostics" style={{ marginTop: 12 }}>
        <div className="module-grid">
          <input value={hostName} onChange={(e) => setHostName(e.target.value)} placeholder="Host name" />
          <input value={dumpName} onChange={(e) => setDumpName(e.target.value)} placeholder="Crash dump name" />
        </div>
        <div className="row-between" style={{ marginTop: 12, flexWrap: "wrap", justifyContent: "flex-start" }}>
          <button onClick={() => historyMutation.mutate()} disabled={isPending}>Collect History</button>
          <button onClick={() => scoreMutation.mutate()} disabled={isPending}>Score</button>
          <button onClick={() => trendMutation.mutate()} disabled={isPending}>Analyze Trend</button>
          <button onClick={() => predictionMutation.mutate()} disabled={isPending}>Predict</button>
          <button onClick={() => patternMutation.mutate()} disabled={isPending}>Patterns</button>
          <button onClick={() => crashParseMutation.mutate()} disabled={isPending}>Parse Dump</button>
          <button onClick={() => exceptionMutation.mutate()} disabled={isPending}>Identify Exception</button>
          <button onClick={() => stackMutation.mutate()} disabled={isPending}>Stack Trace</button>
        </div>
        <MutationFeedback error={actionError} />
        {latestResult ? (
          <JsonViewer data={latestResult} title="Last response" />
        ) : (
          <div className="module-status loading">Run a diagnostic to populate durable history and inspect the latest response.</div>
        )}
      </ActionPanel>

      <div className="module-grid" style={{ marginTop: 12 }}>
        <ActionPanel title="Run History">
          <div className="module-grid">
            <select value={diagnosticFilter} onChange={(e) => setDiagnosticFilter(e.target.value)}>
              <option value="">All diagnostic types</option>
              <option value="history">history</option>
              <option value="score">score</option>
              <option value="trend">trend</option>
              <option value="prediction">prediction</option>
              <option value="patterns">patterns</option>
              <option value="crash_dump_parse">crash_dump_parse</option>
              <option value="exception_identify">exception_identify</option>
              <option value="stack_trace_analyze">stack_trace_analyze</option>
            </select>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              <option value="success">success</option>
              <option value="failure">failure</option>
            </select>
            <input value={errorReasonFilter} onChange={(e) => setErrorReasonFilter(e.target.value)} placeholder="Error reason filter" />
            <label className="row-between" style={{ alignItems: "center" }}>
              <span>Latest per type</span>
              <input type="checkbox" checked={latestPerType} onChange={(e) => setLatestPerType(e.target.checked)} />
            </label>
          </div>
          {runsQuery.isLoading ? <div className="module-status loading" style={{ marginTop: 12 }}>Loading reliability runs...</div> : null}
          {runsQuery.error ? <div className="module-status error-text" style={{ marginTop: 12 }}>Failed to load reliability run history.</div> : null}
          {!runsQuery.isLoading && !runs.length ? (
            <div className="module-status loading" style={{ marginTop: 12 }}>No reliability runs match the current filters yet.</div>
          ) : null}
          {runs.length ? (
            <table className="table-lite" style={{ marginTop: 12 }}>
              <thead>
                <tr>
                  <th>When</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Summary</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr
                    key={run.id}
                    className={selectedRunId === run.id ? "selected-row" : undefined}
                    onClick={() => setSelectedRunId(run.id)}
                    style={{ cursor: "pointer" }}
                  >
                    <td>{run.created_at || "n/a"}</td>
                    <td>{run.diagnostic_type}</td>
                    <td>{run.status}</td>
                    <td>{JSON.stringify(run.summary || {})}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </ActionPanel>

        <ActionPanel title="Run Detail">
          {selectedRun ? (
            <>
              <JsonViewer data={selectedRun} title="Selected reliability run" />
              {selectedRun.related_runs?.length ? (
                <table className="table-lite" style={{ marginTop: 12 }}>
                  <thead>
                    <tr>
                      <th>Related At</th>
                      <th>Type</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedRun.related_runs.map((run) => (
                      <tr key={run.id} onClick={() => setSelectedRunId(run.id)} style={{ cursor: "pointer" }}>
                        <td>{run.created_at || "n/a"}</td>
                        <td>{run.diagnostic_type}</td>
                        <td>{run.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null}
            </>
          ) : (
            <div className="module-status loading">Select a persisted reliability run to inspect full request/result detail.</div>
          )}
        </ActionPanel>
      </div>

      <ActionPanel title="Crash Investigation Timeline" style={{ marginTop: 12 }}>
        {!crashRelatedRuns.length ? (
          <div className="module-status loading">No crash-related runs recorded for the current host filter.</div>
        ) : (
          <table className="table-lite">
            <thead>
              <tr>
                <th>When</th>
                <th>Dump</th>
                <th>Type</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {crashRelatedRuns.map((run) => (
                <tr key={run.id} onClick={() => setSelectedRunId(run.id)} style={{ cursor: "pointer" }}>
                  <td>{run.created_at || "n/a"}</td>
                  <td>{run.dump_name || "n/a"}</td>
                  <td>{run.diagnostic_type}</td>
                  <td>{run.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </ActionPanel>
    </ModulePage>
  );
}
