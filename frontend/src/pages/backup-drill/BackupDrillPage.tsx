import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { getBackups, runBackupRestoreDrill } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import { extractErrorMessage } from "../../lib/errorUtils";

export function BackupDrillPage() {
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState("");
  const [selectedBackup, setSelectedBackup] = useState<string>("");

  const backupsQuery = useQuery({
    queryKey: queryKeys.backupDrill,
    queryFn: getBackups,
    staleTime: 60_000,
  });

  const restoreDrillMutation = useMutation({
    mutationFn: (filename: string) => runBackupRestoreDrill(filename),
    onSuccess: () => {
      setFeedback("Backup restore drill completed.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.backupDrill });
      setTimeout(() => setFeedback(""), 5000);
    },
    onError: (err) => setFeedback(`Error running restore drill: ${extractErrorMessage(err)}`),
  });

  const refreshBackupDrill = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.backupDrill });
  };

  const resetBackupDrillView = () => {
    setFeedback("");
    setSelectedBackup("");
  };

  const handleRunDrill = () => {
    if (!selectedBackup) {
      setFeedback("Select a backup before running the restore drill.");
      return;
    }
    restoreDrillMutation.mutate(selectedBackup);
  };

  const backups = Array.isArray(backupsQuery.data?.backups) ? backupsQuery.data.backups : [];

  return (
    <ModulePage
      title="Backup Drill"
      description="Run restore drill validation for backup snapshots."
      isLoading={backupsQuery.isLoading}
      error={backupsQuery.isError ? "Could not load backups." : ""}
      actions={
        <div className="module-page-actions-group">
          <button type="button" onClick={refreshBackupDrill} disabled={backupsQuery.isFetching}>
            Refresh backups
          </button>
          <button type="button" onClick={resetBackupDrillView}>
            Reset drill view
          </button>
        </div>
      }
    >
      <div className="panel">
        <h2>Available Backups</h2>
        {backups.length ? (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {backups.map((backup: any, index) => (
                  <tr key={index}>
                    <td>{backup.filename || backup.name || `backup-${index}`}</td>
                    <td>
                      <button
                        className="button button--secondary"
                        type="button"
                        onClick={() => setSelectedBackup(backup.filename || backup.name || "")}
                      >
                        Select
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div>No backups available.</div>
        )}
      </div>

      <div className="panel" style={{ marginTop: 24 }}>
        <h2>Restore Drill</h2>
        <div className="form-field">
          <label className="form-label">Selected Backup</label>
          <input value={selectedBackup} disabled className="form-input" />
        </div>
        <button
          className="button button--primary"
          type="button"
          onClick={handleRunDrill}
          disabled={restoreDrillMutation.status === "pending" || !selectedBackup}
        >
          {restoreDrillMutation.status === "pending" ? "Running drill..." : "Run restore drill"}
        </button>
        {feedback ? <div className="module-status success-text" style={{ marginTop: 12 }}>{feedback}</div> : null}
      </div>
    </ModulePage>
  );
}
