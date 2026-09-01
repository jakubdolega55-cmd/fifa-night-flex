# FIFA Night Flex v1.5

## Nowości

- obsługa 8 graczy,
- 3 formaty dla 8 osób:
  - Grupy 4+4 + półfinały + finał — 15 meczów,
  - Double Elimination — 14–15 meczów,
  - Grupy 4+4 + baraże + półfinały + finał — 17 meczów,
- dla 8 graczy pula drużyn to 5 stałych klubów + 3 Wild Cards,
- Double Elimination dla 8 graczy ma pełną drabinkę bez BYE,
- w grupach 4+4 każdy rozgrywa 3 mecze grupowe, a terminarz nie daje tej samej osobie dwóch kolejnych spotkań,
- animowane losowanie struktury obsługuje również 8 osób i zachowuje mobilny układ z v1.4,
- przy każdym nowym formacie wyświetlana jest łączna liczba meczów.

## Aktualizacja z v1.4

Podmień:

- `app.py`
- `database.py`
- `logic.py`
- `ui.py`

Nie trzeba wykonywać żadnego SQL ani zmieniać `DATABASE_URL` / `ADMIN_PASSWORD` w Streamlit Secrets.
