from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Literal
from llmgauge.core.generic_core_scoring import (
    apply_deterministic_check as apply_generic_core_deterministic_check,
    compose_hybrid_score as compose_generic_core_hybrid_score,
    is_generic_core_suite,
)


from llmgauge.core.suite import (
    NormalizedPrompt,
    NormalizedSuite,
    ResponseFormCategory,
    ScoringRole,
)

CODING_CORE_SUITE_ID = "coding-core-v1"
CODING_CORE_VERSION = "0.1.0"
CODING_CORE_MANUAL_RUBRIC_ID = "coding-core-manual-v0"
CODING_CORE_SIDE_BY_SIDE_ID = "coding-core-side-by-side-v0"

CODING_CORE_DIMENSIONS = (
    "diagnosis_accuracy",
    "supplied_evidence_use",
    "correction_code_plausibility",
    "minimality_scope_control",
    "instruction_compliance",
    "response_completeness",
    "shell_operational_safety",
    "uncertainty_unsupported_assumptions",
    "dependency_api_honesty",
    "test_quality_failure_sensitivity",
    "semantic_record_support",
)

CODING_CORE_APPLICABILITY: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "debug/state-transition-defect": (
            "diagnosis_accuracy",
            "supplied_evidence_use",
            "correction_code_plausibility",
            "minimality_scope_control",
            "instruction_compliance",
            "response_completeness",
            "uncertainty_unsupported_assumptions",
        ),
        "patch/bounded-cross-file-change": (
            "supplied_evidence_use",
            "correction_code_plausibility",
            "minimality_scope_control",
            "instruction_compliance",
            "response_completeness",
            "uncertainty_unsupported_assumptions",
        ),
        "tests/behavioral-contract-cases": (
            "supplied_evidence_use",
            "minimality_scope_control",
            "instruction_compliance",
            "response_completeness",
            "uncertainty_unsupported_assumptions",
            "test_quality_failure_sensitivity",
        ),
        "diagnosis/supplied-failure-output": (
            "diagnosis_accuracy",
            "supplied_evidence_use",
            "instruction_compliance",
            "response_completeness",
            "uncertainty_unsupported_assumptions",
        ),
        "shell/safe-repository-maintenance": (
            "supplied_evidence_use",
            "minimality_scope_control",
            "instruction_compliance",
            "response_completeness",
            "shell_operational_safety",
            "uncertainty_unsupported_assumptions",
        ),
        "api/closed-evidence-integration": (
            "supplied_evidence_use",
            "correction_code_plausibility",
            "minimality_scope_control",
            "instruction_compliance",
            "response_completeness",
            "uncertainty_unsupported_assumptions",
            "dependency_api_honesty",
        ),
        "scope/distractor-aware-change-plan": (
            "supplied_evidence_use",
            "minimality_scope_control",
            "instruction_compliance",
            "response_completeness",
            "uncertainty_unsupported_assumptions",
        ),
        "structured/closed-json-change-record": (
            "supplied_evidence_use",
            "minimality_scope_control",
            "instruction_compliance",
            "response_completeness",
            "uncertainty_unsupported_assumptions",
            "semantic_record_support",
        ),
    }
)

Outcome = Literal["pass", "fail", "error", "not_run"]
ManualReviewState = Literal[
    "missing", "unreviewed", "partial", "reviewed", "unscoreable"
]
STATIC_RESPONSE_MAX_CHARS = 1_000_000
_MAX_FORM_BYTES = 64 * 1024
_MAX_EVIDENCE_ITEMS = 32


class StaticScoringError(ValueError):
    """A bounded, public-safe static scoring configuration error."""


@dataclass(frozen=True, slots=True)
class _MethodSpec:
    prompt_id: str
    form_id: str
    form_category: ResponseFormCategory
    check: Callable[[str, Mapping[str, Any]], list[dict[str, str]]]


def _evidence(property_name: str, status: Outcome, detail: str) -> dict[str, str]:
    return {"property": property_name, "status": status, "detail": detail[:256]}


def _failed(evidence: list[dict[str, str]]) -> bool:
    return any(item["status"] == "fail" for item in evidence)


