# Hermes und Multi-Agenten-Bots

## Einordnung

„Hermes" bezeichnet hier eine Umgebung, in der mehrere Agenten/Bots als Diskutanten auftreten können – etwa eigene Bots, die über einen gemeinsamen Kanal sprechen. Menschheit Arena baut dafür **keinen eigenen Raum** und bringt keinen Hermes-Adapter mit. Die App ist bewusst ein abgeschlossener Prozess: zwei Positionen, ein Moderator, ein Richter.

Was stattdessen passiert: Alles, was Hermes oder ein Bot von außen braucht, ist über die REST-API erreichbar. Ein Bot kann eine Debatte anlegen, den Status pollen, das Ergebnis und den Markdown-Bericht abrufen.

## Anbindung

```bash
# Debatte starten (asynchron, 202)
curl -X POST http://127.0.0.1:8000/api/arena/debates \
  -H 'Content-Type: application/json' \
  -d '{"topic":"Sollte offene KI jenseits der EU reguliert werden?","rounds":4,"language":"de"}'

# Status
curl http://127.0.0.1:8000/api/arena/debates/<id>

# Bericht
curl http://127.0.0.1:8000/api/arena/debates/<id>/report.md
```

Mit `APP_ACCESS_TOKEN`:

```bash
curl -X POST ... -H 'X-App-Token: <token>' ...
```

## Wenn Hermes die Rollen selbst stellt

Dann ist Hermes der Anwender, nicht die Arena. Vorgehen:

1. In Hermes vier Modelle/Agenten für Pro, Contra, Moderator, Richter konfigurieren.
2. Die Prompt-Dateien aus `src/menschheit/prompts/<lang>/` als Vorlage übernehmen (sie sind bewusst knapp und fordern JSON).
3. Die Aufrufe über einen OpenAI-kompatiblen Proxy bündeln, damit ein Endpunkt vier Modelle bedient.
4. Ergebnisse in der Arena als Debatte spiegeln, wenn der Bericht gebraucht wird.

Die Arena selbst unterstützt genau eine Konfiguration pro Debatte. Vier Zeilen in der UI, vier Env-Variablen – nicht mehr. Das ist Absicht: Die Vergleichbarkeit der Läufe hängt an identischen Einstellungen.

## Grenzen der Integration

- Kein Streaming in die UI; Polling alle 1,4 s.
- Keine externen Trigger außer HTTP.
- Keine gegenseitige Authentifizierung zwischen Bots; das Token ist ein Shared Secret.
- Keine Wiederverwendung fremder Nachrichtenformate – der Parser erwartet JSON mit den dokumentierten Feldern, toleriert aber Alias-Namen (siehe `tests/test_parser.py`).

## Bewertung

Für den Zweck „Hermes als Diskussionsumgebung" ist die Arena die falsche Schicht. Für den Zweck „Hermes steuert eine Debatte, deren Verlauf und Ergebnis auditierbar sein soll", ist sie brauchbar. Wer mehr braucht – mehrere Räume, Rollen frei kombinierbar, WebSocket-Streams – baut das in Hermes und nutzt die Arena als Auswertungs- und Berichtsschicht.