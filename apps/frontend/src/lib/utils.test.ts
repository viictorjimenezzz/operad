import {
  cn,
  formatCost,
  formatDurationMs,
  formatNumber,
  formatRelativeTime,
  formatTokens,
  truncateMiddle,
} from "@/lib/utils";
import { describe, expect, it } from "vitest";

describe("cn()", () => {
  it("merges + dedups Tailwind classes", () => {
    expect(cn("p-2", "p-4")).toBe("p-4");
    expect(cn("text-muted", false && "hidden", "font-mono")).toBe("text-muted font-mono");
  });
});

describe("formatNumber()", () => {
  it("returns em-dash for nullish", () => {
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber(undefined)).toBe("—");
    expect(formatNumber(Number.NaN)).toBe("—");
  });
  it("compacts thousands and millions", () => {
    expect(formatNumber(1500)).toBe("1.5k");
    expect(formatNumber(2_500_000)).toBe("2.5M");
    expect(formatNumber(42)).toBe("42");
    expect(formatNumber(3.14)).toBe("3.14");
  });
});

describe("formatTokens()", () => {
  it("rounds and compacts", () => {
    expect(formatTokens(0)).toBe("0");
    expect(formatTokens(1234)).toBe("1.2k");
    expect(formatTokens(2_500_000)).toBe("2.50M");
  });
});

describe("formatCost()", () => {
  it("scales precision to magnitude", () => {
    expect(formatCost(0)).toBe("$0.00");
    expect(formatCost(0.0009)).toBe("$0.0009");
    expect(formatCost(0.45)).toBe("$0.450");
    expect(formatCost(12.345)).toBe("$12.35");
  });
});

describe("formatDurationMs()", () => {
  it("scales unit to magnitude", () => {
    expect(formatDurationMs(0.5)).toBe("<1ms");
    expect(formatDurationMs(45)).toBe("45ms");
    expect(formatDurationMs(1_500)).toBe("1.5s");
    expect(formatDurationMs(75_000)).toBe("1m15s");
    expect(formatDurationMs(3_750_000)).toBe("1h02m");
  });
});

describe("formatRelativeTime()", () => {
  it("prints contextual delta", () => {
    const now = 1_000;
    expect(formatRelativeTime(1_000, now)).toBe("just now");
    expect(formatRelativeTime(995, now)).toBe("5s ago");
    expect(formatRelativeTime(940, now)).toBe("1m ago");
    expect(formatRelativeTime(0, now)).toBe("16m ago");
  });
});

describe("truncateMiddle()", () => {
  it("ellipsizes long strings in the middle", () => {
    expect(truncateMiddle("abcdef", 10)).toBe("abcdef");
    expect(truncateMiddle("0123456789abcdef", 9)).toBe("0123…cdef");
  });
});
