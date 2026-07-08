import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { JsonViewer } from "../../components/common/JsonViewer";
import { FormInput, FormSubmitButton } from "../../components/forms/FormComponents";
import {
  getUsers,
  getUserAuditActivity,
  registerUser,
  revokeUserSessions,
  sendUserPasswordReset,
  updateUser,
} from "../../lib/api";
import { fetchMe } from "../../lib/auth";
import { queryKeys } from "../../lib/queryKeys";
import { createUserSchema, type CreateUserInput } from "../../lib/schemas";
import type { User } from "../../types/api";

/* ── helpers ─────────────────────────────────────────────────── */

function timeSince(iso: string | null | undefined): string {
  if (!iso) return "Never";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 2) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function fmtTs(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

interface AuditEvent {
  id: number;
  created_at: string;
  action: string;
  outcome: string;
  remote_addr: string | null;
  metadata: Record<string, unknown>;
}

const ACTION_ICON: Record<string, string> = {
  "auth.login": "🔑",
  "auth.login.failed": "⚠️",
  "auth.login.locked": "🔒",
  "auth.logout": "🚪",
  "auth.sessions.revoke": "❌",
  "auth.change_password": "🔄",
  "auth.forgot_password": "📧",
  "auth.reset_password": "✅",
  "admin.send_password_reset": "🛡️",
};

function outcomeChip(outcome: string) {
  const ok = outcome === "success";
  return (
    <span
      style={{
        display: "inline-block",
        padding: "1px 7px",
        borderRadius: 10,
        fontSize: 11,
        fontWeight: 600,
        background: ok ? "#dcfce7" : "#fee2e2",
        color: ok ? "#166534" : "#991b1b",
        border: `1px solid ${ok ? "#bbf7d0" : "#fecaca"}`,
      }}
    >
      {outcome}
    </span>
  );
}

/* ── per-row reset state ─────────────────────────────────────── */
interface ResetState {
  loading: boolean;
  devUrl: string | null;
  error: string | null;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      style={{
        flexShrink: 0,
        background: copied ? "#d1fae5" : "#f3f4f6",
        border: `1px solid ${copied ? "#6ee7b7" : "#d1d5db"}`,
        borderRadius: 4,
        padding: "2px 8px",
        fontSize: 11,
        cursor: "pointer",
        color: copied ? "#065f46" : "#374151",
        whiteSpace: "nowrap",
      }}
      onClick={() =>
        void navigator.clipboard.writeText(text).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 2500);
        })
      }
    >
      {copied ? "✓ Copied" : "Copy link"}
    </button>
  );
}

