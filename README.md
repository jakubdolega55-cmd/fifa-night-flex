# FIFA Night Flex v1.7.4.1

Responsywna aplikacja Streamlit do turniejów FIFA dla 4–8 graczy, z trwałym zapisem w Neon/PostgreSQL.

## Formaty

- 4 graczy — liga każdy z każdym + finał (7 meczów)
- 5 graczy — Double Elimination (8) albo liga + finał (11)
- 6 graczy — klasyczne 2×3 + SF + finał (9) albo rozszerzone 2×3 + QF + SF + finał (11)
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

- 4 i 5 graczy — losowanie kolejności draftu, następnie wybór drużyn z pozostałej puli.
- 6 graczy — koło fortuny: Bayern, Barcelona, PSG, Liverpool, Man City, Wild Card.
- 7 graczy — koło fortuny: 5 klubów + 2 Wild Cards.
- 8 graczy — koło fortuny: 5 klubów + 3 Wild Cards.
- Real Madryt pozostaje zablokowany przy Wild Card.

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

Pod wynikiem meczu można opcjonalnie rozpisać dokładnych strzelców. Dla każdej drużyny na wierzchu pojawia się 5 najpopularniejszych nazwisk z licznikami +/–. Pozostali są dostępni niżej, a nowego zawodnika można dopisać w polu `Inny zawodnik`. Po zapisaniu trafia do puli danej drużyny.

Liczniki są wewnątrz formularza meczu, więc ich zmiana nie uruchamia rerunu; wynik i strzelcy są zapisywani razem dopiero po `ZATWIERDŹ WYNIK`. Strzelcy są całkowicie opcjonalni i nie muszą sumować się do wyniku — można zostawić ich całkowicie pustych, np. przy samobójach albo gdy nie pamiętacie wszystkich nazwisk.

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
