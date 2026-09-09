# FIFA Night Flex v1.8.0

Responsywna aplikacja Streamlit do FIFA Night: wariant 1 vs 1 oraz turnieje dla 3–8 graczy, z trwałym zapisem w Neon/PostgreSQL.

## Formaty

- 1 vs 1 — wariant FIFA Night dla dwóch graczy z ręcznym wyborem drużyn (1 mecz)
- 3 graczy — liga każdy z każdym + finał (4 mecze)
- 4 graczy — liga każdy z każdym + finał (7) albo Double Elimination (6)
- 5 graczy — Double Elimination (8) albo liga + finał (11)
- 6 graczy — klasyczne 2×3 + SF + finał (9), rozszerzone 2×3 + QF + SF + finał (11) albo Double Elimination (10)
- 7 graczy — Double Elimination (12), grupy 4+3 + QF + SF + finał (14) albo grupy 4+3 + SF + finał (12)
- 8 graczy — grupy 4+4 + SF + finał (15), Double Elimination (14) albo grupy 4+4 + baraże + SF + finał (17)

## Formaty dla 8 graczy

### Grupy 4+4 + półfinały + finał — 15 meczów

12 meczów grupowych, następnie 1A–2B i 1B–2A, a na końcu finał. Kolejność półfinałów jest dobierana po zakończeniu grup, aby ograniczyć granie bez odpoczynku.

### Double Elimination — 14 meczów

Pełna, symetryczna drabinka dla ośmiu osób, bez Szczęśliwego losu. Zawodnik odpada dopiero po drugiej porażce. Jest jeden finał; mistrz Winners Bracket zaczyna go z bonusem 1:0.

### Grupy 4+4 + baraże + półfinały + finał — 17 meczów

12 meczów grupowych. Zwycięzcy obu grup przechodzą bezpośrednio do półfinałów. Miejsca 2–3 grają dwa baraże, a 4. miejsca odpadają. Każdy zwycięzca barażu dostaje jeden pełny mecz odpoczynku przed swoim półfinałem.

## Drużyny

- 3–5 graczy — losowanie kolejności draftu, następnie wybór jednego z 4 stałych klubów albo dowolnego dostępnego Wild Carda.
- Stałe kluby: Bayern Monachium, FC Barcelona, PSG, Liverpool.
- 6 graczy — 4 stałe kluby + 2 sloty Wild Card.
- 7 graczy — 4 stałe kluby + 3 sloty Wild Card.
- 8 graczy — 4 stałe kluby + 4 sloty Wild Card.
- Manchester City i Arsenal są dostępne jako Wild Cardy.
- Konkretny klub Wild Card może wystąpić tylko raz w jednym turnieju; Real Madryt pozostaje zablokowany.

## Telefon

Losowania i ceremonie używają responsywnego układu. Na małym ekranie karty składają się pionowo, długie nicki są zawijane, a animowane elementy dopasowują wysokość do zawartości.

## Wpisywanie graczy

Pola graczy są wyszukiwalne i podpowiadają nicki z zakończonych turniejów nietestowych zapisanych we wspólnej bazie statystyk. Można też wpisać nowy nick. Pola znajdują się w formularzu, więc wpisywanie i filtrowanie podpowiedzi nie uruchamia pełnego reruna aplikacji; dane trafiają do backendu dopiero po zatwierdzeniu formularza.

## Statystyki i klimat meczu

Przed każdym meczem aplikacja pokazuje kompaktowo H2H, formę z ostatnich 5 oficjalnych spotkań oraz oznaczenia Rivalry/Derby, jeśli para spełnia kryteria historyczne.

Zakładka `Statystyki` zawiera ranking, explorer H2H, aktualną formę, rekordy, Hall of Fame oraz klasyfikację dokładnych strzelców. Po zakończeniu turnieju pojawia się osobny ekran podsumowania z mistrzem, finalistą, najlepszym atakiem/obroną, największym zwycięstwem, najbardziej bramkowym meczem, strzelcem turnieju i wykrytymi nowymi rekordami.

## Wild Card

Jeśli koło wylosuje Wild Card, losowanie zatrzymuje się do czasu wpisania konkretnej drużyny. Pole podpowiada wcześniejsze wybory oraz startową listę: Inter, Atletico, BVB, Man United, Arsenal, Chelsea, Bayer Leverkusen, Tottenham, AC Milan i Napoli. Wpisywanie/wybieranie odbywa się w formularzu, więc nie przeładowuje strony przy każdym znaku.

