# FIFA NIGHT FLEX — NEXT / DYNAMIC SCHEDULE / TV REFRESH HOTFIX — 2026-10-01

Base: `FIFA-NIGHT-1.1.3-V14-POLISHED-FIT-SCRIPT-HOTFIX-2026-10-01.zip`

## Zakres

1. **NEXT = ten sam scheduler co terminarz**
   - nowe `Database.visible_next_match_from()` jest wspólnym źródłem dla Streamlit i API,
   - GROUP/LEAGUE używa projekcji po zapisaniu bieżącego wyniku,
   - fazy pucharowe zachowują zwykły next-ready, bo wynik może dopiero odblokować nową parę.

2. **Dynamiczne publiczne M1 / M2 / M3...**
   - techniczne `match_no` w DB i zależnościach drabinki pozostaje bez zmian,
   - `display_match_no` jest wyłącznie numerem prezentacyjnym,
   - rozegrane mecze są numerowane według rzeczywistej kolejności gry,
   - przyszła część terminarza zmienia kolejność i numery, gdy scheduler zmienia preferowaną kolejkę,
   - drzewko DE nadal pokazuje techniczne numery, żeby zależności bracketu były czytelne i bezpieczne.

3. **Streamlit TV refresh**
   - LIVE: fragment odświeża się co 5 s,
   - AUTO: fragment odświeża się co 30 s,
   - usunięto wcześniejszy rerun całego TV co 1 s.

## Pliki zmienione

- `database.py`
- `app.py`
- `mobile_api.py`
- `mobile/src/FifaScreen.tsx`
- `mobile/src/types.ts`
- `tests/live_schedule_display_order_smoke.py` (nowy test)

## Testy wykonane

- `python -m py_compile app.py database.py mobile_api.py` — PASS
- `python tests/live_schedule_display_order_smoke.py` — PASS
- `PYTHONPATH=. python tests/next_match_projection_smoke.py` — PASS
- `PYTHONPATH=. python tests/smart_scheduler_smoke.py` — PASS

Celowany test odtwarza przypadek, w którym przed wynikiem naiwny NEXT wskazywał M5, ale po zapisaniu bieżącego meczu scheduler wybierał M7. Po hotfixie NEXT i terminarz wskazują tę samą kolejność, a publiczne numery są nadawane według kolejności gry.

## APK

Zmiana dotyka PWA/APK (`FifaScreen.tsx`, `types.ts`), więc aby zobaczyć dynamiczne numery M w zainstalowanej aplikacji Android, potrzebny jest build APK. Według handoffu V14 nie był jeszcze fizycznie zbudowany/zainstalowany po poprzednich zmianach, więc `versionCode` może pozostać **14** i ten hotfix może wejść do pierwszego buildu V14.

## Poza zakresem

Lokalne herby/flagi NIE są częścią tego hotfixa. Robimy je jako osobny następny etap.
