# CHECKPOINT — SECOND YELLOW RED STATS / MILESTONE — 2026-10-01

## Problem
EA FC 27 może pokazać wyrzucenie zawodnika wyłącznie jako dwie żółte kartki w tym samym meczu. FIFA Night już poprawnie tworzył z tego jedną pauzę `second_yellow_red`, ale liczniki/statystyki nadal widziały 0 czerwonych kart.

Skutek: jeśli pierwsze wykluczenie w historii nastąpiłoby po drugiej żółtej, kamień **„Pierwsza zarejestrowana czerwona kartka”** nie zostałby zdobyty.

## Zmiana
- dwie żółte tego samego piłkarza w jednym meczu są w warstwie statystyk liczone dodatkowo jako **1 czerwona / 1 wykluczenie**,
- surowe `match_events` pozostają bez zmian: nadal zapisujemy dwie żółte, nie dopisujemy sztucznego eventu `red_card`,
- jeśli dla tego samego piłkarza/meczu istnieje już bezpośredni event `red_card`, nie dokładamy drugiej czerwonej,
- pauza nadal jest tylko jedna (`second_yellow_red`), bez podwójnej kary.

Poprawka obejmuje:
- live dashboard turnieju,
- szczegółowe statystyki gracza,
- globalne kamienie milowe i ich liczniki,
- endpoint milestones automatycznie korzysta z poprawionych danych.

## Testy
PASS:
- `second_yellow_red_counters_smoke.py` — 2 żółte = 2 yellow + 1 red + pierwszy kamień czerwonej,
- `milestones_refresh_modes_smoke.py`,
- `manual_event_scorer_draw_smoke.py`,
- `summary_last_team_yellow_smoke.py`,
- `mobile_api_smoke.py` — **51/51**.

## APK
**NIE.** Zmiana jest backend/database logic only. API shape i mobile UI bez zmian.
