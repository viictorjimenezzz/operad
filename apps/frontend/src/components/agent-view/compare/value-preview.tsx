import { MarkdownView } from "@/components/ui";

export function ValuePreview({ value }: { value: unknown }) {
  if (typeof value === "string") {
    if (value.trim().length === 0) return <div className="text-muted">—</div>;
    return (
      <div className="max-h-36 overflow-auto rounded border border-border bg-bg-2 p-2 text-[11px]">
        <MarkdownView value={value} />
      </div>
    );
  }

  if (value == null) return <div className="text-muted">—</div>;
  if (typeof value === "number" || typeof value === "boolean") {
    return <span className="font-mono text-[11px] text-text">{String(value)}</span>;
  }

  return (
    <pre className="max-h-36 overflow-auto rounded border border-border bg-bg-2 p-2 font-mono text-[10px] leading-4 text-text">
      {json(value)}
    </pre>
  );
}

function json(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2) ?? "null";
  } catch {
    return String(value);
  }
}
