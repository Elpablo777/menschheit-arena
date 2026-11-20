"""Deterministische Debatten-Engine mit Checkpoints, Stop-Gate und Dual-Order-Richter."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from ..config import Settings
from ..i18n import normalize_lang
from ..llm import model_for
from ..llm.base import LLMClient, LLMResult
from ..storage import Repository, utcnow
from . import prompts
from .models import JudgeVerdict, ModeratorVerdict, ScoreBlock, TurnPayload
from .parser import LLMOutputError, parse_judge, parse_moderator, parse_turn
from .report import build_debate_report

Progress = Callable[[str], None]


class DebateNotFound(RuntimeError):
    pass


class DebateBusy(RuntimeError):
    pass


class DebateEngine:
    def __init__(
        self,
        settings: Settings,
        repository: Repository,
        client: LLMClient,
        progress: Progress | None = None,
    ) -> None:
        self.settings = settings
        self.repo = repository
        self.client = client
        self.progress = progress
        self.tokens = 0
        self._local_lock = threading.Lock()
        self._active: set[str] = set()

    def _notify(self, message: str) -> None:
        if self.progress:
            try:
                self.progress(message)
            except Exception:
                pass

    def _call(
        self,
        messages: list[dict[str, str]],
        *,
        role: str,
        purpose: str,
        meta: dict[str, Any],
    ) -> LLMResult:
        result = self.client.complete(
            messages,
            model=model_for(self.settings, role),
            purpose=purpose,
            meta=meta,
        )
        self.tokens += result.total_tokens
        return result

    def _with_repair(
        self,
        messages: list[dict[str, str]],
        result: LLMResult,
        *,
        parse: Callable[[str], Any],
        role: str,
        purpose: str,
        meta: dict[str, Any],
    ) -> Any:
        try:
            return parse(result.text)
        except LLMOutputError:
            repair = [
                *messages,
                {"role": "assistant", "content": result.text[:4000]},
                {
                    "role": "user",
                    "content": (
                        "Deine Antwort war kein gueltiges JSON oder verletzte das Schema. "
                        "Antworte erneut ausschliesslich mit dem geforderten JSON-Objekt, ohne Codefence."
                    ),
                },
            ]
            repaired = self._call(repair, role=role, purpose=purpose, meta=meta)
            return parse(repaired.text)

    def run(self, debate_id: str) -> dict[str, Any]:
        debate = self.repo.get_debate(debate_id)
        if not debate:
            raise DebateNotFound(debate_id)
        if debate["status"] != "pending":
            raise DebateBusy(f"Debatte {debate_id} hat Status {debate['status']}.")
        with self._local_lock:
            if debate_id in self._active:
                raise DebateBusy(f"Debatte {debate_id} laeuft bereits.")
            self._active.add(debate_id)

        self.tokens = 0
        lang = normalize_lang(debate["language"])
        topic = str(debate["topic"])
        rounds = max(1, min(int(debate["rounds_requested"]), self.settings.max_rounds))
        models = debate.get("models") or {
            "pro": self.settings.pro_model,
            "contra": self.settings.contra_model,
            "judge": self.settings.judge_model,
            "moderator": self.settings.moderator_model,
        }
        knowledge = prompts.load_knowledge(lang)

        self.repo.update_debate(debate_id, status="running", error=None, completed_at=None)
        self._notify("Debatte gestartet")
        try:
            previous_public: dict[str, str] = {"pro": "", "contra": ""}
            directive = ""
            stop_reason: str | None = None

            for round_no in range(1, rounds + 1):
                current: dict[str, dict[str, Any]] = {}
                for role in ("pro", "contra"):
                    self._notify(f"Runde {round_no}/{rounds}: {role}")
                    opponent = previous_public["contra" if role == "pro" else "pro"] if round_no > 1 else ""
                    messages = prompts.turn_messages(
                        role=role,
                        lang=lang,
                        topic=topic,
                        round_no=round_no,
                        rounds_requested=rounds,
                        opponent=opponent,
                        own_previous=previous_public[role] if round_no > 1 else "",
                        directive=directive if round_no > 1 else "",
                        word_limit=self.settings.word_limit,
                        knowledge=knowledge,
                    )
                    meta = {
                        "lang": lang,
                        "round": round_no,
                        "rounds_requested": rounds,
                        "topic": topic,
                        "opponent": opponent,
                        "directive": directive if round_no > 1 else "",
                    }
                    result = self._call(messages, role=role, purpose=role, meta=meta)
                    payload: TurnPayload = self._with_repair(
                        messages,
                        result,
                        parse=parse_turn,
                        role=role,
                        purpose=role,
                        meta=meta,
                    )
                    self.repo.add_turn(
                        debate_id=debate_id,
                        round_no=round_no,
                        role=role,
                        steelman=payload.steelman_opponent,
                        public_argument=payload.public_argument,
                        internal_reasoning=payload.internal_reasoning,
                        confidence=payload.confidence_own_thesis,
                        conceded=payload.conceded_claims,
                        falsification=payload.falsification_condition,
                    )
                    current[role] = {
                        "role": role,
                        "confidence": payload.confidence_own_thesis,
                        "steelman": payload.steelman_opponent,
                        "public_argument": payload.public_argument,
                        "conceded_claims": payload.conceded_claims,
                        "falsification": payload.falsification_condition,
                    }

                self._notify(f"Runde {round_no}/{rounds}: Moderator")
                round_public = [current["pro"], current["contra"]]
                mod_messages = prompts.moderator_messages(
                    lang=lang,
                    topic=topic,
                    round_no=round_no,
                    rounds_requested=rounds,
                    round_public=round_public,
                    previous_directive=directive,
                )
                mod_result = self._call(
                    mod_messages,
                    role="moderator",
                    purpose="moderator",
                    meta={
                        "lang": lang,
                        "round": round_no,
                        "rounds_requested": rounds,
                        "topic": topic,
                    },
                )
                verdict: ModeratorVerdict = self._with_repair(
                    mod_messages,
                    mod_result,
                    parse=parse_moderator,
                    role="moderator",
                    purpose="moderator",
                    meta={"lang": lang, "round": round_no, "rounds_requested": rounds, "topic": topic},
                )

                # Code-erzwungenes Gate: "CONVINCED" zaehlt nur mit Konfidenz <= 25.
                low_confidence = any(
                    int(current[role]["confidence"]) <= 25 for role in ("pro", "contra")
                )
                decision = verdict.decision
                if decision == "CONVINCED" and not low_confidence:
                    decision = "CONTINUE_REFINE"
                    verdict.next_round_directive = (
                        "Der Moderator meldete Überzeugung, aber keine Seite hat das harte "
                        "Konfidenz-Gate von 25 erreicht. Benennt die gefallene Prämisse oder "
                        "führt den Dissens ehrlich weiter."
                    )
                if decision == "CONTINUE_REFINE" and round_no >= rounds:
                    decision = "DEADLOCK"

                self.repo.add_moderation(
                    debate_id=debate_id,
                    round_no=round_no,
                    summary=verdict.round_summary,
                    sycophancy=verdict.sycophancy_detected,
                    drift=verdict.drift_detected,
                    decision=decision,
                    directive=verdict.next_round_directive,
                )
                directive = verdict.next_round_directive
                previous_public = {
                    "pro": current["pro"]["public_argument"],
                    "contra": current["contra"]["public_argument"],
                }
                if decision in {"CONVINCED", "SYNTHESIS_REACHED", "DEADLOCK"}:
                    stop_reason = decision
                    break

            if not stop_reason:
                stop_reason = "DEADLOCK"

            self._notify("Richter-Durchlauf A/B")
            turns = self.repo.list_turns(debate_id)
            transcript_ab = self._transcript(turns, "ab", lang)
            judge_meta = {"lang": lang, "order": "ab", "topic": topic}
            judge_messages_ab = prompts.judge_messages(lang, topic, "ab", transcript_ab)
            judge_ab_result = self._call(
                judge_messages_ab, role="judge", purpose="judge", meta=judge_meta
            )
            pass_ab: JudgeVerdict = self._with_repair(
                judge_messages_ab,
                judge_ab_result,
                parse=parse_judge,
                role="judge",
                purpose="judge",
                meta=judge_meta,
            )

            self._notify("Richter-Durchlauf B/A")
            transcript_ba = self._transcript(turns, "ba", lang)
            judge_meta_ba = {"lang": lang, "order": "ba", "topic": topic}
            judge_messages_ba = prompts.judge_messages(lang, topic, "ba", transcript_ba)
            judge_ba_result = self._call(
                judge_messages_ba, role="judge", purpose="judge", meta=judge_meta_ba
            )
            pass_ba: JudgeVerdict = self._with_repair(
                judge_messages_ba,
                judge_ba_result,
                parse=parse_judge,
                role="judge",
                purpose="judge",
                meta=judge_meta_ba,
            )

            bias_delta = float(
                abs(pass_ab.pro_score().total - pass_ba.pro_score().total)
                + abs(pass_ab.contra_score().total - pass_ba.contra_score().total)
            )
            final_scores = self._average_scores(pass_ab, pass_ba)
            pro_total = float(final_scores["pro"]["total"])
            contra_total = float(final_scores["contra"]["total"])
            if abs(pro_total - contra_total) < 2.0:
                winner = "draw"
            elif pro_total > contra_total:
                winner = "pro"
            else:
                winner = "contra"

            report_md = build_debate_report(
                debate={**debate, "stop_reason": stop_reason, "models": models},
                turns=turns,
                moderations=self.repo.list_moderations(debate_id),
                pass_ab=pass_ab.model_dump(),
                pass_ba=pass_ba.model_dump(),
                bias_delta=bias_delta,
                final_scores=final_scores,
                winner=winner,
                lang=lang,
                is_mock=self.settings.is_mock,
            )
            self.repo.save_judgment(
                debate_id=debate_id,
                pass_ab=pass_ab.model_dump(),
                pass_ba=pass_ba.model_dump(),
                bias_delta=bias_delta,
                toulmin={
                    "average": final_scores,
                    "bias_delta": bias_delta,
                    "winner": winner,
                },
                final_report_md=report_md,
            )
            self.repo.update_debate(
                debate_id,
                status="completed",
                stop_reason=stop_reason,
                total_tokens=self.tokens,
                completed_at=utcnow(),
            )
            self._notify("Abgeschlossen")
            return self.repo.get_debate(debate_id) or {}
        except Exception as exc:
            message = f"{type(exc).__name__}: {str(exc)[:500]}"
            self.repo.update_debate(
                debate_id,
                status="failed",
                error=message,
                stop_reason="ERROR",
                completed_at=utcnow(),
            )
            raise
        finally:
            with self._local_lock:
                self._active.discard(debate_id)

    @staticmethod
    def _average_scores(pass_ab: JudgeVerdict, pass_ba: JudgeVerdict) -> dict[str, dict[str, Any]]:
        keys = ("claims", "logic", "qualifiers", "rebuttals", "realism")
        result: dict[str, dict[str, Any]] = {}
        for side, getter in (("pro", "pro_score"), ("contra", "contra_score")):
            first: ScoreBlock = getattr(pass_ab, getter)()
            second: ScoreBlock = getattr(pass_ba, getter)()
            block: dict[str, Any] = {}
            total = 0.0
            for key in keys:
                value = round((getattr(first, key) + getattr(second, key)) / 2, 1)
                block[key] = value
                total += value
            block["total"] = round(total, 1)
            result[side] = block
        return result

    @staticmethod
    def _transcript(turns: list[dict[str, Any]], order: str, lang: str) -> str:
        side_order = [("A", "pro"), ("B", "contra")] if order == "ab" else [("A", "contra"), ("B", "pro")]
        lines: list[str] = []
        for label, role in side_order:
            name = "Pro Menschheit" if role == "pro" else "Contra / Skeptiker"
            if lang == "en":
                name = "Pro humanity" if role == "pro" else "Contra / sceptic"
            lines.append(f"## Position {label} ({name})")
            side_turns = [turn for turn in turns if turn["role"] == role]
            for turn in side_turns:
                lines.extend(
                    [
                        f"### Runde {turn['round_no']}",
                        f"Steelman: {turn.get('steelman', '')}",
                        turn.get("public_argument", ""),
                        f"Konfidenz: {turn.get('confidence', 0)}",
                        f"Zugestanden: {', '.join(turn.get('conceded_claims', [])) or '(keine)'}",
                        f"Falsifikationsbedingung: {turn.get('falsification', '')}",
                        "",
                    ]
                )
            lines.append("")
        return "\n".join(lines)


def run_debate(
    settings: Settings,
    repository: Repository,
    client: LLMClient,
    debate_id: str,
    progress: Progress | None = None,
) -> dict[str, Any]:
    return DebateEngine(settings, repository, client, progress=progress).run(debate_id)
