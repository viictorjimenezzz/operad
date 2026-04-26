import { HashChip } from "@/components/agent-view/metadata/hash-chip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AgentInvocation, RunSummary } from "@/lib/types";
import { useUIStore } from "@/stores";

interface FingerprintCardProps {
  summary: RunSummary | null | undefined;
  latest: AgentInvocation | null;
}

export function FingerprintCard({ summary, latest }: FingerprintCardProps) {
  const openDrawer = useUIStore((s) => s.openDrawer);
  const hashes: Array<{ key: string; value: string | null | undefined }> = [
    { key: "hash_model", value: null },
    { key: "hash_prompt", value: latest?.hash_prompt },
    { key: "hash_graph", value: null },
    { key: "hash_input", value: latest?.hash_input },
    { key: "hash_output_schema", value: null },
    { key: "hash_config", value: null },
    { key: "hash_content", value: latest?.hash_content },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>fingerprint</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        {hashes.map((h) => (
          <div key={h.key} className="flex items-center justify-between gap-2 text-[11px]">
            <span className="text-muted">{h.key}</span>
            <div className="flex items-center gap-1">
              <HashChip value={h.value} />
              <Button
                size="sm"
                variant="ghost"
                className="h-5 px-1 text-[10px] text-muted"
                title="find runs (soon)"
                onClick={() => {
                  if (!h.value) return;
                  openDrawer("events", {
                    hash: h.key,
                    value: h.value,
                    soon: true,
                    runId: summary?.run_id,
                  });
                }}
              >
                soon
              </Button>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
