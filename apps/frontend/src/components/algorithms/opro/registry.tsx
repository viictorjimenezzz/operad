import { OPROCandidatesTab } from "@/components/algorithms/opro/opro-candidates-tab";
import { OPRODetailOverview } from "@/components/algorithms/opro/opro-detail-overview";
import { OPROHistoryTab } from "@/components/algorithms/opro/opro-history-tab";
import { OPROParameterTab } from "@/components/algorithms/opro/opro-parameter-tab";
import type { ComponentRegistry } from "@json-render/react";

export const oproRegistry: ComponentRegistry = {
  OPRODetailOverview: ({ element }) => {
    const p = element.props as {
      dataSummary?: unknown;
      dataIterations?: unknown;
      dataEvents?: unknown;
      dataChildren?: unknown;
      runId?: string;
    };
    return (
      <OPRODetailOverview
        summary={p.dataSummary}
        iterations={p.dataIterations}
        events={p.dataEvents}
        dataChildren={p.dataChildren}
        runId={p.runId ?? ""}
      />
    );
  },
  OPROHistoryTab: ({ element }) => {
    const p = element.props as {
      dataIterations?: unknown;
      dataEvents?: unknown;
      dataChildren?: unknown;
    };
    return (
      <OPROHistoryTab
        dataIterations={p.dataIterations}
        dataEvents={p.dataEvents}
        dataChildren={p.dataChildren}
      />
    );
  },
  OPROCandidatesTab: ({ element }) => {
    const p = element.props as {
      dataIterations?: unknown;
      dataEvents?: unknown;
      dataChildren?: unknown;
      runId?: string;
    };
    return (
      <OPROCandidatesTab
        dataIterations={p.dataIterations}
        dataEvents={p.dataEvents}
        dataChildren={p.dataChildren}
        runId={p.runId ?? ""}
      />
    );
  },
  OPROParameterTab: ({ element }) => {
    const p = element.props as {
      dataIterations?: unknown;
      dataEvents?: unknown;
      dataChildren?: unknown;
    };
    return (
      <OPROParameterTab
        dataIterations={p.dataIterations}
        dataEvents={p.dataEvents}
        dataChildren={p.dataChildren}
      />
    );
  },
};
