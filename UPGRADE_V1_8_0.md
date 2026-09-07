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
- Awards: kategorie oficjalne + 2 podglądowe (Debiut Roku jest warunkowy);
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

### Awards hotfix 5 — etykiety, Mecz Roku i zmiana nicku
- krótsze listy kandydatów są opisane jako `X zakwalifikowanych`; `TOP 5` pojawia się dopiero przy pięciu kandydatach;
- `Mecz Roku` pokazuje jawny breakdown punktów rankingu;
- `Rywalizacja Roku` ma doprecyzowane kryteria w opisie;
- dodano chronioną hasłem administratora zmianę nazwy gracza działającą na całą historię dzięki zachowaniu tego samego `player_id`;
- odświeżane są także tekstowe snapshoty w ustawieniach/finansach/Awards, aby stary nick nie pozostawał w historycznych ekranach.


### Awards hotfix 6 — nowy algorytm Meczu Roku
- `Mecz Roku` nie jest już rankingiem punktów widocznych dla użytkownika;
- najważniejsze są bliskość wyniku oraz stawka spotkania / ryzyko odpadnięcia;
- ranga fazy i liczba goli pozostają czynnikami pomocniczymi;
- jednostronny finał nie jest automatycznie wysoko tylko dlatego, że był finałem;
- uzasadnienia pokazują wynikowe cechy meczu (np. różnica 1 gola, przegrany odpadał, liczba goli), bez punktów technicznych.
### Awards hotfix 7 — korekta Meczu Roku

- bliskość wyniku nadal jest kluczowa przy różnicy 1–2 goli;
- przy różnicy 3–4 goli kara jest łagodniejsza, bo oba wyniki są już traktowane jako wyraźne zwycięstwa;
- dzięki temu przy identycznej stawce i randze bardzo bramkowy finał 7:3 może znaleźć się przed finałem 4:1;
- punkty techniczne nadal pozostają ukryte — użytkownik widzi tylko ranking, wynik i opis meczu.


### Awards hotfix 8 — balans Meczu Roku
- zmniejszono wpływ samego faktu, że przegrany odpadał;
- bliskość wyniku, karne i bramkowość mają teraz pierwszeństwo przed stawką;
- mecze różnicą 2 goli są wyraźnie słabiej premiowane niż spotkania na styku;
- stawka i ranga fazy nadal pomagają, ale nie powinny wypychać zwykłego 2:0 nad 4:4, 2:2 + karne czy bardziej widowiskowy finał.


### Hotfix 9 — zmiana nazwy gracza na PostgreSQL / Neon
- Naprawiono `psycopg.ProgrammingError` podczas historycznej zmiany nazwy gracza.
- Wzorce `LIKE` dla zapamiętanych składów i zapisanych wyborów AWARDS są teraz przekazywane jako parametry SQL, dzięki czemu znak `%` nie jest interpretowany przez psycopg jako placeholder.
- Nie zmienia to logiki rename: `player_id` pozostaje ten sam, więc historyczne mecze, H2H, statystyki i finanse nadal należą do tego samego profilu.

### Awards hotfix 10 — dopracowanie kryteriów kategorii
- `Gracz Roku`: delikatnie zmniejszono wagę tytułu (32 → 27) i zwiększono wagę każdego finału (11 → 14), aby regularne dochodzenie do finałów miało większe znaczenie.
- `Król Strzelców FIFA Night`: przy równej liczbie goli decyduje mniejsza liczba meczów rozegranych przez danego gracza drużyną tego strzelca; przy kolejnym remisie decyduje liczba hat-tricków tego piłkarza.
- `Clutch Player Roku`: Winners Bracket i WB Final nie są już liczone jako clutch, bo porażka nie eliminuje gracza; liczą się QF/baraż, SF, LB/LB Final oraz finały.
- `Najbardziej Uniwersalny Gracz`: usunięto próg W% ≥ 40% dla drużyny. Udana drużyna to obecnie taka, która wyszła do SF/finału z grup, dotarła do WB Final lub LB Final w Double Elimination albo do finału w formacie ligowym.
- `Król Wild Cardów`: tytuły i finały są liczone wyłącznie wtedy, gdy osiągnięto je Wild Cardem; tytuł daje mocny bonus, a finał dodatkową premię.
- `Debiut Roku`: kategoria nie jest pokazywana w sezonie, w którym wszyscy aktywni gracze są debiutantami. Pojawia się dopiero, gdy obok nowych graczy występują uczestnicy z wcześniejszą historią.
- `Mecz Roku`: balans ustawiono na 35% bliskość, 22% gole, 18% stawka, 13% ranga fazy i 12% karne; wynik techniczny nadal pozostaje ukryty.
- `Najczęściej nominowani`: liczniki TOP3/TOP5 pozostają, ale lista nazw kategorii pokazuje tylko te, w których gracz jest w TOP2, aby ograniczyć bałagan.
- dodano oficjalną kategorię `Najbardziej Widowiskowy Gracz`: minimum 5 meczów; widowiskowość pojedynczego meczu to 45% bliskość, 40% liczba goli i 15% karne, a ranking gracza to 80% średnia widowiskowość + 20% odsetek bardzo widowiskowych spotkań. Ranga meczu i wynik gracza nie wpływają na tę nagrodę.


### Awards hotfix 11 — Debiut Roku: pierwsze 5 i 10 meczów
- `Debiut Roku` nie jest już wyłączany w pierwszym wspólnym sezonie. Dzięki nowej logice nie dubluje `Gracza Roku`, bo ocenia wyłącznie początek kariery.
- w AWARDS są dwie osobne tabelki: **pierwsze 5 meczów** (tempo wejścia) oraz **pierwsze 10 meczów** (ranking główny do nagrody);
- ranking pierwszych 10 jest podstawą nominacji i wyboru laureata; jeśli nikt nie ma jeszcze 10 spotkań, ranking LIVE tymczasowo korzysta z pierwszych 5;
- w obu tabelach pokazujemy W-D-L, W%, punkty/mecz, bilans bramek, finały i tytuły;
- wynik wewnętrzny bierze pod uwagę przede wszystkim rezultaty z okna 5/10 meczów (W%, punkty/mecz i bilans bramek), a dojście do głębokich faz, finałów i zdobycie tytułu jest dodatkową premią. 1v1 nie wchodzi do tej kategorii.

### Hotfix Awards 12
- `Najbardziej Widowiskowy Gracz` jest utrzymany jako pełnoprawna nagroda w środkowej części kolejności AWARDS i wyboru laureatów (po `Największym Progresie`). Kategoria jest widoczna także przy 0 zakwalifikowanych.
- tabela `Najczęściej nominowani` wylicza nazwy kategorii TOP 2 bezpośrednio z aktualnych rankingów AWARDS, więc kolumna nie pozostaje pusta wskutek rozjazdu danych pomocniczych;
- przy braku TOP 2 pokazujemy jednoznaczne `brak TOP 2` zamiast pustego pola;
- widok Debiutu Roku ma fallback zgodności, aby nie zgłaszać fałszywie pustych tabel, jeśli ranking z informacją o oknie 5/10 meczów jest już dostępny.
