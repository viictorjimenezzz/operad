import { smokeCatalog, smokeTree } from "@/lib/json-render-smoke";
import { describe, expect, it } from "vitest";

describe("@json-render upstream API", () => {
  it("createCatalog accepts our component shape", () => {
    expect(Object.keys(smokeCatalog.components)).toEqual(["Card"]);
    expect(smokeCatalog.components.Card.hasChildren).toBe(true);
  });

  it("UITree shape matches our planned layout JSON", () => {
    expect(smokeTree.root).toBe("outer");
    expect(smokeTree.elements.outer?.children).toEqual(["inner"]);
    expect(smokeTree.elements.inner?.type).toBe("Card");
  });
});
