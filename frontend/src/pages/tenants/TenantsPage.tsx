import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import {
  FormInput,
  FormSubmitButton,
  FormCheckbox,
} from "../../components/forms/FormComponents";
import { extractErrorMessage } from "../../lib/errorUtils";
import { createTenant, getTenants, setTenantStatus } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import { createTenantSchema, type CreateTenantInput } from "../../lib/schemas";

export function TenantsPage() {
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState("");

  const form = useForm<CreateTenantInput>({
    resolver: zodResolver(createTenantSchema) as any,
    defaultValues: {
      name: "",
      slug: "",
      isActive: true,
    },
  });

  const tenantsQuery = useQuery({
    queryKey: queryKeys.tenants,
    queryFn: getTenants,
    staleTime: 90_000,
  });

  const createMutation = useMutation({
    mutationFn: (data: CreateTenantInput) =>
      createTenant({
        name: data.name,
        slug: data.slug || undefined,
        is_active: data.isActive,
      }),
    onSuccess: () => {
      setFeedback("✓ Tenant created successfully");
      form.reset();
      queryClient.invalidateQueries({ queryKey: queryKeys.tenants });
      setTimeout(() => setFeedback(""), 4000);
    },
    onError: (err) => {
      const msg = extractErrorMessage(err);
      setFeedback(`✗ ${msg}`);
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) =>
      setTenantStatus(id, active),
    onSuccess: () => {
      setFeedback("✓ Tenant status updated");
      queryClient.invalidateQueries({ queryKey: queryKeys.tenants });
      setTimeout(() => setFeedback(""), 4000);
    },
    onError: (err) => {
      const msg = extractErrorMessage(err);
      setFeedback(`✗ ${msg}`);
    },
  });

  const onSubmit = (data: CreateTenantInput) => {
    createMutation.mutate(data);
  };

  return (
    <ModulePage
      title="Tenants"
      description="List, create, and status management mapped to tenant APIs."
    >
      <div className="module-grid">
        <form className="module-card" onSubmit={form.handleSubmit(onSubmit as any)}>
          <h3>Create Tenant</h3>

          {feedback && (
            <div className={`feedback-message ${feedback.startsWith("✓") ? "feedback-success" : "feedback-error"}`}>
              {feedback}
            </div>
          )}

          <FormInput
            form={form}
            name="name"
            label="Tenant Name"
            placeholder="Acme Corporation"
            required
            helperText="2-255 characters, unique within system"
          />

          <FormInput
            form={form}
            name="slug"
            label="Slug (optional)"
            placeholder="acme-corp"
            helperText="Lowercase, hyphens only. Auto-generated if empty."
          />

          <FormCheckbox
            form={form}
            name="isActive"
            label="Activate immediately"
            helperText="Inactive tenants cannot authenticate"
          />

          <FormSubmitButton
            isLoading={createMutation.isPending}
            isDisabled={!form.formState.isDirty}
          >
            Create Tenant
          </FormSubmitButton>
        </form>

        <div className="module-card">
          <h3>Tenant List ({tenantsQuery.data?.count ?? 0})</h3>
          <table className="table-lite">
            <thead>
              <tr>
                <th>Name</th>
                <th>Slug</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {(tenantsQuery.data?.tenants || []).map((tenant) => (
                <tr key={tenant.id}>
                  <td>{tenant.name}</td>
                  <td>{tenant.slug}</td>
                  <td>{tenant.is_active ? "✓ Active" : "✗ Inactive"}</td>
                  <td>
                    <button
                      onClick={() =>
                        statusMutation.mutate({ id: tenant.id, active: !tenant.is_active })
                      }
                      disabled={statusMutation.isPending || tenant.slug === "default"}
                      className="button-sm"
                    >
                      {tenant.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </ModulePage>
  );
}
