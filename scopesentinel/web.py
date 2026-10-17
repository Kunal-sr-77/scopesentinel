"""Flask routes for the local ScopeSentinel MVP workflow."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

from .agreement import parse_clause
from .analysis import analyze_request
from .domain import (
    Agreement,
    ApprovalStatus,
    ClauseType,
    HistoryRecord,
    Project,
    Request as ClientRequest,
    to_dict,
)
from .samples import sample_project
from .store import JsonHistoryStore
from .view_models import (
    AnalysisViewModel,
    DashboardViewModel,
    EvidenceViewModel,
    PipelineStageViewModel,
)


_CLASSIFICATION_LABELS = {
    "IN_SCOPE": "In scope",
    "POTENTIALLY_OUT_OF_SCOPE": "Potentially out of scope",
    "NEEDS_CLARIFICATION": "Needs clarification",
}


def _request_heading(text: str, word_limit: int = 8) -> str:
    """Create a concise page heading from the original client wording."""

    words = text.split()
    if not words:
        return "Request review"
    heading = " ".join(words[:word_limit]).rstrip(".,!?;:")
    return f"{heading}…" if len(words) > word_limit else heading


def create_app(store: JsonHistoryStore | None = None) -> Flask:
    app = Flask(__name__)
    app.config["HISTORY_STORE"] = store or JsonHistoryStore(
        Path(os.environ.get("SCOPESENTINEL_HISTORY", "data/history.json"))
    )
    app.config["PROJECT"] = sample_project()

    def project() -> Project:
        return app.config["PROJECT"]

    def history_store() -> JsonHistoryStore:
        return app.config["HISTORY_STORE"]

    def navigation() -> dict[str, str]:
        return {
            "dashboard_url": url_for("dashboard"),
            "new_request_url": url_for("new_request"),
            "history_url": url_for("history_page"),
            "setup_url": url_for("setup"),
            "analysis_url": "/requests/",
            "history_notice": history_store().last_notice,
        }

    def view_model(record: HistoryRecord) -> AnalysisViewModel:
        result = record.result
        trace = result.trace
        evidence = tuple(
            EvidenceViewModel(
                clause_id=hit.clause_id,
                clause_type=hit.clause_type.value,
                source_text=hit.source_text,
                relation=hit.relation,
                matched_concepts=hit.matched_concepts,
                matched_constraints=hit.matched_constraints,
            )
            for hit in trace.retrieve.hits
        )
        stages = tuple(
            PipelineStageViewModel(
                key=key,
                label=label,
                status="complete",
                output=to_dict(output) if output is not None else {},
            )
            for key, label, output in (
                ("parse", "Parse", trace.parse),
                ("retrieve", "Retrieve", trace.retrieve),
                ("classify", "Classify", trace.classify),
                ("draft", "Draft", trace.draft),
            )
        )
        classification = result.classification
        return AnalysisViewModel(
            request_id=record.request.id,
            project_name=project().name,
            client_request=record.request.text,
            request_heading=_request_heading(record.request.text),
            classification=classification,
            classification_label=_CLASSIFICATION_LABELS[classification.value],
            rationale=tuple(trace.classify.rationale),
            decision_rules=tuple(trace.classify.decision_rules),
            uncertainty_tags=tuple(result.uncertainty_reasons),
            scheduling_flag=result.scheduling_flag,
            evidence=evidence,
            draft=result.draft,
            pipeline=stages,
            approval_status=record.approval_status,
            can_approve=record.approval_status is ApprovalStatus.PENDING_REVIEW,
        )

    def dashboard_model() -> DashboardViewModel:
        records = history_store().list_records()
        return DashboardViewModel(
            project_name=project().name,
            client_name=project().client_name,
            pending_review_count=sum(
                record.approval_status is ApprovalStatus.PENDING_REVIEW for record in records
            ),
            history=tuple(view_model(record) for record in reversed(records)),
        )

    def setup_values() -> dict[str, str]:
        agreement = project().agreement
        groups = {
            "deliverables": ClauseType.DELIVERABLE,
            "exclusions": ClauseType.EXCLUSION,
            "limits": ClauseType.LIMIT,
            "deadlines": ClauseType.DEADLINE,
            "pricing": ClauseType.RATE,
        }
        effort_hours = agreement.pricing_rules.get("effort_hours", {})
        values = {
            key: "\n".join(
                clause.source_text for clause in agreement.clauses if clause.type is clause_type
            )
            for key, clause_type in groups.items()
        }
        values.update(
            {
                "project_name": project().name,
                "client_name": project().client_name,
                "pages_delivered": str(agreement.current_usage.get("marketing_page", "")),
                "hourly_rate": str(agreement.pricing_rules.get("hourly_rate", "")),
                "page_effort": str(effort_hours.get("additional_marketing_page", "")),
            }
        )
        return values

    def clauses_from_form(form: object) -> list:
        fields = (
            ("deliverables", ClauseType.DELIVERABLE),
            ("exclusions", ClauseType.EXCLUSION),
            ("limits", ClauseType.LIMIT),
            ("deadlines", ClauseType.DEADLINE),
            ("pricing", ClauseType.RATE),
        )
        clauses = []
        for field_name, expected_type in fields:
            source = str(form.get(field_name, ""))
            for index, line in enumerate((line.strip() for line in source.splitlines()), start=1):
                if not line:
                    continue
                parsed = parse_clause(line, clause_id=f"{field_name}-{index}")
                clauses.append(replace(parsed, type=expected_type))
        return clauses

    def optional_number(value: str) -> float | None:
        return None if not value.strip() else float(value)

    @app.get("/health")
    def health() -> tuple[dict[str, str], int]:
        return {"status": "ok", "service": "scopesentinel"}, 200

    @app.get("/")
    def dashboard() -> str:
        return render_template("dashboard.html", dashboard=dashboard_model(), **navigation())

    @app.route("/setup", methods=["GET", "POST"])
    def setup() -> str:
        if request.method == "POST":
            form = request.form
            try:
                pages_delivered = optional_number(form.get("pages_delivered", "0")) or 0
                hourly_rate = optional_number(form.get("hourly_rate", ""))
                page_effort = optional_number(form.get("page_effort", ""))
            except ValueError:
                return render_template(
                    "project_setup.html",
                    values=request.form,
                    error="Usage, rate, and effort values must be numbers.",
                    **navigation(),
                ), 400
            app.config["PROJECT"] = Project(
                id=project().id,
                name=form.get("project_name", "Untitled project").strip() or "Untitled project",
                client_name=form.get("client_name", "Client account").strip() or "Client account",
                agreement=Agreement(
                    clauses=clauses_from_form(form),
                    current_usage={"marketing_page": pages_delivered},
                    pricing_rules={
                        "hourly_rate": hourly_rate,
                        "effort_hours": {
                            "additional_marketing_page": page_effort,
                        },
                    },
                ),
            )
            return redirect(url_for("dashboard"))
        return render_template("project_setup.html", values=setup_values(), **navigation())

    @app.get("/requests/new")
    def new_request() -> str:
        return render_template(
            "request_form.html",
            project_id=project().id,
            project_name=project().name,
            client_name=project().client_name,
            **navigation(),
        )

    @app.post("/requests/new")
    def analyze_new_request() -> object:
        text = request.form.get("request_text", "").strip()
        if not text:
            return render_template(
                "request_form.html",
                project_id=project().id,
                project_name=project().name,
                client_name=project().client_name,
                request_text=text,
                error="Paste a client request before analyzing it.",
                **navigation(),
            ), 400
        request_id = f"request-{uuid4().hex[:10]}"
        client_request = ClientRequest(id=request_id, project_id=project().id, text=text)
        result = analyze_request(client_request, project())
        history_store().save(HistoryRecord(request=client_request, result=result))
        return redirect(url_for("request_detail", request_id=request_id))

    @app.get("/requests/<request_id>")
    def request_detail(request_id: str) -> str:
        record = next(
            (item for item in history_store().list_records() if item.request.id == request_id),
            None,
        )
        if record is None:
            abort(404)
        return render_template(
            "analysis.html",
            analysis=view_model(record),
            approval_form_action=url_for("approve_request", request_id=request_id),
            **navigation(),
        )

    @app.post("/requests/<request_id>/approve")
    def approve_request(request_id: str) -> object:
        record = next(
            (item for item in history_store().list_records() if item.request.id == request_id),
            None,
        )
        if record is None:
            abort(404)
        if request.form.get("review_acknowledged") != "on":
            return "Review acknowledgment is required before approval.", 400
        record.approval_status = ApprovalStatus.APPROVED
        record.approved_at = datetime.now(timezone.utc).isoformat()
        history_store().save(record)
        return redirect(url_for("request_detail", request_id=request_id))

    @app.get("/history")
    def history_page() -> str:
        return render_template("history.html", dashboard=dashboard_model(), **navigation())

    @app.get("/api/history")
    def history() -> tuple[object, int]:
        records = history_store().list_records()
        return jsonify(
            [
                {
                    "request_id": record.request.id,
                    "classification": record.result.classification.value,
                    "approval_status": record.approval_status.value,
                }
                for record in records
            ]
        ), 200

    return app
