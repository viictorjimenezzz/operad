import { LayoutSpec, type TabsElementSpec, resolvePath } from "@/lib/layout-schema";
import { describe, expect, it } from "vitest";

const layoutModules = import.meta.glob("../layouts/*.json", {
  eager: true,
}) as Record<string, { default?: unknown } | unknown>;

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

  it("accepts every per-algorithm layout with a Tabs root", () => {
    for (const [path, mod] of Object.entries(layoutModules)) {
      const raw = (mod as { default?: unknown }).default ?? mod;
      const layout = LayoutSpec.parse(raw);
      const root = layout.spec.elements[layout.spec.root];
      expect(root, path).toBeDefined();
      expect(root?.type, path).toBe("Tabs");
      const tabsRoot = root as TabsElementSpec;
      expect(tabsRoot.children, path).toEqual(tabsRoot.props.tabs.map((tab) => tab.id));
    }
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
