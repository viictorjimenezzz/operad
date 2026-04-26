/**
 * Three-pane side-by-side diff viewer: before / after / critique.
 * Uses simple line-by-line comparison without an external diff library.
 */

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
                ? "bg-green-900/30 text-green-300"
                : l.type === "removed"
                  ? "bg-red-900/30 text-red-300"
                  : ""
            }
          >
            {l.text || " "}
          </div>
        ))}
      </pre>
    </div>
  );
}

export function PromptDriftDiff({
  before,
  after,
  critique,
}: {
  before: string;
  after: string;
  critique?: string;
}) {
  const { left, right } = diffLines(before, after);
  return (
    <div className="flex gap-3">
      <DiffPane lines={left} label="before" />
      <DiffPane lines={right} label="after" />
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="mb-1 text-[0.68rem] uppercase tracking-[0.08em] text-muted">critique</div>
        {critique ? (
          <pre className="overflow-auto rounded border border-border bg-bg-2 p-2 text-[11px] leading-5 text-muted">
            {critique}
          </pre>
        ) : (
          <div className="rounded border border-border bg-bg-2 p-2 text-[11px] text-muted">
            no gradient critique available
          </div>
        )}
      </div>
    </div>
  );
}
