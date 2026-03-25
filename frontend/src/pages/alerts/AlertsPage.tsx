import { useState } from "react";
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
  createAlertRule,
  dispatchAlerts,
  evaluateAlerts,
  getAlertRules,
  getAlertSilences,
  prioritizeAlerts,
} from "../../lib/api";
import type { AlertRule } from "../../types/api";
import { queryKeys } from "../../lib/queryKeys";
import { createAlertRuleSchema, type CreateAlertRuleInput } from "../../lib/schemas";

export function AlertsPage() {
  const queryClient = useQueryClient();
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  const form = useForm<CreateAlertRuleInput>({
    resolver: zodResolver(createAlertRuleSchema) as any,
    defaultValues: {
      name: "",
      metric: "",
      operator: ">",
      threshold: 90,
      severity: "critical",
      description: "",
    },
  });

  const rulesQuery = useQuery({
    queryKey: queryKeys.alerts,
    queryFn: getAlertRules,
    staleTime: 60_000,
  });

  const silencesQuery = useQuery({
    queryKey: ["alerts", "silences"],
    queryFn: getAlertSilences,
    staleTime: 60_000,
  });

  const onOk = (data: unknown) => { setLatestResult(data); setActionError(null); };
  const onErr = (err: unknown) => setActionError(err);

  const createRuleMutation = useMutation({
    mutationFn: (data: CreateAlertRuleInput) =>
      createAlertRule({
        name: data.name,
        metric: data.metric,
        operator: data.operator,
        threshold: data.threshold,
        severity: data.severity,
      }),
    onSuccess: (data) => {
      onOk(data);
      form.reset();
      void queryClient.invalidateQueries({ queryKey: queryKeys.alerts });
    },
    onError: onErr,
  });

  const evaluateMutation = useMutation({ mutationFn: () => evaluateAlerts({}), onSuccess: onOk, onError: onErr });

  const dispatchMutation = useMutation({
    mutationFn: () => {
      const alerts = Array.isArray((latestResult as { alerts?: unknown[] } | null)?.alerts)
        ? ((latestResult as { alerts: unknown[] }).alerts || [])
        : [];
      return dispatchAlerts({ alerts, channels: ["email", "webhook"], deduplicate: true });
    },
    onSuccess: onOk,
    onError: onErr,
  });

  const prioritizeMutation = useMutation({
    mutationFn: () => {
      const alerts = Array.isArray((latestResult as { alerts?: unknown[] } | null)?.alerts)
        ? ((latestResult as { alerts: unknown[] }).alerts || [])
        : [];
      return prioritizeAlerts({ alerts: alerts as AlertRule[], top_n: 10 });
    },
    onSuccess: onOk,
    onError: onErr,
  });

  const onSubmit = (data: CreateAlertRuleInput) => {
    createRuleMutation.mutate(data);
  };

  const rules = Array.isArray(rulesQuery.data?.rules) ? rulesQuery.data.rules : [];
  const silences = Array.isArray(silencesQuery.data?.silences) ? silencesQuery.data.silences : [];

  return (
    <ModulePage
      title="Alerts"
      description="Live rule management and evaluation flow using /api/alerts/* endpoints."
    >
      <div className="module-grid">
        <StatCard label="Rules" value={rules.length} detail="Configured alert thresholds" />
        <StatCard label="Silences" value={silences.length} detail="Active suppression windows" />
      </div>

      <form onSubmit={form.handleSubmit(onSubmit as any)} className="module-card">
        <h3>Create Alert Rule</h3>
        
        <div className="module-grid">
          <FormInput
            form={form}
            name="name"
            label="Rule Name"
            placeholder="CPU Critical Alert"
            required
            helperText="2-255 characters"
          />
          <FormInput
            form={form}
            name="metric"
            label="Metric"
            placeholder="cpu_usage"
            required
            helperText="System metric to monitor"
          />
          <FormSelect
            form={form}
            name="operator"
            label="Operator"
            required
            options={[
              { value: ">", label: "Greater than (>)" },
              { value: "<", label: "Less than (<)" },
              { value: ">=", label: "Greater or equal (>=)" },
              { value: "<=", label: "Less or equal (<=)" },
              { value: "==", label: "Equal (==)" },
              { value: "!=", label: "Not equal (!=)" },
            ]}
          />
          <FormInput
            form={form}
            name="threshold"
            label="Threshold"
            type="number"
            placeholder="90"
            required
            helperText="Numeric threshold value"
          />
          <FormSelect
            form={form}
            name="severity"
            label="Severity"
            required
            options={[
              { value: "info", label: "Info" },
              { value: "warning", label: "Warning" },
              { value: "critical", label: "Critical" },
            ]}
          />
          <FormInput
            form={form}
            name="description"
            label="Description (optional)"
            placeholder="When CPU exceeds 90%, trigger alert"
            helperText="Additional context for the rule"
          />
        </div>

        <FormSubmitButton
          isLoading={createRuleMutation.isPending}
          isDisabled={!form.formState.isDirty}
        >
          Create Rule
        </FormSubmitButton>
      </form>

      <ActionPanel title="Operations">
        <div className="row-between">
          <button onClick={() => evaluateMutation.mutate()} disabled={evaluateMutation.isPending}>Evaluate Alerts</button>
          <button onClick={() => prioritizeMutation.mutate()} disabled={prioritizeMutation.isPending}>Prioritize</button>
          <button onClick={() => dispatchMutation.mutate()} disabled={dispatchMutation.isPending}>Dispatch</button>
        </div>
        <MutationFeedback error={actionError} />
        <JsonViewer data={latestResult} title="Last response" />
      </ActionPanel>
    </ModulePage>
  );
}
