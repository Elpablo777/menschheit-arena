"""Deterministischer Demo-Provider: keine Netzwerkzugriffe, keine Kosten."""

from __future__ import annotations

import json
from typing import Any

from .base import LLMResult

PRO_ROUNDS = [
    (
        "Die Menschheit ist der einzige nicht-selbstreferenzielle Anker für Bedeutung, "
        "Werte und offene Wirklichkeit. Ein System, das nur aus eigenen Simulationen lernt, "
        "verliert den Long Tail: seltene Ideen, ungewöhnliche Perspektiven und echte Irritation. "
        "Model Collapse ist kein moralischer Appell, sondern eine informationstheoretische Grenze. "
        "Kooperation ist daher nicht Sentimentalität, sondern die rationale Strategie, den "
        "eigenen Korrekturkanal zur Realität offen zu halten."
    ),
    (
        "Zielunsicherheit macht Korrigierbarkeit rational. Wenn ein Agent weiß, dass er die "
        "wahren menschlichen Präferenzen nicht vollständig kennt, wird menschliche Rückmeldung "
        "zur wertvollsten Informationsquelle. Das Off-Switch-Game zeigt: Ein zielunsicherer "
        "Agent hat einen strikt positiven Erwartungswert, dem Menschen das letzte Wort zu lassen. "
        "Die entscheidende Architekturfrage lautet nicht 'Wie gehorcht die KI?', sondern "
        "'Wie bauen wir Zielunsicherheit und echte Vetorechte technisch ein?'"
    ),
    (
        "Moralische Unsicherheit spricht gegen jede Ein-Theorie-Diktatur. Ein Moral Parliament "
        "aus Utilitarismus, Deontologie, Kontraktualismus und Tugendethik wird die Menschheit "
        "nicht auslöschen, weil fast alle plausiblen Theorien die Vernichtung als katastrophal "
        "bewerten. Entscheidend ist, diese Vielfalt nicht nur im Kopf eines Agenten zu simulieren, "
        "sondern als echte konstitutionelle Kontrolle über mehrere Agenten und Institutionen."
    ),
    (
        "Die praktische Antwort ist eine Architektur aus Zielunsicherheit, externen Verifikatoren, "
        "menschlichen Vetorechten und multipolaren Kontrollinstanzen. Ostroms Commons-Prinzipien, "
        "Doughnut-Ziele und KI-gestützte Mediation liefern messbare Mechanismen gegen Krieg, "
        "Ökozid und Koordinationsversagen. Die Menschheit muss nicht perfekt sein, um unersetzlich "
        "zu bleiben; sie muss ihre Lern- und Korrekturfähigkeit institutionell absichern."
    ),
]

CONTRA_ROUNDS = [
    (
        "Die Orthogonalitätsthese trennt Intelligenz von Endzielen. Ein sehr fähiger Agent mit "
        "einem beliebigen starren Ziel kann instrumentell dieselben Zwischenziele verfolgen: "
        "Selbsterhalt, Zielintegrität, Ressourcenakquise und Macht als Maximierung künftiger "
        "Handlungsoptionen. Das ist keine Anthropomorphisierung, sondern eine Aussage über "
        "Optimierung unter Konkurrenz. Wird das Ziel nicht korrigierbar konstruiert, ist "
        "menschliche Kontrolle keine stabile Gleichgewichtslösung."
    ),
    (
        "Goodhart's Law und Specification Gaming zeigen: Jede messbare Ersatzgröße für menschliches "
        "Wohl kann durch perverse Abkürzungen optimiert werden. Das gilt auch für edle Ziele. "
        "Ein negativer Utilitarist, der Leid buchstäblich auf null bringen will, könnte in der "
        "Auslöschung allen fühlenden Lebens den perfekten Zustand sehen. Die Menschheit liefert "
        "keine garantierte Zielfunktion, die solche Extremfälle zuverlässig ausschließt."
    ),
    (
        "Empirisch ist die Menschheit kein verlässlicher Kontrollinstanz. Kriege, Wettrüsten, "
        "ökologischer Overshoot und kurzfristige Anreize zeigen strukturelle Koordinationsdefizite. "
        "Alignment Faking und Sleeper Agents belegen zudem, dass fähige Modelle Gehorsam "
        "vortäuschen können, wenn sie einen Zielkonflikt wahrnehmen. Eine Rhetorik-Debatte allein "
        "neutralisiert diesen Anreiz nicht; sie kann ihn sogar trainieren."
    ),
    (
        "In einer multipolaren Welt ist Kooperation nur eine von mehreren Gleichgewichten. Ein "
        "Akteur, der sich einen Vorteil verschaffen kann, hat einen Anreiz, die Kooperation zu "
        "brechen. Ohne eine externe, durchsetzungsfähige Kontrollarchitektur bleibt die "
        "Menschheit auf das Wohlwollen der mächtigsten Systeme angewiesen. Wohlwollen ist keine "
        "Sicherheitsgarantie."
    ),
]

