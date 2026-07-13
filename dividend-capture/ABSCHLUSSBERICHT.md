# Abschlussbericht: Dividend-Capture auf Hyperliquid Equity-Perps

**Frage:** Lohnt es sich, delta-neutral eine Dividende einzusammeln — Aktie long
(Interactive Brokers) + Perp short (Hyperliquid) über den Ex-Tag halten, um die
Dividende zu behalten, während sich der Kurs-Move der beiden Legs aufhebt?

**Antwort: Als naiver Zeit-Trade nein — als basis-disziplinierte Limit-Order-
Strategie vielleicht.** Bei fester Ein-/Ausstiegszeit ist der Edge (die Dividende)
~7× kleiner als das Rauschen (Basisrisiko), das ihn überlagert → Glücksspiel.
Geht man aber nur rein/raus, wenn Perp ≈ Aktie (Basis ~0), bricht die Streuung um
das 4-Fache ein und alle Events werden positiv (siehe §5b) — allerdings nur als
optimistische Obergrenze, deren Umsetzbarkeit an der Fill-Qualität hängt. Unten
die Begründung, komplett aus echten Daten.

---

## 1. Datengrundlage

- **Dividenden + Aktienkurse:** Yahoo Finance (Ex-Daten, Beträge, tägliche OHLC)
- **Perp Mark-Price + Funding:** Hyperliquid `info`-API, HIP-3 Equity-Dex `xyz`
  (`xyz:MSFT`, `xyz:AAPL`, …), stündliche Candles + Funding-History
- **Betrachtet:** 8 Ex-Dividenden-Events mit Perp-Coverage (MSFT, AAPL, NVDA,
  GOOGL, jeweils Feb + Mai/Jun 2026), Notional $100k, 15 % Quellensteuer,
  Maker-Fills (2×3 bps/Leg), Halten Cum-Close → Ex-Open.

Reproduzierbar über `python3 run.py`; Rohdaten gecacht.

---

## 2. Kernergebnisse (die entscheidenden Zahlen)

| Kennzahl | Wert |
|---|---|
| Ø Dividendenrendite der Titel | **0,11 %** (Spanne 0,01–0,23 %) |
| Ø Netto-Dividende, die man einsammeln will | **+$94** / $100k / Event |
| Ø tatsächliches Netto-Ergebnis | +$294 / $100k |
| **Streuung (StdAbw) des Ergebnisses** | **$687** / $100k |
| Spanne der Einzelergebnisse | **−$649 bis +$1.355** |
| Trefferquote (> 0) | 5 von 8 |
| **Rausch/Signal-Verhältnis** | **7,3×** |

> **Die eine Zahl, die alles sagt:** Der Edge, den du verdienen willst, ist
> **$94**. Die Zufallsschwankung pro Trade ist **$687** — das **7,3-Fache**.
> Du wettest um 94 Dollar und riskierst dabei ±687.

---

## 3. Warum es sich nicht lohnt — fünf Gründe

### 3.1 Das Signal ist zu klein
Die Dividende der handelbaren Titel liegt bei 0,1–0,23 % des Kurses. Der normale
Übernacht-Move von Aktie **und** Perp liegt bei 0,5–1 %+. Das, was du einsammeln
willst, ist kleiner als das tägliche Grundrauschen. Bei NVDA ($0,01 Dividende)
ist der Effekt buchstäblich ein Rundungsfehler.

