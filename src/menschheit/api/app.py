"""FastAPI-Control-Plane fuer Arena und Sentinel."""

from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..config import PROJECT_ROOT, Settings, get_settings, reload_settings
from ..debate.engine import DebateEngine
from ..i18n import catalog, normalize_lang, t
from ..llm import build_client
from ..llm.base import LLMClient, LLMError
from ..providers import catalogue, provider_info
from ..sentinel import service
from ..sentinel.scope import ScopeError, ScopeGuard
from ..storage import Database, Repository
from .schemas import (
    ApproveRequest,
    DebateCreate,
    DebateFork,
    EngagementCreate,
    FindingCreate,
    KillSwitchRequest,
    PlanRequest,
    ProviderSelect,
    ProviderTestRequest,
    RejectRequest,
    ValidateTargetRequest,
)

WEB_ROOT = Path(__file__).resolve().parent.parent / "web"
templates = Jinja2Templates(directory=str(WEB_ROOT / "templates"))


def _public_debate(debate: dict[str, Any], progress: str | None = None) -> dict[str, Any]:
    result = dict(debate)
    result["turn_count"] = len(result.get("turns", []))
    result["rounds_actual"] = len({turn.get("round_no") for turn in result.get("turns", []) if turn.get("round_no")})
    result["progress"] = progress
    return result


def _public_engagement(engagement: dict[str, Any]) -> dict[str, Any]:
    result = dict(engagement)
    result.pop("roe_text", None)
    return result


_ENV_LINE_SAFE = str.maketrans({"\n": " ", "\r": " ", '"': "'"})


def _env_line(key: str, value: str) -> str:
    cleaned = str(value).translate(_ENV_LINE_SAFE).strip()
    if not cleaned:
        return f"{key}="
    if any(char in cleaned for char in (" ", "#")):
        return f'{key}="{cleaned}"'
    return f"{key}={cleaned}"


