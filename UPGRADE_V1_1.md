# FIFA Night Flex v1.1

## Co się zmieniło

Dla 4 i 5 graczy działa teraz draft drużyn:

1. Aplikacja losuje kolejność wyboru graczy.
2. Kolejność jest odsłaniana animacją po jednej osobie.
3. Przed rozpoczęciem draftu można użyć „Zapłać i wylosuj ponownie”.
4. Gracze wybierają kolejno spośród pozostałych pozycji: Bayern, Barcelona, PSG, Liverpool, Manchester City, Wild Card.
5. Wybrana pozycja znika z puli.
6. Wild Card pozwala wpisać własną drużynę; Real Madryt jest blokowany.
7. Po zakończeniu draftu aplikacja przechodzi do losowania par (4 graczy) albo drabinki (5 graczy).

Dla 6 i 7 graczy koło fortuny pozostaje bez zmian.

## Aktualizacja z v1.0

Podmień w repozytorium:
- `app.py`
- `database.py`
- `ui.py`

`logic.py` i `requirements.txt` nie wymagają zmian.

Nie zmieniaj `DATABASE_URL`, Neona ani starej aplikacji 6-osobowej. Statystyki nadal są wspólne.
