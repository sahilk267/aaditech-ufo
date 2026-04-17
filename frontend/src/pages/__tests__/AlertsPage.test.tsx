import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AlertsPage } from "../alerts/AlertsPage";

vi.mock("../../lib/api", () => {
  return {
    createAlertRule: vi.fn(),
    createIncidentComment: vi.fn(),
    dispatchAlerts: vi.fn(),
    evaluateAlerts: vi.fn(),
    getAlertDelivery: vi.fn(() => Promise.resolve({ status: "success", deliveries: [], total: 0, pages: 0, page: 1, per_page: 0 })),
    getAlertDeliveryHistory: vi.fn(() => Promise.resolve({ status: "success", deliveries: [], total: 0, pages: 0, page: 1, per_page: 0 })),
    getAlertRules: vi.fn(() => Promise.resolve({ status: "success", rules: [] })),
    getAlertSilences: vi.fn(() => Promise.resolve({ status: "success", silences: [] })),
    getIncident: vi.fn(() => Promise.resolve({ status: "success", incident: { id: 1, title: "Test Incident", status: "open", severity: "critical", hostname: null, assigned_to_user_id: null, resolution_summary: null, last_seen_at: null } })),
    getIncidentComments: vi.fn(() => Promise.resolve({ status: "success", count: 0, comments: [] })),
    getIncidents: vi.fn(() => Promise.resolve({ status: "success", incidents: [], total: 0, pages: 0, page: 1, per_page: 0 })),
    getTenantControls: vi.fn(() => Promise.resolve({ status: "success", tenant_controls: { effective: { entitlements: { case_management_v1: { enabled: true } }, feature_flags: { incident_case_management_v1: { enabled: true } } } } })),
    openEventStream: vi.fn(() => ({ close: vi.fn() })),
    prioritizeAlerts: vi.fn(),
    redeliverAlertDelivery: vi.fn(),
    updateIncident: vi.fn(),
  };
});

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

describe("AlertsPage", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  it("renders header action buttons and basic alert sections", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <AlertsPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Refresh alerts/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Reset view/i })).toBeInTheDocument();
    });

    expect(screen.getByText(/Live rule management and evaluation flow/i)).toBeInTheDocument();
    expect(screen.getByText(/Live feed status:/i)).toBeInTheDocument();
  });
});
