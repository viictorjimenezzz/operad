import { Button } from "@/components/ui/button";
import { JsonView } from "@/components/ui/json-view";
import type { CassetteDeterminismResponse } from "@/lib/types";

interface ReplayControlsProps {
  onReplay: () => void;
  onDeterminism: () => void;
  replaying: boolean;
  checking: boolean;
  result: CassetteDeterminismResponse | null;
}

export function ReplayControls({
  onReplay,
  onDeterminism,
  replaying,
  checking,
  result,
}: ReplayControlsProps) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="primary" onClick={onReplay} disabled={replaying}>
          {replaying ? "replaying…" : "replay"}
        </Button>
        <Button size="sm" onClick={onDeterminism} disabled={checking}>
          {checking ? "checking…" : "determinism"}
        </Button>
        {result && (
          <span
            className={`rounded-md border px-2 py-1 text-[10px] uppercase tracking-[0.08em] ${
              result.ok
                ? "border-ok bg-ok-dim text-ok"
                : "border-err bg-err-dim text-err"
            }`}
          >
            {result.ok ? "byte-equal" : "drift"}
          </span>
        )}
      </div>
      {result && !result.ok && result.diff.length > 0 && (
        <details>
          <summary className="cursor-pointer text-[11px] text-muted">show diff</summary>
          <div className="mt-2">
            <JsonView value={result.diff} collapsed />
          </div>
        </details>
      )}
    </div>
  );
}
