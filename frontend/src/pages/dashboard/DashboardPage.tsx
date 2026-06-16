import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { StatCard } from "../../components/common/StatCard";
import { getApiStatus, getDashboardStatus, getOnboardingStatus, getSystems, listRollouts } from "../../lib/api";
import type { OnboardingAgent } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";

const SystemHealthChart = lazy(() =>
  import("../../components/dashboard/SystemHealthChart").then((m) => ({ default: m.SystemHealthChart }))
);

// Badge CSS class for rollout status
function rolloutBadgeClass(status: string): string {
  const map: Record<string, string> = {
    draft: "badge--draft",
    testing: "badge--testing",
    rolling_out: "badge--rolling-out",
    completed: "badge--completed",
    rolled_back: "badge--rolled-back",
  };
  return `badge ${map[status] ?? "badge--draft"}`;
}

interface RolloutBatch {
  batch_num: number;
  percentage: number;
  status: string;
  agents_total: number;
  agents_updated: number;
  agent_serials: string[];
}

interface ActiveRollout {
  id: number;
  version: string;
  status: string;
  current_batch: number;
  total_batches: number;
  notes: string;
  started_at: string | null;
  batches?: RolloutBatch[];
}

// ── Onboarding Status Widget ─────────────────────────────────────────────────
function OnboardingStatusWidget() {
  const q = useQuery({
    queryKey: ["agent", "onboarding-status"],
    queryFn: getOnboardingStatus,
    staleTime: 60_000,
    refetchInterval: 60_000,
  });

  if (q.isPending) {
    return (
      <div className="module-card" style={{ marginTop: 12 }}>
        <p className="section-label">Fleet Onboarding — Last 24 h</p>
        <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>Loading…</div>
      </div>
    );
  }
  if (q.isError || !q.data) return null;

  const d = q.data;
  const allCheckedIn = d.new_agents_count > 0 && d.checked_in_count === d.new_agents_count;
  const someCheckedIn = d.checked_in_count > 0 && !allCheckedIn;

  return (
    <div className="module-card" style={{ marginTop: 12 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div>
          <p className="section-label" style={{ marginBottom: 2 }}>Fleet Onboarding — Last 24 h</p>
          <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 600, color: "#0f172a" }}>
            {d.new_agents_count === 0
              ? "No new agents"
              : `${d.new_agents_count} new agent${d.new_agents_count !== 1 ? "s" : ""} enrolled`}
          </h3>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="stat-pill" style={{ background: "#f0fdf4", color: "#166534", border: "1px solid #bbf7d0" }}>
            {d.active_agents} active now
          </span>
          <span className="stat-pill" style={{ background: "#f8fafc", color: "#475569", border: "1px solid #e2e8f0" }}>
            {d.total_agents} total
          </span>
        </div>
      </div>

      {d.new_agents_count === 0 ? (
        <div style={{ color: "#64748b", fontSize: "0.85rem" }}>
          Fleet is stable — no new machines enrolled in the last 24 hours.
          Use <strong>Releases → Setup Instructions</strong> to onboard a new host.
        </div>
      ) : (
        <>
          {/* Check-in progress bar */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", color: "#64748b", marginBottom: 4 }}>
              <span>Checked in ({d.checked_in_count} / {d.new_agents_count})</span>
              <span>{d.new_agents_count > 0 ? Math.round((d.checked_in_count / d.new_agents_count) * 100) : 0}%</span>
            </div>
            <div className="progress-track">
              <div
                className={`progress-fill${allCheckedIn ? " progress-fill--done" : someCheckedIn ? "" : " progress-fill--warn"}`}
                style={{ width: `${d.new_agents_count > 0 ? (d.checked_in_count / d.new_agents_count) * 100 : 0}%` }}
              />
            </div>
          </div>

          {/* New agent rows */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {d.new_agents.map((a: OnboardingAgent) => (
              <div
                key={a.serial_number}
                style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "8px 12px", borderRadius: 8,
                  background: a.checked_in ? "#f0fdf4" : "#fffbeb",
                  border: `1px solid ${a.checked_in ? "#bbf7d0" : "#fde68a"}`,
                  fontSize: "0.83rem",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: "1rem" }}>{a.checked_in ? "✅" : "⏳"}</span>
                  <div>
                    <div style={{ fontWeight: 600, color: "#0f172a" }}>{a.hostname}</div>
                    <div style={{ color: "#64748b", fontSize: "0.78rem" }}>
                      {a.serial_number}
                      {a.agent_version ? ` · v${a.agent_version}` : ""}
                    </div>
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontWeight: 500, color: a.checked_in ? "#166534" : "#92400e" }}>
                    {a.checked_in ? "Checked in" : "Awaiting heartbeat"}
                  </div>
                  <div style={{ color: "#94a3b8", fontSize: "0.75rem" }}>
                    enrolled {new Date(a.created_at).toLocaleTimeString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function RolloutProgressWidget() {
  const rolloutsQ = useQuery({
    queryKey: queryKeys.rollouts,
    queryFn: listRollouts,
    staleTime: 15_000,
    refetchInterval: 20_000,
  });

  const activeRollout = useMemo(() => {
    const list = (rolloutsQ.data?.rollouts ?? []) as ActiveRollout[];
    return list.find((r) => r.status === "rolling_out" || r.status === "testing") ?? null;
  }, [rolloutsQ.data]);

  if (rolloutsQ.isLoading) {
    return (
      <div className="module-card" style={{ marginTop: 20 }}>
        <div className="module-status loading">Loading rollout status…</div>
      </div>
    );
  }

  if (!activeRollout) {
    return (
      <div className="module-card" style={{ marginTop: 20 }}>
        <div className="row-between" style={{ marginBottom: 4 }}>
          <h3 style={{ margin: 0, fontSize: "1rem" }}>Active Rollout</h3>
          <span className="badge badge--completed">No active rollout</span>
        </div>
        <p style={{ margin: "8px 0 0", fontSize: "0.85rem", color: "#94a3b8" }}>
          No rollout is currently in progress. Go to{" "}
          <a href="/app/releases" style={{ color: "#0f766e" }}>Releases → Batched Rollout</a>{" "}
          to start one.
        </p>
      </div>
    );
  }

  // Get in-progress batch
  const batches = (activeRollout.batches ?? []) as RolloutBatch[];
  const currentBatch = batches.find((b) => b.status === "in_progress") ?? batches[activeRollout.current_batch - 1];
  const completedBatches = batches.filter((b) => b.status === "completed").length;
  const overallPct = activeRollout.total_batches > 0
    ? Math.round((completedBatches / activeRollout.total_batches) * 100)
    : 0;

  const batchUpdated = currentBatch?.agents_updated ?? 0;
  const batchTotal = currentBatch?.agents_total ?? 0;
  const batchPct = batchTotal > 0 ? Math.round((batchUpdated / batchTotal) * 100) : 0;

  return (
    <div className="module-card" style={{ marginTop: 20 }}>
      {/* Header */}
      <div className="row-between" style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <h3 style={{ margin: 0, fontSize: "1rem" }}>Active Rollout</h3>
          <span className="version-chip">v{activeRollout.version}</span>
        </div>
        <span className={rolloutBadgeClass(activeRollout.status)}>
          {activeRollout.status.replace(/_/g, " ")}
        </span>
      </div>

      {activeRollout.notes && (
        <p style={{ margin: "0 0 12px", fontSize: "0.85rem", color: "#64748b" }}>{activeRollout.notes}</p>
      )}

      {/* Stats row */}
      <div className="stat-row" style={{ marginBottom: 14 }}>
        <div className="stat-pill">
          <strong>{completedBatches}/{activeRollout.total_batches}</strong>
          <span>Batches done</span>
        </div>
        <div className="stat-pill">
          <strong>{activeRollout.current_batch}</strong>
          <span>Current batch</span>
        </div>
        {currentBatch && (
          <>
            <div className="stat-pill">
              <strong style={{ color: "#15803d" }}>{batchUpdated}</strong>
              <span>Updated</span>
            </div>
            <div className="stat-pill">
              <strong>{batchTotal}</strong>
              <span>In batch</span>
            </div>
          </>
        )}
      </div>

      {/* Overall rollout progress */}
      <div style={{ marginBottom: 10 }}>
        <div className="row-between" style={{ marginBottom: 5, fontSize: "0.82rem", color: "#64748b" }}>
          <span>Overall rollout progress</span>
          <span>{overallPct}%</span>
        </div>
        <div className="progress-track">
          <div
            className="progress-fill"
            style={{ width: `${overallPct}%` }}
          />
        </div>
      </div>

      {/* Current batch progress */}
      {currentBatch && batchTotal > 0 && (
        <div style={{ marginBottom: 4 }}>
          <div className="row-between" style={{ marginBottom: 5, fontSize: "0.82rem", color: "#64748b" }}>
            <span>Batch {currentBatch.batch_num} ({currentBatch.percentage}% of fleet)</span>
            <span>{batchPct}% — {batchUpdated}/{batchTotal} agents on v{activeRollout.version}</span>
          </div>
          <div className="progress-track">
            <div
              className={`progress-fill${batchPct === 100 ? " progress-fill--done" : ""}`}
              style={{ width: `${batchPct}%` }}
            />
          </div>
        </div>
      )}

      {/* Batch pills */}
      {batches.length > 0 && (
        <div style={{ display: "flex", gap: 6, marginTop: 12, flexWrap: "wrap" }}>
          {batches.map((b) => (
            <div
              key={b.batch_num}
              title={`Batch ${b.batch_num}: ${b.agents_updated}/${b.agents_total} agents updated`}
              style={{
                padding: "4px 12px",
                borderRadius: 20,
                fontSize: "0.75rem",
                fontWeight: 600,
                background:
                  b.status === "completed" ? "#dcfce7" :
                  b.status === "in_progress" ? "#fef9c3" :
                  b.status === "cancelled" ? "#fee2e2" :
                  "#f1f5f9",
                color:
                  b.status === "completed" ? "#15803d" :
                  b.status === "in_progress" ? "#a16207" :
                  b.status === "cancelled" ? "#b91c1c" :
                  "#64748b",
                border: b.status === "in_progress" ? "2px solid #fcd34d" : "1px solid transparent",
              }}
            >
              B{b.batch_num} — {b.percentage}%
            </div>
          ))}
        </div>
      )}

      {activeRollout.started_at && (
        <p style={{ margin: "10px 0 0", fontSize: "0.75rem", color: "#94a3b8" }}>
          Started {new Date(activeRollout.started_at).toLocaleString()} ·{" "}
          <a href="/app/releases" style={{ color: "#0f766e" }}>Manage rollout →</a>
        </p>
      )}

      {activeRollout.status === "rolling_out" && (
        <p style={{ margin: "6px 0 0", fontSize: "0.75rem", color: "#94a3b8" }}>
          Auto-refreshes every 20 s — agents report progress via heartbeat.
        </p>
      )}
    </div>
  );
}

export function DashboardPage() {
  const [manualHostName, setHostName] = useState<string | null>(null);
  const [showChart, setShowChart] = useState(false);

  const apiStatusQuery = useQuery({
    queryKey: queryKeys.apiStatus,
    queryFn: getApiStatus,
    staleTime: 30_000,
  });

  const systemsQuery = useQuery({
    queryKey: queryKeys.systems,
    queryFn: getSystems,
    staleTime: 30_000,
  });

  const hostName = manualHostName ?? systemsQuery.data?.systems?.[0]?.hostname ?? "";

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setShowChart(true);
    }, 700);
    return () => window.clearTimeout(timeoutId);
  }, []);

  const dashboardStatusQuery = useQuery({
    queryKey: queryKeys.dashboardStatus(hostName || "none"),
    queryFn: () => getDashboardStatus(hostName),
    enabled: Boolean(hostName),
    staleTime: 45_000,
  });

  const queryClient = useQueryClient();

  const refreshDashboardData = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.apiStatus });
    void queryClient.invalidateQueries({ queryKey: queryKeys.systems });
    void queryClient.invalidateQueries({ queryKey: queryKeys.dashboardStatus(hostName || "none") });
    void queryClient.invalidateQueries({ queryKey: queryKeys.rollouts });
  };

  const resetDashboardView = () => {
    setHostName(null);
    setShowChart(false);
    void queryClient.invalidateQueries({ queryKey: queryKeys.dashboardStatus("none") });
  };

  const activeCount = useMemo(() => {
    const systems = systemsQuery.data?.systems || [];
    return systems.filter((s) => s.status === "active").length;
  }, [systemsQuery.data]);

  const isLoading = apiStatusQuery.isLoading || systemsQuery.isLoading;
  const error =
    apiStatusQuery.isError || systemsQuery.isError
      ? "Failed to load API or systems data. Check server connection."
      : null;

  const chartData = useMemo(() => {
    type SystemRow = {
      hostname?: string;
      cpu_usage?: number;
      ram_usage?: number;
      status?: string;
    };
    const systems = (systemsQuery.data?.systems ?? []) as SystemRow[];
    if (systems.length === 0) {
      return [{ time: "No data", health: 0, load: 0 }];
    }
    return systems.slice(0, 10).map((s, i) => {
      const cpu = typeof s.cpu_usage === "number" ? s.cpu_usage : 0;
      const health = s.status === "active" ? Math.max(0, Math.min(100, 100 - cpu * 0.6)) : 40;
      return {
        time: s.hostname ? String(s.hostname).slice(0, 12) : `Sys ${i + 1}`,
        health: Math.round(health),
        load: Math.round(cpu),
      };
    });
  }, [systemsQuery.data]);

  return (
    <ModulePage
      title="Dashboard"
      description="Live operational overview powered by /api/status, /api/systems, and /api/dashboard/status."
      isLoading={isLoading}
      error={error}
      actions={
        <div className="module-page-actions-group">
          <button
            type="button"
            onClick={refreshDashboardData}
            disabled={apiStatusQuery.isFetching || systemsQuery.isFetching || dashboardStatusQuery.isFetching}
          >
            Refresh dashboard
          </button>
          <button type="button" onClick={resetDashboardView}>
            Reset host
          </button>
        </div>
      }
    >
      <div className="grid-cards">
        <StatCard
          label="API"
          value={apiStatusQuery.data?.status || "loading"}
          detail={`Version: ${apiStatusQuery.data?.version || "-"}`}
          status={apiStatusQuery.data?.status === "ok" ? "ok" : "neutral"}
        />
        <StatCard
          label="Systems"
          value={systemsQuery.data?.count ?? 0}
          detail={`Active: ${activeCount}`}
          status={activeCount > 0 ? "ok" : "warn"}
        />
        <StatCard
          label="Aggregate Health"
          value={dashboardStatusQuery.data?.dashboard?.aggregate_health?.overall_status || "unknown"}
          detail={`Cache hit: ${String(dashboardStatusQuery.data?.cache_hit ?? false)}`}
          status={
            dashboardStatusQuery.data?.dashboard?.aggregate_health?.overall_status === "healthy"
              ? "ok"
              : dashboardStatusQuery.data?.dashboard?.aggregate_health?.overall_status
              ? "warn"
              : "neutral"
          }
        />
        <StatCard
          label="Chart data points"
          value={chartData.length}
          detail="Systems shown in health trend"
          status="neutral"
        />
      </div>

      {/* Fleet onboarding status widget */}
      <OnboardingStatusWidget />

      {/* Live rollout progress widget */}
      <RolloutProgressWidget />

      <ActionPanel style={{ marginTop: 12 }}>
        <label style={{ display: "grid", gap: 6, maxWidth: 360 }}>
          Host Name (for /api/dashboard/status)
          <input value={hostName} onChange={(e) => setHostName(e.target.value)} placeholder="Enter host name" />
        </label>
        {dashboardStatusQuery.isError ? (
          <div className="error-text" style={{ marginTop: 12 }}>Failed to load dashboard status for selected host.</div>
        ) : null}
      </ActionPanel>

      <div style={{ marginTop: 24 }}>
        <h3 style={{ marginBottom: 12 }}>
          System Health Trend
          <small style={{ fontWeight: 400, fontSize: "0.75em", marginLeft: 10, color: "#64748b" }}>
            — real data from {chartData.length} system{chartData.length !== 1 ? "s" : ""}
          </small>
        </h3>
        {showChart ? (
          <Suspense fallback={<div className="module-status loading">Loading chart...</div>}>
            <SystemHealthChart data={chartData} />
          </Suspense>
        ) : (
          <div className="module-status loading">Preparing chart...</div>
        )}
      </div>
    </ModulePage>
  );
}
