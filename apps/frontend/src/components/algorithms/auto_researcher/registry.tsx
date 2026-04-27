import {
  AutoResearcherAttemptsTab,
  AutoResearcherBestAnswer,
  AutoResearcherDetailOverview,
  AutoResearcherPlanTab,
} from "@/components/algorithms/auto_researcher/auto-researcher-detail-overview";
import type { ComponentRegistry } from "@json-render/react";

export const autoResearcherRegistry: ComponentRegistry = {
  AutoResearcherDetailOverview: ({ element }) => {
    const p = element.props as {
      dataSummary?: unknown;
      dataIterations?: unknown;
      dataEvents?: unknown;
      dataChildren?: unknown;
    };
    return (
      <AutoResearcherDetailOverview
        dataSummary={p.dataSummary}
        dataIterations={p.dataIterations}
        dataEvents={p.dataEvents}
        dataChildren={p.dataChildren}
      />
    );
  },
  AutoResearcherPlanTab: ({ element }) => {
    const p = element.props as { dataEvents?: unknown; dataChildren?: unknown };
    return <AutoResearcherPlanTab dataEvents={p.dataEvents} dataChildren={p.dataChildren} />;
  },
  AutoResearcherAttemptsTab: ({ element }) => {
    const p = element.props as { dataIterations?: unknown; dataChildren?: unknown };
    return (
      <AutoResearcherAttemptsTab dataIterations={p.dataIterations} dataChildren={p.dataChildren} />
    );
  },
  AutoResearcherBestAnswer: ({ element }) => {
    const p = element.props as { dataChildren?: unknown };
    return <AutoResearcherBestAnswer dataChildren={p.dataChildren} />;
  },
};
