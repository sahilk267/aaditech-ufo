import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { JsonViewer } from "../../components/common/JsonViewer";
import { MutationFeedback } from "../../components/common/MutationFeedback";
import { executeRemoteCommand } from "../../lib/api";

type RemoteHistoryEntry = {
  id: string;
  host: string;
  command: string;
  timestamp: string;
  result: unknown;
  error?: string;
};

export function RemotePage() {
  const [host, setHost] = useState("127.0.0.1");
  const [command, setCommand] = useState("hostname");
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [history, setHistory] = useState<RemoteHistoryEntry[]>([]);

  const remoteExecMutation = useMutation({
    mutationFn: () => executeRemoteCommand(host, command),
    onSuccess: (data) => {
      const entry: RemoteHistoryEntry = {
        id: `${Date.now()}-${host}`,
        host,
        command,
        timestamp: new Date().toISOString(),
        result: data,
      };
      setLatestResult(data);
      setHistory((current) => [entry, ...current].slice(0, 10));
      setActionError(null);
    },
    onError: (err) => {
      const entry: RemoteHistoryEntry = {
        id: `${Date.now()}-${host}`,
        host,
        command,
        timestamp: new Date().toISOString(),
        result: null,
        error: String(err),
      };
      setHistory((current) => [entry, ...current].slice(0, 10));
      setActionError(err);
    },
  });

  const onExecute = () => {
    remoteExecMutation.mutate();
  };

  const replayEntry = (entry: RemoteHistoryEntry) => {
    setHost(entry.host);
    setCommand(entry.command);
    remoteExecMutation.mutate();
  };

  return (
    <ModulePage
      title="Remote Execution"
      description="Policy-controlled remote command execution using /api/remote/exec."
      actions={
        <button onClick={onExecute} disabled={remoteExecMutation.isPending || !host.trim() || !command.trim()}>
          Execute
        </button>
      }
    >
      <ActionPanel title="Execute Command">
        <div className="module-grid">
          <input value={host} onChange={(e) => setHost(e.target.value)} placeholder="Target host" />
          <input value={command} onChange={(e) => setCommand(e.target.value)} placeholder="Command" />
        </div>
        <MutationFeedback error={actionError} />
        {latestResult ? (
          <JsonViewer data={latestResult} title="Latest result" />
        ) : (
          <div className="module-status loading">Execute a command to view stdout, stderr, and policy result details here.</div>
        )}
      </ActionPanel>

      <ActionPanel title="Execution History">
        {history.length ? (
          <table className="table-lite">
            <thead>
              <tr>
                <th>When</th>
                <th>Host</th>
                <th>Command</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {history.map((entry) => (
                <tr key={entry.id}>
                  <td>{new Date(entry.timestamp).toLocaleString()}</td>
                  <td>{entry.host}</td>
                  <td>{entry.command}</td>
                  <td>{entry.error ? "Failed" : "Success"}</td>
                  <td>
                    <button type="button" onClick={() => replayEntry(entry)} disabled={remoteExecMutation.isPending}>
                      Re-run
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="module-status loading">No remote execution history available.</div>
        )}
      </ActionPanel>
    </ModulePage>
  );
}
