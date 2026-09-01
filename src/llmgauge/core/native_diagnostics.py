"""Exact-runtime qualification for current llama-cli native diagnostics.

The ``load_tensors:`` placement prefix and the request-final
``slot print_timing:`` timing block are admitted only for the exact
qualified llama-cli runtime recorded in
``docs/AREA4_NATIVE_LLAMA_CPP_EVIDENCE_V1.md`` (build 10449, commit
0d9ceae1e). Any other or unknown runtime fails closed: current-prefix
evidence stays unavailable while historical ``llm_load_tensors:`` and
``llama_perf`` behavior is preserved unchanged.
"""

from __future__ import annotations

from typing import Any, Mapping

QUALIFIED_LLAMA_CLI_BUILD = "10449"
QUALIFIED_LLAMA_CLI_COMMIT = "0d9ceae1e"

# Effective verbosity required to capture both admitted current sources:
# slot print_timing needs >= 3, load_tensors needs >= 4.
NATIVE_DIAGNOSTICS_VERBOSITY = 4


def current_native_diagnostics_admitted(
    backend_provenance: Mapping[str, Any] | None,
) -> bool:
    """Return True only for the exact qualified llama-cli build and commit.

    Qualification uses observed runtime provenance already collected by
    ``discover_llama_runtime_identity``. Missing, partial, or differing
    build/commit metadata never admits current-prefix evidence.
    """
    if not isinstance(backend_provenance, Mapping):
        return False
    build = backend_provenance.get("build_number")
    commit = backend_provenance.get("commit")
    if not isinstance(build, str) or not isinstance(commit, str):
        return False
    if build != QUALIFIED_LLAMA_CLI_BUILD:
        return False
    return commit.lower() == QUALIFIED_LLAMA_CLI_COMMIT


def native_diagnostics_capture_state(
    backend_provenance: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Serializable capture-policy evidence for runtime provenance."""
    admitted = current_native_diagnostics_admitted(backend_provenance)
    return {
        "current_diagnostics_admitted": admitted,
        "qualified_build": QUALIFIED_LLAMA_CLI_BUILD,
        "qualified_commit": QUALIFIED_LLAMA_CLI_COMMIT,
        "effective_verbosity": NATIVE_DIAGNOSTICS_VERBOSITY,
        "reason": (
            "exact_qualified_llama_cli_build_10449"
            if admitted
            else "runtime_not_qualified"
        ),
    }
