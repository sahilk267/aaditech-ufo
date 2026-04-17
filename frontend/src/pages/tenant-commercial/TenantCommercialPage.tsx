import { ModulePage } from "../../components/common/ModulePage";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getTenantCommercial } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";

export function TenantCommercialPage() {
  const queryClient = useQueryClient();
  const commercialQuery = useQuery({
    queryKey: queryKeys.tenantCommercial,
    queryFn: getTenantCommercial,
    staleTime: 60_000,
  });

  const refreshTenantCommercial = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.tenantCommercial });
  };

  return (
    <ModulePage
      title="Tenant Commercial"
      description="Review tenant commercial profile, billing, and license state."
      isLoading={commercialQuery.isLoading}
      error={commercialQuery.isError ? "Could not load tenant commercial data." : ""}
      actions={
        <div className="module-page-actions-group">
          <button type="button" onClick={refreshTenantCommercial} disabled={commercialQuery.isFetching}>
            Refresh commercial data
          </button>
        </div>
      }
    >
      <div className="panel">
        {commercialQuery.data?.tenant_commercial ? (
          <pre>{JSON.stringify(commercialQuery.data.tenant_commercial, null, 2)}</pre>
        ) : (
          <div>No commercial profile data is available.</div>
        )}
      </div>
    </ModulePage>
  );
}
