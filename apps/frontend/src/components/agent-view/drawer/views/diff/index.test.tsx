import "@/components/agent-view/drawer/views/diff";
import { getDrawerHeader } from "@/components/agent-view/drawer/drawer-host";
import { describe, expect, it } from "vitest";

describe("diff drawer registration", () => {
  it("provides header metadata", () => {
    const header = getDrawerHeader(
      {
        kind: "diff",
        payload: {
          agentPath: "Root.stage_0",
          fromInvocationId: "Root.stage_0:0",
          toInvocationId: "Root.stage_0:1",
        },
      },
      "run-1",
    );
    expect(header.title).toBe("Invocation diff");
    expect(header.subtitle).toBe("Root.stage_0");
  });
});
