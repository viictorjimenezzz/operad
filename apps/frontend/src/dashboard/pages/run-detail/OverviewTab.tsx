import { DashboardRenderer } from "@/components/runtime/dashboard-renderer";
import overviewLayoutJson from "@/layouts/agent/overview.json";
import { LayoutSpec } from "@/lib/layout-schema";
import { useParams } from "react-router-dom";

const overviewLayout = LayoutSpec.parse(overviewLayoutJson);

export function OverviewTab() {
  const { runId } = useParams<{ runId: string }>();
  if (!runId) return null;

  return (
    <div className="h-full overflow-auto px-6 py-6">
      <div className="mx-auto max-w-[1100px]">
        <DashboardRenderer layout={overviewLayout} context={{ runId }} />
      </div>
    </div>
  );
}