/* ── Activity panel (lazy-loaded per user) ───────────────────── */
function UserActivityPanel({ userId }: { userId: number }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["user-audit-activity", userId],
    queryFn: () => getUserAuditActivity(userId, 20),
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <tr>
        <td colSpan={5} style={{ padding: "12px 16px" }}>
          <span style={{ color: "#6b7280", fontSize: 13 }}>Loading activity…</span>
        </td>
      </tr>
    );
  }

  if (isError) {
    return (
      <tr>
        <td colSpan={5} style={{ padding: "12px 16px" }}>
          <span style={{ color: "#dc2626", fontSize: 13 }}>Failed to load activity.</span>
        </td>
      </tr>
    );
  }

  const events: AuditEvent[] = data?.events ?? [];
  const lastLogin: string | null = data?.last_login_at ?? null;
  const failedAttempts: number = data?.failed_login_attempts ?? 0;
  const lockedUntil: string | null = data?.locked_until ?? null;

  return (
    <tr>
      <td
        colSpan={5}
        style={{
          padding: 0,
          background: "var(--surface-elevated, #f9fafb)",
          borderBottom: "1px solid var(--border, #e5e7eb)",
        }}
      >
        <div style={{ padding: "12px 20px 16px" }}>
          {/* summary row */}
          <div
            style={{
              display: "flex",
              gap: 24,
              marginBottom: 12,
              flexWrap: "wrap",
              fontSize: 12,
              color: "#6b7280",
            }}
          >
            <span>
              <strong style={{ color: "#111" }}>Last login:</strong>{" "}
              {lastLogin ? (
                <span title={fmtTs(lastLogin)}>{timeSince(lastLogin)} · {fmtTs(lastLogin)}</span>
              ) : (
                "Never"
              )}
            </span>
            <span>
              <strong style={{ color: failedAttempts > 0 ? "#b45309" : "#111" }}>
                Failed attempts:
              </strong>{" "}
              <span style={{ color: failedAttempts > 0 ? "#b45309" : undefined }}>
                {failedAttempts}
              </span>
            </span>
            {lockedUntil && new Date(lockedUntil) > new Date() && (
              <span style={{ color: "#dc2626" }}>
                🔒 <strong>Locked until:</strong> {fmtTs(lockedUntil)}
              </span>
            )}
          </div>

          {/* events table */}
          {events.length === 0 ? (
            <p style={{ fontSize: 13, color: "#9ca3af", margin: 0 }}>
              No audit events recorded for this user yet.
            </p>
          ) : (
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: 12,
              }}
            >
              <thead>
                <tr style={{ borderBottom: "1px solid #e5e7eb" }}>
                  {["When", "Action", "Outcome", "IP / Source"].map((h) => (
                    <th
                      key={h}
                      style={{
                        padding: "4px 10px",
                        textAlign: "left",
                        fontWeight: 600,
                        color: "#6b7280",
                        textTransform: "uppercase",
                        fontSize: 10,
                        letterSpacing: "0.05em",
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {events.map((ev) => (
                  <tr
                    key={ev.id}
                    style={{ borderBottom: "1px solid #f3f4f6" }}
                  >
                    <td
                      style={{
                        padding: "5px 10px",
                        whiteSpace: "nowrap",
                        color: "#6b7280",
                      }}
                      title={fmtTs(ev.created_at)}
                    >
                      {timeSince(ev.created_at)}
                    </td>
                    <td style={{ padding: "5px 10px" }}>
                      <span style={{ marginRight: 6 }}>
                        {ACTION_ICON[ev.action] ?? "📋"}
                      </span>
                      <span
                        style={{
                          fontFamily: "monospace",
                          fontSize: 11,
                          color: "#374151",
                        }}
                      >
                        {ev.action}
                      </span>
                    </td>
                    <td style={{ padding: "5px 10px" }}>
                      {outcomeChip(ev.outcome)}
                    </td>
                    <td
                      style={{
                        padding: "5px 10px",
                        color: "#9ca3af",
                        fontFamily: "monospace",
                        fontSize: 11,
                      }}
                    >
                      {ev.remote_addr ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </td>
    </tr>
  );
}

/* ══ Main Page ═══════════════════════════════════════════════════ */

export function UsersPage() {
  const queryClient = useQueryClient();
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editedFullName, setEditedFullName] = useState("");
  const [resetStates, setResetStates] = useState<Record<number, ResetState>>({});
  const [expandedActivity, setExpandedActivity] = useState<Set<number>>(new Set());

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

  const meQuery = useQuery({
    queryKey: queryKeys.me,
    queryFn: fetchMe,
    staleTime: 60_000,
  });

  const createUserMutation = useMutation({
    mutationFn: (data: CreateUserInput) =>
      registerUser({ email: data.email, full_name: data.fullName, password: data.password }),
    onSuccess: (data) => {
      setLatestResult(data);
      form.reset();
      void queryClient.invalidateQueries({ queryKey: queryKeys.users });
      void queryClient.invalidateQueries({ queryKey: queryKeys.me });
    },
    onError: (err) => form.setError("root", { message: String(err) }),
  });

  const revokeSessionsMutation = useMutation({
    mutationFn: (userId: number) => revokeUserSessions(userId),
    onSuccess: (data) => {
      setLatestResult(data);
      void queryClient.invalidateQueries({ queryKey: queryKeys.users });
    },
    onError: (err) => form.setError("root", { message: String(err) }),
  });

  const updateUserMutation = useMutation({
    mutationFn: (payload: { id: number; full_name: string }) =>
      updateUser(payload.id, { full_name: payload.full_name }),
    onSuccess: () => {
      if (editingUser) {
        setLatestResult({
          message: "User updated",
          user: { ...editingUser, full_name: editedFullName },
        });
      }
      setEditingUser(null);
      setEditedFullName("");
      void queryClient.invalidateQueries({ queryKey: queryKeys.users });
    },
    onError: (err) => form.setError("root", { message: String(err) }),
  });

  async function handleSendReset(userId: number) {
    setResetStates((p) => ({ ...p, [userId]: { loading: true, devUrl: null, error: null } }));
    try {
      const res = (await sendUserPasswordReset(userId)) as {
        dev_reset_url?: string;
      };
      setResetStates((p) => ({
        ...p,
        [userId]: { loading: false, devUrl: res.dev_reset_url ?? null, error: null },
      }));
      setTimeout(
        () => setResetStates((p) => ({ ...p, [userId]: { loading: false, devUrl: null, error: null } })),
        60_000,
      );
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } }).response?.data?.message ??
        "Failed to generate reset link.";
      setResetStates((p) => ({ ...p, [userId]: { loading: false, devUrl: null, error: msg } }));
    }
  }

  function toggleActivity(userId: number) {
    setExpandedActivity((prev) => {
      const next = new Set(prev);
      next.has(userId) ? next.delete(userId) : next.add(userId);
      return next;
    });
  }

  const onSubmit = (data: CreateUserInput) => createUserMutation.mutate(data);
  const onBeginEdit = (user: User) => { setEditingUser(user); setEditedFullName(user.full_name ?? ""); };
  const onSaveEdit = () => { if (editingUser) updateUserMutation.mutate({ id: editingUser.id, full_name: editedFullName }); };
  const refreshUsers = () => void queryClient.invalidateQueries({ queryKey: queryKeys.users });
  const resetUserForm = () => { form.reset(); setLatestResult(null); setEditingUser(null); setEditedFullName(""); };

  const users: User[] = usersQuery.data?.users ?? [];

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
          <div className="module-status loading">No current session user payload available.</div>
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
                  <th>Email / Name</th>
                  <th>Last Login</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user: User & {
                  last_login_at?: string | null;
                  failed_login_attempts?: number;
                  locked_until?: string | null;
                }) => {
                  const rs = resetStates[user.id] ?? { loading: false, devUrl: null, error: null };
                  const activityOpen = expandedActivity.has(user.id);
                  const isLocked = user.locked_until && new Date(user.locked_until) > new Date();

                  return (
                    <>
                      <tr key={user.id} style={{ verticalAlign: "middle" }}>
                        <td style={{ color: "#9ca3af", fontSize: 12 }}>{user.id}</td>
                        <td>
                          <div style={{ fontWeight: 600, fontSize: 13 }}>{user.email}</div>
                          <div style={{ fontSize: 12, color: "#6b7280" }}>{user.full_name || "—"}</div>
                        </td>
                        <td style={{ fontSize: 12, color: "#6b7280", whiteSpace: "nowrap" }}>
                          {user.last_login_at ? (
                            <span title={fmtTs(user.last_login_at)}>
                              {timeSince(user.last_login_at)}
                            </span>
                          ) : (
                            <span style={{ color: "#d1d5db" }}>Never</span>
                          )}
                          {(user.failed_login_attempts ?? 0) > 0 && (
                            <span
                              style={{
                                marginLeft: 8,
                                background: "#fef3c7",
                                color: "#b45309",
                                border: "1px solid #fde68a",
                                borderRadius: 8,
                                padding: "1px 6px",
                                fontSize: 10,
                                fontWeight: 600,
                              }}
                              title={`${user.failed_login_attempts} failed login attempts`}
                            >
                              {user.failed_login_attempts} failed
                            </span>
                          )}
                        </td>
                        <td>
                          {isLocked ? (
                            <span
                              style={{
                                background: "#fee2e2",
                                color: "#991b1b",
                                border: "1px solid #fecaca",
                                borderRadius: 8,
                                padding: "2px 8px",
                                fontSize: 11,
                                fontWeight: 600,
                              }}
                              title={`Locked until ${fmtTs(user.locked_until)}`}
                            >
                              🔒 Locked
                            </span>
                          ) : user.is_active ? (
                            <span
                              style={{
                                background: "#dcfce7",
                                color: "#166534",
                                border: "1px solid #bbf7d0",
                                borderRadius: 8,
                                padding: "2px 8px",
                                fontSize: 11,
                                fontWeight: 600,
                              }}
                            >
                              Active
                            </span>
                          ) : (
                            <span
                              style={{
                                background: "#f3f4f6",
                                color: "#6b7280",
                                border: "1px solid #e5e7eb",
                                borderRadius: 8,
                                padding: "2px 8px",
                                fontSize: 11,
                                fontWeight: 600,
                              }}
                            >
                              Inactive
                            </span>
                          )}
                        </td>
                        <td>
                          <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
                            <button
                              className="button button--secondary button--sm"
                              type="button"
                              onClick={() => onBeginEdit(user)}
                            >
                              Edit
                            </button>
                            <button
                              className="button button--secondary button--sm"
                              type="button"
                              style={{ color: "#b45309", border: "1px solid #fde68a" }}
                              onClick={() => revokeSessionsMutation.mutate(user.id)}
                              disabled={revokeSessionsMutation.isPending}
                              title="Force logout — revoke all active sessions"
                            >
                              Revoke sessions
                            </button>
                            <button
                              className="button button--secondary button--sm"
                              type="button"
                              style={{ color: "#6d28d9", border: "1px solid #ddd6fe" }}
                              onClick={() => handleSendReset(user.id)}
                              disabled={rs.loading}
                              title="Generate and send a password-reset link"
                            >
                              {rs.loading ? "Sending…" : "Send reset"}
                            </button>
                            <button
                              className="button button--secondary button--sm"
                              type="button"
                              style={{
                                color: activityOpen ? "#0f172a" : "#475569",
                                background: activityOpen ? "#f1f5f9" : undefined,
                              }}
                              onClick={() => toggleActivity(user.id)}
                              title="Show/hide recent account activity"
                            >
                              {activityOpen ? "▼ Activity" : "▶ Activity"}
                            </button>
                          </div>
                        </td>
                      </tr>

                      {/* Activity expansion */}
                      {activityOpen && <UserActivityPanel key={`activity-${user.id}`} userId={user.id} />}

                      {/* Reset link feedback */}
                      {(rs.devUrl || rs.error) && (
                        <tr key={`${user.id}-reset-info`}>
                          <td colSpan={5} style={{ padding: "0 12px 10px" }}>
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
                                    (SMTP not configured — share manually · expires 60 min)
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

      {/* Edit panel */}
      {editingUser && (
        <div className="module-card" style={{ marginTop: 16 }}>
          <h3>Edit User</h3>
          <div className="form-field">
            <label className="form-label">Email</label>
            <input value={editingUser.email} disabled className="form-input" />
          </div>
          <div className="form-field">
            <label className="form-label">Full Name</label>
            <input
              value={editedFullName}
              onChange={(e) => setEditedFullName(e.target.value)}
              className="form-input"
            />
          </div>
          <button
            className="button button--primary"
            type="button"
            onClick={onSaveEdit}
            disabled={updateUserMutation.status === "pending"}
          >
            {updateUserMutation.status === "pending" ? "Saving..." : "Save changes"}
          </button>
          <button
            className="button button--secondary"
            type="button"
            onClick={() => setEditingUser(null)}
            style={{ marginLeft: 8 }}
          >
            Cancel
          </button>
        </div>
      )}

      {/* Create user form */}
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
            <div className="module-status loading">
              Create a user to see the API response payload here.
            </div>
          )}
        </ActionPanel>
      </form>
    </ModulePage>
  );
}
