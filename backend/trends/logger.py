"""
Logger setup for trends module.
Re-exports the common logger from backend root.
"""

import sys
from pathlib import Path

# Add backend root to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from logger import get_logger  # noqa: E402

__all__ = ["get_logger"]

