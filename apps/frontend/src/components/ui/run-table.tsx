import { MarkdownView } from "@/components/ui/markdown";
import { Pager } from "@/components/ui/pager";
import { Pill } from "@/components/ui/pill";
import { Sparkline } from "@/components/ui/sparkline";
import { useUrlState } from "@/hooks/use-url-state";
import { hashColor } from "@/lib/hash-color";
import {
  cn,
  formatCost,
  formatDurationMs,
  formatNumber,
  formatRelativeTime,
  formatTokens,
} from "@/lib/utils";
import * as Popover from "@radix-ui/react-popover";
import { ArrowDown, ArrowUp, Check, Columns3 } from "lucide-react";
import {
  type KeyboardEvent,
  type MouseEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useLocation, useNavigate } from "react-router-dom";

export type RunRow = {
  id: string;
  identity: string;
  state: "running" | "ended" | "error" | "queued";
  startedAt: number | null;
  endedAt: number | null;
  durationMs: number | null;
  fields: Record<string, RunFieldValue>;
};

export type RunFieldValue =
  | { kind: "text"; value: string; mono?: boolean }
  | {
      kind: "num";
      value: number | null;
      format?: "tokens" | "cost" | "ms" | "score" | "int" | "float";
    }
  | { kind: "param"; value: unknown; previous?: unknown; format?: "auto" | "text" | "number" }
  | { kind: "score"; value: number | null; min?: number; max?: number }
  | { kind: "diff"; value: string; previous?: string }
  | { kind: "image"; src: string; alt: string; width?: number; height?: number }
  | { kind: "pill"; value: string; tone: "ok" | "warn" | "error" | "live" | "accent" | "default" }
  | { kind: "hash"; value: string }
  | { kind: "sparkline"; values: (number | null)[] }
  | { kind: "link"; label: string; to: string }
  | { kind: "markdown"; value: string };

export type RunTableColumn = {
  id: string;
  label: string;
  source: string;
  align?: "left" | "right";
  sortable?: boolean;
  defaultSort?: "asc" | "desc";
  width?: number | "1fr";
  defaultVisible?: boolean;
  isColorRail?: boolean;
};

export interface RunTableProps {
  rows: RunRow[];
  columns: RunTableColumn[];
  storageKey: string;
  rowHref?: (row: RunRow) => string | null;
  selectable?: boolean;
  onSelectionChange?: (selected: string[]) => void;
  emptyTitle?: string;
  emptyDescription?: string;
  pageSize?: number;
  groupBy?: (row: RunRow) => { key: string; label: string };
  density?: "compact" | "cozy";
}

type SortState = { id: string; source: string; dir: "asc" | "desc" } | null;

const STORAGE_PREFIX = "operad.dashboard.runtable.cols.";