## Dokładni strzelcy

Pod wynikiem meczu można opcjonalnie rozpisać dokładnych strzelców. Dla każdej drużyny są 3 kompaktowe wiersze z wyborem nazwiska i licznikami −/+, a przyciskiem `Dodaj strzelca` można dołożyć kolejne pozycje. Nowe nazwisko można również dopisać ręcznie i zachować w puli danej drużyny.

Strzelcy są zapisywani razem z wynikiem po `ZATWIERDŹ WYNIK`. Pozostają całkowicie opcjonalni i nie muszą sumować się do wyniku — można zostawić ich pustych, np. przy samobójach albo gdy nie pamiętacie wszystkich nazwisk.

Początkowe listy zawodników uzupełnia się w pliku `scorer_seeds.py`.


## Losowania w Double Elimination

W 7-osobowym Double Elimination po pierwszej rundzie jest **jedno wspólne losowanie**: tym samym przyciskiem losowane są pary kolejnej rundy Winners Bracket oraz `Szczęśliwy los` w Losers Bracket. W 8-osobowym DE pozostaje losowanie par Winners Bracket, bo nie ma tam Szczęśliwego losu. Dla 5 graczy pozostaje losowanie przeciwnika dla gracza ze Szczęśliwym losem.

## Eksport do obrazka

Po zakończeniu turnieju na ekranie podsumowania pojawia się przycisk `Pobierz podsumowanie PNG`.

Eksport generuje czytelną grafikę **1080×1080** do wrzucenia na grupę. W v1.6.6 powiększono typografię i uproszczono układ. Na obrazku znajdują się m.in.:

- numer turnieju (bez nazwy aplikacji),
- data, liczba graczy i format,
- mistrz i finalista,
- wynik finału,
- strzelec turnieju,
- mecz turnieju,
- miejsca 3–4 (jeśli format pozwala je ustalić),
- bilans mistrza i podstawowe liczby turnieju.

Turnieje testowe też można eksportować, ale na grafice są oznaczone jako testowe i nie dostają numeru oficjalnego.

## Historia i zabezpieczenie bazy

Panel `Historia i baza` obsługuje usunięcie ostatniego zakończonego turnieju nietestowego, wyczyszczenie całej historii oraz blokowanie/odblokowanie historii. Operacje administracyjne wymagają `ADMIN_PASSWORD` ze Streamlit Secrets.

Pełne czyszczenie usuwa turnieje, mecze i statystyki. Tabela graczy i zapamiętane składy pozostają w bazie, ale autocomplete pokazuje wyłącznie nicki występujące w aktualnych oficjalnych statystykach.

## Streamlit Secrets

W Streamlit Community Cloud ustaw:

```toml
DATABASE_URL = "TWÓJ_CONNECTION_STRING_Z_NEON"
ADMIN_PASSWORD = "TWOJE_HASLO"
```

Plik `.streamlit/secrets.toml` nie może trafić do GitHuba.


## Mobilne strzelcy v1.6.7

Sekcja strzelców została skompresowana pod telefon: każdy z 5 podstawowych zawodników zajmuje jeden niski wiersz z nazwiskiem po lewej i licznikiem goli po prawej. Drużyny są prezentowane jedna pod drugą, a `Pozostali zawodnicy` i `Inny zawodnik` są domyślnie zwinięte. Wszystko nadal znajduje się w formularzu meczu, więc zmiana liczników nie powoduje rerunu strony; dane zapisują się dopiero przy zatwierdzeniu wyniku.



## v1.8.0 — 1v1, nowe formaty, jackpot i FIFA Night Awards

