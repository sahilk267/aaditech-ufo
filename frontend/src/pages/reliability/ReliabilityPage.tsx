import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { JsonViewer } from "../../components/common/JsonViewer";
import { MutationFeedback } from "../../components/common/MutationFeedback";
import {
  analyzeReliabilityTrend,
  collectReliabilityHistory,
  predictReliability,
  scoreReliability,
} from "../../lib/api";

export function ReliabilityPage() {
  const [hostName, setHostName] = useState("localhost");
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  const onOk = (data: unknown) => { setLatestResult(data); setActionError(null); };
  const onErr = (err: unknown) => setActionError(err);

  const historyMutation = useMutation({ mutationFn: () => collectReliabilityHistory(hostName), onSuccess: onOk, onError: onErr });
  const scoreMutation = useMutation({ mutationFn: () => scoreReliability(hostName), onSuccess: onOk, onError: onErr });
  const trendMutation = useMutation({ mutationFn: () => analyzeReliabilityTrend(hostName), onSuccess: onOk, onError: onErr });
  const predictionMutation = useMutation({ mutationFn: () => predictReliability(hostName), onSuccess: onOk, onError: onErr });

  const isPending = historyMutation.isPending || scoreMutation.isPending || trendMutation.isPending || predictionMutation.isPending;

  return (
    <ModulePage
      title="Reliability"
      description="History, score, trend, and prediction diagnostics using /api/reliability/* endpoints."
    >
      <ActionPanel title="Diagnostics">
        <input value={hostName} onChange={(e) => setHostName(e.target.value)} placeholder="Host name" style={{ width: "100%" }} />
        <div className="row-between" style={{ marginTop: 12 }}>
          <button onClick={() => historyMutation.mutate()} disabled={isPending}>Collect History</button>
          <button onClick={() => scoreMutation.mutate()} disabled={isPending}>Score</button>
          <button onClick={() => trendMutation.mutate()} disabled={isPending}>Analyze Trend</button>
          <button onClick={() => predictionMutation.mutate()} disabled={isPending}>Predict</button>
        </div>
        <MutationFeedback error={actionError} />
        {latestResult ? (
          <JsonViewer data={latestResult} title="Last response" />
        ) : (
          <div className="module-status loading">Run a reliability diagnostic to see scoring, trend, or prediction output here.</div>
        )}
      </ActionPanel>
    </ModulePage>
  );
}
