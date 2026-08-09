"""
Thin process entrypoint, kept at the repo root so `python main.py` and
`uvicorn main:app` both work without callers needing to know the package
layout. The actual application is assembled in app/main.py.
"""

from __future__ import annotations

import uvicorn

from app.core.config import settings
from app.main import app  # noqa: F401  (re-exported for `uvicorn main:app`)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, reload=settings.is_dev, log_level="info")
