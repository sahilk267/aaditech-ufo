import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { JsonViewer } from "../../components/common/JsonViewer";
import { MutationFeedback } from "../../components/common/MutationFeedback";
import { StatCard } from "../../components/common/StatCard";
import {
  runAgentEngine,
  listAgentSessions,
  getAgentEngineTools,
} from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";

type SessionRow = {
  id: number;
  session_id: string;
  request_text: string;
  status: string;
  step_summary: { total: number; success: number; failed: number };
  duration_ms: number | null;
  created_at: string | null;
};

type ToolInfo = {
  name: string;
  class: string;
  doc: string;
};

function statusBadge(status: string) {
  if (status === "completed") return "ok";
  if (status === "partial") return "warn";
  if (status === "failed") return "critical";
  return "neutral";
}

export function AgentEnginePage() {
  const [requestText, setRequestText] = useState(
    "Analyze current system health: check CPU and memory metrics, review active alert rules, and provide recommendations."
  );
  const [dryRun, setDryRun] = useState(true);
  const [lastResult, setLastResult] = useState<unknown>(null);
  const [mutationError, setMutationError] = useState<unknown>(null);
  const [selectedSession, setSelectedSession] = useState<unknown>(null);

  const queryClient = useQueryClient();

  const sessionsQuery = useQuery({
    queryKey: queryKeys.agentSessions,
    queryFn: () => listAgentSessions({ limit: 20 }),
  });

  const toolsQuery = useQuery({
    queryKey: queryKeys.agentEngineTools,
    queryFn: () => getAgentEngineTools(),
  });

  const runMutation = useMutation({
    mutationFn: () =>
      runAgentEngine({ request: requestText, dry_run: dryRun }),
    onSuccess: (data) => {
      setLastResult(data);
      setMutationError(null);
      void queryClient.invalidateQueries({ queryKey: queryKeys.agentSessions });
    },
    onError: (err) => {
      setMutationError(err);
    },
  });

  const sessions: SessionRow[] = (sessionsQuery.data as { sessions?: SessionRow[] })?.sessions ?? [];
  const tools: ToolInfo[] = (toolsQuery.data as { tools?: ToolInfo[] })?.tools ?? [];

  const completedCount = sessions.filter((s) => s.status === "completed").length;
  const failedCount = sessions.filter((s) => s.status === "failed").length;
  const partialCount = sessions.filter((s) => s.status === "partial").length;
  const avgDuration =
    sessions.length > 0
      ? Math.round(
          sessions
            .filter((s) => s.duration_ms != null)
            .reduce((sum, s) => sum + (s.duration_ms ?? 0), 0) /
            Math.max(1, sessions.filter((s) => s.duration_ms != null).length)
        )
      : null;

  const resultData = lastResult as Record<string, unknown> | null;
  const planSteps = (resultData?.plan as unknown[]) ?? [];
  const stepResults = (resultData?.step_results as unknown[]) ?? [];
  const stepSummary = resultData?.step_summary as
    | { total: number; success: number; failed: number }
    | undefined;

  return (
    <ModulePage
      title="Agent Engine"
      description="AI-driven orchestration: natural-language requests are decomposed into steps, executed by specialised tools, and synthesised into recommendations."
      isLoading={sessionsQuery.isLoading}
      error={
        sessionsQuery.isError
          ? "Unable to load agent sessions."
          : undefined
      }
      actions={
        <div className="module-page-actions-group">
          <button
            type="button"
            onClick={() =>
              void queryClient.invalidateQueries({ queryKey: queryKeys.agentSessions })
            }
            disabled={sessionsQuery.isFetching}
          >
            Refresh sessions
          </button>
        </div>
      }
    >
      {/* Stats */}
      <div className="stats-grid">
        <StatCard
          label="Total sessions"
          value={sessions.length}
          detail={`${completedCount} completed, ${partialCount} partial`}
          status="neutral"
        />
        <StatCard
          label="Failed sessions"
          value={failedCount}
          detail={failedCount > 0 ? "Check session list for details" : "All runs succeeded"}
          status={failedCount > 0 ? "critical" : "ok"}
        />
        <StatCard
          label="Registered tools"
          value={tools.length}
          detail={tools.map((t) => t.name).join(", ") || "Loading…"}
          status="neutral"
        />
        <StatCard
          label="Avg duration"
          value={avgDuration != null ? `${avgDuration} ms` : "n/a"}
          detail="Across all completed sessions"
          status="neutral"
        />
      </div>

      {/* Run panel */}
      <ActionPanel title="Run Agent">
        <div className="module-grid" style={{ marginBottom: 12 }}>
          <textarea
            rows={4}
            style={{ gridColumn: "1 / -1", resize: "vertical" }}
            value={requestText}
            onChange={(e) => setRequestText(e.target.value)}
            placeholder="Describe what you want the agent to investigate or do…"
          />
        </div>
        <div
          className="row-between"
          style={{ alignItems: "center", marginBottom: 12 }}
        >
          <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
            />
            Dry-run mode (safe — no live workflow execution)
          </label>
          <button
            type="button"
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending || !requestText.trim()}
          >
            {runMutation.isPending ? "Running…" : "Run Agent"}
          </button>
        </div>
        <MutationFeedback error={mutationError} />

        {/* Latest result summary */}
        {resultData && (
          <div className="stats-grid" style={{ marginTop: 12 }}>
            <StatCard
              label="Run status"
              value={String(resultData.status ?? "unknown")}
              detail={`Session: ${String(resultData.session_id ?? "").slice(0, 18)}…`}
              status={statusBadge(String(resultData.status ?? ""))}
            />
            <StatCard
              label="Steps executed"
              value={stepSummary?.total ?? 0}
              detail={`${stepSummary?.success ?? 0} success / ${stepSummary?.failed ?? 0} failed`}
              status={(stepSummary?.failed ?? 0) > 0 ? "warn" : "ok"}
            />
            <StatCard
              label="Plan steps"
              value={planSteps.length}
              detail="Generated by the Planner"
              status="neutral"
            />
            <StatCard
              label="Duration"
              value={
                resultData.duration_ms != null
                  ? `${String(resultData.duration_ms)} ms`
                  : "n/a"
              }
              detail="End-to-end orchestration time"
              status="neutral"
            />
          </div>
        )}
      </ActionPanel>

      {/* Plan viewer */}
      {planSteps.length > 0 && (
        <ActionPanel title="Generated Plan">
          <div className="table-card">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Tool</th>
                  <th>Description</th>
                  <th>Retries</th>
                </tr>
              </thead>
              <tbody>
                {planSteps.map((step, i) => {
                  const s = step as Record<string, unknown>;
                  return (
                    <tr key={i}>
                      <td>{String(s.index ?? i)}</td>
                      <td>
                        <code>{String(s.tool ?? "")}</code>
                      </td>
                      <td>{String(s.description ?? "")}</td>
                      <td>{String(s.retry_limit ?? 2)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </ActionPanel>
      )}

      {/* Step results */}
      {stepResults.length > 0 && (
        <ActionPanel title="Step Execution Results">
          <div className="table-card">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Tool</th>
                  <th>Status</th>
                  <th>Retries</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {stepResults.map((step, i) => {
                  const s = step as Record<string, unknown>;
                  return (
                    <tr
                      key={i}
                      onClick={() => setSelectedSession(step)}
                      style={{ cursor: "pointer" }}
                    >
                      <td>{String(s.step_index ?? i)}</td>
                      <td>
                        <code>{String(s.tool ?? "")}</code>
                      </td>
                      <td
                        style={{
                          color:
                            s.status === "success"
                              ? "var(--color-ok, #22c55e)"
                              : "var(--color-critical, #ef4444)",
                          fontWeight: 600,
                        }}
                      >
                        {String(s.status ?? "")}
                      </td>
                      <td>{String(s.retries ?? 0)}</td>
                      <td>{s.error ? String(s.error).slice(0, 60) : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {selectedSession && (
            <div style={{ marginTop: 12 }}>
              <JsonViewer data={selectedSession} title="Step detail" />
            </div>
          )}
        </ActionPanel>
      )}

      {/* Full result JSON */}
      {resultData && (
        <ActionPanel title="Full Response">
          <JsonViewer data={resultData} title="Orchestration result" />
        </ActionPanel>
      )}

      {/* Session history */}
      <ActionPanel title="Session History">
        {sessions.length > 0 ? (
          <div className="table-card">
            <table>
              <thead>
                <tr>
                  <th>Session ID</th>
                  <th>Request</th>
                  <th>Status</th>
                  <th>Steps</th>
                  <th>Duration</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => (
                  <tr key={session.session_id}>
                    <td>
                      <code style={{ fontSize: "0.8em" }}>
                        {session.session_id.slice(0, 14)}…
                      </code>
                    </td>
                    <td style={{ maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {session.request_text}
                    </td>
                    <td>{session.status}</td>
                    <td>
                      {session.step_summary.total} ({session.step_summary.success} ok / {session.step_summary.failed} fail)
                    </td>
                    <td>
                      {session.duration_ms != null ? `${session.duration_ms} ms` : "n/a"}
                    </td>
                    <td>{session.created_at?.slice(0, 16) ?? "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="module-status loading">
            No agent sessions yet. Submit a request above to start.
          </div>
        )}
      </ActionPanel>

      {/* Tool registry */}
      <ActionPanel title="Registered Tools">
        {tools.length > 0 ? (
          <div className="table-card">
            <table>
              <thead>
                <tr>
                  <th>Tool</th>
                  <th>Class</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                {tools.map((tool) => (
                  <tr key={tool.name}>
                    <td>
                      <code>{tool.name}</code>
                    </td>
                    <td>{tool.class}</td>
                    <td>{tool.doc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="module-status loading">Loading tool registry…</div>
        )}
      </ActionPanel>
    </ModulePage>
  );
}
