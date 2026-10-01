# CHECKPOINT — MILESTONES + STREAMLIT REFRESH RULE — 2026-10-01

## Zmiany
- Dodane globalne kamienie milowe:
  - pierwszy zarejestrowany samobój,
  - pierwsza zarejestrowana czerwona kartka,
  - pierwszy zarejestrowany gol w dogrywce.
- Kolejne progi pozostają bez zmian: samobóje 10/25/50/100, czerwone 5/10/25/50, gole w dogrywce 25/50/100/200.
- Liczniki „następny kamień” zaczynają teraz od 1 dla tych trzech kategorii.

## Streamlit refresh — potwierdzona reguła
- przygotowanie i losowanie przed startem turnieju: 1 s (`render_setup_tv_watch`),
- po starcie turnieju LIVE: 5 s,
- po starcie turnieju AUTO: 30 s (zmiana slajdu również co ok. 30 s).
- W tej części nie zmieniano logiki, tylko dodano test regresyjny potwierdzający wymagane wartości.

## Testy
- `tests/milestones_refresh_modes_smoke.py` — PASS
- `tests/live_schedule_display_order_smoke.py` — PASS
- `tests/versioning_alias_smoke.py` — PASS
- `python -m py_compile database.py app.py` — PASS

## APK
NIE z powodu tego patcha. Zmiana kamieni milowych jest backendowa, a zachowanie refreshu Streamlit nie wymaga zmiany mobilnego UI.