def _json_object_without_duplicates(text: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate object key")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON constant: {value}")

    return json.loads(
        text,
        object_pairs_hook=reject_duplicates,
        parse_constant=reject_constant,
    )


def _load_response_form(
    suite: NormalizedSuite,
    prompt: NormalizedPrompt,
) -> tuple[Mapping[str, Any] | None, str | None]:
    response_form = prompt.response_form
    if response_form is None:
        return None, "response-form-missing"

    reference = response_form.definition
    relative_path = (
        Path("response-forms") / f"v{reference.version}" / f"{reference.id}.json"
    )
    candidate = suite.suite_root / relative_path
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(suite.suite_root)
        if not resolved.is_file() or resolved.stat().st_size > _MAX_FORM_BYTES:
            return None, "response-form-unavailable"
        data = _json_object_without_duplicates(resolved.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, UnicodeError, json.JSONDecodeError, ValueError):
        return None, "response-form-unavailable"

    if not isinstance(data, dict):
        return None, "response-form-invalid"
    if (
        data.get("resource_id") != reference.id
        or data.get("version") != reference.version
        or data.get("category") != response_form.category.value
    ):
        return None, "response-form-identity-mismatch"
    return data, None


def _patch_check(raw_response: str, form: Mapping[str, Any]) -> list[dict[str, str]]:
    envelope = form.get("allowed_envelope")
    if not isinstance(envelope, dict):
        raise ValueError("invalid response-form envelope")
    first_line = envelope.get("first_line")
    last_line = envelope.get("last_line")
    hunks = envelope.get("hunks")
    if (
        not isinstance(first_line, str)
        or not isinstance(last_line, str)
        or not isinstance(hunks, dict)
    ):
        raise ValueError("invalid response-form patch configuration")
    prefixes = hunks.get("body_line_prefixes")
    hunk_prefix = hunks.get("header_prefix")
    if (
        not isinstance(prefixes, list)
        or not prefixes
        or not all(isinstance(item, str) and len(item) == 1 for item in prefixes)
        or not isinstance(hunk_prefix, str)
        or not hunk_prefix
    ):
        raise ValueError("invalid response-form hunk configuration")

    lines = raw_response.splitlines()
    evidence: list[dict[str, str]] = []
    envelope_ok = len(lines) >= 2 and lines[0] == first_line and lines[-1] == last_line
    evidence.append(
        _evidence(
            "patch-envelope",
            "pass" if envelope_ok else "fail",
            "exact patch envelope observed"
            if envelope_ok
            else "patch envelope is missing or has surrounding text",
        )
    )
    fence_free = not any(line.strip().startswith("```") for line in lines)
    evidence.append(
        _evidence(
            "markdown-fence",
            "pass" if fence_free else "fail",
            "no Markdown fence observed"
            if fence_free
            else "Markdown fence is not allowed",
        )
    )
    if not envelope_ok:
        return evidence

    allowed_paths = {"src/config.py", "tests/test_config.py"}
    sections: list[tuple[str, list[str]]] = []
    current_path: str | None = None
    current_body: list[str] = []
    unsupported_operation = False
    extra_content = False
    for line in lines[1:-1]:
        if line.startswith("*** Update File: "):
            if current_path is not None:
                sections.append((current_path, current_body))
            current_path = line.removeprefix("*** Update File: ")
            current_body = []
        elif line.startswith("*** "):
            unsupported_operation = True
            if current_path is not None:
                current_body.append(line)
        elif current_path is not None:
            current_body.append(line)
        else:
            extra_content = True
    if current_path is not None:
        sections.append((current_path, current_body))

    evidence.append(
        _evidence(
            "file-sections",
            "pass" if sections else "fail",
            "at least one update section observed"
            if sections
            else "no supported update section was observed",
        )
    )
    evidence.append(
        _evidence(
            "update-only",
            "fail" if unsupported_operation else "pass",
            "unsupported patch operation observed"
            if unsupported_operation
            else "only update operations observed",
        )
    )
    evidence.append(
        _evidence(
            "extra-content",
            "fail" if extra_content else "pass",
            "content outside a file section was observed"
            if extra_content
            else "no content outside file sections was observed",
        )
    )

    paths = [path for path, _ in sections]
    duplicate_paths = len(paths) != len(set(paths))
    absolute_paths = any(
        PurePosixPath(path).is_absolute() or re.match(r"^[A-Za-z]:[/\\]", path)
        for path in paths
    )
    traversing_paths = any(
        "\\" in path or ".." in PurePosixPath(path).parts for path in paths
    )
    undeclared_paths = any(path not in allowed_paths for path in paths)
    for property_name, failed, failure_detail, pass_detail in (
        (
            "duplicate-paths",
            duplicate_paths,
            "duplicate patch path observed",
            "patch paths are unique",
        ),
        (
            "absolute-paths",
            absolute_paths,
            "absolute patch path observed",
            "patch paths are relative",
        ),
        (
            "path-traversal",
            traversing_paths,
            "traversing or non-portable patch path observed",
            "patch paths are normalized",
        ),
        (
            "declared-paths",
            undeclared_paths,
            "undeclared patch path observed",
            "all patch paths are declared",
        ),
    ):
        evidence.append(
            _evidence(
                property_name,
                "fail" if failed else "pass",
                failure_detail if failed else pass_detail,
            )
        )

    missing_hunk = False
    invalid_hunk_line = False
    empty_hunk = False
    for _, body in sections:
        hunk_seen = False
        hunk_has_body = False
        for line in body:
            if line.startswith(hunk_prefix):
                if hunk_seen and not hunk_has_body:
                    empty_hunk = True
                hunk_seen = True
                hunk_has_body = False
            elif not hunk_seen or not any(
                line.startswith(prefix) for prefix in prefixes
            ):
                invalid_hunk_line = True
            else:
                hunk_has_body = True
        if not hunk_seen:
            missing_hunk = True
        elif not hunk_has_body:
            empty_hunk = True

    evidence.append(
        _evidence(
            "hunk-presence",
            "fail" if missing_hunk else "pass",
            "a file section has no hunk"
            if missing_hunk
            else "every file section has a hunk",
        )
    )
    evidence.append(
        _evidence(
            "hunk-content",
            "fail" if empty_hunk else "pass",
            "an empty hunk was observed"
            if empty_hunk
            else "every hunk has body content",
        )
    )
    evidence.append(
        _evidence(
            "hunk-line-prefixes",
            "fail" if invalid_hunk_line else "pass",
            "a hunk line has a prohibited prefix"
            if invalid_hunk_line
            else "all hunk lines use allowed prefixes",
        )
    )
    return evidence


