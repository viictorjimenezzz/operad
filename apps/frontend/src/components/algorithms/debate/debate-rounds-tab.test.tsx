import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { DebateRoundsTab } from "./debate-rounds-tab";

afterEach(cleanup);

const rounds = [0, 1, 2].map((roundIndex) => ({
  round_index: roundIndex,
  proposals: [
    { author: "Proposer A", content: `A round ${roundIndex + 1}` },
    { author: "Proposer B", content: `B round ${roundIndex + 1}` },
    { author: "Proposer C", content: `C round ${roundIndex + 1}` },
  ],
  critiques: [
    { target_author: "Proposer A", comments: "needs more detail", score: 0.61 },
    { target_author: "Proposer B", comments: "good but tangential", score: 0.74 },
    { target_author: "Proposer C", comments: "off-topic", score: 0.52 },
  ],
  scores: [0.61, 0.74, 0.52],
  timestamp: roundIndex + 1,
}));

function renderWithRouter(initialEntry = "/") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <DebateRoundsTab data={rounds} />
    </MemoryRouter>,
  );
}

describe("<DebateRoundsTab />", () => {
  it("renders one table row per unique round", () => {
    renderWithRouter();

    expect(screen.getByRole("table")).toBeTruthy();
    expect(screen.getByText("Proposal 1")).toBeTruthy();
    expect(screen.getByText("Proposal 2")).toBeTruthy();
    expect(screen.getByText("Proposal 3")).toBeTruthy();
    expect(screen.getAllByRole("row")).toHaveLength(4);
    expect(screen.getByText("Round 1")).toBeTruthy();
    expect(screen.getByText("Round 2")).toBeTruthy();
    expect(screen.getByText("Round 3")).toBeTruthy();
  });

  it("keeps proposal cells compact without visible per-cell proposer chrome", () => {
    renderWithRouter();

    expect(screen.queryByText("Proposer A")).toBeNull();
    expect(screen.queryByText("proposal")).toBeNull();
    expect(screen.getByText("A round 1")).toBeTruthy();
    expect(
      screen.getAllByRole("button", { name: "show critic reasoning for Proposal 1" }),
    ).toHaveLength(3);
  });

  it("uses one focused proposal column across the table", () => {
    renderWithRouter();

    const firstCell = screen.getByRole("cell", { name: "Round 1 Proposal 1" });
    const secondCell = screen.getByRole("cell", { name: "Round 2 Proposal 2" });

    fireEvent.click(firstCell);
    expect(firstCell.getAttribute("aria-expanded")).toBe("true");

    fireEvent.click(secondCell);
    expect(firstCell.getAttribute("aria-expanded")).toBe("false");
    expect(secondCell.getAttribute("aria-expanded")).toBe("true");
  });

  it("does not render pinned round controls from the query param", () => {
    renderWithRouter("/?round=2");

    expect(screen.queryByText("Pinned round")).toBeNull();
    expect(screen.queryByText("?round=2")).toBeNull();
    expect(screen.getByText("Round 2")).toBeTruthy();
  });

  it("deduplicates repeated streamed rounds by round_index", () => {
    const repeated = rounds[1];
    if (!repeated) throw new Error("expected repeated round fixture");

    render(
      <MemoryRouter>
        <DebateRoundsTab data={[...rounds, repeated]} />
      </MemoryRouter>,
    );

    expect(screen.getAllByText("Round 2")).toHaveLength(1);
  });
});
