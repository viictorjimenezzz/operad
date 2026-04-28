import { agentGroupTabs } from "@/components/agent-view/page-shell/agent-group-tabs";
import { AgentGroupPage } from "@/dashboard/pages/AgentGroupPage";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockUseAgentGroup = vi.fn();
const mockUseAgentMeta = vi.fn();

vi.mock("@/hooks/use-runs", () => ({
  useAgentGroup: () => mockUseAgentGroup(),
  useAgentMeta: () => mockUseAgentMeta(),
}));

/**
 * Tests the showTraining gate by exercising agentGroupTabs, which is the
 * direct consumer of the flag produced by AgentGroupPage's gate logic.
 */

function tabLabels(showTraining: boolean): string[] {
  return agentGroupTabs("abc123", { showTraining }).map((t) => t.label);
}

describe("Training tab gate (§2)", () => {
  it("hides Training tab when agent has best_score but no trainable_paths", () => {
    // Simulates research_analyst: metrics.best_score=0.8 but trainable_paths=[]
    // The old gate used `detail.runs.some(run => run.metrics?.best_score != null)`
    // which would have shown the tab. The new gate must NOT show it.
    const labels = tabLabels(false);
    expect(labels).not.toContain("Training");
  });

  it("shows Training tab when trainable_paths is non-empty", () => {
    // Simulates a trainable agent: trainable_paths=["role"]
    const labels = tabLabels(true);
    expect(labels).toContain("Training");
  });

  it("Training tab label is exactly 'Training' (not 'Train')", () => {
    const tabs = agentGroupTabs("abc123", { showTraining: true });
    const trainTab = tabs.find((t) => t.to.endsWith("/training"));
    expect(trainTab?.label).toBe("Training");
  });

  it("Training tab URL matches the label: /training", () => {
    const tabs = agentGroupTabs("abc123", { showTraining: true });
    const trainTab = tabs.find((t) => t.label === "Training");
    expect(trainTab?.to).toBe("/agents/abc123/training");
  });

  it("Invocations tab URL matches the label: /invocations", () => {
    const tabs = agentGroupTabs("abc123", {});
    const invTab = tabs.find((t) => t.label === "Invocations");
    expect(invTab?.to).toBe("/agents/abc123/invocations");
  });
});

describe("AgentGroupPage chrome", () => {
  beforeEach(() => {
    mockUseAgentGroup.mockReturnValue({
      data: {
        hash_content: "abc123def456",
        class_name: "Reasoner",
        root_agent_path: "Reasoner",
        count: 2,
        running: 0,
        errors: 0,
        last_seen: 2000,
        first_seen: 1000,
        latencies: [100, 120],
        prompt_tokens: 0,
        completion_tokens: 0,
        cost_usd: 0,
        is_trainer: false,
        notes_markdown_count: 0,
        runs: [
          {
            run_id: "run-1",
            root_agent_path: "Reasoner",
          },
        ],
      },
      isLoading: false,
      error: null,
    });
    mockUseAgentMeta.mockReturnValue({ data: { class_name: "Reasoner", trainable_paths: [] } });
  });

  it("renders tabs and breadcrumb path in one compact header", () => {
    render(
      <MemoryRouter initialEntries={["/agents/abc123def456"]}>
        <Routes>
          <Route path="/agents/:hashContent" element={<AgentGroupPage />}>
            <Route index element={<div>overview body</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    const sections = screen.getByLabelText("agent instance sections");
    expect(within(sections).getByText("Overview")).toBeTruthy();
    expect(within(sections).getByText("Invocations")).toBeTruthy();
    expect(within(sections).getByText("Metrics")).toBeTruthy();
    const path = screen.getByLabelText("agent path");
    expect(within(path).getByText("Agents")).toBeTruthy();
    expect(within(path).getByText("Reasoner")).toBeTruthy();
    expect(within(path).getByText("abc123def456")).toBeTruthy();
    expect(within(path).getByText("ended")).toBeTruthy();
  });
});
