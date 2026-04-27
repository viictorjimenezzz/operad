import { beamRegistry } from "@/components/algorithms/beam/registry";
import { debateRegistry } from "@/components/algorithms/debate/registry";
import { evoGradientRegistry } from "@/components/algorithms/evogradient/registry";
import { sweepRegistry } from "@/components/algorithms/sweep/registry";
import { talkerReasonerRegistry } from "@/components/algorithms/talker_reasoner/registry";
import { trainerRegistry } from "@/components/algorithms/trainer/registry";
import type { ComponentRegistry } from "@json-render/react";

export const algorithmsRegistry: ComponentRegistry = {
  ...evoGradientRegistry,
  ...trainerRegistry,
  ...beamRegistry,
  ...debateRegistry,
  ...sweepRegistry,
  ...talkerReasonerRegistry,
};
