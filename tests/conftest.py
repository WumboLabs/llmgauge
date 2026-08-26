from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))


def pytest_configure(config) -> None:
    os.environ.setdefault("NO_COLOR", "1")
