import { registerDrawerView } from "@/components/agent-view/drawer/drawer-registry";
import { ExperimentRunner } from "@/components/agent-view/drawer/views/experiment/experiment-runner";
import { createElement } from "react";

registerDrawerView("experiment", {
  getTitle: () => "Prompt experiment",
  getSubtitle: (payload) => (typeof payload.agentPath === "string" ? payload.agentPath : null),
  render: ({ payload, runId }) => {
    if (typeof payload.agentPath !== "string" || payload.agentPath.length === 0) {
      return createElement(
        "div",
        { className: "p-3 text-xs text-err" },
        "agentPath is required for experiment drawer",
      );
    }
    return createElement(ExperimentRunner, {
      runId,
      agentPath: payload.agentPath,
      initialInput: payload.input,
    });
  },
});

export { ExperimentRunner };
