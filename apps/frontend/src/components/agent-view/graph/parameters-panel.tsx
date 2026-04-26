import { Button } from "@/components/ui/button";
import type { AgentParametersResponse } from "@/lib/types";
import { useMemo, useState } from "react";

interface ParametersPanelProps {
  agentPath: string;
  data: AgentParametersResponse | null | undefined;
  onOpenGradient: (paramPath: string) => void;
}

function toPreview(value: unknown): string {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function constraintSummary(constraint: unknown): string {
  if (!constraint || typeof constraint !== "object") return "-";
  const row = constraint as Record<string, unknown>;
  if (row.kind === "numeric") {
    const min = row.min == null ? "-inf" : String(row.min);
    const max = row.max == null ? "+inf" : String(row.max);
    return `${min} <= x <= ${max}`;
  }
  if (row.kind === "vocab" && Array.isArray(row.allowed)) {
    return `vocab: ${row.allowed.slice(0, 3).map(String).join(", ")}${row.allowed.length > 3 ? "…" : ""}`;
  }
  if (row.kind === "text") {
    const max = row.max_length;
    if (typeof max === "number") return `len <= ${max}`;
  }
  return JSON.stringify(constraint);
}

export function ParametersPanel({ agentPath, data, onOpenGradient }: ParametersPanelProps) {
  const rows = data?.parameters ?? [];
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const count = rows.length;

  const rowsWithPreview = useMemo(
    () =>
      rows.map((row) => {
        const text = toPreview(row.value);
        return { row, text, truncated: text.length > 80 };
      }),
    [rows],
  );

  return (
    <details className="rounded border border-border bg-bg-2 p-2" open>
      <summary className="cursor-pointer text-[11px] text-muted">parameters ({count} trainable)</summary>
      <div className="mt-2 space-y-2">
        {count === 0 ? (
          <div className="text-[11px] text-muted">
            no trainable parameters · use <code>{agentPath}.mark_trainable(role=True, task=True)</code>
          </div>
        ) : (
          rowsWithPreview.map(({ row, text, truncated }) => {
            const isOpen = expanded.has(row.path);
            const value = truncated && !isOpen ? `${text.slice(0, 80)}…` : text;
            return (
              <div key={row.path} className="rounded border border-border/70 bg-bg-1 p-2 text-[11px]">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <code className="truncate text-text" title={row.path}>
                    {row.path}
                  </code>
                  <span className="rounded border border-border px-1 py-0.5 text-[10px] text-muted">{row.type}</span>
                </div>
                <div className="mb-1 whitespace-pre-wrap break-words font-mono text-text">{value || "-"}</div>
                <div className="flex items-center justify-between gap-2 text-[10px] text-muted">
                  <span title={row.constraint ? JSON.stringify(row.constraint) : "-"}>
                    constraint: {constraintSummary(row.constraint)}
                  </span>
                  <div className="flex items-center gap-1">
                    {row.grad ? (
                      <button
                        type="button"
                        className="rounded border border-border bg-bg-2 px-1 py-0.5 text-[10px] text-warn"
                        title={row.grad.message || "gradient"}
                        onClick={() => onOpenGradient(row.path)}
                      >
                        grad
                      </button>
                    ) : null}
                    {truncated ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-5 px-1 text-[10px]"
                        onClick={() => {
                          setExpanded((prev) => {
                            const next = new Set(prev);
                            if (next.has(row.path)) next.delete(row.path);
                            else next.add(row.path);
                            return next;
                          });
                        }}
                      >
                        {isOpen ? "collapse" : "expand"}
                      </Button>
                    ) : null}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </details>
  );
}
