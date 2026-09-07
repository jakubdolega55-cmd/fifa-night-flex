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

## Hotfix Awards po testach v1.8.0
- `Rywalizacja Roku`: pole „ważne mecze” pokazuje teraz faktyczną liczbę ważnych spotkań. Wewnętrzna waga nadal premiuje finał/półfinał, ale nie jest już prezentowana jako liczba meczów.
- `Król Strzelców FIFA Night`: ranking jest liczony per **konkretny piłkarz + konkretny gracz**; np. 9 goli Ferrana Torresa dla Benia wyprzedza 8 goli Isaka dla Jarka.
- `Supersnajper Roku` pozostaje rankingiem piłkarza liczonym globalnie we wszystkich wpisanych golach.
- komunikat o decyzji organizatora został zmieniony na prześmiewczy tekst w stylu FIFA Night.


### Awards hotfix 2 — Najbardziej Uniwersalny Gracz
- doprecyzowano opis klasyfikacji, aby „2 drużyny / 2 dobre” nie wyglądało jak 100% udanych startów;
- ranking nadal premiuje liczbę różnych drużyn spełniających próg, szerokość puli oraz ogólne W%;
- w uzasadnieniu pokazujemy teraz osobno liczbę różnych drużyn, liczbę drużyn spełniających próg, liczbę startów i W%.

### Awards hotfix 3 — defensywa, nominacje i kolejność gali
- `Beton Roku` uwzględnia teraz czyste konta zarówno w punktacji, jak i w opisie kandydata;
- w opisach Awards zrezygnowano ze skrótów GF/GA/GD na rzecz polskich określeń (np. „bilans bramek/mecz”);
- pod rankingami dodano `Najczęściej nominowani`: liczba unikalnych kategorii TOP 3, TOP 5 oraz liczba pozycji #1; kategorie drużynowe/meczowe nie nabijają nominacji graczom;
- wybór laureatów ma teraz trzy celowo ułożone etapy: główne nagrody, specjalistyczne oraz specjalne/finał gali;
- przy każdym kandydacie z TOP 3 widać, ile nagród ma już wybranych; kandydat bez nagrody jest oznaczony jako `bez nagrody`, co ułatwia rozłożenie wyróżnień przy zbliżonych kandydaturach;
- nad wyborem laureatów wyświetlany jest bieżący rozkład nagród per gracz;
- `Król Strzelców FIFA Night` liczy nagrodę do właściwego gracza kontrolującego danego piłkarza, dzięki czemu licznik rozkładu nagród pozostaje poprawny.

### Awards hotfix 4
- Zwykły widok `AWARDS` używa teraz tej samej kolejności kategorii co panel wyboru laureatów.
- W widoku rankingów kolejność jest płaska — bez podziału na etapy i bez opisów etapów.
- Podział na etapy pozostaje wyłącznie w sekcji organizatora do wyboru laureatów.
