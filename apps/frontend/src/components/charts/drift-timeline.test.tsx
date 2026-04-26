import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { DriftTimeline } from "./drift-timeline";

afterEach(cleanup);

const entries = [
  {
    epoch: 0,
    before_text: "old role",
    after_text: "new role",
    selected_path: "role",
    changes: [{ path: "role", before_text: "old role", after_text: "new role" }],
    changed_params: ["role"],
    delta_count: 1,
    critique: "tighten role",
    gradient_epoch: 0,
    gradient_batch: 1,
    timestamp: 1,
  },
  {
    epoch: 1,
    before_text: "rule a",
    after_text: "rule b",
    selected_path: "rules[0]",
    changes: [
      { path: "rules[0]", before_text: "rule a", after_text: "rule b" },
      { path: "task", before_text: "task a", after_text: "task b" },
    ],
    changed_params: ["rules[0]", "task"],
    delta_count: 2,
    critique: "be specific",
    gradient_epoch: 1,
    gradient_batch: 2,
    timestamp: 2,
  },
];

describe("DriftTimeline", () => {
  it("renders empty state when missing", () => {
    render(<DriftTimeline data={undefined} />);
    expect(screen.getByText("no drift events")).toBeTruthy();
  });

  it("defaults to latest epoch and selected path", () => {
    render(<DriftTimeline data={entries} />);
    expect(screen.getByText("critique (rules[0])")).toBeTruthy();
    expect(screen.getByText("be specific")).toBeTruthy();
  });

  it("switches selected path", () => {
    render(<DriftTimeline data={entries} />);
    const selects = screen.getAllByRole("combobox");
    const second = selects[1];
    if (!second) throw new Error("expected second selector");
    fireEvent.change(second, { target: { value: "task" } });
    expect(screen.getByText("critique (task)")).toBeTruthy();
  });
});
