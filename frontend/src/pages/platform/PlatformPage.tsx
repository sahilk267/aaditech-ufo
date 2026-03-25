import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { JsonViewer } from "../../components/common/JsonViewer";
import { MutationFeedback } from "../../components/common/MutationFeedback";
import {
  FormCheckbox,
  FormInput,
  FormSelect,
  FormSubmitButton,
} from "../../components/forms/FormComponents";
import {
  getCacheStatus,
  optimizeDatabase,
  queueMaintenanceJob,
} from "../../lib/api";
import {
  cacheManagementSchema,
  databaseOptimizeSchema,
  type CacheManagementInput,
  type DatabaseOptimizeInput,
} from "../../lib/schemas";

export function PlatformPage() {
  const queryClient = useQueryClient();
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  const cacheStatusQuery = useQuery({
    queryKey: ["platform", "cache"],
    queryFn: getCacheStatus,
    staleTime: 30_000,
  });

  const dbForm = useForm<DatabaseOptimizeInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(databaseOptimizeSchema) as any,
    defaultValues: {
      dryRun: true,
      analyzeStatistics: true,
      rebuildIndexes: false,
      vacuumFull: false,
    },
  });

  const cacheForm = useForm<CacheManagementInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(cacheManagementSchema) as any,
    defaultValues: {
      action: "stats",
      keyPattern: "",
    },
  });

  const onOk = (data: unknown) => {
    setLatestResult(data);
    setActionError(null);
  };

  const onErr = (err: unknown) => {
    setActionError(err);
  };

  const optimizeMutation = useMutation({
    mutationFn: (payload: DatabaseOptimizeInput) =>
      optimizeDatabase({
        dry_run: payload.dryRun,
        analyze_statistics: payload.analyzeStatistics,
        rebuild_indexes: payload.rebuildIndexes,
        vacuum_full: payload.vacuumFull,
      }),
    onSuccess: onOk,
    onError: onErr,
  });

  const settingsMutation = useMutation({
    mutationFn: async (payload: CacheManagementInput) => {
      if (payload.action === "stats") {
        return getCacheStatus();
      }

      const job =
        payload.keyPattern && payload.keyPattern.trim().length
          ? `cache_${payload.action}:${payload.keyPattern.trim()}`
          : `cache_${payload.action}`;
      return queueMaintenanceJob(job);
    },
    onSuccess: async (data) => {
      onOk(data);
      await queryClient.invalidateQueries({ queryKey: ["platform", "cache"] });
    },
    onError: onErr,
  });

  const onSubmitDbOptimize = (data: DatabaseOptimizeInput) => {
    optimizeMutation.mutate(data);
  };

  const onSubmitSystemSettings = (data: CacheManagementInput) => {
    settingsMutation.mutate(data);
  };

  return (
    <ModulePage
      title="Platform Operations"
      description="System settings and maintenance controls with validated forms for cache and database operations."
      isLoading={cacheStatusQuery.isLoading}
      error={cacheStatusQuery.isError ? "Failed to load cache status." : null}
    >
      <ActionPanel title="Cache Status">
        <JsonViewer data={cacheStatusQuery.data} />
      </ActionPanel>

      <form
        onSubmit={cacheForm.handleSubmit(onSubmitSystemSettings)}
        className="module-card"
        style={{ marginTop: 12 }}
      >
        <h3 className="action-panel-title">System Settings: Cache Actions</h3>
        <div className="module-grid">
          <FormSelect
            form={cacheForm}
            name="action"
            label="Action"
            required
            options={[
              { value: "stats", label: "Refresh Cache Status" },
              { value: "clear", label: "Clear Cache" },
              { value: "warm", label: "Warm Cache" },
            ]}
          />
          <FormInput
            form={cacheForm}
            name="keyPattern"
            label="Key Pattern (optional)"
            placeholder="tenant:*"
            helperText="Pattern to target cache subsets"
          />
        </div>

        <FormSubmitButton
          isLoading={settingsMutation.isPending}
          isDisabled={!cacheForm.formState.isDirty}
        >
          Apply Setting
        </FormSubmitButton>
      </form>

      <form
        onSubmit={dbForm.handleSubmit(onSubmitDbOptimize)}
        className="module-card"
        style={{ marginTop: 12 }}
      >
        <h3 className="action-panel-title">Database Optimization</h3>
        <div className="module-grid">
          <FormCheckbox
            form={dbForm}
            name="dryRun"
            label="Dry-run mode"
            helperText="Simulate optimization without destructive changes"
          />
          <FormCheckbox
            form={dbForm}
            name="analyzeStatistics"
            label="Analyze table statistics"
          />
          <FormCheckbox
            form={dbForm}
            name="rebuildIndexes"
            label="Rebuild indexes"
          />
          <FormCheckbox
            form={dbForm}
            name="vacuumFull"
            label="VACUUM FULL"
            helperText="May lock tables on some databases"
          />
        </div>

        <FormSubmitButton
          isLoading={optimizeMutation.isPending}
          isDisabled={!dbForm.formState.isDirty}
        >
          Run Optimization
        </FormSubmitButton>
      </form>

      <ActionPanel title="Operation Result" style={{ marginTop: 12 }}>
        <MutationFeedback error={actionError} />
        <JsonViewer data={latestResult} title="Last response" />
      </ActionPanel>
    </ModulePage>
  );
}
