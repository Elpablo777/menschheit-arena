# Security Policy

## Meldung von Schwachstellen

Bitte keine öffentlichen Issues für Sicherheitslücken nutzen.

- Kontakt: `[security@example.com]` (bitte im eigenen Fork/Repo ersetzen)
- PGP-Key: `[optional, Fingerprint]`
- Erwartete Rückmeldung: innerhalb von 5 Arbeitstagen
- Koordinierte Veröffentlichung: nach Behebung, spätestens 90 Tage

## Geltungsbereich

Menschheit Arena ist eine Planungs- und Protokollebene. Sie führt keine offensiven Aktionen aus. Als Schwachstellen gelten insbesondere:

- Umgehung des Scope-Guards (Ziele außerhalb der Freigabe werden zugelassen)
- Ausführung von Aktionen ohne dokumentierte Freigabe
- Manipulierbarkeit der Audit-Kette über den vorgesehenen Weg hinaus
- Preisgabe von `LLM_API_KEY` oder `APP_ACCESS_TOKEN`
- XSS in der UI über Modell- oder Nutzereingaben
- SQL-Injection über API-Eingaben

Nicht als Schwachstelle gilt die bewusste Eigenschaft, dass Modelle falsche oder irreführende Ausgaben erzeugen können. Das ist ein Restrisiko, kein Fehler.

## Was wir nicht tun

Wir führen keine Tests gegen Systeme Dritter durch und erbitten solche auch nicht. Bitte teste nur gegen eigene Installationen.