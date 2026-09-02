"""Frozen upstream-lineage qualification for current llama-cli diagnostics.

Policy: ``LLAMA_RUNTIME_LINEAGE_POLICY = UPSTREAM_IDENTITY_ALLOWLIST``
(docs/AREA4_NATIVE_LLAMA_CPP_EVIDENCE_V1.md, "Runtime lineage qualification
amendment (v2.1)"). The observed ``build_number`` plus ``commit`` pair from
runtime provenance must resolve to exactly one frozen upstream identity in
the packaged manifest (``data/llama_runtime_lineage.json``, generated
offline by ``scripts/generate_llama_runtime_lineage.py``). Placement and
slot-timing admission are independent per-record flags: builds
9538..10405 admit ``load_tensors:`` placement evidence only; builds
10406..10449 admit both placement and the request-final
``slot print_timing:`` block. Missing, malformed, ambiguous, or non-manifest
metadata fails closed: current-prefix evidence stays unavailable while
historical ``llm_load_tensors:`` and ``llama_perf`` behavior is preserved
unchanged. Lookup is offline; the manifest is frozen package data.

Trust model: the manifest checks self-reported ``--version`` metadata
against frozen known-upstream identities. It does not attest binary
contents, and a forged qualified build+commit pair is out of scope — the
same boundary as the previous exact build+commit gate it replaces.
Dirty-tree or metadata-preserving patched builds of an admitted commit are
an accepted residual defended downstream by the strict capture grammars and
the Area 4 recomputation validator.

Observed commits are resolved, never blindly truncated: a 9-character
observed SHA must equal a canonical manifest short SHA; a longer observed
SHA (10-40 characters) may match only when exactly one manifest full SHA
begins with it; a shorter observed prefix (7-8 characters) is admitted only
when it resolves to exactly one manifest record. In every case the observed
build number must equal the resolved record's build number exactly.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any, Mapping

LINEAGE_POLICY = "upstream_identity_allowlist"
LINEAGE_MANIFEST_SCHEMA = "llmgauge.llama_runtime_lineage.v1"
LINEAGE_MANIFEST_RESOURCE = ("data", "llama_runtime_lineage.json")

# Effective verbosity required to capture the admitted current sources:
# load_tensors placement needs >= 4; slot print_timing needs >= 3 and is
# therefore covered by the same setting when timing is also admitted.
NATIVE_DIAGNOSTICS_VERBOSITY = 4

_FULL_SHA_RE = re.compile(r"\A[0-9a-f]{40}\Z")
_SHORT_SHA_RE = re.compile(r"\A[0-9a-f]{9}\Z")
_HEX_COMMIT_RE = re.compile(r"\A[0-9a-f]{7,40}\Z")
_DECIMAL_BUILD_RE = re.compile(r"\A[0-9]+\Z")

REASON_MATCHED = "upstream_identity_pair_matched"
REASON_MISSING_METADATA = "missing_or_malformed_identity_metadata"
REASON_NOT_IN_MANIFEST = "identity_not_in_lineage_manifest"
REASON_AMBIGUOUS_PREFIX = "ambiguous_commit_prefix"
REASON_BUILD_MISMATCH = "build_number_does_not_match_resolved_identity"


@dataclass(frozen=True)
class LineageRecord:
    """One frozen qualified upstream identity."""

    full_commit: str
    short_commit: str
    build_number: int
    placement_admitted: bool
    slot_timing_admitted: bool


class LineageManifest:
    """Frozen upstream identity set with conservative commit resolution."""

    def __init__(self, records: list[LineageRecord]) -> None:
        self.records = tuple(records)
        self._by_short: dict[str, LineageRecord] = {}
        for record in self.records:
            if record.short_commit in self._by_short:
                raise ValueError(f"duplicate canonical short SHA {record.short_commit}")
            self._by_short[record.short_commit] = record

    @property
    def placement_count(self) -> int:
        return sum(1 for record in self.records if record.placement_admitted)

    @property
    def slot_timing_count(self) -> int:
        return sum(1 for record in self.records if record.slot_timing_admitted)

    def resolve(
        self, commit: str, build_number: str
    ) -> tuple[LineageRecord | None, str]:
        """Resolve an observed commit/build pair to exactly one record.

        Fail-closed: returns ``(None, reason)`` for malformed metadata,
        unknown commits, ambiguous prefixes, and any build-number that does
        not equal the resolved record's build number.
        """
        normalized = commit.lower()
        if not _HEX_COMMIT_RE.fullmatch(normalized):
            return None, REASON_MISSING_METADATA
        if not _DECIMAL_BUILD_RE.fullmatch(build_number):
            return None, REASON_MISSING_METADATA
        if len(normalized) == 9:
            # Canonical reported form: exact key equality (never a prefix
            # scan; every manifest short SHA is a distinct 9-character key).
            record = self._by_short.get(normalized)
            candidates = [record] if record is not None else []
        else:
            # 7-8 characters resolve only when unique; 10-40 characters are
            # extended/full SHA representations matched against full SHAs.
            candidates = [
                candidate
                for candidate in self.records
                if candidate.full_commit.startswith(normalized)
            ]
        if not candidates:
            return None, REASON_NOT_IN_MANIFEST
        if len(candidates) > 1:
            return None, REASON_AMBIGUOUS_PREFIX
        resolved = candidates[0]
        if str(resolved.build_number) != build_number:
            return None, REASON_BUILD_MISMATCH
        return resolved, REASON_MATCHED


def parse_lineage_manifest(data: Mapping[str, Any]) -> LineageManifest:
    """Validate and index a lineage manifest document (fail closed)."""
    if not isinstance(data, Mapping):
        raise ValueError("lineage manifest must be an object")
    if data.get("schema_version") != LINEAGE_MANIFEST_SCHEMA:
        raise ValueError("lineage manifest schema_version is invalid")
    raw_records = data.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        raise ValueError("lineage manifest records must be a non-empty list")
    records: list[LineageRecord] = []
    for item in raw_records:
        if not isinstance(item, Mapping):
            raise ValueError("lineage manifest record must be an object")
        full = item.get("full_commit")
        short = item.get("short_commit")
        build = item.get("build_number")
        placement = item.get("placement_admitted")
        timing = item.get("slot_timing_admitted")
        if (
            not isinstance(full, str)
            or _FULL_SHA_RE.fullmatch(full) is None
            or not isinstance(short, str)
            or _SHORT_SHA_RE.fullmatch(short) is None
            or not full.startswith(short)
            or not isinstance(build, int)
            or isinstance(build, bool)
            or not isinstance(placement, bool)
            or not isinstance(timing, bool)
        ):
            raise ValueError("lineage manifest record fields are invalid")
        records.append(
            LineageRecord(
                full_commit=full,
                short_commit=short,
                build_number=build,
                placement_admitted=placement,
                slot_timing_admitted=timing,
            )
        )
    builds = [record.build_number for record in records]
    if len(set(builds)) != len(builds):
        raise ValueError("lineage manifest has duplicate build numbers")
    if builds != sorted(builds):
        raise ValueError("lineage manifest build numbers are not monotonic")
    return LineageManifest(records)


@lru_cache(maxsize=1)
def packaged_lineage_manifest() -> LineageManifest:
    """Load the frozen packaged manifest through package resources (offline)."""
    text = (
        resources.files("llmgauge")
        .joinpath(*LINEAGE_MANIFEST_RESOURCE)
        .read_text(encoding="utf-8")
    )
    return parse_lineage_manifest(json.loads(text))


@dataclass(frozen=True)
class NativeLineageQualification:
    """Independent per-source admission result for one observed runtime."""

    matched: bool
    identity: Mapping[str, Any] | None
    placement_admitted: bool
    slot_timing_admitted: bool
    reason: str
    observed_build: str | None
    observed_commit: str | None


def qualify_current_native_diagnostics(
    backend_provenance: Mapping[str, Any] | None,
    *,
    manifest: LineageManifest | None = None,
) -> NativeLineageQualification:
    """Qualify observed runtime provenance against the frozen lineage manifest.

    Qualification uses observed runtime provenance already collected by
    ``discover_llama_runtime_identity``. Missing, partial, malformed, or
    non-manifest build/commit metadata never admits current-prefix evidence,
    and a placement-only identity never implies slot-timing admission.
    """
    active = packaged_lineage_manifest() if manifest is None else manifest
    build = None
    commit = None
    if isinstance(backend_provenance, Mapping):
        raw_build = backend_provenance.get("build_number")
        raw_commit = backend_provenance.get("commit")
        if isinstance(raw_build, str):
            build = raw_build
        if isinstance(raw_commit, str):
            commit = raw_commit
    if build is None or commit is None:
        return NativeLineageQualification(
            matched=False,
            identity=None,
            placement_admitted=False,
            slot_timing_admitted=False,
            reason=REASON_MISSING_METADATA,
            observed_build=build,
            observed_commit=commit,
        )
    record, reason = active.resolve(commit, build)
    if record is None:
        return NativeLineageQualification(
            matched=False,
            identity=None,
            placement_admitted=False,
            slot_timing_admitted=False,
            reason=reason,
            observed_build=build,
            observed_commit=commit,
        )
    return NativeLineageQualification(
        matched=True,
        identity={
            "short_commit": record.short_commit,
            "full_commit": record.full_commit,
            "build_number": record.build_number,
            "placement_admitted": record.placement_admitted,
            "slot_timing_admitted": record.slot_timing_admitted,
        },
        placement_admitted=record.placement_admitted,
        slot_timing_admitted=record.slot_timing_admitted,
        reason=reason,
        observed_build=build,
        observed_commit=commit,
    )


def native_diagnostics_capture_state(
    backend_provenance: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Serializable capture-policy evidence for runtime provenance.

    Records the bounded lineage facts needed to explain admission: policy,
    identity match, the matched canonical short commit, the observed build,
    and the independent per-source flags. Never embeds the manifest itself
    or any local checkout path.
    """
    qualification = qualify_current_native_diagnostics(backend_provenance)
    matched_commit = None
    if qualification.matched and qualification.identity is not None:
        matched_commit = str(qualification.identity["short_commit"])
    return {
        "lineage_policy": LINEAGE_POLICY,
        "lineage_identity_matched": qualification.matched,
        "lineage_matched_commit": matched_commit,
        "lineage_observed_build": qualification.observed_build,
        "placement_admitted": qualification.placement_admitted,
        "slot_timing_admitted": qualification.slot_timing_admitted,
        "effective_verbosity": (
            NATIVE_DIAGNOSTICS_VERBOSITY if qualification.placement_admitted else None
        ),
        "reason": qualification.reason,
    }