export function RunTable({
  rows,
  columns,
  storageKey,
  rowHref,
  selectable,
  onSelectionChange,
  emptyTitle = "No runs",
  emptyDescription = "No rows match this view.",
  pageSize = 50,
  groupBy,
  density = "compact",
}: RunTableProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const [sortParam, setSortParam] = useUrlState("sort");
  const [colsParam, setColsParam] = useUrlState("cols");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(() => new Set());

  const tableColumns = useMemo(() => columns.filter((column) => !column.isColorRail), [columns]);
  const allColumnIds = useMemo(() => tableColumns.map((column) => column.id), [tableColumns]);
  const storageId = `${STORAGE_PREFIX}${storageKey}`;

  const [visibleIds, setVisibleIds] = useState<Set<string>>(() =>
    initialVisibleIds(tableColumns, storageId, colsParam),
  );

  useEffect(() => {
    if (colsParam == null) return;
    setVisibleIds(parseVisibleIds(colsParam, tableColumns));
  }, [colsParam, tableColumns]);

  const visibleColumns = useMemo(
    () => tableColumns.filter((column) => visibleIds.has(column.id)),
    [tableColumns, visibleIds],
  );

  const sort = useMemo(() => resolveSort(sortParam, tableColumns), [sortParam, tableColumns]);
  const sortedRows = useMemo(() => sortRows(rows, sort), [rows, sort]);
  const pageRows = useMemo(
    () => sortedRows.slice(page * pageSize, page * pageSize + pageSize),
    [sortedRows, page, pageSize],
  );
  const groups = useMemo(() => groupPageRows(pageRows, groupBy), [pageRows, groupBy]);
  const keyboardRows = useMemo(
    () => groups.flatMap((group) => (collapsedGroups.has(group.key) ? [] : group.rows)),
    [groups, collapsedGroups],
  );

  useEffect(() => {
    const lastPage = Math.max(0, Math.ceil(sortedRows.length / pageSize) - 1);
    if (page > lastPage) setPage(lastPage);
  }, [page, pageSize, sortedRows.length]);

  useEffect(() => {
    onSelectionChange?.([...selected]);
  }, [onSelectionChange, selected]);

  const gridTemplate = useMemo(() => {
    const widths = visibleColumns.map((column) =>
      typeof column.width === "number"
        ? `${column.width}px`
        : column.width === "1fr"
          ? "minmax(0, 1fr)"
          : "minmax(0, 1fr)",
    );
    return ["8px", selectable ? "26px" : null, ...widths].filter(Boolean).join(" ");
  }, [selectable, visibleColumns]);

  const rowHeight = density === "compact" ? "min-h-7" : "min-h-8";

  const updateVisibleIds = (next: Set<string>) => {
    const ids = allColumnIds.filter((id) => next.has(id));
    setVisibleIds(new Set(ids));
    setColsParam(ids.length === allColumnIds.length ? null : ids.join(","));
    writeStorage(storageId, ids);
  };

  const toggleColumn = (id: string) => {
    const next = new Set(visibleIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    updateVisibleIds(next);
  };

  const toggleSelected = (id: string) => {
    if (!selectable) return;
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const openRow = (row: RunRow, event?: MouseEvent) => {
    const href = rowHref?.(row);
    if (!href) return;
    if (event?.metaKey || event?.ctrlKey) {
      window.open(href, "_blank", "noopener,noreferrer");
      return;
    }
    navigate(href);
  };

  const onRowClick = (row: RunRow, event: MouseEvent) => {
    if (isInteractive(event.target)) return;
    setHighlightedId(row.id);
    if (event.shiftKey && selectable) {
      event.preventDefault();
      toggleSelected(row.id);
      return;
    }
    openRow(row, event);
  };

  const onRowKeyDown = (row: RunRow, event: KeyboardEvent<HTMLDivElement>) => {
    if (isInteractive(event.target)) return;
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    setHighlightedId(row.id);
    if (event.key === " " && selectable) {
      toggleSelected(row.id);
      return;
    }
    openRow(row);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (isInteractive(event.target)) return;
    if (keyboardRows.length === 0) return;
    const currentIndex = Math.max(
      0,
      keyboardRows.findIndex((row) => row.id === highlightedId),
    );
    if (event.key === "j" || event.key === "ArrowDown") {
      event.preventDefault();
      setHighlightedId(
        keyboardRows[Math.min(currentIndex + 1, keyboardRows.length - 1)]?.id ?? null,
      );
      return;
    }
    if (event.key === "k" || event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightedId(keyboardRows[Math.max(currentIndex - 1, 0)]?.id ?? null);
      return;
    }
    const highlighted = keyboardRows.find((row) => row.id === highlightedId) ?? keyboardRows[0];
    if (!highlighted) return;
    if (event.key === "Enter" || event.key === "o") {
      event.preventDefault();
      openRow(highlighted);
      return;
    }
    if (event.key === " " && selectable) {
      event.preventDefault();
      toggleSelected(highlighted.id);
    }
  };

  if (rows.length === 0) {
    return (
      <div className="overflow-hidden rounded-lg border border-border bg-bg-1">
        <div className="min-h-40">
          <div className="flex h-full min-h-40 flex-col items-center justify-center gap-2 p-6 text-center">
            <h3 className="m-0 text-sm font-medium text-text">{emptyTitle}</h3>
            <p className="m-0 max-w-md text-xs text-muted">{emptyDescription}</p>
          </div>
        </div>
        <RunTableFooter
          page={page}
          pageSize={pageSize}
          total={rows.length}
          onPageChange={setPage}
          showPager={false}
          columns={tableColumns}
          visibleIds={visibleIds}
          onToggleColumn={toggleColumn}
        />
      </div>
    );
  }

  return (
    <div
      role="application"
      // biome-ignore lint/a11y/noNoninteractiveTabindex: the table container owns j/k, arrow, enter, and space keyboard navigation.
      tabIndex={0}
      onKeyDown={onKeyDown}
      aria-label="runs table"
      className="overflow-hidden rounded-lg border border-border bg-bg-1 outline-none focus-visible:ring-2 focus-visible:ring-[--color-accent-dim]"
    >
      <div className="max-h-[560px] overflow-auto">
        <div
          className="sticky top-0 z-10 grid min-h-7 items-center gap-2 border-b border-border bg-bg-2/95 px-0 pr-3 text-[10px] font-medium uppercase tracking-[0.06em] text-muted-2 backdrop-blur"
          style={{ gridTemplateColumns: gridTemplate }}
        >
          <span />
          {selectable ? <span /> : null}
          {visibleColumns.map((column) => {
            const active = sort?.id === column.id;
            return (
              <button
                key={column.id}
                type="button"
                disabled={!column.sortable}
                onClick={() => {
                  const nextDir = active && sort?.dir === "asc" ? "desc" : "asc";
                  setSortParam(`${column.id},${nextDir}`);
                }}
                className={cn(
                  "flex h-full min-w-0 items-center gap-1 text-left uppercase tracking-[0.06em]",
                  column.align === "right" && "justify-end text-right",
                  column.sortable
                    ? "text-muted-2 transition-colors hover:text-text"
                    : "cursor-default text-muted-2",
                )}
              >
                <span className="truncate">{column.label}</span>
                {active ? (
                  sort.dir === "asc" ? (
                    <ArrowUp size={10} />
                  ) : (
                    <ArrowDown size={10} />
                  )
                ) : null}
              </button>
            );
          })}
        </div>
        <div>
          {groups.map((group) => (
            <div key={group.key}>
              {group.label ? (
                <button
                  type="button"
                  onClick={() =>
                    setCollapsedGroups((current) => {
                      const next = new Set(current);
                      if (next.has(group.key)) next.delete(group.key);
                      else next.add(group.key);
                      return next;
                    })
                  }
                  className="flex h-7 w-full items-center gap-2 border-b border-border bg-bg-2/40 px-3 text-left text-[11px] text-muted transition-colors hover:bg-bg-2"
                >
                  <span className="font-medium text-text">{group.label}</span>
                  <span className="font-mono text-muted-2">{group.rows.length}</span>
                </button>
              ) : null}
              {collapsedGroups.has(group.key)
                ? null
                : group.rows.map((row) => {
                    const href = rowHref?.(row);
                    const active = href ? samePath(location.pathname, href) : false;
                    const highlighted = highlightedId === row.id;
                    return (
                      <div
                        key={row.id}
                        onClick={(event) => onRowClick(row, event)}
                        onKeyDown={(event) => onRowKeyDown(row, event)}
                        onMouseEnter={() => setHighlightedId(row.id)}
                        className={cn(
                          "grid items-center gap-2 border-b border-border px-0 pr-3 text-[12px] transition-colors last:border-b-0",
                          rowHeight,
                          href && "cursor-pointer",
                          highlighted && "bg-bg-2/45",
                          active && "outline outline-1 outline-[--color-accent-dim]",
                        )}
                        style={{ gridTemplateColumns: gridTemplate }}
                      >
                        <span className="flex h-full items-stretch justify-start">
                          <span
                            aria-hidden
                            className="my-0.5 rounded-r"
                            style={{
                              width: active ? 6 : 4,
                              background: hashColor(row.identity),
                            }}
                          />
                        </span>
                        {selectable ? (
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              toggleSelected(row.id);
                            }}
                            className={cn(
                              "flex h-5 w-5 items-center justify-center rounded border border-border text-bg transition-colors",
                              selected.has(row.id)
                                ? "bg-accent text-bg"
                                : "bg-bg-inset text-transparent hover:border-border-strong",
                            )}
                            aria-label={`select ${row.id}`}
                          >
                            <Check size={12} />
                          </button>
                        ) : null}
                        {visibleColumns.map((column) => (
                          <div
                            key={column.id}
                            className={cn(
                              "min-w-0 truncate",
                              column.align === "right" && "text-right",
                            )}
                          >
                            {renderCell(row, column)}
                          </div>
                        ))}
                      </div>
                    );
                  })}
            </div>
          ))}
        </div>
      </div>
      <RunTableFooter
        page={page}
        pageSize={pageSize}
        total={sortedRows.length}
        onPageChange={setPage}
        showPager={sortedRows.length > pageSize}
        columns={tableColumns}
        visibleIds={visibleIds}
        onToggleColumn={toggleColumn}
      />
    </div>
  );
}

