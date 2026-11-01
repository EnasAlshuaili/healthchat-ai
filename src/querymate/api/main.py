"""FastAPI application for docs/API_CONTRACT.md v0.3, curated_single_topic mode.

`/api/chat` delegates every question to `querymate.pipeline.respond`, which runs
the Safety & Scope Router first and returns one fixed reply: a safety or input
template, an owner-reviewed curated answer, or the safe fallback. This module adds
only the request ID and response validation: it does no routing, lookup, or
template selection of its own. The topic matcher and the TF-IDF retrieval baseline
are not connected.

Run locally (bound to 127.0.0.1, access log off):
    .venv\\Scripts\\python.exe scripts\\run_api.py
"""

from __future__ import annotations

from fastapi import FastAPI, Request

from querymate import pipeline, safety
from querymate.api.errors import install_handlers, request_id_of
from querymate.api.middleware import RequestContextMiddleware
from querymate.api.schemas import ChatRequest, ChatResponse, HealthResponse, HealthVersions

# FastAPI's native OpenTelemetry can record validation errors with the submitted
# input and stack traces. Keep it off, overriding FASTAPI_OTEL_AUTO_CONFIGURE.
TELEMETRY_OFF = {
    "tracing": False,
    "metrics": False,
    "logs": False,
    "operation_spans": False,
    "auto_configure": False,
}


def create_app() -> FastAPI:
    app = FastAPI(
        title="QueryMate API",
        # Only the two contract endpoints exist. Swagger UI would also load assets from a CDN.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        telemetry=TELEMETRY_OFF,
    )
    install_handlers(app)
    app.add_middleware(RequestContextMiddleware)

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        # Connected components (contract v0.3), not the execution of the router for a request.
        return HealthResponse(
            versions=HealthVersions(
                router=safety.ROUTER_VERSION,
                matcher=None,
                content=pipeline.TEMPLATE_VERSION,
                knowledge=pipeline.connected_knowledge_version(),
            )
        )

    @app.post("/api/chat", response_model=ChatResponse)
    def chat(payload: ChatRequest, request: Request) -> ChatResponse:
        result = pipeline.respond(payload.question)
        # Validating the pipeline's own serialisation enforces the v0.3 invariants. A failure
        # here is an unexpected error outside the pipeline and becomes a generic 500.
        return ChatResponse.model_validate(result.to_dict(request_id_of(request)))

    return app


app = create_app()
