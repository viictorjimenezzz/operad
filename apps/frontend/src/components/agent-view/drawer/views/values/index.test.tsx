import "@/components/agent-view/drawer/views/values";
import { getDrawerHeader } from "@/components/agent-view/drawer/drawer-host";
import { describe, expect, it } from "vitest";

describe("values drawer registration", () => {
  it("provides dynamic header title", () => {
    const header = getDrawerHeader(
      { kind: "values", payload: { agentPath: "Root", attr: "question", side: "out" } },
      "run-1",
    );
    expect(header.title).toBe("Values of question (output)");
    expect(header.subtitle).toBe("Root");
  });
});
