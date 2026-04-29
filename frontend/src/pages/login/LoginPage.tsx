import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { fetchMeWithAuth, login, verifyTotpLogin } from "../../lib/auth";
import { useAuthStore } from "../../store/authStore";
import { ROUTES } from "../../config/routes";

export function LoginPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((state) => state.setAuth);
  const setTenantSlug = useAuthStore((state) => state.setTenantSlug);
  const [tenantSlug, setTenantSlugInput] = useState("default");
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("ChangeMe123!");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaChallengeToken, setMfaChallengeToken] = useState("");

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
      if (!auth.tokens) {
        throw new Error("Missing login tokens");
      }
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
      if (!auth.tokens) {
        throw new Error("Missing login tokens");
      }
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
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
        ) : (
          <label>
            Authenticator Code
            <input value={mfaCode} onChange={(e) => setMfaCode(e.target.value)} required />
          </label>
        )}

        {error ? <div className="error-text">{error}</div> : null}
        {!mfaChallengeToken ? (
          <button type="submit" disabled={loading}>{loading ? "Signing in..." : "Sign in"}</button>
        ) : (
          <button type="button" onClick={onVerifyMfa} disabled={loading || !mfaCode.trim()}>
            {loading ? "Verifying..." : "Verify MFA"}
          </button>
        )}
        <small style={{ marginTop: 12 }}>
          Need legacy admin or control-panel fallback pages during cutover? Use the browser-session login at <a href="/login">/login</a>.
        </small>
      </form>
    </div>
  );
}