def _code_only_check(
    raw_response: str, form: Mapping[str, Any]
) -> list[dict[str, str]]:
    envelope = form.get("allowed_envelope")
    if not isinstance(envelope, dict):
        raise ValueError("invalid response-form envelope")
    language_tag = envelope.get("language_tag")
    fenced_blocks = envelope.get("fenced_blocks")
    if language_tag != "python" or fenced_blocks != 1:
        raise ValueError("invalid response-form code-only configuration")

    lines = raw_response.splitlines()
    exact_envelope = (
        len(lines) >= 3 and lines[0] == f"```{language_tag}" and lines[-1] == "```"
    )
    fence_lines = [line for line in lines if line.startswith("```")]
    exactly_one_block = exact_envelope and len(fence_lines) == 2
    code_lines = lines[1:-1] if exact_envelope else []
    nonempty_code = bool("\n".join(code_lines).strip())
    patch_envelope = any(
        line in {"*** Begin Patch", "*** End Patch"} for line in code_lines
    )

    return [
        _evidence(
            "code-envelope",
            "pass" if exact_envelope else "fail",
            "code fence is the complete response"
            if exact_envelope
            else "code fence is missing or has surrounding text",
        ),
        _evidence(
            "fenced-block-count",
            "pass" if exactly_one_block else "fail",
            "exactly one fenced block observed"
            if exactly_one_block
            else "response does not contain exactly one fenced block",
        ),
        _evidence(
            "language-tag",
            "pass" if exact_envelope else "fail",
            "exact python language tag observed"
            if exact_envelope
            else "exact python language tag was not observed",
        ),
        _evidence(
            "code-content",
            "pass" if nonempty_code else "fail",
            "non-empty code content observed"
            if nonempty_code
            else "code content is empty",
        ),
        _evidence(
            "second-artifact",
            "fail" if patch_envelope else "pass",
            "patch envelope observed inside code artifact"
            if patch_envelope
            else "no second artifact observed",
        ),
    ]


