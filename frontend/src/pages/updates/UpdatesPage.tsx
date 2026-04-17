import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { JsonViewer } from "../../components/common/JsonViewer";
import { MutationFeedback } from "../../components/common/MutationFeedback";
import { StatCard } from "../../components/common/StatCard";
import { getUpdateRun, getUpdateRuns, monitorUpdates, scoreUpdateConfidence } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";

export function UpdatesPage() {
  const queryClient = useQueryClient();
  const [hostName, setHostName] = useState("localhost");
  const [reliabilityScore, setReliabilityScore] = useState(0.8);
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [lastUpdatesPayload, setLastUpdatesPayload] = useState<Record<string, unknown>[]>([]);
  const [lastUpdateRunId, setLastUpdateRunId] = useState<number | null>(null);

  const runsQuery = useQuery({
    queryKey: [...queryKeys.updateRuns, hostName, statusFilter],
    queryFn: () => getUpdateRuns({ hostName: hostName || undefined, status: statusFilter || undefined }),
    staleTime: 20_000,
  });

  const selectedRunQuery = useQuery({
    queryKey: selectedRunId != null ? queryKeys.updateRun(selectedRunId) : [...queryKeys.updateRuns, "none"],
    queryFn: () => getUpdateRun(selectedRunId as number),
    enabled: selectedRunId != null,
  });

  const refreshUpdateQueries = async () => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.updateRuns });
    if (selectedRunId != null) {
      await queryClient.invalidateQueries({ queryKey: queryKeys.updateRun(selectedRunId) });
    }
  };

  const resetUpdatesView = () => {
    setHostName("localhost");
    setReliabilityScore(0.8);
    setStatusFilter("");
    setSelectedRunId(null);
    setLatestResult(null);
    setActionError(null);
    setLastUpdatesPayload([]);
    setLastUpdateRunId(null);
  };

  const onErr = (err: unknown) => setActionError(err);

  const monitorMutation = useMutation({
    mutationFn: () => monitorUpdates(hostName),
    onSuccess: async (data) => {
      setLatestResult(data);
      setActionError(null);
      const raw = data as { updates?: { updates?: Record<string, unknown>[]; update_run_id?: number } };
      setLastUpdatesPayload(raw?.updates?.updates ?? []);
      setLastUpdateRunId(raw?.updates?.update_run_id ?? null);
      await refreshUpdateQueries();
    },
    onError: onErr,
  });

  const confidenceMutation = useMutation({
    mutationFn: () => scoreUpdateConfidence(hostName, lastUpdatesPayload, reliabilityScore, lastUpdateRunId),
    onSuccess: async (data) => {
      setLatestResult(data);
      setActionError(null);
      await refreshUpdateQueries();
    },
    onError: onErr,
  });

  const runs = Array.isArray(runsQuery.data?.update_runs) ? runsQuery.data.update_runs : [];
  const monitoredCount = runs.reduce((sum, item) => sum + (item.update_count || 0), 0);
  const confidenceCount = runs.filter((item) => item.confidence_score != null).length;

  return (
    <ModulePage
      title="Updates"
      description="Update monitoring with durable history, confidence linkage, and operator drill-down instead of one-shot snapshots."
      actions={
        <div className="module-page-actions-group">
          <button type="button" onClick={refreshUpdateQueries} disabled={runsQuery.isFetching || selectedRunQuery.isFetching}>
            Refresh updates
          </button>
          <button type="button" onClick={resetUpdatesView}>
            Reset updates view
          </button>
        </div>
      }
    >
      <div className="module-grid">
        <StatCard label="Runs" value={runs.length} detail="Persisted update monitoring executions" />
        <StatCard label="Updates Seen" value={monitoredCount} detail="Total updates captured across visible runs" />
        <StatCard label="Confidence Scored" value={confidenceCount} detail="Runs with attached confidence analysis" status={confidenceCount > 0 ? "ok" : "neutral"} />
      </div>

      <ActionPanel title="Update Controls" style={{ marginTop: 12 }}>
        <div className="module-grid">
          <input value={hostName} onChange={(e) => setHostName(e.target.value)} placeholder="Host name" />
          <input
            type="number"
            min={0}
            max={1}
            step="0.1"
            value={reliabilityScore}
            onChange={(e) => setReliabilityScore(Number(e.target.value) || 0)}
            placeholder="Reliability score (0-1)"
          />
        </div>
        <div className="row-between" style={{ marginTop: 12, justifyContent: "flex-start", flexWrap: "wrap" }}>
          <button onClick={() => monitorMutation.mutate()} disabled={monitorMutation.isPending || confidenceMutation.isPending}>Monitor Updates</button>
          <button
            onClick={() => confidenceMutation.mutate()}
            disabled={monitorMutation.isPending || confidenceMutation.isPending || !lastUpdatesPayload.length}
          >
            Score Confidence {lastUpdatesPayload.length ? `(${lastUpdatesPayload.length} updates)` : ""}
          </button>
        </div>
        {!lastUpdatesPayload.length ? (
          <div className="module-status loading" style={{ marginTop: 12 }}>Run update monitoring first so confidence scoring can attach to a persisted update run.</div>
        ) : null}
        <MutationFeedback error={actionError} />
        {latestResult ? (
          <JsonViewer data={latestResult} title="Last response" />
        ) : (
          <div className="module-status loading">Run monitoring or confidence scoring to inspect the latest update result here.</div>
        )}
      </ActionPanel>

      <div className="module-grid" style={{ marginTop: 12 }}>
        <ActionPanel title="Update Run History">
          <div className="module-grid">
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              <option value="success">success</option>
              <option value="failure">failure</option>
            </select>
          </div>
          {runsQuery.isLoading ? <div className="module-status loading" style={{ marginTop: 12 }}>Loading update history...</div> : null}
          {runsQuery.error ? <div className="module-status error-text" style={{ marginTop: 12 }}>Failed to load update run history.</div> : null}
          {!runsQuery.isLoading && !runs.length ? (
            <div className="module-status loading" style={{ marginTop: 12 }}>No update runs match the current filters yet.</div>
          ) : null}
          {runs.length ? (
            <table className="table-lite" style={{ marginTop: 12 }}>
              <thead>
                <tr>
                  <th>When</th>
                  <th>Status</th>
                  <th>Updates</th>
                  <th>Confidence</th>
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
                    <td>{run.status}</td>
                    <td>{run.update_count}</td>
                    <td>{run.confidence_score != null ? run.confidence_score.toFixed(2) : "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </ActionPanel>

        <ActionPanel title="Selected Update Run">
          {selectedRunQuery.data?.update_run ? (
            <JsonViewer data={selectedRunQuery.data.update_run} title="Selected update run" />
          ) : (
            <div className="module-status loading">Select an update run to inspect captured updates and attached confidence data.</div>
          )}
        </ActionPanel>
      </div>
    </ModulePage>
  );
}
