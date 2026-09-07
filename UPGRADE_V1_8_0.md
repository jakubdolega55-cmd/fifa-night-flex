# Upgrade do FIFA Night Flex v1.8.0

## Baza
Wersja jest przygotowana jako upgrade z v1.7.7.1. `init_schema()` automatycznie dodaje do istniejącej tabeli `matches` kolumnę `match_status` i oznacza historycznie rozegrane mecze jako `played`. Historyczne wyniki nie są przepisywane ani usuwane.

Nowy status `skipped` służy wyłącznie do matematycznie bezpiecznego pomijania zbędnych spotkań. Taki mecz pozostaje bez wyniku i nie trafia do statystyk.

## Najważniejsze zmiany
- 3 graczy: liga każdy z każdym + finał, 4 mecze.
- 4 graczy: dodatkowy Double Elimination, 6 meczów.
- 6 graczy: dodatkowy Double Elimination, 10 meczów.
- osobny tryb 1 vs 1, ręczne drużyny i własna stawka;
- `Gra za kasę` per uczestnik, rollover jackpotu między płatnymi oficjalnymi turniejami;
- 1v1 może być płatne, ale nigdy nie tworzy ani nie konsumuje turniejowego jackpotu;
- nowe pule drużyn i Wild Cardów, Live Team Rating oraz anty-powtórka poprzedniej drużyny;
- uproszczone opcjonalne strzelce;
- bezpieczne `Pomiń mecz` dla ligi + finał;
- rozliczenia TXT i PNG 1080×1080;
- FIFA Night Awards i roczne grafiki PNG;
- osobna zakładka H2H została usunięta z UI, ale dane H2H pozostają bez zmian.

## Zasady zachowane
- Real Madryt pozostaje zablokowany.
- Testy nie trafiają do oficjalnych statystyk ani finansów.
- Losowanie przeciwników/grup pozostaje losowe; fairness nie zmienia wylosowanych par.
- Grand Final Double Elimination nie ma resetu; mistrz WB startuje od 1:0, a bonus nie ma strzelca.
- Strzelcy pozostają opcjonalni.

## Testy wykonane przed paczką
- `py_compile` dla plików Python;
- migracja bazy v1.7.7.1 → v1.8.0 na SQLite;
- end-to-end dla 3 graczy, DE4 i DE6;
- pełna regresja wszystkich 14 formatów turniejowych 3–8 graczy;
- 1v1 płatne i bezpłatne;
- jackpot: rollover przez nieuprawnionego mistrza, brak zużycia przez 1v1, wypłata w kolejnym turnieju;
- `Pomiń mecz`: status `skipped`, przejście do finału i brak wpisu do statystyk;
- Awards: 19 kategorii + 2 podglądowe;
- generowanie trzech typów PNG w rozdzielczości 1080×1080.
