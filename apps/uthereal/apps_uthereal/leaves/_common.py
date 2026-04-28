"""YAML loading and dumping helpers for uthereal leaf agents.

Owner: 1-3-yaml-loader.
"""

from __future__ import annotations

import copy
import logging
import re
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any, TypeVar

from operad import Agent, Configuration, Example
from pydantic import BaseModel, ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import YAMLError

try:
    from apps_uthereal.errors import LoaderError
except ImportError:  # pragma: no cover - replaced by task 1-1 in integration.

    class LoaderError(Exception):
        """Structured loader failure used until the app scaffold is present."""

        def __init__(
            self,
            yaml_path: Path | str,
            reason: str,
            **details: Any,
        ) -> None:
            self.yaml_path = Path(yaml_path)
            self.reason = reason
            self.details = details
            for key, value in details.items():
                setattr(self, key, value)
            super().__init__(f"[{reason}] {self.yaml_path}: {details}")

try:
    from apps_uthereal.tiers import tier_to_config
except ImportError:  # pragma: no cover - replaced by task 1-1 in integration.

    def tier_to_config(
        tier: str,
        *,
        overrides: dict[str, Any] | None = None,
    ) -> Configuration:
        """Return a minimal offline-safe Gemini configuration for tests."""

        models = {
            "fast": "gemini-2.0-flash",
            "thinking_low": "gemini-2.5-flash",
            "thinking_high": "gemini-2.5-pro",
        }
        try:
            model = models[tier]
        except KeyError as exc:
            raise KeyError(tier) from exc

        raw: dict[str, Any] = {
            "backend": "gemini",
            "model": model,
            "api_key": "test",
        }
        if overrides:
            _deep_update(raw, overrides)
        return Configuration.model_validate(raw)


In = TypeVar("In", bound=BaseModel)
Out = TypeVar("Out", bound=BaseModel)

CLOSURE_SEPARATOR = "\n\n## Output\n\n"
TYPE_REGISTRY: dict[str, type[BaseModel]] = {}

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(
    r"<(?P<tag>[A-Za-z_][A-Za-z0-9_.-]*)>(?P<value>.*?)</(?P=tag)>",
    re.DOTALL,
)
_MISSING = object()


@dataclass(frozen=True)
class _YamlMetadata:
    source_bytes: bytes
    source_data: CommentedMap
    initial_hash_content: str
    role: str
    task_body: str
    closure: str
    rules: list[str]
    examples: list[dict[str, Any]]
    tier: str
    templated_examples: bool = False


def load_yaml(
    path: Path,
    leaf_cls: type[Agent[In, Out]],
    *,
    config_overrides: dict[str, Any] | None = None,
    strict_examples: bool = False,
) -> Agent[In, Out]:
    """Construct an instance of `leaf_cls` populated from a uthereal YAML."""

    yaml_path = Path(path)
    source_bytes = yaml_path.read_bytes()
    data, templated_examples = _load_yaml_bytes_resilient(source_bytes, yaml_path)
    prompt = _required_mapping(data, "prompt", yaml_path, field="prompt")
    config_data = _required_mapping(data, "config", yaml_path, field="config")

    tier = config_data.get("llm_tier", _MISSING)
    if tier is _MISSING:
        raise LoaderError(yaml_path, "missing_field", field="config.llm_tier")
    if not isinstance(tier, str):
        raise LoaderError(yaml_path, "unknown_tier", tier=tier)

    config = _config_from_tier(tier, yaml_path, config_overrides=config_overrides)

    role = _string_field(prompt, "role", yaml_path)
    task_body = _string_field(prompt, "task", yaml_path)
    closure = _optional_string_field(prompt, "closure")
    rules = _rules_field(prompt, yaml_path)
    examples = parse_examples(
        _examples_field(prompt, yaml_path),
        leaf_cls,
        strict=strict_examples,
        yaml_path=yaml_path,
    )

    task = task_body
    if closure:
        task = f"{task_body}{CLOSURE_SEPARATOR}{closure}"

    agent = leaf_cls(
        config=config,
        role=role,
        task=task,
        rules=rules,
        examples=examples,
    )
    metadata = _YamlMetadata(
        source_bytes=source_bytes,
        source_data=copy.deepcopy(data),
        initial_hash_content=agent.hash_content,
        role=role,
        task_body=task_body,
        closure=closure,
        rules=rules,
        examples=_dump_examples(examples),
        tier=tier,
        templated_examples=templated_examples,
    )
    object.__setattr__(agent, "_uthereal_yaml_metadata", metadata)
    return agent