- osobny tryb **1 vs 1** z ręcznym wyborem drużyn, opcjonalną stawką i minimum 5 meczów do rankingu `Król 1 vs 1`;
- turniej **3-osobowy**: liga + finał (4 mecze);
- **Double Elimination dla 4 i 6 graczy** (odpowiednio 6 i 10 meczów), z zachowaniem finału bez resetu i startu mistrza WB od 1:0;
- checkbox **Gra za kasę** przy każdym uczestniku i **jackpot** przenoszony, gdy mistrz nie gra za kasę; 1v1 nie tworzy i nie zużywa jackpotu;
- nowe pule drużyn 6–8: Bayern, Barcelona, PSG, Liverpool + odpowiednio 2/3/4 Wild Cardy; Man City jest teraz Wild Cardem;
- **Live Team Rating**, miękkie ważenie losowania i anty-powtórka poprzedniej drużyny;
- uproszczone, opcjonalne wpisywanie strzelców: 3 kompaktowe wiersze +/− i możliwość dodania kolejnych;
- matematycznie bezpieczne **Pomiń mecz** w lidze + finał; pominięte spotkanie nie jest 0:0 i nie wchodzi do statystyk;
- **Przesuń mecz na później** — tylko gdy istnieje inny gotowy mecz; zmienia kolejność LIVE bez pomijania spotkania;
- rozliczenia rozszerzone o jackpot oraz eksport **TXT + PNG 1080×1080**;
- nowy ekran **AWARDS**: 19 kategorii nagród, TOP5 live, uzasadnienia, wybór organizatora z TOP2–3 oraz dwa rankingi podglądowe bez nagrody; `Król Strzelców FIFA Night` liczy konkretny duet piłkarz EA FC + gracz (np. Ferran Torres — Benio), a `Supersnajper Roku` sumuje gole piłkarza globalnie;
- roczne grafiki **Rok w liczbach** i **FIFA Night Awards**;
- usunięta osobna zakładka H2H ze Statystyk (same dane H2H pozostają w bazie i są dalej wykorzystywane).

## Kolejność między turniejami v1.7.0

Po utworzeniu kolejnego turnieju aplikacja sprawdza **bezpośrednio poprzedni zakończony turniej tego samego typu (testowy/produkcyjny)**. Gracz jest brany pod uwagę tylko wtedy, gdy wpisany nick jest identyczny znak w znak z nickiem z poprzedniego turnieju (po usunięciu przypadkowych spacji na początku/końcu).

Mechanizm działa również po zmianie liczby graczy lub formatu, np. 7 → 5, 5 → 7 albo 6 → 8. Pary i grupy są losowane normalnie. Dane z poprzedniego turnieju **nie zmieniają przeciwników** — mogą wyłącznie przestawić kolejność rozegrania już wylosowanych, niezależnych meczów otwierających.

W formatach ze Szczęśliwym losem losowanie pozostaje losowe, ale ma miękkie wagi: spośród aktualnych kandydatów osoba, która czekała najdłużej po swoim ostatnim meczu poprzedniego turnieju, ma 25% standardowej wagi na Szczęśliwy los, druga 50%, pozostali 100%. Nikt nie jest ze Szczęśliwego losu wykluczony. Przy remisie oczekiwania wybór osób z obniżoną wagą jest losowy, więc dotyczy maksymalnie dwóch graczy.

Priorytet z poprzedniego turnieju nie jest pokazywany na ekranie losowania. Algorytm kolejności najpierw ogranicza mecze back-to-back i długie przerwy, a dopiero potem wykorzystuje poprzednie oczekiwanie jako dodatkowy tie-breaker.

## Podsumowanie v1.7.0

- mistrz: gracz, drużyna, bilans W/R/P i bramki,
- miejsca 2–4: tylko gracz i drużyna,
- brak informacji o losowaniach Winners w podsumowaniu i PNG,
- strzelcy pozostają całkowicie opcjonalni; jeżeli nie wpisano żadnego, podsumowanie i PNG pokazują „Nie uzupełniono strzelców” zamiast błędu lub `0 goli`.



## v1.7.1
- Lepsze wyważenie kolejności między kolejnymi turniejami: finalista poprzedniego turnieju nie zaczyna od razu, jeśli można bezpiecznie dać mu jeden mecz przerwy.
- Rzeczywista kolejność poprzednich spotkań liczona po `played_at`.
- Status Testowy/Oficjalny można zmienić podczas turnieju i po jego zakończeniu.



