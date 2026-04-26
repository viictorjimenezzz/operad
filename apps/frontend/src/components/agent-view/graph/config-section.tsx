import { cn } from "@/lib/utils";
import { ChevronDown } from "lucide-react";
import { useMemo, useState } from "react";

interface ConfigSectionProps {
  config: Record<string, unknown> | null | undefined;
}

function flatten(
  input: Record<string, unknown>,
  prefix = "",
): Array<{ key: string; value: string }> {
  const out: Array<{ key: string; value: string }> = [];
  for (const [k, v] of Object.entries(input)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v != null && typeof v === "object" && !Array.isArray(v)) {
      out.push(...flatten(v as Record<string, unknown>, key));
    } else {
      out.push({ key, value: JSON.stringify(v) });
    }
  }
  return out;
}

export function ConfigSection({ config }: ConfigSectionProps) {
  const [open, setOpen] = useState(false);
  const rows = useMemo(() => flatten(config ?? {}), [config]);

  const model = (config?.model as string | undefined) ?? "-";
  const backend = (config?.backend as string | undefined) ?? "-";
  const sampling = (config?.sampling as Record<string, unknown> | undefined) ?? {};
  const temperature = sampling.temperature as number | undefined;

  return (
    <div className="rounded border border-border bg-bg-2">
      <button
        type="button"
        className="flex w-full items-center justify-between px-2 py-1.5 text-left text-[11px]"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="text-muted">configuration</span>
        <span className="flex items-center gap-2 text-text">
          <code>{backend}</code>
          <code>{model}</code>
          <code>T {temperature ?? "-"}</code>
          <ChevronDown
            className={cn("h-3.5 w-3.5 transition-transform", open ? "rotate-180" : "rotate-0")}
          />
        </span>
      </button>
      {open ? (
        <div className="max-h-48 space-y-1 overflow-auto border-t border-border px-2 py-1.5">
          {rows.map((row) => (
            <div key={row.key} className="grid grid-cols-[1fr_1fr] gap-2 text-[11px]">
              <code className="truncate text-muted">{row.key}</code>
              <code className="truncate text-text" title={row.value}>
                {row.value}
              </code>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
