import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { fetchMeWithAuth, login, verifyTotpLogin } from "../../lib/auth";
import { forgotPassword } from "../../lib/api";
import { useAuthStore } from "../../store/authStore";
import { ROUTES } from "../../config/routes";

type View = "login" | "forgot" | "forgot-sent";

export function LoginPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((state) => state.setAuth);
  const setTenantSlug = useAuthStore((state) => state.setTenantSlug);

  /* ── login state ── */
  const [tenantSlug, setTenantSlugInput] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaChallengeToken, setMfaChallengeToken] = useState("");

  /* ── forgot-password state ── */
  const [view, setView] = useState<View>("login");
  const [forgotEmail, setForgotEmail] = useState("");
  const [forgotTenant, setForgotTenant] = useState("");
  const [forgotLoading, setForgotLoading] = useState(false);
  const [forgotError, setForgotError] = useState("");
  const [devResetUrl, setDevResetUrl] = useState("");

  /* ── login handlers ── */
  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const auth = await login({ email, password, tenantSlug });
      if (auth.status === "mfa_required" && auth.challenge?.challenge_token) {
        setMfaChallengeToken(auth.challenge.challenge_token);
        setError("");
        return;
      }
      if (!auth.tokens) throw new Error("Missing login tokens");
      setTenantSlug(tenantSlug);
      const me = await fetchMeWithAuth(auth.tokens.access_token, tenantSlug);
      setAuth(auth.tokens, me.user);
      navigate(ROUTES.DASHBOARD, { replace: true });
    } catch {
      setError("Login failed. Verify tenant/email/password.");
    } finally {
      setLoading(false);
    }
  }

  async function onVerifyMfa() {
    setError("");
    setLoading(true);
    try {
      const auth = await verifyTotpLogin(mfaChallengeToken, mfaCode);
      if (!auth.tokens) throw new Error("Missing login tokens");
      setTenantSlug(tenantSlug);
      const me = await fetchMeWithAuth(auth.tokens.access_token, tenantSlug);
      setAuth(auth.tokens, me.user);
      navigate(ROUTES.DASHBOARD, { replace: true });
    } catch {
      setError("MFA verification failed. Check the authenticator code.");
    } finally {
      setLoading(false);
    }
  }

  /* ── forgot-password handler ── */
  function openForgot() {
    setForgotEmail(email);
    setForgotTenant(tenantSlug || "default");
    setForgotError("");
    setDevResetUrl("");
    setView("forgot");
  }

  async function onForgotSubmit(e: FormEvent) {
    e.preventDefault();
    setForgotError("");
    setForgotLoading(true);
    try {
      const res = await forgotPassword({
        email: forgotEmail.trim(),
        tenant_slug: forgotTenant.trim() || "default",
      }) as { status?: string; dev_reset_url?: string };
      setDevResetUrl(res.dev_reset_url ?? "");
      setView("forgot-sent");
    } catch {
      setForgotError("Something went wrong. Please try again.");
    } finally {
      setForgotLoading(false);
    }
  }

  /* ══ FORGOT-PASSWORD FORM ══════════════════════════════════════════ */
  if (view === "forgot") {
    return (
      <div className="login-wrap">
        <form className="login-card" onSubmit={onForgotSubmit}>
          <h1>Forgot password</h1>
          <p style={{ color: "#6b7280" }}>
            Enter your email and tenant. If an account exists we'll send a reset link.
          </p>

          <label>
            Tenant Slug
            <input
              value={forgotTenant}
              onChange={(e) => setForgotTenant(e.target.value)}
              placeholder="default"
              required
            />
          </label>
          <label>
            Email
            <input
              type="email"
              value={forgotEmail}
              onChange={(e) => setForgotEmail(e.target.value)}
              required
            />
          </label>

          {forgotError && <div className="error-text">{forgotError}</div>}

          <button type="submit" disabled={forgotLoading || !forgotEmail.trim()}>
            {forgotLoading ? "Sending…" : "Send reset link"}
          </button>

          <p style={{ textAlign: "center", marginTop: 12, fontSize: 13 }}>
            <button
              type="button"
              className="button button--secondary"
              style={{ background: "none", border: "none", cursor: "pointer", color: "#6b7280", fontSize: 13, padding: 0 }}
              onClick={() => setView("login")}
            >
              ← Back to sign in
            </button>
          </p>
        </form>
      </div>
    );
  }

  /* ══ FORGOT-SENT CONFIRMATION ════════════════════════════════════= */
  if (view === "forgot-sent") {
    return (
      <div className="login-wrap">
        <div className="login-card" style={{ textAlign: "center" }}>
          <div style={{ fontSize: 44, marginBottom: 10 }}>📬</div>
          <h1 style={{ marginBottom: 8 }}>Check your inbox</h1>
          <p style={{ color: "#6b7280", marginBottom: devResetUrl ? 16 : 24 }}>
            If an account exists for <strong>{forgotEmail}</strong> on tenant&nbsp;
            <strong>{forgotTenant}</strong>, a reset link has been sent. Links expire in 60 minutes.
          </p>

          {devResetUrl && (
            <div
              style={{
                background: "#fefce8",
                border: "1px solid #fde047",
                borderRadius: 8,
                padding: "12px 14px",
                marginBottom: 20,
                textAlign: "left",
              }}
            >
              <p style={{ fontSize: 12, color: "#92400e", fontWeight: 600, margin: "0 0 6px" }}>
                ⚠ Dev mode — SMTP not configured. Use this link to test:
              </p>
              <a
                href={devResetUrl}
                style={{
                  fontSize: 12,
                  color: "#1d4ed8",
                  wordBreak: "break-all",
                  textDecoration: "underline",
                }}
              >
                {devResetUrl}
              </a>
            </div>
          )}

          <button
            className="button"
            style={{ width: "100%" }}
            onClick={() => setView("login")}
          >
            Back to sign in
          </button>
        </div>
      </div>
    );
  }

  /* ══ MAIN LOGIN FORM ════════════════════════════════════════════════ */
  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={onSubmit}>
        <h1>UFO Control Center</h1>
        <p>Sign in to the new operations SPA.</p>

        <label>
          Tenant Slug
          <input value={tenantSlug} onChange={(e) => setTenantSlugInput(e.target.value)} required />
        </label>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>

        {!mfaChallengeToken ? (
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
        ) : (
          <label>
            Authenticator Code
            <input value={mfaCode} onChange={(e) => setMfaCode(e.target.value)} required />
          </label>
        )}

        {error ? <div className="error-text">{error}</div> : null}

        {!mfaChallengeToken ? (
          <button type="submit" disabled={loading}>
            {loading ? "Signing in..." : "Sign in"}
          </button>
        ) : (
          <button type="button" onClick={onVerifyMfa} disabled={loading || !mfaCode.trim()}>
            {loading ? "Verifying..." : "Verify MFA"}
          </button>
        )}

        {!mfaChallengeToken && (
          <p style={{ textAlign: "center", marginTop: 10, marginBottom: 0, fontSize: 13 }}>
            <button
              type="button"
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                color: "#6b7280",
                fontSize: 13,
                padding: 0,
                textDecoration: "underline",
              }}
              onClick={openForgot}
            >
              Forgot password?
            </button>
          </p>
        )}

        <small style={{ marginTop: 12 }}>
          Need legacy admin or control-panel fallback pages during cutover? Use the browser-session login at{" "}
          <a href="/login">/login</a>.
        </small>
      </form>
    </div>
  );
}
