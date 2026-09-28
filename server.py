"""
Unified Server Launcher for Sewa Setu Credential Verification Engine.
Runs the FastAPI Backend (backend/main.py) and serves the Web Frontend (frontend/).
Run with: python server.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.main import app, start_server

if __name__ == "__main__":
    start_server(host="127.0.0.1", port=8000, reload=False)
