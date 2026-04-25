/**
 * Per-algorithm layout selector. Layouts are imported as JSON
 * (Vite bundles them as objects), Zod-parsed at module load to fail
 * fast on schema regressions, and looked up by `algorithm_path`.
 *
 * Add a new algorithm by dropping a `<algo>.json` here, importing it,
 * and registering it in `algorithmLayouts`. Anything not in the map
 * falls back to `default.json`.
 */
import { LayoutSpec } from "@/lib/layout-schema";
import beamRaw from "./beam.json";
import debateRaw from "./debate.json";
import defaultRaw from "./default.json";
import evogradientRaw from "./evogradient.json";
import trainerRaw from "./trainer.json";

const defaultLayout = LayoutSpec.parse(defaultRaw);
const algorithmLayouts: Record<string, LayoutSpec> = {
  EvoGradient: LayoutSpec.parse(evogradientRaw),
  Trainer: LayoutSpec.parse(trainerRaw),
  Debate: LayoutSpec.parse(debateRaw),
  Beam: LayoutSpec.parse(beamRaw),
};

export function pickLayout(algorithmPath: string | null | undefined): LayoutSpec {
  if (!algorithmPath) return defaultLayout;
  return algorithmLayouts[algorithmPath] ?? defaultLayout;
}

export const layouts = {
  default: defaultLayout,
  ...algorithmLayouts,
} as const;
