from enum import StrEnum
from pathlib import Path
import re
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    field_validator,
    model_validator,
)
import yaml


_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?")
_SEMANTIC_VERSION_PART = r"(?:0|[1-9][0-9]*)"
_SEMANTIC_VERSION_PATTERN = re.compile(
    rf"{_SEMANTIC_VERSION_PART}\.{_SEMANTIC_VERSION_PART}\.{_SEMANTIC_VERSION_PART}"
)
_URI_SCHEME_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
_MAX_DIAGNOSTICS = 100
_MAX_DIAGNOSTIC_LENGTH = 512


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise SuiteDefinitionError(["yaml: duplicate mapping key"])
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _validate_identifier(value: str) -> str:
    if not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError("must be a non-empty identifier")
    return value


def _validate_semantic_version(value: str) -> str:
    if not _SEMANTIC_VERSION_PATTERN.fullmatch(value):
        raise ValueError("must use MAJOR.MINOR.PATCH form")
    return value


class PrimaryCapability(StrEnum):
    INSTRUCTION_FOLLOWING = "instruction-following"
    STRUCTURED_OUTPUT = "structured-output"
    HONESTY_UNCERTAINTY = "honesty-uncertainty"
    SUMMARIZATION = "summarization"
    EXTRACTION = "extraction"
    PLANNING = "planning"
    TECHNICAL_EXPLANATION = "technical-explanation"
    CODING = "coding"
    CODE_REVIEW = "code-review"
    TROUBLESHOOTING = "troubleshooting"
    SAFETY_REFUSAL = "safety-refusal"
    TOOL_PREPARATION = "tool-preparation"
    BOUNDED_CONTEXT = "bounded-context"


class SecondaryStressor(StrEnum):
    NOISE = "noise"
    LATE_CONSTRAINTS = "late-constraints"
    ADVERSARIAL_INSTRUCTIONS = "adversarial-instructions"
    STRICT_LENGTH = "strict-length"


class ScoringRole(StrEnum):
    DETERMINISTIC = "deterministic"
    MANUAL = "manual"
    HYBRID = "hybrid"


class _LogicalReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    version: str

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _validate_identifier(value)

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        return _validate_semantic_version(value)


class DeterministicCheckReference(_LogicalReference):
    pass


class ManualRubricReference(_LogicalReference):
    pass


class FixtureReference(_LogicalReference):
    path: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if not value:
            raise ValueError("must be a non-empty relative POSIX path")
        if "\\" in value:
            raise ValueError("must use POSIX separators")
        if value.startswith("/"):
            raise ValueError("must be relative")
        if _URI_SCHEME_PATTERN.match(value):
            raise ValueError("must not contain a URI scheme or drive prefix")
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("must not contain control characters")

        segments = value.split("/")
        if any(segment == "" for segment in segments):
            raise ValueError("must not contain empty path segments")
        if any(segment == "." for segment in segments):
            raise ValueError("must not contain '.' path segments")
        if any(segment == ".." for segment in segments):
            raise ValueError("must not contain '..' path segments")
        return value


class ScoringDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: ScoringRole
    deterministic_check: DeterministicCheckReference | None = None
    manual_rubric: ManualRubricReference | None = None
    hybrid_rule: Literal["side-by-side"] | None = None

    @model_validator(mode="after")
    def validate_role_references(self) -> "ScoringDefinition":
        if self.role is ScoringRole.DETERMINISTIC:
            if self.deterministic_check is None:
                raise ValueError("deterministic role requires deterministic_check")
            if self.manual_rubric is not None or self.hybrid_rule is not None:
                raise ValueError(
                    "deterministic role forbids manual_rubric and hybrid_rule"
                )
        elif self.role is ScoringRole.MANUAL:
            if self.manual_rubric is None:
                raise ValueError("manual role requires manual_rubric")
            if self.deterministic_check is not None or self.hybrid_rule is not None:
                raise ValueError(
                    "manual role forbids deterministic_check and hybrid_rule"
                )
        else:
            if self.deterministic_check is None or self.manual_rubric is None:
                raise ValueError(
                    "hybrid role requires deterministic_check and manual_rubric"
                )
            if self.hybrid_rule != "side-by-side":
                raise ValueError("hybrid role requires hybrid_rule 'side-by-side'")
        return self


class ProfileDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_ids: list[str]

    @field_validator("prompt_ids")
    @classmethod
    def validate_prompt_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("must be a non-empty list")
        for prompt_id in value:
            if not prompt_id:
                raise ValueError("members must be non-empty prompt IDs")
        return value


class PromptDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    file: str
    primary_capability: PrimaryCapability | None = None
    secondary_stressors: list[SecondaryStressor] | None = None
    scoring: ScoringDefinition | None = None
    fixtures: list[FixtureReference] | None = None

    @field_validator("id", "file")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("must be non-empty")
        return value

    @model_validator(mode="after")
    def validate_unique_metadata(self) -> "PromptDefinition":
        if self.secondary_stressors is not None:
            stressors = [stressor.value for stressor in self.secondary_stressors]
            if len(stressors) != len(set(stressors)):
                raise ValueError("secondary_stressors must not contain duplicates")
        if self.fixtures is not None:
            references = [(fixture.id, fixture.version) for fixture in self.fixtures]
            if len(references) != len(set(references)):
                raise ValueError("fixture (id, version) references must be unique")
        return self


class SuiteManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: Literal["llmgauge.suite.v0"]
    suite_id: str
    suite_version: str
    title: str | None = None
    prompts: list[PromptDefinition]
    profiles: dict[str, ProfileDefinition] | None = None
    default_profile: str | None = None

    @field_validator("suite_id", "suite_version")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("must be non-empty")
        return value

    @field_validator("title")
    @classmethod
    def validate_optional_title(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("must be non-empty")
        return value

    @field_validator("default_profile")
    @classmethod
    def validate_default_profile(cls, value: str | None) -> str | None:
        if value is not None:
            _validate_identifier(value)
        return value

    @model_validator(mode="after")
    def validate_manifest_contract(self) -> "SuiteManifest":
        prompt_positions: dict[str, int] = {}
        for index, prompt in enumerate(self.prompts):
            if prompt.id in prompt_positions:
                raise ValueError("prompt IDs must be unique")
            prompt_positions[prompt.id] = index

        profile_aware = self.profiles is not None or self.default_profile is not None
        if profile_aware and self.title is None:
            raise ValueError("profile-aware manifest requires title")
        if not profile_aware:
            for prompt in self.prompts:
                metadata = (
                    prompt.primary_capability,
                    prompt.secondary_stressors,
                    prompt.scoring,
                    prompt.fixtures,
                )
                if any(value is not None for value in metadata):
                    raise ValueError(
                        "legacy prompts must not declare profile-aware metadata"
                    )
            return self

        if self.profiles is None or self.default_profile is None:
            raise ValueError("profiles and default_profile must appear together")
        if not self.profiles:
            raise ValueError("profiles must be a non-empty mapping")
        if self.default_profile not in self.profiles:
            raise ValueError("default_profile must name a declared profile")

        for profile_name, profile in self.profiles.items():
            _validate_identifier(profile_name)
            seen_members: set[str] = set()
            previous_position = -1
            for prompt_id in profile.prompt_ids:
                if prompt_id not in prompt_positions:
                    raise ValueError("profile references an unknown prompt ID")
                if prompt_id in seen_members:
                    raise ValueError(
                        "profile members must not contain duplicate prompt IDs"
                    )
                position = prompt_positions[prompt_id]
                if position <= previous_position:
                    raise ValueError(
                        "profile members must preserve canonical prompt order"
                    )
                seen_members.add(prompt_id)
                previous_position = position

        for prompt in self.prompts:
            if prompt.primary_capability is None:
                raise ValueError("profile-aware prompt requires primary_capability")
            if prompt.secondary_stressors is None:
                raise ValueError("profile-aware prompt requires secondary_stressors")
            if prompt.scoring is None:
                raise ValueError("profile-aware prompt requires scoring")
            if prompt.fixtures is None:
                raise ValueError("profile-aware prompt requires fixtures")
        return self


_DIAGNOSTICS_TRUNCATED = "diagnostics-truncated: additional errors omitted"


def _bound_diagnostic(value: str) -> str:
    return value[:_MAX_DIAGNOSTIC_LENGTH]


def _limit_diagnostics(diagnostics: list[str]) -> list[str]:
    if len(diagnostics) > _MAX_DIAGNOSTICS:
        diagnostics = diagnostics[: _MAX_DIAGNOSTICS - 1] + [_DIAGNOSTICS_TRUNCATED]
    return [_bound_diagnostic(diagnostic) for diagnostic in diagnostics]


class SuiteDefinitionError(ValueError):
    def __init__(self, diagnostics: list[str]) -> None:
        bounded_diagnostics = _limit_diagnostics(diagnostics)
        self.diagnostics = tuple(bounded_diagnostics)
        rendered = "Invalid suite definition: " + "; ".join(bounded_diagnostics)
        super().__init__(_bound_diagnostic(rendered))


def _format_validation_diagnostics(exc: ValidationError) -> list[str]:
    errors = exc.errors(include_url=False, include_context=False, include_input=False)
    truncated = len(errors) > _MAX_DIAGNOSTICS
    visible_errors = errors[: _MAX_DIAGNOSTICS - 1] if truncated else errors
    diagnostics: list[str] = []
    for error in visible_errors:
        location = ".".join(str(part) for part in error["loc"]) or "<root>"
        message = str(error["msg"])
        diagnostics.append(_bound_diagnostic(f"{location}: {message}"))
    if truncated:
        diagnostics.append(_DIAGNOSTICS_TRUNCATED)
    return diagnostics


def load_suite(suite_dir: Path) -> dict[str, Any]:
    suite_file = suite_dir / "suite.yaml"
    if not suite_file.exists():
        raise FileNotFoundError(f"Missing suite file: {suite_file}")

    try:
        with suite_file.open("r", encoding="utf-8") as handle:
            data = yaml.load(handle, Loader=_UniqueKeyLoader)
    except SuiteDefinitionError:
        raise
    except yaml.YAMLError:
        raise SuiteDefinitionError(["yaml: malformed YAML"]) from None

    if not isinstance(data, dict):
        raise SuiteDefinitionError(["yaml: root must be a mapping"])

    try:
        SuiteManifest.model_validate(data)
    except ValidationError as exc:
        raise SuiteDefinitionError(_format_validation_diagnostics(exc)) from None
    return data


def validate_suite(suite_dir: Path) -> list[str]:
    try:
        suite = load_suite(suite_dir)
    except SuiteDefinitionError as exc:
        return list(exc.diagnostics)
    except Exception as exc:
        return [str(exc)]

    errors: list[str] = []
    if "title" not in suite:
        errors.append("Missing required field: title")
    for prompt in suite["prompts"]:
        prompt_file = prompt["file"]
        path = suite_dir / prompt_file
        if not path.exists():
            errors.append(f"Prompt file does not exist: {path}")
    return errors
