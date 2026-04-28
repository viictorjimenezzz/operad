import { createElement } from "react";
import { CategoricalEvolution } from "./categorical-evolution";
import { ConfigurationEvolution } from "./configuration-evolution";
import { ExampleListEvolution } from "./example-list-evolution";
import { type FloatConstraint, FloatEvolution, type FloatEvolutionProps } from "./float-evolution";
import { RuleListEvolution } from "./rule-list-evolution";
import { TextEvolution } from "./text-evolution";

import type { CategoricalEvolutionProps } from "./categorical-evolution";
import type { ConfigurationEvolutionProps } from "./configuration-evolution";
import type { ExampleListEvolutionProps } from "./example-list-evolution";
import type { RuleListEvolutionProps } from "./rule-list-evolution";
import type { ParameterEvolutionPoint, TextEvolutionProps } from "./text-evolution";

export { CategoricalEvolution } from "./categorical-evolution";
export type { CategoricalEvolutionProps } from "./categorical-evolution";
export { ConfigurationEvolution } from "./configuration-evolution";
export type { ConfigurationEvolutionProps } from "./configuration-evolution";
export { ExampleListEvolution } from "./example-list-evolution";
export type { ExampleListEvolutionProps } from "./example-list-evolution";
export { FloatEvolution } from "./float-evolution";
export type { FloatConstraint, FloatEvolutionProps } from "./float-evolution";
export { RuleListEvolution } from "./rule-list-evolution";
export type { RuleListEvolutionProps } from "./rule-list-evolution";
export { TextEvolution } from "./text-evolution";
export type { ParameterEvolutionPoint, TextEvolutionProps } from "./text-evolution";

export type ParameterEvolutionViewProps = {
  path?: string;
  type: "text" | "rule_list" | "example_list" | "float" | "categorical" | "configuration" | string;
  points: ParameterEvolutionPoint[];
  constraint?: FloatConstraint | undefined;
  selectedStep: number | null;
  onSelectStep: (index: number) => void;
};

export function ParameterEvolutionView({
  path,
  type,
  points,
  constraint,
  selectedStep,
  onSelectStep,
}: ParameterEvolutionViewProps) {
  if (type === "text") {
    const props: TextEvolutionProps = { points, selectedStep, onSelectStep };
    return createElement(TextEvolution, props);
  }
  if (type === "rule_list") {
    const props: RuleListEvolutionProps = { points, selectedStep, onSelectStep };
    return createElement(RuleListEvolution, props);
  }
  if (type === "example_list") {
    const props: ExampleListEvolutionProps = { points, selectedStep, onSelectStep };
    return createElement(ExampleListEvolution, props);
  }
  if (type === "float") {
    const props: FloatEvolutionProps = {
      path: path ?? type,
      points,
      constraint,
      selectedStep: selectedStep ?? undefined,
      onSelectStep,
    };
    return createElement(FloatEvolution, props);
  }
  if (type === "categorical") {
    const props: CategoricalEvolutionProps = {
      path: path ?? type,
      points,
      selectedStep: selectedStep ?? undefined,
      onSelectStep,
    };
    return createElement(CategoricalEvolution, props);
  }
  if (type === "configuration") {
    const props: ConfigurationEvolutionProps = {
      path: path ?? type,
      points,
      selectedStep: selectedStep ?? undefined,
      onSelectStep,
    };
    return createElement(ConfigurationEvolution, props);
  }
  return null;
}