def dump_yaml(
    agent: Agent[Any, Any],
    path: Path,
    *,
    source_path: Path | None = None,
) -> None:
    """Write the agent's current parameter state back to YAML."""

    output_path = Path(path)
    metadata = _metadata_for(agent)

    if source_path is not None:
        source_bytes = Path(source_path).read_bytes()
        if (
            metadata is not None
            and agent.hash_content == metadata.initial_hash_content
            and source_bytes == metadata.source_bytes
        ):
            _write_bytes(output_path, source_bytes)
            return
        data = _load_yaml_bytes(source_bytes, Path(source_path))
    elif metadata is not None:
        if agent.hash_content == metadata.initial_hash_content:
            _write_bytes(output_path, metadata.source_bytes)
            return
        data = copy.deepcopy(metadata.source_data)
    else:
        data = _fresh_yaml(agent)

    _update_yaml_data(data, agent, metadata=metadata)
    _write_yaml_data(data, output_path)


def parse_examples(
    raw: list[dict[str, Any]],
    leaf_cls: type[Agent[In, Out]],
    *,
    strict: bool = False,
    yaml_path: Path | None = None,
) -> tuple[Example[In, Out], ...]:
    """Convert YAML example dicts to typed operad Example objects."""

    examples: list[Example[In, Out]] = []
    error_path = yaml_path or Path("<examples>")

    for index, item in enumerate(raw):
        try:
            if not isinstance(item, Mapping):
                raise TypeError("example must be a mapping")
            input_data = _coerce_example_input(item.get("input", {}), leaf_cls.input)
            output_data = item.get("output", {})
            if not isinstance(output_data, Mapping):
                raise TypeError("example output must be a mapping")
            examples.append(
                Example[In, Out](
                    input=leaf_cls.input.model_validate(input_data),
                    output=leaf_cls.output.model_validate(dict(output_data)),
                )
            )
        except (TypeError, ValidationError) as exc:
            if strict:
                raise LoaderError(
                    error_path,
                    "example_validation_failed",
                    index=index,
                    errors=_validation_errors(exc),
                ) from exc
            logger.warning(
                "Dropping YAML example %s after validation failure: %s",
                index,
                exc,
            )
    return tuple(examples)


def split_closure_from_task(task: str) -> tuple[str, str]:
    """Inverse of the closure-to-task merge. Returns (task_body, closure)."""

    if CLOSURE_SEPARATOR not in task:
        return task, ""
    task_body, closure = task.split(CLOSURE_SEPARATOR, 1)
    return task_body, closure


def _yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = 4096
    return yaml


def _load_yaml_bytes(source: bytes, path: Path) -> CommentedMap:
    data, _ = _load_yaml_bytes_resilient(source, path)
    return data


