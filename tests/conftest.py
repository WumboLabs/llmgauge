from __future__ import annotations

import os


def pytest_configure(config) -> None:
    os.environ.setdefault("NO_COLOR", "1")