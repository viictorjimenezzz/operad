import { AgentGroupGraphTab } from "@/dashboard/pages/AgentGroupGraphTab";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  graphPage: vi.fn(),
  useAgentGroup: vi.fn(),
}));

vi.mock("@/components/agent-view/graph/graph-page", () => ({
  GraphPage: ({ runId }: { runId: string }) => {
    mocks.graphPage(runId);
    return <div data-testid="graph-run">{runId}</div>;
  },
}));

vi.mock("@/hooks/use-runs", () => ({
  useAgentGroup: mocks.useAgentGroup,
}));

function renderGraph() {
  return render(
    <MemoryRouter initialEntries={["/agents/hash-1/graph"]}>
      <Routes>
        <Route path="/agents/:hashContent/graph" element={<AgentGroupGraphTab />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AgentGroupGraphTab", () => {
  afterEach(cleanup);

  beforeEach(() => {
    mocks.graphPage.mockClear();
    mocks.useAgentGroup.mockReset();
  });

  it("uses the newest graph-capable run for the parent graph", () => {
    mocks.useAgentGroup.mockReturnValue({
      data: {
        runs: [
          { run_id: "old-graph", started_at: 1, has_graph: true },
          { run_id: "new-no-graph", started_at: 3, has_graph: false },
          { run_id: "new-graph", started_at: 2, has_graph: true },
        ],
      },
    });

    renderGraph();

    expect(screen.getByTestId("graph-run").textContent).toBe("new-graph");
    expect(mocks.graphPage).toHaveBeenCalledWith("new-graph");
  });

  it("falls back to the newest run when no graph-capable run exists", () => {
    mocks.useAgentGroup.mockReturnValue({
      data: {
        runs: [
          { run_id: "old-run", started_at: 1, has_graph: false },
          { run_id: "new-run", started_at: 2, has_graph: false },
        ],
      },
    });

    renderGraph();

    expect(screen.getByTestId("graph-run").textContent).toBe("new-run");
  });
});
