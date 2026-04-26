import { HookBadge } from "@/components/agent-view/graph/hook-badge";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("HookBadge", () => {
  it("renders active and inactive labels with doc tooltip", () => {
    render(
      <div>
        <HookBadge label="forward_in" active doc="input doc" />
        <HookBadge label="forward_out" active={false} doc="output doc" />
      </div>,
    );

    expect(screen.getByText("forward_in").getAttribute("title")).toBe("input doc");
    expect(screen.getByText("forward_out").getAttribute("title")).toBe("output doc");
  });
});