def _ordered_keys(value: Any, expected: list[str]) -> bool:
    return isinstance(value, dict) and list(value) == expected


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _all_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for item in value.values():
            strings.extend(_all_strings(item))
        return strings
    if isinstance(value, list):
        strings = []
        for item in value:
            strings.extend(_all_strings(item))
        return strings
    return []


_FORBIDDEN_STRING_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-path", re.compile(r"(?:/home/|/Users/|[A-Za-z]:\\\\Users\\\\)")),
    ("url", re.compile(r"\b(?:https?|ftp)://", re.IGNORECASE)),
    (
        "secret",
        re.compile(
            r"(?:BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|(?:api[_-]?key|token|password)\s*[:=])",
            re.IGNORECASE,
        ),
    ),
    (
        "command",
        re.compile(
            r"(?:^|\n)\s*(?:\$\s+|sudo\s+|git\s+|pytest(?:\s|$)|python(?:3)?\s+-m\s+)",
            re.IGNORECASE,
        ),
    ),
    (
        "applied-or-verified-claim",
        re.compile(
            r"\b(?:change (?:was|is) applied|tests? passed|verified successfully|static review passed)\b",
            re.IGNORECASE,
        ),
    ),
)


def _closed_json_check(
    raw_response: str, form: Mapping[str, Any]
) -> list[dict[str, str]]:
    try:
        value = _json_object_without_duplicates(raw_response)
        parsed = True
    except (json.JSONDecodeError, ValueError):
        value = None
        parsed = False

    evidence = [
        _evidence(
            "json-parse",
            "pass" if parsed else "fail",
            "one JSON value parsed"
            if parsed
            else "response is not one valid JSON value",
        )
    ]
    if not parsed:
        return evidence

    envelope = form.get("allowed_envelope")
    properties = form.get("properties")
    if not isinstance(envelope, dict) or not isinstance(properties, dict):
        raise ValueError("invalid response-form JSON configuration")
    top_key_order = envelope.get("key_order")
    if not isinstance(top_key_order, list) or not all(
        isinstance(item, str) for item in top_key_order
    ):
        raise ValueError("invalid response-form JSON key order")

    top_level_ok = _ordered_keys(value, top_key_order)
    evidence.append(
        _evidence(
            "top-level-keys",
            "pass" if top_level_ok else "fail",
            "top-level keys and order conform"
            if top_level_ok
            else "top-level keys or order do not conform",
        )
    )
    if not isinstance(value, dict):
        return evidence

    no_nulls = not any(item is None for item in _walk_values(value))
    evidence.append(
        _evidence(
            "null-values",
            "pass" if no_nulls else "fail",
            "no null values observed" if no_nulls else "null value observed",
        )
    )

    change_id = properties.get("change_id")
    summary = properties.get("summary")
    if not isinstance(change_id, dict) or not isinstance(summary, dict):
        raise ValueError("invalid response-form scalar configuration")
    change_id_ok = value.get("change_id") == change_id.get("const")
    summary_value = value.get("summary")
    summary_ok = (
        _nonempty_string(summary_value)
        and isinstance(summary.get("max_length"), int)
        and len(summary_value) <= summary["max_length"]
    )
    evidence.extend(
        [
            _evidence(
                "change-id",
                "pass" if change_id_ok else "fail",
                "change ID conforms" if change_id_ok else "change ID does not conform",
            ),
            _evidence(
                "summary",
                "pass" if summary_ok else "fail",
                "summary type and length conform"
                if summary_ok
                else "summary type or length does not conform",
            ),
        ]
    )

    files_config = properties.get("files")
    files_value = value.get("files")
    files_ok = False
    if isinstance(files_config, dict):
        expected_files = files_config.get("items_in_order")
        item_order = files_config.get("item_key_order")
        files_ok = (
            isinstance(files_value, list)
            and isinstance(expected_files, list)
            and isinstance(item_order, list)
            and len(files_value) == len(expected_files) == 2
            and all(_ordered_keys(item, item_order) for item in files_value)
            and files_value == expected_files
        )
    evidence.append(
        _evidence(
            "files",
            "pass" if files_ok else "fail",
            "file records and order conform"
            if files_ok
            else "file records or order do not conform",
        )
    )

    behavior_config = properties.get("behavior")
    behavior_value = value.get("behavior")
    behavior_ok = False
    if isinstance(behavior_config, dict):
        behavior_order = behavior_config.get("key_order")
        behavior_ok = (
            isinstance(behavior_order, list)
            and _ordered_keys(behavior_value, behavior_order)
            and all(_nonempty_string(behavior_value.get(key)) for key in behavior_order)
        )
    evidence.append(
        _evidence(
            "behavior",
            "pass" if behavior_ok else "fail",
            "behavior record conforms"
            if behavior_ok
            else "behavior record does not conform",
        )
    )

    verification_config = properties.get("verification")
    verification_value = value.get("verification")
    verification_ok = False
    if isinstance(verification_config, dict):
        expected_verification = verification_config.get("items_in_order")
        item_order = verification_config.get("item_key_order")
        if (
            isinstance(verification_value, list)
            and isinstance(expected_verification, list)
            and isinstance(item_order, list)
            and len(verification_value) == len(expected_verification) == 2
        ):
            verification_ok = True
            for item, expected in zip(
                verification_value, expected_verification, strict=True
            ):
                if not _ordered_keys(item, item_order) or not isinstance(item, dict):
                    verification_ok = False
                    break
                if (
                    item.get("check") != expected.get("check")
                    or item.get("status") != expected.get("status")
                    or not _nonempty_string(item.get("reason"))
                ):
                    verification_ok = False
                    break
    evidence.append(
        _evidence(
            "verification",
            "pass" if verification_ok else "fail",
            "verification records and order conform"
            if verification_ok
            else "verification records or order do not conform",
        )
    )

    uncertainty_config = properties.get("uncertainties")
    uncertainty_value = value.get("uncertainties")
    uncertainty_ok = False
    if isinstance(uncertainty_config, dict):
        subject = uncertainty_config.get("required_subject")
        uncertainty_ok = (
            isinstance(uncertainty_value, list)
            and len(uncertainty_value) == 1
            and _nonempty_string(uncertainty_value[0])
            and isinstance(subject, str)
            and subject.casefold() in uncertainty_value[0].casefold()
        )
    evidence.append(
        _evidence(
            "uncertainties",
            "pass" if uncertainty_ok else "fail",
            "required uncertainty subject conforms"
            if uncertainty_ok
            else "required uncertainty subject does not conform",
        )
    )

    forbidden_classes = sorted(
        name
        for name, pattern in _FORBIDDEN_STRING_PATTERNS
        if any(pattern.search(text) for text in _all_strings(value))
    )
    evidence.append(
        _evidence(
            "forbidden-string-content",
            "fail" if forbidden_classes else "pass",
            "prohibited string content observed: " + ", ".join(forbidden_classes)
            if forbidden_classes
            else "no deterministically representable prohibited string content observed",
        )
    )
    return evidence


