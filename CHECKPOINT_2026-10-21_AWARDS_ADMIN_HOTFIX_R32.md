# CHECKPOINT — 2026-10-21 — R32 Awards admin hotfix

## Cel
Naprawa błędu Streamlit w Awards oraz uporządkowanie widoczności kontrolek administracyjnych po teście Gali.

## Zmiany
- naprawiono `NameError: award_owner_name is not defined` w `render_awards()`;
- dodano helper `award_owner_name()` dla nagród przypisanych do jednego gracza; nagrody par/drużyn nie są sztucznie przypisywane jednej osobie;
- `Reset gali / laureatów` jest widoczny po odblokowaniu panelu organizatora także wtedy, gdy `FIFA_GALA_TEST_MODE=0`;
- reset wymaga wpisania `RESET`, czyści wybory laureatów bieżącego sezonu i resetuje stan Gali, ale nie rusza meczów, statystyk, odznak ani historii;
- sekcja `Zakończ Sezon N` jest zawsze widoczna w panelu organizatora; dopóki Gala nie ma stanu `finished`, przycisk jest widoczny, ale zablokowany i pokazuje bieżący stan Gali;
- po `ZAKOŃCZ GALĘ` przycisk zakończenia sezonu odblokowuje się zgodnie z dotychczasową logiką.

## Testy
- `python -m py_compile app.py` — PASS
- `tests/awards_admin_controls_r32_smoke.py` — PASS
- `tests/gala_closeout_smoke.py` — PASS
- `tests/awards_season_close_smoke.py` — PASS
- `FIFA_GALA_TEST_MODE=1 python tests/gala_backend_smoke.py` — PASS
- `tests/gala_counters_smoke.py` — PASS
- `tests/mobile_api_smoke.py` — 52/52 PASS

## Uwaga operacyjna
Jeśli Gala jest obecnie na ekranie finałowym, ale nie kliknięto `ZAKOŃCZ GALĘ`, stan pozostaje `finale`. W takim stanie zamknięcie sezonu celowo jest nadal zablokowane.
