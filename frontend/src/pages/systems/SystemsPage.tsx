import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { JsonViewer } from "../../components/common/JsonViewer";
import { PERMISSIONS } from "../../config/permissions";
import { extractErrorMessage } from "../../lib/errorUtils";
import { getSystem, getSystems, submitManualSystemData } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import { useAuthStore } from "../../store/authStore";

export function SystemsPage() {
  const queryClient = useQueryClient();
  const userPermissions = useAuthStore((state) => state.user?.permissions || []);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [message, setMessage] = useState("");

  const systemsQuery = useQuery({
    queryKey: queryKeys.systems,
    queryFn: getSystems,
    staleTime: 30_000,
  });

  const effectiveSelectedId = selectedId ?? systemsQuery.data?.systems?.[0]?.id ?? null;

  const detailQuery = useQuery({
    queryKey: queryKeys.system(effectiveSelectedId || 0),
    queryFn: () => getSystem(effectiveSelectedId as number),
    enabled: Boolean(effectiveSelectedId),
  });

  const submitMutation = useMutation({
    mutationFn: submitManualSystemData,
    onSuccess: (data) => {
      setMessage(data.message || "Manual submit complete");
      queryClient.invalidateQueries({ queryKey: queryKeys.systems });
      if (effectiveSelectedId) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.system(effectiveSelectedId) });
      }
    },
    onError: (err) => {
      setMessage(extractErrorMessage(err));
    },
  });

  const canManualSubmit = userPermissions.includes(PERMISSIONS.SYSTEM_SUBMIT);

  const refreshSystems = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.systems });
    if (effectiveSelectedId) {
      void queryClient.invalidateQueries({ queryKey: queryKeys.system(effectiveSelectedId) });
    }
  };

  const resetSystemsView = () => {
    setMessage("");
    if (systemsQuery.data?.systems?.length) {
      const firstSystem = systemsQuery.data.systems[0];
      setSelectedId(firstSystem.id);
    } else {
      setSelectedId(null);
    }
  };

  return (
    <ModulePage
      title="Systems"
      description="Inventory table, live details, and manual submit action are now API-wired."
      isLoading={systemsQuery.isLoading}
      error={systemsQuery.isError ? "Failed to load systems inventory." : null}
      actions={
        <div className="module-page-actions-group">
          <button type="button" onClick={refreshSystems} disabled={systemsQuery.isFetching}>
            Refresh systems
          </button>
          <button type="button" onClick={resetSystemsView}>
            Reset view
          </button>
        </div>
      }
    >
      <div className="module-grid">
        <div className="module-card">
          <div className="row-between">
            <h3>Systems ({systemsQuery.data?.count ?? 0})</h3>
            <button
              onClick={() => submitMutation.mutate()}
              disabled={submitMutation.isPending || !canManualSubmit}
              title={!canManualSubmit ? `Missing permission: ${PERMISSIONS.SYSTEM_SUBMIT}` : undefined}
            >
              {submitMutation.isPending ? "Submitting..." : "Manual Submit"}
            </button>
          </div>
          {!canManualSubmit ? <small>Manual submit requires {PERMISSIONS.SYSTEM_SUBMIT}.</small> : null}
          {message ? <small>{message}</small> : null}
          {systemsQuery.isLoading ? (
            <div className="module-status loading">Loading systems inventory...</div>
          ) : systemsQuery.error ? (
            <div className="module-status error-text">Failed to load systems inventory.</div>
          ) : systemsQuery.data?.systems?.length ? (
            <table className="table-lite" style={{ marginTop: 10 }}>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Hostname</th>
                  <th>Status</th>
                  <th>Last Update</th>
                </tr>
              </thead>
              <tbody>
                {(systemsQuery.data?.systems || []).map((system) => (
                  <tr
                    key={system.id}
                    onClick={() => {
                      setSelectedId(system.id);
                      setMessage("");
                    }}
                    className={effectiveSelectedId === system.id ? "selected-row" : ""}
                  >
                    <td>{system.id}</td>
                    <td>{system.hostname}</td>
                    <td>{system.status}</td>
                    <td>{system.last_update || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="module-status loading">No systems found yet.</div>
          )}
        </div>

        <div className="module-card">
          <h3>Selected System Detail</h3>
          {effectiveSelectedId && detailQuery.isLoading ? (
            <div className="module-status loading">Loading system detail...</div>
          ) : detailQuery.error ? (
            <div className="module-status error-text">Failed to load system detail.</div>
          ) : detailQuery.data?.system ? (
            <JsonViewer data={detailQuery.data?.system} />
          ) : systemsQuery.data?.systems?.length ? (
            <p>Select a system from the table.</p>
          ) : (
            <p>System detail will appear here once inventory data is available.</p>
          )}
        </div>
      </div>
    </ModulePage>
  );
}