function RunTableFooter({
  page,
  pageSize,
  total,
  onPageChange,
  showPager,
  columns,
  visibleIds,
  onToggleColumn,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  showPager: boolean;
  columns: RunTableColumn[];
  visibleIds: Set<string>;
  onToggleColumn: (id: string) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-t border-border bg-bg-1">
      {showPager ? (
        <Pager
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={onPageChange}
          className="flex-1 border-t-0"
        />
      ) : (
        <div className="px-3 py-1.5 font-mono text-[11px] text-muted-2">{total} rows</div>
      )}
      <Popover.Root>
        <Popover.Trigger asChild>
          <button
            type="button"
            className="mr-2 inline-flex h-7 items-center gap-1.5 rounded border border-border bg-bg-2 px-2 text-[11px] text-muted transition-colors hover:border-border-strong hover:text-text"
          >
            <Columns3 size={13} />
            Columns
          </button>
        </Popover.Trigger>
        <Popover.Portal>
          <Popover.Content
            align="end"
            sideOffset={6}
            className="z-50 min-w-48 rounded-md border border-border-strong bg-bg-1 p-1 shadow-[var(--shadow-popover)]"
          >
            {columns.map((column) => (
              <button
                key={column.id}
                type="button"
                onClick={() => onToggleColumn(column.id)}
                className="flex h-7 w-full items-center gap-2 rounded px-2 text-left text-[12px] text-muted transition-colors hover:bg-bg-2 hover:text-text"
              >
                <span
                  className={cn(
                    "flex h-4 w-4 items-center justify-center rounded border border-border",
                    visibleIds.has(column.id) && "border-accent bg-accent text-bg",
                  )}
                >
                  {visibleIds.has(column.id) ? <Check size={11} /> : null}
                </span>
                <span className="min-w-0 truncate">{column.label}</span>
              </button>
            ))}
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>
    </div>
  );
}

