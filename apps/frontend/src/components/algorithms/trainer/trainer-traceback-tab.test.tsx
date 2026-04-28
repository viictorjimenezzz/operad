import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { TrainerTracebackTab } from "./trainer-traceback-tab";

afterEach(cleanup);

describe("TrainerTracebackTab", () => {
  it("renders the required empty state when traceback path is missing", () => {
    render(<TrainerTracebackTab runId="run-1" dataSummary={{ has_traceback: false }} />);

    expect(screen.getByText("no traceback recorded")).toBeTruthy();
    expect(
      screen.getByText(
        "this run did not save a PromptTraceback; see PromptTraceback.save() in your training script",
      ),
    ).toBeTruthy();
  });
});
