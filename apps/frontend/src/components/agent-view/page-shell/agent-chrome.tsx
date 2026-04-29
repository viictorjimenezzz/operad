import { type AgentTabSpec, AgentTabs } from "@/components/agent-view/page-shell/agent-tabs";
import type { BreadcrumbItem } from "@/components/ui";
import type { RunSummary } from "@/lib/types";
import { cn, truncateMiddle } from "@/lib/utils";
import { ChevronRight } from "lucide-react";
import { Fragment } from "react";
import { Link } from "react-router-dom";

/**
 * Slim invocation chrome: tabs on the left, path context on the right.
 * Runtime KPIs live inside the overview canvas.
 */
export interface AgentChromeProps {
  run: RunSummary;
  basePath: string;
  tabs: AgentTabSpec[];
  /** Optional preceding breadcrumb crumbs (e.g. group > run). */
  breadcrumbs?: BreadcrumbItem[];
}

export function AgentChrome({ run, basePath, tabs, breadcrumbs }: AgentChromeProps) {
  const className = run.algorithm_class ?? run.root_agent_path?.split(".").at(-1) ?? "Agent";
  const agentPath = run.root_agent_path ?? className;
  const runLabel = truncateMiddle(run.run_id, 24);

  const items: BreadcrumbItem[] = [
    ...(breadcrumbs ?? [{ label: "Agents", to: "/agents" }]),
    { label: agentPath },
    { label: runLabel, mono: true },
  ];

  return (
    <header className="flex-shrink-0">
      <AgentTabs base={basePath} tabs={tabs} right={<AgentBreadcrumb items={items} />} />
    </header>
  );
}

function AgentBreadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav
      aria-label="agent invocation path"
      className="flex min-w-0 items-center gap-1.5 text-[12px]"
    >
      {items.map((item, index) => {
        const last = index === items.length - 1;
        const text = (
          <span
            className={cn(
              item.mono ? "font-mono text-[11px]" : "",
              "min-w-0 truncate",
              last ? "text-text" : "text-muted",
            )}
            title={typeof item.label === "string" ? item.label : undefined}
          >
            {item.label}
          </span>
        );
        return (
          <Fragment key={`${index}-${String(item.label)}`}>
            {item.to ? (
              <Link
                to={item.to}
                aria-current={last ? "page" : undefined}
                className="min-w-0 truncate text-muted transition-colors hover:text-text"
              >
                {text}
              </Link>
            ) : (
              text
            )}
            {!last ? (
              <ChevronRight aria-hidden size={12} className="flex-shrink-0 text-muted-2" />
            ) : null}
          </Fragment>
        );
      })}
    </nav>
  );
}
