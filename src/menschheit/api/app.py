"""FastAPI-Control-Plane fuer Arena und Sentinel."""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..config import Settings, get_settings
from ..debate.engine import DebateBusy, DebateEngine, DebateNotFound
from ..i18n import catalog, normalize_lang
from ..llm import build_client
from ..llm.base import LLMClient, LLMError
from ..sentinel import service
from ..sentinel.scope import ScopeError, ScopeGuard
from ..storage import Database, Repository
from .schemas import (
    ApproveRequest,
    DebateCreate,
    EngagementCreate,
    FindingCreate,
    KillSwitchRequest,
    PlanRequest,
    RejectRequest,
    ValidateTargetRequest,
)

WEB_ROOT = Path(__file__).resolve().parent.parent / "web"
templates = Jinja2Templates(directory=str(WEB_ROOT / "templates"))


def _public_debate(debate: dict[str, Any], progress: str | None = None) -> dict[str, Any]:
    result = dict(debate)
    result["turn_count"] = len(result.get("turns", []))
    result["progress"] = progress
    return result


def _public_engagement(engagement: dict[str, Any]) -> dict[str, Any]:
    result = dict(engagement)
    result.pop("roe_text", None)
    return result


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    settings = settings or get_settings()
    db = database or Database(settings.database_url)
    repo = Repository(db)
    startup_error = ""
    try:
        client: LLMClient | None = build_client(settings)
    except Exception as exc:  # Konfigurationsfehler sollen die UI nicht blockieren.
        client = None
        startup_error = f"{type(exc).__name__}: {str(exc)[:300]}"

    progress: dict[str, str] = {}
    progress_lock = threading.Lock()

    def set_progress(debate_id: str, label: str) -> None:
        with progress_lock:
            progress[debate_id] = label

    def get_progress(debate_id: str) -> str | None:
        with progress_lock:
            return progress.get(debate_id)

    def run_in_thread(debate_id: str) -> None:
        if not client:
            set_progress(debate_id, f"Provider nicht bereit: {startup_error}")
            return

        def target() -> None:
            try:
                DebateEngine(settings, repo, client, progress=lambda label: set_progress(debate_id, label)).run(debate_id)
            except Exception as exc:
                set_progress(debate_id, f"Fehler: {type(exc).__name__}")

        threading.Thread(target=target, name=f"debate-{debate_id[:8]}", daemon=True).start()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        repo.fail_stale_debates()
        yield

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description=(
            "Bilinguale Multi-Agenten-Debatten-Arena und sicheres Pentest-Control-Plane. "
            "Aktive offensive Ausfuehrung ist absichtlich nicht implementiert."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = db
    app.state.repo = repo
    app.state.client = client
    app.state.startup_error = startup_error
    app.state.progress = progress

    app.mount("/static", StaticFiles(directory=str(WEB_ROOT / "static")), name="static")

    @app.middleware("http")
    async def token_middleware(request: Request, call_next):
        if (
            settings.access_token
            and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and request.url.path.startswith("/api/")
        ):
            supplied = request.headers.get("X-App-Token", "")
            auth = request.headers.get("Authorization", "")
            if auth.lower().startswith("bearer "):
                supplied = auth.split(" ", 1)[1].strip()
            if supplied != settings.access_token:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Ungueltiges oder fehlendes App-Token."},
                )
        return await call_next(request)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"app_name": settings.app_name, "lang": normalize_lang(settings.lang)},
        )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok" if db.health() else "degraded",
            "database": db.health(),
            "provider": settings.provider,
            "llm_ready": client is not None,
            "version": settings.version,
            "mock": settings.is_mock,
        }

    @app.get("/api/config")
    def config() -> dict[str, Any]:
        data = settings.public_dict()
        data["llm_ready"] = client is not None
        data["startup_error"] = startup_error
        return data

    @app.get("/api/i18n/{lang}")
    def i18n(lang: str) -> dict[str, Any]:
        normalised = normalize_lang(lang)
        return {"lang": normalised, "messages": catalog(normalised)}

    @app.post("/api/arena/debates", status_code=202)
    def create_debate(payload: DebateCreate) -> Any:
        if not client:
            raise HTTPException(503, f"LLM-Provider nicht bereit: {startup_error}")
        rounds = payload.rounds or settings.default_rounds
        if rounds > settings.max_rounds:
            raise HTTPException(400, f"Maximal {settings.max_rounds} Runden erlaubt.")
        models = {
            "pro": settings.pro_model,
            "contra": settings.contra_model,
            "judge": settings.judge_model,
            "moderator": settings.moderator_model,
        }
        if payload.models:
            models.update(payload.models)
        debate = repo.create_debate(
            topic=payload.topic,
            language=payload.language,
            rounds_requested=rounds,
            models=models,
        )
        if payload.sync:
            try:
                completed = DebateEngine(settings, repo, client).run(debate["id"])
                return _public_debate(completed, get_progress(debate["id"]))
            except Exception as exc:
                raise HTTPException(500, f"Debatte fehlgeschlagen: {type(exc).__name__}: {str(exc)[:300]}") from None
        run_in_thread(debate["id"])
        return _public_debate(repo.get_debate(debate["id"]) or debate, get_progress(debate["id"]))

    @app.get("/api/arena/debates")
    def list_debates() -> list[dict[str, Any]]:
        return repo.list_debates()

    @app.get("/api/arena/debates/{debate_id}")
    def get_debate(debate_id: str) -> dict[str, Any]:
        debate = repo.get_debate(debate_id)
        if not debate:
            raise HTTPException(404, "Debatte nicht gefunden.")
        return _public_debate(debate, get_progress(debate_id))

    @app.get("/api/arena/debates/{debate_id}/report.md", response_class=PlainTextResponse)
    def debate_report(debate_id: str) -> PlainTextResponse:
        debate = repo.get_debate(debate_id)
        if not debate:
            raise HTTPException(404, "Debatte nicht gefunden.")
        judgment = debate.get("judgment")
        if not judgment:
            raise HTTPException(404, "Noch kein Bericht vorhanden.")
        return PlainTextResponse(
            judgment["final_report_md"],
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="debate-{debate_id}.md"'},
        )

    @app.post("/api/sentinel/engagements", status_code=201)
    def create_engagement(payload: EngagementCreate) -> dict[str, Any]:
        try:
            engagement = service.create_engagement(
                repo,
                settings,
                client_name=payload.client_name,
                scope=payload.scope,
                ports=payload.ports,
                valid_from=payload.valid_from,
                valid_until=payload.valid_until,
                roe_text=payload.roe_text,
                authorized_by=payload.authorized_by,
                emergency_contact=payload.emergency_contact,
            )
            return _public_engagement(engagement)
        except service.EngagementError as exc:
            raise HTTPException(400, str(exc)) from None
        except ScopeError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.get("/api/sentinel/engagements")
    def list_engagements() -> list[dict[str, Any]]:
        return repo.list_engagements()

    @app.get("/api/sentinel/engagements/{engagement_id}")
    def get_engagement(engagement_id: str) -> dict[str, Any]:
        engagement = repo.get_engagement(engagement_id)
        if not engagement:
            raise HTTPException(404, "Engagement nicht gefunden.")
        return _public_engagement(engagement)

    @app.post("/api/sentinel/engagements/{engagement_id}/plan")
    def plan(engagement_id: str, payload: PlanRequest) -> dict[str, Any]:
        if payload.mode == "llm" and not client:
            raise HTTPException(503, "LLM-Provider nicht bereit.")
        try:
            actions = service.generate_plan(
                repo,
                settings,
                client,  # type: ignore[arg-type]
                engagement_id,
                mode=payload.mode,
                lang=payload.language,
            )
            return {"actions": actions, "count": len(actions)}
        except service.EngagementNotFound:
            raise HTTPException(404, "Engagement nicht gefunden.") from None
        except service.EngagementError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.post("/api/sentinel/actions/{action_id}/approve")
    def approve(action_id: str, payload: ApproveRequest) -> dict[str, Any]:
        try:
            return service.approve_action(repo, settings, action_id, payload.approver)
        except service.EngagementNotFound:
            raise HTTPException(404, "Aktion nicht gefunden.") from None
        except service.EngagementError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.post("/api/sentinel/actions/{action_id}/reject")
    def reject(action_id: str, payload: RejectRequest) -> dict[str, Any]:
        try:
            return service.reject_action(repo, action_id, payload.actor, payload.reason)
        except service.EngagementNotFound:
            raise HTTPException(404, "Aktion nicht gefunden.") from None
        except service.EngagementError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.post("/api/sentinel/engagements/{engagement_id}/kill")
    def kill(engagement_id: str, payload: KillSwitchRequest) -> dict[str, Any]:
        try:
            return _public_engagement(service.activate_kill_switch(repo, engagement_id, payload.actor))
        except service.EngagementNotFound:
            raise HTTPException(404, "Engagement nicht gefunden.") from None

    @app.post("/api/sentinel/engagements/{engagement_id}/findings", status_code=201)
    def create_finding(engagement_id: str, payload: FindingCreate) -> dict[str, Any]:
        try:
            return service.add_finding(
                repo,
                engagement_id,
                title=payload.title,
                owasp_ref=payload.owasp_ref,
                cvss_vector=payload.cvss_vector,
                evidence=payload.evidence,
                remediation=payload.remediation,
                verified_by_human=payload.verified_by_human,
                actor=payload.actor,
            )
        except service.EngagementNotFound:
            raise HTTPException(404, "Engagement nicht gefunden.") from None
        except service.EngagementError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.get("/api/sentinel/engagements/{engagement_id}/report.md", response_class=PlainTextResponse)
    def engagement_report(engagement_id: str, lang: str = "de") -> PlainTextResponse:
        try:
            markdown = service.engagement_report(repo, settings, engagement_id, lang)
        except service.EngagementNotFound:
            raise HTTPException(404, "Engagement nicht gefunden.") from None
        return PlainTextResponse(
            markdown,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="engagement-{engagement_id}.md"'},
        )

    @app.post("/api/sentinel/validate")
    def validate_target(payload: ValidateTargetRequest) -> dict[str, Any]:
        try:
            guard = ScopeGuard(
                payload.scope,
                payload.ports,
                allow_public_targets=settings.allow_public_targets,
            )
        except ScopeError as exc:
            raise HTTPException(400, str(exc)) from None
        decision = guard.check(payload.target, payload.port)
        return {
            "allowed": decision.allowed,
            "reason": decision.reason,
            "target": decision.target,
            "host": decision.host,
            "port": decision.port,
            "kind": decision.kind,
        }

    @app.exception_handler(DebateNotFound)
    async def debate_not_found(_: Request, exc: DebateNotFound):
        return JSONResponse(status_code=404, content={"detail": f"Debatte nicht gefunden: {exc}"})

    @app.exception_handler(DebateBusy)
    async def debate_busy(_: Request, exc: DebateBusy):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(LLMError)
    async def llm_error(_: Request, exc: LLMError):
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    return app


app = create_app()
