import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
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
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [message, setMessage] = useState("");

  const systemsQuery = useQuery({
    queryKey: queryKeys.systems,
    queryFn: getSystems,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (selectedId || !systemsQuery.data?.systems?.length) {
      return;
    }

    const serialNumber = searchParams.get("serial");
    const matchedSystem = serialNumber
      ? systemsQuery.data.systems.find((system) => system.serial_number === serialNumber)
      : undefined;
    const nextSystem = matchedSystem || systemsQuery.data.systems[0];

    setSelectedId(nextSystem.id);

    if (serialNumber && !matchedSystem) {
      setMessage(`System with serial ${serialNumber} was not found. Showing latest available system.`);
    }
  }, [selectedId, searchParams, systemsQuery.data]);

  useEffect(() => {
    if (!selectedId || !systemsQuery.data?.systems?.length) {
      return;
    }

    const selectedSystem = systemsQuery.data.systems.find((system) => system.id === selectedId);
    if (!selectedSystem) {
      return;
    }

    const currentSerial = searchParams.get("serial");
    if (currentSerial === selectedSystem.serial_number) {
      return;
    }

    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("serial", selectedSystem.serial_number);
    setSearchParams(nextParams, { replace: true });
  }, [searchParams, selectedId, setSearchParams, systemsQuery.data]);

  const detailQuery = useQuery({
    queryKey: queryKeys.system(selectedId || 0),
    queryFn: () => getSystem(selectedId as number),
    enabled: Boolean(selectedId),
  });

  const submitMutation = useMutation({
    mutationFn: submitManualSystemData,
    onSuccess: (data) => {
      setMessage(data.message || "Manual submit complete");
      queryClient.invalidateQueries({ queryKey: queryKeys.systems });
    },
    onError: (err) => {
      setMessage(extractErrorMessage(err));
    },
  });

  const canManualSubmit = userPermissions.includes(PERMISSIONS.SYSTEM_SUBMIT);

  return (
    <ModulePage
      title="Systems"
      description="Inventory table, live details, and manual submit action are now API-wired."
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
                  className={selectedId === system.id ? "selected-row" : ""}
                >
                  <td>{system.id}</td>
                  <td>{system.hostname}</td>
                  <td>{system.status}</td>
                  <td>{system.last_update || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="module-card">
          <h3>Selected System Detail</h3>
          {detailQuery.data?.system ? (
            <JsonViewer data={detailQuery.data?.system} />
          ) : (
            <p>Select a system from the table.</p>
          )}
        </div>
      </div>
    </ModulePage>
  );
}
