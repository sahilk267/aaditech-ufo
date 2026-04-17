import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AutomationPage } from "../automation/AutomationPage";

vi.mock("../../lib/api", () => {
  return {
    createAutomationWorkflow: vi.fn(() => Promise.resolve({ status: "success" })),
    executeAutomationWorkflow: vi.fn(() => Promise.resolve({ status: "success" })),
    getAutomationServiceStatus: vi.fn(() => Promise.resolve({ status: "success", service: { name: "spooler", status: "running" } })),
    getAutomationWorkflows: vi.fn(() => Promise.resolve({ status: "success", workflows: [] })),
    getWorkflowRun: vi.fn(() => Promise.resolve({ status: "success", workflow_run: null })),
    getWorkflowRuns: vi.fn(() => Promise.resolve({ status: "success", workflow_runs: [] })),
    getScheduledJobs: vi.fn(() => Promise.resolve({ status: "success", scheduled_jobs: [] })),
    triggerSelfHealing: vi.fn(() => Promise.resolve({ status: "success" })),
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

describe("AutomationPage", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  it("renders module header actions and automation summary cards", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <AutomationPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Refresh automation state/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Reset form/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Self-Heal dry run/i })).toBeInTheDocument();
    });

    expect(screen.getByText(/Workflow execution, service checks, and self-healing/i)).toBeInTheDocument();
  });
});
