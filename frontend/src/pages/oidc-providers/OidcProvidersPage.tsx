import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { createOidcProvider, discoverOidcProvider, getOidcProviders } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import { extractErrorMessage } from "../../lib/errorUtils";

export function OidcProvidersPage() {
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState("");
  const [name, setName] = useState("");
  const [issuer, setIssuer] = useState("");
  const [clientId, setClientId] = useState("");
  const [authorizationEndpoint, setAuthorizationEndpoint] = useState("");
  const [isDefault, setIsDefault] = useState(false);

  const providersQuery = useQuery({
    queryKey: queryKeys.oidcProviders,
    queryFn: getOidcProviders,
    staleTime: 60_000,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createOidcProvider({
        name,
        issuer,
        client_id: clientId,
        authorization_endpoint: authorizationEndpoint,
        is_default: isDefault,
      }),
    onSuccess: () => {
      setFeedback("OIDC provider created.");
      setName("");
      setIssuer("");
      setClientId("");
      setAuthorizationEndpoint("");
      setIsDefault(false);
      void queryClient.invalidateQueries({ queryKey: queryKeys.oidcProviders });
      setTimeout(() => setFeedback(""), 4000);
    },
    onError: (err) => setFeedback(`Error creating provider: ${extractErrorMessage(err)}`),
  });

  const discoverMutation = useMutation({
    mutationFn: (providerId: number) => discoverOidcProvider(providerId),
    onSuccess: () => {
      setFeedback("OIDC provider discovery refreshed.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.oidcProviders });
      setTimeout(() => setFeedback(""), 4000);
    },
    onError: (err) => setFeedback(`Error discovering provider: ${extractErrorMessage(err)}`),
  });

  const refreshOidcProviders = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.oidcProviders });
  };

  const resetOidcProviderForm = () => {
    setFeedback("");
    setName("");
    setIssuer("");
    setClientId("");
    setAuthorizationEndpoint("");
    setIsDefault(false);
  };

  const isLoading = providersQuery.isLoading || createMutation.status === "pending";

  return (
    <ModulePage
      title="OIDC Providers"
      description="Manage tenant OpenID Connect providers and review provider configuration."
      isLoading={isLoading}
      error={providersQuery.isError ? "Could not load OIDC providers." : ""}
      actions={
        <div className="module-page-actions-group">
          <button type="button" onClick={refreshOidcProviders} disabled={providersQuery.isFetching}>
            Refresh providers
          </button>
          <button type="button" onClick={resetOidcProviderForm}>
            Reset form
          </button>
        </div>
      }
    >
      <div className="panel">
        <h2>Create OIDC Provider</h2>
        <div className="form-field">
          <label className="form-label">Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} className="form-input" />
        </div>
        <div className="form-field">
          <label className="form-label">Issuer</label>
          <input value={issuer} onChange={(e) => setIssuer(e.target.value)} className="form-input" />
        </div>
        <div className="form-field">
          <label className="form-label">Client ID</label>
          <input value={clientId} onChange={(e) => setClientId(e.target.value)} className="form-input" />
        </div>
        <div className="form-field">
          <label className="form-label">Authorization endpoint</label>
          <input
            value={authorizationEndpoint}
            onChange={(e) => setAuthorizationEndpoint(e.target.value)}
            className="form-input"
          />
        </div>
        <div className="form-field form-field--checkbox">
          <label className="form-checkbox-label">
            <input
              type="checkbox"
              checked={isDefault}
              onChange={(e) => setIsDefault(e.target.checked)}
            />
            <span>Set as default provider</span>
          </label>
        </div>
        <button
          className="button button--primary"
          type="button"
          onClick={() => createMutation.mutate()}
          disabled={createMutation.status === "pending"}
        >
          {createMutation.status === "pending" ? "Creating..." : "Create provider"}
        </button>
        {feedback ? <div className="module-status success-text">{feedback}</div> : null}
      </div>

      <div className="panel" style={{ marginTop: 24 }}>
        <h2>Configured Providers</h2>
        {providersQuery.data?.providers?.length ? (
          <div className="grid-grid--2">
            {providersQuery.data.providers.map((provider) => (
              <div key={provider.id} className="panel panel--sub">
                <h3>{provider.name}</h3>
                <p>Issuer: {provider.issuer}</p>
                <p>Client ID: {provider.client_id}</p>
                <p>Enabled: {provider.is_enabled ? "Yes" : "No"}</p>
                <p>Default: {provider.is_default ? "Yes" : "No"}</p>
                <button
                  className="button button--secondary"
                  type="button"
                  onClick={() => discoverMutation.mutate(provider.id)}
                  disabled={discoverMutation.status === "pending"}
                >
                  {discoverMutation.status === "pending" ? "Refreshing..." : "Refresh metadata"}
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div>No OIDC providers configured.</div>
        )}
      </div>
    </ModulePage>
  );
}
