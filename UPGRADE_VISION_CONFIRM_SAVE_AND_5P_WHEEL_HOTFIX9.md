# FIFA Night Flex — Hotfix 9

## 1. Odczyt zdjęć przy konkretnym meczu: podgląd → korekta → zapis
- stały adres FastAPI (`https://fifa-night-api.onrender.com`) jest używany automatycznie; można go nadpisać przez `FIFA_NIGHT_API_URL`, ale użytkownik nie wpisuje go przy meczu,
- po analizie zdjęć pojawia się edytowalny podgląd,
- można poprawić wynik, minutę, typ zdarzenia, piłkarza oraz przypisanie do gracza FIFA Night,
- można wyłączyć błędne zdarzenie albo dodać wydarzenie ręcznie,
- zapis jest blokowany, dopóki liczba bramek po obu stronach nie zgadza się z wynikiem,
- seria karnych po meczu jest zapisywana wyłącznie jako wynik serii,
- dopiero `ZATWIERDŹ ODCZYT I ZAPISZ MECZ` zapisuje wynik i wydarzenia do Neona,
- nowe szczegółowe wydarzenia są zapisywane w `match_events`, a gole zwykłe i z karnych są równolegle agregowane do dotychczasowego `match_scorers`, więc stare statystyki strzelców nadal działają,
- samobóje nie są przypisywane jako gole piłkarzom,
- pierwszy samobój dający bonus zawodnikowi z Winners Bracket w finale Double Elimination jest oznaczany jako techniczny (`synthetic_de`) i nie trafia do statystyk strzeleckich.

## 2. Turniej 5-osobowy: koło fortuny drużyn
- 3 i 4 graczy: bez zmian — losowanie kolejności i ręczny wybór drużyn,
- 5 graczy: koło fortuny, tak jak w większych turniejach,
- pula dla 5 graczy: Bayern Monachium, FC Barcelona, PSG, Liverpool + 1 Wild Card,
- jeśli koło wylosuje Wild Card, organizator wybiera konkretny klub (Real Madryt nadal banned),
- po losowaniu drużyn turniej przechodzi do losowania struktury jako etap 2/2.
