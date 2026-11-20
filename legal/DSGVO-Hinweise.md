# DSGVO-Hinweise

> Keine Rechtsberatung. Vor Produktivbetrieb mit Datenschutzbeauftragtem abstimmen.

## Datenverarbeitung in dieser App

| Datenkategorie | Beispiel | Zweck | Speicher |
| --- | --- | --- | --- |
| Debatteninhalte | Thema, Argumente, interner Gedankengang | Auswertung, Bericht | SQLite/Postgres, `turns`, `debates` |
| Modell-Metadaten | Modellname, Token-Zahl, Zeitstempel | Nachvollziehbarkeit | Datenbank |
| Sentinel-Daten | Scope, Aktionen, Findings | Auftrag, Audit | Datenbank |
| Audit-Kette | Akteur, Ereignis, Payload | Manipulationsschutz | Datenbank |
| Personenbezogen | Freigebender Name, Kontakt | Nachweis, RoE | Datenbank |

## Rechtsgrundlagen (Orientierung)

- Vertrag/Erfüllung: Verarbeitung zur Durchführung des Auftrags.
- Berechtigtes Interesse: Manipulationsschutz, Sicherheitsnachweis.
- Einwilligung: nur falls freiwillig, z. B. bei Weitergabe von Modell-Outputs an Dritte.

## Betroffenenrechte

Auskunft, Berichtigung, Löschung, Einschränkung, Widerspruch. Löschung wird durch die append-only Audit-Kette erschwert: Ein Audit-Eintrag kann nicht stillschweigend entfernt werden. Löschkonzept daher vorab definieren – z. B. Löschung nach Ablauf der Frist inklusive Audit-Archiv oder unverifiable Löschung des gesamten Engagements.

## Auftragsverarbeitung

Wird ein externer Modell-Anbieter mit personenbezogenen Daten betrieben, ist ein AVV nötig. Modelle, die für Trainingszwecke des Anbieters genutzt werden könnten, sind für personenbezogene Inhalte ungeeignet. Lokale Modelle (Ollama) vermeiden den Transfer.

## Technische Maßnahmen (Beispiele)

- TLS vor dem Reverse-Proxy.
- `APP_ACCESS_TOKEN` für Schreibzugriffe.
- Keine Secrets in der Datenbank, keine Keys im Report.
- Reports enthalten Modellnamen und Argumente – vor Weitergabe prüfen.
- Zugriff auf Server und Datenbank beschränken.
- Backups verschlüsselt lagern.

## EU AI Act

Die Arena erzeugt Text mit KI und gibt ihn als Debattenbeitrag aus. Das fällt unter Transparenzpflichten: Nutzer müssen erkennen können, dass sie mit einem KI-System interagieren. In dieser App ist das über den sichtbaren Demo-/Live-Badge und den Hinweis im Bericht gelöst. Wer die App in einen größeren Dienst einbettet, muss die Kennzeichnung dort erneut vornehmen.

Sentinel Lab trifft keine Einstellungs- oder Kreditentscheidungen und ist damit nicht Hochrisiko-System im Sinne des AI Act. Eine rechtliche Einzelfallprüfung bleibt nötig.