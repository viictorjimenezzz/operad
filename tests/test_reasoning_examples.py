"""Assert that the seeded class-level ``examples=`` on reasoning leaves
parse as valid ``Example[...]`` instances.

Only ``Critic`` has a concrete ``Candidate -> Score`` contract and thus
ships seeded examples at the class level; the other reasoning leaves are
generic and keep ``examples=()``.
"""

from __future__ import annotations

from operad import Candidate, Critic, Example, Score


def test_critic_examples_are_typed_pairs() -> None:
    assert len(Critic.examples) >= 1
    for ex in Critic.examples:
        assert isinstance(ex, Example)
        assert isinstance(ex.input, Candidate)
        assert isinstance(ex.output, Score)
        assert 0.0 <= ex.output.score <= 1.0


def test_generic_leaves_ship_empty_class_examples() -> None:
    from operad import Actor, Classifier, Evaluator, Extractor, Planner, Reasoner

    for leaf in (Reasoner, Actor, Extractor, Evaluator, Classifier, Planner):
        assert leaf.examples == ()
