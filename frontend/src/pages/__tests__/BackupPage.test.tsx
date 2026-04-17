import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BackupPage } from "../backup/BackupPage";

vi.mock("../../lib/api", () => ({
  createBackup: vi.fn(() => Promise.resolve({ status: "success" })),
  getBackups: vi.fn(() => Promise.resolve({ backups: [] })),
  restoreBackup: vi.fn(() => Promise.resolve({ status: "success" })),
}));

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

describe("BackupPage", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  it("renders backup header actions and backup list section", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <BackupPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Refresh backups/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Reset backup view/i })).toBeInTheDocument();
    });

    expect(screen.getByText(/Manage database backups/i)).toBeInTheDocument();
    await screen.findByRole("heading", { name: /Available Backups/i });
  });
});
