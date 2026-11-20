# Sicherheit

## Prinzip

Die App ist eine Planungs- und Protokollebene. Sie führt keine offensiven Aktionen aus. Alles, was nach „Ausführen" aussieht, ist ein Vorschlag mit Status, Scope-Prüfung und Freigabevermerk.

## Scope-Guard

`sentinel/scope.py` entscheidet über jedes Ziel. Regeln:

- **Zielarten:** IP, CIDR, Domain, URL. Wildcards nur als `*.domain.tld`.
- **Öffentliche Ziele:** gesperrt, solange `ALLOW_PUBLIC_TARGETS=false`. Ein Host gilt als öffentlich, wenn er nicht in `{localhost, 127.0.0.0/8, 10/8, 172.16/12, 192.168/16, 169.254/16, ::1, fc00::/7, fe80::/10}` liegt oder auf eine der privaten Suffixe (`.local`, `.internal`, `.test`, `.localhost`, `.lan`, `.home`) endet.
- **Globale Wildcards:** `*`, `0.0.0.0/0`, `::/0` werden abgelehnt – auch mit `ALLOW_PUBLIC_TARGETS=true`.
- **Ports:** nur aus der Allowlist des Engagements. Ein URL-Eintrag `https://host` bindet implizit Port 443.
- **Credentials:** URLs mit `user:pass@` werden abgelehnt.
- **CIDR vs. Host:** Ein Netz-Eintrag erlaubt keine Hostnamen und ein Host-Eintrag kein Netz.
- **DNS-Rebinding:** Der Guard löst auf und prüft die aufgelöste IP gegen öffentliche Bereiche. Ein Hostname, der auf eine private Adresse zeigt, gilt als privat; zeigt er nach außen, greift die öffentliche Sperre.

Fehler sind `ScopeError` (Konfiguration) oder `ScopeDecision(allowed=False, reason=...)` (Prüfung).

## Freigaben

- `READ_ONLY`-Aktionen brauchen keine Freigabe, werden aber protokolliert.
- `ACTIVE_REQUIRES_APPROVAL` bleibt `proposed`, bis `POST /api/sentinel/actions/{id}/approve` mit Namen aufgerufen wird. Der Name ist Pflicht (min. 2 Zeichen), wird mit Zeitstempel gespeichert und im Audit-Log geführt.
- Reject braucht keinen Namen, einen Akteur und optional einen Grund.
- Ein Kill-Switch setzt alle `proposed` und `approved` Aktionen auf `rejected`, schreibt ein Audit-Event und blockiert weitere Planung.

## Token

`APP_ACCESS_TOKEN` schützt alle schreibenden API-Aufrufe. Header `X-App-Token` oder `Authorization: Bearer <token>`. GET bleibt offen, damit die UI ohne Login startet. Bei Bindung an eine nicht-lokale Adresse ohne Token warnt `menschheit doctor`.

Das Token ist ein Shared Secret, kein Benutzerkonto. Für Mehrbenutzerbetrieb gehört hier ein echtes Auth-System vor.

## Audit

Append-only, hash-verkettet, global über `seq`. Die Kette wird bei jeder Statusänderung fortgeschrieben. `verify_audit_chain()` läuft in `doctor`, in jedem Engagement-Detail und in Tests.

## Eingaben

- Pydantic mit `extra="forbid"` auf allen Schreib-Endpunkten.
- Längen- und Bereichslimits (Thema ≥ 8 Zeichen, Ports 1–65535, RoE ≥ 50 Zeichen).
- SQL ausschließlich parametrisiert.
- UI escaped alle dynamischen Werte; keine `innerHTML`-Zusammenstellung aus Modelltext ohne `escapeHtml`.
- LLM-Antworten werden als JSON geparst, nie evaluiert. Reparaturversuche laufen über einen zweiten Modellaufruf mit Fehlermeldung, nicht über Code.

## Prompt-Injection

Modellausgaben sind Daten, keine Anweisungen. Der Moderator-Prompt weist darauf hin. Trotzdem gilt: Ein Modell kann versuchen, den Richter zu beeinflussen. Gegenmaßnahmen in v0.1: Dual-Order, Toulmin-Trennung, Bias-Delta, harte Konfidenz-Gates. Das reduziert Risiko, beseitigt es nicht.

## Was v0.1 nicht kann

Keine Sandbox, keine Rate-Limits, keine Mandanten-Isolation, keine Verschlüsselung at rest, keine Anbindung an SIEM, keine Exe­cution. Wer die App exponiert, braucht einen Reverse-Proxy mit TLS, Auth und Logging davor.

## Meldeweg

Bei Sicherheitsbefunden bitte nicht über öffentliche Issues, sondern über das Security-Kontakt in `SECURITY.md`.