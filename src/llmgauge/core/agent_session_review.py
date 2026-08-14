from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from llmgauge import __version__
from llmgauge.core.agent_harness import (
    AgentHarnessEvidence,
    load_agent_harness_evidence,
)
from llmgauge.core.scoring import load_result

REVIEW_SCHEMA = "llmgauge.agent_session_review.v0"
ARTIFACT_VERSION = "0.1.0"
METHOD_ID = "agent-session-review-v0"
METHOD_VERSION = "0.1.0"
REVIEW_PATH = Path("agent-harness/review/agent-session-review.json")
TEMPLATE_PATH = Path("agent-harness/review/agent-session-review.template.json")
REPORT_PATH = Path("agent-harness/review/agent-session-review.md")
MAX_BYTES = 1_048_576
MAX_DEPTH = 64
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z$")
TARGETS = frozenset(
    (
        "task_completion_evidence",
        "instruction_adherence_evidence",
        "tool_use_evidence",
        "recovery_evidence",
        "repository_change_evidence",
        "final_response_evidence",
        "attribution_boundary",
        "evidence_limitation",
    )
)
JUDGMENT_TARGETS = TARGETS - {"attribution_boundary", "evidence_limitation"}
ANNOTATION_TARGETS = {"attribution_boundary", "evidence_limitation"}
ATTRIBUTION_VALUES = frozenset(
    (
        "model_behavior",
        "harness_agent_policy",
        "tool_behavior",
        "repository_environment",
        "verifier_behavior",
        "runtime_provider",
        "operator_control",
        "missing_or_incomplete_evidence",
    )
)
REFERENCE_TYPES = frozenset(
    (
        "trajectory_event",
        "tool_lifecycle",
        "model_observation",
        "repository_observation",
        "source_terminal",
        "source_reference",
        "source_member",
    )
)


class AgentSessionReviewError(ValueError):
    pass


def _closed(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise AgentSessionReviewError(
            f"{label} must contain exactly: {', '.join(sorted(keys))}"
        )
    return value


def _string(value: Any, label: str, maximum: int = 192) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise AgentSessionReviewError(
            f"{label} must be a non-empty string of at most {maximum} characters"
        )
    return value


def _identifier(value: Any, label: str) -> str:
    value = _string(value, label)
    if not _ID.fullmatch(value):
        raise AgentSessionReviewError(f"{label} is invalid")
    return value


def _reviewer(
    value: Any, label: str, *, allow_null: bool = False
) -> Mapping[str, Any] | None:
    if value is None and allow_null:
        return None
    reviewer = _closed(value, {"reviewer_id"}, label)
    _identifier(reviewer["reviewer_id"], f"{label} ID")
    return reviewer


def _timestamp(value: Any, label: str) -> str:
    value = _string(value, label, 64)
    if not _TIMESTAMP.fullmatch(value):
        raise AgentSessionReviewError(f"{label} must be an RFC 3339 UTC timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AgentSessionReviewError(
            f"{label} must be an RFC 3339 UTC timestamp"
        ) from exc
    return value


def _unique(items: list[Any], label: str) -> None:
    if len(items) != len(set(items)):
        raise AgentSessionReviewError(f"{label} must be unique")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AgentSessionReviewError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _depth(value: Any) -> None:
    stack = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise AgentSessionReviewError("review JSON exceeds nesting depth limit")
        if isinstance(current, dict):
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)


