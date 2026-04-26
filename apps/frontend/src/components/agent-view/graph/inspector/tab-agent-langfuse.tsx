import { Button } from "@/components/ui";
import { useAgentMeta } from "@/hooks/use-runs";
import { ExternalLink } from "lucide-react";

export function TabAgentLangfuse({ runId, agentPath }: { runId: string; agentPath: string }) {
  const meta = useAgentMeta(runId, agentPath);
  const url = meta.data?.langfuse_search_url ?? null;

  if (meta.isLoading) {
    return <div className="p-5 text-[12px] text-muted-2">loading…</div>;
  }
  if (!url) {
    return (
      <div className="p-5 text-[12px] text-muted-2">Langfuse is not configured for this run.</div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <span className="font-mono text-[11px] text-muted-2">{url}</span>
        <Button
          size="sm"
          variant="ghost"
          className="gap-1"
          onClick={() => window.open(url, "_blank", "noopener,noreferrer")}
        >
          open in new tab
          <ExternalLink size={11} />
        </Button>
      </div>
      <iframe
        title={`Langfuse search · ${agentPath}`}
        src={url}
        className="h-full w-full flex-1 border-0 bg-bg"
      />
    </div>
  );
}
