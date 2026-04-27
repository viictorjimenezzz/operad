import { SERIES_PALETTE, hashColor, paletteIndex } from "@/lib/hash-color";
import { describe, expect, it } from "vitest";

describe("hashColor", () => {
  it("returns the contracted qualitative palette token", () => {
    expect(hashColor(null)).toBe("var(--qual-7)");
    expect(hashColor("agent-a")).toMatch(/^var\(--qual-(?:[1-9]|1[0-2])\)$/);
    expect(SERIES_PALETTE).toHaveLength(12);
  });

  it("is deterministic across calls", () => {
    expect(hashColor("same-agent")).toBe(hashColor("same-agent"));
    expect(paletteIndex("same-agent")).toBe(paletteIndex("same-agent"));
  });

  it("usually separates nearby identities across the modulo palette", () => {
    expect(hashColor("agent-a")).not.toBe(hashColor("agent-b"));
  });
});