function renderCell(row: RunRow, column: RunTableColumn): ReactNode {
  const value = readSource(row, column.source);
  if (value == null) return <span className="text-muted-2">-</span>;
  if (typeof value === "string" || typeof value === "number") {
    return <span className="font-mono tabular-nums text-text">{String(value)}</span>;
  }

  switch (value.kind) {
    case "text":
      return (
        <span className={cn(value.mono && "font-mono tabular-nums")} title={value.value}>
          {value.value}
        </span>
      );
    case "num":
      return (
        <span className="font-mono tabular-nums">{formatRunNumber(value.value, value.format)}</span>
      );
    case "param": {
      const current = formatParam(value.value, value.format);
      const previous = formatParam(value.previous, value.format);
      const changed = value.previous !== undefined && !isSameParam(value.previous, value.value);
      const numericDelta =
        changed && typeof value.value === "number" && typeof value.previous === "number"
          ? value.value - value.previous
          : null;
      return (
        <span className="inline-flex items-center gap-1.5 font-mono tabular-nums">
          <span className="truncate" title={current.raw}>
            {current.text}
          </span>
          {changed ? (
            numericDelta != null ? (
              <span className="text-[11px] text-muted">
                {numericDelta > 0 ? "↑" : numericDelta < 0 ? "↓" : "•"} {formatSignedDelta(numericDelta)}
              </span>
            ) : (
              <span
                aria-label={`param changed from ${previous.text} to ${current.text}`}
                className="h-1.5 w-1.5 rounded-full bg-[--color-warn]"
              />
            )
          ) : null}
        </span>
      );
    }
    case "score": {
      const min = Number.isFinite(value.min) ? (value.min as number) : 0;
      const max = Number.isFinite(value.max) ? (value.max as number) : 1;
      const span = Math.max(max - min, 1e-9);
      const scoreValue = value.value;
      const normalized =
        scoreValue != null && Number.isFinite(scoreValue) ? (scoreValue - min) / span : null;
      const width = normalized == null ? 0 : Math.max(0, Math.min(1, normalized)) * 100;
      const tone =
        scoreValue == null ? "var(--color-muted-2)" : scoreValue > 0 ? "var(--color-ok)" : scoreValue < 0 ? "var(--color-err)" : "var(--color-warn)";
      return (
        <span className="inline-flex w-full min-w-0 items-center gap-2">
          <span className="w-12 flex-shrink-0 text-right font-mono tabular-nums">
            {scoreValue == null ? "—" : scoreValue.toFixed(3)}
          </span>
          <span className="h-1 w-full rounded-full bg-bg-3">
            <span
              aria-label="score bar"
              className="block h-1 rounded-full"
              style={{ width: `${width}%`, background: tone }}
            />
          </span>
        </span>
      );
    }
    case "diff": {
      const next = truncateText(value.value, 80);
      const prev = value.previous != null ? truncateText(value.previous, 80) : null;
      const hasOverflow =
        next.truncated || (value.previous != null ? value.previous.length > 80 : false);
      return (
        <div className="max-w-full">
          <span className="inline-flex min-w-0 items-center gap-1">
            {prev ? (
              <>
                <span className="truncate text-muted-2 line-through" title={value.previous}>
                  {prev.text}
                </span>
                <span className="text-muted-2">→</span>
              </>
            ) : null}
            <span className="truncate text-[--color-ok]" title={value.value}>
              {next.text}
            </span>
          </span>
          {hasOverflow ? (
            <details className="mt-1 text-[11px] text-muted">
              <summary className="cursor-pointer select-none">full diff</summary>
              <pre className="mt-1 max-h-24 overflow-auto whitespace-pre-wrap rounded border border-border bg-bg-inset p-1.5 text-[10px] leading-relaxed text-text">
                {value.previous != null ? `- ${value.previous}\n+ ${value.value}` : value.value}
              </pre>
            </details>
          ) : null}
        </div>
      );
    }
    case "image":
      return (
        <img
          src={value.src}
          alt={value.alt}
          width={value.width ?? 24}
          height={value.height ?? 24}
          className="rounded object-contain bg-bg-inset"
          style={{
            maxWidth: value.width ?? 24,
            maxHeight: value.height ?? 24,
          }}
        />
      );
    case "pill":
      return <Pill tone={value.tone}>{value.value}</Pill>;
    case "hash":
      return (
        <span className="inline-flex items-center gap-1.5 font-mono tabular-nums">
          <span
            aria-hidden
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: hashColor(value.value) }}
          />
          {value.value}
        </span>
      );
    case "sparkline":
      return (
        <Sparkline values={value.values} width={60} height={16} color={hashColor(row.identity)} />
      );
    case "link":
      return (
        <a
          href={value.to}
          onClick={(event) => event.stopPropagation()}
          className="text-accent hover:text-[--color-accent-strong]"
        >
          {value.label}
        </a>
      );
    case "markdown":
      return <MarkdownView value={value.value} />;
    default:
      return null;
  }
}

