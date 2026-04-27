import { DashboardRenderer } from "@/components/runtime/dashboard-renderer";
import overviewLayoutJson from "@/layouts/agent/overview.json";
import { LayoutSpec } from "@/lib/layout-schema";
import { useParams } from "react-router-dom";

const overviewLayout = LayoutSpec.parse(overviewLayoutJson);

export function OverviewTab() {
  const { runId } = useParams<{ runId: string }>();
  if (!runId) return null;

  return (
    <div className="h-full overflow-auto">
      <div className="p-4">
        <DashboardRenderer layout={overviewLayout} context={{ runId }} />
      </div>
    </div>
  );
}
