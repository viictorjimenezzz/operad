import { afterEach, describe, expect, it } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

afterEach(cleanup);
import { GradientLog } from "./gradient-log";

const mockEntries = [
  {
    epoch: 1,
    batch: 3,
    message: "role is too vague",
    severity: "medium",
    target_paths: ["role"],
    by_field: { role: "needs more specificity" },
    applied_diff: "- old\n+ new",
  },
  {
    epoch: 0,
    batch: 5,
    message: "task ambiguous",
    severity: "high",
    target_paths: ["task", "rules"],
    by_field: {},
    applied_diff: "",
  },
];

describe("GradientLog", () => {
  it("renders empty state when data is missing", () => {
    render(<GradientLog data={undefined} />);
    expect(screen.getByText("no gradient events")).toBeTruthy();
  });

  it("renders empty state when data is empty array", () => {
    render(<GradientLog data={[]} />);
    expect(screen.getByText("no gradient events")).toBeTruthy();
  });

  it("renders gradient entries sorted newest-first", () => {
    render(<GradientLog data={mockEntries} />);
    const items = screen.getAllByRole("listitem");
    // epoch 1 should appear before epoch 0 (newest first)
    expect(items[0].textContent).toContain("epoch 1");
    expect(items[1].textContent).toContain("epoch 0");
  });

  it("shows severity badge", () => {
    render(<GradientLog data={mockEntries} />);
    expect(screen.getByText("medium")).toBeTruthy();
    expect(screen.getByText("high")).toBeTruthy();
  });

  it("shows target_paths chips", () => {
    render(<GradientLog data={mockEntries} />);
    expect(screen.getByText("role")).toBeTruthy();
    expect(screen.getByText("task")).toBeTruthy();
  });

  it("filters entries by message text", () => {
    render(<GradientLog data={mockEntries} />);
    const input = screen.getByPlaceholderText("filter by message or field…");
    fireEvent.change(input, { target: { value: "vague" } });
    expect(screen.getByText("role is too vague")).toBeTruthy();
    expect(screen.queryByText("task ambiguous")).toBeNull();
  });

  it("filters entries by target_path", () => {
    render(<GradientLog data={mockEntries} />);
    const input = screen.getByPlaceholderText("filter by message or field…");
    fireEvent.change(input, { target: { value: "rules" } });
    expect(screen.getByText("task ambiguous")).toBeTruthy();
    expect(screen.queryByText("role is too vague")).toBeNull();
  });
});
