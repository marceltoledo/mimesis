"""Deployment wrapper for BC-01 Azure Function app."""
# Deployed build: __BUILD_ID__

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mimesis.video_discovery.function_app import app  # noqa: E402,F401
