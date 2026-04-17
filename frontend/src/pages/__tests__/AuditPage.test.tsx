import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuditPage } from "../audit/AuditPage";

vi.mock("../../lib/api", () => ({
  getAuditEvents: vi.fn(() => Promise.resolve({ status: "success", events: [], total: 0 })),
  getOperationsTimeline: vi.fn(() => Promise.resolve({ status: "success", count: 0, timeline: [] })),
  openEventStream: vi.fn(() => ({ close: vi.fn() })),
}));

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

describe("AuditPage", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  it("renders audit header actions and filter form", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <AuditPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Refresh timeline/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Reset filters/i })).toBeInTheDocument();
    });

    expect(screen.getByText(/Filter and query audit activity/i)).toBeInTheDocument();
    await screen.findByRole("button", { name: /Query Audit Events/i });
  });
});
