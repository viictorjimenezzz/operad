import { afterEach, describe, expect, it } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

afterEach(cleanup);
import { CheckpointTimeline } from "./checkpoint-timeline";

const mockEntries = [
  { epoch: 0, train_loss: 0.9, val_loss: 0.95, score: 0.95, is_best: false },
  { epoch: 1, train_loss: 0.6, val_loss: 0.62, score: 0.62, is_best: true },
  { epoch: 2, train_loss: 0.7, val_loss: 0.72, score: 0.72, is_best: false },
];

describe("CheckpointTimeline", () => {
  it("renders empty state when data is missing", () => {
    render(<CheckpointTimeline data={undefined} />);
    expect(screen.getByText("no checkpoints yet")).toBeTruthy();
  });

  it("renders empty state when array is empty", () => {
    render(<CheckpointTimeline data={[]} />);
    expect(screen.getByText("no checkpoints yet")).toBeTruthy();
  });

  it("renders one row per checkpoint", () => {
    render(<CheckpointTimeline data={mockEntries} />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(3);
  });

  it("shows epoch labels", () => {
    render(<CheckpointTimeline data={mockEntries} />);
    expect(screen.getByText("epoch 0")).toBeTruthy();
    expect(screen.getByText("epoch 1")).toBeTruthy();
    expect(screen.getByText("epoch 2")).toBeTruthy();
  });

  it("shows best badge only on the best entry", () => {
    render(<CheckpointTimeline data={mockEntries} />);
    const bestBadges = screen.getAllByText("best");
    expect(bestBadges).toHaveLength(1);
    expect(bestBadges[0]!.closest("li")?.textContent).toContain("epoch 1");
  });

  it("shows val_loss when present", () => {
    render(<CheckpointTimeline data={mockEntries} />);
    expect(screen.getAllByText("val").length).toBeGreaterThan(0);
  });

  it("works when val_loss is null", () => {
    const entries = [{ epoch: 0, train_loss: 0.8, val_loss: null, score: 0.8, is_best: true }];
    render(<CheckpointTimeline data={entries} />);
    expect(screen.queryByText("val")).toBeNull();
    expect(screen.getByText("best")).toBeTruthy();
  });
});
