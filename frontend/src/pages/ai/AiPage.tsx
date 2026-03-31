import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { JsonViewer } from "../../components/common/JsonViewer";
import { MutationFeedback } from "../../components/common/MutationFeedback";
import {
  analyzeRootCause,
  generateAiRecommendations,
  runOllamaInference,
} from "../../lib/api";

export function AiPage() {
  const [prompt, setPrompt] = useState("Summarize possible root causes for high CPU spikes");
  const [symptomSummary, setSymptomSummary] = useState("CPU usage spikes above 95% every 5 minutes");
  const [probableCause, setProbableCause] = useState("Scheduled task overloading worker service");
  const [evidenceText, setEvidenceText] = useState("task scheduler logs show repeating trigger\nservice restart loop");
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  const onOk = (data: unknown) => { setLatestResult(data); setActionError(null); };
  const onErr = (err: unknown) => setActionError(err);

  const inferenceMutation = useMutation({ mutationFn: () => runOllamaInference(prompt), onSuccess: onOk, onError: onErr });
  const rootCauseMutation = useMutation({ mutationFn: () => analyzeRootCause(symptomSummary, evidenceText.split("\n").filter(Boolean)), onSuccess: onOk, onError: onErr });
  const recommendationsMutation = useMutation({
    mutationFn: () => generateAiRecommendations(symptomSummary, probableCause, evidenceText.split("\n").filter(Boolean)),
    onSuccess: onOk,
    onError: onErr,
  });

  const isPending = inferenceMutation.isPending || rootCauseMutation.isPending || recommendationsMutation.isPending;

  return (
    <ModulePage
      title="AI Operations"
      description="Inference, root-cause analysis, and recommendations using /api/ai/* endpoints."
    >
      <ActionPanel title="Inputs">
        <div className="module-grid">
          <input value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Inference prompt" />
          <input value={symptomSummary} onChange={(e) => setSymptomSummary(e.target.value)} placeholder="Symptom summary" />
          <input value={probableCause} onChange={(e) => setProbableCause(e.target.value)} placeholder="Probable cause" />
          <input value={evidenceText} onChange={(e) => setEvidenceText(e.target.value)} placeholder="Evidence (one per line)" />
        </div>
        <div className="row-between" style={{ marginTop: 12 }}>
          <button onClick={() => inferenceMutation.mutate()} disabled={isPending}>Run Inference</button>
          <button onClick={() => rootCauseMutation.mutate()} disabled={isPending}>Analyze Root Cause</button>
          <button onClick={() => recommendationsMutation.mutate()} disabled={isPending}>Generate Recommendations</button>
        </div>
        <MutationFeedback error={actionError} />
        {latestResult ? (
          <JsonViewer data={latestResult} title="Last response" />
        ) : (
          <div className="module-status loading">Run an AI operation to inspect the latest inference or recommendation payload.</div>
        )}
      </ActionPanel>
    </ModulePage>
  );
}
