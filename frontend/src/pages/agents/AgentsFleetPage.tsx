import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { StatCard } from "../../components/common/StatCard";
import { getAgentFleet, updateAgentTrust } from "../../lib/api";

type EnrollmentState = "pending" | "enrolled" | "trusted" | "revoked" | string;

interface Agent {
  id: number;
  hostname: string;
  serial_number: string;
  platform: string;
  agent_version: string | null;
  enrollment_state: EnrollmentState;
  last_seen_at: string | null;
  last_ip: string | null;
  created_at: string;
}

function stateColor(state: EnrollmentState): string {
  switch (state) {
    case "trusted": return "#22c55e";
    case "enrolled": return "#3b82f6";
    case "pending": return "#f59e0b";
    case "revoked": return "#ef4444";
    default: return "#6b7280";
  }
}

function stateBadge(state: EnrollmentState) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: 12,
        fontWeight: 600,
        background: stateColor(state) + "22",
        color: stateColor(state),
        border: `1px solid ${stateColor(state)}44`,
        textTransform: "uppercase",
        letterSpacing: "0.05em",
      }}
    >
      {state}
    </span>
  );
}

function timeSince(iso: string | null): string {
  if (!iso) return "Never";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 2) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function isActive(lastSeen: string | null): boolean {
  if (!lastSeen) return false;
  return Date.now() - new Date(lastSeen).getTime() < 5 * 60 * 1000;
}

const STATE_FILTERS: { label: string; value: string }[] = [
  { label: "All", value: "" },
  { label: "Trusted", value: "trusted" },
  { label: "Enrolled", value: "enrolled" },
  { label: "Pending", value: "pending" },
  { label: "Revoked", value: "revoked" },
];