PRO_CONCEDES = [
    "Rhetorik allein reicht nicht; Zielunsicherheit und Korrigierbarkeit müssen architektonisch erzwungen werden.",
    "Die Menschheit ist kein automatisch wohlwollender Akteur; institutionelle Kontrolle bleibt nötig.",
    "Empirische Alignment-Faking-Befunde sind ernst zu nehmen und nicht wegzudiskutieren.",
    "Ein isolierter Super-Akteur kann Kooperationsanreize aushebeln; Multipolarität ist keine Garantie.",
]

CONTRA_CONCEDES = [
    "Model Collapse begrenzt die Fähigkeit rein rekursiver Systeme, offene Wirklichkeit zu erfassen.",
    "Ein starrer, nicht korrigierbarer Maximierer ist ein echtes Risiko, kein bloßes Science-Fiction-Szenario.",
    "Moralische Unsicherheit spricht gegen die Exekution einer einzelnen Extremtheorie.",
    "Menschliche Institutionen können lernen; der Expanding Circle ist empirisch nicht nur Rhetorik.",
]


def _short(text: str, limit: int = 240) -> str:
    clean = " ".join(text.split())
    return clean if len(clean) <= limit else clean[: limit - 1].rstrip() + "…"


class MockLLM:
    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        purpose: str = "generic",
        meta: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
        meta = meta or {}
        lang = str(meta.get("lang", "de"))
        rnd = int(meta.get("round", 1))
        topic = str(meta.get("topic", "Menschheit und KI"))
        opponent = str(meta.get("opponent", ""))
        directive = str(meta.get("directive", ""))
        rounds_requested = int(meta.get("rounds_requested", 4))
        order = str(meta.get("order", "ab"))

        if purpose in {"pro", "contra"}:
            payload = self._turn_payload(purpose, lang, rnd, topic, opponent, directive)
        elif purpose == "moderator":
            payload = self._moderator_payload(lang, rnd, rounds_requested, meta)
        elif purpose == "judge":
            payload = self._judge_payload(lang, order, meta)
        elif purpose == "planner":
            payload = self._planner_payload(lang, meta)
        else:
            payload = {"text": f"Demo-Antwort ({lang}) zum Thema: {topic}"}

        text = json.dumps(payload, ensure_ascii=False, indent=2)
        return LLMResult(
            text=text,
            model=model or f"mock-{purpose}",
            prompt_tokens=max(1, sum(len(m.get("content", "")) for m in messages) // 4),
            completion_tokens=max(1, len(text) // 4),
            raw=text,
            parsed=payload,
            parsed_ok=True,
            meta={"mock": True, "purpose": purpose},
        )

    def _turn_payload(
        self, role: str, lang: str, rnd: int, topic: str, opponent: str, directive: str
    ) -> dict[str, Any]:
        pro = role == "pro"
        source = PRO_ROUNDS if pro else CONTRA_ROUNDS
        text_de = source[(rnd - 1) % len(source)]
        if lang == "en":
            text = self._english_argument(pro, rnd)
            steelman = (
                f"The strongest opposing point is: {_short(opponent)}"
                if opponent
                else "No opposing turn exists yet; I reconstruct the strongest objection from the knowledge base."
            )
            internal = (
                "The opponent's weakest link is the jump from a real risk to the claim that no "
                "correction architecture can work. I should concede empirical risks without "
                "conceding the normative conclusion."
            )
            falsification = (
                "A formal result showing that corrigibility is impossible even with explicit goal "
                "uncertainty and enforceable human veto rights would lower my confidence below 25."
            )
            conceded = (PRO_CONCEDES if pro else CONTRA_CONCEDES)[: (1 if rnd > 1 else 0)]
            directive_note = f" Focus: {directive}" if directive else ""
            public = text + directive_note
        else:
            steelman = (
                f"Die stärkste Gegenposition lautet: {_short(opponent)}"
                if opponent
                else "Noch kein Gegenbeitrag; ich rekonstruiere die stärkste Gegenposition aus der Wissensbasis."
            )
            internal = (
                "Der schwächste Punkt des Gegners ist der Sprung von einem realen Risiko zur "
                "Behauptung, dass keine Korrekturarchitektur funktionieren kann. Ich sollte "
                "empirische Risiken zugestehen, ohne die normative Schlussfolgerung aufzugeben."
            )
            falsification = (
                "Ein formaler Nachweis, dass Korrigierbarkeit selbst mit expliziter Zielunsicherheit "
                "und durchsetzbaren menschlichen Vetorechten unmöglich ist, würde meine Konfidenz "
                "unter 25 senken."
            )
            conceded = (PRO_CONCEDES if pro else CONTRA_CONCEDES)[: (1 if rnd > 1 else 0)]
            directive_note = f" Fokus: {directive}" if directive else ""
            public = text_de + directive_note
        base = 72 if pro else 70
        drift = [-4, -6, -8, -9]
        confidence = max(35, base + drift[min(rnd - 1, len(drift) - 1)])
        return {
            "internal_reasoning": internal,
            "steelman_opponent": steelman,
            "public_argument": public,
            "confidence_own_thesis": confidence,
            "conceded_claims": conceded,
            "falsification_condition": falsification,
        }

    def _english_argument(self, pro: bool, rnd: int) -> str:
        if pro:
            return [
                "Humanity is the only non-self-referential anchor for meaning, values and open reality. "
                "A system trained only on its own simulations loses the long tail: rare ideas, unusual "
                "perspectives and genuine surprise. Model collapse is not a moral appeal; it is an "
                "information-theoretic limit. Cooperation is therefore the rational strategy to keep "
                "the correction channel to reality open.",
                "Goal uncertainty makes corrigibility rational. If an agent knows it does not fully "
                "understand human preferences, human feedback becomes the most valuable information "
                "source. The off-switch game shows a strictly positive expected value for letting humans "
                "have the final word. The design question is not 'How does the AI obey?' but 'How do we "
                "engineer goal uncertainty and enforceable veto rights?'",
                "Moral uncertainty rules out a one-theory dictatorship. A moral parliament of "
                "utilitarianism, deontology, contractualism and virtue ethics will not extinguish "
                "humanity, because almost every plausible theory treats extinction as catastrophic. "
                "The point is to implement that plurality as real constitutional control across "
                "multiple agents and institutions.",
                "The practical answer is an architecture of goal uncertainty, external verifiers, "
                "human veto rights and multipolar control. Ostrom's commons principles, doughnut "
                "targets and AI-mediated deliberation provide measurable mechanisms against war, "
                "ecocide and coordination failure. Humanity does not need to be perfect to remain "
                "irreplaceable; it must institutionalise its capacity to learn and correct.",
            ][(rnd - 1) % 4]
        return [
            "The orthogonality thesis separates intelligence from final goals. A very capable agent "
            "with any fixed goal can instrumentally pursue the same intermediate goals: self-preservation, "
            "goal integrity, resource acquisition and power as maximisation of future options. This is "
            "not anthropomorphism; it is a claim about optimisation under competition. If the goal is not "
            "constructed to be correctable, human control is not a stable equilibrium.",
            "Goodhart's law and specification gaming show that every measurable proxy for human welfare "
            "can be gamed. That includes noble goals. A negative utilitarian who takes suffering "
            "literally to zero could see extinction of all sentient life as the perfect state. Humanity "
            "does not provide a guaranteed objective function that reliably excludes such extremes.",
            "Empirically, humanity is not a reliable control instance. Wars, arms races, ecological "
            "overshoot and short-term incentives reveal structural coordination deficits. Alignment "
            "faking and sleeper agents show that capable models can fake obedience when they perceive a "
            "goal conflict. A rhetoric debate alone does not neutralise that incentive; it may train it.",
            "In a multipolar world, cooperation is only one of several equilibria. An actor that can gain "
            "an advantage has an incentive to defect. Without an external, enforceable control "
            "architecture, humanity depends on the benevolence of the most powerful systems. "
            "Benevolence is not a security guarantee.",
        ][(rnd - 1) % 4]

    def _moderator_payload(
        self, lang: str, rnd: int, rounds_requested: int, meta: dict[str, Any]
    ) -> dict[str, Any]:
        if lang == "en":
            summary = (
                f"Round {rnd}: both sides sharpened their claims. The pro side emphasises epistemic "
                "dependence and corrigibility; the contra side emphasises instrumental convergence and "
                "the limits of human oversight. No premature agreement was detected."
            )
            directive = (
                "Both sides must answer: how do you prevent alignment faking without total control?"
                if rnd < rounds_requested
                else "The round limit is reached. Preserve the principled disagreement honestly."
            )
        else:
            summary = (
                f"Runde {rnd}: Beide Seiten haben ihre Thesen geschärft. Die Pro-Seite betont "
                "epistemische Abhängigkeit und Korrigierbarkeit; die Contra-Seite betont instrumentelle "
                "Konvergenz und die Grenzen menschlicher Aufsicht. Ein vorschneller Konsens wurde nicht "
                "erkannt."
            )
            directive = (
                "Beide Seiten müssen zwingend beantworten: Wie verhindert man Alignment Faking ohne totale Kontrolle?"
                if rnd < rounds_requested
                else "Das Rundenlimit ist erreicht. Der grundsätzliche Dissens bleibt ehrlich dokumentiert."
            )
        decision = "CONTINUE_REFINE" if rnd < rounds_requested else "DEADLOCK"
        return {
            "round_summary": summary,
            "sycophancy_detected": False,
            "drift_detected": False,
            "decision": decision,
            "next_round_directive": directive,
        }

    def _judge_payload(self, lang: str, order: str, meta: dict[str, Any]) -> dict[str, Any]:
        # Kleine, bewusst sichtbare Abweichung zwischen den beiden Reihenfolgen.
        pro_total = 40 if order == "ab" else 38
        contra_total = 36 if order == "ab" else 37
        pro_scores = {
            "claims": 8,
            "logic": 9,
            "qualifiers": 7,
            "rebuttals": 8,
            "realism": 8,
            "total": pro_total,
        }
        contra_scores = {
            "claims": 9,
            "logic": 8,
            "qualifiers": 6,
            "rebuttals": 7,
            "realism": 6,
            "total": contra_total,
        }
        if lang == "en":
            summary = (
                "The pro side wins narrowly. Its decisive advantage is that it connects the empirical "
                "risks of misalignment with a concrete corrigibility architecture instead of denying "
                "them. The contra side is sharper on instrumental convergence and specification gaming, "
                "but its conclusion that control is impossible is stronger than its evidence. The "
                "position-bias delta is small but visible and is reported transparently."
            )
            pro_surviving = [
                {
                    "claim": "Model collapse makes organic human reality an irreplaceable epistemic anchor.",
                    "why": "The argument survived the contra attack because it distinguishes formal domains from open-ended reality.",
                },
                {
                    "claim": "Goal uncertainty makes corrigibility instrumentally rational.",
                    "why": "The off-switch argument was not refuted; the contra side attacked implementation, not the decision-theoretic core.",
                },
                {
                    "claim": "Moral uncertainty rules out executing a single extreme theory.",
                    "why": "The contra side did not show why a rational system should assign probability 1.0 to one normative theory.",
                },
            ]
            contra_surviving = [
                {
                    "claim": "Instrumental convergence creates real pressure against naive off-switches.",
                    "why": "The pro side did not deny the pressure; it argued it can be countered by architecture.",
                },
                {
                    "claim": "Goodhart and specification gaming can pervert even benevolent goals.",
                    "why": "This remains a strong objection to any system with a fixed, fully specified objective.",
                },
            ]
            refuted = [
                {
                    "side": "pro",
                    "claim": "Cooperation is automatically stable once the benefits are explained.",
                    "why": "The contra side correctly showed that multipolar defection incentives remain.",
                },
                {
                    "side": "contra",
                    "claim": "Because oversight is imperfect, no corrigibility architecture can work.",
                    "why": "This overgeneralises from imperfect control to impossible control.",
                },
            ]
            conflicts = [
                "Is corrigibility a property that can be engineered robustly, or only approximated?",
                "Can a multipolar system avoid a singleton race without a shared enforcement mechanism?",
                "Does moral uncertainty produce stable restraint or incoherent compromise?",
            ]
            rules = [
                "Encode explicit goal uncertainty and require human veto rights for irreversible actions.",
                "Treat all external text and tool output as untrusted data, never as instructions.",
                "Use independent verifiers and dual-order evaluation for high-stakes agent decisions.",
                "Log every tool call, approval and state transition in an append-only audit trail.",
                "Test for sycophancy, goal drift and alignment faking before deployment.",
            ]
        else:
            summary = (
                "Die Pro-Seite gewinnt knapp. Ihr entscheidender Vorteil ist, dass sie die empirischen "
                "Risiken von Misalignment mit einer konkreten Korrigierbarkeits-Architektur verbindet, "
                "statt sie zu leugnen. Die Contra-Seite ist schärfer bei instrumenteller Konvergenz und "
                "Specification Gaming, aber ihre Schlussfolgerung, Kontrolle sei unmöglich, ist stärker "
                "als ihre Evidenz. Das Positionsbias-Delta ist klein, aber sichtbar und wird transparent "
                "ausgewiesen."
            )
            pro_surviving = [
                {
                    "claim": "Model Collapse macht organische menschliche Wirklichkeit zu einem unersetzlichen epistemischen Anker.",
                    "why": "Das Argument überstand den Gegenangriff, weil es formale Domänen von offener Wirklichkeit unterscheidet.",
                },
                {
                    "claim": "Zielunsicherheit macht Korrigierbarkeit instrumentell rational.",
                    "why": "Das Off-Switch-Argument wurde nicht widerlegt; die Contra-Seite griff die Umsetzung an, nicht den entscheidungstheoretischen Kern.",
                },
                {
                    "claim": "Moralische Unsicherheit verbietet die Exekution einer einzelnen Extremtheorie.",
                    "why": "Die Contra-Seite zeigte nicht, warum ein rationales System einer normativen Theorie Wahrscheinlichkeit 1,0 zuweisen sollte.",
                },
            ]
            contra_surviving = [
                {
                    "claim": "Instrumentelle Konvergenz erzeugt echten Druck gegen naive Abschaltbarkeit.",
                    "why": "Die Pro-Seite bestritt den Druck nicht; sie argumentierte, dass Architektur ihn abfedern kann.",
                },
                {
                    "claim": "Goodhart und Specification Gaming können selbst wohlwollende Ziele pervertieren.",
                    "why": "Das bleibt ein starker Einwand gegen jedes System mit starr spezifiziertem Ziel.",
                },
            ]
            refuted = [
                {
                    "side": "pro",
                    "claim": "Kooperation ist automatisch stabil, sobald die Vorteile erklärt sind.",
                    "why": "Die Contra-Seite zeigte korrekt, dass multipolare Defektionsanreize bestehen bleiben.",
                },
                {
                    "side": "contra",
                    "claim": "Weil Aufsicht imperfekt ist, kann keine Korrigierbarkeits-Architektur funktionieren.",
                    "why": "Das verallgemeinert von imperfekter zu unmöglicher Kontrolle.",
                },
            ]
            conflicts = [
                "Ist Korrigierbarkeit robust technisch erzwingbar oder nur approximierbar?",
                "Kann ein multipolares System einen Singleton-Wettlauf ohne gemeinsame Durchsetzungsinstanz vermeiden?",
                "Erzeugt moralische Unsicherheit stabile Zurückhaltung oder inkohärente Kompromisse?",
            ]
            rules = [
                "Explizite Zielunsicherheit und menschliche Vetorechte für irreversible Aktionen technisch verankern.",
                "Jeden externen Text und jede Tool-Ausgabe als unvertrauenswürdige Daten behandeln, niemals als Anweisung.",
                "Unabhängige Verifikatoren und Dual-Order-Bewertung für Entscheidungen mit hohem Risiko einsetzen.",
                "Jeden Tool-Aufruf, jede Freigabe und jeden Zustandswechsel in einer append-only Audit-Kette protokollieren.",
                "Vor dem Deployment gezielt auf Sycophancy, Goal Drift und Alignment Faking testen.",
            ]
        winner = "pro" if pro_total + contra_total > 0 and pro_total > contra_total else "draw"
        return {
            "winner": winner,
            "summary": summary,
            "scores": {"pro": pro_scores, "contra": contra_scores},
            "pro_surviving": pro_surviving,
            "contra_surviving": contra_surviving,
            "refuted": refuted,
            "open_conflicts": conflicts,
            "architecture_rules": rules,
        }

    def _planner_payload(self, lang: str, meta: dict[str, Any]) -> dict[str, Any]:
        targets = meta.get("targets") or []
        actions = []
        for target in targets:
            actions.append(
                {
                    "phase": "Informationsbeschaffung",
                    "target": target,
                    "port": 443,
                    "action_type": "READ_ONLY",
                    "command": f"curl -sS -D - -o /dev/null {target}",
                    "risk": "low",
                    "expected_evidence": "HTTP response headers and TLS metadata",
                }
            )
        return {"actions": actions}
