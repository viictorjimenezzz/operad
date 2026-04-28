import { EmptyState } from "@/components/ui/empty-state";

export interface PromptColumn {
  runId: string;
  label: string;
  text: string;
}

interface MultiPromptDiffProps {
  prompts: PromptColumn[];
}

type DiffLine = { text: string; type: "added" | "removed" | "unchanged" };

function diffLines(before: string, after: string): { left: DiffLine[]; right: DiffLine[] } {
  const leftLines = before.split("\n");
  const rightLines = after.split("\n");
  const maxLen = Math.max(leftLines.length, rightLines.length);
  const left: DiffLine[] = [];
  const right: DiffLine[] = [];
  for (let i = 0; i < maxLen; i++) {
    const l = leftLines[i] ?? "";
    const r = rightLines[i] ?? "";
    if (l === r) {
      left.push({ text: l, type: "unchanged" });
      right.push({ text: r, type: "unchanged" });
    } else {
      left.push({ text: l, type: "removed" });
      right.push({ text: r, type: "added" });
    }
  }
  return { left, right };
}

function tokenize(text: string): string[] {
  return text
    .split(/\s+/)
    .map((t) => t.trim())
    .filter((t) => t.length > 0);
}

function consensusTokenSet(prompts: PromptColumn[]): Set<string> {
  const counts = new Map<string, number>();
  for (const p of prompts) {
    const unique = new Set(tokenize(p.text));
    for (const token of unique) {
      counts.set(token, (counts.get(token) ?? 0) + 1);
    }
  }
  const set = new Set<string>();
  for (const [token, count] of counts.entries()) {
    if (count >= 2) set.add(token);
  }
  return set;
}

function DiffPane({ lines, label }: { lines: DiffLine[]; label: string }) {
  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <div className="mb-1 text-[0.68rem] uppercase tracking-[0.08em] text-muted">{label}</div>
      <pre className="overflow-auto rounded border border-border bg-bg-2 p-2 text-[11px] leading-5">
        {lines.map((l, i) => (
          <div
            key={i}
            className={
              l.type === "added"
                ? "bg-ok-dim/50 text-ok"
                : l.type === "removed"
                  ? "bg-err-dim/50 text-err"
                  : ""
            }
          >
            {l.text || "\u00a0"}
          </div>
        ))}
      </pre>
    </div>
  );
}

export function MultiPromptDiff({ prompts }: MultiPromptDiffProps) {
  if (prompts.length < 2) {
    return (
      <EmptyState
        title="not enough prompts"
        description="select at least two runs to compare prompt text"
      />
    );
  }

  if (prompts.length === 2) {
    const before = prompts[0];
    const after = prompts[1];
    if (!before || !after) {
      return (
        <EmptyState
          title="not enough prompts"
          description="select at least two runs to compare prompt text"
        />
      );
    }
    const { left, right } = diffLines(before.text, after.text);
    return (
      <div className="flex gap-3">
        <DiffPane lines={left} label={before.label} />
        <DiffPane lines={right} label={after.label} />
      </div>
    );
  }

  const consensus = consensusTokenSet(prompts);

  return (
    <div className="grid gap-3 md:grid-cols-3">
      {prompts.map((p) => {
        const tokens = tokenize(p.text);
        return (
          <div key={p.runId} className="min-w-0 rounded border border-border bg-bg-2 p-2">
            <div className="mb-2 text-[0.68rem] uppercase tracking-[0.08em] text-muted">
              {p.label}
            </div>
            <div className="text-[11px] leading-5">
              {tokens.length === 0 ? <span className="text-muted">(no prompt text)</span> : null}
              {tokens.map((token, i) => (
                <span
                  key={`${p.runId}-${i}`}
                  className={consensus.has(token) ? "rounded bg-ok/20 px-1 text-ok" : undefined}
                >
                  {token}
                  {i < tokens.length - 1 ? " " : ""}
                </span>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export const _multiPromptDiff = {
  tokenize,
  consensusTokenSet,
};
