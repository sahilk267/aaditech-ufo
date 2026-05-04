import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { StatCard } from "../../components/common/StatCard";
import { getApiStatus, getDashboardStatus, getSystems } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";

const SystemHealthChart = lazy(() =>
  import("../../components/dashboard/SystemHealthChart").then((m) => ({ default: m.SystemHealthChart }))
);

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

  // Build chart data from real system inventory — each system becomes a data point.
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
