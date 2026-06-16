from pathlib import Path
from typing import Any

import yaml


def load_suite(suite_dir: Path) -> dict[str, Any]:
    suite_file = suite_dir / "suite.yaml"
    if not suite_file.exists():
        raise FileNotFoundError(f"Missing suite file: {suite_file}")

    with suite_file.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"Suite file did not parse as a mapping: {suite_file}")

    return data


def validate_suite(suite_dir: Path) -> list[str]:
    errors: list[str] = []

    try:
        suite = load_suite(suite_dir)
    except Exception as exc:
        return [str(exc)]

    required_fields = [
        "schema_version",
        "suite_id",
        "suite_version",
        "title",
        "prompts",
    ]

    for field in required_fields:
        if field not in suite:
            errors.append(f"Missing required field: {field}")

    prompts = suite.get("prompts", [])
    if not isinstance(prompts, list):
        errors.append("Field 'prompts' must be a list")
        return errors

    seen_ids: set[str] = set()

    for index, prompt in enumerate(prompts):
        if not isinstance(prompt, dict):
            errors.append(f"Prompt entry #{index} is not a mapping")
            continue

        prompt_id = prompt.get("id")
        prompt_file = prompt.get("file")

        if not prompt_id:
            errors.append(f"Prompt entry #{index} is missing id")
        elif prompt_id in seen_ids:
            errors.append(f"Duplicate prompt id: {prompt_id}")
        else:
            seen_ids.add(prompt_id)

        if not prompt_file:
            errors.append(f"Prompt entry #{index} is missing file")
        else:
            path = suite_dir / prompt_file
            if not path.exists():
                errors.append(f"Prompt file does not exist: {path}")

    return errors
