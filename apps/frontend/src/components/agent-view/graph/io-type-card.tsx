import { cn } from "@/lib/utils";
import { Handle, type NodeProps, Position } from "@xyflow/react";

export type IoTypeCardData = {
  label: string;
  fields: Array<{ name: string; type: string; description: string; system: boolean }>;
  selected: boolean;
  dimmed: boolean;
  onSelect: () => void;
};

export function IoTypeCard({ data }: NodeProps) {
  const d = data as IoTypeCardData;
  const previewFields = d.fields.filter((f) => !f.system).slice(0, 3);
  const more = Math.max(0, d.fields.length - previewFields.length);

  return (
    <button
      type="button"
      aria-label={`I/O type ${d.label}`}
      onClick={d.onSelect}
      className={cn(
        "group relative flex min-w-[200px] flex-col gap-1.5 rounded-2xl border bg-bg-1 px-3 py-2.5 text-left transition-all duration-[var(--motion-quick)]",
        "shadow-[var(--shadow-card-soft)]",
        d.selected
          ? "border-accent ring-2 ring-[--color-accent-dim]"
          : "border-border hover:border-border-strong",
        d.dimmed && "opacity-40",
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!h-2 !w-2 !border-border !bg-bg-2"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!h-2 !w-2 !border-border !bg-bg-2"
      />
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-mono text-[13px] font-medium text-text">{d.label}</span>
        <span className="text-[10px] tabular-nums text-muted-2">
          {d.fields.length} field{d.fields.length === 1 ? "" : "s"}
        </span>
      </div>
      {previewFields.length > 0 ? (
        <ul className="space-y-0.5">
          {previewFields.map((f) => (
            <li
              key={f.name}
              className="flex items-baseline gap-2 truncate font-mono text-[10px] text-muted"
            >
              <span className="truncate text-text">{f.name}</span>
              <span className="truncate text-muted-2">{f.type}</span>
            </li>
          ))}
          {more > 0 ? <li className="text-[10px] text-muted-2">+{more} more</li> : null}
        </ul>
      ) : null}
    </button>
  );
}
