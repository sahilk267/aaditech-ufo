import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Mock } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReleasesPage } from "../releases/ReleasesPage";

let mockGetAgentReleases: Mock;
let mockGetAgentReleasePolicy: Mock;

vi.mock("../../lib/api", () => {
  const getAgentReleases = vi.fn(() => Promise.resolve({ releases: [] }));
  const getAgentReleasePolicy = vi.fn(() => Promise.resolve({ policy: {} }));

  return {
    buildAgentBinary: vi.fn(() => Promise.resolve({ status: "success" })),
    downloadBuiltAgentBinary: vi.fn(() => Promise.resolve(new Blob())),
    getAgentBuildStatus: vi.fn(() => Promise.resolve({ build: {} })),
    getAgentReleaseGuide: vi.fn(() => Promise.resolve({ guide: {} })),
    getAgentReleasePolicy,
    getAgentReleases,
    setAgentReleasePolicy: vi.fn(() => Promise.resolve({ status: "success" })),
    uploadAgentRelease: vi.fn(() => Promise.resolve({ status: "success" })),
  };
});

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

  beforeEach(async () => {
    queryClient = createTestQueryClient();
    const api = await import("../../lib/api");
    mockGetAgentReleases = api.getAgentReleases as Mock;
    mockGetAgentReleasePolicy = api.getAgentReleasePolicy as Mock;
    mockGetAgentReleases.mockResolvedValue({ releases: [] });
    mockGetAgentReleasePolicy.mockResolvedValue({ policy: {} });
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

  it("shows copy URL action for release listings", async () => {
    mockGetAgentReleases.mockResolvedValue({
      count: 1,
      releases: [
        {
          version: "2.0.0",
          filename: "aaditech-agent-2.0.0.exe",
          size_bytes: 1024,
          modified_at: "2026-04-18T00:00:00Z",
          download_url: "/api/agent/releases/download/aaditech-agent-2.0.0.exe",
        },
      ],
    });

    const clipboardWriteText = vi.fn(() => Promise.resolve());
    Object.assign(navigator, {
      clipboard: {
        writeText: clipboardWriteText,
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ReleasesPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Copy URL/i })).toBeInTheDocument();
    });

    screen.getByRole("button", { name: /Copy URL/i }).click();
    await waitFor(() => {
      expect(clipboardWriteText).toHaveBeenCalledWith(
        "/api/agent/releases/download/aaditech-agent-2.0.0.exe"
      );
    });
  });
});
