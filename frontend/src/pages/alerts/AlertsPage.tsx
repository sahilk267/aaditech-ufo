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
  createAlertRule,
  createIncidentComment,
  dispatchAlerts,
  evaluateAlerts,
  getAlertDelivery,
  getAlertDeliveryHistory,
  getIncident,
  getIncidentComments,
  getAlertRules,
  getAlertSilences,
  getIncidents,
  getTenantControls,
  openEventStream,
  prioritizeAlerts,
  redeliverAlertDelivery,
  updateIncident,
} from "../../lib/api";
import type { AlertRule, AlertsStreamSnapshot } from "../../types/api";
import { queryKeys } from "../../lib/queryKeys";
import { createAlertRuleSchema, type CreateAlertRuleInput } from "../../lib/schemas";

export function AlertsPage() {
  const queryClient = useQueryClient();
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [selectedDeliveryId, setSelectedDeliveryId] = useState<number | null>(null);
  const [selectedIncidentId, setSelectedIncidentId] = useState<number | null>(null);
  const [incidentCommentBody, setIncidentCommentBody] = useState("");
  const [streamStatus, setStreamStatus] = useState<"connecting" | "connected" | "reconnecting" | "unsupported">("connecting");

  const form = useForm<CreateAlertRuleInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
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

  const deliveryHistoryQuery = useQuery({
    queryKey: queryKeys.alertDeliveryHistory,
    queryFn: () => getAlertDeliveryHistory(),
    staleTime: 30_000,
  });

  const incidentsQuery = useQuery({
    queryKey: queryKeys.incidents,
    queryFn: () => getIncidents(),
    staleTime: 30_000,
  });

  const tenantControlsQuery = useQuery({
    queryKey: queryKeys.tenantControls,
    queryFn: getTenantControls,
    staleTime: 60_000,
  });

  const selectedDeliveryQuery = useQuery({
    queryKey: [...queryKeys.alertDeliveryHistory, selectedDeliveryId],
    queryFn: () => getAlertDelivery(selectedDeliveryId as number),
    enabled: selectedDeliveryId != null,
  });

  const selectedIncidentQuery = useQuery({
    queryKey: [...queryKeys.incidents, selectedIncidentId],
    queryFn: () => getIncident(selectedIncidentId as number),
    enabled: selectedIncidentId != null,
  });

  const incidentCommentsQuery = useQuery({
    queryKey: selectedIncidentId ? queryKeys.incidentComments(selectedIncidentId) : ["incidents", "comments", "none"],
    queryFn: () => getIncidentComments(selectedIncidentId as number),
    enabled: selectedIncidentId != null,
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

  const redeliverMutation = useMutation({
    mutationFn: (deliveryId: number) => redeliverAlertDelivery(deliveryId),
    onSuccess: async (data) => {
      onOk(data);
      await queryClient.invalidateQueries({ queryKey: queryKeys.alertDeliveryHistory });
    },
    onError: onErr,
  });

  const incidentUpdateMutation = useMutation({
    mutationFn: (payload: { incidentId: number; status: "acknowledged" | "resolved" }) =>
      updateIncident(payload.incidentId, {
        status: payload.status,
        resolution_summary: payload.status === "resolved" ? "Resolved from Alerts console." : undefined,
      }),
    onSuccess: async (data) => {
      onOk(data);
      await queryClient.invalidateQueries({ queryKey: queryKeys.incidents });
    },
    onError: onErr,
  });

  const incidentCommentMutation = useMutation({
    mutationFn: (payload: { incidentId: number; body: string }) =>
      createIncidentComment(payload.incidentId, { body: payload.body, comment_type: "note" }),
    onSuccess: async (data) => {
      onOk(data);
      setIncidentCommentBody("");
      if (selectedIncidentId != null) {
        await queryClient.invalidateQueries({ queryKey: queryKeys.incidentComments(selectedIncidentId) });
      }
    },
    onError: onErr,
  });

  const onSubmit = (data: CreateAlertRuleInput) => {
    createRuleMutation.mutate(data);
  };

  const refreshAlertsData = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.alerts });
    void queryClient.invalidateQueries({ queryKey: ["alerts", "silences"] });
    void queryClient.invalidateQueries({ queryKey: queryKeys.alertDeliveryHistory });
    void queryClient.invalidateQueries({ queryKey: queryKeys.incidents });
    void queryClient.invalidateQueries({ queryKey: queryKeys.tenantControls });
  };

  const resetAlertsView = () => {
    setLatestResult(null);
    setActionError(null);
    setSelectedDeliveryId(null);
    setSelectedIncidentId(null);
    setIncidentCommentBody("");
  };

  const rules = Array.isArray(rulesQuery.data?.rules) ? rulesQuery.data.rules : [];
  const silences = Array.isArray(silencesQuery.data?.silences) ? silencesQuery.data.silences : [];
  const deliveries = Array.isArray(deliveryHistoryQuery.data?.deliveries) ? deliveryHistoryQuery.data.deliveries : [];
  const incidents = Array.isArray(incidentsQuery.data?.incidents) ? incidentsQuery.data.incidents : [];
  const caseManagementEnabled =
    tenantControlsQuery.data?.tenant_controls?.effective?.entitlements?.case_management_v1?.enabled !== false &&
    tenantControlsQuery.data?.tenant_controls?.effective?.feature_flags?.incident_case_management_v1?.enabled !== false;

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.EventSource === "undefined") {
      setStreamStatus("unsupported");
      return undefined;
    }

    const stream = openEventStream<AlertsStreamSnapshot>("/api/alerts/stream?limit=10", {
      event: "alerts.snapshot",
      onOpen: () => setStreamStatus("connected"),
      onError: () => setStreamStatus("reconnecting"),
      onMessage: (payload) => {
        setStreamStatus("connected");
        queryClient.setQueryData(queryKeys.alertDeliveryHistory, {
          status: "success",
          count: payload.deliveries.length,
          total: payload.deliveries.length,
          pages: 1,
          page: 1,
          per_page: payload.deliveries.length || 10,
          deliveries: payload.deliveries,
        });
        queryClient.setQueryData(queryKeys.incidents, {
          status: "success",
          count: payload.incidents.length,
          total: payload.incidents.length,
          pages: 1,
          page: 1,
          per_page: payload.incidents.length || 10,
          incidents: payload.incidents,
        });
      },
    });

    return () => {
      stream.close();
    };
  }, [queryClient]);

  return (
    <ModulePage
      title="Alerts"
      description="Live rule management and evaluation flow using /api/alerts/* endpoints."
      actions={
        <>
          <button type="button" onClick={refreshAlertsData}>
            Refresh alerts
          </button>
          <button type="button" onClick={resetAlertsView}>
            Reset view
          </button>
        </>
      }
    >
      <div className="module-grid">
        <StatCard label="Rules" value={rules.length} detail="Configured alert thresholds" />
        <StatCard label="Silences" value={silences.length} detail="Active suppression windows" />
        <StatCard label="Deliveries" value={deliveries.length} detail="Notification history records" />
        <StatCard label="Incidents" value={incidents.length} detail="Durable correlated incident records" />
      </div>
      <div className="module-status loading">
        Live feed status: {streamStatus === "unsupported" ? "polling fallback only" : streamStatus}
      </div>

      {rulesQuery.isLoading || silencesQuery.isLoading ? (
        <div className="module-status loading">Loading alert configuration...</div>
      ) : null}
      {rulesQuery.error || silencesQuery.error ? (
        <div className="module-status error-text">Failed to load alert rules or silences.</div>
      ) : null}
      {!rulesQuery.isLoading && !silencesQuery.isLoading && !rules.length && !silences.length ? (
        <div className="module-status loading">No alert rules or silences exist yet. Create a rule to start the flow.</div>
      ) : null}

      <form onSubmit={form.handleSubmit(onSubmit)} className="module-card">
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
        {latestResult ? (
          <JsonViewer data={latestResult} title="Last response" />
        ) : (
          <div className="module-status loading">Run evaluate, prioritize, or dispatch to see the latest alert response here.</div>
        )}
      </ActionPanel>

      <ActionPanel title="Delivery History & Incident Actions">
        <div className="module-grid">
          <div>
            <label htmlFor="delivery-history-select">Delivery record</label>
            <select
              id="delivery-history-select"
              value={selectedDeliveryId ?? ""}
              onChange={(e) => setSelectedDeliveryId(Number(e.target.value) || null)}
            >
              <option value="">Select delivery</option>
              {deliveries.map((delivery) => (
                <option key={delivery.id} value={delivery.id}>
                  #{delivery.id} {delivery.status}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="incident-select">Incident</label>
            <select
              id="incident-select"
              value={selectedIncidentId ?? ""}
              onChange={(e) => setSelectedIncidentId(Number(e.target.value) || null)}
            >
              <option value="">Select incident</option>
              {incidents.map((incident) => (
                <option key={incident.id} value={incident.id}>
                  #{incident.id} {incident.title}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="row-between" style={{ marginTop: 12 }}>
          <button onClick={() => selectedDeliveryId && redeliverMutation.mutate(selectedDeliveryId)} disabled={!selectedDeliveryId || redeliverMutation.isPending}>
            Redeliver Selected
          </button>
          <button onClick={() => selectedIncidentId && incidentUpdateMutation.mutate({ incidentId: selectedIncidentId, status: "acknowledged" })} disabled={!selectedIncidentId || incidentUpdateMutation.isPending}>
            Acknowledge Incident
          </button>
          <button onClick={() => selectedIncidentId && incidentUpdateMutation.mutate({ incidentId: selectedIncidentId, status: "resolved" })} disabled={!selectedIncidentId || incidentUpdateMutation.isPending}>
            Resolve Incident
          </button>
        </div>
        {selectedDeliveryQuery.data?.delivery ? (
          <JsonViewer data={selectedDeliveryQuery.data.delivery} title="Selected delivery detail" />
        ) : (
          <div className="module-status loading">Select a delivery record to inspect stored channels, failures, and snapshot details.</div>
        )}
        {incidents.length ? (
          <JsonViewer data={incidents.slice(0, 5)} title="Recent incidents" maxHeight={220} />
        ) : (
          <div className="module-status loading">No durable incidents yet. Correlated alert activity will appear here.</div>
        )}
        {selectedIncidentQuery.data?.incident ? (
          <JsonViewer data={selectedIncidentQuery.data.incident} title="Selected incident detail" maxHeight={220} />
        ) : null}
        {selectedIncidentId && caseManagementEnabled ? (
          <div className="module-card" style={{ marginTop: 12 }}>
            <h3>Case Notes</h3>
            <textarea
              value={incidentCommentBody}
              onChange={(e) => setIncidentCommentBody(e.target.value)}
              placeholder="Add investigation note, handoff context, or resolution evidence..."
              rows={4}
            />
            <div className="row-between" style={{ marginTop: 12 }}>
              <button
                onClick={() => selectedIncidentId && incidentCommentMutation.mutate({ incidentId: selectedIncidentId, body: incidentCommentBody })}
                disabled={!selectedIncidentId || !incidentCommentBody.trim() || incidentCommentMutation.isPending}
              >
                Add Case Note
              </button>
            </div>
            {incidentCommentsQuery.data?.comments?.length ? (
              <JsonViewer data={incidentCommentsQuery.data.comments} title="Incident case comments" maxHeight={220} />
            ) : (
              <div className="module-status loading">No case notes yet for this incident.</div>
            )}
          </div>
        ) : selectedIncidentId ? (
          <div className="module-status loading">Case notes are disabled for this tenant by current controls.</div>
        ) : null}
      </ActionPanel>
    </ModulePage>
  );
}