def _load_yaml_bytes_resilient(
    source: bytes,
    path: Path,
) -> tuple[CommentedMap, bool]:
    """Parse YAML, retrying with a stripped ``examples:`` block on Jinja errors.

    uthereal's selfserve YAMLs (e.g. ``retrieval/agents/agent_talker.yaml``)
    embed Jinja2 ``[% for example in examples %]`` blocks that ruamel.yaml
    cannot scan. We can't run them through Jinja at load time (the bridge has
    no rendering context), so we strip the templated ``examples:`` block and
    treat its examples as empty. ``_YamlMetadata`` records the original bytes
    so `dump_yaml` can replay them when no parameter changed.
    """

    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LoaderError(path, "yaml_parse_failed", parser_error=str(exc)) from exc

    try:
        data = _yaml().load(text)
        return _validate_root(data, path), False
    except YAMLError as first_exc:
        if not _has_template_markers(text):
            raise LoaderError(
                path,
                "yaml_parse_failed",
                parser_error=str(first_exc),
            ) from first_exc
        stripped = _strip_templated_examples(text)
        try:
            data = _yaml().load(stripped)
        except YAMLError as second_exc:
            raise LoaderError(
                path,
                "yaml_parse_failed",
                parser_error=str(second_exc),
            ) from second_exc
        return _validate_root(data, path), True


def _validate_root(data: Any, path: Path) -> CommentedMap:
    if data is None:
        return CommentedMap()
    if not isinstance(data, CommentedMap):
        raise LoaderError(
            path,
            "yaml_parse_failed",
            parser_error="root is not a mapping",
        )
    return data


_TEMPLATE_MARKER_RE = re.compile(r"\[%|\{%|\[\[|\{\{")


def _has_template_markers(text: str) -> bool:
    return bool(_TEMPLATE_MARKER_RE.search(text))


def _strip_templated_examples(text: str) -> str:
    """Replace any ``examples:`` block containing Jinja markers with ``examples: []``.

    The block is identified by its leading indent: every subsequent line that
    is blank or indented more than the ``examples:`` key is part of the block.
    """

    lines = text.splitlines(keepends=True)
    output: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r"^(?P<indent>\s*)examples:\s*$", line)
        if match is None:
            output.append(line)
            index += 1
            continue

        indent = match.group("indent")
        block_start = index + 1
        block_end = block_start
        while block_end < len(lines):
            candidate = lines[block_end]
            if candidate.strip() == "":
                block_end += 1
                continue
            stripped_indent = len(candidate) - len(candidate.lstrip(" "))
            if stripped_indent <= len(indent):
                break
            block_end += 1

        block_text = "".join(lines[block_start:block_end])
        if _has_template_markers(block_text):
            output.append(f"{indent}examples: []\n")
            index = block_end
            continue

        output.append(line)
        index += 1
    return "".join(output)


def _required_mapping(
    data: Mapping[str, Any],
    key: str,
    path: Path,
    *,
    field: str,
) -> Mapping[str, Any]:
    value = data.get(key, _MISSING)
    if value is _MISSING or not isinstance(value, Mapping):
        raise LoaderError(path, "missing_field", field=field)
    return value


def _string_field(data: Mapping[str, Any], key: str, path: Path) -> str:
    value = data.get(key, _MISSING)
    if value is _MISSING:
        raise LoaderError(path, "missing_field", field=f"prompt.{key}")
    if value is None:
        return ""
    return str(value)


def _optional_string_field(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key, "")
    if value is None:
        return ""
    return str(value)


def _rules_field(data: Mapping[str, Any], path: Path) -> list[str]:
    value = data.get("rules", [])
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise LoaderError(path, "missing_field", field="prompt.rules")
    return [str(item) for item in value]


def _examples_field(data: Mapping[str, Any], path: Path) -> list[dict[str, Any]]:
    value = data.get("examples", [])
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise LoaderError(path, "missing_field", field="prompt.examples")
    return list(value)


def _config_from_tier(
    tier: str,
    path: Path,
    *,
    config_overrides: dict[str, Any] | None,
) -> Configuration:
    try:
        return tier_to_config(tier, overrides=config_overrides)
    except LoaderError:
        raise
    except (KeyError, ValueError) as exc:
        raise LoaderError(path, "unknown_tier", tier=tier) from exc


def _coerce_example_input(
    raw_input: Any,
    input_cls: type[BaseModel],
) -> dict[str, Any]:
    if isinstance(raw_input, Mapping):
        return dict(raw_input)
    if isinstance(raw_input, str):
        fields = input_cls.model_fields
        string_fields = [
            name for name, field in fields.items() if field.annotation is str
        ]
        if len(fields) == 1 and len(string_fields) == 1:
            return {string_fields[0]: raw_input}
        return _parse_tagged_input(raw_input, input_cls)
    raise TypeError("example input must be a string or mapping")


