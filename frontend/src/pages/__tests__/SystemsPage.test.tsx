import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SystemsPage } from "../systems/SystemsPage";

vi.mock("../../lib/api", () => ({
  getSystems: vi.fn(() =>
    Promise.resolve({
      count: 1,
      systems: [
        {
          id: 1,
          hostname: "host1",
          status: "active",
          last_update: "2026-04-16T12:00:00Z",
          serial_number: "SN-001",
        },
      ],
    })
  ),
  getSystem: vi.fn(() =>
    Promise.resolve({
      system: {
        id: 1,
        hostname: "host1",
        status: "active",
        serial_number: "SN-001",
        last_update: "2026-04-16T12:00:00Z",
      },
    })
  ),
  submitManualSystemData: vi.fn(() => Promise.resolve({ message: "Manual submit complete" })),
}));

vi.mock("../../store/authStore", () => ({
  useAuthStore: () => [],
}));

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

describe("SystemsPage", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  it("renders systems header actions and inventory table", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <SystemsPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Refresh systems/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Reset view/i })).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText(/Systems \(1\)/i)).toBeInTheDocument();
      expect(screen.getByText(/host1/i)).toBeInTheDocument();
      expect(screen.getByText(/Selected System Detail/i)).toBeInTheDocument();
    });
  });
});
