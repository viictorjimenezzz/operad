import { HashChip } from "@/components/agent-view/metadata/hash-chip";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type FilteredEventKind = "start" | "end" | "chunk" | "error";

export interface NormalizedAgentEvent {
  type: "agent_event";
  run_id: string;
  agent_path: string;
  kind: "start" | "end" | "error" | "chunk";
  input: unknown;
  output: unknown;
  started_at: number;
  finished_at: number | null;
  metadata: Record<string, unknown>;
  error: { type: string; message: string } | null;
  signature: string;
  preview: string;
  latencyMs: number | null;
  invocationId: string | null;
}

export interface EventRowModel {
  id: string;
  kind: FilteredEventKind;
  startedAt: number;
  label: string;
  hash: string;
  preview: string;
  latencyMs: number | null;
  event: NormalizedAgentEvent;
  chunks?: NormalizedAgentEvent[];
}

interface EventRowProps {
  row: EventRowModel;
  selected: boolean;
  expanded: boolean;
  relativeTime: string;
  onSelect: () => void;
  onToggleExpand?: () => void;
}

function badgeVariant(kind: FilteredEventKind): "default" | "ended" | "error" {
  if (kind === "error") return "error";
  if (kind === "end") return "ended";
  return "default";
}

export function EventRow({
  row,
  selected,
  expanded,
  relativeTime,
  onSelect,
  onToggleExpand,
}: EventRowProps) {
  return (
    <div
      className={cn(
        "border-b border-border/60 px-2 py-1.5 text-left text-[11px]",
        selected ? "bg-bg-2" : "hover:bg-bg-2",
      )}
    >
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onSelect}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
        >
          <span className="w-14 font-mono tabular-nums text-muted">{relativeTime}</span>
          <Badge variant={badgeVariant(row.kind)}>{row.kind}</Badge>
          <span className="truncate font-mono text-text">{row.label}</span>
          {row.latencyMs != null ? (
            <span className="font-mono text-muted">{row.latencyMs.toFixed(1)}ms</span>
          ) : null}
        </button>
        {row.chunks ? (
          <button
            type="button"
            onClick={onToggleExpand}
            className="rounded border border-border bg-bg-2 px-1.5 py-0.5 font-mono text-[10px] text-muted hover:text-text"
            aria-label={expanded ? "Collapse chunk group" : "Expand chunk group"}
          >
            {expanded ? "hide" : "show"} {row.chunks.length}
          </button>
        ) : null}
        <HashChip hash={row.hash} asButton={false} />
      </div>
      <div className="mt-1 truncate font-mono text-[10px] text-muted">{row.preview}</div>

      {expanded && row.chunks ? (
        <div className="mt-2 space-y-1 border-t border-border/60 pt-1">
          {row.chunks.map((chunk, idx) => (
            <button
              key={chunk.signature}
              type="button"
              onClick={onSelect}
              className="flex w-full items-center gap-2 rounded px-1 py-0.5 text-left hover:bg-bg-3"
            >
              <span className="font-mono text-[10px] text-muted">#{idx + 1}</span>
              <span className="truncate font-mono text-[10px] text-muted">{chunk.preview}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
