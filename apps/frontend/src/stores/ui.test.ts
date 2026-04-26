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
      drawer: null,
      drawerWidth: 480,
    });
  });

  it("toggles sidebar state", () => {
    expect(useUIStore.getState().sidebarCollapsed).toBe(false);
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarCollapsed).toBe(true);
    useUIStore.getState().setSidebarCollapsed(false);
    expect(useUIStore.getState().sidebarCollapsed).toBe(false);
  });

  it("opens/closes drawer, supports atomic swap, and clamps width", () => {
    useUIStore.getState().openDrawer("events", { agentPath: "root.worker" });
    expect(useUIStore.getState().drawer).toEqual({
      kind: "events",
      payload: { agentPath: "root.worker" },
    });

    useUIStore.getState().openDrawer("prompts", { agentPath: "root.other", attr: "question" });
    expect(useUIStore.getState().drawer).toEqual({
      kind: "prompts",
      payload: { agentPath: "root.other", attr: "question" },
    });

    useUIStore.getState().setDrawerWidth(120);
    expect(useUIStore.getState().drawerWidth).toBe(320);

    useUIStore.getState().setDrawerWidth(900);
    expect(useUIStore.getState().drawerWidth).toBe(600);

    useUIStore.getState().closeDrawer();
    expect(useUIStore.getState().drawer).toBeNull();
  });

  it("supports find-runs drawer kind", () => {
    useUIStore.getState().openDrawer("find-runs", { hash: "hash_prompt", value: "abcd1234" });
    expect(useUIStore.getState().drawer).toEqual({
      kind: "find-runs",
      payload: { hash: "hash_prompt", value: "abcd1234" },
    });
  });

  it("persists sidebarCollapsed and drawerWidth", () => {
    useUIStore.getState().setSidebarCollapsed(true);
    useUIStore.getState().setDrawerWidth(512);

    const raw = localStorage.getItem("operad.ui");
    expect(raw).toBeTruthy();

    const parsed = JSON.parse(raw as string) as {
      state: { sidebarCollapsed: boolean; drawerWidth: number };
    };
    expect(parsed.state.sidebarCollapsed).toBe(true);
    expect(parsed.state.drawerWidth).toBe(512);
  });
});
