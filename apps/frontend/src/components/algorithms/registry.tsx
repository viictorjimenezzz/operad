import { autoResearcherRegistry } from "@/components/algorithms/auto_researcher/registry";
import { beamRegistry } from "@/components/algorithms/beam/registry";
import { debateRegistry } from "@/components/algorithms/debate/registry";
import { evoGradientRegistry } from "@/components/algorithms/evogradient/registry";
import { oproRegistry } from "@/components/algorithms/opro/registry";
import { selfRefineRegistry } from "@/components/algorithms/selfrefine/registry";
import { sweepRegistry } from "@/components/algorithms/sweep/registry";
import { talkerReasonerRegistry } from "@/components/algorithms/talker_reasoner/registry";
import { trainerRegistry } from "@/components/algorithms/trainer/registry";
import { verifierRegistry } from "@/components/algorithms/verifier/registry";
import type { ComponentRegistry } from "@json-render/react";

export const algorithmsRegistry: ComponentRegistry = {
  ...evoGradientRegistry,
  ...oproRegistry,
  ...trainerRegistry,
  ...beamRegistry,
  ...debateRegistry,
  ...selfRefineRegistry,
  ...autoResearcherRegistry,
  ...sweepRegistry,
  ...verifierRegistry,
  ...talkerReasonerRegistry,
};
