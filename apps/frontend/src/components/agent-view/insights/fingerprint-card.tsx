import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { hashColor, hashColorDim } from "@/lib/hash-color";
import { truncateMiddle } from "@/lib/utils";
import { useUIStore } from "@/stores/ui";
import { Copy, Search } from "lucide-react";
import { useMemo, useState } from "react";

export interface FingerprintCardProps {
  hashes: Record<string, string | null>;
}

const HASH_KEYS = [
  "hash_model",
  "hash_prompt",
  "hash_graph",
  "hash_input",
  "hash_output_schema",
  "hash_config",
  "hash_content",
] as const;

export function FingerprintCard({ hashes }: FingerprintCardProps) {
  const openDrawer = useUIStore((s) => s.openDrawer);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const titleHash = hashes.hash_content ?? hashes.hash_prompt ?? "fingerprint";
  const titleStyle = useMemo(
    () => ({
      backgroundColor: hashColorDim(titleHash),
      borderColor: hashColor(titleHash),
    }),
    [titleHash],
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          fingerprint
          <span
            className="inline-flex rounded border px-1.5 py-0.5 font-mono text-[0.64rem] normal-case"
            style={titleStyle}
          >
            {truncateMiddle(titleHash, 8)}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {HASH_KEYS.map((key) => {
          const value = hashes[key] ?? null;
          const style = value
            ? {
                backgroundColor: hashColorDim(value),
                borderColor: hashColor(value),
              }
            : undefined;
          return (
            <div key={key} className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-2">
              <span className="font-mono text-[0.68rem] text-muted">{key}</span>
              <span
                className="inline-flex min-w-[72px] rounded border px-1.5 py-0.5 font-mono text-[0.68rem] text-text"
                style={style}
                title={value ?? "missing"}
              >
                {value ? truncateMiddle(value, 10) : "—"}
              </span>
              <button
                type="button"
                className="rounded border border-border p-1 text-muted hover:text-text disabled:opacity-40"
                aria-label={`copy ${key}`}
                disabled={!value}
                onClick={async () => {
                  if (!value) return;
                  try {
                    await navigator.clipboard.writeText(value);
                    setCopiedKey(key);
                    setTimeout(
                      () => setCopiedKey((current) => (current === key ? null : current)),
                      1100,
                    );
                  } catch {
                    setCopiedKey(null);
                  }
                }}
              >
                <Copy size={12} />
              </button>
              <button
                type="button"
                className="rounded border border-border p-1 text-muted hover:text-text disabled:opacity-40"
                aria-label={`find runs for ${key}`}
                title="find runs (soon)"
                disabled={!value}
                onClick={() => {
                  if (!value) return;
                  openDrawer("find-runs", { hash: key, value });
                }}
              >
                <Search size={12} />
              </button>
            </div>
          );
        })}
        {copiedKey ? <div className="text-[0.68rem] text-ok">copied {copiedKey}</div> : null}
      </CardContent>
    </Card>
  );
}
