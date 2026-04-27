import { AgentHero } from "@/components/agent-view/page-shell/agent-hero";
import {
  AgentTabs,
  type AgentTabSpec,
} from "@/components/agent-view/page-shell/agent-tabs";
import type { RunSummary } from "@/lib/types";
import type { ReactNode } from "react";

export interface AgentChromeProps {
  run: RunSummary;
  langfuseUrl?: string | null;
  hashContent?: string | null;
  basePath: string;
  tabs: AgentTabSpec[];
  rightActions?: ReactNode;
}

export function AgentChrome({
  run,
  langfuseUrl,
  hashContent,
  basePath,
  tabs,
  rightActions,
}: AgentChromeProps) {
  return (
    <header className="flex-shrink-0">
      <AgentHero run={run} langfuseUrl={langfuseUrl ?? null} hashContent={hashContent ?? null} />
      <AgentTabs base={basePath} tabs={tabs} right={rightActions} />
    </header>
  );
}
