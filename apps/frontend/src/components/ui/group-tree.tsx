import { Sparkline } from "@/components/ui/sparkline";
import { StatusDot } from "@/components/ui/status-dot";
import { hashColor } from "@/lib/hash-color";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronRight } from "lucide-react";
import { type ReactNode, useState } from "react";

/**
 * Universal three-level tree for the dashboard sidebar. Levels:
 *   1. group  — collection key (e.g. algorithm class)
 *   2. row    — instance / single run
 *   3. child  — invocations under a multi-invoked instance
 *
 * Caller supplies plain data; the tree handles expand/collapse,
 * indentation, color identity, sparklines, and active-row highlighting.
 *
 * The tree is intentionally not aware of routing or domain; the
 * `onSelect` callback receives the full row, the parent supplies the
 * navigation logic.
 */

export interface GroupTreeRow {
  /** Stable identifier (used for navigation + selection). */
  id: string;
  /** Hash that drives the color identity (defaults to id). */
  colorIdentity?: string;
  /** Title rendered on the row. */
  label: ReactNode;
  /** Secondary text below the title. */
  meta?: ReactNode;
  /** Pill / badge / tag rendered on the trailing edge. */
  trailing?: ReactNode;
  /** Sparkline data to render on the right (optional). */
  sparkline?: Array<number | null>;
  /** Status dot tone. */
  state?: "running" | "ended" | "error" | "idle";
  /** Whether the row is currently selected/active. */
  active?: boolean;
  /** When provided, row is expandable and these are its children. */
  children?: GroupTreeRow[];
  /** When >= 1, displayed as a count chip; useful for grouped invocations. */
  count?: number;
}

export interface GroupTreeGroupProps {
  /** Group label rendered in the section header. */
  label: ReactNode;
  /** Optional count chip in the header. */
  count?: number;
  /** Collapsed by default? */
  defaultOpen?: boolean;
  rows: GroupTreeRow[];
  onSelect: (row: GroupTreeRow) => void;
  /** Render an empty-state when rows is []. */
  empty?: ReactNode;
  /** Hide the section header when the surrounding panel already supplies it. */
  hideHeader?: boolean;
}

export function GroupTreeSection({
  label,
  count,
  defaultOpen = true,
  rows,
  onSelect,
  empty,
  hideHeader,
}: GroupTreeGroupProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      {hideHeader ? null : (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center gap-1.5 border-b border-border px-3 py-1.5 text-[10px] font-medium uppercase tracking-[0.08em] text-muted transition-colors hover:text-text"
          aria-expanded={open}
        >
          {open ? (
            <ChevronDown size={11} className="flex-shrink-0" />
          ) : (
            <ChevronRight size={11} className="flex-shrink-0" />
          )}
          <span className="flex-1 truncate text-left">{label}</span>
          {count != null ? (
            <span className="rounded-full bg-bg-3 px-2 py-0.5 text-[10px] tabular-nums text-muted-2">
              {count}
            </span>
          ) : null}
        </button>
      )}
      {open || hideHeader ? (
        rows.length > 0 ? (
          <ul className="py-0.5">
            {rows.map((row) => (
              <GroupTreeRowView key={row.id} row={row} depth={0} onSelect={onSelect} />
            ))}
          </ul>
        ) : empty ? (
          <div className="px-3 py-2 text-[11px] text-muted-2">{empty}</div>
        ) : null
      ) : null}
    </div>
  );
}

function GroupTreeRowView({
  row,
  depth,
  onSelect,
}: {
  row: GroupTreeRow;
  depth: number;
  onSelect: (row: GroupTreeRow) => void;
}) {
  const [open, setOpen] = useState(true);
  const hasChildren = !!row.children && row.children.length > 0;
  const identity = row.colorIdentity ?? row.id;

  return (
    <li>
      <div
        className={cn(
          "group relative flex items-center gap-2 border-l-2 border-transparent px-3 py-1.5 transition-colors duration-[var(--motion-quick)] ease-out",
          row.active ? "border-l-accent bg-bg-2" : "hover:bg-bg-2/60",
        )}
        style={{ paddingLeft: 12 + depth * 14 }}
      >
        {hasChildren ? (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? "collapse" : "expand"}
            className="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded text-muted-2 hover:text-text"
          >
            {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          </button>
        ) : (
          <span className="inline-block w-4 flex-shrink-0" />
        )}
        <button
          type="button"
          onClick={() => onSelect(row)}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
        >
          <StatusDot identity={identity} size="sm" {...(row.state !== undefined ? { state: row.state } : {})} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 truncate text-[12px] font-medium text-text">
              <span className="min-w-0 truncate">{row.label}</span>
              {row.count != null && row.count > 1 ? (
                <span className="rounded-full bg-bg-3 px-1.5 py-px text-[9px] tabular-nums text-muted-2">
                  {row.count}
                </span>
              ) : null}
            </div>
            {row.meta != null ? (
              <div className="truncate text-[10px] text-muted-2">{row.meta}</div>
            ) : null}
          </div>
          {row.sparkline ? (
            <Sparkline
              values={row.sparkline}
              width={42}
              height={16}
              color={hashColor(identity)}
              className="flex-shrink-0"
            />
          ) : null}
          {row.trailing != null ? (
            <span className="flex-shrink-0 text-[10px] text-muted-2">{row.trailing}</span>
          ) : null}
        </button>
      </div>
      {hasChildren && open ? (
        <ul>
          {row.children!.map((c) => (
            <GroupTreeRowView key={c.id} row={c} depth={depth + 1} onSelect={onSelect} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}
