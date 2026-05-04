import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { logout } from "../../lib/auth";
import { useAuthStore } from "../../store/authStore";
import { ROUTES } from "../../config/routes";
import { NAV_SECTIONS } from "../../config/navigation";
import { hasPermission } from "../../lib/rbac";
import { prefetchRoute } from "../../app/routePrefetch";
import { ChangePasswordModal } from "../account/ChangePasswordModal";

export function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const clearAuth = useAuthStore((state) => state.clearAuth);
  const userPermissions = user?.permissions || [];
  const [changePasswordOpen, setChangePasswordOpen] = useState(false);

  // Flatten all visible items for prefetch
  const allVisibleItems = NAV_SECTIONS.flatMap((s) => s.items).filter((item) =>
    hasPermission(userPermissions, item.permission)
  );

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      allVisibleItems
        .slice(0, 4)
        .map((item) => item.route)
        .filter((route) => route !== location.pathname)
        .forEach(prefetchRoute);
    }, 350);
    return () => window.clearTimeout(timeoutId);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  function prefetchOnIntent(route: string) {
    if (route !== location.pathname) {
      prefetchRoute(route);
    }
  }

  async function onLogout() {
    try {
      await logout();
    } catch {
      // Ignore logout transport errors and clear local auth state.
    } finally {
      clearAuth();
      navigate(ROUTES.LOGIN, { replace: true });
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <h2>AADITECH UFO</h2>
          <small>Operations SPA</small>
        </div>
        <nav>
          {NAV_SECTIONS.map((section) => {
            const visibleItems = section.items.filter((item) =>
              hasPermission(userPermissions, item.permission)
            );
            if (visibleItems.length === 0) return null;
            return (
              <div key={section.label} className="nav-section">
                <div className="nav-section-label">{section.label}</div>
                {visibleItems.map((item) => (
                  <NavLink
                    key={item.route}
                    to={item.route}
                    onMouseEnter={() => prefetchOnIntent(item.route)}
                    onFocus={() => prefetchOnIntent(item.route)}
                    className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
                  >
                    {item.label}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>

        {/* Show restricted sections */}
        {NAV_SECTIONS.some((s) =>
          s.items.some((item) => !hasPermission(userPermissions, item.permission))
        ) ? (
          <div className="blocked-features">
            <small>Some modules require elevated permissions.</small>
          </div>
        ) : null}
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <strong>{user?.full_name || "Unknown User"}</strong>
            <div className="meta">{user?.email || "No session"}</div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" onClick={() => setChangePasswordOpen(true)}>
              Change password
            </button>
            <button type="button" onClick={onLogout}>Logout</button>
          </div>
        </header>

        <div className="content-wrap">
          <Outlet />
        </div>
      </main>

      <ChangePasswordModal open={changePasswordOpen} onClose={() => setChangePasswordOpen(false)} />
    </div>
  );
}
