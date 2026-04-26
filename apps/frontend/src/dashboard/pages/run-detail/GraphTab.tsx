import { GraphPage } from "@/components/agent-view/graph/graph-page";
import { useSidebarAutoCollapse } from "@/components/agent-view/page-shell/use-sidebar-auto-collapse";
import { useParams } from "react-router-dom";

export function GraphTab() {
  useSidebarAutoCollapse();
  const { runId } = useParams<{ runId: string }>();
  if (!runId) return null;

  return <GraphPage runId={runId} />;
}
