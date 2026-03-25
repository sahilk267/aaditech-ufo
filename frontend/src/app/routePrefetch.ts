import { ROUTES } from "../config/routes";

type PrefetchLoader = () => Promise<unknown>;

const routeLoaders: Record<string, PrefetchLoader> = {
  [ROUTES.DASHBOARD]: () => import("../pages/dashboard/DashboardPage"),
  [ROUTES.SYSTEMS]: () => import("../pages/systems/SystemsPage"),
  [ROUTES.HISTORY]: () => import("../pages/history/HistoryPage"),
  [ROUTES.TENANTS]: () => import("../pages/tenants/TenantsPage"),
  [ROUTES.USERS]: () => import("../pages/users/UsersPage"),
  [ROUTES.ALERTS]: () => import("../pages/alerts/AlertsPage"),
  [ROUTES.AUTOMATION]: () => import("../pages/automation/AutomationPage"),
  [ROUTES.LOGS]: () => import("../pages/logs/LogsPage"),
  [ROUTES.RELIABILITY]: () => import("../pages/reliability/ReliabilityPage"),
  [ROUTES.AI]: () => import("../pages/ai/AiPage"),
  [ROUTES.RELEASES]: () => import("../pages/releases/ReleasesPage"),
  [ROUTES.UPDATES]: () => import("../pages/updates/UpdatesPage"),
  [ROUTES.REMOTE]: () => import("../pages/remote/RemotePage"),
  [ROUTES.PLATFORM]: () => import("../pages/platform/PlatformPage"),
  [ROUTES.BACKUP]: () => import("../pages/backup/BackupPage"),
  [ROUTES.AUDIT]: () => import("../pages/audit/AuditPage"),
};

const prefetchedRoutes = new Set<string>();

export function prefetchRoute(route: string) {
  if (prefetchedRoutes.has(route)) return;
  const loader = routeLoaders[route];
  if (!loader) return;

  prefetchedRoutes.add(route);
  void loader();
}
