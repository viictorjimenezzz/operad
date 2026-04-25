import { cn } from "@/lib/utils";
import { Star } from "lucide-react";
import { useIsPinned, usePinnedRuns } from "@/hooks/use-pinned-runs";

interface PinIndicatorProps {
  runId: string;
  size?: "sm" | "md";
  className?: string;
}

export function PinIndicator({
  runId,
  size = "md",
  className,
}: PinIndicatorProps) {
  const pinned = useIsPinned(runId);
  const { toggle } = usePinnedRuns();
  const iconSize = size === "sm" ? "h-3 w-3" : "h-4 w-4";

  return (
    <button
      type="button"
      aria-label={pinned ? "Unpin run" : "Pin run"}
      onClick={() => toggle(runId)}
      className={cn(
        "rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
    >
      <Star
        className={cn(
          iconSize,
          pinned
            ? "fill-yellow-400 stroke-yellow-400"
            : "stroke-muted-foreground",
        )}
      />
    </button>
  );
}
