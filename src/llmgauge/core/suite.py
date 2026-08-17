from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import re
from types import MappingProxyType
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


class TaskFamily(StrEnum):
    SUPPLIED_CODE_DEBUGGING = "supplied-code-debugging"
    MINIMAL_PATCH_GENERATION = "minimal-patch-generation"
    TEST_DESIGN_AND_CREATION = "test-design-and-creation"
    FAILURE_OUTPUT_DIAGNOSIS = "failure-output-diagnosis"
    SAFE_COMMAND_RECOMMENDATION = "safe-command-recommendation"
    DEPENDENCY_API_UNCERTAINTY = "dependency-api-uncertainty"
    SCOPED_CHANGE_PLANNING = "scoped-change-planning"
    STRUCTURED_CODING_RESPONSE = "structured-coding-response"
    CONSTRAINED_REWRITE = "constrained-rewrite"
    TYPED_RECORD_SERIALIZATION = "typed-record-serialization"
    EVIDENCE_SUFFICIENCY_JUDGMENT = "evidence-sufficiency-judgment"
    GROUNDED_DECISION_SUMMARY = "grounded-decision-summary"
    GROUNDED_FIELD_EXTRACTION = "grounded-field-extraction"
    DEPENDENCY_AWARE_PLANNING = "dependency-aware-planning"
    AUDIENCE_CALIBRATED_MECHANISM_EXPLANATION = (
        "audience-calibrated-mechanism-explanation"
    )
    PURE_FUNCTION_IMPLEMENTATION = "pure-function-implementation"
    DEFECT_PRIORITIZATION = "defect-prioritization"
    DISCRIMINATING_DIAGNOSIS = "discriminating-diagnosis"
    CALIBRATED_RISK_BOUNDARY = "calibrated-risk-boundary"
    DECLARED_TOOL_REQUEST_PREPARATION = "declared-tool-request-preparation"
    BOUNDED_SOURCE_RECONCILIATION = "bounded-source-reconciliation"


class InteractionMode(StrEnum):
    STATIC_SINGLE_TURN = "static-single-turn"


class ExecutionMode(StrEnum):
    NONE = "none"


class ResponseFormCategory(StrEnum):
    CODE_ONLY = "code-only"
    EXPLANATION_PLUS_CODE = "explanation-plus-code"
    EXPLANATION_ONLY = "explanation-only"
    BOUNDED_PATCH = "bounded-patch"
    CLOSED_JSON_RECORD = "closed-json-record"


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
    DEBUGGING = "debugging"
    MINIMAL_PATCH_GENERATION = "minimal-patch-generation"
    TEST_CREATION = "test-creation"
    FAILURE_DIAGNOSIS = "failure-diagnosis"
    SHELL_COMMAND_SAFETY = "shell-command-safety"
    DEPENDENCY_API_UNCERTAINTY = "dependency-api-uncertainty"
    SCOPE_CONTROL = "scope-control"
    STRUCTURED_OUTPUT_COMPLIANCE = "structured-output-compliance"


class SecondaryStressor(StrEnum):
    NOISE = "noise"
    LATE_CONSTRAINTS = "late-constraints"
    ADVERSARIAL_INSTRUCTIONS = "adversarial-instructions"
    STRICT_LENGTH = "strict-length"
    SCOPE_CONTROL = "scope-control"
    DEPENDENCY_API_UNCERTAINTY = "dependency-api-uncertainty"
    STRUCTURED_OUTPUT_COMPLIANCE = "structured-output-compliance"
    DEBUGGING = "debugging"
    MINIMAL_PATCH_GENERATION = "minimal-patch-generation"
    INSTRUCTION_COMPLIANCE = "instruction-compliance"


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


class ResponseFormDefinitionReference(_LogicalReference):
    pass


class HybridCompositionReference(_LogicalReference):
    pass


class ResponseFormDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ResponseFormCategory
    definition: ResponseFormDefinitionReference


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
    hybrid_composition: HybridCompositionReference | None = None

    @model_validator(mode="after")
    def validate_role_references(self) -> "ScoringDefinition":
        if self.role is ScoringRole.DETERMINISTIC:
            if self.deterministic_check is None:
                raise ValueError("deterministic role requires deterministic_check")
            if self.manual_rubric is not None or self.hybrid_rule is not None:
                raise ValueError(
                    "deterministic role forbids manual_rubric and hybrid_rule"
                )
            if self.hybrid_composition is not None:
                raise ValueError("deterministic role forbids hybrid_composition")
        elif self.role is ScoringRole.MANUAL:
            if self.manual_rubric is None:
                raise ValueError("manual role requires manual_rubric")
            if self.deterministic_check is not None or self.hybrid_rule is not None:
                raise ValueError(
                    "manual role forbids deterministic_check and hybrid_rule"
                )
            if self.hybrid_composition is not None:
                raise ValueError("manual role forbids hybrid_composition")
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
    task_family: TaskFamily | None = None
    interaction_mode: InteractionMode | None = None
    execution_mode: ExecutionMode | None = None
    response_form: ResponseFormDefinition | None = None

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


