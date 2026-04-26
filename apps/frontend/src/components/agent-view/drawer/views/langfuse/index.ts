import { registerDrawerView } from "@/components/agent-view/drawer/drawer-registry";
import { LangfuseEmbed } from "@/components/agent-view/drawer/views/langfuse/langfuse-embed";
import { createElement } from "react";

registerDrawerView("langfuse", {
  getTitle: () => "Langfuse trace",
  getSubtitle: (payload) => (typeof payload.agentPath === "string" ? payload.agentPath : null),
  render: ({ payload, runId }) => createElement(LangfuseEmbed, { payload, runId }),
});
