# CHECKPOINT 2026-10-01 — TEAM VISUALS + LIVE FORM

Base: FIFA-NIGHT-1.1.3-FC27-DRAW-WEIGHTS-170-145-040-060-2026-10-01

## Zakres tego checkpointu
- Kluby: herb w 3 miejscach: wynik losowania, ekran aktualnego meczu, Następny mecz.
- Reprezentacje: flaga w tych samych 3 miejscach.
- Brak herbów/flag w tabelach, drabinkach i zwykłej liście meczów.
- Ekran meczu: osobny kafelek LIVE FORM, ostatnie 5 wyników.
- Prezentacja formy: W = zielone, D/R = R = żółte, L/P = P = czerwone.
- Dane formy korzystają z istniejącego match_context; bez zmian DB i bez dodatkowego API.
- Nieznany Wild Card: fallback do inicjałów.
- Android versionCode: 13 -> 14.

## Uwaga techniczna / następny punkt
W tej funkcjonalnej wersji herby klubów są ładowane z lekkich URL-i i mają fallback. Lokalny bundling/ostateczne dopolerowanie assetów odkładamy do następnego punktu, zgodnie z decyzją użytkownika, żeby nie przeciągać tej aktualizacji.

## Testy
PASS:
- Python compile: app.py, database.py, logic.py, mobile_api.py, ui.py, team_visuals.py
- team_visuals_live_form_smoke.py
- fc27_draw_weight_tuning_smoke.py
- fc27_real_ban_mobile_settings_smoke.py
- fc27_real_ban_switch_smoke.py
- national_mode_fc27_smoke.py
- mobile_api_smoke.py: 51/51
- smart_scheduler_smoke.py
- de9_de10_smoke.py
- group_tiebreak_smoke.py
- swiss_smoke.py
- forfeit_smoke.py
- mobile_formdata_sdk57_source_smoke.py

Nie wykonano fizycznego testu na telefonie/TV.
