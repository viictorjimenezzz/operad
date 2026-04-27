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
  it("renders one round card per round", () => {
    renderWithRouter();

    expect(screen.getAllByText("Round 1").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Round 2").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Round 3").length).toBeGreaterThan(0);
  });

  it("reads and updates the round query param", () => {
    renderWithRouter("/?round=2");

    expect(screen.getByText("?round=2")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Round 3" }));
    expect(screen.getByText("?round=3")).toBeDefined();
  });
});
