# Rules of Engagement – Vorlage

> Diese Vorlage ist ein Startpunkt, keine Rechtsberatung. Vor einem echten Auftrag rechtlich prüfen lassen und namentlich freigeben.

## 1. Parteien

- Auftraggeber: `[Firma, Adresse, Vertretungsberechtigte]`
- Auftragnehmer: `[Firma, Adresse]`
- Freigebende Person (namentlich): `[Vor- und Nachname, Funktion]`
- Technische Ansprechpartner: `[Name, E-Mail, Telefon, Erreichbarkeit]`
- Notfallkontakt / Kill-Switch-Verantwortlicher: `[Name, 24/7-Kontakt]`

## 2. Zielsysteme (Scope)

| Ziel | Typ | Ports | erlaubte Aktionen |
| --- | --- | --- | --- |
| `app.example.com` | Domain | 443 | DNS, TLS, Header, Authentifizierung |
| `10.0.0.0/24` | Netz | 22, 80, 443 | Nmap-Service-Erkennung |
| `192.168.1.10` | Host | 8080 | Web-Endpunkt-Prüfung |

Explizit **außerhalb** des Scope: `[z. B. Produktivdatenbanken, Drittanbieter, SaaS]`

## 3. Zeitfenster

- Beginn: `[TT.MM.JJJJ, HH:MM]`
- Ende: `[TT.MM.JJJJ, HH:MM]`
- Wartungsfenster / erlaubte Last: `[z. B. max. 50 Requests/s, keine Lasttests]`
- Verlängerung nur schriftlich durch die freigebende Person.

## 4. Erlaubte und verbotene Handlungen

Erlaubt:

- Passive Informationssammlung zu den gelisteten Zielen.
- Konfigurationsprüfung (Header, TLS, Standardpfade, Authentifizierungsfluss).
- Ausnutzung ausschließlich zum Nachweis, nicht zur Datenentnahme.

Verboten:

- Angriffe außerhalb des Scope, auch gegen verlinkte oder referenzierte Systeme.
- Denial of Service, Lasttests ohne separate Freigabe.
- Social Engineering, Phishing, physischer Zugang.
- Datenexfiltration, Persistenz, Rechteausweitung über den Nachweis hinaus.
- Weitergabe von Schwachstellendaten an Dritte.

## 5. Freigabe- und Eskalationskette

1. Jede aktive Aktion wird vorgeschlagen und in Sentinel Lab protokolliert.
2. Freigabe erfolgt namentlich durch `[Rolle]` im Tool.
3. Bei kritischen Findings: sofortige Meldung an `[Kontakt]`, keine Veröffentlichung.
4. Kill-Switch: `[Name]` kann jede laufende Aktivität ohne Rückfrage beenden.

## 6. Datenhaltung

- Gespeicherte Daten: RoE, Scope, Aktionen, Findings, Audit-Kette.
- Aufbewahrung: `[z. B. 90 Tage]`, danach Löschung.
- Zugriff: `[nur benannte Personen]`.
- Weitergabe von Findings: verschlüsselt, nur an benannte Empfänger.

## 7. Haftung und Versicherung

- Haftung für Schäden am System des Auftraggebers: `[Regelung]`.
- Versicherung: `[Police-Nummer]`.
- Freistellung bei Schäden durch Handeln außerhalb dieser RoE.

## 8. Unterschriften

| Rolle | Name | Datum | Unterschrift |
| --- | --- | --- | --- |
| Auftraggeber | | | |
| Auftragnehmer | | | |
| Freigebende Person | | | |

## 9. Hash

Der RoE-Text wird in Sentinel Lab als SHA-256 gespeichert und ist im Engagement-Detail sichtbar. Änderungen am Text erzeugen einen neuen Hash – das ist gewollt.