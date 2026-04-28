import { ParameterDrawer } from "@/components/agent-view/structure/parameter-drawer";
import { useParameterDrawer } from "@/components/agent-view/structure/use-parameter-drawer";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

function DrawerFixture({
  open,
  onClose = vi.fn(),
}: {
  open: boolean;
  onClose?: () => void;
}) {
  return (
    <ParameterDrawer
      open={open}
      identity="abc123"
      title="Planner.role"
      subtitle="TextParameter - trainable"
      onClose={onClose}
    >
      <div>timeline content</div>
    </ParameterDrawer>
  );
}

function HookProbe() {
  const drawer = useParameterDrawer();
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <div>
      <div>param={drawer.paramPath ?? ""}</div>
      <div>step={drawer.stepIndex ?? ""}</div>
      <div>url={location.pathname + location.search}</div>
      <button type="button" onClick={() => drawer.open("Planner.role")}>
        open role
      </button>
      <button type="button" onClick={() => drawer.open("Planner.task", 2)}>
        open task
      </button>
      <button type="button" onClick={() => drawer.selectStep(3)}>
        select step
      </button>
      <button type="button" onClick={drawer.close}>
        close
      </button>
      <button type="button" onClick={() => navigate(-1)}>
        back
      </button>
    </div>
  );
}

describe("ParameterDrawer", () => {
  it("does not render when closed", () => {
    render(<DrawerFixture open={false} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders title, subtitle, and content when open", () => {
    render(<DrawerFixture open />);
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByText("Planner.role")).toBeTruthy();
    expect(screen.getByText("TextParameter - trainable")).toBeTruthy();
    expect(screen.getByText("timeline content")).toBeTruthy();
  });

  it("closes from the backdrop", () => {
    const onClose = vi.fn();
    render(<DrawerFixture open onClose={onClose} />);
    const backdrop = screen.getAllByRole("button", { name: "close parameter drawer" })[0];
    if (!backdrop) throw new Error("expected drawer backdrop");
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes from Escape", () => {
    const onClose = vi.fn();
    render(<DrawerFixture open onClose={onClose} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("uses the contracted drawer width clamp and color rail", () => {
    render(<DrawerFixture open />);
    const dialog = screen.getByRole("dialog");
    expect(dialog.className).toContain(
      "w-[clamp(var(--drawer-min),var(--drawer-width),var(--drawer-max))]",
    );
    expect(dialog.firstElementChild?.className).toContain("w-[4px]");
  });
});

describe("useParameterDrawer", () => {
  it("opens, selects a step, and closes through URL state", () => {
    render(
      <MemoryRouter initialEntries={["/agents/hash/training?tab=parameters"]}>
        <HookProbe />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByText("open role"));
    expect(screen.getByText("param=Planner.role")).toBeTruthy();
    expect(
      screen.getByText("url=/agents/hash/training?tab=parameters&param=Planner.role"),
    ).toBeTruthy();

    fireEvent.click(screen.getByText("select step"));
    expect(screen.getByText("step=3")).toBeTruthy();
    expect(
      screen.getByText("url=/agents/hash/training?tab=parameters&param=Planner.role&step=3"),
    ).toBeTruthy();

    fireEvent.click(screen.getByText("close"));
    expect(screen.getByText("param=")).toBeTruthy();
    expect(screen.getByText("step=")).toBeTruthy();
    expect(screen.getByText("url=/agents/hash/training?tab=parameters")).toBeTruthy();
  });

  it("treats invalid step values as unselected", () => {
    render(
      <MemoryRouter initialEntries={["/agents/hash/training?param=Planner.role&step=nope"]}>
        <HookProbe />
      </MemoryRouter>,
    );

    expect(screen.getByText("param=Planner.role")).toBeTruthy();
    expect(screen.getByText("step=")).toBeTruthy();
  });

  it("lets browser back navigate between drawer states", () => {
    render(
      <MemoryRouter initialEntries={["/agents/hash/training"]}>
        <HookProbe />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByText("open role"));
    fireEvent.click(screen.getByText("open task"));
    expect(screen.getByText("param=Planner.task")).toBeTruthy();
    expect(screen.getByText("step=2")).toBeTruthy();

    fireEvent.click(screen.getByText("back"));
    expect(screen.getByText("param=Planner.role")).toBeTruthy();
    expect(screen.getByText("step=")).toBeTruthy();
  });
});
