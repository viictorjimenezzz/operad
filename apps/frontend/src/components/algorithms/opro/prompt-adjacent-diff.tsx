import { MarkdownView } from "@/components/ui";
import { cn } from "@/lib/utils";
import { useState } from "react";

type DiffLine = { before: string; after: string };

export function AdjacentPromptDiff({
  before,
  after,
  beforeLabel = "previous",
  afterLabel = "current",
}: {
  before: string;
  after: string;
  beforeLabel?: string;
  afterLabel?: string;
}) {
  const lines = changedLines(before, after);
  if (lines.length === 0) {
    return (
      <div className="rounded border border-border bg-bg-2 px-2 py-1.5 text-[12px] text-muted">
        no text changes
      </div>
    );
  }
  return (
    <div className="space-y-2 rounded border border-border bg-bg-inset p-2 text-[12px]">
      {lines.map((line, index) => (
        <div key={`${line.before}:${line.after}:${index}`} className="grid gap-2 md:grid-cols-2">
          <DiffCell label={beforeLabel} value={line.before || "(empty)"} tone="before" />
          <DiffCell label={afterLabel} value={line.after || "(empty)"} tone="after" />
        </div>
      ))}
    </div>
  );
}

export function FullValueToggle({ value }: { value: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="rounded border border-border bg-bg-2 px-2 py-1 text-[12px] text-muted transition-colors hover:border-border-strong hover:text-text"
      >
        {open ? "Hide full value" : "View full value"}
      </button>
      {open ? (
        <div className="mt-2 max-h-72 overflow-auto border-t border-border pt-2">
          <MarkdownView value={value} />
        </div>
      ) : null}
    </div>
  );
}

function DiffCell({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "before" | "after";
}) {
  return (
    <div
      className={cn(
        "min-w-0 rounded border px-2 py-1.5 font-mono text-[11px] leading-5",
        tone === "before"
          ? "border-[--color-err-dim] bg-[--color-err-dim]/25 text-[--color-err]"
          : "border-[--color-ok-dim] bg-[--color-ok-dim]/25 text-[--color-ok]",
      )}
    >
      <div className="mb-1 text-[10px] uppercase tracking-[0.06em] text-muted-2">{label}</div>
      <div className="whitespace-pre-wrap">{value}</div>
    </div>
  );
}

function changedLines(before: string, after: string): DiffLine[] {
  const left = before.split("\n");
  const right = after.split("\n");
  const max = Math.max(left.length, right.length);
  const out: DiffLine[] = [];
  for (let index = 0; index < max; index += 1) {
    const beforeLine = left[index] ?? "";
    const afterLine = right[index] ?? "";
    if (beforeLine !== afterLine) out.push({ before: beforeLine, after: afterLine });
  }
  return out.slice(0, 12);
}

