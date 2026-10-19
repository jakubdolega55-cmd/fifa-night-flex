# CHECKPOINT — R22 — Streamlit auto-detect + compact setup TV

Data: 2026-10-19
Baza: R21 / FIFA NIGHT FLEX 1.1.3 / Android versionCode 15

## Zmiany
- pasywny Streamlit sprawdza co 2 s identyfikator aktualnego turnieju; gdy telefon utworzy/resetuje turniej, pełny widok Streamlit sam się przeładowuje bez ręcznego F5;
- po wykryciu nowego turnieju widok publiczny wraca do LIVE/TV;
- dla faz przygotowania oficjalnego turnieju widok publiczny pomija duży hero i nawigację i od razu pokazuje TV SYNC;
- TV SYNC ma wariant compact: niższy iframe, mniejsze koło i mniejsze odstępy, aby koło było widoczne na ekranie laptopa bez dużego scrollowania;
- istniejący mechanizm 1 s setup watcher oraz 5 s LIVE / 30 s AUTO pozostaje;
- logika losowań, wagi R21 i mobile/PWA bez zmian.

## Testy
- `python -m py_compile app.py ui.py` — PASS (istniejący warning JS escape `\s` bez wpływu na działanie);
- `tests/streamlit_auto_tournament_compact_tv_smoke.py` — PASS;
- `tests/tv_partial_wheel_idle_source_smoke.py` — PASS;
- `tests/milestones_refresh_modes_smoke.py` — PASS;
- `tests/fc27_small_wheel_smoke.py` — PASS.

## APK
NIE. Zmiany dotyczą wyłącznie Streamlit/TV. Android pozostaje versionCode 15 z R20.
