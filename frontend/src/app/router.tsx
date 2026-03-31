/* eslint-disable react-refresh/only-export-components */
import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, createBrowserRouter } from "react-router-dom";
import type { RouteObject } from "react-router-dom";
import { APP_BASE_PATH } from "../config/env";
import { ROUTE_PERMISSIONS } from "../config/routePermissions";
import { ROUTES } from "../config/routes";
import { RequireAuth, RequirePermission } from "../lib/guards";
import { AppShell } from "../components/layout/AppShell";

const LoginPage = lazy(() => import("../pages/login/LoginPage").then((m) => ({ default: m.LoginPage })));
const DashboardPage = lazy(() => import("../pages/dashboard/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const SystemsPage = lazy(() => import("../pages/systems/SystemsPage").then((m) => ({ default: m.SystemsPage })));
const HistoryPage = lazy(() => import("../pages/history/HistoryPage").then((m) => ({ default: m.HistoryPage })));
const TenantsPage = lazy(() => import("../pages/tenants/TenantsPage").then((m) => ({ default: m.TenantsPage })));
const UsersPage = lazy(() => import("../pages/users/UsersPage").then((m) => ({ default: m.UsersPage })));
const AlertsPage = lazy(() => import("../pages/alerts/AlertsPage").then((m) => ({ default: m.AlertsPage })));
const AutomationPage = lazy(() => import("../pages/automation/AutomationPage").then((m) => ({ default: m.AutomationPage })));
const LogsPage = lazy(() => import("../pages/logs/LogsPage").then((m) => ({ default: m.LogsPage })));
const ReliabilityPage = lazy(() => import("../pages/reliability/ReliabilityPage").then((m) => ({ default: m.ReliabilityPage })));
const AiPage = lazy(() => import("../pages/ai/AiPage").then((m) => ({ default: m.AiPage })));
const ReleasesPage = lazy(() => import("../pages/releases/ReleasesPage").then((m) => ({ default: m.ReleasesPage })));
const UpdatesPage = lazy(() => import("../pages/updates/UpdatesPage").then((m) => ({ default: m.UpdatesPage })));
const RemotePage = lazy(() => import("../pages/remote/RemotePage").then((m) => ({ default: m.RemotePage })));
const PlatformPage = lazy(() => import("../pages/platform/PlatformPage").then((m) => ({ default: m.PlatformPage })));
const BackupPage = lazy(() => import("../pages/backup/BackupPage").then((m) => ({ default: m.BackupPage })));
const AuditPage = lazy(() => import("../pages/audit/AuditPage").then((m) => ({ default: m.AuditPage })));

function lazyElement(element: ReactNode) {
  return (
    <Suspense fallback={<div className="module-status loading">Loading module...</div>}>
      {element}
    </Suspense>
  );
}

function guardedElement(route: keyof typeof ROUTE_PERMISSIONS, element: ReactNode) {
  return (
    <RequirePermission permission={ROUTE_PERMISSIONS[route]}>
      {lazyElement(element)}
    </RequirePermission>
  );
}

const appChildren: RouteObject[] = [
  {
    path: ROUTES.DASHBOARD.slice(1),
    element: guardedElement(ROUTES.DASHBOARD, <DashboardPage />),
  },
  {
    path: ROUTES.SYSTEMS.slice(1),
    element: guardedElement(ROUTES.SYSTEMS, <SystemsPage />),
  },
  {
    path: ROUTES.HISTORY.slice(1),
    element: guardedElement(ROUTES.HISTORY, <HistoryPage />),
  },
  {
    path: ROUTES.TENANTS.slice(1),
    element: guardedElement(ROUTES.TENANTS, <TenantsPage />),
  },
  {
    path: ROUTES.USERS.slice(1),
    element: guardedElement(ROUTES.USERS, <UsersPage />),
  },
  {
    path: ROUTES.ALERTS.slice(1),
    element: guardedElement(ROUTES.ALERTS, <AlertsPage />),
  },
  {
    path: ROUTES.AUTOMATION.slice(1),
    element: guardedElement(ROUTES.AUTOMATION, <AutomationPage />),
  },
  {
    path: ROUTES.LOGS.slice(1),
    element: guardedElement(ROUTES.LOGS, <LogsPage />),
  },
  {
    path: ROUTES.RELIABILITY.slice(1),
    element: guardedElement(ROUTES.RELIABILITY, <ReliabilityPage />),
  },
  {
    path: ROUTES.AI.slice(1),
    element: guardedElement(ROUTES.AI, <AiPage />),
  },
  {
    path: ROUTES.RELEASES.slice(1),
    element: guardedElement(ROUTES.RELEASES, <ReleasesPage />),
  },
  {
    path: ROUTES.UPDATES.slice(1),
    element: guardedElement(ROUTES.UPDATES, <UpdatesPage />),
  },
  {
    path: ROUTES.REMOTE.slice(1),
    element: guardedElement(ROUTES.REMOTE, <RemotePage />),
  },
  {
    path: ROUTES.PLATFORM.slice(1),
    element: guardedElement(ROUTES.PLATFORM, <PlatformPage />),
  },
  {
    path: ROUTES.BACKUP.slice(1),
    element: guardedElement(ROUTES.BACKUP, <BackupPage />),
  },
  {
    path: ROUTES.AUDIT.slice(1),
    element: guardedElement(ROUTES.AUDIT, <AuditPage />),
  },
  { index: true, element: <Navigate to={ROUTES.DASHBOARD} replace /> },
];

export const router = createBrowserRouter(
  [
    { path: ROUTES.LOGIN, element: lazyElement(<LoginPage />) },
    {
      path: "/",
      element: (
        <RequireAuth>
          <AppShell />
        </RequireAuth>
      ),
      children: appChildren,
    },
    { path: "*", element: <Navigate to={ROUTES.DASHBOARD} replace /> },
  ],
  {
    basename: APP_BASE_PATH,
  }
);
