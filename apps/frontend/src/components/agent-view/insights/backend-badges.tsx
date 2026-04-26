import { Badge } from "@/components/ui/badge";
import type { AgentMetaResponse } from "@/lib/types";

interface BackendBadgesProps {
  meta: AgentMetaResponse | null | undefined;
}

export function BackendBadges({ meta }: BackendBadgesProps) {
  const config = (meta?.config ?? {}) as Record<string, unknown>;
  const sampling = (config.sampling ?? {}) as Record<string, unknown>;
  const io = (config.io ?? {}) as Record<string, unknown>;

  const chips = [
    String(config.backend ?? "unknown"),
    String(config.model ?? "unknown-model"),
    `T ${sampling.temperature ?? "-"}`,
    `top_p ${sampling.top_p ?? "-"}`,
    String(io.structured_output ? "structured" : "freeform"),
    String(io.renderer ?? "xml"),
  ];

  return (
    <div className="flex flex-wrap gap-1.5">
      {chips.map((chip) => (
        <Badge key={chip} variant="default" className="normal-case tracking-normal">
          {chip}
        </Badge>
      ))}
    </div>
  );
}
