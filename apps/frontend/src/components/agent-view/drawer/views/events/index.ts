import { registerDrawerView } from "@/components/agent-view/drawer/drawer-registry";
import { FilteredEvents } from "@/components/agent-view/drawer/views/events/filtered-events";
import { createElement } from "react";

registerDrawerView("events", {
  getTitle: () => "Filtered events",
  getSubtitle: (payload) => (typeof payload.agentPath === "string" ? payload.agentPath : null),
  render: ({ payload, runId }) => createElement(FilteredEvents, { payload, runId }),
});
