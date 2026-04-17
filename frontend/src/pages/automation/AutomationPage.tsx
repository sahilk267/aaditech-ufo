import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { StatCard } from "../../components/common/StatCard";
import { JsonViewer } from "../../components/common/JsonViewer";
import { MutationFeedback } from "../../components/common/MutationFeedback";
import {
  FormInput,
  FormSelect,
  FormSubmitButton,
} from "../../components/forms/FormComponents";
import {
  createAutomationWorkflow,
  executeAutomationWorkflow,
  getAutomationServiceStatus,
  getAutomationWorkflows,
  getWorkflowRun,
  getWorkflowRuns,
  getScheduledJobs,
  triggerSelfHealing,
} from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import { createAutomationWorkflowSchema, type CreateAutomationWorkflowInput } from "../../lib/schemas";

export function AutomationPage() {
  const queryClient = useQueryClient();
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [serviceName, setServiceName] = useState("spooler");
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<number | null>(null);

  const form = useForm<CreateAutomationWorkflowInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(createAutomationWorkflowSchema) as any,
    defaultValues: {
      name: "",
      description: "",
      triggerType: "alert",
      triggerMatch: { metric: "cpu_usage" },
      steps: [{ action: "restart_service", service: "spooler", params: {} }],
      isActive: true,
    },
  });

  const selectedAction = form.watch("steps.0.action");

  const workflowsQuery = useQuery({
    queryKey: ["automation", "workflows"],
    queryFn: getAutomationWorkflows,
    staleTime: 60_000,
  });

  const scheduledJobsQuery = useQuery({
    queryKey: ["automation", "scheduled-jobs"],
    queryFn: getScheduledJobs,
    staleTime: 60_000,
  });

  const workflowRunsQuery = useQuery({
    queryKey: queryKeys.workflowRuns,
    queryFn: () => getWorkflowRuns(),
    staleTime: 30_000,
  });

  const selectedWorkflowRunQuery = useQuery({
    queryKey: [...queryKeys.workflowRuns, selectedWorkflowId, "latest-run"],
    queryFn: async () => {
      const runs = await getWorkflowRuns(selectedWorkflowId ? { workflowId: selectedWorkflowId } : undefined);
      const latestRun = Array.isArray(runs.workflow_runs) ? runs.workflow_runs[0] : undefined;
      if (!latestRun?.id) {
        return null;
      }
      const detail = await getWorkflowRun(Number(latestRun.id));
      return detail.workflow_run;
    },
    enabled: selectedWorkflowId != null,
  });

  useEffect(() => {
    const workflows = Array.isArray(workflowsQuery.data?.workflows) ? workflowsQuery.data.workflows : [];
    if (!selectedWorkflowId && workflows.length) {
      const id = Number((workflows[0] as { id?: number }).id);
      if (Number.isFinite(id)) {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setSelectedWorkflowId(id);
      }
    }
  }, [selectedWorkflowId, workflowsQuery.data]);

  const onOk = (data: unknown) => { setLatestResult(data); setActionError(null); };
  const onErr = (err: unknown) => setActionError(err);

  const createWorkflowMutation = useMutation({
    mutationFn: (data: CreateAutomationWorkflowInput) => {
      const firstStep = data.steps[0] || { action: "restart_service", service: "spooler", params: {} };
      const actionType =
        firstStep.action === "restart_service" ? "service_restart" : firstStep.action;

      const actionConfig: Record<string, unknown> =
        actionType === "script_execute"
          ? {
              script_path: String(firstStep.params?.script_path || firstStep.params?.script || ""),
              ...(Array.isArray(firstStep.params?.args)
                ? { args: firstStep.params.args }
                : firstStep.params?.args
                ? { args: String(firstStep.params.args).split(",").map((item) => item.trim()).filter(Boolean) }
                : {}),
            }
          : {
              service_name: firstStep.service,
              ...(firstStep.params || {}),
            };

      return createAutomationWorkflow({
        name: data.name,
        description: data.description,
        trigger_type: data.triggerType,
        trigger_conditions: data.triggerMatch || {},
        action_type: actionType,
        action_config: actionConfig,
        is_active: data.isActive,
      });
    },
    onSuccess: (data) => {
      onOk(data);
      form.reset();
      void queryClient.invalidateQueries({ queryKey: ["automation", "workflows"] });
    },
    onError: onErr,
  });

  const executeWorkflowMutation = useMutation({
    mutationFn: (workflowId: number) => executeAutomationWorkflow(workflowId, { dry_run: true, payload: {} }),
    onSuccess: onOk,
    onError: onErr,
  });

  const serviceStatusMutation = useMutation({ mutationFn: () => getAutomationServiceStatus(serviceName), onSuccess: onOk, onError: onErr });
  const selfHealMutation = useMutation({ mutationFn: () => triggerSelfHealing({ alerts: [], dry_run: true }), onSuccess: onOk, onError: onErr });

  const onSubmit = (data: CreateAutomationWorkflowInput) => {
    createWorkflowMutation.mutate(data);
  };

  const refreshAutomationData = () => {
    void queryClient.invalidateQueries({ queryKey: ["automation", "workflows"] });
    void queryClient.invalidateQueries({ queryKey: ["automation", "scheduled-jobs"] });
    void queryClient.invalidateQueries({ queryKey: queryKeys.workflowRuns });
  };

  const resetAutomationForm = () => {
    form.reset();
    setLatestResult(null);
    setActionError(null);
    setSelectedWorkflowId(null);
  };

  const workflows = Array.isArray(workflowsQuery.data?.workflows) ? workflowsQuery.data.workflows : [];
  const scheduledJobs = Array.isArray(scheduledJobsQuery.data?.scheduled_jobs)
    ? scheduledJobsQuery.data.scheduled_jobs
    : [];
  const workflowRuns = Array.isArray(workflowRunsQuery.data?.workflow_runs) ? workflowRunsQuery.data.workflow_runs : [];

  return (
    <ModulePage
      title="Automation"
      description="Workflow execution, service checks, and self-healing via /api/automation/* endpoints."
      isLoading={workflowsQuery.isLoading || scheduledJobsQuery.isLoading}
      error={workflowsQuery.error || scheduledJobsQuery.error ? "Failed to load automation dashboard." : null}
      actions={
        <div className="module-page-actions-group">
          <button type="button" onClick={refreshAutomationData} disabled={workflowsQuery.isFetching || scheduledJobsQuery.isFetching || workflowRunsQuery.isFetching}>
            Refresh automation state
          </button>
          <button type="button" onClick={resetAutomationForm}>
            Reset form
          </button>
          <button type="button" onClick={() => selfHealMutation.mutate()} disabled={selfHealMutation.isPending}>
            Self-Heal dry run
          </button>
        </div>
      }
    >
      <div className="module-grid">
        <StatCard label="Workflows" value={workflows.length} detail="Tenant automation definitions" />
        <StatCard label="Scheduled Jobs" value={scheduledJobs.length} detail="Recurring workflow executions" />
        <StatCard label="Workflow Runs" value={workflowRuns.length} detail="Durable workflow execution history" />
      </div>

      {workflowsQuery.isLoading || scheduledJobsQuery.isLoading ? (
        <div className="module-status loading">Loading automation workflows and jobs...</div>
      ) : null}
      {workflowsQuery.error || scheduledJobsQuery.error ? (
        <div className="module-status error-text">Failed to load automation workflows or scheduled jobs.</div>
      ) : null}
      {!workflowsQuery.isLoading && !scheduledJobsQuery.isLoading && !workflows.length && !scheduledJobs.length ? (
        <div className="module-status loading">No workflows or scheduled jobs exist yet. Create a workflow to begin automation testing.</div>
      ) : null}

      <form onSubmit={form.handleSubmit(onSubmit)} className="module-card">
        <h3>Create Workflow</h3>
        <div className="module-grid">
          <FormInput
            form={form}
            name="name"
            label="Workflow Name"
            placeholder="Restart Critical Service"
            required
            helperText="2-255 characters"
          />
          <FormInput
            form={form}
            name="description"
            label="Description"
            placeholder="Restart service when high CPU alerts trigger"
            helperText="Optional, up to 2000 characters"
          />
        </div>
        <div className="module-grid" style={{ marginTop: 12 }}>
          <FormSelect
            form={form}
            name="steps.0.action"
            label="Action"
            placeholder="Select an action"
            options={[
              { value: "restart_service", label: "Restart service" },
              { value: "script_execute", label: "Execute script" },
            ]}
            required
            helperText="Choose the action to perform when the workflow triggers."
          />
          {selectedAction === "restart_service" ? (
            <FormInput
              form={form}
              name="steps.0.service"
              label="Service Name"
              placeholder="spooler"
              helperText="Example: spooler or sshd"
            />
          ) : null}
          {selectedAction === "script_execute" ? (
            <>
              <FormInput
                form={form}
                name="steps.0.params.script_path"
                label="Script Path"
                placeholder="/usr/local/bin/check_disk.sh"
                required
                helperText="Allowed script root is configured on the backend."
              />
              <FormInput
                form={form}
                name="steps.0.params.args"
                label="Script Arguments"
                placeholder="arg1,arg2"
                helperText="Comma-separated arguments for the script."
              />
            </>
          ) : null}
        </div>
        <FormSubmitButton
          isLoading={createWorkflowMutation.isPending}
          isDisabled={!form.formState.isDirty}
        >
          Create Workflow
        </FormSubmitButton>
      </form>

      <ActionPanel title="Execution & Service Checks">
        <div className="module-grid">
          <select value={selectedWorkflowId ?? ""} onChange={(e) => setSelectedWorkflowId(Number(e.target.value) || null)}>
            <option value="">Select workflow</option>
            {workflows.map((workflow: unknown) => {
              const id = Number((workflow as { id?: number }).id);
              const name = String((workflow as { name?: string }).name || `Workflow ${id}`);
              return <option key={id} value={id}>{name}</option>;
            })}
          </select>
          <input value={serviceName} onChange={(e) => setServiceName(e.target.value)} placeholder="Service name" />
        </div>
        {!selectedWorkflowId && workflows.length ? (
          <div className="module-status loading" style={{ marginTop: 12 }}>Select a workflow before running the dry-run execution.</div>
        ) : null}
        <div className="row-between" style={{ marginTop: 12 }}>
          <button onClick={() => selectedWorkflowId && executeWorkflowMutation.mutate(selectedWorkflowId)} disabled={!selectedWorkflowId || executeWorkflowMutation.isPending}>Execute (Dry Run)</button>
          <button onClick={() => serviceStatusMutation.mutate()} disabled={serviceStatusMutation.isPending}>Check Service</button>
          <button onClick={() => selfHealMutation.mutate()} disabled={selfHealMutation.isPending}>Self-Heal (Dry Run)</button>
        </div>
        <MutationFeedback error={actionError} />
        {latestResult ? (
          <JsonViewer data={latestResult} title="Last response" />
        ) : (
          <div className="module-status loading">Run a workflow, service check, or self-heal dry run to inspect the latest response.</div>
        )}
      </ActionPanel>

      <ActionPanel title="Workflow Run History">
        {workflowRuns.length ? (
          <JsonViewer data={workflowRuns.slice(0, 10)} title="Recent workflow runs" maxHeight={240} />
        ) : (
          <div className="module-status loading">No workflow runs yet. Execute a workflow to build operator history.</div>
        )}
        {selectedWorkflowRunQuery.data ? (
          <JsonViewer data={selectedWorkflowRunQuery.data} title="Selected workflow latest run detail" maxHeight={260} />
        ) : (
          <div className="module-status loading">Select a workflow to inspect its most recent run detail.</div>
        )}
      </ActionPanel>
    </ModulePage>
  );
}
