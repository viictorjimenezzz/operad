import { type RunRow, RunTable, type RunTableColumn } from "@/components/ui/run-table";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const columns: RunTableColumn[] = [
  { id: "state", label: "State", source: "_state", sortable: true, width: 90 },
  { id: "run", label: "Run", source: "_id", sortable: true, width: 100 },
  { id: "tokens", label: "Tokens", source: "tokens", sortable: true, width: 90 },
  { id: "spark", label: "Trend", source: "spark", width: 80 },
  { id: "group", label: "Group", source: "group", width: 80 },
];

function makeRows(count = 55): RunRow[] {
  return Array.from({ length: count }, (_, index) => ({
    id: `run-${index.toString().padStart(2, "0")}`,
    identity: `identity-${index}`,
    state: index % 10 === 0 ? "error" : index % 7 === 0 ? "running" : "ended",
    startedAt: 1_000 + index,
    endedAt: 1_010 + index,
    durationMs: 100 + index,
    fields: {
      tokens: { kind: "num", value: count - index, format: "tokens" },
      spark: { kind: "sparkline", values: [index, index + 1, index + 2] },
      group: { kind: "text", value: index % 2 === 0 ? "even" : "odd" },
    },
  }));
}

function renderTable(extra: Partial<ComponentProps<typeof RunTable>> = {}) {
  return render(
    <MemoryRouter>
      <RunTable
        rows={makeRows()}
        columns={columns}
        storageKey="test"
        pageSize={50}
        rowHref={(row) => `/runs/${row.id}`}
        {...extra}
      />
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("RunTable", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("renders a pager and sparkline column for 50-row pages", () => {
    renderTable();

    expect(screen.getByText("1-50 of 55")).toBeTruthy();
    expect(document.querySelector("svg[aria-label='sparkline']")).toBeTruthy();
  });

  it("sorts rows by a sortable column", () => {
    renderTable({ rows: makeRows(3) });

    fireEvent.click(screen.getByRole("button", { name: /Tokens/ }));
    const text = document.body.textContent ?? "";
    expect(text.indexOf("run-02")).toBeLessThan(text.indexOf("run-00"));
  });

  it("toggles multi-select with shift-click and keyboard space", () => {
    const onSelectionChange = vi.fn();
    renderTable({ selectable: true, rows: makeRows(3), onSelectionChange });

    fireEvent.click(screen.getByText("run-00"), { shiftKey: true });
    expect(onSelectionChange).toHaveBeenLastCalledWith(["run-00"]);

    const root = screen.getByText("run-00").closest("[tabindex='0']");
    if (!root) throw new Error("missing focus root");
    fireEvent.keyDown(root, { key: "j" });
    fireEvent.keyDown(root, { key: " " });
    expect(onSelectionChange).toHaveBeenLastCalledWith(["run-00", "run-01"]);
  });

  it("hides columns through the Radix columns menu", () => {
    renderTable({ rows: makeRows(3) });

    expect(screen.getByText("3")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Columns/ }));
    fireEvent.click(screen.getAllByText("Tokens").at(-1) ?? screen.getByText("Tokens"));
    expect(screen.queryByText("3")).toBeNull();
  });

  it("renders collapsible group headers", () => {
    renderTable({
      rows: makeRows(4),
      groupBy: (row) => ({
        key: String(row.fields.group?.kind === "text" ? row.fields.group.value : "none"),
        label: String(row.fields.group?.kind === "text" ? row.fields.group.value : "none"),
      }),
    });

    const evenGroup = screen.getByRole("button", { name: /even/ });
    expect(evenGroup).toBeTruthy();
    fireEvent.click(evenGroup);
    expect(screen.queryByText("run-00")).toBeNull();
    expect(screen.getByText("run-01")).toBeTruthy();
  });
});
