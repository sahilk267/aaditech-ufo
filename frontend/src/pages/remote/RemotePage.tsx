import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { JsonViewer } from "../../components/common/JsonViewer";
import { MutationFeedback } from "../../components/common/MutationFeedback";
import { executeRemoteCommand } from "../../lib/api";

export function RemotePage() {
  const [host, setHost] = useState("127.0.0.1");
  const [command, setCommand] = useState("hostname");
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  const remoteExecMutation = useMutation({
    mutationFn: () => executeRemoteCommand(host, command),
    onSuccess: (data) => { setLatestResult(data); setActionError(null); },
    onError: (err) => setActionError(err),
  });

  return (
    <ModulePage
      title="Remote Execution"
      description="Policy-controlled remote command execution using /api/remote/exec."
    >
      <ActionPanel title="Execute Command">
        <div className="module-grid">
          <input value={host} onChange={(e) => setHost(e.target.value)} placeholder="Target host" />
          <input value={command} onChange={(e) => setCommand(e.target.value)} placeholder="Command" />
        </div>
        <button style={{ marginTop: 12 }} onClick={() => remoteExecMutation.mutate()} disabled={remoteExecMutation.isPending}>
          Execute
        </button>
        <MutationFeedback error={actionError} />
        {latestResult ? (
          <JsonViewer data={latestResult} title="Result" />
        ) : (
          <div className="module-status loading">Execute a command to view stdout, stderr, and policy result details here.</div>
        )}
      </ActionPanel>
    </ModulePage>
  );
}