function readSource(row: RunRow, source: string): RunFieldValue | string | number | null {
  switch (source) {
    case "_id":
      return row.id;
    case "_state":
      return { kind: "pill", value: row.state, tone: stateTone(row.state) };
    case "_started":
      return formatRelativeTime(row.startedAt);
    case "_ended":
      return formatRelativeTime(row.endedAt);
    case "_duration":
      return formatDurationMs(row.durationMs);
    case "_color":
      return { kind: "hash", value: row.identity };
    default:
      return row.fields[source] ?? row.fields[source.replace(/^fields\./, "")] ?? null;
  }
}

function sortRows(rows: RunRow[], sort: SortState): RunRow[] {
  if (!sort) return rows;
  const dir = sort.dir === "asc" ? 1 : -1;
  return [...rows].sort(
    (a, b) => compareValues(sortSource(a, sort.source), sortSource(b, sort.source)) * dir,
  );
}

function compareValues(
  a: RunFieldValue | string | number | null,
  b: RunFieldValue | string | number | null,
): number {
  const av = comparable(a);
  const bv = comparable(b);
  if (av == null && bv == null) return 0;
  if (av == null) return 1;
  if (bv == null) return -1;
  if (typeof av === "number" && typeof bv === "number") return av - bv;
  return String(av).localeCompare(String(bv));
}

