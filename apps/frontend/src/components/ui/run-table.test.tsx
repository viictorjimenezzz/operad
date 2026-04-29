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

  it("renders and sorts param cells with numeric and textual values", () => {
    const rows: RunRow[] = [
      {
        id: "run-a",
        identity: "identity-a",
        state: "ended",
        startedAt: 1,
        endedAt: 2,
        durationMs: 10,
        fields: {
          paramValue: { kind: "param", value: 2, previous: 1, format: "number" },
        },
      },
      {
        id: "run-b",
        identity: "identity-b",
        state: "ended",
        startedAt: 2,
        endedAt: 3,
        durationMs: 11,
        fields: {
          paramValue: { kind: "param", value: 10, previous: 10, format: "number" },
        },
      },
    ];
    const paramColumns: RunTableColumn[] = [
      { id: "run", label: "Run", source: "_id", sortable: true, width: 100 },
      { id: "param", label: "Param", source: "paramValue", sortable: true, width: 140 },
    ];
    render(
      <MemoryRouter>
        <RunTable rows={rows} columns={paramColumns} storageKey="param-test" pageSize={50} />
      </MemoryRouter>,
    );

    expect(screen.getAllByText(/\+1/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: /Param/ }));
    fireEvent.click(screen.getByRole("button", { name: /Param/ }));
    const text = document.body.textContent ?? "";
    expect(text.indexOf("run-b")).toBeLessThan(text.indexOf("run-a"));
  });

  it("renders and sorts score cells with bars", () => {
    const rows: RunRow[] = [
      {
        id: "run-neg",
        identity: "identity-neg",
        state: "ended",
        startedAt: 1,
        endedAt: 2,
        durationMs: 10,
        fields: { scoreValue: { kind: "score", value: -0.5, min: -1, max: 1 } },
      },
      {
        id: "run-pos",
        identity: "identity-pos",
        state: "ended",
        startedAt: 2,
        endedAt: 3,
        durationMs: 11,
        fields: { scoreValue: { kind: "score", value: 0.5, min: -1, max: 1 } },
      },
    ];
    const scoreColumns: RunTableColumn[] = [
      { id: "run", label: "Run", source: "_id", sortable: true, width: 100 },
      { id: "score", label: "Score", source: "scoreValue", sortable: true, width: 160 },
    ];
    render(
      <MemoryRouter>
        <RunTable rows={rows} columns={scoreColumns} storageKey="score-test" pageSize={50} />
      </MemoryRouter>,
    );

    expect(screen.getAllByLabelText("score bar").length).toBe(2);
    fireEvent.click(screen.getByRole("button", { name: /Score/ }));
    fireEvent.click(screen.getByRole("button", { name: /Score/ }));
    const text = document.body.textContent ?? "";
    expect(text.indexOf("run-pos")).toBeLessThan(text.indexOf("run-neg"));
  });

  it("renders diff and image cells and keeps image non-sortable", () => {
    const rows: RunRow[] = [
      {
        id: "run-0",
        identity: "identity-0",
        state: "ended",
        startedAt: 1,
        endedAt: 2,
        durationMs: 10,
        fields: {
          diffValue: { kind: "diff", value: "next value", previous: "previous value" },
          imageValue: {
            kind: "image",
            src: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg'/>",
            alt: "thumbnail",
            width: 20,
            height: 20,
          },
        },
      },
      {
        id: "run-1",
        identity: "identity-1",
        state: "ended",
        startedAt: 2,
        endedAt: 3,
        durationMs: 11,
        fields: {
          diffValue: { kind: "diff", value: "zz next", previous: "aa previous" },
          imageValue: {
            kind: "image",
            src: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg'/>",
            alt: "thumbnail-2",
          },
        },
      },
    ];
    const diffImageColumns: RunTableColumn[] = [
      { id: "run", label: "Run", source: "_id", sortable: true, width: 100 },
      { id: "diff", label: "Diff", source: "diffValue", sortable: true, width: 200 },
      { id: "image", label: "Image", source: "imageValue", sortable: false, width: 60 },
    ];
    render(
      <MemoryRouter>
        <RunTable
          rows={rows}
          columns={diffImageColumns}
          storageKey="diff-image-test"
          pageSize={50}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("next value")).toBeTruthy();
    expect(screen.getByAltText("thumbnail")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Diff/ }));
    fireEvent.click(screen.getByRole("button", { name: /Diff/ }));
    const text = document.body.textContent ?? "";
    expect(text.indexOf("run-1")).toBeLessThan(text.indexOf("run-0"));
    const imageHeader = screen.getByRole("button", { name: /Image/ });
    expect(imageHeader.hasAttribute("disabled")).toBe(true);
  });

  it("expands long diff cells directly without a full-diff toggle", () => {
    const previous = `previous value ${"old ".repeat(40)}tail`;
    const next = `next value ${"new ".repeat(40)}tail`;
    const rows: RunRow[] = [
      {
        id: "run-diff",
        identity: "identity-diff",
        state: "ended",
        startedAt: 1,
        endedAt: 2,
        durationMs: 10,
        fields: {
          diffValue: { kind: "diff", value: next, previous },
        },
      },
    ];
    const diffColumns: RunTableColumn[] = [
      { id: "run", label: "Run", source: "_id", sortable: true, width: 100 },
      { id: "diff", label: "Diff", source: "diffValue", sortable: true, width: 240 },
    ];
    render(
      <MemoryRouter>
        <RunTable rows={rows} columns={diffColumns} storageKey="diff-expand-test" pageSize={50} />
      </MemoryRouter>,
    );

    expect(screen.queryByText("full diff")).toBeNull();
    expect(document.body.textContent ?? "").not.toContain("- previous value");
    fireEvent.click(screen.getByRole("button", { name: /next value/ }));
    expect(screen.queryByText("full diff")).toBeNull();
    expect(document.body.textContent ?? "").toContain("- previous value");
    expect(document.body.textContent ?? "").toContain("+ next value");
  });

  it("renders link cells as safe external links", () => {
    const rows: RunRow[] = [
      {
        id: "run-link",
        identity: "identity-link",
        state: "ended",
        startedAt: 1,
        endedAt: 2,
        durationMs: 10,
        fields: {
          linkValue: { kind: "link", label: "open", to: "https://langfuse.example/trace/run-link" },
        },
      },
    ];
    const linkColumns: RunTableColumn[] = [
      { id: "run", label: "Run", source: "_id", sortable: true, width: 100 },
      { id: "link", label: "Link", source: "linkValue", sortable: false, width: 120 },
    ];
    render(
      <MemoryRouter>
        <RunTable rows={rows} columns={linkColumns} storageKey="link-test" pageSize={50} />
      </MemoryRouter>,
    );

    const link = screen.getByRole("link", { name: "open" });
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
  });
});
