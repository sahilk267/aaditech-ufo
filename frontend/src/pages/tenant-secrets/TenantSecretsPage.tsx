import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { createTenantSecret, getTenantSecrets, revokeTenantSecret, rotateTenantSecret } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import { extractErrorMessage } from "../../lib/errorUtils";

export function TenantSecretsPage() {
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState("");
  const [secretName, setSecretName] = useState("");
  const [secretValue, setSecretValue] = useState("");

  const secretsQuery = useQuery({
    queryKey: queryKeys.tenantSecrets,
    queryFn: getTenantSecrets,
    staleTime: 60_000,
  });

  const createMutation = useMutation({
    mutationFn: () => createTenantSecret({ name: secretName, secret_value: secretValue, secret_type: "tenant_secret" }),
    onSuccess: () => {
      setFeedback("Tenant secret created.");
      setSecretName("");
      setSecretValue("");
      void queryClient.invalidateQueries({ queryKey: queryKeys.tenantSecrets });
      setTimeout(() => setFeedback(""), 4000);
    },
    onError: (err) => setFeedback(`Error creating secret: ${extractErrorMessage(err)}`),
  });

  const rotateMutation = useMutation({
    mutationFn: (secretId: number) => rotateTenantSecret(secretId, { secret_value: "rotated-value" }),
    onSuccess: () => {
      setFeedback("Secret rotated.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.tenantSecrets });
      setTimeout(() => setFeedback(""), 4000);
    },
    onError: (err) => setFeedback(`Error rotating secret: ${extractErrorMessage(err)}`),
  });

  const revokeMutation = useMutation({
    mutationFn: (secretId: number) => revokeTenantSecret(secretId),
    onSuccess: () => {
      setFeedback("Secret revoked.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.tenantSecrets });
      setTimeout(() => setFeedback(""), 4000);
    },
    onError: (err) => setFeedback(`Error revoking secret: ${extractErrorMessage(err)}`),
  });

  const refreshTenantSecrets = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.tenantSecrets });
  };

  const resetTenantSecretsView = () => {
    setFeedback("");
    setSecretName("");
    setSecretValue("");
  };

  const secrets = Array.isArray(secretsQuery.data?.secrets) ? secretsQuery.data.secrets : [];

  return (
    <ModulePage
      title="Tenant Secrets"
      description="Manage tenant secret values, rotation, and secure storage."
      isLoading={secretsQuery.isLoading}
      error={secretsQuery.isError ? "Could not load tenant secrets." : ""}
      actions={
        <div className="module-page-actions-group">
          <button type="button" onClick={refreshTenantSecrets} disabled={secretsQuery.isFetching}>
            Refresh secrets
          </button>
          <button type="button" onClick={resetTenantSecretsView}>
            Reset secret form
          </button>
        </div>
      }
    >
      <div className="panel">
        <h2>Create Secret</h2>
        <div className="form-field">
          <label className="form-label">Secret Name</label>
          <input value={secretName} onChange={(e) => setSecretName(e.target.value)} className="form-input" />
        </div>
        <div className="form-field">
          <label className="form-label">Secret Value</label>
          <input value={secretValue} onChange={(e) => setSecretValue(e.target.value)} className="form-input" />
        </div>
        <button className="button button--primary" type="button" onClick={() => createMutation.mutate()} disabled={createMutation.status === "pending"}>
          {createMutation.status === "pending" ? "Creating..." : "Create secret"}
        </button>
      </div>

      <div className="panel" style={{ marginTop: 24 }}>
        <h2>Tenant Secrets</h2>
        {secrets.length ? (
          <div className="grid-grid--2">
            {secrets.map((secret: any) => (
              <div key={secret.id} className="panel panel--sub">
                <h3>{secret.name}</h3>
                <p>Status: {secret.status ?? "unknown"}</p>
                <button
                  className="button button--secondary"
                  type="button"
                  onClick={() => rotateMutation.mutate(secret.id)}
                  disabled={rotateMutation.status === "pending"}
                >
                  {rotateMutation.status === "pending" ? "Rotating..." : "Rotate"}
                </button>
                <button
                  className="button button--danger"
                  type="button"
                  onClick={() => revokeMutation.mutate(secret.id)}
                  disabled={revokeMutation.status === "pending"}
                  style={{ marginLeft: 8 }}
                >
                  {revokeMutation.status === "pending" ? "Revoking..." : "Revoke"}
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div>No secrets found.</div>
        )}
        {feedback ? <div className="module-status success-text">{feedback}</div> : null}
      </div>
    </ModulePage>
  );
}
