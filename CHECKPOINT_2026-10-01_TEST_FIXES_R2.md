# FIFA NIGHT FLEX — TEST FIXES R2 — 2026-10-01

Zakres:
- Swiss R1-R3: remis dozwolony, 3-1-0, bez dogrywki/karnych;
- Swiss standings: naprawa KeyError dla position/d;
- EA FC 27 jako domyślna wersja nowego turnieju (Streamlit/mobile/API);
- Streamlit TV Wide v2;
- NEXT/public M1-M2: iteracyjna projekcja schedulera; brak zgadywania przy dynamicznym unlocku KO/DE;
- DE9/DE10: dynamiczne losowania Losers blokują przedwczesny NEXT;
- DE BYE: znany gracz jest zapisywany do przyszłego meczu niezależnie od nierozstrzygniętego drugiego slotu;
- DE terminarz/drzewko: publiczne display_match_no + tłumaczenie Zwycięzca/Przegrany Mx na publiczne numery;
- mobile DE tree używa publicznych numerów.

Testy PASS:
- swiss_draws_3_1_0_smoke.py
- de9_de10_smoke.py
- de_bye_public_schedule_smoke.py
- public_schedule_next_invariant_smoke.py (groups6, swiss8, double9, double10)
- Python compile (ui.py ma istniejący nieblokujący SyntaxWarning dot. escape sequence w osadzonym JS/CSS)
