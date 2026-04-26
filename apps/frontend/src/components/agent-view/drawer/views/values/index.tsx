import { registerDrawerView } from "@/components/agent-view/drawer/drawer-registry";
import { ValueTimeline } from "@/components/agent-view/drawer/views/values/value-timeline";
import type { DrawerPayload } from "@/stores/ui";

registerDrawerView("values", {
  getTitle: (payload: DrawerPayload) => {
    const attr = typeof payload.attr === "string" ? payload.attr : "value";
    const side = payload.side === "out" ? "output" : "input";
    return `Values of ${attr} (${side})`;
  },
  getSubtitle: (payload: DrawerPayload) =>
    typeof payload.agentPath === "string" ? payload.agentPath : null,
  render: ({ payload, runId }) => <ValueTimeline payload={payload} runId={runId} />,
});
