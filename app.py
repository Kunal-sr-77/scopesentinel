"""ScopeSentinel development entry point."""

from __future__ import annotations

import os

from scopesentinel.web import create_app


if __name__ == "__main__":
    create_app().run(
        host="0.0.0.0",
        port=int(os.environ.get("SCOPESENTINEL_PORT", "8000")),
    )
