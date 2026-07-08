import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { resetPassword } from "../../lib/api";
import { ROUTES } from "../../config/routes";

type Stage = "form" | "success" | "expired";

function PasswordStrengthBar({ password }: { password: string }) {
  const checks = [
    password.length >= 8,
    /[A-Z]/.test(password),
    /[a-z]/.test(password),
    /\d/.test(password),
    /[^A-Za-z0-9]/.test(password),
  ];
  const score = checks.filter(Boolean).length;
  const colors = ["#ef4444", "#f97316", "#eab308", "#22c55e", "#16a34a"];
  const labels = ["Very weak", "Weak", "Fair", "Strong", "Very strong"];
  if (!password) return null;
  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ display: "flex", gap: 3, marginBottom: 4 }}>
        {[1, 2, 3, 4, 5].map((n) => (
          <div
            key={n}
            style={{
              flex: 1,
              height: 4,
              borderRadius: 2,
              background: n <= score ? colors[score - 1] : "#e5e7eb",
              transition: "background 0.2s",
            }}
          />
        ))}
      </div>
      <span style={{ fontSize: 11, color: colors[score - 1] ?? "#9ca3af" }}>
        {labels[score - 1] ?? ""}
      </span>
    </div>
  );
}

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();

  const token = params.get("token") ?? "";
  const tenantSlug = params.get("tenant") ?? "default";

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState<Stage>(token ? "form" : "expired");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setFieldErrors({});

    if (!token) {
      setStage("expired");
      return;
    }

    if (newPassword !== confirmPassword) {
      setFieldErrors({ confirm_password: ["Passwords do not match"] });
      return;
    }

    setLoading(true);
    try {
      await resetPassword({ token, new_password: newPassword, tenant_slug: tenantSlug });
      setStage("success");
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { details?: Record<string, string[]>; message?: string } } }).response;
      const data = resp?.data;
      if (data?.details) {
        setFieldErrors(data.details);
      } else {
        const msg = data?.message ?? "Reset failed. The link may have expired.";
        if (msg.toLowerCase().includes("expired") || msg.toLowerCase().includes("invalid")) {
          setStage("expired");
        } else {
          setError(msg);
        }
      }
    } finally {
      setLoading(false);
    }
  }

  if (stage === "success") {
    return (
      <div className="login-wrap">
        <div className="login-card" style={{ textAlign: "center" }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
          <h1 style={{ marginBottom: 8 }}>Password reset</h1>
          <p style={{ color: "#6b7280", marginBottom: 24 }}>
            Your password has been updated. All other sessions have been signed out.
          </p>
          <button
            className="button button--primary"
            style={{ width: "100%" }}
            onClick={() => navigate(ROUTES.LOGIN, { replace: true })}
          >
            Sign in with new password
          </button>
        </div>
      </div>
    );
  }

  if (stage === "expired") {
    return (
      <div className="login-wrap">
        <div className="login-card" style={{ textAlign: "center" }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>⏳</div>
          <h1 style={{ marginBottom: 8 }}>Link expired</h1>
          <p style={{ color: "#6b7280", marginBottom: 24 }}>
            This password-reset link is invalid or has expired. Links are valid for 60 minutes.
            <br />
            Request a new one from the sign-in page.
          </p>
          <Link to={ROUTES.LOGIN} className="button" style={{ display: "block", textAlign: "center" }}>
            Back to sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={handleSubmit} noValidate>
        <h1>Reset password</h1>
        <p style={{ color: "#6b7280", marginBottom: 20 }}>
          Choose a new password for <strong>{tenantSlug}</strong>.
        </p>

        {error && (
          <div
            className="feedback-banner feedback-banner--error"
            style={{ marginBottom: 16 }}
          >
            {error}
          </div>
        )}

        <label>
          New password
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
            placeholder="At least 8 characters"
            style={{
              borderColor: fieldErrors.new_password ? "#ef4444" : undefined,
            }}
          />
          <PasswordStrengthBar password={newPassword} />
          {fieldErrors.new_password && (
            <span style={{ color: "#ef4444", fontSize: 12, marginTop: 4, display: "block" }}>
              {fieldErrors.new_password.join(" · ")}
            </span>
          )}
        </label>

        <label>
          Confirm password
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            autoComplete="new-password"
            placeholder="Re-enter new password"
            style={{
              borderColor: fieldErrors.confirm_password ? "#ef4444" : undefined,
            }}
          />
          {fieldErrors.confirm_password && (
            <span style={{ color: "#ef4444", fontSize: 12, marginTop: 4, display: "block" }}>
              {fieldErrors.confirm_password.join(" · ")}
            </span>
          )}
        </label>

        <button
          type="submit"
          className="button button--primary"
          style={{ width: "100%", marginTop: 8 }}
          disabled={loading || !newPassword || !confirmPassword}
        >
          {loading ? "Resetting…" : "Set new password"}
        </button>

        <p style={{ textAlign: "center", marginTop: 16, fontSize: 13, color: "#9ca3af" }}>
          <Link to={ROUTES.LOGIN} style={{ color: "#6b7280" }}>
            ← Back to sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