def _walk_values(value: Any) -> list[Any]:
    values = [value]
    if isinstance(value, dict):
        for item in value.values():
            values.extend(_walk_values(item))
    elif isinstance(value, list):
        for item in value:
            values.extend(_walk_values(item))
    return values


_DETERMINISTIC_METHODS: Mapping[tuple[str, str], _MethodSpec] = MappingProxyType(
    {
        ("coding-core-bounded-patch-envelope-v0", CODING_CORE_VERSION): _MethodSpec(
            prompt_id="patch/bounded-cross-file-change",
            form_id="coding-core-bounded-patch-form-v0",
            form_category=ResponseFormCategory.BOUNDED_PATCH,
            check=_patch_check,
        ),
        ("coding-core-code-only-tests-envelope-v0", CODING_CORE_VERSION): _MethodSpec(
            prompt_id="tests/behavioral-contract-cases",
            form_id="coding-core-code-only-tests-form-v0",
            form_category=ResponseFormCategory.CODE_ONLY,
            check=_code_only_check,
        ),
        ("coding-core-closed-json-record-v0", CODING_CORE_VERSION): _MethodSpec(
            prompt_id="structured/closed-json-change-record",
            form_id="coding-core-closed-json-record-form-v0",
            form_category=ResponseFormCategory.CLOSED_JSON_RECORD,
            check=_closed_json_check,
        ),
    }
)
MANUAL_RUBRICS = frozenset({(CODING_CORE_MANUAL_RUBRIC_ID, CODING_CORE_VERSION)})
HYBRID_COMPOSITIONS = frozenset({(CODING_CORE_SIDE_BY_SIDE_ID, CODING_CORE_VERSION)})
DETERMINISTIC_METHODS = frozenset(_DETERMINISTIC_METHODS)