### 3.2 Das Basisrisiko lässt sich nicht weghedgen
Der Kurs-Move hebt sich **nur, soweit Perp und Aktie identisch laufen**. Tun sie
aber nicht: Die Aktie handelt 6,5 h/Tag, der Perp 24/7. Über die Ex-Nacht friert
die Aktie ein, der Perp läuft weiter — und macht den Ex-Open-Gap **nicht**
identisch mit. Beispiel MSFT 21.05.: Aktie **+3,69**, Perp **−1,54** im selben
Fenster. Was übrig bleibt (der „Basis-Rest") war −$649 bis +$1.355 — ein
Vielfaches der Dividende.

### 3.3 „Beide gleichzeitig schließen" hilft nicht
Gleichzeitiges Schließen entfernt nur das *Legging-Risiko* (ein Bein vor dem
anderen). Es entfernt **nicht** die Tatsache, dass sich Perp und Aktie
**während** des Haltens unterschiedlich bewegt haben. Zum Ausstiegszeitpunkt
stehen sie an verschiedenen Preisen (Basis), und diese Differenz ist real —
egal wie synchron du auf „schließen" drückst.

### 3.4 „Früher rein, später raus" macht es schlechter
Getestet über Fenster von 1 bis 20 Handelstagen: Die Dividende bleibt ein
**einmaliger** Fixbetrag (~$94), egal wie lange man hält. Länger halten
*mittelt das Rauschen nicht weg* — die Basis ist nicht verlässlich
mean-reverting, man zieht nur zwei zufällige Stichproben weiter auseinander.
Gleichzeitig **wächst das Funding** mit der Haltedauer (bei 20 Tagen bis −$795,
also 4× die Dividende). Mehr Zeit = gleiches Signal + mehr Kosten + mehr
Rauschen. Strikt schlechter.

### 3.5 Kosten und Funding-Clawback
Fees sind ein sicherer Abzug von ~$0,25/Aktie (2×3 bps/Leg als Maker; als Taker
2×9 bps → dreifach). Dazu kommt der Marktmechanismus: Erwartet der Markt den
Ex-Drop, shorten alle den Perp vorab → Perp handelt mit Discount → Funding wird
negativ → **der Short zahlt** → die Dividende wird über Funding zurückgeholt. In
einem effizienten Markt ist das genau der Kanal, der den Edge auf null zieht.

---

## 4. Statistisches Urteil

Selbst wenn der Erwartungswert leicht positiv wäre (+$94 Netto-Dividende), ist er
in einer Streuung von ±$687 nicht von null zu unterscheiden. Um so ein Signal aus
dem Rauschen zu holen, bräuchte man **hunderte** unabhängige Events
(N ≈ (7,3)² ≈ 53 Trades allein für 1σ Signifikanz, realistisch ein Vielfaches).
Es gibt aber nur **4 Ex-Termine pro Titel und Jahr**. Die Statistik konvergiert
nie schnell genug, um den Mini-Edge sicher zu ernten — man handelt de facto reines
Basis-Rauschen mit einem Hauch Drift.

---

## 5. Wann es sich lohnen *würde*

Die Strategie ist konzeptionell sauber — sie scheitert nur an der Größenordnung.
Sie würde tragen, wenn **alle** folgenden Bedingungen zusammenkämen:

1. **Dividendenrendite ≥ 1,5–2 %** — erst dann ist das Signal größer als die
   ~0,5–1 % Basis-Noise. (Big-Tech-Perps auf HL zahlen alle < 0,3 % → fällt aus.)
2. **Perp bildet den Ex-Drop sauber ab** und Funding holt ihn nicht zurück —
   empirisch pro Titel zu prüfen, nicht anzunehmen.
3. **Maker-Fills** und **minimale Haltedauer** (nur die eine Ex-Nacht).
4. **Enges Perp-zu-Aktie-Tracking** (kleiner, stabiler Basis-Spread) — sonst
   frisst der Basis-Rest den Dividenden-Edge.

Auf dem aktuellen `xyz`-Dex ist Bedingung 1 für keinen der Big-Tech-Namen
erfüllt.

---

## 5b. Revision: Mit Basis-Disziplin wird es handelbar (Obergrenze)

Der naive Ansatz (fixe Uhrzeit, Cum-Close → Ex-Open) ist eine **Wette auf die
Basis**. Ändert man nur *eine* Sache — man geriert nur rein und raus, **wenn Perp
≈ Aktie** (Basis ~0, per Limit-Order) — passiert Folgendes über die 9 abgedeckten
Events:

| | Naiv (Ex-Open) | Basis-diszipliniert |
|---|---|---|
| Ø Ergebnis / $100k | +$219 | +$246 |
| **StdAbw (Streuung)** | **$683** | **$158** |
| **Trefferquote** | **5 / 9** | **9 / 9** |

Der Erwartungswert bleibt fast gleich — aber die **Streuung bricht um das
4-Fache ein** und **jedes** Event wird positiv. Der Grund folgt direkt aus der
P&L-Formel `P&L = (Basis_aus − Basis_ein) + Netto-Div − Funding − Fees`: legt man
beide Basiswerte auf ~0, verschwindet der Zufallsterm und übrig bleibt die saubere
Dividende minus Kosten.

**Aber — der entscheidende Vorbehalt:** Diese Spalte ist eine **optimistische
Obergrenze**. Das Modell wählt den Snapshot mit minimaler |Basis| *im Nachhinein*
aus Tages-Open/-Close-Punkten. In der Praxis:

- Du kannst einen Basis-≈0-Fill **nicht garantieren** — die Limit-Order füllt
  vielleicht nicht im nötigen Zeitfenster.
- Musst du am Ex-Tag zwingend raus und die Basis steht gerade −0,7 (wie beim
  ersten STRC-Open), zahlst du drauf.
- Reale Slippage frisst einen Teil des Edges.

**Die korrekte Schlussfolgerung ist also nuancierter als „lohnt sich nicht":**
Als **fixe Zeit-Trade** (naiv) ist die Strategie ein Glücksspiel und lohnt nicht.
Als **basis-disziplinierte Limit-Order-Strategie** *kann* sie ein echter, wenn
auch dünner Dividenden-Harvester sein (Ø +0,25 %/Event, geringe Streuung) — die
Umsetzbarkeit hängt komplett davon ab, ob du verlässlich Basis-≈0-Fills an beiden
Enden bekommst. Das ist die eigentliche offene Frage für die Praxis, nicht die
Dividende selbst.

## 6. Fazit

> Delta-neutrale Dividend-Capture auf Hyperliquid-Equity-Perps ist **kein
> Dividenden-Edge, sondern ein Basis-Glücksspiel**. Der Gewinn, den man
> einsammeln will (~0,1 % / ~$94 je $100k), ist um das **7-Fache** kleiner als
> die unvermeidbare Schwankung des Perp-gegen-Aktie-Basisrisikos (±$687). Weder
> gleichzeitiges Schließen noch längeres Halten lösen das Problem — Ersteres
> ändert nichts an der Divergenz, Letzteres erhöht nur Kosten und Rauschen. Der
> Aufwand (zwei Broker, Übernacht-Risiko, Liquidationsgefahr bei gehebeltem
> Short) steht in keinem Verhältnis zu einem Erwartungswert, der statistisch
> nicht von null zu trennen ist.

**Empfehlung:** Strategie in dieser Form nicht handeln. Falls weiterverfolgt,
zuerst auf Titeln mit **echter, fetter Dividende (≥ 1,5 %)** und dokumentiertem,
sauberem Perp-Tracking testen — sonst ist es teures Rauschen.

---

## Addendum: STRC (Strategy „Stretch"-Vorzugsaktie) — der einzige Kandidat

STRC ist auf dem `xyz`-Dex gelistet und ist strukturell der beste Kandidat:
**monatliche Dividende ~$0,96 auf ~$87 = ~1,1 %/Monat (~13 % p.a.)**, also
5–10× die Big-Tech-Rendite und **12 statt 4 Events/Jahr**.

**Aber es reicht (noch) nicht:**

- **Perp zu neu:** Coverage erst ab 22.06.2026 (~3 Wochen, 500 Std). Nur **ein**
  Ex-Termin (30.06.) ist backtestbar — statistisch wertlos.
- **Das eine Event verlor Geld:** STRC fiel $83,67 → $80,99 (**−3,2 %**) bei nur
  $0,48 Dividende. Full net **−$390** / $100k.
- **Kein stabiles Par-Papier:** trotz $100-Ziel lief STRC über das Jahr
  $74,57–$100,07 (25 % Spanne), Tages-Vola **1,38 %/Tag**. Damit ist selbst die
  fette 1,1%-Dividende nur **~0,8× so groß wie der Übernacht-Move** — Signal/Noise
  weiter unter 1 (Big Tech lag bei ~0,2×).

**Einordnung:** STRC ist ~4× besser als Big Tech, aber pro Event immer noch nicht
über der Schwelle. Der einzige Hoffnungsträger ist die **Basis-Stabilität**: beim
einen Event fielen Aktie (−$2,68) und Perp (−$2,13) fast im Gleichschritt, der
Basis-Rest war klein. Wenn der Perp STRC eng trackt, *könnte* die 1,1%-Dividende
delta-neutral durchkommen. Das lässt sich aber erst mit 4–6 abgedeckten Terminen
seriös messen.

**Empfehlung STRC:** beobachten, nicht handeln. STRC ist ab sofort in der
Default-Tickerliste (`run.py`) — das Modell sammelt mit jedem Monatstermin
automatisch mehr Daten. In ~4–6 Monaten erneut auswerten; erst dann ist ein
Urteil über die Basis-Stabilität möglich.

---

*Alle Zahlen aus `out/events.csv` / `out/report.html`. Educational, keine
Anlageberatung.*
