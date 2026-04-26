import { registerDrawerView } from "@/components/agent-view/drawer/drawer-registry";
import { SideDrawer } from "@/components/agent-view/drawer/side-drawer";
import { useUIStore } from "@/stores";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

function renderDrawer(path = "/runs/run-42") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/runs/:runId" element={<SideDrawer />} />
        <Route path="/" element={<SideDrawer />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("SideDrawer", () => {
  beforeEach(() => {
    localStorage.clear();
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      writable: true,
      value: 1200,
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

  afterEach(() => {
    cleanup();
  });

  it("stays offscreen and unmounted when closed", () => {
    renderDrawer();
    const panel = screen.getByLabelText("inspector drawer");
    expect(panel.className.includes("translate-x-full")).toBe(true);
    expect(screen.queryByText("stub view")).toBeNull();
  });

  it("renders stub with payload when kind is unregistered", () => {
    act(() => {
      useUIStore.getState().openDrawer("langfuse", { agentPath: "root.worker", foo: "bar" });
    });
    renderDrawer();

    expect(screen.getByText("Langfuse trace")).toBeTruthy();
    expect(screen.getByText("root.worker")).toBeTruthy();
    expect(screen.getByText("stub view")).toBeTruthy();
    expect(screen.getByText(/"foo": "bar"/)).toBeTruthy();
  });

  it("renders registered views and swaps content without closing", () => {
    registerDrawerView("prompts", {
      getTitle: (_payload, runId) => `Prompt diff for ${runId}`,
      getSubtitle: (payload) => (typeof payload.agentPath === "string" ? payload.agentPath : null),
      render: ({ payload }) => <div>prompts view: {String(payload.attr ?? "")}</div>,
    });
    registerDrawerView("values", {
      getTitle: () => "Values timeline",
      render: ({ payload }) => <div>values view: {String(payload.attr ?? "")}</div>,
    });

    act(() => {
      useUIStore.getState().openDrawer("prompts", { agentPath: "root.a", attr: "question" });
    });
    renderDrawer();

    expect(screen.getByText("Prompt diff for run-42")).toBeTruthy();
    expect(screen.getByText("prompts view: question")).toBeTruthy();

    act(() => {
      useUIStore.getState().openDrawer("values", { attr: "answer" });
    });
    expect(screen.getByText("Values timeline")).toBeTruthy();
    expect(screen.getByText("values view: answer")).toBeTruthy();
    expect(screen.queryByText("prompts view: question")).toBeNull();
  });

  it("closes with escape, close button, and outside click", () => {
    act(() => {
      useUIStore.getState().openDrawer("langfuse", {});
    });
    renderDrawer();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(useUIStore.getState().drawer).toBeNull();

    act(() => {
      useUIStore.getState().openDrawer("langfuse", {});
    });
    fireEvent.click(screen.getByRole("button", { name: "Close drawer" }));
    expect(useUIStore.getState().drawer).toBeNull();

    act(() => {
      useUIStore.getState().openDrawer("langfuse", {});
    });
    fireEvent.mouseDown(window);
    expect(useUIStore.getState().drawer).toBeNull();
  });

  it("resizes from drag handle and persists width", () => {
    act(() => {
      useUIStore.getState().openDrawer("langfuse", {});
    });
    renderDrawer();

    fireEvent.mouseDown(screen.getByRole("separator", { name: "Resize drawer" }), {
      clientX: 700,
    });
    fireEvent.mouseMove(window, { clientX: 820 });
    fireEvent.mouseUp(window);

    expect(useUIStore.getState().drawerWidth).toBe(380);
    const raw = localStorage.getItem("operad.ui");
    expect(raw).toContain("\"drawerWidth\":380");
  });
});