function comparable(value: RunFieldValue | string | number | null): string | number | null {
  if (value == null) return null;
  if (typeof value === "string" || typeof value === "number") return value;
  switch (value.kind) {
    case "num":
      return value.value;
    case "param":
      return paramComparable(value.value);
    case "score":
      return value.value;
    case "diff":
      return value.value;
    case "image":
      return null;
    case "sparkline":
      for (let i = value.values.length - 1; i >= 0; i -= 1) {
        const item = value.values[i];
        if (item != null) return item;
      }
      return null;
    default:
      return "value" in value ? value.value : null;
  }
}

function sortSource(row: RunRow, source: string): RunFieldValue | string | number | null {
  switch (source) {
    case "_started":
      return row.startedAt;
    case "_ended":
      return row.endedAt;
    case "_duration":
      return row.durationMs;
    case "_state":
      return row.state;
    default:
      return readSource(row, source);
  }
}

function resolveSort(sortParam: string | null, columns: RunTableColumn[]): SortState {
  const byId = new Map(columns.map((column) => [column.id, column]));
  if (sortParam) {
    const [id, dir] = sortParam.split(",");
    const column = id ? byId.get(id) : null;
    if (column?.sortable && (dir === "asc" || dir === "desc")) {
      return { id: column.id, source: column.source, dir };
    }
  }
  const fallback = columns.find((column) => column.sortable && column.defaultSort);
  return fallback?.defaultSort
    ? { id: fallback.id, source: fallback.source, dir: fallback.defaultSort }
    : null;
}

function parseVisibleIds(raw: string, columns: RunTableColumn[]): Set<string> {
  const allowed = new Set(columns.map((column) => column.id));
  const ids = raw.split(",").filter((id) => allowed.has(id));
  return new Set(
    ids.length > 0
      ? ids
      : columns.filter((column) => column.defaultVisible !== false).map((column) => column.id),
  );
}

function initialVisibleIds(
  columns: RunTableColumn[],
  storageId: string,
  colsParam: string | null,
): Set<string> {
  if (colsParam != null) return parseVisibleIds(colsParam, columns);
  const stored = readStorage(storageId, columns);
  if (stored) return stored;
  return new Set(
    columns.filter((column) => column.defaultVisible !== false).map((column) => column.id),
  );
}

function readStorage(storageId: string, columns: RunTableColumn[]): Set<string> | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(storageId);
  if (!raw) return null;
  return parseVisibleIds(raw, columns);
}

