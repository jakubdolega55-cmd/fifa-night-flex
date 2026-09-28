# FIFA Night Flex — checkpoint 2026-09-28

## Zakres łatki

1. **Supersnajper Roku / Król Strzelców FIFA Night**
   - Awards używają tej samej kanonizacji nazwisk co główna klasyfikacja strzelców.
   - Historyczne skróty typu `B. Saka` + `Bukayo Saka`, `H. Kane` + `Harry Kane`, `M. Ødegaard` + `Martin Ødegaard` łączą się, jeśli roster daje jednoznaczne dopasowanie.
   - Łączone są także gole, mecze z golem, hat-tricki i progress gali.

2. **Król Końcówek / najpóźniejszy gol**
   - Usunięto dokładny rekord / tie-break „najpóźniejszy gol”, bo FC27 może pokazywać gole doliczonego czasu wyłącznie jako `90'`.
   - Król Końcówek: liczba goli od 85' + pomocniczo liczba goli oznaczonych przez źródło jako `90'`.
   - Gole w 105'/120' nie są liczone jako „90”.
   - PWA nie pokazuje już metryki „Najpóźniejszy gol”.
   - Mobile ukryje tę linię automatycznie, ponieważ backend zwraca `latest_goal=null` — bez zmiany APK.

3. **Comeback King**
   - pełny comeback zakończony wygraną: 100% punktów,
   - odrobienie straty do remisu: 50% punktów,
   - odrobienie do remisu + wygrana po karnych: 100% punktów,
   - odrobienie do remisu + przegrana po karnych: 50% punktów.
   - Skala pełnej wartości pozostaje: strata 1 = 1 pkt, 2 = 2 pkt, 3 = 4 pkt, 4 = 7 pkt, 5 = 11 pkt itd.

4. **FC27 — seria rzutów karnych po 120'**
   - prompt API AI opisuje realny layout FC27: wiele prób oznaczonych `120'`, tick = trafiony, X = pudło, wynik meczu u góry nadal remisowy.
   - takie próby nie trafiają do zwykłych `events`, goli, Supersnajpera ani rankingów karnych w trakcie meczu;
   - przy kompletnym widocznym przebiegu AI ma policzyć wynik serii do `shootout_left/right`;
   - przy niepełnej serii ma zwrócić null + `needs_more_images=true`, bez zgadywania.

5. **LIVE Stats/Awards z wcześniejszej łatki** pozostają zachowane.

## Pliki zmienione
- `database.py`
- `mobile_api.py`
- `app.py`
- `tests/awards_logic_patch_smoke.py`

## APK
Nowy build APK **nie jest wymagany**. Zmiany są backendowe / Streamlit. Aktualne APK V11 korzysta z backendu i ukryje `latest_goal`, gdy API zwraca null.

## Testy
- `awards_logic_patch_smoke.py` — PASS
- `live_stats_awards_smoke.py` — PASS
- `manual_event_scorer_draw_smoke.py` — PASS
- `summary_last_team_yellow_smoke.py` — PASS
- `penalty_miss_icon_prompt_smoke.py` — PASS 6/6
- `mobile_api_smoke.py` — PASS 51/51
- `py_compile database.py mobile_api.py app.py` — PASS
