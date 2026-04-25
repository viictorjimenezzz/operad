import { LayoutSpec, resolvePath } from "@/lib/layout-schema";
import { describe, expect, it } from "vitest";

const minimal = {
  algorithm: "*",
  version: 1,
  dataSources: {
    summary: { endpoint: "/runs/$context.runId/summary" },
  },
  spec: {
    root: "page",
    elements: {
      page: { type: "Card", props: { title: "x" } },
    },
  },
};

describe("LayoutSpec", () => {
  it("accepts a minimal valid layout", () => {
    const layout = LayoutSpec.parse(minimal);
    expect(layout.spec.root).toBe("page");
    expect(layout.dataSources.summary?.endpoint).toMatch(/runId/);
  });

  it("rejects a non-1 version", () => {
    expect(() => LayoutSpec.parse({ ...minimal, version: 2 })).toThrow();
  });

  it("rejects elements without type", () => {
    expect(() =>
      LayoutSpec.parse({
        ...minimal,
        spec: { root: "page", elements: { page: { props: {} } } },
      }),
    ).toThrow();
  });
});

describe("resolvePath()", () => {
  it("substitutes $context.X", () => {
    expect(resolvePath("/runs/$context.runId/summary", { runId: "abc" })).toBe("/runs/abc/summary");
    expect(resolvePath("/x/$context.a/y/$context.b", { a: "1", b: "2" })).toBe("/x/1/y/2");
  });

  it("throws on unknown context key", () => {
    expect(() => resolvePath("/x/$context.unknown", {})).toThrow();
  });
});
