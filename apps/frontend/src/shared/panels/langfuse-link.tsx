import { useManifest } from "@/hooks/use-runs";
import { langfuseUrlFor } from "@/lib/langfuse";
import { Button } from "@/shared/ui/button";

export function LangfuseLink({ runId }: { runId: string | null }) {
  const manifest = useManifest();
  const base = manifest.data?.langfuseUrl ?? null;
  if (!base || !runId) return null;
  const href = langfuseUrlFor(base, runId);
  return (
    <Button
      variant="ghost"
      size="sm"
      className="self-start"
      onClick={() => window.open(href, "_blank", "noopener")}
    >
      view in langfuse →
    </Button>
  );
}
