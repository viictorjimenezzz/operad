import { createElement } from "react";
import { ExampleListEvolution } from "./example-list-evolution";
import { RuleListEvolution } from "./rule-list-evolution";
import { TextEvolution } from "./text-evolution";

import type { ExampleListEvolutionProps } from "./example-list-evolution";
import type { RuleListEvolutionProps } from "./rule-list-evolution";
import type { ParameterEvolutionPoint, TextEvolutionProps } from "./text-evolution";

export { ExampleListEvolution } from "./example-list-evolution";
export type { ExampleListEvolutionProps } from "./example-list-evolution";
export { RuleListEvolution } from "./rule-list-evolution";
export type { RuleListEvolutionProps } from "./rule-list-evolution";
export { TextEvolution } from "./text-evolution";
export type { ParameterEvolutionPoint, TextEvolutionProps } from "./text-evolution";
export { WhyPane } from "./why-pane";
export type {
  ParameterEvolutionPoint as WhyPanePoint,
  TapeStepRef,
  TextualGradient,
  WhyPaneProps,
} from "./why-pane";

export type ParameterEvolutionViewProps = {
  type: "text" | "rule_list" | "example_list" | string;
  points: ParameterEvolutionPoint[];
  selectedStep: number | null;
  onSelectStep: (index: number) => void;
};

export function ParameterEvolutionView({
  type,
  points,
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
  return null;
}
