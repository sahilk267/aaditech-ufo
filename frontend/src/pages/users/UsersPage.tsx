import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { JsonViewer } from "../../components/common/JsonViewer";
import {
  FormInput,
  FormSubmitButton,
} from "../../components/forms/FormComponents";
import { registerUser } from "../../lib/api";
import { fetchMe } from "../../lib/auth";
import { queryKeys } from "../../lib/queryKeys";
import { createUserSchema, type CreateUserInput } from "../../lib/schemas";

export function UsersPage() {
  const queryClient = useQueryClient();
  const [latestResult, setLatestResult] = useState<unknown>(null);

  const form = useForm<CreateUserInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(createUserSchema) as any,
    defaultValues: {
      email: "",
      fullName: "",
      password: "",
    },
  });

  const meQuery = useQuery({ queryKey: queryKeys.me, queryFn: fetchMe, staleTime: 60_000 });

  const createUserMutation = useMutation({
    mutationFn: (data: CreateUserInput) =>
      registerUser({
        email: data.email,
        full_name: data.fullName,
        password: data.password,
      }),
    onSuccess: (data) => {
      setLatestResult(data);
      form.reset();
      void queryClient.invalidateQueries({ queryKey: queryKeys.me });
    },
    onError: (err) => {
      form.setError("root", { message: String(err) });
    },
  });

  const onSubmit = (data: CreateUserInput) => {
    createUserMutation.mutate(data);
  };

  return (
    <ModulePage
      title="Users"
      description="Tenant-scoped user provisioning using /api/auth/register with current identity context from /api/auth/me."
    >
      <ActionPanel title="Current Session User">
        <JsonViewer data={meQuery.data} />
      </ActionPanel>

      <form onSubmit={form.handleSubmit(onSubmit)} className="module-card" style={{ marginTop: 12 }}>
        <h3 className="action-panel-title">Create User</h3>
        
        {form.formState.errors.root && (
          <div className="form-error-banner">
            {form.formState.errors.root.message}
          </div>
        )}

        <div className="module-grid">
          <FormInput
            form={form}
            name="email"
            label="Email Address"
            type="email"
            placeholder="user@example.com"
            required
            helperText="User's email for authentication"
          />
          <FormInput
            form={form}
            name="fullName"
            label="Full Name"
            placeholder="John Doe"
            required
            helperText="User's full name (2-255 characters)"
          />
          <FormInput
            form={form}
            name="password"
            label="Password"
            type="password"
            placeholder="Enter secure password"
            required
            helperText="Minimum 8 chars, uppercase, number, special char"
          />
        </div>

        <FormSubmitButton
          isLoading={createUserMutation.isPending}
          isDisabled={!form.formState.isDirty}
        >
          Create User
        </FormSubmitButton>

        {Boolean(latestResult) && (
          <ActionPanel title="New User Created" style={{ marginTop: 16 }}>
            <JsonViewer data={latestResult} />
          </ActionPanel>
        )}
      </form>
    </ModulePage>
  );
}
