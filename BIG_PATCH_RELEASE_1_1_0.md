# FIFA Night Flex 1.1.0 — BIG PATCH
Stan: 2026-09-15

## Zakres wydania
Pełny BIG PATCH rozwijający FIFA Night Flex z bazowej wersji 1.0.2.

Najważniejsze elementy:
- wybór EA SPORTS FC 26 / FC 27 zapisywany przy turnieju;
- historyczne turnieje bez wersji migrowane do FC26;
- Live Team Rating liczony osobno dla FC26 i FC27, z płynnym priorem FC26 -> FC27 dla pierwszych 5 meczów danej drużyny;
- wspólna historia FIFA Night dla statystyk, rekordów, Awards, kamieni milowych, H2H i finansów;
- status Wild Card klasyfikowany per mecz według wersji gry (np. Arsenal/Manchester City: WC w FC26, normalna pula w FC27);
- Real Madryt jako helper dla gracza `Gra za kasę = NIE`, bez Team Rating / Team of Year, ale z normalnymi statystykami gracza i przeciwnika;
- resolver nazwisk piłkarzy i zapamiętywane aliasy per wersja gry + klub;
- ekran `Więcej zawodników`: 8, 9, 10;
- Swiss8 i Swiss10;
- cztery formaty 9-osobowe i trzy formaty 10-osobowe;
- Final Three wyłącznie w wariancie 9B;
- DE4–DE10 z ujednoliconą polityką prawdziwych losowań / deterministic reveal;
- wcześniejsze source-level losowania z placeholderami tam, gdzie pomagają live schedulerowi i nie psują fairness;
- smart scheduler: najpierw unikanie back-to-back, następnie długie oczekiwanie; nie zmienia par;
- natychmiastowe rewanże w DE są unikane, starsze rewanże są normalnym wynikiem losowania;
- Undo zachowuje wcześniej publicznie pokazane source-level losowania;
- mobile/PWA/API/Streamlit obsługują nowe formaty i widoczne losowania/reveale.

## Wersje
- Mobile/PWA: 1.1.0
- Android versionCode: 5
- API: 1.1.0

## Migracja bazy
Nie ma osobnego skryptu SQL do ręcznego uruchamiania. `Database.init_schema()` wykonuje migrację idempotentnie przy starcie API oraz Streamlit:
- dodaje `tournaments.game_version` z domyślnym `FC26`, jeśli kolumny nie ma;
- uzupełnia stare/puste rekordy jako `FC26`;
- tworzy nowe tabele rosterów i aliasów piłkarzy, jeśli ich nie ma;
- zachowuje istniejącą historię.

Przed pierwszym wdrożeniem 1.1.0 zalecany jest backup Neon.
