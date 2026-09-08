# Hotfix 27 — wariant 1 vs 1 w jednym wyborze + audyt „Przesuń mecz”

## FIFA Night

- Usunięto dodatkowy przełącznik `Turniej / 1 vs 1`.
- Na jednym pasku wyboru wariantu są teraz: `1 vs 1`, `3`, `4`, `5`, `6`, `7`, `8`.
- 1 vs 1 nadal zachowuje własny formularz graczy, drużyn i stawki, ale jest wybierane dokładnie tam, gdzie liczba graczy turniejowych.

## Statystyki

- Zakładka `Ciekawostki` została przemianowana na `Drużyny i strzelcy`.
- Nadal zawiera statystyki drużyn, Live Team Rating, klasyfikację strzelców oraz bazę podpowiedzi zawodników drużyn.

## Przesuń mecz na później — audyt

Mechanizm pozostaje awaryjnym odstępstwem od automatycznej kolejności. Przycisk pojawia się wyłącznie, gdy istnieje co najmniej jeden inny mecz z już ustalonymi obiema stronami, który można realnie rozegrać teraz.

Przetestowano pełne przejścia turniejów ze zmianą kolejności dla wszystkich formatów:

- 3: liga + finał,
- 4: liga + finał, Double Elimination,
- 5: liga + finał, Double Elimination,
- 6: oba warianty grupowe, Double Elimination,
- 7: oba warianty grupowe, Double Elimination,
- 8: oba warianty grupowe, Double Elimination,
- 1 vs 1: brak przycisku, ponieważ nie istnieje alternatywny mecz.

W trakcie audytu poprawiono dodatkowy przypadek brzegowy: źródło `POS` (miejsce w tabeli) czeka teraz na zakończenie lub bezpieczne pominięcie wszystkich meczów danej ligi/grupy. Dzięki temu wielokrotne awaryjne przesuwanie spotkań nie może przedwcześnie odblokować finału ligi.

Nie zmieniono algorytmu wyliczającego domyślną kolejność. `Przesuń mecz na później` nadal działa tylko jako ręczna interwencja awaryjna.
