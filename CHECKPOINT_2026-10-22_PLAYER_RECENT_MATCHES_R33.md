# CHECKPOINT — 2026-10-22 — R33 historia ostatnich meczów gracza

## Cel
Dodać do profilu gracza szybki podgląd ostatnich oficjalnych meczów bez przechodzenia do globalnej Historii.

## Zmiany
- profil gracza zwraca teraz do 15 ostatnich oficjalnych meczów zamiast 10;
- każdy wpis ma kontekst rozgrywek: `FIFA Night #N`, `FIFA Night (w toku)` albo `1 VS 1`;
- wynik jest dostępny również z perspektywy wybranego gracza (`player_score`), więc przy grze jako away nie jest odwrócony;
- wpis zawiera rywala, drużynę gracza, drużynę rywala, fazę, numer meczu i datę;
- jeśli dla meczu istnieje zaufany Summary, historia zawiera xG, strzały, posiadanie i faule dla gracza oraz rywala;
- jeśli istnieją Events, historia zawiera zapisaną oś zdarzeń (gole, karne, kartki, kontuzje, zmiany; techniczny samobój DE jest pomijany);
- mobile/PWA: nowa karta `Ostatnie mecze` w profilu z przełącznikiem 5 / 10 / 15 i rozwijaniem konkretnego meczu;
- Streamlit: sekcja `Ostatnie mecze` ma przełącznik 5 / 10 / 15, tabelę oraz rozwijane szczegóły każdego spotkania;
- stare mecze bez Summary/Events nadal są widoczne; w szczegółach pokazują informację o braku tych danych.

## Testy
- `python -m py_compile database.py app.py mobile_api.py` — PASS
- `tests/player_recent_matches_r33_smoke.py` — PASS
- `tests/achievement_badges_r27_smoke.py` — PASS
- `tests/records_summary_turnaround_r28_smoke.py` — PASS
- `tests/achievement_badge_details_r29_smoke.py` — PASS
- `tests/achievement_badge_context_r30_smoke.py` — PASS
- `tests/achievement_categories_profile_r31_smoke.py` — PASS
- `tests/gala_closeout_smoke.py` — PASS
- `tests/awards_season_close_smoke.py` — PASS
- `tests/mobile_api_smoke.py` — 52/52 PASS
- transpile `mobile/src/StatsScreen.tsx` przez TypeScript — PASS

## Zakres
Nie zmieniono zasad turniejów, statystyk all-time, Awards, Gali, odznak ani Android `versionCode` (pozostaje 15).
