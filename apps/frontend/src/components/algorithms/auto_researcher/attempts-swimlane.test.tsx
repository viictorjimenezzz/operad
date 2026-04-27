import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { AttemptsSwimlane } from "./attempts-swimlane";

afterEach(cleanup);

const data = {
  iterations: [
    { iter_index: 0, phase: "reason", score: 0.71, text: null, metadata: { attempt_index: 0 } },
    { iter_index: 1, phase: "reflect", score: 0.71, text: null, metadata: { attempt_index: 0 } },
    { iter_index: 1, phase: "reason", score: 0.84, text: null, metadata: { attempt_index: 0 } },
    { iter_index: 0, phase: "reason", score: 0.55, text: null, metadata: { attempt_index: 1 } },
  ],
  max_iter: 2,
  threshold: 0.8,
  converged: null,
};

describe("<AttemptsSwimlane />", () => {
  it("renders per-attempt swimlanes and pins attempts", () => {
    render(
      <MemoryRouter>
        <AttemptsSwimlane data={data} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Attempt #1")).toBeDefined();
    expect(screen.getByText("Attempt #2")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Attempt 2" }));
    expect(screen.getByText("?attempt=1")).toBeDefined();
  });

  it("explains legacy events without attempt_index", () => {
    render(
      <MemoryRouter>
        <AttemptsSwimlane
          data={{
            ...data,
            iterations: [{ iter_index: 0, phase: "reason", score: 0.6, text: null, metadata: {} }],
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("attempt index missing")).toBeDefined();
    expect(screen.getByText("Attempt unknown")).toBeDefined();
  });
});
