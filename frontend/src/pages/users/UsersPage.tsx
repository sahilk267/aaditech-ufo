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
import { getUsers, registerUser, revokeUserSessions, updateUser } from "../../lib/api";
import { fetchMe } from "../../lib/auth";
import { queryKeys } from "../../lib/queryKeys";
import { createUserSchema, type CreateUserInput } from "../../lib/schemas";
import type { User } from "../../types/api";

export function UsersPage() {
  const queryClient = useQueryClient();
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editedFullName, setEditedFullName] = useState("");

  const form = useForm<CreateUserInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(createUserSchema) as any,
    defaultValues: {
      email: "",
      fullName: "",
      password: "",
    },
  });

  const usersQuery = useQuery({
    queryKey: queryKeys.users,
    queryFn: getUsers,
    staleTime: 60_000,
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
      void queryClient.invalidateQueries({ queryKey: queryKeys.users });
      void queryClient.invalidateQueries({ queryKey: queryKeys.me });
    },
    onError: (err) => {
      form.setError("root", { message: String(err) });
    },
  });

  const revokeSessionsMutation = useMutation({
    mutationFn: (userId: number) => revokeUserSessions(userId),
    onSuccess: (data) => {
      setLatestResult(data);
      void queryClient.invalidateQueries({ queryKey: queryKeys.users });
    },
    onError: (err) => {
      form.setError("root", { message: String(err) });
    },
  });

  const updateUserMutation = useMutation({
    mutationFn: (payload: { id: number; full_name: string }) => updateUser(payload.id, { full_name: payload.full_name }),
    onSuccess: () => {
      if (editingUser) {
        setLatestResult({ message: "User updated", user: { ...editingUser, full_name: editedFullName } });
      }
      setEditingUser(null);
      setEditedFullName("");
      void queryClient.invalidateQueries({ queryKey: queryKeys.users });
    },
    onError: (err) => {
      form.setError("root", { message: String(err) });
    },
  });

  const onSubmit = (data: CreateUserInput) => {
    createUserMutation.mutate(data);
  };

  const onBeginEdit = (user: User) => {
    setEditingUser(user);
    setEditedFullName(user.full_name ?? "");
  };

  const onSaveEdit = () => {
    if (!editingUser) return;
    updateUserMutation.mutate({ id: editingUser.id, full_name: editedFullName });
  };

  const refreshUsers = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.users });
  };

  const resetUserForm = () => {
    form.reset();
    setLatestResult(null);
    setEditingUser(null);
    setEditedFullName("");
  };

  return (
    <ModulePage
      title="Users"
      description="Tenant-scoped user provisioning and management using /api/users."
      actions={
        <>
          <button type="button" onClick={refreshUsers} disabled={usersQuery.isFetching}>
            Refresh users
          </button>
          <button type="button" onClick={resetUserForm}>
            Reset form
          </button>
        </>
      }
    >
      <ActionPanel title="Current Session User">
        {meQuery.isLoading ? (
          <div className="module-status loading">Loading current session user...</div>
        ) : meQuery.error ? (
          <div className="module-status error-text">Failed to load current session user.</div>
        ) : meQuery.data ? (
          <JsonViewer data={meQuery.data} />
        ) : (
          <div className="module-status loading">No current session user payload is available.</div>
        )}
      </ActionPanel>

      <div className="panel" style={{ marginTop: 16 }}>
        <h2>User Directory</h2>
        {usersQuery.isLoading ? (
          <div className="module-status loading">Loading users...</div>
        ) : usersQuery.error ? (
          <div className="module-status error-text">Failed to load users list.</div>
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Email</th>
                  <th>Full Name</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {usersQuery.data?.users?.map((user: User) => (
                  <tr key={user.id}>
                    <td>{user.id}</td>
                    <td>{user.email}</td>
                    <td>{user.full_name || "-"}</td>
                    <td style={{ display: "flex", gap: 6 }}>
                      <button className="button button--secondary" type="button" onClick={() => onBeginEdit(user)}>
                        Edit
                      </button>
                      <button
                        className="button button--secondary"
                        type="button"
                        style={{ fontSize: "0.82em", color: "#b45309", border: "1px solid #fde68a" }}
                        onClick={() => revokeSessionsMutation.mutate(user.id)}
                        disabled={revokeSessionsMutation.isPending}
                        title="Force logout — revoke all active sessions for this user"
                      >
                        Revoke sessions
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {editingUser ? (
        <div className="module-card" style={{ marginTop: 16 }}>
          <h3>Edit User</h3>
          <div className="form-field">
            <label className="form-label">Email</label>
            <input value={editingUser.email} disabled className="form-input" />
          </div>
          <div className="form-field">
            <label className="form-label">Full Name</label>
            <input value={editedFullName} onChange={(e) => setEditedFullName(e.target.value)} className="form-input" />
          </div>
          <button className="button button--primary" type="button" onClick={onSaveEdit} disabled={updateUserMutation.status === "pending"}>
            {updateUserMutation.status === "pending" ? "Saving..." : "Save changes"}
          </button>
          <button className="button button--secondary" type="button" onClick={() => setEditingUser(null)} style={{ marginLeft: 8 }}>
            Cancel
          </button>
        </div>
      ) : null}

      <form onSubmit={form.handleSubmit(onSubmit)} className="module-card" style={{ marginTop: 16 }}>
        <h3 className="action-panel-title">Create User</h3>

        {form.formState.errors.root && (
          <div className="form-error-banner">{form.formState.errors.root.message}</div>
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

        <ActionPanel title="New User Created" style={{ marginTop: 16 }}>
          {latestResult ? (
            <JsonViewer data={latestResult} />
          ) : (
            <div className="module-status loading">Create a user to see the API response payload here.</div>
          )}
        </ActionPanel>
      </form>
    </ModulePage>
  );
}

