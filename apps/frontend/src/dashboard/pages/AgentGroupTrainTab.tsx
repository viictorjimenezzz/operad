import { ParametersTab } from "@/components/agent-view/parameter-evolution/parameters-tab";
import { useParams } from "react-router-dom";

export function AgentGroupTrainTab() {
  const { hashContent } = useParams<{ hashContent: string }>();
  if (!hashContent) return null;

  return (
    <div className="h-full overflow-auto p-4">
      <ParametersTab hashContent={hashContent} scope="group" />
    </div>
  );
}
