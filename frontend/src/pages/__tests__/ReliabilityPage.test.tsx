import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReliabilityPage } from "../reliability/ReliabilityPage";

vi.mock("../../lib/api", () => ({
  analyzeReliabilityTrend: vi.fn(() => Promise.resolve({ status: "success" })),
  analyzeStackTraces: vi.fn(() => Promise.resolve({ status: "success" })),
  collectReliabilityHistory: vi.fn(() => Promise.resolve({ status: "success" })),
  detectPatterns: vi.fn(() => Promise.resolve({ status: "success" })),
  getReliabilityReport: vi.fn(() => Promise.resolve({ status: "success", report: { total_runs_considered: 0, latest_score: {}, latest_trend: {}, latest_prediction: {}, recent_failures: [], crash_related_runs: [] } })),
  getReliabilityRun: vi.fn(() => Promise.resolve({ reliability_run: null })),
  getReliabilityRuns: vi.fn(() => Promise.resolve({ status: "success", reliability_runs: [] })),
  identifyExceptions: vi.fn(() => Promise.resolve({ status: "success" })),
  parseCrashDumps: vi.fn(() => Promise.resolve({ status: "success" })),
  predictReliability: vi.fn(() => Promise.resolve({ status: "success" })),
  scoreReliability: vi.fn(() => Promise.resolve({ status: "success" })),
}));

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

describe("ReliabilityPage", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  it("renders reliability header actions and summary cards", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <ReliabilityPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Refresh reliability/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Reset view/i })).toBeInTheDocument();
    });

    expect(screen.getByText(/Operator-facing reliability diagnostics/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText(/Runs/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Latest Score/i)).toBeInTheDocument();
    });
  });
});
