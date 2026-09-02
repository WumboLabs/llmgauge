#!/usr/bin/env python3
"""Generate the frozen llama.cpp runtime-lineage identity manifest.

The manifest is the packaged authority for
``LLAMA_RUNTIME_LINEAGE_POLICY = UPSTREAM_IDENTITY_ALLOWLIST`` (see
``docs/AREA4_NATIVE_LLAMA_CPP_EVIDENCE_V1.md``). It enumerates exactly the
accepted upstream ``ggml-org/llama.cpp`` identity intervals between the
semantic qualification floors and the frozen ceiling, one record per commit:
``full_commit``, ``short_commit`` (canonical 9-character reported form),
``build_number``, ``placement_admitted``, ``slot_timing_admitted``.

Safety properties:

- the floors and ceiling are hard-coded contract constants; the enumeration
  range is bounded by them, so a newer repository HEAD can never silently
  extend admission (a ceiling change requires a new semantic qualification
  milestone first);
- the source repository must be a clone of ``ggml-org/llama.cpp`` whose
  history contains the exact contract commit identities;
- output is deterministic (fixed field order, fixed provenance, LF newlines),
  so ``--check`` can compare bytes against the tracked manifest;
- any discrepancy exits nonzero and writes nothing.

This script is a build-time tool only. Runtime LLMGauge never invokes it and
never requires a llama.cpp checkout.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

GENERATOR_VERSION = "llmgauge.llama_runtime_lineage.v1"

# Frozen contract boundaries (docs/AREA4_NATIVE_LLAMA_CPP_EVIDENCE_V1.md,
# "Runtime lineage qualification amendment (v2.1)"). These are the authority;
# they are never derived from the inspected repository.
UPSTREAM_REPOSITORY = "ggml-org/llama.cpp"
PLACEMENT_FLOOR_SHORT = "5343f4502"
TIMING_FLOOR_SHORT = "decaf508b"
CEILING_SHORT = "0d9ceae1e"
EXPECTED_FULL_COMMITS = {
    PLACEMENT_FLOOR_SHORT: "5343f4502ab5273d7cef85012af020cad0182376",
    TIMING_FLOOR_SHORT: "decaf508bb9ef683c93f58d320b6d6faef507895",
    CEILING_SHORT: "0d9ceae1e38291035605613ab41a8f5e693d6fcd",
}
EXPECTED_PLACEMENT_COUNT = 912
EXPECTED_TIMING_COUNT = 44
EXPECTED_FIRST_BUILD = 9538
EXPECTED_CEILING_BUILD = 10449
EXPECTED_TIMING_FIRST_BUILD = 10406
# Date the semantic qualification contract was accepted (not the wall-clock
# generation date); keeps the artifact deterministic and audit-bound.
QUALIFICATION_DATE = "2026-09-01"
SHORT_SHA_LENGTH = 9


class GenerationError(RuntimeError):
    """Raised for any contract discrepancy; the manifest is not written."""


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()
        raise GenerationError(
            f"git {' '.join(args)} failed: {detail[0] if detail else completed.returncode}"
        )
    return completed.stdout


def _verify_repository(repo: Path) -> None:
    if not (repo / ".git").exists() and not (repo / "HEAD").exists():
        raise GenerationError(f"{repo} is not a git repository")
    remotes = _git(repo, "remote", "-v").splitlines()
    if not any(UPSTREAM_REPOSITORY in line for line in remotes):
        raise GenerationError(
            f"{repo} has no remote referencing {UPSTREAM_REPOSITORY}; "
            "the manifest may only be generated from a verified upstream clone"
        )


def _resolve_full(repo: Path, short: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "-q", f"{short}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    full = completed.stdout.strip()
    if completed.returncode != 0 or not full:
        raise GenerationError(f"commit {short} is not present in {repo}")
    expected = EXPECTED_FULL_COMMITS.get(short)
    if expected is not None and full != expected:
        raise GenerationError(
            f"commit {short} resolves to {full}, not the contract full SHA {expected}"
        )
    return full


def _count(repo: Path, *rev_args: str) -> int:
    return int(_git(repo, "rev-list", "--count", *rev_args).strip())


def _interval(
    repo: Path, floor_full: str, ceiling_full: str, label: str
) -> list[tuple[str, str]]:
    """Return inclusive floor..ceiling (full, short) pairs, oldest first.

    ``%h`` uses the same automatic-abbreviation algorithm as
    ``git rev-parse --short``; the anchor cross-check in ``build_manifest``
    proves agreement for the contract commits.
    """
    if _count(repo, "--first-parent", f"{floor_full}~1..{ceiling_full}") != _count(
        repo,
        f"{floor_full}~1..{ceiling_full}",
    ):
        raise GenerationError(f"{label} interval is not first-parent linear")
    merges = _count(repo, "--merges", f"{floor_full}~1..{ceiling_full}")
    if merges != 0:
        raise GenerationError(f"{label} interval contains {merges} merge commits")
    lines = _git(
        repo,
        "log",
        "--reverse",
        "--format=%H %h",
        f"{floor_full}~1..{ceiling_full}",
    ).splitlines()
    pairs: list[tuple[str, str]] = []
    for line in lines:
        parts = line.split()
        if len(parts) != 2:
            raise GenerationError(f"{label} interval enumeration produced {line!r}")
        pairs.append((parts[0], parts[1]))
    return pairs


def _short(repo: Path, full: str) -> str:
    return _git(repo, "rev-parse", "--short", full).strip()


def build_manifest(repo: Path) -> dict[str, Any]:
    """Enumerate the frozen intervals and return the validated manifest."""
    _verify_repository(repo)
    placement_floor = _resolve_full(repo, PLACEMENT_FLOOR_SHORT)
    timing_floor = _resolve_full(repo, TIMING_FLOOR_SHORT)
    ceiling = _resolve_full(repo, CEILING_SHORT)
    if not _count(repo, f"{placement_floor}..{ceiling}"):
        raise GenerationError("placement floor is not an ancestor of the ceiling")
    if not _count(repo, f"{timing_floor}..{ceiling}"):
        raise GenerationError("timing floor is not an ancestor of the ceiling")

    placement_pairs = _interval(repo, placement_floor, ceiling, "placement")
    timing_pairs = _interval(repo, timing_floor, ceiling, "timing")
    if len(placement_pairs) != EXPECTED_PLACEMENT_COUNT:
        raise GenerationError(
            f"placement interval has {len(placement_pairs)} commits, "
            f"expected {EXPECTED_PLACEMENT_COUNT}"
        )
    if len(timing_pairs) != EXPECTED_TIMING_COUNT:
        raise GenerationError(
            f"timing interval has {len(timing_pairs)} commits, "
            f"expected {EXPECTED_TIMING_COUNT}"
        )
    if not {full for full, _ in timing_pairs} <= {full for full, _ in placement_pairs}:
        raise GenerationError(
            "timing identities are not a subset of placement identities"
        )

    floor_count = _count(repo, placement_floor)
    ceiling_count = _count(repo, ceiling)
    timing_floor_count = _count(repo, timing_floor)
    if (floor_count, ceiling_count, timing_floor_count) != (
        EXPECTED_FIRST_BUILD,
        EXPECTED_CEILING_BUILD,
        EXPECTED_TIMING_FIRST_BUILD,
    ):
        raise GenerationError(
            "build-number anchors disagree with the contract: "
            f"floor={floor_count} ceiling={ceiling_count} timing={timing_floor_count}"
        )

    timing_set = {full for full, _ in timing_pairs}
    records: list[dict[str, Any]] = []
    for index, (full, short) in enumerate(placement_pairs):
        if _short(repo, full) != short:
            raise GenerationError(
                f"git rev-parse --short disagrees with log %h for {full}"
            )
        # Linearity (zero merges, first-parent equality) plus anchor equality
        # makes rev-list --count a bijection: the oldest interval commit has
        # the floor count and each later commit increments by exactly one.
        build_number = floor_count + index
        if len(short) != SHORT_SHA_LENGTH or len(full) != 40:
            raise GenerationError(
                f"commit {full} reported form {short!r} is not the canonical "
                f"{SHORT_SHA_LENGTH}-character abbreviation of a 40-character SHA"
            )
        if not full.startswith(short):
            raise GenerationError(
                f"short SHA {short} is not a prefix of full SHA {full}"
            )
        records.append(
            {
                "full_commit": full,
                "short_commit": short,
                "build_number": build_number,
                "placement_admitted": True,
                "slot_timing_admitted": full in timing_set,
            }
        )

    _validate_records(records)
    return {
        "schema_version": GENERATOR_VERSION,
        "policy": "upstream_identity_allowlist",
        "provenance": {
            "upstream_repository": UPSTREAM_REPOSITORY,
            "placement_floor": {
                "short": PLACEMENT_FLOOR_SHORT,
                "full": placement_floor,
            },
            "timing_floor": {"short": TIMING_FLOOR_SHORT, "full": timing_floor},
            "ceiling": {"short": CEILING_SHORT, "full": ceiling},
            "placement_record_count": EXPECTED_PLACEMENT_COUNT,
            "slot_timing_record_count": EXPECTED_TIMING_COUNT,
            "build_range": [EXPECTED_FIRST_BUILD, EXPECTED_CEILING_BUILD],
            "qualification_date": QUALIFICATION_DATE,
            "generator": GENERATOR_VERSION,
            "generation_procedure": (
                "git rev-list --reverse <placement_floor>~1..<ceiling>; "
                "per-commit git rev-parse --short and rev-list --count; "
                "timing flag from the inclusive <timing_floor>.. ceiling interval"
            ),
        },
        "records": records,
    }


def _validate_records(records: list[dict[str, Any]]) -> None:
    fulls = [record["full_commit"] for record in records]
    shorts = [record["short_commit"] for record in records]
    builds = [record["build_number"] for record in records]
    if len(set(fulls)) != len(fulls):
        raise GenerationError("duplicate full SHAs in manifest")
    if len(set(shorts)) != len(shorts):
        raise GenerationError("duplicate canonical short SHAs in manifest")
    if len(set(builds)) != len(builds):
        raise GenerationError("duplicate build numbers in manifest")
    if builds != sorted(builds) or any(
        second - first != 1 for first, second in zip(builds, builds[1:], strict=False)
    ):
        raise GenerationError("build numbers are not strictly increasing by one")
    placement = [record for record in records if record["placement_admitted"]]
    timing = [record for record in records if record["slot_timing_admitted"]]
    if len(placement) != EXPECTED_PLACEMENT_COUNT:
        raise GenerationError(
            f"{len(placement)} placement records, expected {EXPECTED_PLACEMENT_COUNT}"
        )
    if len(timing) != EXPECTED_TIMING_COUNT:
        raise GenerationError(
            f"{len(timing)} timing records, expected {EXPECTED_TIMING_COUNT}"
        )
    if not {record["full_commit"] for record in timing} <= {
        record["full_commit"] for record in placement
    }:
        raise GenerationError("timing records are not a subset of placement records")
    if records[0]["short_commit"] != PLACEMENT_FLOOR_SHORT:
        raise GenerationError("placement floor anchor mismatch")
    if records[-1]["short_commit"] != CEILING_SHORT:
        raise GenerationError("ceiling anchor mismatch")
    if timing and timing[0]["short_commit"] != TIMING_FLOOR_SHORT:
        raise GenerationError("timing floor anchor mismatch")


def serialize(manifest: dict[str, Any]) -> bytes:
    return (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo",
        type=Path,
        required=True,
        help="path to a verified local upstream llama.cpp git clone (read-only)",
    )
    parser.add_argument("--out", type=Path, required=True, help="manifest output path")
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare the generated bytes against --out without writing; nonzero on mismatch",
    )
    args = parser.parse_args(argv)
    try:
        data = serialize(build_manifest(args.repo))
    except GenerationError as exc:
        print(f"lineage manifest generation failed: {exc}", file=sys.stderr)
        return 1
    if args.check:
        try:
            tracked = args.out.read_bytes()
        except OSError as exc:
            print(f"cannot read tracked manifest {args.out}: {exc}", file=sys.stderr)
            return 1
        if tracked != data:
            print(f"generated manifest differs from {args.out}", file=sys.stderr)
            return 1
        print(f"manifest reproduces byte-for-byte: {args.out}")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    print(f"wrote {args.out} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
