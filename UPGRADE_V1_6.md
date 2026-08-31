# FIFA Night Flex v1.6

Najważniejsze zmiany:
- H2H, forma oraz automatyczne oznaczenia Rivalry/Derby przed każdym meczem,
- rozbudowane Statystyki: H2H explorer, rekordy, Hall of Fame i klasyfikacja strzelców,
- pełny ekran podsumowania po zakończeniu turnieju,
- Wild Card zatrzymuje losowanie do czasu wpisania konkretnej drużyny,
- podpowiedzi drużyn Wild Card z historii + lista startowa, bez rerunu podczas pisania,
- opcjonalne dokładne przypisywanie strzelców w meczu,
- liczniki strzelców działają wewnątrz formularza: +/– nie przeładowuje strony, zapis następuje dopiero z wynikiem,
- nowe nazwisko strzelca automatycznie zostaje w bazie drużyny,
- kolejność strzelców ustala się według liczby goli / częstotliwości,
- `scorer_seeds.py` służy do ręcznego wpisania początkowych list zawodników.

Aktualizacja z v1.5.1: podmień `app.py`, `database.py`, `logic.py` i dodaj `scorer_seeds.py`.
Nie trzeba wykonywać ręcznie SQL — nowe tabele tworzą się automatycznie.
