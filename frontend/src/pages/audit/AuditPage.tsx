import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { JsonViewer } from "../../components/common/JsonViewer";
import { MutationFeedback } from "../../components/common/MutationFeedback";
import {
  FormInput,
  FormSubmitButton,
} from "../../components/forms/FormComponents";
import { getAuditEvents } from "../../lib/api";
import { auditFilterSchema, type AuditFilterInput } from "../../lib/schemas";

export function AuditPage() {
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  const form = useForm<AuditFilterInput>({
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

  return (
    <ModulePage
      title="Audit & Compliance"
      description="Filter and query audit activity using /api/audit-events with client-side validated filters."
    >
      <form onSubmit={form.handleSubmit(onSubmit as any)} className="module-card">
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
        <JsonViewer data={latestResult} title="/api/audit-events response" />
      </ActionPanel>
    </ModulePage>
  );
}
