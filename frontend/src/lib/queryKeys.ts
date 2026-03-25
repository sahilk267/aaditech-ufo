export const queryKeys = {
  me: ["auth", "me"] as const,
  dashboard: ["dashboard"] as const,
  dashboardStatus: (hostName: string) => ["dashboard", "status", hostName] as const,
  apiStatus: ["platform", "api-status"] as const,
  systems: ["systems"] as const,
  system: (id: number) => ["systems", id] as const,
  tenants: ["tenants"] as const,
  alerts: ["alerts"] as const,
  automation: ["automation"] as const,
  releases: ["releases"] as const,
  releasePolicy: ["releases", "policy"] as const,
  releaseGuide: (version: string) => ["releases", "guide", version] as const,
};