## v1.7.3 — Performance
- bez zmian długości i wyglądu animacji,
- koło fortuny po kliknięciu korzysta z jednego lekkiego zapisu i od razu renderuje wynik — bez dodatkowego fragment rerun przed animacją,
- losowanie grup/drabinki nie zapisuje już grup po jednym graczu przed pokazaniem animacji; te zapisy są wykonywane dopiero po zaakceptowaniu losowania,
- ekrany przygotowania turnieju używają lżejszego stanu bez pobierania meczów,
- połączenia z Neon są utrzymywane w małej puli i ponownie używane pomiędzy rerunami Streamlit,
- losowania DE 5/7/8 pokazują animację bez dodatkowego odczytu po samym kliknięciu losowania,
- pełny fallback do starego sposobu łączenia pozostaje dostępny, jeśli pool nie jest jeszcze zainstalowany.

## v1.7.2
- W DE 7 losowanie Winners Bracket i Losers Bracket po pierwszej rundzie zostało połączone w jeden ekran i jeden przycisk.
- `BYE` w widocznym interfejsie zostało zastąpione określeniem `Szczęśliwy los`.
- Wewnętrzne klucze bazy pozostały bez zmian, więc aktywne i stare turnieje są kompatybilne.


## v1.7.4 — ważone wyrównanie drużyn między turniejami
- 4–5 graczy: kolejność draftu jest nadal losowa, ale miejsce z poprzedniego zakończonego turnieju delikatnie wpływa na szansę wcześniejszego wyboru drużyny; mistrz ma mniejszą, ostatnie miejsce większą szansę.
- Mechanizm działa także przy zmianie liczby graczy między turniejami; pozycja jest przeliczana względem wielkości poprzedniego turnieju.
- 6–8 graczy: Wild Cardy są losowane ważeniem 1.40 / 1.25 / 1.10 / 1.00 dla miejsc 1 / 2 / 3 / pozostałych. Pozostałe pięć klubów jest przydzielanych całkowicie losowo.
- Nowy gracz lub nick bez dokładnego odpowiednika w poprzednim turnieju ma neutralną wagę 1.00.
- Wagi nie są pokazywane w interfejsie i nie zmieniają animacji koła.


## v1.7.4.1 — hotfix połączeń Neon

- naprawione martwe połączenia pozostające w puli po uśpieniu Streamlit/Neon,
- każde połączenie z puli jest sprawdzane przed przekazaniem aplikacji,
- usunięty ręczny rollback w gałęzi poola; transakcją zarządza `pool.connection()`,
- zachowana pula połączeń i optymalizacje wydajności z v1.7.3.

## v1.7.5 — statystyki bez rozpoczynania turnieju

Na ekranie startowym jest teraz przełącznik `🎮 Nowy turniej / 📊 Statystyki`. Statystyki wszech czasów można przeglądać od razu po otwarciu aplikacji, bez tworzenia bieżącego turnieju. Widok korzysta z tego samego modułu statystyk co podczas aktywnego turnieju, więc ranking, H2H, rekordy, drużyny, profile graczy i strzelcy pozostają spójne.

## v1.7.5.1
- Hotfix nawigacji startowej: widoczne przyciski `NOWY TURNIEJ` i `STATYSTYKI` zamiast niewidocznie renderującego się segmented control.


## v1.7.6 — priorytet nowego gracza i rozliczenia stawek

- Gracz, który nie wystąpił w bezpośrednio poprzednim turnieju tej samej klasy (oficjalny/testowy), dostaje najwyższy miękki priorytet na wcześniejszy pierwszy mecz. Dotyczy to zarówno całkiem nowej osoby, jak i gracza wracającego po przerwie.
- Pary, grupy i drabinka nadal są losowane normalnie — zmienia się wyłącznie kolejność rozegrania już wylosowanych niezależnych meczów, jeśli można to zrobić bez pogorszenia bezpieczeństwa bieżącego terminarza.
- W DE 5 i DE 7 nowy gracz ma mocno obniżoną, ale nadal niezerową szansę na `Szczęśliwy los` (waga 0.15). Dzięki temu wejście do turnieju nie powinno kończyć się czekaniem do 5.–6. meczu tylko dlatego, że gracz dostał wolny slot.
- W pełni nowym składzie, w którym nikt nie grał poprzedniego turnieju, nie ma sztucznego priorytetu — wszyscy pozostają równi.
- Przy tworzeniu turnieju można wpisać `Stawkę na osobę (zł)`. Ostatnia wpisana stawka jest pamiętana jako domyślna na kolejny turniej.
- Model rozliczenia: każdy uczestnik wpłaca tę samą stawkę, zwycięzca bierze całą pulę.
- `Statystyki → Rozliczenia` pozwalają wybrać kilka zakończonych oficjalnych turniejów i skompensować wzajemne należności do krótkiej listy końcowych przelewów.
- Stawkę zakończonego turnieju można poprawić również później, więc starsze turnieje można uzupełnić retroaktywnie.
- Rozliczenie pokazuje bilans każdego gracza, gotową listę `kto → komu → ile`, tekst do skopiowania i plik TXT do pobrania.


