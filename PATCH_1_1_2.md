# FIFA Night Flex 1.1.2 — RC przed poprawką Laureatów

## Zmiany
- Poddanie meczu: wynik turniejowy 3:0/0:3, ale mecz nie istnieje w statystykach historycznych, H2H, W/L, GF/GA, ratingach, Awards, rekordach i milestone'ach.
- Undo obsługuje poddanie.
- UI Streamlit i mobile: osobny przycisk Poddaj mecz, wybór poddającego i potwierdzenie.
- Rozdzielenie akcji: Przesuń mecz na później / Nie rozgrywaj meczu / Poddaj mecz.
- Swiss 8/10: po pełnej rundzie obowiązkowy ekran par do ręcznego zatwierdzenia; następna runda pozostaje zablokowana do ACK.
- Swiss 8/10: 3. i 4. miejsce z przegranych półfinałów, bez meczu o brąz.
- Streamlit: poprawione renderowanie tabel L/S/A/B/C/F3; usuwa KeyError `tables["A"]` w Swiss.
- Wild Card: lekki boost dla TOP3 poprzedniego turnieju: 1.55 / 1.35 / 1.15 / 1.00.
- Cross-tournament rest/scheduler nie traktuje poddania jako fizycznie rozegranego meczu.
- Wersja API/mobile 1.1.2, Android versionCode 7.

## Walidacja
- Python compile: PASS
- mobile_api_smoke: 51/51 PASS
- big_patch_smoke: 8/8 formatów PASS
- DE4/5/6 audit: PASS
- DE9/10 smoke: PASS
- versioning/alias/continuity: PASS
- shrinking wheel: PASS
- visible draw policy: PASS
- dedicated forfeit smoke: PASS
- Swiss 8/10: manual ACK + no-rematch + Buchholz + TOP4 + 3rd/4th: PASS

Nie wykonano pełnego npm install / TypeScript compiler / EAS build w kontenerze. Te kroki pozostają do wykonania w środowisku buildowym.

## Awards organizer UX
- Laureate dropdown labels now include the candidate's category-specific `reason` / "Dlaczego jest wysoko" stats, so the organizer does not need to scroll back to the ranking table.
- A saved laureate can be removed per category with `USUŃ LAUREATA / RESETUJ WYBÓR` and selected again.
- Reset affects only the selected category; other award selections remain unchanged.
