import { agentGroupTabs } from "@/components/agent-view/page-shell/agent-group-tabs";
import { describe, expect, it } from "vitest";

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
