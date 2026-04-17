import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { MutationFeedback } from "../../components/common/MutationFeedback";
import { collectReliabilityHistory, getSystems } from "../../lib/api";

type ReliabilityRecord = {
  timestamp?: string;
  source?: string;
  product?: string;
  event_id?: string;
  message?: string;
};

function normalizeTimestamp(value: string | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function getWindowHours(label: string): number | null {
  if (label === "1h") return 1;
  if (label === "24h") return 24;
  if (label === "7d") return 24 * 7;
  return null;
}

export function HistoryPage() {
  const [hostName, setHostName] = useState("");
  const [searchText, setSearchText] = useState("");
  const [timeWindow, setTimeWindow] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  const systemsQuery = useQuery({
    queryKey: ["systems"],
    queryFn: getSystems,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (!hostName && systemsQuery.data?.systems?.length) {
      setHostName(systemsQuery.data.systems[0].hostname);
    }
  }, [hostName, systemsQuery.data]);

  const historyMutation = useMutation({
    mutationFn: () => collectReliabilityHistory(hostName),
    onSuccess: (data) => {
      setLatestResult(data);
      setActionError(null);
    },
    onError: (err) => setActionError(err),
  });

  useEffect(() => {
    if (hostName) {
      historyMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hostName]);

  const historyRecords = useMemo(() => {
    const raw = latestResult as { history?: { records?: ReliabilityRecord[] } } | null;
    return Array.isArray(raw?.history?.records) ? raw.history.records : [];
  }, [latestResult]);

  const sourceOptions = useMemo(() => {
    const unique = new Set<string>();
    historyRecords.forEach((record) => {
      if (record.source) unique.add(record.source);
    });
    return Array.from(unique).sort((a, b) => a.localeCompare(b));
  }, [historyRecords]);

  const refreshHistory = () => {
    if (!hostName) return;
    historyMutation.mutate();
  };

  const resetHistoryView = () => {
    setSearchText("");
    setTimeWindow("all");
    setSourceFilter("all");
    setLatestResult(null);
    setActionError(null);
    setHostName(systemsQuery.data?.systems?.[0]?.hostname ?? "");
  };

  const filteredRecords = useMemo(() => {
    const now = new Date();
    const normalizedSearch = searchText.trim().toLowerCase();
    const windowHours = getWindowHours(timeWindow);

    return historyRecords.filter((record) => {
      if (sourceFilter !== "all" && (record.source || "") !== sourceFilter) {
        return false;
      }

      if (windowHours !== null && record.timestamp) {
        const date = new Date(record.timestamp);
        if (!Number.isNaN(date.getTime())) {
          const diffHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60);
          if (diffHours > windowHours) return false;
        }
      }

      if (!normalizedSearch) return true;
      const blob = `${record.timestamp || ""} ${record.source || ""} ${record.product || ""} ${record.event_id || ""} ${record.message || ""}`.toLowerCase();
      return blob.includes(normalizedSearch);
    });
  }, [historyRecords, searchText, timeWindow, sourceFilter]);

  return (
    <ModulePage
      title="History"
      description="Reliability records history with host selection, filtering, and sortable tabular review."
      isLoading={systemsQuery.isLoading}
      error={systemsQuery.isError ? "Failed to load hosts for history view." : null}
      actions={
        <div className="module-page-actions-group">
          <button type="button" onClick={refreshHistory} disabled={!hostName || historyMutation.isPending || systemsQuery.isLoading}>
            Refresh history
          </button>
          <button type="button" onClick={resetHistoryView}>
            Reset history view
          </button>
        </div>
      }
    >
      <ActionPanel title="History Filters">
        <div className="module-grid">
          <select value={hostName} onChange={(e) => setHostName(e.target.value)}>
            <option value="">Select host</option>
            {(systemsQuery.data?.systems || []).map((system) => (
              <option key={system.id} value={system.hostname}>{system.hostname}</option>
            ))}
          </select>
          <input
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Search timestamp/source/product/event/message"
          />
          <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}>
            <option value="all">All sources</option>
            {sourceOptions.map((source) => (
              <option key={source} value={source}>{source}</option>
            ))}
          </select>
          <select value={timeWindow} onChange={(e) => setTimeWindow(e.target.value)}>
            <option value="all">All time</option>
            <option value="1h">Last hour</option>
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
          </select>
        </div>
        <div className="row-between" style={{ marginTop: 12, justifyContent: "flex-start" }}>
          <button onClick={() => historyMutation.mutate()} disabled={!hostName || historyMutation.isPending}>
            {historyMutation.isPending ? "Refreshing..." : "Refresh History"}
          </button>
          <small>Rows: {filteredRecords.length} / {historyRecords.length}</small>
        </div>
        <MutationFeedback error={actionError || historyMutation.error} />
      </ActionPanel>

      <ActionPanel title="Historical Reliability Records" style={{ marginTop: 12 }}>
        {historyMutation.isPending ? (
          <div className="module-status loading">Loading reliability history...</div>
        ) : filteredRecords.length === 0 ? (
          <div className="module-status loading">No records found for current filters/host.</div>
        ) : (
          <table className="table-lite">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Source</th>
                <th>Product</th>
                <th>Event ID</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {filteredRecords.map((record, idx) => (
                <tr key={`${record.timestamp || "none"}-${record.event_id || "none"}-${idx}`}>
                  <td>{normalizeTimestamp(record.timestamp)}</td>
                  <td>{record.source || "-"}</td>
                  <td>{record.product || "-"}</td>
                  <td>{record.event_id || "-"}</td>
                  <td>{record.message || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </ActionPanel>
    </ModulePage>
  );
}
