import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AiPage } from "../ai/AiPage";

vi.mock("../../lib/api", () => ({
  analyzeRootCause: vi.fn(() => Promise.resolve({ status: "success" })),
  generateAiRecommendations: vi.fn(() => Promise.resolve({ status: "success" })),
  getAiOperationsReport: vi.fn(() => Promise.resolve({ report: { summary: { total_events: 0, success_rate: 0, success_count: 0, failure_count: 0, fallback_count: 0, avg_duration_ms: 0 }, counts: { by_action: {}, by_adapter: {}, by_primary_error_reason: {} }, recent_operations: [], recent_failures: [] } })),
  runOllamaInference: vi.fn(() => Promise.resolve({ status: "success" })),
}));

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

describe("AiPage", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  it("renders AI header actions and status cards", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <AiPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Refresh AI report/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Reset AI inputs/i })).toBeInTheDocument();
    });

    expect(screen.getByText(/Inference, root-cause analysis/i)).toBeInTheDocument();
    await screen.findByText(/AI events/i);
  });
});
