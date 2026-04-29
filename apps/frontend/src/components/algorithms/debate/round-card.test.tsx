import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { RoundCard } from "./round-card";

afterEach(cleanup);

const round = {
  round_index: 0,
  proposals: [
    { author: "Proposer A", content: "Alpha answer" },
    { author: "Proposer B", content: "Beta answer" },
    { author: "Proposer C", content: "Gamma answer" },
  ],
  critiques: [
    { target_author: "Proposer A", comments: "needs more detail", score: 0.61 },
    { target_author: "Proposer B", comments: "good but tangential", score: 0.74 },
    { target_author: "Proposer C", comments: "off-topic", score: 0.52 },
  ],
  scores: [0.61, 0.74, 0.52],
  timestamp: 1,
};

function renderRoundCard(element: ReactElement) {
  return render(
    <table>
      <tbody>{element}</tbody>
    </table>,
  );
}

describe("<RoundCard />", () => {
  it("renders compact proposal cells and critic score controls", () => {
    renderRoundCard(<RoundCard round={round} roundNumber={1} proposerCount={3} />);

    expect(screen.getByText("Round 1")).toBeDefined();
    expect(screen.getByText("Alpha answer")).toBeDefined();
    expect(
      screen.getByRole("button", { name: "show critic reasoning for Proposal 1" }),
    ).toBeDefined();
    expect(screen.queryByText("Proposer A")).toBeNull();
  });

  it("toggles a proposal cell between proposal text and critic reasoning", () => {
    renderRoundCard(<RoundCard round={round} roundNumber={1} proposerCount={3} />);

    fireEvent.click(screen.getByRole("button", { name: "show critic reasoning for Proposal 1" }));

    expect(screen.getByText("needs more detail")).toBeDefined();
    expect(screen.queryByText("Alpha answer")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "show proposal for Proposal 1" }));

    expect(screen.getByText("Alpha answer")).toBeDefined();
    expect(screen.queryByText("needs more detail")).toBeNull();
  });

  it("expands a row and focuses a clicked proposal cell without using the score button", () => {
    renderRoundCard(<RoundCard round={round} roundNumber={1} proposerCount={3} />);

    const row = screen.getByText("Round 1").closest("tr");
    if (!row) throw new Error("expected round row");
    expect(row?.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(row);
    expect(row?.getAttribute("aria-expanded")).toBe("true");

    const cell = screen.getByRole("cell", { name: "Round 1 Proposal 1" });
    expect(cell.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(cell);
    expect(row?.getAttribute("aria-expanded")).toBe("true");
    expect(cell.getAttribute("aria-expanded")).toBe("true");

    fireEvent.click(screen.getByRole("button", { name: "show critic reasoning for Proposal 2" }));
    expect(screen.getByText("good but tangential")).toBeDefined();
    expect(cell.getAttribute("aria-expanded")).toBe("true");
  });

  it("preserves empty columns for missing proposals", () => {
    renderRoundCard(
      <RoundCard
        round={{ ...round, proposals: round.proposals.slice(0, 2) }}
        roundNumber={1}
        proposerCount={3}
      />,
    );

    expect(screen.getByText("No proposal recorded.")).toBeDefined();
  });
});
