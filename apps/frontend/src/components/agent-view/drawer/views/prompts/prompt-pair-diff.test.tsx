import { PromptPairDiff, _promptPairDiff } from "@/components/agent-view/drawer/views/prompts/prompt-pair-diff";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("PromptPairDiff", () => {
  it("chooses line strategy for rules/examples blocks", () => {
    expect(_promptPairDiff.chooseDiffStrategy("<rules>a</rules>", "<rules>b</rules>")).toBe("line");
  });

  it("parses chat and renders turn cards", () => {
    render(
      <PromptPairDiff
        mode="side-by-side"
        before='[{"role":"system","content":"old"}]'
        after='[{"role":"system","content":"new"}]'
      />,
    );
    expect(screen.getAllByText(/system/i).length).toBeGreaterThan(0);
  });

  it("falls back to raw diff when chat parsing fails", () => {
    render(<PromptPairDiff mode="inline" before='[{"role":"system"}]' after="plain" />);
    expect(screen.getByText(/plain/i)).toBeTruthy();
  });
});
