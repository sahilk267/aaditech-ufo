import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import {
  listAgentCommands,
  queueAgentCommand,
  type AgentCommandRecord,
  type QueueAgentCommandPayload,
} from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import { extractErrorMessage } from "../../lib/errorUtils";

const DEFAULT_TYPE = "ping";

const STATUS_FILTERS: Array<{ value: string; label: string }> = [
  { value: "", label: "All statuses" },
  { value: "pending", label: "Pending" },
  { value: "dispatched", label: "Dispatched" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "expired", label: "Expired" },
];

function formatTs(value: string | null): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case "completed":
      return "success-text";
    case "failed":
    case "expired":
      return "error-text";
    case "dispatched":
      return "warning-text";
    default:
      return "";
  }
}

export function AgentCommandsPage() {
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [serialFilter, setSerialFilter] = useState<string>("");

  const [commandType, setCommandType] = useState<string>(DEFAULT_TYPE);
  const [targetSerial, setTargetSerial] = useState<string>("");
  const [expiresIn, setExpiresIn] = useState<number>(3600);
  const [payloadText, setPayloadText] = useState<string>("{}");
  const [feedback, setFeedback] = useState<string>("");
  const [feedbackKind, setFeedbackKind] = useState<"success" | "error" | "">("");

  const filters = useMemo(
    () => ({
      status: statusFilter || undefined,
      command_type: typeFilter || undefined,
      target_serial_number: serialFilter || undefined,
    }),
    [statusFilter, typeFilter, serialFilter],
  );

  const commandsQuery = useQuery({
    queryKey: queryKeys.agentCommands(filters),
    queryFn: () => listAgentCommands({ ...filters, limit: 100 }),
    refetchInterval: 5000,
    staleTime: 2000,
  });

  const allowedTypes = commandsQuery.data?.allowed_command_types ?? [DEFAULT_TYPE];

  const refreshCommands = () => {
    void queryClient.invalidateQueries({ queryKey: ["agents", "commands"] });
  };

  const queueMutation = useMutation({
    mutationFn: () => {
      let parsedPayload: Record<string, unknown> = {};
      const trimmed = payloadText.trim();
      if (trimmed.length > 0) {
        const parsed = JSON.parse(trimmed);
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          parsedPayload = parsed as Record<string, unknown>;
        } else {
          throw new Error("Payload must be a JSON object.");
        }
      }
      const body: QueueAgentCommandPayload = {
        command_type: commandType,
        payload: parsedPayload,
        expires_in_seconds: Math.max(60, Math.min(expiresIn || 3600, 86400)),
      };
      if (targetSerial.trim()) body.target_serial_number = targetSerial.trim();
      return queueAgentCommand(body);
    },
    onSuccess: (data) => {
      setFeedback(`Queued command #${data.command.id} (${data.command.command_type}).`);
      setFeedbackKind("success");
      setPayloadText("{}");
      refreshCommands();
      window.setTimeout(() => {
        setFeedback("");
        setFeedbackKind("");
      }, 5000);
    },
    onError: (err) => {
      setFeedback(`Failed to queue command: ${extractErrorMessage(err)}`);
      setFeedbackKind("error");
    },
  });

  const rows: AgentCommandRecord[] = commandsQuery.data?.commands ?? [];

  return (
    <ModulePage
      title="Remote Commands"
      description="Queue whitelisted commands for agents and review their dispatch + result history."
      isLoading={commandsQuery.isLoading}
      error={commandsQuery.isError ? "Could not load command queue." : ""}
      actions={
        <div className="module-page-actions-group">
          <button type="button" onClick={refreshCommands} disabled={commandsQuery.isFetching}>
            {commandsQuery.isFetching ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      }
    >
      <div className="panel">
        <h2>Queue New Command</h2>
        <div className="module-grid" style={{ gap: 12 }}>
          <div className="form-field">
            <label className="form-label">Command type</label>
            <select
              className="form-input"
              value={commandType}
              onChange={(e) => setCommandType(e.target.value)}
            >
              {allowedTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>
          <div className="form-field">
            <label className="form-label">Target serial (optional)</label>
            <input
              className="form-input"
              value={targetSerial}
              onChange={(e) => setTargetSerial(e.target.value)}
              placeholder="Leave blank to broadcast to any agent"
            />
          </div>
          <div className="form-field">
            <label className="form-label">Expires in (seconds)</label>
            <input
              className="form-input"
              type="number"
              min={60}
              max={86400}
              value={expiresIn}
              onChange={(e) => setExpiresIn(Number(e.target.value) || 3600)}
            />
          </div>
        </div>
        <div className="form-field" style={{ marginTop: 12 }}>
          <label className="form-label">Payload (JSON object)</label>
          <textarea
            className="form-input"
            rows={4}
            value={payloadText}
            onChange={(e) => setPayloadText(e.target.value)}
            placeholder='{"service_name": "MyService"}'
            style={{ fontFamily: "monospace" }}
          />
        </div>
        <button
          className="button button--primary"
          type="button"
          onClick={() => queueMutation.mutate()}
          disabled={queueMutation.status === "pending" || !commandType}
          style={{ marginTop: 12 }}
        >
          {queueMutation.status === "pending" ? "Queueing…" : "Queue command"}
        </button>
        {feedback ? (
          <div
            className={`module-status ${feedbackKind === "success" ? "success-text" : "error-text"}`}
            style={{ marginTop: 12 }}
          >
            {feedback}
          </div>
        ) : null}
      </div>

      <div className="panel" style={{ marginTop: 24 }}>
        <h2>Command History</h2>
        <div className="module-grid" style={{ gap: 12, marginBottom: 12 }}>
          <div className="form-field">
            <label className="form-label">Status</label>
            <select
              className="form-input"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              {STATUS_FILTERS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <div className="form-field">
            <label className="form-label">Command type</label>
            <select
              className="form-input"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
            >
              <option value="">All types</option>
              {allowedTypes.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div className="form-field">
            <label className="form-label">Target serial</label>
            <input
              className="form-input"
              value={serialFilter}
              onChange={(e) => setSerialFilter(e.target.value)}
              placeholder="Filter by exact serial"
            />
          </div>
        </div>

        {rows.length === 0 ? (
          <div className="module-status loading">No commands match these filters yet.</div>
        ) : (
          <table className="table-lite">
            <thead>
              <tr>
                <th>ID</th>
                <th>Type</th>
                <th>Target</th>
                <th>Status</th>
                <th>Queued</th>
                <th>Dispatched</th>
                <th>Completed</th>
                <th>Result / Error</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((cmd) => (
                <tr key={cmd.id}>
                  <td>{cmd.id}</td>
                  <td>{cmd.command_type}</td>
                  <td>{cmd.target_serial_number || <em>broadcast</em>}</td>
                  <td className={statusBadgeClass(cmd.status)}>{cmd.status}</td>
                  <td>{formatTs(cmd.created_at)}</td>
                  <td>{formatTs(cmd.dispatched_at)}</td>
                  <td>{formatTs(cmd.completed_at)}</td>
                  <td>
                    {cmd.error_message ? (
                      <span className="error-text">{cmd.error_message}</span>
                    ) : cmd.result ? (
                      <pre style={{ margin: 0, maxWidth: 320, overflowX: "auto" }}>
                        {JSON.stringify(cmd.result, null, 2)}
                      </pre>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </ModulePage>
  );
}