## v1.7.7 — status rozliczeń i ranking finansowy

- Każdy zakończony oficjalny turniej może mieć status `🟠 nierozliczony` albo `✅ rozliczony`.
- Przy retroaktywnym wpisywaniu stawki można od razu zaznaczyć, że stary turniej został już rozliczony; status można później cofnąć.
- Domyślna lista wspólnego rozliczenia pokazuje tylko nierozliczone turnieje. Opcja `Pokaż także rozliczone turnieje` udostępnia pełną historię.
- Po wygenerowaniu listy przelewów można jednym przyciskiem oznaczyć wszystkie użyte turnieje jako rozliczone.
- `Statystyki → Rozliczenia` zawierają ranking finansowy wszech czasów: bilans, łączne wygrane, łączne wpłaty, liczbę płatnych turniejów i zwycięstw.
- Kafelki pokazują osobę najbardziej na plus i najbardziej na minus.
- Turnieje oznaczone jako rozliczone nadal liczą się do historycznego rankingu finansowego; status wpływa wyłącznie na listę bieżących należności.
- Nie ma migracji schematu: status jest przechowywany w istniejącym `extra_json`, więc starsze turnieje pozostają kompatybilne.

## v1.7.7.1 — czytelniejsza nawigacja startowa

- przyciski „🎮 NOWY TURNIEJ” i „📊 STATYSTYKI” zostały przeniesione pod główny baner FIFA NIGHT FLEX;
- nie są już narażone na przycięcie przez górny obszar Streamlita;
- brak zmian w bazie, statystykach i logice turniejów.

### Drobne poprawki Awards po wydaniu v1.8.0
- Beton Roku pokazuje i premiuje czyste konta.
- Opisy statystyk używają polskich nazw zamiast skrótów GF/GA/GD.
- Na końcu rankingów Awards znajduje się podsumowanie najczęściej nominowanych w TOP 3/TOP 5.
- Wybór laureatów jest ułożony w 3 etapy od najważniejszych nagród do kategorii specjalnych; przy kandydacie widać, ile nagród ma już wybranych.

### Awards hotfix 5 — czytelność rankingów i administracyjna zmiana nicku
- gdy mniej niż 5 osób spełnia warunki kategorii, nagłówek pokazuje `X zakwalifikowanych` zamiast mylącego `TOP X`;
- `Mecz Roku` premiuje przede wszystkim charakter meczu: bliskość wyniku, karne i bramkowość; stawka (odpadnięcie / tytuł) jest ważnym bonusem, ale nie może sama wynieść przeciętnego meczu, a ranga fazy pozostaje pomocnicza;
- opis `Rywalizacji Roku` podaje minimalną próbę oraz główne elementy rankingu;
- w sekcji `Historia i baza` administrator może po podaniu `ADMIN_PASSWORD` zmienić nazwę istniejącego gracza;
- zmiana nicku działa historycznie, ponieważ wszystkie wyniki są przypisane do stałego `player_id`; dodatkowo aktualizowane są tekstowe snapshoty ostatnich składów, gry za kasę i zapisanych laureatów Awards;
- zmiana nazwy nie łączy dwóch istniejących profili — kolizja z już istniejącym nickiem jest blokowana.


### Debiut Roku
Debiut Roku jest oceniany na podstawie początku kariery: AWARDS pokazuje osobno ranking pierwszych 5 i pierwszych 10 oficjalnych meczów turniejowych. Pierwsze 10 stanowi ranking główny do nagrody.

#### Awards hotfix 12
- gwarantowana widoczność `Najbardziej Widowiskowego Gracza` w kolejności AWARDS;
- naprawione nazwy kategorii w kolumnie `Kategorie TOP 2` w podsumowaniu nominacji;
- czytelne `brak TOP 2` zamiast pustej komórki oraz fallback widoku Debiutu Roku.

