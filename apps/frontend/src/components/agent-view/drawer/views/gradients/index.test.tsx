import "@/components/agent-view/drawer/views/gradients";
import { getDrawerHeader } from "@/components/agent-view/drawer/drawer-host";
import { describe, expect, it } from "vitest";

describe("gradients drawer registration", () => {
  it("provides header metadata", () => {
    const header = getDrawerHeader(
      {
        kind: "gradients",
        payload: { agentPath: "Root.stage_0", paramPath: "role" },
      },
      "run-1",
    );
    expect(header.title).toBe("Gradient rationale");
    expect(header.subtitle).toBe("role");
  });
});