function writeStorage(storageId: string, ids: string[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(storageId, ids.join(","));
}

function groupPageRows(
  rows: RunRow[],
  groupBy: RunTableProps["groupBy"],
): Array<{ key: string; label: string | null; rows: RunRow[] }> {
  if (!groupBy) return [{ key: "__all__", label: null, rows }];
  const groups = new Map<string, { key: string; label: string; rows: RunRow[] }>();
  for (const row of rows) {
    const group = groupBy(row);
    const existing = groups.get(group.key);
    if (existing) existing.rows.push(row);
    else groups.set(group.key, { ...group, rows: [row] });
  }
  return [...groups.values()];
}

function formatRunNumber(
  value: number | null,
  format: Extract<RunFieldValue, { kind: "num" }>["format"],
): string {
  if (value == null || !Number.isFinite(value)) return "-";
  switch (format) {
    case "tokens":
      return formatTokens(value);
    case "cost":
      return formatCost(value);
    case "ms":
      return formatDurationMs(value);
    case "score":
      return value.toFixed(3);
    case "int":
      return Math.round(value).toString();
    case "float":
      return value.toFixed(2);
    default:
      return formatNumber(value);
  }
}

function formatParam(value: unknown, format: Extract<RunFieldValue, { kind: "param" }>["format"]) {
  if (value === null || value === undefined) return { text: "—", raw: "—" };
  if (format === "text") return { text: String(value), raw: String(value) };
  if (format === "number") {
    const numberValue = typeof value === "number" ? value : Number(value);
    if (Number.isFinite(numberValue)) {
      const formatted = formatNumber(numberValue);
      return { text: formatted, raw: formatted };
    }
    const fallback = String(value);
    return { text: fallback, raw: fallback };
  }
  if (typeof value === "number") {
    const formatted = formatNumber(value);
    return { text: formatted, raw: formatted };
  }
  if (typeof value === "string" || typeof value === "boolean") {
    return { text: String(value), raw: String(value) };
  }
  try {
    const json = JSON.stringify(value);
    return { text: json ?? String(value), raw: json ?? String(value) };
  } catch {
    const fallback = String(value);
    return { text: fallback, raw: fallback };
  }
}

function isSameParam(a: unknown, b: unknown): boolean {
  if (Object.is(a, b)) return true;
  if (
    typeof a === "number" &&
    typeof b === "number" &&
    Number.isFinite(a) &&
    Number.isFinite(b) &&
    a === b
  ) {
    return true;
  }
  if (a == null || b == null) return false;
  if (typeof a === "object" || typeof b === "object") {
    try {
      return JSON.stringify(a) === JSON.stringify(b);
    } catch {
      return false;
    }
  }
  return String(a) === String(b);
}

function formatSignedDelta(delta: number): string {
  if (delta === 0) return "0";
  const sign = delta > 0 ? "+" : "−";
  const abs = Math.abs(delta);
  const base = formatNumber(abs);
  return `${sign}${base}`;
}

function paramComparable(value: unknown): string | number | null {
  if (value == null) return null;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value) ?? null;
  } catch {
    return String(value);
  }
}

function truncateText(value: string, max: number): { text: string; truncated: boolean } {
  if (value.length <= max) return { text: value, truncated: false };
  return { text: `${value.slice(0, max)}…`, truncated: true };
}

function stateTone(state: RunRow["state"]): Extract<RunFieldValue, { kind: "pill" }>["tone"] {
  switch (state) {
    case "running":
      return "live";
    case "error":
      return "error";
    case "queued":
      return "warn";
    default:
      return "ok";
  }
}

function samePath(pathname: string, href: string): boolean {
  try {
    const url = new URL(href, window.location.origin);
    return pathname === url.pathname;
  } catch {
    return pathname === href.split("?")[0]?.split("#")[0];
  }
}

function isInteractive(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && Boolean(target.closest("button,a,input,textarea,select"));
}
