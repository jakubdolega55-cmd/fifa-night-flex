# CHECKPOINT R30 — 2026-10-21 — kontekst zdobytych odznak

## Cel
Po fizycznym feedbacku doprecyzowano szczegóły zdobytych odznak. Zamiast samego warunku/wyniku odznaka ma pokazywać, gdzie faktycznie została zdobyta.

## Zmiany
- Każda historycznie odtworzona odznaka może teraz dostać `event_context`:
  - `FIFA Night #N` dla zakończonego turnieju,
  - `FIFA Night (w toku)` dla aktywnego turnieju,
  - `1 vs 1` dla meczu w trybie duel1v1.
- Odznaki meczowe nadal mają `match_context`: rywal + wynik z perspektywy gracza, w tym wynik serii karnych.
- Dodano `team_context`: drużyna używana przez gracza w meczu/turnieju, gdy jest dostępna.
- Mobile/PWA i Streamlit pokazują kontekst w formie:
  - `Zdobyta: DD.MM.RRRR • FIFA Night #N`
  - `Mecz: vs Rywal • wynik`
  - `Drużyna: ...`
- `Thriller`, `Masakra`, `Ice Cold` i `Pierwsza krew` nie powtarzają już samego wyniku drugi raz w polu detail; wynik pochodzi z `match_context`.
- Nie zmieniono żadnego warunku ani progu zdobywania odznak.

## Wsteczność
Kontekst jest rekonstruowany z istniejącej historii dokładnie tak jak odznaki R27-R29, więc dotyczy również wcześniej zdobytych odznak, o ile mecz/turniej istnieje w bazie.

## Testy
- `achievement_badge_context_r30_smoke.py` — PASS (w tym Thriller 4:3, Ice Cold 2:2 k. 7:6, turniej, rywal i drużyna)
- `achievement_badge_details_r29_smoke.py` — PASS
- `achievement_badges_r27_smoke.py` — PASS
- `records_summary_turnaround_r28_smoke.py` — PASS
- Python compile — PASS
- `mobile_api_smoke.py` — 52/52 PASS
- Pełny `npm run check` nieoznaczony jako PASS: w paczce nie ma `mobile/node_modules`.

Android `versionCode` pozostaje 15.
