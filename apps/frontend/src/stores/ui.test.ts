import { useUIStore } from "@/stores/ui";
import { beforeEach, describe, expect, it } from "vitest";

describe("useUIStore", () => {
  beforeEach(() => {
    localStorage.clear();
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      writable: true,
      value: 1000,
    });
    useUIStore.setState({
      currentTab: "overview",
      eventKindFilter: "all",
      eventSearch: "",
      autoFollow: true,
      eventsFollow: true,
      sidebarCollapsed: false,
      selectedInvocationId: null,
      selectedInvocationAgentPath: null,
      comparisonInvocationId: null,
      comparisonInvocationAgentPath: null,
      graphSelection: null,
      graphInspectorTab: "overview",
      graphSplitFraction: 0.5,
    });
  });

  it("toggles sidebar state", () => {
    expect(useUIStore.getState().sidebarCollapsed).toBe(false);
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarCollapsed).toBe(true);
    useUIStore.getState().setSidebarCollapsed(false);
    expect(useUIStore.getState().sidebarCollapsed).toBe(false);
  });

  it("tracks graph selection and clamps inspector tab on node selection", () => {
    useUIStore.getState().setGraphSelection({ kind: "edge", agentPath: "Root.stage_0" });
    expect(useUIStore.getState().graphSelection).toEqual({
      kind: "edge",
      agentPath: "Root.stage_0",
    });
    expect(useUIStore.getState().graphInspectorTab).toBe("overview");

    useUIStore.getState().setGraphSelection({ kind: "node", nodeKey: "Question" });
    expect(useUIStore.getState().graphInspectorTab).toBe("fields");

    useUIStore.getState().setGraphSelection({ kind: "edge", agentPath: "Root.stage_1" });
    // Switching away from "fields" should reset inspector tab to overview
    expect(useUIStore.getState().graphInspectorTab).toBe("overview");

    useUIStore.getState().clearGraphSelection();
    expect(useUIStore.getState().graphSelection).toBeNull();
  });

  it("clamps split fraction within bounds", () => {
    useUIStore.getState().setGraphSplitFraction(0.1);
    expect(useUIStore.getState().graphSplitFraction).toBe(0.25);
    useUIStore.getState().setGraphSplitFraction(0.95);
    expect(useUIStore.getState().graphSplitFraction).toBe(0.75);
    useUIStore.getState().setGraphSplitFraction(0.42);
    expect(useUIStore.getState().graphSplitFraction).toBeCloseTo(0.42);
  });

  it("persists sidebarCollapsed and graphSplitFraction", () => {
    useUIStore.getState().setSidebarCollapsed(true);
    useUIStore.getState().setGraphSplitFraction(0.6);

    const raw = localStorage.getItem("operad.ui");
    expect(raw).toBeTruthy();

    const parsed = JSON.parse(raw as string) as {
      state: { sidebarCollapsed: boolean; graphSplitFraction: number };
    };
    expect(parsed.state.sidebarCollapsed).toBe(true);
    expect(parsed.state.graphSplitFraction).toBeCloseTo(0.6);
  });

  it("tracks selected invocation context", () => {
    useUIStore.getState().setSelectedInvocation("Root:5", "Root");
    expect(useUIStore.getState().selectedInvocationId).toBe("Root:5");
    expect(useUIStore.getState().selectedInvocationAgentPath).toBe("Root");
    useUIStore.getState().clearSelectedInvocation();
    expect(useUIStore.getState().selectedInvocationId).toBeNull();
    expect(useUIStore.getState().selectedInvocationAgentPath).toBeNull();
  });
});
