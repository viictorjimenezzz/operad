import { usePinnedRunsStore } from "@/stores/pinned-runs";
import { beforeEach, describe, expect, it } from "vitest";

beforeEach(() => {
  usePinnedRunsStore.getState().clear();
  localStorage.clear();
});

describe("usePinnedRunsStore", () => {
  it("pins a run and returns true", () => {
    const result = usePinnedRunsStore.getState().pin("run-1");
    expect(result).toBe(true);
    expect(usePinnedRunsStore.getState().pinned).toContain("run-1");
  });

  it("returns true pinning a duplicate without adding it again", () => {
    usePinnedRunsStore.getState().pin("run-1");
    const result = usePinnedRunsStore.getState().pin("run-1");
    expect(result).toBe(true);
    expect(usePinnedRunsStore.getState().pinned.length).toBe(1);
  });

  it("returns false and does not add when at cap of 20", () => {
    for (let i = 0; i < 20; i++) {
      usePinnedRunsStore.getState().pin(`run-${i}`);
    }
    const result = usePinnedRunsStore.getState().pin("run-overflow");
    expect(result).toBe(false);
    expect(usePinnedRunsStore.getState().pinned).not.toContain("run-overflow");
    expect(usePinnedRunsStore.getState().pinned.length).toBe(20);
  });

  it("unpins a run", () => {
    usePinnedRunsStore.getState().pin("run-1");
    usePinnedRunsStore.getState().unpin("run-1");
    expect(usePinnedRunsStore.getState().pinned).not.toContain("run-1");
  });

  it("toggle pins an unpinned run", () => {
    usePinnedRunsStore.getState().toggle("run-1");
    expect(usePinnedRunsStore.getState().pinned).toContain("run-1");
  });

  it("toggle unpins a pinned run", () => {
    usePinnedRunsStore.getState().pin("run-1");
    usePinnedRunsStore.getState().toggle("run-1");
    expect(usePinnedRunsStore.getState().pinned).not.toContain("run-1");
  });

  it("isPinned returns correct boolean", () => {
    expect(usePinnedRunsStore.getState().isPinned("run-1")).toBe(false);
    usePinnedRunsStore.getState().pin("run-1");
    expect(usePinnedRunsStore.getState().isPinned("run-1")).toBe(true);
  });

  it("clear empties all pinned runs", () => {
    usePinnedRunsStore.getState().pin("run-1");
    usePinnedRunsStore.getState().pin("run-2");
    usePinnedRunsStore.getState().clear();
    expect(usePinnedRunsStore.getState().pinned.length).toBe(0);
  });

  it("persists to localStorage", () => {
    usePinnedRunsStore.getState().pin("run-persist");
    const raw = localStorage.getItem("operad:pinned-runs:v1");
    expect(raw).not.toBeNull();
    if (raw === null) throw new Error("expected pinned-runs localStorage payload");
    const parsed = JSON.parse(raw);
    expect(parsed.state.pinned).toContain("run-persist");
  });
});