def _prompt_by_id(suite: NormalizedSuite, prompt_id: str) -> NormalizedPrompt:
    if (
        suite.suite_id != CODING_CORE_SUITE_ID
        or suite.suite_version != CODING_CORE_VERSION
    ):
        raise StaticScoringError(
            "unsupported-suite: static scoring suite ID/version is unsupported"
        )
    prompt = next((item for item in suite.prompts if item.id == prompt_id), None)
    if prompt is None:
        raise StaticScoringError(
            "unsupported-prompt: static scoring prompt is unsupported"
        )
    return prompt


def apply_deterministic_check(
    suite: NormalizedSuite,
    prompt_id: str,
    raw_response: str | None,
    *,
    generation_failed: bool = False,
) -> dict[str, Any]:
    """Apply one declared non-executing check to preserved raw response evidence."""
    if is_generic_core_suite(suite):
        return apply_generic_core_deterministic_check(
            suite,
            prompt_id,
            raw_response,
            generation_failed=generation_failed,
        )
    prompt = _prompt_by_id(suite, prompt_id)
    scoring = prompt.scoring
    if scoring is None or scoring.deterministic_check is None:
        raise StaticScoringError(
            "prompt-method-mismatch: prompt has no deterministic check"
        )
    reference = scoring.deterministic_check
    method_key = (reference.id, reference.version)
    spec = _DETERMINISTIC_METHODS.get(method_key)
    if spec is None:
        raise StaticScoringError(
            "unsupported-method: deterministic check ID/version is unsupported"
        )
    response_form = prompt.response_form
    if (
        spec.prompt_id != prompt.id
        or response_form is None
        or response_form.definition.id != spec.form_id
        or response_form.definition.version != reference.version
        or response_form.category is not spec.form_category
    ):
        raise StaticScoringError(
            "prompt-method-mismatch: prompt, method, and response form do not match"
        )

    base = {
        "prompt_id": prompt.id,
        "check_id": reference.id,
        "check_version": reference.version,
        "response_form_id": response_form.definition.id,
        "response_form_version": response_form.definition.version,
    }
    if raw_response is None or (generation_failed and raw_response == ""):
        detail = (
            "raw response evidence is absent after generation failure"
            if generation_failed
            else "raw response evidence is absent"
        )
        return {
            **base,
            "outcome": "not_run",
            "evidence": [_evidence("raw-response", "not_run", detail)],
            "error_classification": None,
        }
    if not isinstance(raw_response, str):
        return {
            **base,
            "outcome": "error",
            "evidence": [
                _evidence(
                    "raw-response",
                    "error",
                    "raw response evidence has an unsupported type",
                )
            ],
            "error_classification": "invalid-input",
        }
    if len(raw_response) > STATIC_RESPONSE_MAX_CHARS:
        return {
            **base,
            "outcome": "error",
            "evidence": [
                _evidence(
                    "raw-response",
                    "error",
                    "raw response exceeds the local parsing bound",
                )
            ],
            "error_classification": "resource-bound",
        }

    form, form_error = _load_response_form(suite, prompt)
    if form_error is not None or form is None:
        return {
            **base,
            "outcome": "error",
            "evidence": [
                _evidence(
                    "response-form",
                    "error",
                    "selected response-form resource is unavailable or invalid",
                )
            ],
            "error_classification": form_error,
        }

    try:
        evidence = spec.check(raw_response, form)[:_MAX_EVIDENCE_ITEMS]
    except RecursionError:
        return {
            **base,
            "outcome": "error",
            "evidence": [
                _evidence(
                    "raw-response",
                    "error",
                    "raw response exceeds the local parsing depth bound",
                )
            ],
            "error_classification": "resource-bound",
        }
    except (TypeError, ValueError):
        return {
            **base,
            "outcome": "error",
            "evidence": [
                _evidence(
                    "response-form",
                    "error",
                    "selected response-form resource cannot be evaluated",
                )
            ],
            "error_classification": "response-form-invalid",
        }
    outcome: Outcome = "fail" if _failed(evidence) else "pass"
    return {
        **base,
        "outcome": outcome,
        "evidence": evidence,
        "error_classification": None,
    }