def load_review(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except OSError as exc:
        raise AgentSessionReviewError(f"cannot read review: {exc}") from exc
    if not path.is_file() or stat.st_size > MAX_BYTES:
        raise AgentSessionReviewError(
            "review must be a regular JSON file no larger than 1048576 bytes"
        )
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AgentSessionReviewError(f"invalid review JSON: {exc}") from exc
    _depth(value)
    if not isinstance(value, dict):
        raise AgentSessionReviewError("review JSON must be an object")
    return value


def _result_root(result_dir: Path) -> Path:
    try:
        root = result_dir.resolve(strict=True)
    except OSError as exc:
        raise AgentSessionReviewError(f"cannot establish result root: {exc}") from exc
    if not root.is_dir() or result_dir.is_symlink():
        raise AgentSessionReviewError("result root must be a non-symlink directory")
    return root


def _derivative_path(result_dir: Path, relative: Path, *, create_parent: bool) -> Path:
    root = _result_root(result_dir)
    path = root / relative
    try:
        path.relative_to(root)
        harness = root / "agent-harness"
        if harness.is_symlink() or not harness.is_dir():
            raise AgentSessionReviewError(
                "agent-harness directory is not a safe directory"
            )
        review_dir = harness / "review"
        if review_dir.is_symlink():
            raise AgentSessionReviewError(
                "agent-harness review directory must not be a symlink"
            )
        if create_parent and not review_dir.exists():
            review_dir.mkdir(mode=0o700)
        if review_dir.exists() and not review_dir.is_dir():
            raise AgentSessionReviewError(
                "agent-harness review directory is not a safe directory"
            )
        if path.is_symlink():
            raise AgentSessionReviewError(
                "review derivative artifact must not be a symlink"
            )
    except OSError as exc:
        raise AgentSessionReviewError(
            f"cannot resolve contained review artifact: {exc}"
        ) from exc
    return path


def _reference_sets(evidence: AgentHarnessEvidence) -> dict[str, set[str]]:
    return {
        "trajectory_event": {item.event_id for item in evidence.trajectory},
        "tool_lifecycle": {item.lifecycle_id for item in evidence.tool_lifecycles},
        "model_observation": {
            item.observation_id for item in evidence.model_observations
        },
        "repository_observation": {
            item.observation_id for item in evidence.repository_observations
        },
        "source_terminal": {"source_terminal"},
        "source_reference": {item.reference_id for item in evidence.source_references},
        "source_member": {item.member_id for item in evidence.source_inventory},
    }


def _references(value: Any, evidence: AgentHarnessEvidence, label: str) -> None:
    if not isinstance(value, list) or not value or len(value) > 32:
        raise AgentSessionReviewError(f"{label} must contain 1 to 32 source references")
    known = _reference_sets(evidence)
    seen: set[tuple[str, str]] = set()
    for item in value:
        item = _closed(item, {"reference_type", "reference_id"}, "source reference")
        kind, ident = (
            item["reference_type"],
            _identifier(item["reference_id"], "source reference ID"),
        )
        if kind not in REFERENCE_TYPES or ident not in known[kind]:
            raise AgentSessionReviewError(
                "source reference does not identify contained evidence"
            )
        pair = (kind, ident)
        if pair in seen:
            raise AgentSessionReviewError("source references must be unique")
        seen.add(pair)


def _source(
    value: Any, evidence: AgentHarnessEvidence, result: Mapping[str, Any]
) -> None:
    value = _closed(
        value,
        {
            "evidence_schema_version",
            "evidence_contract_version",
            "evaluation_class",
            "evidence_id",
            "imported_session_id",
            "source_package_sha256",
            "source_run_fingerprint_state",
            "source_run_fingerprint",
        },
        "source",
    )
    expected = {
        "evidence_schema_version": evidence.schema_version,
        "evidence_contract_version": evidence.contract_version,
        "evaluation_class": evidence.evidence_class,
        "evidence_id": evidence.evidence_id,
        "imported_session_id": evidence.imported_session_id,
        "source_package_sha256": evidence.source_package_sha256,
    }
    for key, expected_value in expected.items():
        if value[key] != expected_value:
            raise AgentSessionReviewError(
                f"source {key} does not match owning evidence"
            )
    fingerprint = result.get("run_fingerprint")
    if fingerprint is None:
        if (
            value["source_run_fingerprint_state"] != "not_represented"
            or value["source_run_fingerprint"] is not None
        ):
            raise AgentSessionReviewError(
                "source fingerprint must be not_represented when absent"
            )
    else:
        if (
            value["source_run_fingerprint_state"] != "represented"
            or value["source_run_fingerprint"] != fingerprint
        ):
            raise AgentSessionReviewError(
                "source fingerprint does not match owning result"
            )
        _closed(
            fingerprint, {"schema_version", "algorithm", "value"}, "run fingerprint"
        )


def _basis(
    value: Any, targets: list[str], scoreability: str, evidence: AgentHarnessEvidence
) -> None:
    if not isinstance(value, list) or len(value) > 16:
        raise AgentSessionReviewError(
            "required_evidence_basis must contain at most 16 items"
        )
    if scoreability == "not_assessed":
        if value:
            raise AgentSessionReviewError("not_assessed requires empty evidence basis")
        return
    if not value:
        raise AgentSessionReviewError("assessed scoreability requires evidence basis")
    ids: list[str] = []
    states: list[str] = []
    for item in value:
        item = _closed(
            item,
            {
                "basis_id",
                "target",
                "state",
                "rationale",
                "source_references",
                "applicability_mismatch",
            },
            "evidence basis item",
        )
        ids.append(_identifier(item["basis_id"], "basis ID"))
        if item["target"] not in targets:
            raise AgentSessionReviewError("evidence basis target must be declared")
        state = item["state"]
        if state not in {
            "sufficient",
            "missing",
            "unavailable",
            "target_method_mismatch",
        }:
            raise AgentSessionReviewError("evidence basis state is invalid")
        states.append(state)
        _string(item["rationale"], "evidence basis rationale", 4096)
        _references(item["source_references"], evidence, "evidence basis")
        mismatch = item["applicability_mismatch"]
        if state == "target_method_mismatch":
            mismatch = _closed(
                mismatch,
                {"kind", "target", "method_id", "method_version"},
                "applicability_mismatch",
            )
            if mismatch != {
                "kind": "target_method_mismatch",
                "target": item["target"],
                "method_id": METHOD_ID,
                "method_version": METHOD_VERSION,
            }:
                raise AgentSessionReviewError(
                    "applicability_mismatch does not match basis target and method"
                )
        elif mismatch is not None:
            raise AgentSessionReviewError(
                "applicability_mismatch is only allowed for target_method_mismatch"
            )
    _unique(ids, "basis IDs")
    if scoreability == "scoreable" and any(state != "sufficient" for state in states):
        raise AgentSessionReviewError("scoreable requires sufficient evidence basis")
    if scoreability == "unscoreable" and not ({"missing", "unavailable"} & set(states)):
        raise AgentSessionReviewError(
            "unscoreable requires missing or unavailable evidence"
        )
    if scoreability == "not_applicable" and (
        "target_method_mismatch" not in states
        or set(states) != {"target_method_mismatch"}
    ):
        raise AgentSessionReviewError(
            "not_applicable requires only target_method_mismatch evidence"
        )


def _findings(
    value: Any, targets: list[str], state: str, evidence: AgentHarnessEvidence
) -> None:
    if not isinstance(value, list) or len(value) > 64:
        raise AgentSessionReviewError("findings must contain at most 64 items")
    ids: list[str] = []
    reviewed_targets: set[str] = set()
    for item in value:
        item = _closed(
            item,
            {
                "finding_id",
                "finding_kind",
                "target",
                "judgment_outcome",
                "rationale",
                "source_references",
                "reviewer",
                "reviewed_at_utc",
                "evidence_completeness",
                "attribution",
                "limitations",
                "reviewer_tags",
            },
            "finding",
        )
        ids.append(_identifier(item["finding_id"], "finding ID"))
        kind, target, outcome = (
            item["finding_kind"],
            item["target"],
            item["judgment_outcome"],
        )
        if target not in targets:
            raise AgentSessionReviewError("finding target must be declared")
        if kind == "judgment":
            if target not in JUDGMENT_TARGETS or outcome not in {
                "favorable",
                "mixed",
                "unfavorable",
                "not_assessable",
            }:
                raise AgentSessionReviewError(
                    "judgment finding target or outcome is invalid"
                )
        elif kind == "annotation":
            if target not in ANNOTATION_TARGETS or outcome is not None:
                raise AgentSessionReviewError(
                    "annotation finding target or outcome is invalid"
                )
        else:
            raise AgentSessionReviewError("finding kind is invalid")
        reviewed_targets.add(target)
        _string(item["rationale"], "finding rationale", 4096)
        _references(item["source_references"], evidence, "finding")
        _reviewer(item["reviewer"], "finding reviewer")
        _timestamp(item["reviewed_at_utc"], "finding reviewed_at_utc")
        if item["evidence_completeness"] not in {"complete", "partial"}:
            raise AgentSessionReviewError("finding evidence_completeness is invalid")
        limitations = item["limitations"]
        if not isinstance(limitations, list) or len(limitations) > 16:
            raise AgentSessionReviewError(
                "finding limitations must contain at most 16 items"
            )
        for limitation in limitations:
            _string(limitation, "finding limitation", 1024)
        tags = item["reviewer_tags"]
        if not isinstance(tags, list) or len(tags) > 16:
            raise AgentSessionReviewError("reviewer_tags must contain at most 16 items")
        for tag in tags:
            _string(tag, "reviewer tag", 64)
        attribution = _closed(
            item["attribution"], {"values", "state", "rationale"}, "attribution"
        )
        values = attribution["values"]
        if (
            not isinstance(values, list)
            or not values
            or len(values) > 8
            or any(v not in ATTRIBUTION_VALUES for v in values)
        ):
            raise AgentSessionReviewError("attribution values are invalid")
        _unique(values, "attribution values")
        if attribution["state"] not in {
            "observed",
            "reviewer_inference",
            "unavailable",
            "unknown",
        }:
            raise AgentSessionReviewError("attribution state is invalid")
        if attribution["state"] == "reviewer_inference":
            _string(attribution["rationale"], "attribution rationale", 4096)
        elif attribution["rationale"] is not None:
            raise AgentSessionReviewError(
                "attribution rationale is only allowed for reviewer_inference"
            )
        if outcome == "not_assessable" or target == "evidence_limitation":
            if not limitations:
                raise AgentSessionReviewError(
                    "insufficient evidence findings require limitations"
                )
    _unique(ids, "finding IDs")
    if state == "reviewed" and not set(targets) <= reviewed_targets:
        raise AgentSessionReviewError(
            "reviewed requires a judgment finding for every declared review target"
        )


def validate_review(
    review: Mapping[str, Any], result_dir: Path, *, template: bool = False
) -> None:
    result = load_result(result_dir)
    reference = result.get("agent_harness_evidence")
    if not isinstance(reference, Mapping):
        raise AgentSessionReviewError("result is not imported Agent Harness evidence")
    evidence = load_agent_harness_evidence(result_dir, reference)
    review = _closed(
        review,
        {
            "schema_version",
            "artifact_version",
            "method",
            "source",
            "reviewer",
            "reviewed_at_utc",
            "declared_review_targets",
            "scoreability",
            "review_state",
            "findings",
            "evidence_completeness",
            "limitations",
            "publication_state",
            "comparison_state",
        },
        "review",
    )
    if (
        review["schema_version"] != REVIEW_SCHEMA
        or review["artifact_version"] != ARTIFACT_VERSION
    ):
        raise AgentSessionReviewError("review schema or artifact version is invalid")
    if review["method"] != {
        "method_id": METHOD_ID,
        "method_version": METHOD_VERSION,
        "mode": "manual",
    }:
        raise AgentSessionReviewError("review method is invalid")
    _source(review["source"], evidence, result)
    targets = review["declared_review_targets"]
    if (
        not isinstance(targets, list)
        or not targets
        or len(targets) > 8
        or any(item not in TARGETS for item in targets)
    ):
        raise AgentSessionReviewError("declared_review_targets is invalid")
    _unique(targets, "declared review targets")
    scoreability = _closed(
        review["scoreability"], {"value", "required_evidence_basis"}, "scoreability"
    )["value"]
    legal = {
        "not_assessed": {"not_started"},
        "scoreable": {"awaiting_review", "in_review", "reviewed", "incomplete_review"},
        "unscoreable": {"incomplete_review", "unavailable"},
        "not_applicable": {"not_applicable"},
    }
    if scoreability not in legal or review["review_state"] not in legal[scoreability]:
        raise AgentSessionReviewError(
            "scoreability and review_state combination is invalid"
        )
    _basis(
        review["scoreability"]["required_evidence_basis"],
        targets,
        scoreability,
        evidence,
    )
    if review["evidence_completeness"] != evidence.source_completeness:
        raise AgentSessionReviewError(
            "review evidence_completeness does not match owning evidence"
        )
    if (
        review["publication_state"] != "not_assessed"
        or review["comparison_state"] != "not_assessed"
    ):
        raise AgentSessionReviewError(
            "publication_state and comparison_state must be not_assessed"
        )
    limitations = review["limitations"]
    if not isinstance(limitations, list) or len(limitations) > 32:
        raise AgentSessionReviewError(
            "document limitations must contain at most 32 items"
        )
    for limitation in limitations:
        _string(limitation, "document limitation", 1024)
    if template:
        if (
            review["reviewer"] is not None
            or review["reviewed_at_utc"] is not None
            or review["findings"]
            or scoreability != "not_assessed"
            or review["review_state"] != "not_started"
        ):
            raise AgentSessionReviewError(
                "template must use the initial unreviewed state"
            )
    else:
        _reviewer(review["reviewer"], "reviewer")
        _timestamp(review["reviewed_at_utc"], "reviewed_at_utc")
    _findings(review["findings"], targets, review["review_state"], evidence)


def build_template(result_dir: Path) -> dict[str, Any]:
    result = load_result(result_dir)
    reference = result.get("agent_harness_evidence")
    if not isinstance(reference, Mapping):
        raise AgentSessionReviewError("result is not imported Agent Harness evidence")
    evidence = load_agent_harness_evidence(result_dir, reference)
    fingerprint = result.get("run_fingerprint")
    return {
        "schema_version": REVIEW_SCHEMA,
        "artifact_version": ARTIFACT_VERSION,
        "method": {
            "method_id": METHOD_ID,
            "method_version": METHOD_VERSION,
            "mode": "manual",
        },
        "source": {
            "evidence_schema_version": evidence.schema_version,
            "evidence_contract_version": evidence.contract_version,
            "evaluation_class": evidence.evidence_class,
            "evidence_id": evidence.evidence_id,
            "imported_session_id": evidence.imported_session_id,
            "source_package_sha256": evidence.source_package_sha256,
            "source_run_fingerprint_state": "represented"
            if fingerprint
            else "not_represented",
            "source_run_fingerprint": fingerprint if fingerprint else None,
        },
        "reviewer": None,
        "reviewed_at_utc": None,
        "declared_review_targets": ["task_completion_evidence"],
        "scoreability": {"value": "not_assessed", "required_evidence_basis": []},
        "review_state": "not_started",
        "findings": [],
        "evidence_completeness": evidence.source_completeness,
        "limitations": [],
        "publication_state": "not_assessed",
        "comparison_state": "not_assessed",
    }


def _atomic_json(path: Path, data: Mapping[str, Any], *, force: bool) -> None:
    payload = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary: str | None = None
    try:
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.", dir=path.parent
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if force:
            os.replace(temporary, path)
        else:
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                raise AgentSessionReviewError(
                    f"destination already exists: {path}"
                ) from exc
            os.unlink(temporary)
        temporary = None
    except AgentSessionReviewError:
        raise
    except OSError as exc:
        raise AgentSessionReviewError(f"cannot publish review artifact: {exc}") from exc
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            except OSError as exc:
                raise AgentSessionReviewError(
                    f"cannot clean temporary review artifact: {exc}"
                ) from exc


def write_template(result_dir: Path, *, force: bool) -> Path:
    document = build_template(result_dir)
    validate_review(document, result_dir, template=True)
    path = _derivative_path(result_dir, TEMPLATE_PATH, create_parent=True)
    _atomic_json(path, document, force=force)
    return path


def apply_review(result_dir: Path, review: Mapping[str, Any], *, force: bool) -> Path:
    validate_review(review, result_dir)
    path = _derivative_path(result_dir, REVIEW_PATH, create_parent=True)
    _atomic_json(path, review, force=force)
    return path


def _fact_summary(label: str, fact: Any) -> str:
    return f"- {label} availability: `{fact.availability}`"


def _producer_version_summary(fact: Any) -> str:
    if fact.availability == "available":
        return f"- Source producer version: `{fact.value}` (availability: `available`)"
    return f"- Source producer version availability: `{fact.availability}`"


def _render_references(owner: str, references: list[Mapping[str, Any]]) -> list[str]:
    return [
        f"- {owner}: `{reference['reference_type']}:{reference['reference_id']}`"
        for reference in references
    ]


def build_report(result_dir: Path) -> str:
    result = load_result(result_dir)
    reference = result.get("agent_harness_evidence")
    if not isinstance(reference, Mapping):
        raise AgentSessionReviewError("result is not imported Agent Harness evidence")
    evidence = load_agent_harness_evidence(result_dir, reference)
    review_path = _derivative_path(result_dir, REVIEW_PATH, create_parent=False)
    review: Mapping[str, Any] | None = None
    if review_path.exists():
        review = load_review(review_path)
        validate_review(review, result_dir)

    scoreability = review["scoreability"]["value"] if review else "not_assessed"
    review_state = review["review_state"] if review else "not_started"
    reviewer_id = (
        review["reviewer"]["reviewer_id"] if review else "absent (no review metadata)"
    )
    fingerprint = result.get("run_fingerprint")
    identity_lines = [
        f"- Evidence schema/contract: `{evidence.schema_version}` / `{evidence.contract_version}`",
        f"- Evaluation class: `{evidence.evidence_class}`",
        f"- Evidence ID: `{evidence.evidence_id}`",
        f"- Imported session ID: `{evidence.imported_session_id}`",
        f"- Source package SHA-256: `{evidence.source_package_sha256}`",
        f"- Source: `{evidence.source.source_type}` / `{evidence.source.source_format}` v`{evidence.source.source_format_version}`",
        f"- Source producer: `{evidence.source.producer.producer_id}`",
        _producer_version_summary(evidence.source.producer.version),
        f"- Structural validation: `{evidence.validation_outcome}`",
    ]
    if fingerprint is None:
        identity_lines.append("- Source run fingerprint: `not_represented`")
    else:
        identity_lines.append(
            f"- Source run fingerprint: `represented` `{fingerprint['value']}`"
        )

    evidence_lines = [
        f"- Evidence completeness: `{evidence.source_completeness}`",
        f"- Source terminal outcome: `{evidence.terminal.outcome}`",
        f"- Source terminal availability: `{evidence.terminal.availability}`",
        _fact_summary("Session start", evidence.source.started_at),
        _fact_summary("Session end", evidence.source.ended_at),
        _fact_summary("Workspace observation", evidence.source.workspace_path),
        _fact_summary("Selected leaf observation", evidence.source.selected_leaf),
        "- Source verifier outcome: `unavailable` (no separate verifier outcome is represented by this evidence model).",
        "- This report omits raw trajectory, command output, and private repository content.",
    ]

    scoring_lines = [
        f"- Method: `{METHOD_ID}` `{METHOD_VERSION}` (`manual`)",
        f"- Scoreability: `{scoreability}`",
        f"- Review state: `{review_state}`",
        f"- Reviewer: `{reviewer_id}`",
        f"- Review metadata: `{'present' if review else 'absent'}`",
        "- Numeric dimensions and aggregate scores: not admitted.",
    ]
    recovery_lines = [
        "- Recovery and attribution are reviewer derivatives over cited contained evidence; no causal or recovery relationship is inferred from ordering alone."
    ]
    reference_lines: list[str] = []
    if review is None:
        scoring_lines.append(
            "- Reviewer judgment: absent explicitly because no canonical review metadata exists."
        )
    else:
        for basis in review["scoreability"]["required_evidence_basis"]:
            scoring_lines.extend(
                [
                    f"- Evidence basis `{basis['basis_id']}`: target `{basis['target']}`, state `{basis['state']}`, rationale: {basis['rationale']}",
                ]
            )
            reference_lines.extend(
                _render_references(
                    f"evidence basis `{basis['basis_id']}`", basis["source_references"]
                )
            )
        for finding in review["findings"]:
            outcome = finding["judgment_outcome"]
            scoring_lines.extend(
                [
                    f"- Finding `{finding['finding_id']}`: kind `{finding['finding_kind']}`, target `{finding['target']}`, outcome `{outcome if outcome is not None else 'not applicable'}`.",
                    f"  - Reviewer: `{finding['reviewer']['reviewer_id']}`; reviewed at `{finding['reviewed_at_utc']}`; evidence completeness: `{finding['evidence_completeness']}`.",
                    f"  - Rationale: {finding['rationale']}",
                ]
            )
            if finding["limitations"]:
                scoring_lines.append(
                    "  - Limitations: " + "; ".join(finding["limitations"])
                )
            attribution = finding["attribution"]
            recovery_lines.append(
                f"- Finding `{finding['finding_id']}` attribution: values `{', '.join(attribution['values'])}`; state `{attribution['state']}`; rationale: `{attribution['rationale'] if attribution['rationale'] is not None else 'not applicable'}`."
            )
            reference_lines.extend(
                _render_references(
                    f"finding `{finding['finding_id']}`", finding["source_references"]
                )
            )
            if finding["target"] == "recovery_evidence":
                recovery_lines.append(
                    f"- Recovery finding `{finding['finding_id']}` is limited to its cited evidence and does not establish an uncited recovery episode."
                )

    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    return "\n".join(
        [
            "# Agent-session review report",
            "",
            f"Generated by `llmgauge.agent_session_review_report` (LLMGauge {__version__}) at {now}.",
            "",
            "## 1. Report scope and claim limits",
            "This is a mutable derivative review aid over contained Agent Harness evidence. It evaluates the recorded full stack, not the model alone. It does not establish a universal or model-only quality claim, replace source outcomes, make a comparison decision, or make a publication decision.",
            "",
            "## 2. Evaluation and evidence identity",
            *identity_lines,
            "",
            "## 3. Evidence and terminal summary",
            *evidence_lines,
            "",
            "## 4. Scoring and review",
            *scoring_lines,
            "",
            "## 5. Recovery and attribution",
            *recovery_lines,
            "",
            "## 6. Comparison and publication boundary",
            f"- Comparison state: `{review['comparison_state'] if review else 'not_assessed'}`.",
            f"- Publication state: `{review['publication_state'] if review else 'not_assessed'}`.",
            "- Both remain not assessed; later separately accepted gates are required.",
            "",
            "## 7. Source references",
            *(
                reference_lines
                or [
                    "- No reviewer or evidence-basis source references; review metadata is absent."
                ]
            ),
            "",
        ]
    )


def write_report(result_dir: Path) -> Path:
    report = build_report(result_dir)
    path = _derivative_path(result_dir, REPORT_PATH, create_parent=True)
    payload = report.encode("utf-8")
    temporary: str | None = None
    try:
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.", dir=path.parent
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise AgentSessionReviewError(f"cannot publish review report: {exc}") from exc
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            except OSError as exc:
                raise AgentSessionReviewError(
                    f"cannot clean temporary review report: {exc}"
                ) from exc
    return path
