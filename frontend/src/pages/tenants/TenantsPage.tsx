import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { StatCard } from "../../components/common/StatCard";
import {
  FormInput,
  FormSubmitButton,
  FormCheckbox,
} from "../../components/forms/FormComponents";
import { extractErrorMessage } from "../../lib/errorUtils";
import {
  activateTotp,
  createOidcProvider,
  createTenant,
  discoverOidcProvider,
  disableTotp,
  enrollTotp,
  getTenantCommercial,
  getTenantCommercialProviderBoundary,
  getOidcProviders,
  getTenantQuotas,
  getTenantSettings,
  getTenants,
  getTotpStatus,
  getTenantUsage,
  getTenantUsageReport,
  setTenantStatus,
  updateOidcProvider,
  updateTenantCommercial,
  updateTenantQuotas,
  updateTenantSettings,
} from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import { createTenantSchema, type CreateTenantInput } from "../../lib/schemas";

export function TenantsPage() {
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [enrollmentSecret, setEnrollmentSecret] = useState("");
  const [enrollmentUri, setEnrollmentUri] = useState("");
  const [oidcName, setOidcName] = useState("");
  const [oidcIssuer, setOidcIssuer] = useState("");
  const [oidcClientId, setOidcClientId] = useState("");
  const [oidcDiscoveryEndpoint, setOidcDiscoveryEndpoint] = useState("");
  const [oidcAuthEndpoint, setOidcAuthEndpoint] = useState("");
  const [oidcTokenEndpoint, setOidcTokenEndpoint] = useState("");
  const [oidcUserinfoEndpoint, setOidcUserinfoEndpoint] = useState("");
  const [oidcClientSecret, setOidcClientSecret] = useState("");
  const [oidcTestEmail, setOidcTestEmail] = useState("");
  const [oidcTestMode, setOidcTestMode] = useState(true);
  const [planKey, setPlanKey] = useState("");
  const [planDisplayName, setPlanDisplayName] = useState("");
  const [billingEmail, setBillingEmail] = useState("");
  const [providerName, setProviderName] = useState("");
  const [licenseStatus, setLicenseStatus] = useState("");
  const [seatLimit, setSeatLimit] = useState("");

  const form = useForm<CreateTenantInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(createTenantSchema) as any,
    defaultValues: {
      name: "",
      slug: "",
      isActive: true,
    },
  });

  const tenantsQuery = useQuery({
    queryKey: queryKeys.tenants,
    queryFn: getTenants,
    staleTime: 90_000,
  });

  const tenantSettingsQuery = useQuery({
    queryKey: queryKeys.tenantSettings,
    queryFn: getTenantSettings,
    staleTime: 60_000,
  });

  const oidcProvidersQuery = useQuery({
    queryKey: queryKeys.oidcProviders,
    queryFn: getOidcProviders,
    staleTime: 60_000,
  });

  const tenantQuotasQuery = useQuery({
    queryKey: queryKeys.tenantQuotas,
    queryFn: getTenantQuotas,
    staleTime: 60_000,
  });

  const tenantUsageQuery = useQuery({
    queryKey: queryKeys.tenantUsage,
    queryFn: getTenantUsage,
    staleTime: 30_000,
  });

  const tenantCommercialQuery = useQuery({
    queryKey: queryKeys.tenantCommercial,
    queryFn: getTenantCommercial,
    staleTime: 60_000,
  });

  const tenantCommercialBoundaryQuery = useQuery({
    queryKey: queryKeys.tenantCommercialProviderBoundary,
    queryFn: getTenantCommercialProviderBoundary,
    staleTime: 60_000,
  });

  const tenantUsageReportQuery = useQuery({
    queryKey: queryKeys.tenantUsageReport,
    queryFn: () => getTenantUsageReport(8),
    staleTime: 30_000,
  });

  const totpQuery = useQuery({
    queryKey: queryKeys.myTotp,
    queryFn: getTotpStatus,
    staleTime: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: (data: CreateTenantInput) =>
      createTenant({
        name: data.name,
        slug: data.slug || undefined,
        is_active: data.isActive,
      }),
    onSuccess: () => {
      setFeedback("Tenant created successfully.");
      form.reset();
      queryClient.invalidateQueries({ queryKey: queryKeys.tenants });
      setTimeout(() => setFeedback(""), 4000);
    },
    onError: (err) => {
      const msg = extractErrorMessage(err);
      setFeedback(`Error: ${msg}`);
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) =>
      setTenantStatus(id, active),
    onSuccess: () => {
      setFeedback("Tenant status updated.");
      queryClient.invalidateQueries({ queryKey: queryKeys.tenants });
      setTimeout(() => setFeedback(""), 4000);
    },
    onError: (err) => {
      const msg = extractErrorMessage(err);
      setFeedback(`Error: ${msg}`);
    },
  });

  const toggleTenantTotpMutation = useMutation({
    mutationFn: (enabled: boolean) => updateTenantSettings({ auth_policy: { ...(tenantSettingsQuery.data?.tenant_settings.auth_policy || {}), totp_mfa_enabled: enabled } }),
    onSuccess: () => {
      setFeedback("Tenant auth policy updated.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.tenantSettings });
    },
    onError: (err) => setFeedback(`Error: ${extractErrorMessage(err)}`),
  });

  const toggleTenantOidcMutation = useMutation({
    mutationFn: (enabled: boolean) =>
      updateTenantSettings({
        auth_policy: {
          ...(tenantSettingsQuery.data?.tenant_settings.auth_policy || {}),
          oidc_enabled: enabled,
        },
      }),
    onSuccess: () => {
      setFeedback("Tenant OIDC policy updated.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.tenantSettings });
    },
    onError: (err) => setFeedback(`Error: ${extractErrorMessage(err)}`),
  });

  const enrollTotpMutation = useMutation({
    mutationFn: enrollTotp,
    onSuccess: (data) => {
      setFeedback("Authenticator enrollment secret created.");
      setEnrollmentSecret(data.totp.secret || "");
      setEnrollmentUri(data.totp.provisioning_uri || "");
      void queryClient.invalidateQueries({ queryKey: queryKeys.myTotp });
    },
    onError: (err) => setFeedback(`Error: ${extractErrorMessage(err)}`),
  });

  const activateTotpMutation = useMutation({
    mutationFn: () => activateTotp(totpCode),
    onSuccess: () => {
      setFeedback("Authenticator MFA enabled.");
      setTotpCode("");
      setEnrollmentSecret("");
      setEnrollmentUri("");
      void queryClient.invalidateQueries({ queryKey: queryKeys.myTotp });
    },
    onError: (err) => setFeedback(`Error: ${extractErrorMessage(err)}`),
  });

  const disableTotpMutation = useMutation({
    mutationFn: () => disableTotp(currentPassword),
    onSuccess: () => {
      setFeedback("Authenticator MFA disabled.");
      setCurrentPassword("");
      void queryClient.invalidateQueries({ queryKey: queryKeys.myTotp });
    },
    onError: (err) => setFeedback(`Error: ${extractErrorMessage(err)}`),
  });

  const createOidcProviderMutation = useMutation({
    mutationFn: () =>
      createOidcProvider({
        name: oidcName,
        issuer: oidcIssuer,
        client_id: oidcClientId,
        discovery_endpoint: oidcDiscoveryEndpoint || undefined,
        authorization_endpoint: oidcAuthEndpoint || undefined,
        token_endpoint: oidcTokenEndpoint || undefined,
        userinfo_endpoint: oidcUserinfoEndpoint || undefined,
        client_secret: oidcClientSecret || undefined,
        scopes: ["openid", "profile", "email"],
        claim_mappings: {
          email: "email",
          full_name: "name",
          groups: "groups",
        },
        role_mappings: {
          admins: ["admin"],
        },
        test_mode: oidcTestMode,
        test_claims: {
          default: {
            email: oidcTestEmail || "oidc-user@example.com",
            name: "OIDC Test User",
            groups: ["admins"],
          },
        },
        is_enabled: true,
        is_default: (oidcProvidersQuery.data?.count || 0) === 0,
      }),
    onSuccess: () => {
      setFeedback("OIDC provider created.");
      setOidcName("");
      setOidcIssuer("");
      setOidcClientId("");
      setOidcDiscoveryEndpoint("");
      setOidcAuthEndpoint("");
      setOidcTokenEndpoint("");
      setOidcUserinfoEndpoint("");
      setOidcClientSecret("");
      setOidcTestEmail("");
      setOidcTestMode(true);
      void queryClient.invalidateQueries({ queryKey: queryKeys.oidcProviders });
    },
    onError: (err) => setFeedback(`Error: ${extractErrorMessage(err)}`),
  });

  const updateOidcProviderMutation = useMutation({
    mutationFn: ({ providerId, payload }: { providerId: number; payload: Record<string, unknown> }) =>
      updateOidcProvider(providerId, payload),
    onSuccess: () => {
      setFeedback("OIDC provider updated.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.oidcProviders });
    },
    onError: (err) => setFeedback(`Error: ${extractErrorMessage(err)}`),
  });

  const discoverOidcProviderMutation = useMutation({
    mutationFn: (providerId: number) => discoverOidcProvider(providerId),
    onSuccess: () => {
      setFeedback("OIDC provider metadata refreshed.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.oidcProviders });
    },
    onError: (err) => setFeedback(`Error: ${extractErrorMessage(err)}`),
  });

  const updateQuotaMutation = useMutation({
    mutationFn: ({ quotaKey, limitValue, isEnforced }: { quotaKey: string; limitValue: number | null; isEnforced: boolean }) =>
      updateTenantQuotas({
        quotas: {
          [quotaKey]: {
            limit_value: limitValue,
            is_enforced: isEnforced,
          },
        },
      }),
    onSuccess: () => {
      setFeedback("Tenant quota updated.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.tenantQuotas });
      void queryClient.invalidateQueries({ queryKey: queryKeys.tenantUsage });
      void queryClient.invalidateQueries({ queryKey: queryKeys.tenantUsageReport });
    },
    onError: (err) => setFeedback(`Error: ${extractErrorMessage(err)}`),
  });

  const updateCommercialMutation = useMutation({
    mutationFn: () =>
      updateTenantCommercial({
        plan: {
          plan_key: planKey || tenantCommercialQuery.data?.tenant_commercial.plan.plan_key,
          display_name: planDisplayName || tenantCommercialQuery.data?.tenant_commercial.plan.display_name,
        },
        billing_profile: {
          billing_email: billingEmail || tenantCommercialQuery.data?.tenant_commercial.billing_profile.billing_email,
          provider_name: providerName || tenantCommercialQuery.data?.tenant_commercial.billing_profile.provider_name,
        },
        license: {
          license_status: licenseStatus || tenantCommercialQuery.data?.tenant_commercial.license.license_status,
          seat_limit: seatLimit.trim() ? Number(seatLimit) : tenantCommercialQuery.data?.tenant_commercial.license.seat_limit,
        },
      }),
    onSuccess: () => {
      setFeedback("Tenant commercial profile updated.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.tenantCommercial });
      void queryClient.invalidateQueries({ queryKey: queryKeys.tenantCommercialProviderBoundary });
    },
    onError: (err) => setFeedback(`Error: ${extractErrorMessage(err)}`),
  });

  const onSubmit = (data: CreateTenantInput) => {
    createMutation.mutate(data);
  };

  return (
    <ModulePage
      title="Tenants"
      description="List, create, and status management mapped to tenant APIs."
    >
      <div className="module-grid">
        <form className="module-card" onSubmit={form.handleSubmit(onSubmit)}>
          <h3>Create Tenant</h3>

          {feedback && (
            <div className={`feedback-message ${feedback.startsWith("Error:") ? "feedback-error" : "feedback-success"}`}>
              {feedback}
            </div>
          )}

          <FormInput
            form={form}
            name="name"
            label="Tenant Name"
            placeholder="Acme Corporation"
            required
            helperText="2-255 characters, unique within system"
          />

          <FormInput
            form={form}
            name="slug"
            label="Slug (optional)"
            placeholder="acme-corp"
            helperText="Lowercase, hyphens only. Auto-generated if empty."
          />

          <FormCheckbox
            form={form}
            name="isActive"
            label="Activate immediately"
            helperText="Inactive tenants cannot authenticate"
          />

          <FormSubmitButton
            isLoading={createMutation.isPending}
            isDisabled={!form.formState.isDirty}
          >
            Create Tenant
          </FormSubmitButton>
        </form>

        <div className="module-card">
          <h3>Tenant List ({tenantsQuery.data?.count ?? 0})</h3>
          {tenantsQuery.isLoading ? (
            <div className="module-status loading">Loading tenants...</div>
          ) : tenantsQuery.error ? (
            <div className="module-status error-text">Failed to load tenants.</div>
          ) : tenantsQuery.data?.tenants?.length ? (
            <table className="table-lite">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Slug</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {(tenantsQuery.data?.tenants || []).map((tenant) => (
                  <tr key={tenant.id}>
                    <td>{tenant.name}</td>
                    <td>{tenant.slug}</td>
                    <td>{tenant.is_active ? "Active" : "Inactive"}</td>
                    <td>
                      <button
                        onClick={() =>
                          statusMutation.mutate({ id: tenant.id, active: !tenant.is_active })
                        }
                        disabled={statusMutation.isPending || tenant.slug === "default"}
                        className="button-sm"
                      >
                        {tenant.is_active ? "Deactivate" : "Activate"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="module-status loading">No tenants found yet.</div>
          )}
        </div>

        <div className="module-card">
          <h3>Current Tenant Auth Policy</h3>
          {tenantSettingsQuery.isLoading ? (
            <div className="module-status loading">Loading auth policy...</div>
          ) : tenantSettingsQuery.error ? (
            <div className="module-status error-text">Failed to load auth policy.</div>
          ) : (
            <>
              <p>Min password length: {String(tenantSettingsQuery.data?.tenant_settings.auth_policy.min_password_length ?? 8)}</p>
              <p>Lockout: {String(tenantSettingsQuery.data?.tenant_settings.auth_policy.lockout_threshold ?? 5)} attempts / {String(tenantSettingsQuery.data?.tenant_settings.auth_policy.lockout_minutes ?? 15)} minutes</p>
              <p>Session max age: {String(tenantSettingsQuery.data?.tenant_settings.auth_policy.session_max_age_minutes ?? 10080)} minutes</p>
              <p>TOTP MFA policy: {tenantSettingsQuery.data?.tenant_settings.auth_policy.totp_mfa_enabled ? "Enabled" : "Optional / disabled"}</p>
              <p>OIDC SSO policy: {tenantSettingsQuery.data?.tenant_settings.auth_policy.oidc_enabled ? "Enabled" : "Disabled"}</p>
              <div className="row-between">
                <button type="button" onClick={() => toggleTenantTotpMutation.mutate(true)} disabled={toggleTenantTotpMutation.isPending}>
                  Enable TOTP Policy
                </button>
                <button type="button" onClick={() => toggleTenantTotpMutation.mutate(false)} disabled={toggleTenantTotpMutation.isPending}>
                  Disable TOTP Policy
                </button>
              </div>
              <div className="row-between" style={{ marginTop: "0.75rem" }}>
                <button type="button" onClick={() => toggleTenantOidcMutation.mutate(true)} disabled={toggleTenantOidcMutation.isPending}>
                  Enable OIDC
                </button>
                <button type="button" onClick={() => toggleTenantOidcMutation.mutate(false)} disabled={toggleTenantOidcMutation.isPending}>
                  Disable OIDC
                </button>
              </div>
            </>
          )}
        </div>

        <div className="module-card">
          <h3>My Authenticator MFA</h3>
          {totpQuery.isLoading ? (
            <div className="module-status loading">Loading MFA status...</div>
          ) : totpQuery.error ? (
            <div className="module-status error-text">Failed to load MFA status.</div>
          ) : (
            <>
              <p>Status: {totpQuery.data?.totp.status ?? "not_configured"}</p>
              <div className="row-between">
                <button type="button" onClick={() => enrollTotpMutation.mutate()} disabled={enrollTotpMutation.isPending}>
                  Start Enrollment
                </button>
              </div>
              {enrollmentSecret ? (
                <>
                  <p>Secret: <code>{enrollmentSecret}</code></p>
                  <p>URI: <code>{enrollmentUri}</code></p>
                </>
              ) : null}
              {(totpQuery.data?.totp.status === "pending" || enrollTotpMutation.isSuccess) ? (
                <>
                  <input
                    value={totpCode}
                    onChange={(e) => setTotpCode(e.target.value)}
                    placeholder="6-digit authenticator code"
                  />
                  <button type="button" onClick={() => activateTotpMutation.mutate()} disabled={activateTotpMutation.isPending || !totpCode.trim()}>
                    Activate MFA
                  </button>
                </>
              ) : null}
              {totpQuery.data?.totp.enabled ? (
                <>
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="Current password to disable MFA"
                  />
                  <button type="button" onClick={() => disableTotpMutation.mutate()} disabled={disableTotpMutation.isPending || !currentPassword.trim()}>
                    Disable MFA
                  </button>
                </>
              ) : null}
            </>
          )}
        </div>

        <div className="module-card">
          <h3>OIDC Providers</h3>
          {oidcProvidersQuery.isLoading ? (
            <div className="module-status loading">Loading providers...</div>
          ) : oidcProvidersQuery.error ? (
            <div className="module-status error-text">Failed to load OIDC providers.</div>
          ) : (
            <>
              <div className="stack-sm">
                <input value={oidcName} onChange={(e) => setOidcName(e.target.value)} placeholder="Provider name" />
                <input value={oidcIssuer} onChange={(e) => setOidcIssuer(e.target.value)} placeholder="https://issuer.example.com" />
                <input value={oidcClientId} onChange={(e) => setOidcClientId(e.target.value)} placeholder="Client ID" />
                <input value={oidcDiscoveryEndpoint} onChange={(e) => setOidcDiscoveryEndpoint(e.target.value)} placeholder="Discovery endpoint (optional)" />
                <input value={oidcAuthEndpoint} onChange={(e) => setOidcAuthEndpoint(e.target.value)} placeholder="Authorization endpoint (or use discovery)" />
                <input value={oidcTokenEndpoint} onChange={(e) => setOidcTokenEndpoint(e.target.value)} placeholder="Token endpoint (optional if discovery used)" />
                <input value={oidcUserinfoEndpoint} onChange={(e) => setOidcUserinfoEndpoint(e.target.value)} placeholder="Userinfo endpoint (optional if discovery used)" />
                <input value={oidcClientSecret} onChange={(e) => setOidcClientSecret(e.target.value)} placeholder="Client secret (optional)" type="password" />
                <input value={oidcTestEmail} onChange={(e) => setOidcTestEmail(e.target.value)} placeholder="Test-mode user email" />
                <label className="row-between" style={{ alignItems: "center" }}>
                  <span>Use deterministic test mode</span>
                  <input type="checkbox" checked={oidcTestMode} onChange={(e) => setOidcTestMode(e.target.checked)} />
                </label>
                <button
                  type="button"
                  onClick={() => createOidcProviderMutation.mutate()}
                  disabled={
                    createOidcProviderMutation.isPending ||
                    !oidcName.trim() ||
                    !oidcIssuer.trim() ||
                    !oidcClientId.trim() ||
                    (!oidcAuthEndpoint.trim() && !oidcDiscoveryEndpoint.trim())
                  }
                >
                  Add Provider
                </button>
              </div>
              {oidcProvidersQuery.data?.providers?.length ? (
                <table className="table-lite" style={{ marginTop: "1rem" }}>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Mode</th>
                      <th>Status</th>
                      <th>Default</th>
                      <th>Discovery</th>
                      <th>Last Auth</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {oidcProvidersQuery.data.providers.map((provider) => (
                      <tr key={provider.id}>
                        <td>{provider.name}</td>
                        <td>{provider.test_mode ? "Test" : "External"}</td>
                        <td>{provider.is_enabled ? "Enabled" : "Disabled"}</td>
                        <td>{provider.is_default ? "Yes" : "No"}</td>
                        <td>{provider.last_discovery_status ?? "Not run"}</td>
                        <td>{provider.last_auth_status ?? "Not run"}</td>
                        <td>
                          <div className="stack-sm">
                            <button
                              type="button"
                              className="button-sm"
                              disabled={updateOidcProviderMutation.isPending || discoverOidcProviderMutation.isPending}
                              onClick={() =>
                                updateOidcProviderMutation.mutate({
                                  providerId: provider.id,
                                  payload: { is_enabled: !provider.is_enabled },
                                })
                              }
                            >
                              {provider.is_enabled ? "Disable" : "Enable"}
                            </button>
                            <button
                              type="button"
                              className="button-sm"
                              disabled={updateOidcProviderMutation.isPending || discoverOidcProviderMutation.isPending || provider.is_default}
                              onClick={() =>
                                updateOidcProviderMutation.mutate({
                                  providerId: provider.id,
                                  payload: { is_default: true },
                                })
                              }
                            >
                              Make Default
                            </button>
                            {!provider.test_mode ? (
                              <button
                                type="button"
                                className="button-sm"
                                disabled={updateOidcProviderMutation.isPending || discoverOidcProviderMutation.isPending}
                                onClick={() => discoverOidcProviderMutation.mutate(provider.id)}
                              >
                                Refresh Metadata
                              </button>
                            ) : null}
                            {provider.last_error ? <small className="error-text">{provider.last_error}</small> : null}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="module-status loading" style={{ marginTop: "1rem" }}>
                  No OIDC providers configured yet.
                </div>
              )}
            </>
          )}
        </div>

        <div className="module-card">
          <h3>Quota Usage</h3>
          {tenantUsageQuery.isLoading || tenantQuotasQuery.isLoading || tenantUsageReportQuery.isLoading ? (
            <div className="module-status loading">Loading quotas...</div>
          ) : tenantUsageQuery.error || tenantQuotasQuery.error || tenantUsageReportQuery.error ? (
            <div className="module-status error-text">Failed to load quotas.</div>
          ) : (
            <>
              <div className="stats-grid" style={{ marginBottom: "1rem" }}>
                <StatCard
                  label="Quota domains"
                  value={tenantUsageReportQuery.data?.tenant_usage_report.summary.quota_count ?? 0}
                  detail="Tracked tenant quota keys"
                  status="neutral"
                />
                <StatCard
                  label="Enforced"
                  value={tenantUsageReportQuery.data?.tenant_usage_report.summary.enforced_count ?? 0}
                  detail="Currently hard-enforced"
                  status="ok"
                />
                <StatCard
                  label="Near limit"
                  value={tenantUsageReportQuery.data?.tenant_usage_report.summary.near_limit_count ?? 0}
                  detail="80% or more of limit used"
                  status={(tenantUsageReportQuery.data?.tenant_usage_report.summary.near_limit_count ?? 0) > 0 ? "warn" : "ok"}
                />
                <StatCard
                  label="Quota blocks"
                  value={tenantUsageReportQuery.data?.tenant_usage_report.summary.recent_enforcement_count ?? 0}
                  detail="Recent enforcement failures"
                  status={(tenantUsageReportQuery.data?.tenant_usage_report.summary.recent_enforcement_count ?? 0) > 0 ? "warn" : "ok"}
                />
              </div>
              <table className="table-lite">
                <thead>
                  <tr>
                    <th>Quota</th>
                    <th>Usage</th>
                    <th>Limit</th>
                    <th>Health</th>
                    <th>Mode</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {(tenantUsageReportQuery.data?.tenant_usage_report.quotas || []).map((item) => {
                    const quota = tenantQuotasQuery.data?.tenant_quotas.effective?.[item.quota_key];
                    const current = tenantUsageQuery.data?.tenant_usage.current?.[item.quota_key]?.current_value ?? item.current_value;
                    return (
                      <tr key={item.quota_key}>
                        <td>{item.quota_key}</td>
                        <td>{String(current)}{item.percent_used != null ? ` (${item.percent_used}%)` : ""}</td>
                        <td>{quota?.limit_value ?? "Unlimited"}</td>
                        <td>{item.status}</td>
                        <td>{quota?.is_enforced ? "Enforced" : "Monitor only"}</td>
                        <td>
                          <div className="row-between">
                            <button
                              type="button"
                              className="button-sm"
                              disabled={updateQuotaMutation.isPending}
                              onClick={() =>
                                updateQuotaMutation.mutate({
                                  quotaKey: item.quota_key,
                                  limitValue: Math.max(current, 1),
                                  isEnforced: true,
                                })
                              }
                            >
                              Enforce Current
                            </button>
                            <button
                              type="button"
                              className="button-sm"
                              disabled={updateQuotaMutation.isPending}
                              onClick={() =>
                                updateQuotaMutation.mutate({
                                  quotaKey: item.quota_key,
                                  limitValue: null,
                                  isEnforced: false,
                                })
                              }
                            >
                              Clear
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div style={{ marginTop: "1rem" }}>
                <h4>Recent Quota Enforcement</h4>
                {tenantUsageReportQuery.data?.tenant_usage_report.recent_enforcement_events.length ? (
                  <table className="table-lite">
                    <thead>
                      <tr>
                        <th>Quota</th>
                        <th>When</th>
                        <th>Requested</th>
                        <th>Limit</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tenantUsageReportQuery.data?.tenant_usage_report.recent_enforcement_events.map((event) => {
                        const details = event.details || {};
                        return (
                          <tr key={event.id}>
                            <td>{event.quota_key ?? "unknown"}</td>
                            <td>{event.created_at ?? "n/a"}</td>
                            <td>{String(details.requested_value ?? "n/a")}</td>
                            <td>{String(details.limit_value ?? "n/a")}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                ) : (
                  <div className="module-status loading">No recent quota enforcement failures.</div>
                )}
              </div>
            </>
          )}
        </div>

        <div className="module-card">
          <h3>Commercial Draft</h3>
          {tenantCommercialQuery.isLoading || tenantCommercialBoundaryQuery.isLoading ? (
            <div className="module-status loading">Loading commercial profile...</div>
          ) : tenantCommercialQuery.error || tenantCommercialBoundaryQuery.error ? (
            <div className="module-status error-text">Failed to load commercial profile.</div>
          ) : (
            <>
              <p>Plan: {tenantCommercialQuery.data?.tenant_commercial.plan.display_name} ({tenantCommercialQuery.data?.tenant_commercial.plan.plan_key})</p>
              <p>Provider: {tenantCommercialQuery.data?.tenant_commercial.billing_profile.provider_name ?? "manual"}</p>
              <p>License: {tenantCommercialQuery.data?.tenant_commercial.license.license_status}</p>
              <div className="stats-grid" style={{ marginBottom: "1rem" }}>
                <StatCard
                  label="Provider"
                  value={tenantCommercialBoundaryQuery.data?.provider_boundary.current_provider ?? "manual"}
                  detail="Current commercial provider boundary"
                  status="neutral"
                />
                <StatCard
                  label="Customer sync"
                  value={tenantCommercialBoundaryQuery.data?.provider_boundary.sync_readiness.can_sync_customer ? "Ready" : "Not ready"}
                  detail={`Customer ref ready: ${tenantCommercialBoundaryQuery.data?.provider_boundary.sync_readiness.customer_ready ? "yes" : "no"}`}
                  status={tenantCommercialBoundaryQuery.data?.provider_boundary.sync_readiness.can_sync_customer ? "ok" : "warn"}
                />
                <StatCard
                  label="Subscription sync"
                  value={tenantCommercialBoundaryQuery.data?.provider_boundary.sync_readiness.can_sync_subscription ? "Ready" : "Not ready"}
                  detail={`Subscription ref ready: ${tenantCommercialBoundaryQuery.data?.provider_boundary.sync_readiness.subscription_ready ? "yes" : "no"}`}
                  status={tenantCommercialBoundaryQuery.data?.provider_boundary.sync_readiness.can_sync_subscription ? "ok" : "warn"}
                />
                <StatCard
                  label="License sync"
                  value={tenantCommercialBoundaryQuery.data?.provider_boundary.sync_readiness.can_sync_license ? "Ready" : "Not ready"}
                  detail={`Lifecycle ready: ${tenantCommercialBoundaryQuery.data?.provider_boundary.sync_readiness.license_ready ? "yes" : "no"}`}
                  status={tenantCommercialBoundaryQuery.data?.provider_boundary.sync_readiness.can_sync_license ? "ok" : "warn"}
                />
              </div>
              <div className="stack-sm">
                <input value={planKey} onChange={(e) => setPlanKey(e.target.value)} placeholder="Plan key" />
                <input value={planDisplayName} onChange={(e) => setPlanDisplayName(e.target.value)} placeholder="Plan display name" />
                <input value={billingEmail} onChange={(e) => setBillingEmail(e.target.value)} placeholder="Billing email" />
                <input value={providerName} onChange={(e) => setProviderName(e.target.value)} placeholder="Provider name" />
                <input value={licenseStatus} onChange={(e) => setLicenseStatus(e.target.value)} placeholder="License status" />
                <input value={seatLimit} onChange={(e) => setSeatLimit(e.target.value)} placeholder="Seat limit (optional)" />
                <button
                  type="button"
                  onClick={() => updateCommercialMutation.mutate()}
                  disabled={updateCommercialMutation.isPending}
                >
                  Save Commercial Draft
                  </button>
                </div>
                <div style={{ marginTop: "1rem" }}>
                  <h4>Supported Providers</h4>
                  <table className="table-lite">
                    <thead>
                      <tr>
                        <th>Provider</th>
                        <th>Customer Sync</th>
                        <th>Subscription Sync</th>
                        <th>License Sync</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(tenantCommercialBoundaryQuery.data?.provider_boundary.supported_providers || {}).map(([providerKey, capability]) => (
                        <tr key={providerKey}>
                          <td>{providerKey}</td>
                          <td>{String(capability.supports_customer_sync ? "Yes" : "No")}</td>
                          <td>{String(capability.supports_subscription_sync ? "Yes" : "No")}</td>
                          <td>{String(capability.supports_license_sync ? "Yes" : "No")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div style={{ marginTop: "1rem" }}>
                  <h4>Lifecycle Semantics</h4>
                  <p>Plan statuses: {(tenantCommercialQuery.data?.tenant_commercial.lifecycle_semantics.allowed_plan_statuses || []).join(", ")}</p>
                  <p>Billing cycles: {(tenantCommercialQuery.data?.tenant_commercial.lifecycle_semantics.allowed_billing_cycles || []).join(", ")}</p>
                  <p>License statuses: {(tenantCommercialQuery.data?.tenant_commercial.lifecycle_semantics.allowed_license_statuses || []).join(", ")}</p>
                  <p>Enforcement modes: {(tenantCommercialQuery.data?.tenant_commercial.lifecycle_semantics.allowed_enforcement_modes || []).join(", ")}</p>
                </div>
              </>
            )}
          </div>
      </div>
    </ModulePage>
  );
}
