import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { ROUTES } from "../config/routes";
import { useAuthStore } from "../store/authStore";

type RequireAuthProps = {
  children: ReactNode;
};

type RequirePermissionProps = {
  permission: string;
  children: ReactNode;
};

export function RequireAuth({ children }: RequireAuthProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to={ROUTES.LOGIN} replace state={{ from: location.pathname }} />;
  }

  return <>{children}</>;
}

export function RequirePermission({ permission, children }: RequirePermissionProps) {
  const user = useAuthStore((state) => state.user);

  if (!user?.permissions?.includes(permission)) {
    return <div className="blocked">Missing permission: {permission}</div>;
  }

  return <>{children}</>;
}
