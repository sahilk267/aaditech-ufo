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
  FormSubmitButton,
} from "../../components/forms/FormComponents";
import {
  createAutomationWorkflow,
  executeAutomationWorkflow,
  getAutomationServiceStatus,
  getAutomationWorkflows,
  getScheduledJobs,
  triggerSelfHealing,
} from "../../lib/api";
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
      steps: [{ action: "restart_service", service: "spooler" }],
      isActive: true,
    },
  });

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
      const firstStep = data.steps[0] || { action: "restart_service" };
      const actionType =
        firstStep.action === "restart_service" ? "service_restart" : firstStep.action;

      return createAutomationWorkflow({
        name: data.name,
        description: data.description,
        trigger_type: data.triggerType,
        trigger_conditions: data.triggerMatch || {},
        action_type: actionType,
        action_config: {
          service_name: firstStep.service,
          ...(firstStep.params || {}),
        },
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

  const workflows = Array.isArray(workflowsQuery.data?.workflows) ? workflowsQuery.data.workflows : [];
  const scheduledJobs = Array.isArray(scheduledJobsQuery.data?.scheduled_jobs)
    ? scheduledJobsQuery.data.scheduled_jobs
    : [];

  return (
    <ModulePage
      title="Automation"
      description="Workflow execution, service checks, and self-healing via /api/automation/* endpoints."
    >
      <div className="module-grid">
        <StatCard label="Workflows" value={workflows.length} detail="Tenant automation definitions" />
        <StatCard label="Scheduled Jobs" value={scheduledJobs.length} detail="Recurring workflow executions" />
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
    </ModulePage>
  );
}
