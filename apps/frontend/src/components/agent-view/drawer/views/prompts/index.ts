import {
  PromptDiffView,
} from "@/components/agent-view/drawer/views/prompts/prompt-diff";
import { registerDrawerView } from "@/components/agent-view/drawer/drawer-registry";
import { createElement } from "react";

registerDrawerView("prompts", {
  getTitle: () => "Prompt diff",
  getSubtitle: (payload) => (typeof payload.agentPath === "string" ? payload.agentPath : null),
  render: ({ payload, runId }) => {
    if (typeof payload.agentPath !== "string" || payload.agentPath.length === 0) {
      return createElement(
        "div",
        { className: "p-3 text-xs text-err" },
        "agentPath is required for prompts drawer",
      );
    }
    const focus = typeof payload.focus === "string" ? payload.focus : null;
    return createElement(PromptDiffView, {
      runId,
      agentPath: payload.agentPath,
      focus,
    });
  },
});

export { PromptDiffView };
export * from "@/components/agent-view/drawer/views/prompts/prompt-pair-diff";
export * from "@/components/agent-view/drawer/views/prompts/prompt-renderer";
export * from "@/components/agent-view/drawer/views/prompts/drift-navigator";
export * from "@/components/agent-view/drawer/views/prompts/prompt-utils";
