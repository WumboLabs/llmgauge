from __future__ import annotations

from typing import Any, Mapping

import typer
from rich.table import Table

from llmgauge.cli_common import console
from llmgauge.core.sampling_profiles import (
    SamplingProfileError,
    builtin_sampling_profile_ids,
    resolve_sampling_profile,
)

profiles_app = typer.Typer(
    name="profiles",
    help=(
        "Discover and inspect built-in reasoning/sampling profiles "
        "usable with 'run --sampling-profile'."
    ),
    no_args_is_help=True,
)

_RUNTIME_DEFAULT_LABEL = "runtime default"

_VENDOR_QUALIFICATION_DOC_URL = (
    "https://github.com/WumboLabs/llmgauge/blob/main/"
    "docs/VENDOR_ALIGNED_SAMPLING_PROFILES.md"
)


def _builtin_profile(profile_id: str) -> dict[str, Any]:
    """Resolve one built-in profile through the shared ``--sampling-profile`` resolver."""
    try:
        # An empty config restricts resolution to the built-in registry while
        # reusing the authoritative resolver semantics unchanged.
        resolved = resolve_sampling_profile({}, profile_id)
    except SamplingProfileError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if resolved is None:  # unreachable for a provided profile_id
        raise typer.BadParameter("No built-in profile selected.")
    return resolved


def _ordered_builtin_profiles() -> list[Mapping[str, Any]]:
    profiles = [
        _builtin_profile(profile_id) for profile_id in builtin_sampling_profile_ids()
    ]
    return sorted(
        profiles,
        key=lambda profile: (
            profile["profile_kind"] != "controlled",
            str(profile["profile_kind"]),
            str(profile["profile_id"]),
        ),
    )


def _setting_label(value: Any) -> str:
    if value is None:
        return _RUNTIME_DEFAULT_LABEL
    return str(value)


@profiles_app.command("list")
def profiles_list() -> None:
    """List built-in reasoning/sampling profiles."""
    table = Table(title="Reasoning/Sampling Profiles", expand=True)
    table.add_column("Profile ID", no_wrap=True)
    table.add_column("Version", no_wrap=True)
    table.add_column("Kind", no_wrap=True)
    table.add_column("Source", no_wrap=True)

    for profile in _ordered_builtin_profiles():
        table.add_row(
            str(profile["profile_id"]),
            str(profile["profile_version"]),
            str(profile["profile_kind"]),
            str(profile["source"]),
        )

    console.print(table)


@profiles_app.command("show")
def profiles_show(
    profile_id: str = typer.Argument(
        ...,
        metavar="PROFILE_ID",
        help="Built-in profile ID to inspect (see 'llmgauge profiles list').",
    ),
) -> None:
    """Show one built-in profile's exact requested controls and provenance."""
    profile = _builtin_profile(profile_id)
    settings: Mapping[str, Any] = profile["settings"]

    console.print(f"Profile ID: [bold]{profile['profile_id']}[/bold]")
    console.print(f"Version: {profile['profile_version']}")
    console.print(f"Kind: {profile['profile_kind']}")
    console.print(f"Source: {profile['source']}")
    console.print("Content hash (SHA-256):")
    console.print(f"  {profile['canonical_settings_sha256']}")
    console.print()
    console.print("Requested settings:")
    for key, value in settings.items():
        console.print(f"  {key}: {_setting_label(value)}")
    console.print()
    console.print(
        "Claim boundary: this profile records requested controls; it does not "
        "prove semantic model reasoning or runtime behavior."
    )
    if profile["profile_kind"] == "vendor_aligned":
        console.print(
            "Vendor-aligned means these controls are derived from documented "
            "vendor settings. Alignment is operator-declared rather than "
            "verified: it is not vendor endorsement and does not prove "
            "equivalent behavior to vendor-hosted inference."
        )
        console.print(f"Qualification sources: {_VENDOR_QUALIFICATION_DOC_URL}")
