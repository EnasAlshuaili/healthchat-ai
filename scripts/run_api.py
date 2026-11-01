"""Run the mock-only QueryMate API locally (D-19, docs/API_CONTRACT.md).

Usage (from the project root):
    .venv\\Scripts\\python.exe scripts\\run_api.py

Binds to 127.0.0.1 only. The access log is off because Uvicorn's access log
includes client addresses and query strings.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

HOST = "127.0.0.1"
PORT = 8000
ACCESS_LOG = False


def main() -> None:
    import uvicorn

    from querymate.api.main import app  # noqa: E402

    uvicorn.run(app, host=HOST, port=PORT, access_log=ACCESS_LOG)


if __name__ == "__main__":
    main()
