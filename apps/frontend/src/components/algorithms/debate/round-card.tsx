import type { DebateCritique, DebateProposal, DebateRound } from "@/lib/types";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";
import { type KeyboardEvent, type MouseEvent, useState } from "react";

export interface RoundCardProps {
  round: DebateRound;
  roundNumber: number;
  proposerCount?: number;
  gridTemplateColumns?: string;
  isExpanded?: boolean;
  activeCellIndex?: number | null;
  onToggleRound?: () => void;
  onSelectCell?: (proposalIndex: number) => void;
}

export function RoundCard({
  round,
  roundNumber,
  proposerCount = round.proposals.length,
  gridTemplateColumns,
  isExpanded,
  activeCellIndex,
  onToggleRound,
  onSelectCell,
}: RoundCardProps) {
  const [reasoningOpen, setReasoningOpen] = useState<Record<number, boolean>>({});
  const [localExpanded, setLocalExpanded] = useState(false);
  const [localActiveCellIndex, setLocalActiveCellIndex] = useState<number | null>(null);
  const scores = round.scores;
  const maxScore = scores.length > 0 ? Math.max(...scores) : null;
  const columnCount = Math.max(
    1,
    proposerCount,
    round.proposals.length,
    round.critiques.length,
    scores.length,
  );
  const focusedCellIndex = activeCellIndex ?? localActiveCellIndex;
  const expanded = isExpanded ?? (localExpanded || focusedCellIndex != null);
  const template = gridTemplateColumns ?? buildRoundGridTemplate(columnCount, focusedCellIndex);
  const rowHeight =
    focusedCellIndex != null ? "min-h-[320px]" : expanded ? "min-h-[188px]" : "min-h-[92px]";

  const toggleRound = () => {
    if (onToggleRound) {
      onToggleRound();
      return;
    }
    setLocalActiveCellIndex(null);
    setLocalExpanded((current) => !current);
  };

  const selectCell = (index: number) => {
    if (onSelectCell) {
      onSelectCell(index);
      return;
    }
    setLocalExpanded(false);
    setLocalActiveCellIndex((current) => (current === index ? null : index));
  };

  const onRowKeyDown = (event: KeyboardEvent<HTMLTableRowElement>) => {
    if (event.target !== event.currentTarget) return;
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    toggleRound();
  };

  return (
    <tr
      aria-expanded={expanded}
      tabIndex={0}
      className={cn(
        "grid min-w-max items-stretch border-b border-border last:border-b-0",
        rowHeight,
      )}
      style={{ gridTemplateColumns: template }}
      onClick={toggleRound}
      onKeyDown={onRowKeyDown}
    >
      <td className="flex min-w-0 flex-col justify-between bg-bg-2/50 p-3">
        <div>
          <div className="text-[12px] font-medium text-text">Round {roundNumber}</div>
          <div className="mt-1 text-[11px] text-muted">
            {round.proposals.length} props
            <br />
            mean {formatScore(mean(scores))}
          </div>
        </div>
        <div className="font-mono text-[11px] text-muted-2">
          {round.timestamp == null ? "no timestamp" : formatTime(round.timestamp)}
        </div>
      </td>

      {Array.from({ length: columnCount }, (_, index) => {
        const proposal = round.proposals[index] ?? null;
        if (!proposal) {
          return (
            <td
              key={`empty-${index}`}
              className="flex min-w-0 items-center justify-center border-l border-border bg-bg-1 p-3 text-[12px] text-muted-2"
            >
              No proposal recorded.
            </td>
          );
        }

        const critique = findCritique(round.critiques, proposal, index);
        const score = scores[index] ?? critique?.score ?? null;
        const isBest = maxScore != null && score === maxScore;
        const showReasoning = Boolean(reasoningOpen[index]);
        const focused = focusedCellIndex === index;
        const text = showReasoning
          ? critique?.comments || "No critique recorded for this proposal."
          : proposal.content || "No proposal text recorded.";
        const proposalLabel = `Proposal ${index + 1}`;
        return (
          <td
            key={`${proposal.author || "proposer"}-${index}`}
            aria-label={`Round ${roundNumber} ${proposalLabel}`}
            aria-expanded={focused}
            className={cn(
              "relative min-w-0 border-l border-border bg-bg-1 px-3 py-2 text-left transition-colors hover:bg-bg-2/30",
              focused && "bg-bg-2/35 shadow-[inset_0_0_0_1px_var(--color-border-strong)]",
            )}
            onClick={(event: MouseEvent<HTMLElement>) => {
              event.stopPropagation();
              selectCell(index);
            }}
            onKeyDown={(event: KeyboardEvent<HTMLElement>) => {
              if (event.target !== event.currentTarget) return;
              if (event.key !== "Enter" && event.key !== " ") return;
              event.preventDefault();
              event.stopPropagation();
              selectCell(index);
            }}
          >
            {score != null ? (
              <button
                type="button"
                className={scoreButtonClass(isBest)}
                aria-label={
                  showReasoning
                    ? `show proposal for ${proposalLabel}`
                    : `show critic reasoning for ${proposalLabel}`
                }
                onClick={(event) => {
                  event.stopPropagation();
                  setReasoningOpen((current) => ({
                    ...current,
                    [index]: !current[index],
                  }));
                }}
              >
                {showReasoning ? <X size={13} /> : formatScore(score)}
              </button>
            ) : null}

            <p
              className={cn(
                "m-0 whitespace-pre-wrap break-words pr-14 text-[12px] leading-5 text-text/80",
                focused
                  ? "max-h-[280px] overflow-y-auto"
                  : expanded
                    ? "line-clamp-6"
                    : "line-clamp-3",
              )}
            >
              {text}
            </p>
          </td>
        );
      })}
    </tr>
  );
}

export function buildRoundGridTemplate(
  proposerCount: number,
  activeProposalIndex: number | null = null,
): string {
  const columns = Array.from({ length: proposerCount }, (_, index) =>
    activeProposalIndex === index ? "minmax(420px, 560px)" : "minmax(220px, 260px)",
  );
  return ["104px", ...columns].join(" ");
}

function scoreButtonClass(isBest: boolean): string {
  return cn(
    "absolute right-2 top-2 z-[1] inline-flex h-7 min-w-11 items-center justify-center rounded px-2 font-mono text-[11px] tabular-nums transition-colors",
    isBest
      ? "bg-[var(--color-ok)]/15 text-[var(--color-ok)] hover:bg-[var(--color-ok)]/25"
      : "bg-bg-3 text-text hover:bg-bg-2",
  );
}

function findCritique(
  critiques: DebateCritique[],
  proposal: DebateProposal,
  index: number,
): DebateCritique | null {
  if (proposal.author) {
    const match = critiques.find((critique) => critique.target_author === proposal.author);
    if (match) return match;
  }
  return critiques[index] ?? null;
}

function mean(values: number[]): number | null {
  if (values.length === 0) return null;
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function formatScore(value: number | null | undefined): string {
  return typeof value === "number" ? value.toFixed(2) : "n/a";
}

function formatTime(value: number): string {
  return new Date(value * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}
