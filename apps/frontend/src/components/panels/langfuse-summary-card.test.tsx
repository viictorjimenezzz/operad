import { LangfuseSummaryCard } from "@/components/panels/langfuse-summary-card";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockUseManifest = vi.fn();

vi.mock("@/hooks/use-runs", () => ({
  useManifest: () => mockUseManifest(),
}));

const summaryData = {
  run_id: "run-1",
  started_at: 0,
  last_event_at: 0,
  state: "ended",
  has_graph: false,
  is_algorithm: false,
  algorithm_path: null,
  root_agent_path: null,
  event_total: 42,
  duration_ms: 1000,
  prompt_tokens: 100,
  completion_tokens: 50,
  event_counts: { agent_error: 2 },
  cost: { prompt_tokens: 100, completion_tokens: 50, cost_usd: 0.0042 },
  error: null,
  algorithm_terminal_score: null,
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe("<LangfuseSummaryCard />", () => {
  it("shows summary fields with valid data", () => {
    mockUseManifest.mockReturnValue({ data: null });
    render(<LangfuseSummaryCard runId="run-1" data={summaryData} />);
    expect(screen.getByText("42")).toBeDefined();
    expect(screen.getByText("$0.0042")).toBeDefined();
  });

  it("shows 'view in Langfuse' button when langfuseUrl is configured", () => {
    mockUseManifest.mockReturnValue({ data: { langfuseUrl: "http://lf.example" } });
    render(<LangfuseSummaryCard runId="run-1" data={summaryData} />);
    expect(screen.getByText("view in Langfuse →")).toBeDefined();
  });

  it("hides link button when langfuseUrl is null", () => {
    mockUseManifest.mockReturnValue({ data: { langfuseUrl: null } });
    render(<LangfuseSummaryCard runId="run-1" data={summaryData} />);
    expect(screen.queryByText("view in Langfuse →")).toBeNull();
  });

  it("hides link button when runId is null", () => {
    mockUseManifest.mockReturnValue({ data: { langfuseUrl: "http://lf.example" } });
    render(<LangfuseSummaryCard runId={null} data={summaryData} />);
    expect(screen.queryByText("view in Langfuse →")).toBeNull();
  });

  it("shows error count from event_counts", () => {
    mockUseManifest.mockReturnValue({ data: null });
    render(<LangfuseSummaryCard runId="run-1" data={summaryData} />);
    expect(screen.getByText("2")).toBeDefined();
  });

  it("renders dashes when data is invalid", () => {
    mockUseManifest.mockReturnValue({ data: null });
    render(<LangfuseSummaryCard runId="run-1" data={null} />);
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
  });

  it("external link icon rendered with configured langfuseUrl", () => {
    mockUseManifest.mockReturnValue({ data: { langfuseUrl: "http://lf.example" } });
    render(<LangfuseSummaryCard runId="run-1" data={summaryData} />);
    expect(screen.getByLabelText("Open trace in Langfuse")).toBeDefined();
  });
});
