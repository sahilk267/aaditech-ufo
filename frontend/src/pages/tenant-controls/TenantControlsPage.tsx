import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { getTenantControls, updateTenantControls } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import { extractErrorMessage } from "../../lib/errorUtils";

export function TenantControlsPage() {
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState("");
  const [controls, setControls] = useState<Record<string, unknown>>({});

  const controlsQuery = useQuery({
    queryKey: queryKeys.tenantControls,
    queryFn: getTenantControls,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (controlsQuery.data?.tenant_controls) {
      setControls(controlsQuery.data.tenant_controls);
    }
  }, [controlsQuery.data]);

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => updateTenantControls(payload),
    onSuccess: () => {
      setFeedback("Tenant controls updated.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.tenantControls });
      setTimeout(() => setFeedback(""), 4000);
    },
    onError: (err) => {
      setFeedback(`Error updating controls: ${extractErrorMessage(err)}`);
    },
  });

  const refreshTenantControls = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.tenantControls });
  };

  const resetTenantControlsView = () => {
    setFeedback("");
    setControls({});
  };

  const handleSubmit = () => {
    updateMutation.mutate({
      entitlements: controls?.entitlements ?? {},
      feature_flags: controls?.feature_flags ?? {},
    });
  };

  const error = controlsQuery.isError ? "Could not load tenant controls." : "";

  return (
    <ModulePage
      title="Tenant Controls"
      description="View tenant entitlements and feature flags with effective defaults."
      isLoading={controlsQuery.isLoading}
      error={error}
      actions={
        <div className="module-page-actions-group">
          <button type="button" onClick={refreshTenantControls} disabled={controlsQuery.isFetching}>
            Refresh controls
          </button>
          <button type="button" onClick={resetTenantControlsView}>
            Reset controls view
          </button>
        </div>
      }
    >
      <div className="panel">
        <h2>Tenant Controls</h2>
        <p>Current controls are shown for reference. Edit values in the backend model and save.</p>
        <pre>{JSON.stringify(controls, null, 2)}</pre>
        <button className="button button--primary" type="button" onClick={handleSubmit} disabled={updateMutation.status === "pending"}>
          {updateMutation.status === "pending" ? "Updating..." : "Save controls"}
        </button>
        {feedback ? <div className="module-status success-text">{feedback}</div> : null}
      </div>
    </ModulePage>
  );
}
