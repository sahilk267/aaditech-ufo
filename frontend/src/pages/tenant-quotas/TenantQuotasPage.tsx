import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { getTenantQuotas, updateTenantQuotas } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import { extractErrorMessage } from "../../lib/errorUtils";

export function TenantQuotasPage() {
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState("");
  const [quotas, setQuotas] = useState<Record<string, { limit_value?: number | null; is_enforced?: boolean }>>({});

  const quotasQuery = useQuery({
    queryKey: queryKeys.tenantQuotas,
    queryFn: getTenantQuotas,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (quotasQuery.data?.tenant_quotas?.effective) {
      setQuotas(quotasQuery.data.tenant_quotas.effective as Record<string, { limit_value?: number | null; is_enforced?: boolean }>);
    }
  }, [quotasQuery.data]);

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => updateTenantQuotas(payload),
    onSuccess: () => {
      setFeedback("Quota policy updated.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.tenantQuotas });
      setTimeout(() => setFeedback(""), 4000);
    },
    onError: (err) => {
      setFeedback(`Error updating quotas: ${extractErrorMessage(err)}`);
    },
  });

  const refreshTenantQuotas = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.tenantQuotas });
  };

  const resetTenantQuotasView = () => {
    setFeedback("");
    setQuotas({});
  };

  const handleLimitChange = (key: string, value: string) => {
    setQuotas((current) => ({
      ...current,
      [key]: {
        ...current[key],
        limit_value: value === "" ? null : Number(value),
      },
    }));
  };

  const handleSubmit = () => {
    const payload = {
      quotas: Object.fromEntries(
        Object.entries(quotas).map(([quotaKey, quota]) => [quotaKey, {
          limit_value: quota.limit_value,
          is_enforced: quota.is_enforced ?? false,
        }])
      ),
    };
    updateMutation.mutate(payload);
  };

  const error = quotasQuery.isError ? "Could not load tenant quota policies." : "";

  return (
    <ModulePage
      title="Tenant Quotas"
      description="View and update tenant quota policies for supported quota types."
      isLoading={quotasQuery.isLoading}
      error={error}
      actions={
        <div className="module-page-actions-group">
          <button type="button" onClick={refreshTenantQuotas} disabled={quotasQuery.isFetching}>
            Refresh quotas
          </button>
          <button type="button" onClick={resetTenantQuotasView}>
            Reset quotas view
          </button>
        </div>
      }
    >
      <div className="panel">
        {Object.entries(quotas).length === 0 ? (
          <div>No quota data available.</div>
        ) : (
          <div className="grid-grid--2">
            {Object.entries(quotas).map(([quotaKey, quota]) => (
              <div key={quotaKey} className="panel panel--sub">
                <h3>{quotaKey}</h3>
                <div className="form-field">
                  <label className="form-label">Limit value</label>
                  <input
                    type="number"
                    value={quota.limit_value ?? ""}
                    onChange={(event) => handleLimitChange(quotaKey, event.target.value)}
                    className="form-input"
                    min={0}
                  />
                </div>
                <div className="form-field form-field--checkbox">
                  <label className="form-checkbox-label">
                    <input
                      type="checkbox"
                      checked={quota.is_enforced ?? false}
                      onChange={() =>
                        setQuotas((current) => ({
                          ...current,
                          [quotaKey]: {
                            ...current[quotaKey],
                            is_enforced: !(current[quotaKey]?.is_enforced ?? false),
                          },
                        }))
                      }
                    />
                    <span>Enforced</span>
                  </label>
                </div>
              </div>
            ))}
          </div>
        )}
        <button className="button button--primary" type="button" onClick={handleSubmit} disabled={updateMutation.status === "pending"}>
          {updateMutation.status === "pending" ? "Updating..." : "Save quotas"}
        </button>
        {feedback ? <div className="module-status success-text">{feedback}</div> : null}
      </div>
    </ModulePage>
  );
}
