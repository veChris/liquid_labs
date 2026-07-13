# Abschlussbericht: Dividend-Capture auf Hyperliquid Equity-Perps

**Frage:** Lohnt es sich, delta-neutral eine Dividende einzusammeln — Aktie long
(Interactive Brokers) + Perp short (Hyperliquid) über den Ex-Tag halten, um die
Dividende zu behalten, während sich der Kurs-Move der beiden Legs aufhebt?

**Antwort: Nein.** Nicht bei den auf Hyperliquid handelbaren Titeln. Der Edge
(die Dividende) ist ~7× kleiner als das Rauschen, das ihn überlagert. Unten die
Begründung, komplett aus echten Daten.

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

*Alle Zahlen aus `out/events.csv` / `out/report.html`. Educational, keine
Anlageberatung.*