export function AgentsFleetPage() {
  const qc = useQueryClient();
  const [stateFilter, setStateFilter] = useState("");
  const [search, setSearch] = useState("");
  const [actionResult, setActionResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const fleetQuery = useQuery({
    queryKey: ["agents-fleet"],
    queryFn: getAgentFleet,
    refetchInterval: 30000,
  });

  const trustMutation = useMutation({
    mutationFn: ({ id, state }: { id: number; state: string }) =>
      updateAgentTrust(id, state),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["agents-fleet"] });
      setActionResult({ ok: true, msg: `Agent ${vars.state === "trusted" ? "trusted" : "revoked"} successfully.` });
      setTimeout(() => setActionResult(null), 4000);
    },
    onError: (err: Error) => {
      setActionResult({ ok: false, msg: err.message || "Action failed" });
    },
  });

  const agents: Agent[] = fleetQuery.data?.agents ?? [];

  const filtered = agents.filter((a) => {
    const matchState = !stateFilter || a.enrollment_state === stateFilter;
    const q = search.toLowerCase();
    const matchSearch =
      !q ||
      a.hostname.toLowerCase().includes(q) ||
      a.serial_number.toLowerCase().includes(q) ||
      (a.agent_version ?? "").toLowerCase().includes(q) ||
      a.platform.toLowerCase().includes(q);
    return matchState && matchSearch;
  });

  const total = agents.length;
  const trusted = agents.filter((a) => a.enrollment_state === "trusted").length;
  const pending = agents.filter((a) => a.enrollment_state === "pending").length;
  const activeNow = agents.filter((a) => isActive(a.last_seen_at)).length;

  return (
    <ModulePage
      title="Fleet Management"
      subtitle={`${total} agent${total !== 1 ? "s" : ""} enrolled • auto-refreshes every 30s`}
      status={fleetQuery.isError ? "error" : fleetQuery.isLoading ? "loading" : "ok"}
    >
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16, marginBottom: 24 }}>
        <StatCard label="Total Agents" value={total} status="ok" />
        <StatCard label="Trusted" value={trusted} status={trusted > 0 ? "ok" : "neutral"} />
        <StatCard label="Pending Approval" value={pending} status={pending > 0 ? "warn" : "ok"} />
        <StatCard label="Active Now (5m)" value={activeNow} status={activeNow > 0 ? "ok" : "neutral"} />
      </div>

      {actionResult && (
        <div
          className={`feedback-banner feedback-banner--${actionResult.ok ? "success" : "error"}`}
          style={{ marginBottom: 16 }}
        >
          {actionResult.msg}
        </div>
      )}

      <ActionPanel title="Agent Fleet">
        <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
          <div className="page-tabs" style={{ marginBottom: 0 }}>
            {STATE_FILTERS.map((f) => (
              <button
                key={f.value}
                className={`page-tab${stateFilter === f.value ? " page-tab--active" : ""}`}
                onClick={() => setStateFilter(f.value)}
              >
                {f.label}
              </button>
            ))}
          </div>
          <input
            type="text"
            placeholder="Search hostname, serial, version…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              padding: "6px 12px",
              borderRadius: 6,
              border: "1px solid var(--border)",
              background: "var(--surface)",
              color: "var(--text)",
              fontSize: 13,
              minWidth: 240,
            }}
          />
          <button
            className="button button--sm"
            onClick={() => fleetQuery.refetch()}
            disabled={fleetQuery.isFetching}
          >
            {fleetQuery.isFetching ? "Refreshing…" : "↺ Refresh"}
          </button>
        </div>

        {fleetQuery.isLoading && (
          <p className="module-status loading">Loading fleet…</p>
        )}

        {fleetQuery.isError && (
          <p className="module-status error">
            Failed to load fleet: {(fleetQuery.error as Error).message}
          </p>
        )}

        {!fleetQuery.isLoading && filtered.length === 0 && (
          <div className="empty-state">
            <p>
              {total === 0
                ? "No agents enrolled yet. Use Releases → Setup Instructions to onboard a host."
                : "No agents match your filter."}
            </p>
          </div>
        )}

        {filtered.length > 0 && (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)", textAlign: "left" }}>
                  {["Status", "Hostname", "Serial", "Platform", "Version", "Last Seen", "IP", "Actions"].map((h) => (
                    <th
                      key={h}
                      style={{ padding: "8px 12px", color: "var(--text-secondary)", fontWeight: 600, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em" }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((agent) => (
                  <tr
                    key={agent.id}
                    style={{ borderBottom: "1px solid var(--border-subtle)", verticalAlign: "middle" }}
                  >
                    <td style={{ padding: "10px 12px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span
                          style={{
                            width: 8,
                            height: 8,
                            borderRadius: "50%",
                            background: isActive(agent.last_seen_at) ? "#22c55e" : "#6b7280",
                            flexShrink: 0,
                          }}
                          title={isActive(agent.last_seen_at) ? "Active" : "Inactive"}
                        />
                        {stateBadge(agent.enrollment_state)}
                      </div>
                    </td>
                    <td style={{ padding: "10px 12px", fontWeight: 500, color: "var(--text)" }}>
                      {agent.hostname}
                    </td>
                    <td style={{ padding: "10px 12px" }}>
                      <span className="version-chip">{agent.serial_number}</span>
                    </td>
                    <td style={{ padding: "10px 12px", color: "var(--text-secondary)" }}>
                      {agent.platform}
                    </td>
                    <td style={{ padding: "10px 12px" }}>
                      {agent.agent_version ? (
                        <span className="version-chip">{agent.agent_version}</span>
                      ) : (
                        <span style={{ color: "var(--text-secondary)", fontSize: 12 }}>—</span>
                      )}
                    </td>
                    <td style={{ padding: "10px 12px", color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                      {isActive(agent.last_seen_at) && (
                        <span style={{ color: "#22c55e", marginRight: 4 }}>●</span>
                      )}
                      {timeSince(agent.last_seen_at)}
                    </td>
                    <td style={{ padding: "10px 12px", color: "var(--text-secondary)", fontSize: 12 }}>
                      {agent.last_ip || "—"}
                    </td>
                    <td style={{ padding: "10px 12px" }}>
                      <div style={{ display: "flex", gap: 6 }}>
                        {agent.enrollment_state !== "trusted" && (
                          <button
                            className="button button--sm button--green"
                            disabled={trustMutation.isPending}
                            onClick={() => trustMutation.mutate({ id: agent.id, state: "trusted" })}
                          >
                            Trust
                          </button>
                        )}
                        {agent.enrollment_state !== "revoked" && (
                          <button
                            className="button button--sm button--amber"
                            disabled={trustMutation.isPending}
                            onClick={() => {
                              if (confirm(`Revoke agent "${agent.hostname}"? It will stop being able to submit data.`)) {
                                trustMutation.mutate({ id: agent.id, state: "revoked" });
                              }
                            }}
                          >
                            Revoke
                          </button>
                        )}
                        {agent.enrollment_state === "revoked" && (
                          <button
                            className="button button--sm"
                            disabled={trustMutation.isPending}
                            onClick={() => trustMutation.mutate({ id: agent.id, state: "enrolled" })}
                          >
                            Re-enroll
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </ActionPanel>

      <div style={{ marginTop: 16, padding: "12px 16px", borderRadius: 8, background: "var(--surface-elevated)", border: "1px solid var(--border)" }}>
        <p className="section-label">About enrollment states</p>
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginTop: 8 }}>
          {[
            { state: "pending", desc: "Agent registered but not yet approved" },
            { state: "enrolled", desc: "Enrolled and submitting data" },
            { state: "trusted", desc: "Explicitly trusted — full command access" },
            { state: "revoked", desc: "Access revoked — agent cannot submit data" },
          ].map(({ state, desc }) => (
            <div key={state} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
              {stateBadge(state)}
              <span style={{ color: "var(--text-secondary)" }}>{desc}</span>
            </div>
          ))}
        </div>
      </div>
    </ModulePage>
  );
}
