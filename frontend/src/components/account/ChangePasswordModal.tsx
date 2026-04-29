import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { changeMyPassword } from "../../lib/api";
import { extractErrorMessage } from "../../lib/errorUtils";
import { useAuthStore } from "../../store/authStore";

type Props = {
  open: boolean;
  onClose: () => void;
};

export function ChangePasswordModal({ open, onClose }: Props) {
  const setAuth = useAuthStore((s) => s.setAuth);
  const user = useAuthStore((s) => s.user);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [feedback, setFeedback] = useState<{ kind: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    if (!open) {
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setFeedback(null);
    }
  }, [open]);

  const mutation = useMutation({
    mutationFn: () => changeMyPassword(currentPassword, newPassword),
    onSuccess: (data) => {
      if (user && data.tokens) {
        setAuth(data.tokens, user);
      }
      setFeedback({ kind: "success", message: data.message || "Password updated." });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      window.setTimeout(() => onClose(), 1500);
    },
    onError: (err) => {
      setFeedback({ kind: "error", message: extractErrorMessage(err) });
    },
  });

  if (!open) return null;

  const submit = () => {
    setFeedback(null);
    if (!currentPassword || !newPassword) {
      setFeedback({ kind: "error", message: "Please fill in all fields." });
      return;
    }
    if (newPassword.length < 8) {
      setFeedback({ kind: "error", message: "New password must be at least 8 characters." });
      return;
    }
    if (newPassword !== confirmPassword) {
      setFeedback({ kind: "error", message: "New password and confirmation do not match." });
      return;
    }
    if (newPassword === currentPassword) {
      setFeedback({ kind: "error", message: "New password must differ from the current one." });
      return;
    }
    mutation.mutate();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="change-password-title"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        className="panel"
        style={{ width: "min(420px, 92vw)", padding: 24, background: "white", borderRadius: 8 }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="change-password-title" style={{ marginTop: 0 }}>Change Password</h2>
        <p style={{ marginTop: 0, color: "#555" }}>
          Pick a strong new password. All other sessions will be signed out automatically.
        </p>

        <div className="form-field">
          <label className="form-label" htmlFor="cp-current">Current password</label>
          <input
            id="cp-current"
            type="password"
            className="form-input"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            autoComplete="current-password"
          />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="cp-new">New password</label>
          <input
            id="cp-new"
            type="password"
            className="form-input"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            autoComplete="new-password"
          />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="cp-confirm">Confirm new password</label>
          <input
            id="cp-confirm"
            type="password"
            className="form-input"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            autoComplete="new-password"
          />
        </div>

        {feedback ? (
          <div
            className={`module-status ${feedback.kind === "success" ? "success-text" : "error-text"}`}
            style={{ marginTop: 12 }}
          >
            {feedback.message}
          </div>
        ) : null}

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 16 }}>
          <button type="button" onClick={onClose} disabled={mutation.status === "pending"}>
            Cancel
          </button>
          <button
            type="button"
            className="button button--primary"
            onClick={submit}
            disabled={mutation.status === "pending"}
          >
            {mutation.status === "pending" ? "Updating…" : "Update password"}
          </button>
        </div>
      </div>
    </div>
  );
}