def _write_env_file(path: Path, values: dict[str, str]) -> None:
    """Schreibt die Werte in eine bestehende .env, ohne fremde Zeilen zu verlieren."""
    lines: list[str] = []
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                lines.append(raw)
                continue
            key = stripped.split("=", 1)[0].strip()
            if key in values:
                continue
            lines.append(raw)
    for key, value in values.items():
        lines.append(_env_line(key, value))
    body = "\n".join(lines).strip() + "\n"
    path.write_text(body, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


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
                DebateEngine(
                    settings, repo, client, progress=lambda label: set_progress(debate_id, label)
                ).run(debate_id)
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
        data["api_key_set"] = bool(settings.llm_api_key)
        return data

    @app.get("/api/providers")
    def providers() -> dict[str, Any]:
        return {"providers": catalogue(), "selected": settings.provider}

    @app.post("/api/providers/test")
    def provider_test(payload: ProviderTestRequest) -> dict[str, Any]:
        """Prueft einen Provider mit einem Minimalaufruf, ohne die Konfiguration zu aendern."""
        info = provider_info(payload.provider)
        base_url = (payload.base_url or info.get("base_url") or "").strip()
        if not base_url:
            return {"ok": False, "message": "Keine Base-URL angegeben."}
        api_key = payload.api_key if payload.api_key is not None else settings.llm_api_key
        try:
            probe: LLMClient = build_client(
                Settings(
                    provider=payload.provider,
                    llm_base_url=base_url,
                    llm_api_key=api_key,
                    timeout_seconds=25.0,
                    max_tokens=64,
                )
            )
            model = payload.model or info["defaults"]["pro"]
            result = probe.complete(
                [{"role": "user", "content": "Antworte mit dem einzelnen Wort: ok"}],
                model=model,
                purpose="probe",
                max_tokens=32,
                temperature=0,
            )
            return {
                "ok": True,
                "message": f"{model} antwortet mit {result.total_tokens} Tokens.",
                "sample": result.text[:200],
                "model": model,
            }
        except LLMError as exc:
            return {"ok": False, "message": str(exc)[:400]}
        except Exception as exc:
            return {"ok": False, "message": f"{type(exc).__name__}: {str(exc)[:300]}"}

    @app.post("/api/providers/select")
    def provider_select(payload: ProviderSelect) -> dict[str, Any]:
        """Speichert Provider, Base-URL, Key und Modell dauerhaft in der .env."""
        import os

        info = provider_info(payload.provider)
        base_url = (payload.base_url or info.get("base_url") or "").strip()
        if payload.provider not in {"mock", "ollama", "litellm", "custom"} and not base_url:
            raise HTTPException(400, "Base-URL fehlt.")

        env_path = Path(os.environ.get("MENSCHHEIT_ENV", PROJECT_ROOT / ".env"))
        env_path.parent.mkdir(parents=True, exist_ok=True)
        backup = None
        if env_path.exists():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = env_path.with_name(f"{env_path.name}.bak-{stamp}")
            backup.write_bytes(env_path.read_bytes())

        values = {
            "LLM_PROVIDER": payload.provider,
            "LLM_BASE_URL": base_url,
            "LLM_API_KEY": payload.api_key or "",
            "ARENA_PRO_MODEL": payload.model or info["defaults"]["pro"],
            "ARENA_CONTRA_MODEL": payload.model or info["defaults"]["contra"],
            "ARENA_JUDGE_MODEL": payload.model or info["defaults"]["judge"],
            "ARENA_MODERATOR_MODEL": payload.model or info["defaults"]["moderator"],
        }
        _write_env_file(env_path, values)
        reload_settings()
        try:
            rebuilt = build_client(get_settings())
            app.state.client = rebuilt
            app.state.startup_error = ""
            globals()["client"] = rebuilt
        except Exception as exc:
            app.state.client = None
            app.state.startup_error = f"{type(exc).__name__}: {str(exc)[:200]}"
        return {
            "ok": True,
            "provider": payload.provider,
            "base_url": base_url,
            "model": values["ARENA_PRO_MODEL"],
            "backup": backup.name if backup else None,
            "message": t("toast.provider_saved", settings.lang) if hasattr(settings, "lang") else "Standard gespeichert.",
        }

    @app.get("/api/i18n/{lang}")
    def i18n(lang: str) -> dict[str, Any]:
        normalised = normalize_lang(lang)
        return {"lang": normalised, "messages": catalog(normalised)}

    # ---------- Arena ----------

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
        config_data: dict[str, Any] = {}
        if payload.models:
            models.update(payload.models)
        if payload.config:
            config_data = payload.config.model_dump(exclude_none=True)
            for role in ("pro", "contra", "judge", "moderator"):
                value = config_data.get(f"{role}_model")
                if value:
                    models[role] = str(value)

        debate = repo.create_debate(
            topic=payload.topic,
            language=payload.language,
            rounds_requested=rounds,
            models=models,
            config=config_data,
            parent_debate_id=payload.parent_debate_id,
        )
        if payload.sync:
            try:
                completed = DebateEngine(settings, repo, client).run(debate["id"])
                return _public_debate(completed, get_progress(debate["id"]))
            except LLMError as exc:
                raise HTTPException(502, f"LLM-Fehler: {str(exc)[:300]}") from None
            except Exception as exc:
                raise HTTPException(
                    500, f"Debatte fehlgeschlagen: {type(exc).__name__}: {str(exc)[:300]}"
                ) from None
        run_in_thread(debate["id"])
        return _public_debate(repo.get_debate(debate["id"]) or debate, get_progress(debate["id"]))

    @app.post("/api/arena/debates/{debate_id}/fork", status_code=202)
    def fork_debate(debate_id: str, payload: DebateFork) -> Any:
        """Startet eine neue Debatte auf Basis einer bestehenden, mit anderem Thema."""
        if not client:
            raise HTTPException(503, f"LLM-Provider nicht bereit: {startup_error}")
        source = repo.get_debate(debate_id)
        if not source:
            raise HTTPException(404, "Quell-Debatte nicht gefunden.")
        rounds = payload.rounds or int(source.get("rounds_requested") or settings.default_rounds)
        if rounds > settings.max_rounds:
            raise HTTPException(400, f"Maximal {settings.max_rounds} Runden erlaubt.")
        models = dict(source.get("models") or {}) if payload.inherit_models else {}
        base_models = {
            "pro": settings.pro_model,
            "contra": settings.contra_model,
            "judge": settings.judge_model,
            "moderator": settings.moderator_model,
        }
        base_models.update({k: v for k, v in models.items() if v})
        config_data = dict(source.get("config") or {}) if payload.inherit_config else {}
        language = normalize_lang(payload.language or source.get("language") or settings.lang)
        debate = repo.create_debate(
            topic=payload.topic,
            language=language,
            rounds_requested=rounds,
            models=base_models,
            config=config_data,
            parent_debate_id=debate_id,
        )
        run_in_thread(debate["id"])
        return _public_debate(repo.get_debate(debate["id"]) or debate, get_progress(debate["id"]))

    @app.get("/api/arena/debates")
    def list_debates(limit: int = 100) -> list[dict[str, Any]]:
        return repo.list_debates(limit=limit)

    @app.get("/api/arena/debates/{debate_id}")
    def get_debate(debate_id: str) -> dict[str, Any]:
        debate = repo.get_debate(debate_id)
        if not debate:
            raise HTTPException(404, "Debatte nicht gefunden.")
        return _public_debate(debate, get_progress(debate_id))

    @app.get("/api/arena/debates/{debate_id}/transcript")
    def debate_transcript(debate_id: str) -> dict[str, Any]:
        """Rohdaten fuer die geordnete Protokollansicht."""
        debate = repo.get_debate(debate_id)
        if not debate:
            raise HTTPException(404, "Debatte nicht gefunden.")
        rounds: list[dict[str, Any]] = []
        turns = debate.get("turns") or []
        for round_no in sorted({turn["round_no"] for turn in turns}):
            entries = [turn for turn in turns if turn["round_no"] == round_no]
            pro = next((turn for turn in entries if turn["role"] == "pro"), None)
            contra = next((turn for turn in entries if turn["role"] == "contra"), None)
            moderation = next(
                (mod for mod in debate.get("moderations") or [] if mod["round_no"] == round_no), None
            )
            rounds.append({"round_no": round_no, "pro": pro, "contra": contra, "moderation": moderation})
        return {
            "debate": {
                "id": debate["id"],
                "topic": debate["topic"],
                "language": debate["language"],
                "status": debate["status"],
                "rounds_requested": debate["rounds_requested"],
                "rounds_actual": debate.get("rounds_actual", 0),
                "models": debate.get("models", {}),
                "created_at": debate["created_at"],
                "completed_at": debate.get("completed_at"),
                "parent_debate_id": debate.get("parent_debate_id"),
            },
            "rounds": rounds,
            "judgment": debate.get("judgment"),
        }

    @app.get("/api/arena/debates/{debate_id}/calls")
    def debate_calls(debate_id: str, role: str | None = None, limit: int = 500) -> dict[str, Any]:
        """Alle LLM-Aufrufe mit Prompts, Antworten und Token-Zahlen."""
        if not repo.get_debate(debate_id):
            raise HTTPException(404, "Debatte nicht gefunden.")
        calls = repo.list_llm_calls(debate_id, role=role, limit=limit)
        return {
            "count": len(calls),
            "total_tokens": sum(int(call.get("total_tokens") or 0) for call in calls),
            "calls": calls,
        }

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

    @app.delete("/api/arena/debates/{debate_id}")
    def delete_debate(debate_id: str) -> dict[str, Any]:
        if not repo.delete_debate(debate_id):
            raise HTTPException(404, "Debatte nicht gefunden.")
        with progress_lock:
            progress.pop(debate_id, None)
        return {"deleted": debate_id}

    @app.get("/api/prompts/{role}/{lang}")
    def prompt_text(role: str, lang: str) -> dict[str, Any]:
        """Gibt den System-Prompt einer Rolle aus (Rohtext, wie er verwendet wird)."""
        from ..debate import prompts as prompt_module

        normalised = normalize_lang(lang)
        if role not in {"pro", "contra", "moderator", "judge", "planner"}:
            raise HTTPException(404, "Unbekannte Rolle.")
        try:
            return {"role": role, "lang": normalised, "system_prompt": prompt_module.load_prompt(role, normalised)}
        except FileNotFoundError:
            raise HTTPException(404, "Prompt nicht gefunden.") from None

    # ---------- Sentinel ----------

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

    @app.get("/api/sentinel/engagements")
    def list_engagements(limit: int = 100) -> list[dict[str, Any]]:
        return repo.list_engagements(limit=limit)

    @app.get("/api/sentinel/engagements/{engagement_id}")
    def get_engagement(engagement_id: str) -> dict[str, Any]:
        engagement = repo.get_engagement(engagement_id)
        if not engagement:
            raise HTTPException(404, "Engagement nicht gefunden.")
        return _public_engagement(engagement)

    @app.post("/api/sentinel/engagements/{engagement_id}/plan")
    def plan(engagement_id: str, payload: PlanRequest) -> dict[str, Any]:
        if payload.mode == "llm" and not client:
            raise HTTPException(503, f"LLM-Provider nicht bereit: {startup_error}")
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

    @app.delete("/api/sentinel/engagements/{engagement_id}")
    def delete_engagement(engagement_id: str) -> dict[str, Any]:
        if not repo.delete_engagement(engagement_id):
            raise HTTPException(404, "Engagement nicht gefunden.")
        return {"deleted": engagement_id}

    @app.get("/api/audit")
    def audit_status() -> dict[str, Any]:
        valid, errors = repo.verify_audit_chain()
        return {"valid": valid, "errors": errors[:20], "events": len(repo.db.fetch_all("SELECT id FROM audit_events"))}

    return app


app = create_app()