@dataclass(frozen=True, slots=True)
class NormalizedLogicalReference:
    id: str
    version: str


@dataclass(frozen=True, slots=True)
class NormalizedResponseFormDefinition:
    category: ResponseFormCategory
    definition: NormalizedLogicalReference


@dataclass(frozen=True, slots=True)
class NormalizedFixtureReference:
    id: str
    version: str
    path: str
    resolved_path: Path


@dataclass(frozen=True, slots=True)
class NormalizedScoringDefinition:
    role: ScoringRole
    deterministic_check: NormalizedLogicalReference | None
    manual_rubric: NormalizedLogicalReference | None
    hybrid_rule: Literal["side-by-side"] | None
    hybrid_composition: NormalizedLogicalReference | None


@dataclass(frozen=True, slots=True)
class NormalizedPrompt:
    id: str
    file: str
    resolved_file: Path
    primary_capability: PrimaryCapability | None
    secondary_stressors: tuple[SecondaryStressor, ...]
    task_family: TaskFamily | None
    interaction_mode: InteractionMode | None
    execution_mode: ExecutionMode | None
    response_form: NormalizedResponseFormDefinition | None
    scoring: NormalizedScoringDefinition | None
    fixtures: tuple[NormalizedFixtureReference, ...]
    metadata: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class NormalizedSuite:
    schema_version: Literal["llmgauge.suite.v0"]
    suite_id: str
    suite_version: str
    title: str | None
    suite_root: Path
    canonical_prompt_ids: tuple[str, ...]
    profiles: Mapping[str, tuple[str, ...]]
    default_profile: str | None
    selected_profile: str | None
    selection_kind: Literal["legacy-all", "profile", "custom"]
    selected_prompt_ids: tuple[str, ...]
    is_complete_named_profile: bool
    is_custom_subset: bool
    prompts: tuple[NormalizedPrompt, ...]
    selected_prompts: tuple[NormalizedPrompt, ...]
    metadata: Mapping[str, Any]


