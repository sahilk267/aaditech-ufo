import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ModulePage } from '../../components/common/ModulePage';
import { ActionPanel } from '../../components/common/ActionPanel';
import { JsonViewer } from '../../components/common/JsonViewer';
import { MutationFeedback } from '../../components/common/MutationFeedback';
import {
  FormInput,
  FormCheckbox,
  FormSubmitButton,
} from '../../components/forms/FormComponents';
import { restoreBackupSchema, type RestoreBackupInput } from '../../lib/schemas';
import { createBackup, getBackups, restoreBackup, verifyBackup } from '../../lib/api';

/**
 * BackupPage - Backup management console
 *
 * Features:
 * - Restore from backup with verification
 * - Dry-run mode for safe testing
 * - Integrity validation option
 */

export function BackupPage() {
  const queryClient = useQueryClient();
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [selectedFilename, setSelectedFilename] = useState('');

  const form = useForm<RestoreBackupInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(restoreBackupSchema) as any,
    defaultValues: {
      filename: '',
      dryRun: true,
      verifyIntegrity: true,
    },
  });

  const backupsQuery = useQuery({
    queryKey: ['backups'],
    queryFn: getBackups,
    staleTime: 30_000,
  });

  const createBackupMutation = useMutation({
    mutationFn: createBackup,
    onSuccess: async (data) => {
      setLatestResult(data);
      setActionError(null);
      await queryClient.invalidateQueries({ queryKey: ['backups'] });
    },
    onError: (err) => setActionError(err),
  });

  const restoreBackupMutation = useMutation({
    mutationFn: (data: RestoreBackupInput) => restoreBackup(data.filename),
    onSuccess: async (data) => {
      setLatestResult(data);
      setActionError(null);
      form.reset();
      await queryClient.invalidateQueries({ queryKey: ['backups'] });
    },
    onError: (err) => setActionError(err),
  });

  const verifyBackupMutation = useMutation({
    mutationFn: (filename: string) => verifyBackup(filename),
    onSuccess: (data) => {
      setLatestResult(data);
      setActionError(null);
    },
    onError: (err) => setActionError(err),
  });

  const onSubmit = (data: RestoreBackupInput) => {
    restoreBackupMutation.mutate(data);
  };

  const backupRows = Array.isArray(backupsQuery.data?.backups) ? backupsQuery.data.backups : [];

  const applySelectedBackup = () => {
    if (!selectedFilename) return;
    form.setValue('filename', selectedFilename, { shouldDirty: true, shouldValidate: true });
  };

  const refreshBackupList = () => {
    void queryClient.invalidateQueries({ queryKey: ['backups'] });
  };

  const resetBackupView = () => {
    setLatestResult(null);
    setActionError(null);
    setSelectedFilename('');
    form.reset();
  };

  return (
    <ModulePage
      title="Backup Management"
      description="Manage database backups and restore operations. Create, view, and restore backup snapshots."
      actions={
        <div className="module-page-actions-group">
          <button type="button" onClick={refreshBackupList} disabled={backupsQuery.isFetching}>
            Refresh backups
          </button>
          <button type="button" onClick={resetBackupView}>
            Reset backup view
          </button>
        </div>
      }
      isLoading={backupsQuery.isLoading}
      error={backupsQuery.isError ? 'Failed to load backup list.' : null}
    >
      <div style={{ display: 'grid', gap: '16px' }}>
        <ActionPanel title="Create Backup">
          <button
            onClick={() => createBackupMutation.mutate()}
            disabled={createBackupMutation.isPending}
          >
            {createBackupMutation.isPending ? 'Creating backup...' : 'Create New Backup'}
          </button>
          <MutationFeedback error={createBackupMutation.error || actionError} />
          <small>
            Current API parity supports create/list/restore. Dry-run and integrity toggles are advisory UI controls.
          </small>
        </ActionPanel>

        <ActionPanel title={`Available Backups (${backupRows.length})`}>
          {backupsQuery.isLoading ? (
            <div className="module-status loading">Loading backup inventory...</div>
          ) : backupRows.length === 0 ? (
            <div className="module-status loading">No backups found yet. Create one first.</div>
          ) : (
            <>
              <table className="table-lite">
                <thead>
                  <tr>
                    <th>Filename</th>
                    <th>Timestamp</th>
                    <th>Size (MB)</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                  {backupRows.map((backup: any) => (
                    <tr key={backup.filename}>
                      <td>{backup.filename || '-'}</td>
                      <td>{backup.timestamp || '-'}</td>
                      <td>{backup.size || '-'}</td>
                      <td>
                        <button
                          type="button"
                          style={{ fontSize: '0.78em', padding: '4px 8px', marginRight: 6 }}
                          onClick={() => verifyBackupMutation.mutate(backup.filename)}
                          disabled={verifyBackupMutation.isPending}
                          title="Verify backup integrity"
                        >
                          {verifyBackupMutation.isPending ? '…' : 'Verify'}
                        </button>
                        <button
                          type="button"
                          style={{ fontSize: '0.78em', padding: '4px 8px', background: 'var(--color-surface-raised, #f8fafc)', color: '#475569', border: '1px solid #e2e8f0' }}
                          onClick={() => setSelectedFilename(backup.filename)}
                        >
                          Select
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="row-between" style={{ marginTop: 12, justifyContent: 'flex-start' }}>
                <select value={selectedFilename} onChange={(e) => setSelectedFilename(e.target.value)}>
                  <option value="">Select backup filename</option>
                  {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                  {backupRows.map((backup: any) => (
                    <option key={backup.filename} value={backup.filename}>{backup.filename}</option>
                  ))}
                </select>
                <button onClick={applySelectedBackup} disabled={!selectedFilename}>Use In Restore Form</button>
              </div>
            </>
          )}
        </ActionPanel>

        {/* Restore from backup form */}
        <form onSubmit={form.handleSubmit(onSubmit)} className="module-card">
          <h3>Restore from Backup</h3>

          <MutationFeedback error={actionError || restoreBackupMutation.error} />

          <div className="module-grid">
            <FormInput
              form={form}
              name="filename"
              label="Backup Filename"
              placeholder="backup-2024-03-24-1730.tar.gz"
              required
              helperText="Select from available backups in the system"
            />
          </div>

          <FormCheckbox
            form={form}
            name="dryRun"
            label="Perform dry-run (recommended first)"
            helperText="Test restore without making actual changes"
          />

          <FormCheckbox
            form={form}
            name="verifyIntegrity"
            label="Verify backup integrity"
            helperText="Validate backup structure before restoring"
          />

          <FormSubmitButton
            isLoading={restoreBackupMutation.isPending}
            isDisabled={!form.formState.isDirty}
          >
            Restore Backup
          </FormSubmitButton>
        </form>

        {/* Restore result */}
        {Boolean(latestResult) && (
          <ActionPanel title="Restore Result">
            <JsonViewer data={latestResult} />
          </ActionPanel>
        )}

        {/* Best practices */}
        <ActionPanel title="Best Practices">
          <div style={{ fontSize: '13px', color: '#64748b', lineHeight: '1.8' }}>
            <div style={{ marginBottom: '12px', paddingBottom: '12px', borderBottom: '1px solid #e2e8f0' }}>
              <div style={{ fontWeight: '500', color: '#475569' }}>Before Restoring</div>
              <div style={{ marginTop: '4px', marginLeft: '16px' }}>
                <ul style={{ margin: 0, paddingLeft: '20px' }}>
                  <li>Always run a dry-run restore first</li>
                  <li>Verify backup integrity to catch corruption early</li>
                  <li>Ensure sufficient disk space (at least 2x backup size)</li>
                  <li>Notify users of potential downtime</li>
                </ul>
              </div>
            </div>
            <div style={{ marginBottom: '12px', paddingBottom: '12px', borderBottom: '1px solid #e2e8f0' }}>
              <div style={{ fontWeight: '500', color: '#475569' }}>During Restore</div>
              <div style={{ marginTop: '4px', marginLeft: '16px' }}>
                <ul style={{ margin: 0, paddingLeft: '20px' }}>
                  <li>Monitor system resources throughout the operation</li>
                  <li>Keep backup files accessible for recovery</li>
                  <li>Do not interrupt the process once started</li>
                </ul>
              </div>
            </div>
            <div>
              <div style={{ fontWeight: '500', color: '#475569' }}>After Restore</div>
              <div style={{ marginTop: '4px', marginLeft: '16px' }}>
                <ul style={{ margin: 0, paddingLeft: '20px' }}>
                  <li>Verify data integrity with checksums</li>
                  <li>Test critical workflows to ensure functionality</li>
                  <li>Update system documentation with restore timestamp</li>
                  <li>Review audit logs for any anomalies</li>
                </ul>
              </div>
            </div>
          </div>
        </ActionPanel>
      </div>
    </ModulePage>
  );
}
