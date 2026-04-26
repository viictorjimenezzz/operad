import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { MultiPromptDiff, _multiPromptDiff } from "./multi-prompt-diff";

afterEach(cleanup);

describe("MultiPromptDiff", () => {
  it("renders two-way diff for N=2", () => {
    render(
      <MultiPromptDiff
        prompts={[
          { runId: "a", label: "run a", text: "alpha\nbeta" },
          { runId: "b", label: "run b", text: "alpha\ngamma" },
        ]}
      />,
    );

    expect(screen.getByText("run a")).toBeTruthy();
    expect(screen.getByText("run b")).toBeTruthy();
  });

  it("highlights consensus tokens for N=3", () => {
    render(
      <MultiPromptDiff
        prompts={[
          { runId: "a", label: "run a", text: "keep this token" },
          { runId: "b", label: "run b", text: "keep another" },
          { runId: "c", label: "run c", text: "unique value" },
        ]}
      />,
    );

    expect(screen.getAllByText("keep").length).toBeGreaterThanOrEqual(2);
  });

  it("consensus set keeps tokens seen in >=2 columns", () => {
    const set = _multiPromptDiff.consensusTokenSet([
      { runId: "a", label: "a", text: "one two" },
      { runId: "b", label: "b", text: "two three" },
      { runId: "c", label: "c", text: "four" },
    ]);

    expect(set.has("two")).toBe(true);
    expect(set.has("one")).toBe(false);
    expect(set.has("four")).toBe(false);
  });
});
