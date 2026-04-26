import type { AgentDiffChange } from "@/lib/types";

interface ChangeRowProps {
  change: AgentDiffChange;
}

function tone(kind: string): string {
  if (kind === "added") return "text-ok";
  if (kind === "removed") return "text-err";
  return "text-warn";
}

export function ChangeRow({ change }: ChangeRowProps) {
  const detail = change.detail?.trim() ?? "";
  return (
    <div className="rounded border border-border bg-bg-2 p-2">
      <div className="mb-1 flex items-center justify-between gap-2 text-xs">
        <code className="truncate text-text" title={change.path}>
          {change.path}
        </code>
        <span className={`rounded border border-border px-1 py-0.5 text-[10px] uppercase ${tone(change.kind)}`}>
          {change.kind}
        </span>
      </div>
      {detail.length > 0 ? (
        <pre className="overflow-x-auto whitespace-pre-wrap text-[11px] text-muted">{detail}</pre>
      ) : (
        <div className="text-[11px] text-muted">no detail</div>
      )}
    </div>
  );
}
