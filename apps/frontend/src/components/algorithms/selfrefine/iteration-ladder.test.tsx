import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { IterationLadder } from "./iteration-ladder";

afterEach(cleanup);

const data = {
  iterations: [
    {
      iter_index: 0,
      phase: "reflect",
      score: 0.51,
      text: "draft 0",
      metadata: { needs_revision: true, critique_summary: "add examples" },
    },
    {
      iter_index: 1,
      phase: "refine",
      score: null,
      text: "draft 1",
      metadata: {},
    },
    {
      iter_index: 1,
      phase: "reflect",
      score: 0.62,
      text: "draft 1",
      metadata: { needs_revision: true, critique_summary: "tighten conclusion" },
    },
    {
      iter_index: 2,
      phase: "reflect",
      score: 0.74,
      text: "draft 2",
      metadata: { needs_revision: true, critique_summary: "cite sources" },
    },
    {
      iter_index: 3,
      phase: "reflect",
      score: 0.83,
      text: "draft 3",
      metadata: { needs_revision: false, critique_summary: "ready" },
    },
  ],
  max_iter: 5,
  threshold: 0.8,
  converged: true,
};

function renderWithRouter(initialEntry = "/") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <IterationLadder data={data} />
    </MemoryRouter>,
  );
}

describe("<IterationLadder />", () => {
  it("collapses older iterations by default and shows score delta", () => {
    renderWithRouter();

    expect(screen.getByText("draft 0")).toBeDefined();
    expect(screen.queryByText("draft 3")).toBeNull();
    expect(screen.getByText("+0.11")).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: /Iteration 3/ }));
    expect(screen.getByText("draft 3")).toBeDefined();
    expect(screen.getByText("converged here")).toBeDefined();
  });

  it("opens the pinned iteration from the URL", () => {
    renderWithRouter("/?iter=3");

    expect(screen.getByText("draft 3")).toBeDefined();
  });
});
