"""Small deterministic sample project used by the local demo."""

from __future__ import annotations

from .domain import Project
from .evaluation import evaluation_agreement


def sample_project() -> Project:
    """Return a fresh sample project for each application instance."""

    return Project(
        id="northstar-marketing-site",
        name="Northstar Marketing Site",
        client_name="Northstar Studio",
        agreement=evaluation_agreement(),
    )