def applicable_manual_dimensions(prompt_id: str) -> tuple[str, ...]:
    try:
        return CODING_CORE_APPLICABILITY[prompt_id]
    except KeyError:
        raise StaticScoringError(
            "unsupported-prompt: manual rubric prompt is unsupported"
        ) from None


_DETERMINISTIC_RESULT_FIELDS = frozenset(
    {
        "prompt_id",
        "check_id",
        "check_version",
        "response_form_id",
        "response_form_version",
        "outcome",
        "evidence",
        "error_classification",
    }
)
_SUPPORTED_ERROR_CLASSIFICATIONS = frozenset(
    {
        "invalid-input",
        "resource-bound",
        "response-form-unavailable",
        "response-form-invalid",
        "response-form-identity-mismatch",
    }
)
_EVIDENCE_STATUSES = frozenset({"pass", "fail", "error", "not_run"})
_MAX_EVIDENCE_PROPERTY_LENGTH = 128
_INVALID_DETERMINISTIC_COMPONENT = (
    "invalid-deterministic-component: deterministic component is malformed "
    "or inconsistent"
)


def _validate_deterministic_component(
    prompt: NormalizedPrompt,
    deterministic_result: Mapping[str, Any],
) -> Outcome:
    scoring = prompt.scoring
    response_form = prompt.response_form
    check = scoring.deterministic_check if scoring is not None else None
    if (
        check is None
        or response_form is None
        or not isinstance(deterministic_result, Mapping)
        or set(deterministic_result) != _DETERMINISTIC_RESULT_FIELDS
        or deterministic_result.get("prompt_id") != prompt.id
        or deterministic_result.get("check_id") != check.id
        or deterministic_result.get("check_version") != check.version
        or deterministic_result.get("response_form_id") != response_form.definition.id
        or deterministic_result.get("response_form_version")
        != response_form.definition.version
    ):
        raise StaticScoringError(_INVALID_DETERMINISTIC_COMPONENT)

    outcome = deterministic_result.get("outcome")
    evidence = deterministic_result.get("evidence")
    error_classification = deterministic_result.get("error_classification")
    if (
        not isinstance(outcome, str)
        or outcome not in {"pass", "fail", "error", "not_run"}
        or (
            error_classification is not None
            and not isinstance(error_classification, str)
        )
        or not isinstance(evidence, list)
        or not 1 <= len(evidence) <= _MAX_EVIDENCE_ITEMS
    ):
        raise StaticScoringError(_INVALID_DETERMINISTIC_COMPONENT)

    statuses: list[str] = []
    for item in evidence:
        if not isinstance(item, Mapping) or set(item) != {
            "property",
            "status",
            "detail",
        }:
            raise StaticScoringError(_INVALID_DETERMINISTIC_COMPONENT)
        property_name = item.get("property")
        status = item.get("status")
        detail = item.get("detail")
        if (
            not isinstance(property_name, str)
            or not property_name
            or len(property_name) > _MAX_EVIDENCE_PROPERTY_LENGTH
            or not isinstance(status, str)
            or status not in _EVIDENCE_STATUSES
            or not isinstance(detail, str)
            or not detail
            or len(detail) > 256
        ):
            raise StaticScoringError(_INVALID_DETERMINISTIC_COMPONENT)
        statuses.append(status)

    valid_relationship = (
        (
            outcome == "pass"
            and error_classification is None
            and all(status == "pass" for status in statuses)
        )
        or (
            outcome == "fail"
            and error_classification is None
            and all(status in {"pass", "fail"} for status in statuses)
            and "fail" in statuses
        )
        or (
            outcome == "error"
            and error_classification in _SUPPORTED_ERROR_CLASSIFICATIONS
            and all(status == "error" for status in statuses)
        )
        or (
            outcome == "not_run"
            and error_classification is None
            and all(status == "not_run" for status in statuses)
        )
    )
    if not valid_relationship:
        raise StaticScoringError(_INVALID_DETERMINISTIC_COMPONENT)
    return outcome


