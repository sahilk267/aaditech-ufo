import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { getTenantSettings, updateTenantSettings } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import { extractErrorMessage } from "../../lib/errorUtils";

export function TenantSettingsPage() {
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState("");
  const [policy, setPolicy] = useState({
    totp_mfa_enabled: false,
    oidc_enabled: false,
    local_admin_fallback_enabled: false,
  });

  const settingsQuery = useQuery({
    queryKey: queryKeys.tenantSettings,
    queryFn: getTenantSettings,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (settingsQuery.data?.tenant_settings?.auth_policy) {
      setPolicy({
        totp_mfa_enabled: Boolean(settingsQuery.data.tenant_settings.auth_policy.totp_mfa_enabled),
        oidc_enabled: Boolean(settingsQuery.data.tenant_settings.auth_policy.oidc_enabled),
        local_admin_fallback_enabled: Boolean(
          settingsQuery.data.tenant_settings.auth_policy.local_admin_fallback_enabled
        ),
      });
    }
  }, [settingsQuery.data]);

  const updateSettingsMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => updateTenantSettings(payload),
    onSuccess: () => {
      setFeedback("Tenant settings saved successfully.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.tenantSettings });
      setTimeout(() => setFeedback(""), 4000);
    },
    onError: (err) => {
      setFeedback(`Error saving settings: ${extractErrorMessage(err)}`);
    },
  });

  const refreshTenantSettings = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.tenantSettings });
  };

  const resetTenantSettingsView = () => {
    setFeedback("");
    setPolicy({
      totp_mfa_enabled: false,
      oidc_enabled: false,
      local_admin_fallback_enabled: false,
    });
  };

  const handleToggle = (field: keyof typeof policy) => {
    setPolicy((current) => ({ ...current, [field]: !current[field] }));
  };

  const handleSave = () => {
    updateSettingsMutation.mutate({ auth_policy: policy });
  };

  const error = settingsQuery.isError ? "Could not load tenant settings." : "";

  return (
    <ModulePage
      title="Tenant Settings"
      description="Review and update tenant authentication and policy defaults."
      isLoading={settingsQuery.isLoading}
      error={error}
      actions={
        <div className="module-page-actions-group">
          <button type="button" onClick={refreshTenantSettings} disabled={settingsQuery.isFetching}>
            Refresh settings
          </button>
          <button type="button" onClick={resetTenantSettingsView}>
            Reset settings view
          </button>
        </div>
      }
    >
      <div className="panel">
        <h2>Authentication Policy</h2>
        <div className="form-field form-field--checkbox">
          <label className="form-checkbox-label">
            <input
              type="checkbox"
              checked={policy.totp_mfa_enabled}
              onChange={() => handleToggle("totp_mfa_enabled")}
            />
            <span>Enable TOTP MFA</span>
          </label>
        </div>
        <div className="form-field form-field--checkbox">
          <label className="form-checkbox-label">
            <input type="checkbox" checked={policy.oidc_enabled} onChange={() => handleToggle("oidc_enabled")} />
            <span>Enable OIDC login</span>
          </label>
        </div>
        <div className="form-field form-field--checkbox">
          <label className="form-checkbox-label">
            <input
              type="checkbox"
              checked={policy.local_admin_fallback_enabled}
              onChange={() => handleToggle("local_admin_fallback_enabled")}
            />
            <span>Enable local admin fallback</span>
          </label>
        </div>
        <button className="button button--primary" type="button" onClick={handleSave} disabled={updateSettingsMutation.status === "pending"}>
          {updateSettingsMutation.status === "pending" ? "Saving..." : "Save settings"}
        </button>
        {feedback ? <div className="module-status success-text">{feedback}</div> : null}
      </div>
      <div className="panel" style={{ marginTop: 24 }}>
        <h3>Current tenant settings</h3>
        <pre>{JSON.stringify(settingsQuery.data?.tenant_settings ?? {}, null, 2)}</pre>
      </div>
    </ModulePage>
  );
}
