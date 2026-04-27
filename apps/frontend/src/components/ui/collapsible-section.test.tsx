import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("CollapsibleSection", () => {
  it("opens when the URL hash targets its section id", () => {
    render(
      <MemoryRouter initialEntries={["/#section=backend"]}>
        <CollapsibleSection id="backend" label="Backend" preview="model">
          backend body
        </CollapsibleSection>
      </MemoryRouter>,
    );

    expect(screen.getByText("backend body")).toBeTruthy();
  });

  it("toggles open state locally", () => {
    render(
      <MemoryRouter>
        <CollapsibleSection id="identity" label="Identity" preview="hash">
          identity body
        </CollapsibleSection>
      </MemoryRouter>,
    );

    expect(screen.queryByText("identity body")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Identity/ }));
    expect(screen.getByText("identity body")).toBeTruthy();
  });
});
