"""Minimal web shell; feature routes are added after Step 1 is committed."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify

from .store import JsonHistoryStore


def create_app(store: JsonHistoryStore | None = None) -> Flask:
    app = Flask(__name__)
    app.config["HISTORY_STORE"] = store or JsonHistoryStore(
        Path(os.environ.get("SCOPESENTINEL_HISTORY", "data/history.json"))
    )

    @app.get("/health")
    def health() -> tuple[dict[str, str], int]:
        return {"status": "ok", "service": "scopesentinel"}, 200

    @app.get("/")
    def placeholder() -> str:
        return "<h1>ScopeSentinel</h1><p>Evidence-backed scope review is initializing.</p>"

    @app.get("/api/history")
    def history() -> tuple[object, int]:
        records = app.config["HISTORY_STORE"].list_records()
        return jsonify([record.request.id for record in records]), 200

    return app
