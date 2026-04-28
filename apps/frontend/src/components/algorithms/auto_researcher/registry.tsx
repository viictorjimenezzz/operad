import { AutoResearcherAttemptsTab } from "@/components/algorithms/auto_researcher/attempts-tab";
import { AutoResearcherBestTab } from "@/components/algorithms/auto_researcher/best-tab";
import { AutoResearcherPlanTab } from "@/components/algorithms/auto_researcher/plan-tab";
import type { ComponentRegistry } from "@json-render/react";

export const autoResearcherRegistry: ComponentRegistry = {
  AutoResearcherPlanTab: ({ element }) => {
    const p = element.props as { dataEvents?: unknown };
    return <AutoResearcherPlanTab dataEvents={p.dataEvents} />;
  },
  AutoResearcherAttemptsTab: ({ element }) => {
    const p = element.props as { dataIterations?: unknown };
    return <AutoResearcherAttemptsTab dataIterations={p.dataIterations} />;
  },
  AutoResearcherBestTab: ({ element }) => {
    const p = element.props as {
      dataSummary?: unknown;
      dataIterations?: unknown;
      dataEvents?: unknown;
    };
    return (
      <AutoResearcherBestTab
        dataSummary={p.dataSummary}
        dataIterations={p.dataIterations}
        dataEvents={p.dataEvents}
      />
    );
  },
};
