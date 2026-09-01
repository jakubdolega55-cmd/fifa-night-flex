# FIFA Night Flex v1.7.1

## Fairness między turniejami
- oczekiwanie z poprzedniego turnieju jest teraz liczone wg faktycznej kolejności rozegrania (`played_at`), a nie numeru logicznego meczu,
- zawodnik, który grał ostatni mecz poprzedniego turnieju (zwykle finalista/mistrz), dostaje — jeśli da się to zrobić bez pogorszenia bieżącego terminarza — jeden pełny mecz przerwy przed pierwszym występem w kolejnym turnieju,
- osoby długo czekające są nadal delikatnie przesuwane wcześniej,
- pary/grupy pozostają w 100% wylosowane; zmienia się tylko kolejność rozegrania niezależnych meczów,
- algorytm nie może pogorszyć liczby meczów back-to-back, maksymalnej przerwy ani momentu, w którym wszyscy po raz pierwszy wchodzą do gry względem bazowego terminarza,
- miękkie ważenie BYE z v1.7.0 zostaje bez zmian.

## Testowy / Oficjalny
- status turnieju można zmienić bez resetowania na każdym etapie oraz po zakończeniu,
- zmiana nie rusza wyników, drabinki, drużyn ani strzelców,
- po zakończeniu status od razu decyduje, czy turniej jest uwzględniany w statystykach oficjalnych,
- przy ponownym losowaniu/akceptacji struktury kontekst fairness jest odświeżany wg aktualnego statusu.