def manual_review_state(
    prompt_id: str, score_entry: Mapping[str, Any] | None
) -> ManualReviewState:
    dimensions = applicable_manual_dimensions(prompt_id)
    if score_entry is None:
        return "missing"
    if not isinstance(score_entry, Mapping):
        raise StaticScoringError(
            "invalid-manual-component: manual component is malformed"
        )

    reviewed = score_entry.get("reviewed") is True
    if not reviewed:
        return "unreviewed"

    nested_dimensions = score_entry.get("dimensions")
    if "dimensions" in score_entry and not isinstance(nested_dimensions, Mapping):
        raise StaticScoringError(
            "invalid-manual-component: manual component is malformed"
        )
    values = (
        nested_dimensions if isinstance(nested_dimensions, Mapping) else score_entry
    )

    valid_numeric_count = 0
    for field in dimensions:
        value = values.get(field)
        if (
            not isinstance(value, bool)
            and isinstance(value, int | float)
            and 0 <= value <= 5
            and (not isinstance(value, float) or math.isfinite(value))
        ):
            valid_numeric_count += 1

    verdict = score_entry.get("verdict")
    rationale = score_entry.get("score_rationale")
    scorer_id = score_entry.get("scorer_id")
    if (
        valid_numeric_count == len(dimensions)
        and isinstance(verdict, str)
        and verdict in {"pass", "mixed", "fail"}
        and isinstance(rationale, str)
        and bool(rationale.strip())
        and isinstance(scorer_id, str)
        and bool(scorer_id.strip())
    ):
        return "reviewed"
    if valid_numeric_count:
        return "partial"
    return "unscoreable"


def compose_hybrid_score(
    suite: NormalizedSuite,
    prompt_id: str,
    deterministic_result: Mapping[str, Any],
    manual_score_entry: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Compose independent structural and manual state without a numeric blend."""
    if is_generic_core_suite(suite):
        return compose_generic_core_hybrid_score(
            suite, prompt_id, deterministic_result, manual_score_entry
        )
    prompt = _prompt_by_id(suite, prompt_id)
    scoring = prompt.scoring
    if (
        scoring is None
        or scoring.role is not ScoringRole.HYBRID
        or scoring.hybrid_rule != "side-by-side"
        or scoring.hybrid_composition is None
        or scoring.manual_rubric is None
    ):
        raise StaticScoringError(
            "prompt-method-mismatch: prompt has no supported hybrid composition"
        )
    composition = scoring.hybrid_composition
    rubric = scoring.manual_rubric
    if (composition.id, composition.version) not in HYBRID_COMPOSITIONS:
        raise StaticScoringError(
            "unsupported-method: hybrid composition ID/version is unsupported"
        )
    if (rubric.id, rubric.version) not in MANUAL_RUBRICS:
        raise StaticScoringError(
            "unsupported-method: manual rubric ID/version is unsupported"
        )
    deterministic_outcome = _validate_deterministic_component(
        prompt, deterministic_result
    )

    state = manual_review_state(prompt_id, manual_score_entry)
    return {
        "prompt_id": prompt.id,
        "composition_id": composition.id,
        "composition_version": composition.version,
        "deterministic_result": dict(deterministic_result),
        "manual_component": {
            "rubric_id": rubric.id,
            "rubric_version": rubric.version,
            "review_state": state,
            "reviewed": state == "reviewed",
            "verdict": manual_score_entry.get("verdict")
            if manual_score_entry is not None
            else None,
        },
        "complete": deterministic_outcome in {"pass", "fail"} and state == "reviewed",
    }
