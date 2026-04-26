import { AgentEdgePopup } from "@/components/agent-view/graph/agent-edge-popup";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

describe("AgentEdgePopup", () => {
  it("triggers edit-and-run action", () => {
    const onOpenExperiment = vi.fn();
    render(
      <AgentEdgePopup
        agentPath="Root.stage_0"
        meta={null}
        invocations={{ agent_path: "Root.stage_0", invocations: [] }}
        onOpenLangfuse={vi.fn()}
        onOpenEvents={vi.fn()}
        onOpenPrompts={vi.fn()}
        onOpenExperiment={onOpenExperiment}
        onClose={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /edit and run/i }));
    expect(onOpenExperiment).toHaveBeenCalledTimes(1);
  });
});