#### Awards hotfix 13
- uproszczono wszystkie opisy kategorii AWARDS;
- opisy mówią teraz tylko, za co jest dana nagroda i jakie wyniki bierze pod uwagę;
- usunięto z opisów techniczne wagi, procentowy podział algorytmów i sformułowania typu „premia” / „sensowna próba”;
- sposób liczenia rankingów nie został zmieniony.

## Odznaki graczy i kamienie milowe
Odznaki są częścią profilu konkretnego gracza w `Statystyki → Gracze`. Każda odznaka jest zwinięta i dopiero po rozwinięciu pokazuje opis, datę i miejsce zdobycia; osobno można rozwinąć listę odznak jeszcze niezdobytych. Globalne jubileusze całej historii FIFA Night zostały przeniesione do `AWARDS → Kamienie milowe`. Historyczne gole jubileuszowe mogą wymagać jednorazowego wskazania strzelca przez administratora, ponieważ w bazie przechowywane są sumy goli strzelców w meczu, a nie kolejność bramek.

### Live terminarz
W aktywnym turnieju terminarz jest prezentowany według aktualnej kolejności gry, nie wyłącznie według logicznych numerów meczów. Po każdym wyniku kolejność odświeża się automatycznie; `TERAZ` wskazuje bieżące spotkanie, `NASTĘPNY` kolejny już ustalony mecz, a zablokowane pozycje czekają na rozstrzygnięcie wcześniejszych par.

### Dodatkowe osiągnięcia i jubileusze
Odznaki graczy obejmują także sytuacyjne wyczyny: wygrany finał po karnych, trzy eliminacyjne zwycięstwa w jednym turnieju, zwycięski rewanż po wcześniejszej porażce, mistrzostwo bez straty gola, trzy wygrane jedną bramką oraz pokonanie obrońcy tytułu w kolejnym FIFA Night. Globalne jubileusze meczów, goli i zwycięstw są zapisywane przy 50/100 i dalej co 100, a czyste konta i hat-tricki co 25.

### Tryb TV i sterowanie urządzeniem

Aplikacja rozróżnia urządzenie ze sterowaniem od urządzeń działających bez sterowania. W `⚙️ Ustawieniach` po podaniu `ADMIN_PASSWORD` można włączyć sterowanie w bieżącej sesji przeglądarki. Bez sterowania każdy może uruchomić i prowadzić **testowy turniej FIFA Night** oraz **oficjalny mecz 1 vs 1**. Każde 1 vs 1 jest oficjalne — niezależnie od tego, czy jest grane za kasę, czy bez stawki. Oficjalny turniej FIFA Night dla 3–8 graczy wymaga sterowania. Zmiana już rozpoczętego turnieju z testowego na oficjalny również wymaga ponownego podania `ADMIN_PASSWORD` i jednocześnie włącza sterowanie na tym urządzeniu. Pozostałe urządzenia podczas aktywnego oficjalnego turnieju otwierają widok tylko do odczytu; aktywne 1 vs 1 można prowadzić bez sterowania.

W profilu gracza znajduje się także `🏆 Gablota` z trofeami, odznakami, wybranymi FIFA Night Awards i ważnymi momentami z historii.

### Hotfix 19 — drzewko Double Elimination

- w `Terminarzu` dla formatów DE 4–8 dodano przełącznik `📋 Lista / 🌳 Drzewko`;
- `Lista` nadal pokazuje faktyczną, dynamiczną kolejność rozgrywania gotowych meczów;
- `Drzewko` pokazuje osobno Winners Bracket, Losers Bracket i Wielki Finał, wraz z numerami logicznymi meczów M1, M2 itd.;
- na kartach widać aktualnych graczy i drużyny, wynik/status meczu oraz dalszą drogę zwycięzcy i przegranego (`W → ...`, `P → ...`);
- nierozstrzygnięte pary pokazują źródło uczestników, więc drabinkę można prześledzić także przed rozegraniem wcześniejszych spotkań;
- losowania pośrednie w DE5/DE7/DE8 są opisane jako możliwe ścieżki do czasu ustalenia konkretnej pary;
- bonusowe 1:0 dla zwycięzcy Winners Bracket jest oznaczone także na karcie Wielkiego Finału;
- brak zmian w bazie i w logice rozgrywania turnieju — jest to wyłącznie nowy widok tej samej drabinki.

