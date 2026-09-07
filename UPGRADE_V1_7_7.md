# FIFA Night Flex v1.7.7

## Co nowego

### Status rozliczenia
- zakończone oficjalne turnieje mają status `🟠 nierozliczony` / `✅ rozliczony`,
- przy uzupełnianiu starej stawki można od razu ustawić `Ten turniej jest już rozliczony`,
- status można później cofnąć,
- rozliczone turnieje są domyślnie ukryte z listy bieżącego rozliczenia, ale można je pokazać przełącznikiem,
- po wykonaniu przelewów można jednym kliknięciem oznaczyć cały wybrany zestaw jako rozliczony.

### Ranking finansowy
W `Statystyki → Rozliczenia` pojawia się ranking finansowy wszystkich zakończonych oficjalnych turniejów z dodatnią stawką. Pokazuje:
- bilans łączny,
- łączne wygrane,
- łączne wpłaty,
- liczbę płatnych turniejów,
- liczbę wygranych płatnych turniejów,
- osobę najbardziej na plus i najbardziej na minus.

Turniej pozostaje w rankingu również po oznaczeniu go jako rozliczony. Status służy tylko do śledzenia, czy realne przelewy zostały już wykonane.

## Pliki do podmiany po v1.7.6
- `app.py`
- `database.py`

`README.md` i ten plik są informacyjne.

Nie ma migracji schematu bazy. Pole `cash_settled` jest zapisywane w istniejącym `extra_json`.
