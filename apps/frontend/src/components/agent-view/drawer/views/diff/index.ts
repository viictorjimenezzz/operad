import { registerDrawerView } from "@/components/agent-view/drawer/drawer-registry";
import { InvocationDiffView } from "@/components/agent-view/drawer/views/diff/invocation-diff";
import { createElement } from "react";

registerDrawerView("diff", {
  getTitle: () => "Invocation diff",
  getSubtitle: (payload) => (typeof payload.agentPath === "string" ? payload.agentPath : null),
  render: ({ payload, runId }) => createElement(InvocationDiffView, { payload, runId }),
});

export { InvocationDiffView };
