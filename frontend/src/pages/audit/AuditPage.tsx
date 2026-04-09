import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { JsonViewer } from "../../components/common/JsonViewer";
import { MutationFeedback } from "../../components/common/MutationFeedback";
import {
  FormInput,
  FormSubmitButton,
} from "../../components/forms/FormComponents";
import { getAuditEvents, getOperationsTimeline, openEventStream } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import { auditFilterSchema, type AuditFilterInput } from "../../lib/schemas";
import type { OperationsTimelineStreamSnapshot } from "../../types/api";

export function AuditPage() {
  const queryClient = useQueryClient();
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [streamStatus, setStreamStatus] = useState<"connecting" | "connected" | "reconnecting" | "unsupported">("connecting");
  const timelineQuery = useQuery({
    queryKey: queryKeys.operationsTimeline,
    queryFn: () => getOperationsTimeline(25),
    staleTime: 30_000,
  });

  const form = useForm<AuditFilterInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(auditFilterSchema) as any,
    defaultValues: {
      eventType: "",
      searchText: "",
      userId: undefined,
      dateFrom: "",
      dateTo: "",
      limit: 50,
    },
  });

  const auditQueryMutation = useMutation({
    mutationFn: (filters: AuditFilterInput) =>
      getAuditEvents({
        offset: 0,
        limit: filters.limit,
        eventType: filters.eventType || undefined,
        userId: filters.userId,
        searchText: filters.searchText || undefined,
        dateFrom: filters.dateFrom || undefined,
        dateTo: filters.dateTo || undefined,
      }),
    onSuccess: (data) => {
      setLatestResult(data);
      setActionError(null);
    },
    onError: (err) => {
      setActionError(err);
    },
  });

  const onSubmit = (data: AuditFilterInput) => {
    auditQueryMutation.mutate(data);
  };

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.EventSource === "undefined") {
      setStreamStatus("unsupported");
      return undefined;
    }

    const stream = openEventStream<OperationsTimelineStreamSnapshot>("/api/operations/timeline/stream?limit=25", {
      event: "operations.timeline.snapshot",
      onOpen: () => setStreamStatus("connected"),
      onError: () => setStreamStatus("reconnecting"),
      onMessage: (payload) => {
        setStreamStatus("connected");
        queryClient.setQueryData(queryKeys.operationsTimeline, {
          status: "success",
          count: payload.count,
          timeline: payload.timeline,
        });
      },
    });

    return () => {
      stream.close();
    };
  }, [queryClient]);

  return (
    <ModulePage
      title="Audit & Compliance"
      description="Filter and query audit activity using /api/audit-events with client-side validated filters."
    >
      <form onSubmit={form.handleSubmit(onSubmit)} className="module-card">
        <h3 className="action-panel-title">Audit Filters</h3>
        <div className="module-grid">
          <FormInput
            form={form}
            name="eventType"
            label="Event Type"
            placeholder="e.g. user.login"
            helperText="Optional event category filter"
          />
          <FormInput
            form={form}
            name="userId"
            label="Actor User ID"
            type="number"
            placeholder="e.g. 42"
            helperText="Optional actor filter"
          />
          <FormInput
            form={form}
            name="dateFrom"
            label="Date From"
            type="date"
            helperText="Optional start date"
          />
          <FormInput
            form={form}
            name="dateTo"
            label="Date To"
            type="date"
            helperText="Optional end date"
          />
          <FormInput
            form={form}
            name="searchText"
            label="Search Text"
            placeholder="email, hostname, action details..."
            helperText="Full-text style search input"
          />
          <FormInput
            form={form}
            name="limit"
            label="Result Limit"
            type="number"
            min={10}
            max={1000}
            step={10}
            helperText="10 to 1000"
          />
        </div>

        <FormSubmitButton
          isLoading={auditQueryMutation.isPending}
          isDisabled={!form.formState.isDirty}
        >
          Query Audit Events
        </FormSubmitButton>
      </form>

      <ActionPanel title="Audit Query Result" style={{ marginTop: 12 }}>
        <MutationFeedback error={actionError} />
        {latestResult ? (
          <JsonViewer data={latestResult} title="/api/audit-events response" />
        ) : (
          <div className="module-status loading">Run an audit query to load matching events here.</div>
        )}
      </ActionPanel>

      <ActionPanel title="Operations Timeline" style={{ marginTop: 12 }}>
        <div className="module-status loading" style={{ marginBottom: 12 }}>
          Live feed status: {streamStatus === "unsupported" ? "polling fallback only" : streamStatus}
        </div>
        {timelineQuery.data?.timeline?.length ? (
          <JsonViewer data={timelineQuery.data.timeline} title="/api/operations/timeline response" />
        ) : (
          <div className="module-status loading">Merged audit, workflow, delivery, and incident timeline will appear here.</div>
        )}
      </ActionPanel>
    </ModulePage>
  );
}