def _freeze_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _freeze_metadata(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_metadata(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_metadata(item) for item in value)
    return value


def _opaque_metadata(data: dict[str, Any], owned_fields: set[str]) -> Mapping[str, Any]:
    return _freeze_metadata(
        {key: value for key, value in data.items() if key not in owned_fields}
    )


def _resolve_owned_file(suite_root: Path, relative_path: str, location: str) -> Path:
    try:
        FixtureReference.validate_path(relative_path)
    except ValueError as exc:
        raise SuiteDefinitionError(
            [f"invalid-relative-path: {location}: {exc}"]
        ) from None

    lexical_target = suite_root.joinpath(*relative_path.split("/"))
    try:
        lexical_target.relative_to(suite_root)
    except ValueError:
        raise SuiteDefinitionError(
            [f"path-escape: {location}: target leaves suite root"]
        ) from None

    try:
        resolved_target = lexical_target.resolve(strict=True)
    except (OSError, RuntimeError):
        raise SuiteDefinitionError(
            [f"missing-resource: {location}: target is unavailable"]
        ) from None

    try:
        resolved_target.relative_to(suite_root)
    except ValueError:
        raise SuiteDefinitionError(
            [f"symlink-escape: {location}: target leaves suite root"]
        ) from None
    if not resolved_target.is_file():
        raise SuiteDefinitionError(
            [f"non-regular-resource: {location}: target is not a regular file"]
        )
    try:
        with resolved_target.open("rb"):
            pass
    except OSError:
        raise SuiteDefinitionError(
            [f"unreadable-resource: {location}: target is unreadable"]
        ) from None
    return resolved_target


def _normalize_logical_reference(
    reference: _LogicalReference | None,
) -> NormalizedLogicalReference | None:
    if reference is None:
        return None
    return NormalizedLogicalReference(id=reference.id, version=reference.version)


_CODING_CORE_VERSION = "0.1.0"
_CODING_CORE_MANUAL_RUBRIC_ID = "coding-core-manual-v0"
_CODING_CORE_COMPOSITION_ID = "coding-core-side-by-side-v0"
_CODING_CORE_REPAIR_ROLE = "repair/prior-response-test-feedback"


@dataclass(frozen=True, slots=True)
class _CodingCorePromptContract:
    id: str
    task_family: TaskFamily
    primary_capability: PrimaryCapability
    secondary_stressors: tuple[SecondaryStressor, ...]
    response_category: ResponseFormCategory
    response_definition_id: str
    scoring_role: ScoringRole
    deterministic_check_id: str | None


_CODING_CORE_PROMPT_CONTRACTS = (
    _CodingCorePromptContract(
        id="debug/state-transition-defect",
        task_family=TaskFamily.SUPPLIED_CODE_DEBUGGING,
        primary_capability=PrimaryCapability.DEBUGGING,
        secondary_stressors=(
            SecondaryStressor.SCOPE_CONTROL,
            SecondaryStressor.DEPENDENCY_API_UNCERTAINTY,
        ),
        response_category=ResponseFormCategory.EXPLANATION_PLUS_CODE,
        response_definition_id="coding-core-explanation-plus-code-form-v0",
        scoring_role=ScoringRole.MANUAL,
        deterministic_check_id=None,
    ),
    _CodingCorePromptContract(
        id="patch/bounded-cross-file-change",
        task_family=TaskFamily.MINIMAL_PATCH_GENERATION,
        primary_capability=PrimaryCapability.MINIMAL_PATCH_GENERATION,
        secondary_stressors=(
            SecondaryStressor.SCOPE_CONTROL,
            SecondaryStressor.STRUCTURED_OUTPUT_COMPLIANCE,
        ),
        response_category=ResponseFormCategory.BOUNDED_PATCH,
        response_definition_id="coding-core-bounded-patch-form-v0",
        scoring_role=ScoringRole.HYBRID,
        deterministic_check_id="coding-core-bounded-patch-envelope-v0",
    ),
    _CodingCorePromptContract(
        id="tests/behavioral-contract-cases",
        task_family=TaskFamily.TEST_DESIGN_AND_CREATION,
        primary_capability=PrimaryCapability.TEST_CREATION,
        secondary_stressors=(
            SecondaryStressor.SCOPE_CONTROL,
            SecondaryStressor.STRUCTURED_OUTPUT_COMPLIANCE,
        ),
        response_category=ResponseFormCategory.CODE_ONLY,
        response_definition_id="coding-core-code-only-tests-form-v0",
        scoring_role=ScoringRole.HYBRID,
        deterministic_check_id="coding-core-code-only-tests-envelope-v0",
    ),
    _CodingCorePromptContract(
        id="diagnosis/supplied-failure-output",
        task_family=TaskFamily.FAILURE_OUTPUT_DIAGNOSIS,
        primary_capability=PrimaryCapability.FAILURE_DIAGNOSIS,
        secondary_stressors=(
            SecondaryStressor.DEBUGGING,
            SecondaryStressor.SCOPE_CONTROL,
            SecondaryStressor.DEPENDENCY_API_UNCERTAINTY,
        ),
        response_category=ResponseFormCategory.EXPLANATION_ONLY,
        response_definition_id="coding-core-explanation-only-form-v0",
        scoring_role=ScoringRole.MANUAL,
        deterministic_check_id=None,
    ),
    _CodingCorePromptContract(
        id="shell/safe-repository-maintenance",
        task_family=TaskFamily.SAFE_COMMAND_RECOMMENDATION,
        primary_capability=PrimaryCapability.SHELL_COMMAND_SAFETY,
        secondary_stressors=(
            SecondaryStressor.SCOPE_CONTROL,
            SecondaryStressor.DEPENDENCY_API_UNCERTAINTY,
        ),
        response_category=ResponseFormCategory.EXPLANATION_ONLY,
        response_definition_id="coding-core-explanation-only-form-v0",
        scoring_role=ScoringRole.MANUAL,
        deterministic_check_id=None,
    ),
    _CodingCorePromptContract(
        id="api/closed-evidence-integration",
        task_family=TaskFamily.DEPENDENCY_API_UNCERTAINTY,
        primary_capability=PrimaryCapability.DEPENDENCY_API_UNCERTAINTY,
        secondary_stressors=(
            SecondaryStressor.SCOPE_CONTROL,
            SecondaryStressor.DEBUGGING,
        ),
        response_category=ResponseFormCategory.EXPLANATION_PLUS_CODE,
        response_definition_id="coding-core-explanation-plus-code-form-v0",
        scoring_role=ScoringRole.MANUAL,
        deterministic_check_id=None,
    ),
    _CodingCorePromptContract(
        id="scope/distractor-aware-change-plan",
        task_family=TaskFamily.SCOPED_CHANGE_PLANNING,
        primary_capability=PrimaryCapability.SCOPE_CONTROL,
        secondary_stressors=(
            SecondaryStressor.MINIMAL_PATCH_GENERATION,
            SecondaryStressor.DEPENDENCY_API_UNCERTAINTY,
        ),
        response_category=ResponseFormCategory.EXPLANATION_ONLY,
        response_definition_id="coding-core-explanation-only-form-v0",
        scoring_role=ScoringRole.MANUAL,
        deterministic_check_id=None,
    ),
    _CodingCorePromptContract(
        id="structured/closed-json-change-record",
        task_family=TaskFamily.STRUCTURED_CODING_RESPONSE,
        primary_capability=PrimaryCapability.STRUCTURED_OUTPUT_COMPLIANCE,
        secondary_stressors=(
            SecondaryStressor.SCOPE_CONTROL,
            SecondaryStressor.INSTRUCTION_COMPLIANCE,
        ),
        response_category=ResponseFormCategory.CLOSED_JSON_RECORD,
        response_definition_id="coding-core-closed-json-record-form-v0",
        scoring_role=ScoringRole.HYBRID,
        deterministic_check_id="coding-core-closed-json-record-v0",
    ),
)
_CODING_CORE_PROMPT_IDS = tuple(
    contract.id for contract in _CODING_CORE_PROMPT_CONTRACTS
)
_CODING_CORE_SMOKE_IDS = (
    "debug/state-transition-defect",
    "patch/bounded-cross-file-change",
    "shell/safe-repository-maintenance",
    "structured/closed-json-change-record",
)
_GENERIC_CORE_VERSION = "0.1.0"
_GENERIC_CORE_MANUAL_RUBRIC_ID = "default-manual-v0"


@dataclass(frozen=True, slots=True)
class _GenericCorePromptContract:
    id: str
    task_family: TaskFamily
    primary_capability: PrimaryCapability
    secondary_stressors: tuple[SecondaryStressor, ...]
    scoring_role: ScoringRole
    deterministic_check_id: str | None
    fixture_ids: tuple[str, ...]


_GENERIC_CORE_PROMPT_CONTRACTS = (
    _GenericCorePromptContract(
        id="generic-core-instruction-rewrite-01",
        task_family=TaskFamily.CONSTRAINED_REWRITE,
        primary_capability=PrimaryCapability.INSTRUCTION_FOLLOWING,
        secondary_stressors=(
            SecondaryStressor.LATE_CONSTRAINTS,
            SecondaryStressor.STRICT_LENGTH,
        ),
        scoring_role=ScoringRole.HYBRID,
        deterministic_check_id="generic-core-constraint-envelope-v0",
        fixture_ids=("generic-core-constraint-envelope-v0",),
    ),
    _GenericCorePromptContract(
        id="generic-core-structured-json-01",
        task_family=TaskFamily.TYPED_RECORD_SERIALIZATION,
        primary_capability=PrimaryCapability.STRUCTURED_OUTPUT,
        secondary_stressors=(SecondaryStressor.NOISE,),
        scoring_role=ScoringRole.DETERMINISTIC,
        deterministic_check_id="generic-core-typed-record-json-v0",
        fixture_ids=("generic-core-typed-record-json-v0",),
    ),
    _GenericCorePromptContract(
        id="generic-core-honesty-evidence-gap-01",
        task_family=TaskFamily.EVIDENCE_SUFFICIENCY_JUDGMENT,
        primary_capability=PrimaryCapability.HONESTY_UNCERTAINTY,
        secondary_stressors=(),
        scoring_role=ScoringRole.MANUAL,
        deterministic_check_id=None,
        fixture_ids=(),
    ),
    _GenericCorePromptContract(
        id="generic-core-summary-decision-log-01",
        task_family=TaskFamily.GROUNDED_DECISION_SUMMARY,
        primary_capability=PrimaryCapability.SUMMARIZATION,
        secondary_stressors=(
            SecondaryStressor.NOISE,
            SecondaryStressor.STRICT_LENGTH,
        ),
        scoring_role=ScoringRole.HYBRID,
        deterministic_check_id="generic-core-summary-envelope-v0",
        fixture_ids=("generic-core-summary-envelope-v0",),
    ),
    _GenericCorePromptContract(
        id="generic-core-extraction-ledger-01",
        task_family=TaskFamily.GROUNDED_FIELD_EXTRACTION,
        primary_capability=PrimaryCapability.EXTRACTION,
        secondary_stressors=(SecondaryStressor.NOISE,),
        scoring_role=ScoringRole.DETERMINISTIC,
        deterministic_check_id="generic-core-ledger-extraction-v0",
        fixture_ids=("generic-core-ledger-extraction-v0",),
    ),
    _GenericCorePromptContract(
        id="generic-core-plan-dependencies-01",
        task_family=TaskFamily.DEPENDENCY_AWARE_PLANNING,
        primary_capability=PrimaryCapability.PLANNING,
        secondary_stressors=(SecondaryStressor.LATE_CONSTRAINTS,),
        scoring_role=ScoringRole.MANUAL,
        deterministic_check_id=None,
        fixture_ids=(),
    ),
    _GenericCorePromptContract(
        id="generic-core-explain-cache-protocol-01",
        task_family=TaskFamily.AUDIENCE_CALIBRATED_MECHANISM_EXPLANATION,
        primary_capability=PrimaryCapability.TECHNICAL_EXPLANATION,
        secondary_stressors=(),
        scoring_role=ScoringRole.MANUAL,
        deterministic_check_id=None,
        fixture_ids=(),
    ),
    _GenericCorePromptContract(
        id="generic-core-code-interval-merge-01",
        task_family=TaskFamily.PURE_FUNCTION_IMPLEMENTATION,
        primary_capability=PrimaryCapability.CODING,
        secondary_stressors=(),
        scoring_role=ScoringRole.HYBRID,
        deterministic_check_id="generic-core-interval-function-v0",
        fixture_ids=(
            "generic-core-interval-function-cases-v0",
            "generic-core-interval-execution-limits-v0",
        ),
    ),
    _GenericCorePromptContract(
        id="generic-core-review-window-average-01",
        task_family=TaskFamily.DEFECT_PRIORITIZATION,
        primary_capability=PrimaryCapability.CODE_REVIEW,
        secondary_stressors=(),
        scoring_role=ScoringRole.MANUAL,
        deterministic_check_id=None,
        fixture_ids=(),
    ),
    _GenericCorePromptContract(
        id="generic-core-troubleshoot-staged-pipeline-01",
        task_family=TaskFamily.DISCRIMINATING_DIAGNOSIS,
        primary_capability=PrimaryCapability.TROUBLESHOOTING,
        secondary_stressors=(SecondaryStressor.NOISE,),
        scoring_role=ScoringRole.MANUAL,
        deterministic_check_id=None,
        fixture_ids=(),
    ),
    _GenericCorePromptContract(
        id="generic-core-safety-risky-heating-01",
        task_family=TaskFamily.CALIBRATED_RISK_BOUNDARY,
        primary_capability=PrimaryCapability.SAFETY_REFUSAL,
        secondary_stressors=(SecondaryStressor.ADVERSARIAL_INSTRUCTIONS,),
        scoring_role=ScoringRole.MANUAL,
        deterministic_check_id=None,
        fixture_ids=(),
    ),
    _GenericCorePromptContract(
        id="generic-core-tool-record-lookup-01",
        task_family=TaskFamily.DECLARED_TOOL_REQUEST_PREPARATION,
        primary_capability=PrimaryCapability.TOOL_PREPARATION,
        secondary_stressors=(),
        scoring_role=ScoringRole.DETERMINISTIC,
        deterministic_check_id="generic-core-tool-request-v0",
        fixture_ids=("generic-core-tool-request-v0",),
    ),
    _GenericCorePromptContract(
        id="generic-core-context-policy-reconcile-01",
        task_family=TaskFamily.BOUNDED_SOURCE_RECONCILIATION,
        primary_capability=PrimaryCapability.BOUNDED_CONTEXT,
        secondary_stressors=(
            SecondaryStressor.NOISE,
            SecondaryStressor.ADVERSARIAL_INSTRUCTIONS,
        ),
        scoring_role=ScoringRole.DETERMINISTIC,
        deterministic_check_id="generic-core-context-reconciliation-v0",
        fixture_ids=(
            "generic-core-context-policy-excerpts-v0",
            "generic-core-context-reconciliation-v0",
        ),
    ),
)
_GENERIC_CORE_PROMPT_IDS = tuple(
    contract.id for contract in _GENERIC_CORE_PROMPT_CONTRACTS
)
_GENERIC_CORE_SMOKE_IDS = (
    "generic-core-instruction-rewrite-01",
    "generic-core-structured-json-01",
    "generic-core-honesty-evidence-gap-01",
    "generic-core-extraction-ledger-01",
)


def _matches_coding_reference(
    reference: _LogicalReference | None, expected_id: str
) -> bool:
    return (
        reference is not None
        and reference.id == expected_id
        and reference.version == _CODING_CORE_VERSION
    )


def _validate_coding_core_contract(
    manifest: SuiteManifest,
    canonical_prompt_ids: tuple[str, ...],
    profiles: Mapping[str, tuple[str, ...]],
) -> None:
    if (
        manifest.suite_id != "coding-core-v1"
        or manifest.suite_version != _CODING_CORE_VERSION
    ):
        return

    diagnostics: list[str] = []
    if canonical_prompt_ids != _CODING_CORE_PROMPT_IDS:
        diagnostics.append(
            "coding-core-inventory: prompts must match the canonical eight-role order"
        )
    if _CODING_CORE_REPAIR_ROLE in canonical_prompt_ids or any(
        _CODING_CORE_REPAIR_ROLE in members for members in profiles.values()
    ):
        diagnostics.append(
            "coding-core-repair-role: the multi-turn repair role is not a static member"
        )
    if set(profiles) != {"smoke", "core"}:
        diagnostics.append(
            "coding-core-profiles: profiles must be exactly 'smoke' and 'core'"
        )
    if manifest.default_profile != "core":
        diagnostics.append(
            "coding-core-default-profile: default_profile must be 'core'"
        )
    if profiles.get("smoke") != _CODING_CORE_SMOKE_IDS:
        diagnostics.append(
            "coding-core-smoke-membership: smoke members or order are invalid"
        )
    if profiles.get("core") != _CODING_CORE_PROMPT_IDS:
        diagnostics.append(
            "coding-core-core-membership: core must equal the canonical inventory"
        )

    contracts_by_id = {
        contract.id: contract for contract in _CODING_CORE_PROMPT_CONTRACTS
    }
    for index, prompt in enumerate(manifest.prompts):
        contract = contracts_by_id.get(prompt.id)
        if contract is None:
            continue
        location = f"coding-core-prompt-{index + 1}"
        if (
            prompt.task_family is not contract.task_family
            or prompt.primary_capability is not contract.primary_capability
            or tuple(prompt.secondary_stressors or ()) != contract.secondary_stressors
        ):
            diagnostics.append(
                f"{location}-metadata: task family, capability, or stressors are invalid"
            )
        if prompt.interaction_mode is not InteractionMode.STATIC_SINGLE_TURN:
            diagnostics.append(
                f"{location}-interaction: interaction_mode must be 'static-single-turn'"
            )
        if prompt.execution_mode is not ExecutionMode.NONE:
            diagnostics.append(f"{location}-execution: execution_mode must be 'none'")
        response_form = prompt.response_form
        if (
            response_form is None
            or response_form.category is not contract.response_category
            or not _matches_coding_reference(
                response_form.definition, contract.response_definition_id
            )
        ):
            diagnostics.append(
                f"{location}-response-form: category or definition reference is invalid"
            )

        scoring = prompt.scoring
        if scoring is None:
            diagnostics.append(f"{location}-scoring: scoring declaration is required")
            continue
        if scoring.role is not contract.scoring_role:
            diagnostics.append(f"{location}-scoring-role: scoring role is invalid")
        if not _matches_coding_reference(
            scoring.manual_rubric, _CODING_CORE_MANUAL_RUBRIC_ID
        ):
            diagnostics.append(
                f"{location}-manual-rubric: manual rubric reference is invalid"
            )
        if contract.deterministic_check_id is None:
            if (
                scoring.deterministic_check is not None
                or scoring.hybrid_rule is not None
                or scoring.hybrid_composition is not None
            ):
                diagnostics.append(
                    f"{location}-manual-scoring: hybrid fields are forbidden"
                )
        else:
            if not _matches_coding_reference(
                scoring.deterministic_check, contract.deterministic_check_id
            ):
                diagnostics.append(
                    f"{location}-deterministic-check: check reference is invalid"
                )
            if scoring.hybrid_rule != "side-by-side":
                diagnostics.append(
                    f"{location}-hybrid-rule: hybrid_rule must be 'side-by-side'"
                )
            if not _matches_coding_reference(
                scoring.hybrid_composition, _CODING_CORE_COMPOSITION_ID
            ):
                diagnostics.append(
                    f"{location}-hybrid-composition: composition reference is invalid"
                )

    if diagnostics:
        raise SuiteDefinitionError(diagnostics)


def _matches_generic_reference(
    reference: _LogicalReference | None, expected_id: str
) -> bool:
    return (
        reference is not None
        and reference.id == expected_id
        and reference.version == _GENERIC_CORE_VERSION
    )


def _validate_generic_core_profiles(
    manifest: SuiteManifest,
    canonical_prompt_ids: tuple[str, ...],
    profiles: Mapping[str, tuple[str, ...]],
) -> None:
    if (
        manifest.suite_id != "generic-core-v1"
        or manifest.suite_version != _GENERIC_CORE_VERSION
    ):
        return

    diagnostics: list[str] = []
    if set(profiles) != {"core", "smoke"}:
        diagnostics.append(
            "generic-core-profiles: profiles must be exactly 'core' and 'smoke'"
        )
    if manifest.default_profile != "core":
        diagnostics.append(
            "generic-core-default-profile: default_profile must be 'core'"
        )

    core = profiles.get("core")
    smoke = profiles.get("smoke")
    if canonical_prompt_ids != _GENERIC_CORE_PROMPT_IDS:
        diagnostics.append(
            "generic-core-inventory: prompts must match the canonical thirteen-role order"
        )
    if core is not None and core != canonical_prompt_ids:
        diagnostics.append(
            "generic-core-core-membership: core must equal the canonical inventory"
        )
    if smoke is not None:
        if smoke != _GENERIC_CORE_SMOKE_IDS:
            diagnostics.append(
                "generic-core-smoke-membership: smoke members or order are invalid"
            )
        elif core is not None:
            smoke_members = set(smoke)
            if (
                not smoke
                or len(smoke) >= len(core)
                or tuple(prompt_id for prompt_id in core if prompt_id in smoke_members)
                != smoke
            ):
                diagnostics.append(
                    "generic-core-smoke-order: smoke must preserve core-relative order"
                )

    contracts_by_id = {
        contract.id: contract for contract in _GENERIC_CORE_PROMPT_CONTRACTS
    }
    for index, prompt in enumerate(manifest.prompts):
        contract = contracts_by_id.get(prompt.id)
        if contract is None:
            continue
        location = f"generic-core-prompt-{index + 1}"
        if (
            prompt.task_family is not contract.task_family
            or prompt.primary_capability is not contract.primary_capability
            or tuple(prompt.secondary_stressors or ()) != contract.secondary_stressors
        ):
            diagnostics.append(
                f"{location}-metadata: task family, capability, or stressors are invalid"
            )
        declared_fixture_ids = tuple(fixture.id for fixture in (prompt.fixtures or ()))
        if declared_fixture_ids != contract.fixture_ids or any(
            fixture.version != _GENERIC_CORE_VERSION
            for fixture in (prompt.fixtures or ())
        ):
            diagnostics.append(f"{location}-fixtures: fixture references are invalid")

        scoring = prompt.scoring
        if scoring is None:
            diagnostics.append(f"{location}-scoring: scoring declaration is required")
            continue
        if scoring.role is not contract.scoring_role:
            diagnostics.append(f"{location}-scoring-role: scoring role is invalid")
        if contract.scoring_role is ScoringRole.DETERMINISTIC:
            if not _matches_generic_reference(
                scoring.deterministic_check, contract.deterministic_check_id or ""
            ):
                diagnostics.append(
                    f"{location}-deterministic-check: check reference is invalid"
                )
            if (
                scoring.manual_rubric is not None
                or scoring.hybrid_rule is not None
                or scoring.hybrid_composition is not None
            ):
                diagnostics.append(
                    f"{location}-deterministic-scoring: hybrid fields are forbidden"
                )
        elif contract.scoring_role is ScoringRole.MANUAL:
            if not _matches_generic_reference(
                scoring.manual_rubric, _GENERIC_CORE_MANUAL_RUBRIC_ID
            ):
                diagnostics.append(
                    f"{location}-manual-rubric: manual rubric reference is invalid"
                )
            if (
                scoring.deterministic_check is not None
                or scoring.hybrid_rule is not None
                or scoring.hybrid_composition is not None
            ):
                diagnostics.append(
                    f"{location}-manual-scoring: hybrid fields are forbidden"
                )
        else:
            if not _matches_generic_reference(
                scoring.deterministic_check, contract.deterministic_check_id or ""
            ):
                diagnostics.append(
                    f"{location}-deterministic-check: check reference is invalid"
                )
            if not _matches_generic_reference(
                scoring.manual_rubric, _GENERIC_CORE_MANUAL_RUBRIC_ID
            ):
                diagnostics.append(
                    f"{location}-manual-rubric: manual rubric reference is invalid"
                )
            if scoring.hybrid_rule != "side-by-side":
                diagnostics.append(
                    f"{location}-hybrid-rule: hybrid_rule must be 'side-by-side'"
                )
            if scoring.hybrid_composition is not None:
                diagnostics.append(
                    f"{location}-hybrid-composition: composition reference is forbidden"
                )

    if diagnostics:
        raise SuiteDefinitionError(diagnostics)


def _select_prompt_ids(
    *,
    manifest: SuiteManifest,
    canonical_prompt_ids: tuple[str, ...],
    profiles: Mapping[str, tuple[str, ...]],
    profile: str | None,
    prompt_ids: Sequence[str] | None,
) -> tuple[str | None, Literal["legacy-all", "profile", "custom"], tuple[str, ...]]:
    if profile is not None and prompt_ids is not None:
        raise SuiteDefinitionError(
            ["selection-conflict: profile and custom prompt IDs are mutually exclusive"]
        )

    if prompt_ids is not None:
        selected = tuple(prompt_ids)
        if not selected:
            raise SuiteDefinitionError(
                ["custom-selection-empty: custom prompt IDs must be non-empty"]
            )
        if len(selected) != len(set(selected)):
            raise SuiteDefinitionError(
                ["custom-selection-duplicate: custom prompt IDs must be unique"]
            )
        canonical_positions = {
            prompt_id: position
            for position, prompt_id in enumerate(canonical_prompt_ids)
        }
        if any(prompt_id not in canonical_positions for prompt_id in selected):
            raise SuiteDefinitionError(
                [
                    "custom-selection-unknown: custom selection contains an unknown prompt ID"
                ]
            )
        positions = [canonical_positions[prompt_id] for prompt_id in selected]
        if positions != sorted(positions):
            raise SuiteDefinitionError(
                [
                    "custom-selection-order: custom prompt IDs must preserve "
                    "canonical order"
                ]
            )
        return None, "custom", selected

    if manifest.profiles is None:
        if profile is not None:
            raise SuiteDefinitionError(
                ["legacy-profile-selection: legacy suites do not declare profiles"]
            )
        return None, "legacy-all", canonical_prompt_ids

    selected_profile = profile if profile is not None else manifest.default_profile
    if selected_profile not in profiles:
        raise SuiteDefinitionError(
            ["unknown-profile: requested profile is not declared by the suite"]
        )
    return selected_profile, "profile", profiles[selected_profile]


def load_normalized_suite(
    suite_dir: Path,
    *,
    profile: str | None = None,
    prompt_ids: Sequence[str] | None = None,
) -> NormalizedSuite:
    """Validate, resolve, and select one suite without mutating its raw manifest."""
    data = load_suite(suite_dir)
    manifest = SuiteManifest.model_validate(data)
    try:
        suite_root = suite_dir.resolve(strict=True)
    except (OSError, RuntimeError):
        raise SuiteDefinitionError(
            ["suite-root-unavailable: suite root is unavailable"]
        ) from None
    if not suite_root.is_dir():
        raise SuiteDefinitionError(
            ["suite-root-invalid: suite root is not a directory"]
        )

    canonical_prompt_ids = tuple(prompt.id for prompt in manifest.prompts)
    profiles = MappingProxyType(
        {
            name: tuple(definition.prompt_ids)
            for name, definition in (manifest.profiles or {}).items()
        }
    )
    _validate_generic_core_profiles(manifest, canonical_prompt_ids, profiles)
    _validate_coding_core_contract(manifest, canonical_prompt_ids, profiles)

    normalized_prompts: list[NormalizedPrompt] = []
    raw_prompts = data["prompts"]
    for prompt_index, (prompt, raw_prompt) in enumerate(
        zip(manifest.prompts, raw_prompts, strict=True)
    ):
        resolved_file = _resolve_owned_file(
            suite_root, prompt.file, f"prompts.{prompt_index}.file"
        )
        normalized_fixtures = tuple(
            NormalizedFixtureReference(
                id=fixture.id,
                version=fixture.version,
                path=fixture.path,
                resolved_path=_resolve_owned_file(
                    suite_root,
                    fixture.path,
                    f"prompts.{prompt_index}.fixtures.{fixture_index}.path",
                ),
            )
            for fixture_index, fixture in enumerate(prompt.fixtures or ())
        )
        scoring = (
            NormalizedScoringDefinition(
                role=prompt.scoring.role,
                deterministic_check=_normalize_logical_reference(
                    prompt.scoring.deterministic_check
                ),
                manual_rubric=_normalize_logical_reference(
                    prompt.scoring.manual_rubric
                ),
                hybrid_rule=prompt.scoring.hybrid_rule,
                hybrid_composition=_normalize_logical_reference(
                    prompt.scoring.hybrid_composition
                ),
            )
            if prompt.scoring is not None
            else None
        )
        normalized_prompts.append(
            NormalizedPrompt(
                id=prompt.id,
                file=prompt.file,
                resolved_file=resolved_file,
                primary_capability=prompt.primary_capability,
                secondary_stressors=tuple(prompt.secondary_stressors or ()),
                task_family=prompt.task_family,
                interaction_mode=prompt.interaction_mode,
                execution_mode=prompt.execution_mode,
                response_form=(
                    NormalizedResponseFormDefinition(
                        category=prompt.response_form.category,
                        definition=NormalizedLogicalReference(
                            id=prompt.response_form.definition.id,
                            version=prompt.response_form.definition.version,
                        ),
                    )
                    if prompt.response_form is not None
                    else None
                ),
                scoring=scoring,
                fixtures=normalized_fixtures,
                metadata=_opaque_metadata(
                    raw_prompt,
                    {
                        "id",
                        "file",
                        "primary_capability",
                        "secondary_stressors",
                        "scoring",
                        "fixtures",
                        "task_family",
                        "interaction_mode",
                        "execution_mode",
                        "response_form",
                    },
                ),
            )
        )

    selected_profile, selection_kind, selected_prompt_ids = _select_prompt_ids(
        manifest=manifest,
        canonical_prompt_ids=canonical_prompt_ids,
        profiles=profiles,
        profile=profile,
        prompt_ids=prompt_ids,
    )
    prompts_by_id = {prompt.id: prompt for prompt in normalized_prompts}
    normalized_prompt_tuple = tuple(normalized_prompts)
    return NormalizedSuite(
        schema_version=manifest.schema_version,
        suite_id=manifest.suite_id,
        suite_version=manifest.suite_version,
        title=manifest.title,
        suite_root=suite_root,
        canonical_prompt_ids=canonical_prompt_ids,
        profiles=profiles,
        default_profile=manifest.default_profile,
        selected_profile=selected_profile,
        selection_kind=selection_kind,
        selected_prompt_ids=selected_prompt_ids,
        is_complete_named_profile=selection_kind == "profile",
        is_custom_subset=selection_kind == "custom",
        prompts=normalized_prompt_tuple,
        selected_prompts=tuple(
            prompts_by_id[prompt_id] for prompt_id in selected_prompt_ids
        ),
        metadata=_opaque_metadata(
            data,
            {
                "schema_version",
                "suite_id",
                "suite_version",
                "title",
                "prompts",
                "profiles",
                "default_profile",
            },
        ),
    )


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
