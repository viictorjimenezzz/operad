import { ParametersPanel } from "@/components/agent-view/graph/parameters-panel";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => cleanup());

describe("ParametersPanel", () => {
  it("renders empty state", () => {
    render(<ParametersPanel agentPath="Root" data={{ agent_path: "Root", parameters: [] }} onOpenGradient={vi.fn()} />);
    expect(screen.getByText(/no trainable parameters/i)).toBeTruthy();
  });

  it("renders parameters and opens gradients drawer callback", () => {
    const onOpenGradient = vi.fn();
    render(
      <ParametersPanel
        agentPath="Root"
        data={{
          agent_path: "Root",
          parameters: [
            {
              path: "role",
              type: "TextParameter",
              value: "You are concise.",
              requires_grad: true,
              grad: { message: "be stricter", severity: 0.4, target_paths: ["role"], by_field: {} },
              constraint: null,
            },
          ],
        }}
        onOpenGradient={onOpenGradient}
      />,
    );

    expect(screen.getByText("role")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "grad" }));
    expect(onOpenGradient).toHaveBeenCalledWith("role");
  });
});
