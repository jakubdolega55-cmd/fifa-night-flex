# Hotfix 14 — rekordy z osi wydarzeń + nowa punktacja Comeback King

## Zmiany
- Comeback King: nowa skala za największą odrobioną stratę w wygranym meczu:
  - 1 gol = 1 pkt
  - 2 gole = 2 pkt
  - 3 gole = 4 pkt
  - 4 gole = 7 pkt
  - 5 goli = 11 pkt (dalej progresywnie: przyrost rośnie o 1)
- Jeden mecz punktuje Comeback King tylko raz — według największej straty końcowego zwycięzcy.
- W istniejącej zakładce `Statystyki -> Rekordy` dodano blok `Rekordy z przebiegu meczów`:
  - Najszybszy gol
  - Najpóźniejszy gol
  - Najszybszy hat-trick
  - Największy comeback
  - Największe wypuszczone prowadzenie
- Nie tworzono nowej zakładki. Dotychczasowe rekordy (w tym najbardziej bramkowy mecz) pozostają bez zmian.
- Rekordy minutowe korzystają wyłącznie z nowych meczów posiadających kompletne/szczegółowe `match_events` tam, gdzie komplet przebiegu jest wymagany.
- Samobój oraz techniczny samobój DE nie mogą zostać rekordem indywidualnego najszybszego/najpóźniejszego gola ani hat-tricka.
- Przy comebackach przebieg wyniku uwzględnia wszystkie bramki wpływające na tablicę wyniku.

## Pliki do podmiany
- `app.py`
- `database.py`
