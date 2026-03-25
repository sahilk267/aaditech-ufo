import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { JsonViewer } from "../../components/common/JsonViewer";
import { MutationFeedback } from "../../components/common/MutationFeedback";
import { monitorUpdates, scoreUpdateConfidence } from "../../lib/api";

export function UpdatesPage() {
  const [hostName, setHostName] = useState("localhost");
  const [reliabilityScore, setReliabilityScore] = useState(0.8);
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [lastUpdatesPayload, setLastUpdatesPayload] = useState<unknown[]>([]);

  const onErr = (err: unknown) => setActionError(err);

  const monitorMutation = useMutation({
    mutationFn: () => monitorUpdates(hostName),
    onSuccess: (data) => {
      setLatestResult(data);
      setActionError(null);
      const raw = data as { updates?: { updates?: unknown[]; entries?: unknown[] } };
      setLastUpdatesPayload(raw?.updates?.updates ?? raw?.updates?.entries ?? []);
    },
    onError: onErr,
  });

  const confidenceMutation = useMutation({
    mutationFn: () => scoreUpdateConfidence(hostName, (lastUpdatesPayload as Record<string, unknown>[]), reliabilityScore),
    onSuccess: (data) => { setLatestResult(data); setActionError(null); },
    onError: onErr,
  });

  const updatesCount = useMemo(() => lastUpdatesPayload.length, [lastUpdatesPayload]);
  const isPending = monitorMutation.isPending || confidenceMutation.isPending;

  return (
    <ModulePage
      title="Updates"
      description="Update monitoring plus AI confidence scoring with /api/updates/monitor and /api/ai/confidence/score."
    >
      <ActionPanel title="Windows Update Controls">
        <div className="module-grid">
          <input value={hostName} onChange={(e) => setHostName(e.target.value)} placeholder="Host name" />
          <input
            type="number" min={0} max={1} step="0.1"
            value={reliabilityScore}
            onChange={(e) => setReliabilityScore(Number(e.target.value) || 0)}
            placeholder="Reliability score (0–1)"
          />
        </div>
        <div className="row-between" style={{ marginTop: 12 }}>
          <button onClick={() => monitorMutation.mutate()} disabled={isPending}>Monitor Updates</button>
          <button onClick={() => confidenceMutation.mutate()} disabled={isPending || !updatesCount}>
            Score Confidence {updatesCount ? `(${updatesCount} updates)` : ""}
          </button>
        </div>
        <MutationFeedback error={actionError} />
        <JsonViewer data={latestResult} title="Last response" />
      </ActionPanel>
    </ModulePage>
  );
}
