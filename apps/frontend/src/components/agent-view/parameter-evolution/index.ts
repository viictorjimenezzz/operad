import { EmptyState } from "@/components/ui";
import { createElement } from "react";
import { CategoricalEvolution } from "./categorical-evolution";
import { ConfigurationEvolution } from "./configuration-evolution";
import {
  type FloatConstraint,
  FloatEvolution,
  type ParameterEvolutionPoint,
} from "./float-evolution";

export { CategoricalEvolution } from "./categorical-evolution";
export type { CategoricalEvolutionProps } from "./categorical-evolution";
export { ConfigurationEvolution } from "./configuration-evolution";
export type { ConfigurationEvolutionProps } from "./configuration-evolution";
export { FloatEvolution } from "./float-evolution";
export type {
  FloatConstraint,
  FloatEvolutionProps,
  ParameterEvolutionPoint,
} from "./float-evolution";

export type ParameterEvolutionKind =
  | "text"
  | "rule_list"
  | "example_list"
  | "float"
  | "categorical"
  | "configuration";

export interface ParameterEvolutionViewProps {
  path: string;
  type: ParameterEvolutionKind;
  points: ParameterEvolutionPoint[];
  constraint?: FloatConstraint | undefined;
  selectedStep?: number | undefined;
  onSelectStep?: ((step: number) => void) | undefined;
}

export function ParameterEvolutionView({
  path,
  type,
  points,
  constraint,
  selectedStep,
  onSelectStep,
}: ParameterEvolutionViewProps) {
  switch (type) {
    case "float":
      return createElement(FloatEvolution, {
        path,
        points,
        constraint,
        selectedStep,
        onSelectStep,
      });
    case "categorical":
      return createElement(CategoricalEvolution, {
        path,
        points,
        selectedStep,
        onSelectStep,
      });
    case "configuration":
      return createElement(ConfigurationEvolution, {
        path,
        points,
        selectedStep,
        onSelectStep,
      });
    default:
      return createElement(EmptyState, {
        title: "unsupported parameter view",
        description: `${type} evolution is handled by a sibling renderer`,
      });
  }
}