### Hotfix 21 — czytelniejsze drzewko DE + szczegóły meczu

- widok DE renderuje się jako jeden kompaktowy canvas, bez surowego HTML w kartach i bez pustych obramowanych kolumn;
- Winners, Losers i Wielki Finał pozostają na jednej mapie;
- w widoku `Lista` każdy rozegrany mecz ma rozwijane `⚽ Szczegóły meczu` ze strzelcami obu stron i karnymi;
- szczegóły są dostępne także w Historii starych turniejów.

### Hotfix 22 — DE bracket polish
- Drzewko DE pozostaje zawsze poziome; na telefonie przewija się w bok.
- Rundy Winners są ułożone obok siebie bez sztucznej pustej kolumny.
- Wielki Finał jest częścią tego samego widoku i mieści się w głównym canvasie na typowym desktopie.
- Szczęśliwy los/BYE jest oznaczony wyłącznie przy tym konkretnym meczu/rundzie, w której gracz dostał wolny los; oznaczenie nie ciągnie się za graczem dalej po drabince.

### Hotfix 25 — TV AUTO
- w `📺 TV` dodano przełącznik `📺 LIVE / 🔄 AUTO` dla pełnych turniejów;
- `AUTO` co około 10 sekund przełącza trzy ekrany: `TERAZ / NASTĘPNY`, `SYTUACJA TURNIEJU` oraz `WYNIKI I STRZELCY`;
- dla Double Elimination ekran sytuacji pokazuje drzewko, a dla lig i grup — aktualną tabelę;
- tryb AUTO jest wyłącznie prezentacją i nie zmienia kolejności meczów ani algorytmu dobierającego następne spotkanie;
- awaryjne `Przesuń mecz na później` z Hotfix 24 pozostaje jedynym ręcznym odstępstwem od automatycznej kolejności.
- Hotfix 27: mechanizm przesuwania został przetestowany na wszystkich obsługiwanych formatach 3–8; dodatkowo pozycje ligowe/grupowe nie odblokowują już fazy pucharowej przed zamknięciem wszystkich meczów danej tabeli.

## Uproszczona nawigacja
Główne panele poza aktywną rozgrywką to tylko `🎮 FIFA NIGHT`, `📊 STATYSTYKI`, `🏆 AWARDS` i `⚙️ USTAWIENIA`. W panelu FIFA Night wybiera się od razu wariant `1 vs 1` albo liczbę graczy `3–8` — bez dodatkowego przełącznika trybu. Historia turniejów znajduje się w `Statystyki → Historia`. Drużyny i strzelcy są zebrani razem w `Statystyki → Drużyny i strzelcy`.

### Hotfix 29 — oficjalny FIFA Night zakończony przed końcem

Oficjalnego turnieju 3–8 graczy nie trzeba już ani dogrywać do końca, ani resetować, jeśli wieczór kończy się wcześniej. Na ekranie aktywnego oficjalnego turnieju organizator ma opcję `⏹️ Zakończ FIFA Night jako niedokończony`.

Po takim zamknięciu:
- wszystkie faktycznie rozegrane mecze pozostają oficjalne i liczą się do statystyk graczy, H2H, rekordów, statystyk drużyn, strzelców, Awards, odznak meczowych i globalnych kamieni milowych;
- nierozgrane spotkania nie dostają sztucznych wyników i w historii są oznaczone jako `NIE ROZEGRANO`;
- turniej zostaje w `Statystyki → Historia` jako `NIEDOKOŃCZONY` i zachowuje swój numer FIFA Night;
- nie ma mistrza, podium, tytułu ani rozliczenia finansowego/jackpotu;
- nie można go później wznowić — jest zamkniętym wpisem historycznym.

`Reset bieżącego turnieju` nadal usuwa cały bieżący turniej razem z rozegranymi wynikami i służy do sytuacji, w których danych nie chcemy zachowywać.

Przy okazji `AWARDS → Kamienie milowe → Oś historii` nie używa już przewijanej tabeli. Wpisy są grupowane po dacie (`DD-MM-RRRR`) w rozwijanych sekcjach, a pod datą pokazana jest pełna lista kamieni milowych z danego dnia — bez limitu 10/15 pozycji.
