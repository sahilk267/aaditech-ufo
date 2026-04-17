import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DashboardPage } from "../dashboard/DashboardPage";

vi.mock("../../lib/api", () => ({
  getApiStatus: vi.fn(() => Promise.resolve({ status: "ok", version: "1.0.0" })),
  getSystems: vi.fn(() => Promise.resolve({ systems: [], count: 0 })),
  getDashboardStatus: vi.fn(() => Promise.resolve({ dashboard: { aggregate_health: { overall_status: "healthy" } }, cache_hit: true })),
}));

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

describe("DashboardPage", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  it("renders dashboard header actions and main status cards", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <DashboardPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Refresh dashboard/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Reset host/i })).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.queryByText(/Loading…/i)).not.toBeInTheDocument();
    });

    expect(screen.getByText(/Live operational overview/i)).toBeInTheDocument();
    expect(screen.getAllByText(/API/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Systems/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Aggregate Health/i)).toBeInTheDocument();
  });
});