def _parse_tagged_input(text: str, input_cls: type[BaseModel]) -> dict[str, str]:
    fields = input_cls.model_fields
    parsed: dict[str, str] = {}
    for match in _TAG_RE.finditer(text):
        tag = match.group("tag")
        if tag in fields:
            parsed[tag] = match.group("value")
    return parsed


def _validation_errors(exc: TypeError | ValidationError) -> Any:
    if isinstance(exc, ValidationError):
        return exc.errors()
    return str(exc)


def _metadata_for(agent: Agent[Any, Any]) -> _YamlMetadata | None:
    metadata = getattr(agent, "_uthereal_yaml_metadata", None)
    if isinstance(metadata, _YamlMetadata):
        return metadata
    return None


def _fresh_yaml(agent: Agent[Any, Any]) -> CommentedMap:
    data = CommentedMap()
    data["agent_name"] = agent.name or type(agent).__name__
    data["config"] = CommentedMap({"llm_tier": "fast"})
    data["prompt"] = CommentedMap()
    return data


def _update_yaml_data(
    data: MutableMapping[str, Any],
    agent: Agent[Any, Any],
    *,
    metadata: _YamlMetadata | None,
) -> None:
    prompt = _ensure_map(data, "prompt")
    config = _ensure_map(data, "config")
    task_body, closure = split_closure_from_task(str(agent.task))

    if prompt.get("role") != agent.role:
        prompt["role"] = agent.role
    if prompt.get("task") != task_body:
        prompt["task"] = task_body
    if prompt.get("closure", "") != closure:
        prompt["closure"] = closure

    rules = [str(rule) for rule in agent.rules]
    raw_rules = prompt.get("rules", [])
    if not isinstance(raw_rules, Sequence) or list(raw_rules) != rules:
        prompt["rules"] = CommentedSeq(rules)

    examples = _dump_examples(agent.examples)
    if metadata is None or examples != metadata.examples:
        prompt["examples"] = _examples_to_yaml(examples)

    if "llm_tier" not in config:
        config["llm_tier"] = metadata.tier if metadata is not None else "fast"


def _ensure_map(data: MutableMapping[str, Any], key: str) -> MutableMapping[str, Any]:
    value = data.get(key)
    if isinstance(value, MutableMapping):
        return value
    replacement: MutableMapping[str, Any] = CommentedMap()
    data[key] = replacement
    return replacement


def _dump_examples(examples: Sequence[Example[Any, Any]]) -> list[dict[str, Any]]:
    dumped: list[dict[str, Any]] = []
    for example in examples:
        dumped.append(
            {
                "input": example.input.model_dump(mode="json"),
                "output": example.output.model_dump(mode="json"),
            }
        )
    return dumped


def _examples_to_yaml(examples: list[dict[str, Any]]) -> CommentedSeq:
    yaml_examples = CommentedSeq()
    for example in examples:
        item = CommentedMap()
        item["input"] = example["input"]
        item["output"] = example["output"]
        yaml_examples.append(item)
    return yaml_examples


def _write_yaml_data(data: Mapping[str, Any], path: Path) -> None:
    stream = StringIO()
    _yaml().dump(data, stream)
    _write_bytes(path, stream.getvalue().encode("utf-8"))


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _deep_update(target: dict[str, Any], overrides: Mapping[str, Any]) -> None:
    for key, value in overrides.items():
        if (
            isinstance(value, Mapping)
            and isinstance(target.get(key), dict)
        ):
            _deep_update(target[key], value)
        else:
            target[key] = value


__all__ = [
    "CLOSURE_SEPARATOR",
    "TYPE_REGISTRY",
    "dump_yaml",
    "load_yaml",
    "parse_examples",
    "split_closure_from_task",
]
