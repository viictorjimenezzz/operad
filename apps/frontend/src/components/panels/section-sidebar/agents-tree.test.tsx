import { AgentsTree } from "@/components/panels/section-sidebar/agents-tree";
import type { AgentGroupSummary } from "@/lib/types";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

const useAgentGroupsMock = vi.fn();

vi.mock("@/hooks/use-runs", () => ({
  useAgentGroups: () => useAgentGroupsMock(),
}));

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}

function renderTree(initialPath = "/agents") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route
          path="/agents"
          element={
            <>
              <AgentsTree search="" />
              <LocationProbe />
            </>
          }
        />
        <Route
          path="/agents/:hashContent"
          element={
            <>
              <AgentsTree search="" />
              <LocationProbe />
            </>
          }
        />
        <Route
          path="/agents/:hashContent/runs/:runId"
          element={
            <>
              <AgentsTree search="" />
              <LocationProbe />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

function sampleGroup(overrides: Partial<AgentGroupSummary> = {}): AgentGroupSummary {
  return {
    hash_content: "abc123hash",
    class_name: "research_analyst",
    root_agent_path: "Root.research_analyst",
    count: 1,
    running: 0,
    errors: 0,
    last_seen: 1_700_000_100,
    first_seen: 1_700_000_000,
    latencies: [22, 25, 20],
    prompt_tokens: 10,
    completion_tokens: 20,
    cost_usd: 0.03,
    run_ids: ["run-001"],
    is_trainer: false,
    notes_markdown_count: 0,
    ...overrides,
  };
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("<AgentsTree />", () => {
  it("renders instance -> invocation rows and routes each level", async () => {
    useAgentGroupsMock.mockReturnValue({
      data: [sampleGroup()],
      isLoading: false,
    });

    renderTree();

    expect(screen.getByText("research_analyst")).toBeTruthy();
    expect(screen.getByText("abc123hash")).toBeTruthy();
    expect(screen.getByText("run-001")).toBeTruthy();

    fireEvent.click(screen.getByText("research_analyst"));
    await waitFor(() => {
      expect(screen.getByTestId("location").textContent).toBe("/agents/abc123hash");
    });

    fireEvent.click(screen.getByText("run-001"));
    await waitFor(() => {
      expect(screen.getByTestId("location").textContent).toBe("/agents/abc123hash/runs/run-001");
    });
  });
});
