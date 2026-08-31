# FIFA Night Flex v1.6.1

- strzelcy nie muszą już sumować się do wyniku meczu,
- można zapisać tylko część znanych strzelców; samobóje/brakujące gole nie blokują zapisu,
- dodano po 5 startowych strzelców dla 15 obsługiwanych klubów na bazie składów EA SPORTS FC 26,
- dodano panel `Statystyki → Strzelcy → Listy zawodników drużyn`,
- w panelu można dopisać po jednym lub wielu zawodników bez edycji plików,
- wpisywanie nazw odbywa się w formularzu, więc nie powoduje rerunu przy każdym znaku,
- własne nazwiska wpisane przy meczu nadal automatycznie zapamiętują się dla danej drużyny.

Aktualizacja z v1.6:
podmień `app.py`, `database.py`, `scorer_seeds.py`.
Nie trzeba wykonywać SQL ani zmieniać Streamlit Secrets.
