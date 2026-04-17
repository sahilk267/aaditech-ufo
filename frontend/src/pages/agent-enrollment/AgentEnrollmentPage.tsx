import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { enrollAgent, getAgentEnrollmentTokens } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import { extractErrorMessage } from "../../lib/errorUtils";

export function AgentEnrollmentPage() {
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState("");
  const [hostName, setHostName] = useState("");
  const [command, setCommand] = useState("");

  const tokensQuery = useQuery({
    queryKey: queryKeys.agentEnrollmentTokens,
    queryFn: getAgentEnrollmentTokens,
    staleTime: 60_000,
  });

  const refreshEnrollmentTokens = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.agentEnrollmentTokens });
  };

  const resetEnrollmentView = () => {
    setFeedback("");
    setHostName("");
    setCommand("");
  };

  const tokenMutation = useMutation({
    mutationFn: () => getAgentEnrollmentTokens(),
    onSuccess: () => {
      setFeedback("Enrollment token generated.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.agentEnrollmentTokens });
      setTimeout(() => setFeedback(""), 4000);
    },
    onError: (err) => setFeedback(`Error generating token: ${extractErrorMessage(err)}`),
  });

  const enrollMutation = useMutation({
    mutationFn: () => enrollAgent({ host_name: hostName, command }),
    onSuccess: () => {
      setFeedback("Agent enrollment request sent.");
      setHostName("");
      setCommand("");
      setTimeout(() => setFeedback(""), 4000);
    },
    onError: (err) => setFeedback(`Error enrolling agent: ${extractErrorMessage(err)}`),
  });

  return (
    <ModulePage
      title="Agent Enrollment"
      description="Generate enrollment tokens and submit agent onboarding requests."
      isLoading={tokensQuery.isLoading}
      error={tokensQuery.isError ? "Could not load enrollment tokens." : ""}
      actions={
        <div className="module-page-actions-group">
          <button type="button" onClick={refreshEnrollmentTokens} disabled={tokensQuery.isFetching}>
            Refresh tokens
          </button>
          <button type="button" onClick={resetEnrollmentView}>
            Reset form
          </button>
        </div>
      }
    >
      <div className="panel">
        <h2>Enrollment Token</h2>
        <button
          className="button button--primary"
          type="button"
          onClick={() => tokenMutation.mutate()}
          disabled={tokenMutation.status === "pending"}
        >
          {tokenMutation.status === "pending" ? "Generating..." : "Generate token"}
        </button>
        {tokensQuery.data?.token ? (
          <pre style={{ marginTop: 16 }}>{JSON.stringify(tokensQuery.data.token, null, 2)}</pre>
        ) : (
          <div style={{ marginTop: 16 }}>No enrollment token available.</div>
        )}
      </div>

      <div className="panel" style={{ marginTop: 24 }}>
        <h2>Enroll Agent</h2>
        <div className="form-field">
          <label className="form-label">Host name</label>
          <input value={hostName} onChange={(e) => setHostName(e.target.value)} className="form-input" />
        </div>
        <div className="form-field">
          <label className="form-label">Command</label>
          <input value={command} onChange={(e) => setCommand(e.target.value)} className="form-input" />
        </div>
        <button
          className="button button--primary"
          type="button"
          onClick={() => enrollMutation.mutate()}
          disabled={enrollMutation.status === "pending"}
        >
          {enrollMutation.status === "pending" ? "Sending..." : "Send enrollment request"}
        </button>
        {feedback ? <div className="module-status success-text" style={{ marginTop: 12 }}>{feedback}</div> : null}
      </div>
    </ModulePage>
  );
}
