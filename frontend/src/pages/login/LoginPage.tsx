import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { fetchMe, login } from "../../lib/auth";
import { useAuthStore } from "../../store/authStore";
import { ROUTES } from "../../config/routes";

export function LoginPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((state) => state.setAuth);
  const setTenantSlug = useAuthStore((state) => state.setTenantSlug);
  const [tenantSlug, setTenantSlugInput] = useState("default");
  const [email, setEmail] = useState("admin@toolboxgalaxy.local");
  const [password, setPassword] = useState("Admin123!");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const auth = await login({ email, password, tenantSlug });
      setTenantSlug(tenantSlug);
      const me = await fetchMe();
      setAuth(auth.tokens, me.user);
      navigate(ROUTES.DASHBOARD, { replace: true });
    } catch (err) {
      setError("Login failed. Verify tenant/email/password.");
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
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>

        {error ? <div className="error-text">{error}</div> : null}
        <button type="submit" disabled={loading}>{loading ? "Signing in..." : "Sign in"}</button>
        <small style={{ marginTop: 12 }}>
          Need legacy admin or control-panel fallback pages during cutover? Use the browser-session login at <a href="/login">/login</a>.
        </small>
      </form>
    </div>
  );
}
