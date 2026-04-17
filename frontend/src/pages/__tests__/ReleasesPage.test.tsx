import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReleasesPage } from "../releases/ReleasesPage";

vi.mock("../../lib/api", () => ({
  buildAgentBinary: vi.fn(() => Promise.resolve({ status: "success" })),
  downloadBuiltAgentBinary: vi.fn(() => Promise.resolve(new Blob())),
  getAgentBuildStatus: vi.fn(() => Promise.resolve({ build: {} })),
  getAgentReleaseGuide: vi.fn(() => Promise.resolve({ guide: {} })),
  getAgentReleasePolicy: vi.fn(() => Promise.resolve({ policy: {} })),
  getAgentReleases: vi.fn(() => Promise.resolve({ releases: [] })),
  setAgentReleasePolicy: vi.fn(() => Promise.resolve({ status: "success" })),
  uploadAgentRelease: vi.fn(() => Promise.resolve({ status: "success" })),
}));

vi.mock("../../store/authStore", () => ({
  useAuthStore: (selector: unknown) => (selector as any)({ user: { permissions: [] } }),
}));

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

describe("ReleasesPage", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  it("renders release header actions and upload form", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <ReleasesPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Refresh releases/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Reset releases view/i })).toBeInTheDocument();
    });

    expect(screen.getByText(/Release upload, policy, and guide workflows/i)).toBeInTheDocument();
  });
});
