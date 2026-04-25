"""Offline tests for `Agent.parameters()` / `named_parameters()` and the
`mark_trainable` / `freeze_parameters` surface.
"""

from __future__ import annotations

import pytest

from operad import Configuration
from operad.agents.pipeline import Pipeline
from operad.core.config import Sampling
from operad.optim import (
    CategoricalParameter,
    ConfigurationConstraint,
    ConfigurationParameter,
    ExampleListParameter,
    FloatParameter,
    Parameter,
    RuleListParameter,
    TextParameter,
)

from tests._helpers.fake_leaf import A, B, FakeLeaf


def _leaf(cfg: Configuration, **kw) -> FakeLeaf:
    return FakeLeaf(config=cfg, input=A, output=B, **kw)


def test_leaf_default_parameter_set_without_top_p(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    names = {path for path, _ in leaf.named_parameters(recurse=False)}
    assert names == {
        "role",
        "task",
        "style",
        "rules",
        "examples",
        "config.sampling.temperature",
        "config.model",
        "config.backend",
        "config.io.renderer",
    }


def test_leaf_top_p_emitted_when_set() -> None:
    cfg = Configuration(
        backend="anthropic",
        model="claude-test",
        api_key="sk-test",
        sampling=Sampling(temperature=0.0, top_p=0.9),
    )
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    names = {path for path, _ in leaf.named_parameters(recurse=False)}
    assert "config.sampling.top_p" in names


def test_leaf_top_p_skipped_when_none(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    assert cfg.sampling.top_p is None
    names = {path for path, _ in leaf.named_parameters(recurse=False)}
    assert "config.sampling.top_p" not in names


def test_parameter_subclasses_match_expected_types(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    by_path = dict(leaf.named_parameters(recurse=False))
    assert isinstance(by_path["role"], TextParameter)
    assert isinstance(by_path["task"], TextParameter)
    assert isinstance(by_path["style"], TextParameter)
    assert isinstance(by_path["rules"], RuleListParameter)
    assert isinstance(by_path["examples"], ExampleListParameter)
    assert isinstance(by_path["config.sampling.temperature"], FloatParameter)
    assert isinstance(by_path["config.model"], CategoricalParameter)
    assert isinstance(by_path["config.backend"], CategoricalParameter)
    assert isinstance(by_path["config.io.renderer"], CategoricalParameter)


def test_parameters_recurse_false_excludes_children(cfg: Configuration) -> None:
    a, b = _leaf(cfg), _leaf(cfg)
    pipe = Pipeline(a, b, input=A, output=B)
    local = list(pipe.named_parameters(recurse=False))
    # Pipeline has config=None → only role/task/style/rules/examples.
    assert {path for path, _ in local} == {
        "role", "task", "style", "rules", "examples",
    }


def test_named_parameters_recurse_prefixes_child_names(cfg: Configuration) -> None:
    a, b = _leaf(cfg), _leaf(cfg)
    pipe = Pipeline(a, b, input=A, output=B)
    names = [p for p, _ in pipe.named_parameters(recurse=True)]
    assert "role" in names  # pipeline's own role
    assert "stage_0.role" in names
    assert "stage_1.role" in names
    assert "stage_0.config.sampling.temperature" in names
    assert "stage_1.config.model" in names


def test_composite_has_no_sampling_params(cfg: Configuration) -> None:
    a, b = _leaf(cfg), _leaf(cfg)
    pipe = Pipeline(a, b, input=A, output=B)
    local = {path for path, _ in pipe.named_parameters(recurse=False)}
    for forbidden in (
        "config.sampling.temperature",
        "config.sampling.top_p",
        "config.model",
        "config.backend",
        "config.io.renderer",
    ):
        assert forbidden not in local


def test_element_wise_expands_rules(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    leaf.rules = ["r0", "r1", "r2"]
    names = [p for p, _ in leaf.named_parameters(recurse=False, element_wise=True)]
    assert "rules" not in names
    assert "rules[0]" in names
    assert "rules[1]" in names
    assert "rules[2]" in names


def test_element_wise_rule_param_is_text(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    leaf.rules = ["only-rule"]
    params = {p: param for p, param in leaf.named_parameters(recurse=False, element_wise=True)}
    rp = params["rules[0]"]
    assert isinstance(rp, TextParameter)
    assert rp.kind == "rule_i"
    assert rp.value == "only-rule"


def test_element_wise_expands_examples(cfg: Configuration) -> None:
    from operad.core.example import Example
    leaf = _leaf(cfg)
    leaf.examples = [
        Example(input=A(text="i0"), output=B(value=0)),
        Example(input=A(text="i1"), output=B(value=1)),
    ]
    names = [p for p, _ in leaf.named_parameters(recurse=False, element_wise=True)]
    assert "examples" not in names
    assert "examples[0]" in names
    assert "examples[1]" in names


def test_element_wise_example_uses_base_parameter(cfg: Configuration) -> None:
    from operad.core.example import Example
    leaf = _leaf(cfg)
    leaf.examples = [Example(input=A(text="x"), output=B(value=1))]
    by_path = dict(leaf.named_parameters(recurse=False, element_wise=True))
    ep = by_path["examples[0]"]
    assert type(ep) is Parameter  # base, not a subclass
    assert ep.kind == "example_i"


def test_default_requires_grad_true(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    for p in leaf.parameters(recurse=False):
        assert p.requires_grad is True


def test_mark_trainable_is_noop_when_already_true(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    leaf.mark_trainable(role=True)
    by_path = dict(leaf.named_parameters(recurse=False))
    assert by_path["role"].requires_grad is True
    # task was never set, so stays default-true
    assert by_path["task"].requires_grad is True


def test_freeze_then_mark_roundtrip(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    leaf.freeze_parameters(role=True)
    assert dict(leaf.named_parameters(recurse=False))["role"].requires_grad is False
    leaf.mark_trainable(role=True)
    assert dict(leaf.named_parameters(recurse=False))["role"].requires_grad is True


def test_freeze_does_not_affect_other_fields(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    leaf.freeze_parameters(role=True)
    by_path = dict(leaf.named_parameters(recurse=False))
    assert by_path["role"].requires_grad is False
    assert by_path["task"].requires_grad is True
    assert by_path["rules"].requires_grad is True


def test_mark_trainable_recurse_broadcasts(cfg: Configuration) -> None:
    a, b = _leaf(cfg), _leaf(cfg)
    pipe = Pipeline(a, b, input=A, output=B)
    pipe.freeze_parameters(role=True, recurse=True)
    assert dict(a.named_parameters(recurse=False))["role"].requires_grad is False
    assert dict(b.named_parameters(recurse=False))["role"].requires_grad is False
    assert dict(pipe.named_parameters(recurse=False))["role"].requires_grad is False


def test_mark_trainable_recurse_false_leaves_children_alone(cfg: Configuration) -> None:
    a, b = _leaf(cfg), _leaf(cfg)
    pipe = Pipeline(a, b, input=A, output=B)
    pipe.freeze_parameters(role=True, recurse=False)
    assert dict(pipe.named_parameters(recurse=False))["role"].requires_grad is False
    assert dict(a.named_parameters(recurse=False))["role"].requires_grad is True
    assert dict(b.named_parameters(recurse=False))["role"].requires_grad is True


def test_per_path_child_only(cfg: Configuration) -> None:
    a, b = _leaf(cfg), _leaf(cfg)
    pipe = Pipeline(a, b, input=A, output=B)
    pipe.freeze_parameters(**{"stage_0.role": True})
    assert dict(a.named_parameters(recurse=False))["role"].requires_grad is False
    assert dict(b.named_parameters(recurse=False))["role"].requires_grad is True
    assert dict(pipe.named_parameters(recurse=False))["role"].requires_grad is True


def test_per_path_combines_with_broadcast(cfg: Configuration) -> None:
    """Per-path selections are additive to broadcast when they target the
    same fields — both write the method's ``value``."""
    a, b = _leaf(cfg), _leaf(cfg)
    pipe = Pipeline(a, b, input=A, output=B)
    pipe.freeze_parameters(
        role=True, recurse=True, **{"stage_0.task": True}
    )
    assert dict(a.named_parameters(recurse=False))["role"].requires_grad is False
    assert dict(a.named_parameters(recurse=False))["task"].requires_grad is False
    assert dict(b.named_parameters(recurse=False))["role"].requires_grad is False
    assert dict(b.named_parameters(recurse=False))["task"].requires_grad is True


def test_per_path_unknown_child_raises(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    with pytest.raises(KeyError):
        leaf.mark_trainable(**{"nonexistent.role": True})


def test_per_path_unknown_field_raises(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    with pytest.raises(KeyError):
        leaf.mark_trainable(**{"bogus": True})


def test_sampling_kwarg_without_config_raises_at_root(cfg: Configuration) -> None:
    a, b = _leaf(cfg), _leaf(cfg)
    pipe = Pipeline(a, b, input=A, output=B)
    with pytest.raises(KeyError):
        pipe.mark_trainable(temperature=True, recurse=False)


def test_sampling_broadcast_skips_composite_silently(cfg: Configuration) -> None:
    a, b = _leaf(cfg), _leaf(cfg)
    pipe = Pipeline(a, b, input=A, output=B)
    # Pipeline has no config, but broadcast should still reach children.
    # We have to call from a leaf-level starting point because the strict
    # root check runs on whoever receives the explicit call.
    a.mark_trainable(temperature=False, recurse=False)
    # Now broadcast freeze from the pipeline via recurse=True — root has no
    # config, so strict check must fire. That's covered above; here we verify
    # the lenient recursion path.
    # Call the private broadcast directly to exercise the non-strict branch.
    pipe._set_requires_grad(False, temperature=True, recurse=True, _strict=False)
    assert dict(a.named_parameters(recurse=False))["config.sampling.temperature"].requires_grad is False
    assert dict(b.named_parameters(recurse=False))["config.sampling.temperature"].requires_grad is False


def test_trainable_parameters_filters(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    leaf.freeze_parameters(role=True)
    trainable_paths = {
        p.path for p in leaf.trainable_parameters()
    }
    assert "role" not in trainable_paths
    assert "task" in trainable_paths


def test_trainable_parameters_recurses(cfg: Configuration) -> None:
    a, b = _leaf(cfg), _leaf(cfg)
    pipe = Pipeline(a, b, input=A, output=B)
    pipe.freeze_parameters(role=True, recurse=True)
    trainable = list(pipe.trainable_parameters())
    role_params = [p for p in trainable if p.kind == "role"]
    assert role_params == []  # all roles frozen


def test_clone_resets_overrides(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    leaf.freeze_parameters(role=True)
    cloned = leaf.clone()
    assert cloned._requires_grad_overrides == {}
    assert dict(cloned.named_parameters(recurse=False))["role"].requires_grad is True


def test_clone_composite_resets_overrides(cfg: Configuration) -> None:
    a, b = _leaf(cfg), _leaf(cfg)
    pipe = Pipeline(a, b, input=A, output=B)
    pipe.freeze_parameters(role=True, recurse=True)
    cloned = pipe.clone()
    assert cloned._requires_grad_overrides == {}
    # Children were cloned too — their overrides should also be empty.
    for _, child in cloned._children.items():
        assert child._requires_grad_overrides == {}


def test_parameters_read_live_values(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    leaf.role = "first"
    p1 = dict(leaf.named_parameters(recurse=False))["role"]
    assert p1.value == "first"
    leaf.role = "second"
    p2 = dict(leaf.named_parameters(recurse=False))["role"]
    assert p2.value == "second"


def test_unfreeze_is_alias(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    leaf.freeze_parameters(role=True)
    leaf.unfreeze_parameters(role=True)
    assert dict(leaf.named_parameters(recurse=False))["role"].requires_grad is True


# ---------------------------------------------------------------------------
# config=True yields ConfigurationParameter and silently overrides leaf flags
# ---------------------------------------------------------------------------


def _config_constraint() -> ConfigurationConstraint:
    return ConfigurationConstraint(
        allowed_backends=["llamacpp", "ollama"],
        allowed_models={"llamacpp": ["test", "m2"], "ollama": ["o1"]},
    )


def test_mark_trainable_config_yields_configuration_parameter(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    leaf.set_configuration_constraint(_config_constraint())
    leaf.mark_trainable(config=True)

    by_path = dict(leaf.named_parameters(recurse=False))
    assert "config" in by_path
    assert isinstance(by_path["config"], ConfigurationParameter)
    assert by_path["config"].kind == "configuration"
    assert isinstance(by_path["config"].constraint, ConfigurationConstraint)


def test_mark_trainable_config_silently_overrides_leaf_flags(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    leaf.mark_trainable(config=True, temperature=True)

    by_path = dict(leaf.named_parameters(recurse=False))
    # ConfigurationParameter is yielded.
    assert "config" in by_path
    assert isinstance(by_path["config"], ConfigurationParameter)
    # Leaf-level config params are NOT yielded.
    assert "config.sampling.temperature" not in by_path
    assert "config.model" not in by_path
    assert "config.backend" not in by_path
    assert "config.io.renderer" not in by_path


def test_freeze_config_drops_configuration_parameter(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    leaf.mark_trainable(config=True)
    assert "config" in dict(leaf.named_parameters(recurse=False))

    leaf.freeze_parameters(config=True)
    by_path = dict(leaf.named_parameters(recurse=False))
    # config flag is now False → leaf-level params return.
    assert "config" not in by_path
    assert "config.sampling.temperature" in by_path
    assert "config.model" in by_path


def test_mark_trainable_config_without_config_raises_at_root(cfg: Configuration) -> None:
    a, b = _leaf(cfg), _leaf(cfg)
    pipe = Pipeline(a, b, input=A, output=B)
    with pytest.raises(KeyError):
        pipe.mark_trainable(config=True, recurse=False)


def test_mark_trainable_config_broadcast_skips_composite_silently(cfg: Configuration) -> None:
    a, b = _leaf(cfg), _leaf(cfg)
    pipe = Pipeline(a, b, input=A, output=B)
    # Mirrors `test_sampling_broadcast_skips_composite_silently`: the
    # composite root has no config, so the strict path at the root would
    # raise. The lenient broadcast (`_strict=False`) reaches children
    # without choking on the configless root.
    pipe._set_requires_grad(True, config=True, recurse=True, _strict=False)
    pipe_paths = {p for p, _ in pipe.named_parameters(recurse=False)}
    assert "config" not in pipe_paths
    assert "config" in dict(a.named_parameters(recurse=False))
    assert "config" in dict(b.named_parameters(recurse=False))
