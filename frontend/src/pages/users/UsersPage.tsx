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
import { getUsers, registerUser, revokeUserSessions, sendUserPasswordReset, updateUser } from "../../lib/api";
import { fetchMe } from "../../lib/auth";
import { queryKeys } from "../../lib/queryKeys";
import { createUserSchema, type CreateUserInput } from "../../lib/schemas";
import type { User } from "../../types/api";

interface ResetState {
  loading: boolean;
  devUrl: string | null;
  error: string | null;
}

export function UsersPage() {
  const queryClient = useQueryClient();
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editedFullName, setEditedFullName] = useState("");
  // per-row reset state keyed by user id
  const [resetStates, setResetStates] = useState<Record<number, ResetState>>({});

  const form = useForm<CreateUserInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(createUserSchema) as any,
    defaultValues: { email: "", fullName: "", password: "" },
  });

  const usersQuery = useQuery({
    queryKey: queryKeys.users,
    queryFn: getUsers,
    staleTime: 60_000,
  });

  const meQuery = useQuery({ queryKey: queryKeys.me, queryFn: fetchMe, staleTime: 60_000 });

  const createUserMutation = useMutation({
    mutationFn: (data: CreateUserInput) =>
      registerUser({ email: data.email, full_name: data.fullName, password: data.password }),
    onSuccess: (data) => {
      setLatestResult(data);
      form.reset();
      void queryClient.invalidateQueries({ queryKey: queryKeys.users });
      void queryClient.invalidateQueries({ queryKey: queryKeys.me });
    },
    onError: (err) => { form.setError("root", { message: String(err) }); },
  });

  const revokeSessionsMutation = useMutation({
    mutationFn: (userId: number) => revokeUserSessions(userId),
    onSuccess: (data) => {
      setLatestResult(data);
      void queryClient.invalidateQueries({ queryKey: queryKeys.users });
    },
    onError: (err) => { form.setError("root", { message: String(err) }); },
  });

  const updateUserMutation = useMutation({
    mutationFn: (payload: { id: number; full_name: string }) =>
      updateUser(payload.id, { full_name: payload.full_name }),
    onSuccess: () => {
      if (editingUser) {
        setLatestResult({ message: "User updated", user: { ...editingUser, full_name: editedFullName } });
      }
      setEditingUser(null);
      setEditedFullName("");
      void queryClient.invalidateQueries({ queryKey: queryKeys.users });
    },
    onError: (err) => { form.setError("root", { message: String(err) }); },
  });

  async function handleSendReset(userId: number) {
    setResetStates((prev) => ({
      ...prev,
      [userId]: { loading: true, devUrl: null, error: null },
    }));
    try {
      const res = await sendUserPasswordReset(userId) as {
        dev_reset_url?: string;
        email_sent?: boolean;
        message?: string;
      };
      setResetStates((prev) => ({
        ...prev,
        [userId]: {
          loading: false,
          devUrl: res.dev_reset_url ?? null,
          error: null,
        },
      }));
      // auto-dismiss the dev URL panel after 60 s
      setTimeout(() => {
        setResetStates((prev) => ({
          ...prev,
          [userId]: { loading: false, devUrl: null, error: null },
        }));
      }, 60_000);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } }).response?.data?.message ??
        "Failed to generate reset link.";
      setResetStates((prev) => ({
        ...prev,
        [userId]: { loading: false, devUrl: null, error: msg },
      }));
    }
  }

  const onSubmit = (data: CreateUserInput) => { createUserMutation.mutate(data); };
  const onBeginEdit = (user: User) => { setEditingUser(user); setEditedFullName(user.full_name ?? ""); };
  const onSaveEdit = () => { if (editingUser) updateUserMutation.mutate({ id: editingUser.id, full_name: editedFullName }); };
  const refreshUsers = () => { void queryClient.invalidateQueries({ queryKey: queryKeys.users }); };
  const resetUserForm = () => { form.reset(); setLatestResult(null); setEditingUser(null); setEditedFullName(""); };

  return (
    <ModulePage
      title="Users"
      description="Tenant-scoped user provisioning and management using /api/users."
      actions={
        <>
          <button type="button" onClick={refreshUsers} disabled={usersQuery.isFetching}>Refresh users</button>
          <button type="button" onClick={resetUserForm}>Reset form</button>
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
                {usersQuery.data?.users?.map((user: User) => {
                  const rs = resetStates[user.id] ?? { loading: false, devUrl: null, error: null };
                  return (
                    <>
                      <tr key={user.id}>
                        <td>{user.id}</td>
                        <td>{user.email}</td>
                        <td>{user.full_name || "-"}</td>
                        <td style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                          <button
                            className="button button--secondary"
                            type="button"
                            onClick={() => onBeginEdit(user)}
                          >
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
                          <button
                            className="button button--secondary"
                            type="button"
                            style={{ fontSize: "0.82em", color: "#6d28d9", border: "1px solid #ddd6fe" }}
                            onClick={() => handleSendReset(user.id)}
                            disabled={rs.loading}
                            title="Generate and send a password-reset link for this user"
                          >
                            {rs.loading ? "Sending…" : "Send reset"}
                          </button>
                        </td>
                      </tr>
                      {(rs.devUrl || rs.error) && (
                        <tr key={`${user.id}-reset-info`}>
                          <td colSpan={4} style={{ padding: "0 8px 10px" }}>
                            {rs.error ? (
                              <div
                                style={{
                                  background: "#fef2f2",
                                  border: "1px solid #fecaca",
                                  borderRadius: 6,
                                  padding: "8px 12px",
                                  fontSize: 13,
                                  color: "#b91c1c",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 8,
                                }}
                              >
                                ✗ {rs.error}
                                <button
                                  type="button"
                                  style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: "#b91c1c", fontSize: 14 }}
                                  onClick={() => setResetStates((p) => ({ ...p, [user.id]: { loading: false, devUrl: null, error: null } }))}
                                >
                                  ✕
                                </button>
                              </div>
                            ) : rs.devUrl ? (
                              <div
                                style={{
                                  background: "#fefce8",
                                  border: "1px solid #fde047",
                                  borderRadius: 6,
                                  padding: "8px 12px",
                                  fontSize: 13,
                                }}
                              >
                                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                                  <span style={{ fontWeight: 600, color: "#92400e" }}>
                                    ✓ Reset link generated
                                  </span>
                                  <span style={{ color: "#78716c", fontSize: 12 }}>
                                    (SMTP not configured — share manually · expires in 60 min)
                                  </span>
                                  <button
                                    type="button"
                                    style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: "#92400e", fontSize: 14 }}
                                    onClick={() => setResetStates((p) => ({ ...p, [user.id]: { loading: false, devUrl: null, error: null } }))}
                                  >
                                    ✕
                                  </button>
                                </div>
                                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                  <a
                                    href={rs.devUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    style={{ color: "#1d4ed8", wordBreak: "break-all", fontSize: 12 }}
                                  >
                                    {rs.devUrl}
                                  </a>
                                  <CopyButton text={rs.devUrl} />
                                </div>
                              </div>
                            ) : null}
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
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
          <button
            className="button button--primary"
            type="button"
            onClick={onSaveEdit}
            disabled={updateUserMutation.status === "pending"}
          >
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

        <FormSubmitButton isLoading={createUserMutation.isPending} isDisabled={!form.formState.isDirty}>
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

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      style={{
        flexShrink: 0,
        background: copied ? "#d1fae5" : "#f3f4f6",
        border: "1px solid " + (copied ? "#6ee7b7" : "#d1d5db"),
        borderRadius: 4,
        padding: "2px 8px",
        fontSize: 11,
        cursor: "pointer",
        color: copied ? "#065f46" : "#374151",
        whiteSpace: "nowrap",
      }}
      onClick={() => {
        void navigator.clipboard.writeText(text).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 2500);
        });
      }}
    >
      {copied ? "✓ Copied" : "Copy link"}
    </button>
  );
}
