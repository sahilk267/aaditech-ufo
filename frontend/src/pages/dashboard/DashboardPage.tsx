import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
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

  const activeCount = useMemo(() => {
    const systems = systemsQuery.data?.systems || [];
    return systems.filter((s) => s.status === "active").length;
  }, [systemsQuery.data]);

  const isLoading = apiStatusQuery.isLoading || systemsQuery.isLoading;
  const error =
    apiStatusQuery.isError || systemsQuery.isError
      ? "Failed to load API or systems data. Check server connection."
      : null;

  // Sample health trend data
  const chartData = [
    { time: "00:00", health: 95, load: 45 },
    { time: "04:00", health: 92, load: 38 },
    { time: "08:00", health: 88, load: 62 },
    { time: "12:00", health: 91, load: 55 },
    { time: "16:00", health: 94, load: 48 },
    { time: "20:00", health: 96, load: 40 },
  ];

  return (
    <ModulePage
      title="Dashboard"
      description="Live operational overview powered by /api/status, /api/systems, and /api/dashboard/status."
      isLoading={isLoading}
      error={error}
    >
      <div className="grid-cards">
        <StatCard label="API" value={apiStatusQuery.data?.status || "loading"} detail={`Version: ${apiStatusQuery.data?.version || "-"}`} />
        <StatCard label="Systems" value={systemsQuery.data?.count ?? 0} detail={`Active: ${activeCount}`} />
        <StatCard
          label="Aggregate Health"
          value={dashboardStatusQuery.data?.dashboard?.aggregate_health?.overall_status || "unknown"}
          detail={`Cache hit: ${String(dashboardStatusQuery.data?.cache_hit ?? false)}`}
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
        <h3 style={{ marginBottom: 12 }}>System Health Trend</h3>
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
