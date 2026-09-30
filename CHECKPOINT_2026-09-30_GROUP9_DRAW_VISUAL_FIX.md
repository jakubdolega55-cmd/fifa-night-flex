# CHECKPOINT 2026-09-30 — GROUP9 DRAW VISUAL FIX

## Zmiana
Naprawiono wizualizację losowania Streamlit dla formatów 9-osobowych:
- `groups9_final4`
- `groups9_barrage_final3`
- `groups9_top8`

Układ: 3 grupy (A/B/C) po 3 miejsca. Sekwencja odkrywania: A1, B1, C1, A2, B2, C2, A3, B3, C3.

Dodatkowo dodano brakujący layout `groups10_sf` (2 grupy po 5), aby ten sam błąd nie wystąpił przy 10 graczach.

## Testy
- `python -m py_compile ui.py` — PASS
- izolowany test `_draw_layout` przez AST dla wszystkich trzech `groups9_*` — PASS
- `groups10_sf` — PASS

## Deploy
Backend/API i mobile nie są zmieniane. Do GitHuba wystarczy podmienić `ui.py` i zredeployować Streamlit.
Nowy APK nie jest potrzebny.
