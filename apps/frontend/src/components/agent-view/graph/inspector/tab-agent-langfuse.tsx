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
    <div className="flex h-full items-center justify-center p-5">
      <div className="max-w-md rounded-xl border border-border bg-bg-1 p-5 text-[12px] text-muted">
        <div className="text-[13px] font-medium text-text">Open Langfuse in a new tab</div>
        <p className="mt-2 leading-5">
          Langfuse usually blocks iframe embedding with browser security headers, so the dashboard
          links out instead of showing a broken embedded page.
        </p>
        <div className="mt-3 break-all rounded-md bg-bg-inset p-2 font-mono text-[11px] text-muted-2">
          {url}
        </div>
        <Button
          size="sm"
          variant="primary"
          className="mt-4 gap-1"
          onClick={() => window.open(url, "_blank", "noopener,noreferrer")}
        >
          open in new tab
          <ExternalLink size={11} />
        </Button>
      </div>
    </div>
  );
}
