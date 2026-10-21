# FIFA NIGHT FLEX — HANDOFF 2026-10-21 — R27 / Android V15

## START HERE — NAJWAŻNIEJSZE

**Pracuj dalej wyłącznie na tej bazie:**

`FIFA-NIGHT-1.1.3-V15-R27-HANDOFF-FULL-2026-10-21.zip`

Stan aplikacji:
- FIFA NIGHT FLEX **1.1.3**
- checkpoint funkcjonalny: **R27**
- Android `versionCode`: **15**
- backend/Streamlit: Python + FastAPI + Streamlit
- mobile/PWA: Expo / React Native
- DB: Neon/Postgres
- hosting: Render

Nie wracaj do R15/R16/R17/R18/R19/R20/R21/R22/R23/R24/R25/R26 jako bazy. Wszystkie ich poprawki są już zawarte w R27.

**Najbliższy następny task: fizycznie obejrzeć R27 na realnych danych (53 odznaki + podział kategorii), a dopiero potem decydować o dalszych rekordach/ciekawostkach.**

Użytkownik pracuje najlepiej w trybie:
**jeden mały temat → test → checkpoint → patch GitHub → następny temat.**
Nie robić dużych, wielowątkowych patchy naraz i nie odpalać ciężkich suite’ów bez potrzeby, bo wcześniej zdarzały się limity czasu.

---

# 1. CO ZOSTAŁO ZROBIONE W OSTATNIM ETAPIE R17–R22

## R17 — liczniki Gali / statuetek
Naprawiono dwa osobne agregatory:

### „Najczęściej nominowani”
- liczy każdą kategorię Awards, w której nominowany jest **gracz FIFA Night**,
- każda kategoria liczy się maksymalnie raz na gracza,
- `Rywalizacja Sezonu` liczy obu uczestników,
- `Mecz Sezonu` liczy obu uczestników,
- `Król Strzelców FIFA Night` przypisuje nominację do gracza FIFA Night, dla którego strzelał piłkarz,
- `Drużyna Sezonu` i `Supersnajper Sezonu` nie liczą się do TOP3/TOP5 konkretnego gracza, bo kandydatem jest klub / realny piłkarz.

### „Rozkład statuetek do tej pory”
- liczy tylko **fizyczne statuetki**,
- `Mecz Sezonu` daje **2 statuetki** — po jednej każdemu uczestnikowi zwycięskiego meczu,
- `Rywalizacja Sezonu`, `Drużyna Sezonu` i `Supersnajper Sezonu` są pełnoprawnymi kategoriami Awards/Gali, ale **nie dają fizycznej statuetki**,
- aktualny łączny komplet fizycznych statuetek: **16**.

Użytkownik przed poprawką ręcznie policzył dla Kubsiego **14 kategorii TOP3 i 15 TOP5**, więc po wdrożeniu R17 należy fizycznie sprawdzić, czy UI pokazuje właśnie 14/15 dla tego stanu danych.

## R18 — Rok → Sezon + czytelniejsze metryki
- publiczne nazwy Awards/Gali przestawione z `Roku` na `Sezonu`, np.:
  - Gracz Sezonu
  - Drużyna Sezonu
  - Supersnajper Sezonu
  - Debiut Sezonu
  - Rywalizacja Sezonu
  - Mecz Sezonu
  - Clutch Player Sezonu
  - Beton Sezonu
  - Ofensywny Gracz Sezonu
- Clutch nadal ma wewnętrzną korektę małej próbki dla uczciwego rankingu, ale UI **nie pokazuje już „skorygowanego %”**,
- UI pokazuje surowy bilans np. `11/15 clutch • skuteczność 73,3%`,
- Comeback King pokazuje `pkt/mecz`, a nie `/10 meczów`,
- Król Końcówek pokazuje `gole 85+/mecz`, a nie `/10 meczów`,
- matematyczny balans tych rankingów nie został zmieniony — zmieniła się prezentacja.

## R19 — prawdziwe sezony Awards + „Zakończ sezon”
Dodano trwałą granicę sezonów Awards:
- aktywny sezon zapisany w `app_settings`,
- przy pierwszym wdrożeniu `Sezon 1` przejmuje aktualne dane i wybory laureatów z dotychczasowego 2026,
- Awards dla aktywnego sezonu liczą od jego `started_at`, nie od 1 stycznia na sztywno,
- po pełnej Gali admin może użyć **„Zakończ sezon”**,
- nie można zamknąć sezonu, gdy trwa aktywna oficjalna rozgrywka,
- zamknięcie zapisuje zamrożony snapshot Awards + Gali,
- kolejny sezon startuje dokładnie w chwili zamknięcia,
- nowy sezon ma czyste wybory laureatów i czystą Galę,
- **nie są zerowane**: mecze, H2H, statystyki all-time, odznaki, milestones, historia turniejów.

### Ważne dla testowej Gali
Jeżeli użytkownik chce tylko przejść testową Galę:
- robi pełną Galę,
- potem **resetuje laureatów/Galę**,
- **NIE klika „Zakończ sezon”**.

„Zakończ sezon” jest tylko dla prawdziwego zamknięcia okresu nagród.

## R20 — sezony w PWA/APK
Mobile/PWA zostały dostosowane do sezonów:
- selector `Sezon 1 / Sezon 2 / ...`, a nie lata,
- bieżący sezon pobierany z backendu,
- zamknięte sezony odczytywane z zamrożonych snapshotów,
- sterowanie Galą tylko dla aktywnego sezonu,
- PNG i nazwy plików używają sezonu,
- karty podsumowujące mówią `SEZON W LICZBACH`,
- profil gracza pokazuje nagrody jako `Sezon N • ...`,
- legacy routes roczne pozostawione dla kompatybilności.

Z tego powodu Android został podbity z `versionCode 14` do **15**.

## R21 — FC27 3/4/5: WC za częsty + stare koło przed pierwszym spinem
Użytkownik fizycznie zauważył:
- przy 3/4/5 osobach WC wpadał zdecydowanie za często,
- przed pierwszym kliknięciem Streamlit pokazywał stare/błędne koło.

Naprawiono:
- dla małego koła FC27 realny gracz ma mnożnik **x0.10 do otrzymania slotu Wild Card**,
- puste/ghost sloty pozostają neutralne x1.00,
- pięć nazwanych drużyn jest więc wyraźnie premiowanych,
- w deterministycznym teście WC pojawiało się orientacyjnie:
  - 3 osoby: ~5.6%
  - 4 osoby: ~23.3%
  - 5 osób: ~36.7%
- Streamlit przed pierwszym spinem bierze koło z backendowego `remaining_wheel_pool`, a nie rekonstruuje go z ukrytych przydziałów,
- koło prawidłowo zmniejsza się po kolejnych losowaniach,
- ostatni realny gracz w 3/4/5 nadal kręci, gdy zostaje więcej niż jedno pole.

**Wymaga fizycznego retestu** na prawdziwym turnieju 3/4/5.

## R22 — Streamlit sam wykrywa nowy turniej + kompaktowe koło
Użytkownik fizycznie zgłosił:
- po rozpoczęciu nowego turnieju na telefonie trzeba było ręcznie odświeżać Streamlit,
- na laptopie trzeba było mocno przewijać w dół, żeby zobaczyć koło.

Naprawiono:
- pasywny Streamlit sprawdza co **2 s** identyfikator aktualnego turnieju,
- po utworzeniu/resetowaniu turnieju z telefonu sam przeładowuje właściwy widok bez F5,
- po wykryciu nowego turnieju wraca do widoku LIVE/TV,
- podczas faz setup/draw publiczny widok pomija duży hero/nawigację i pokazuje TV SYNC wysoko,
- wariant compact: niższy iframe, mniejsze koło, mniejsze marginesy,
- istniejące odświeżanie pozostaje:
  - setup/draw ~1 s,
  - LIVE ~5 s,
  - AUTO ~30 s.

**Wymaga fizycznego retestu** na laptopie + telefonie.

## R23 — Android APK: zapis PNG
Naprawiono wspólny helper `mobile/src/export.ts` dla zapisu PNG w galerii Androida:
- projekt działa na Expo SDK 57,
- `saveToLibraryAsync()` nie może być używane z root importu `expo-media-library`, bo w SDK 57 stary interfejs został przeniesiony do legacy i rootowa metoda jest deprecated / rzuca błąd w runtime,
- import zmieniono na `expo-media-library/legacy`,
- ścieżka `UDOSTĘPNIJ` przez `expo-sharing` pozostała bez zmian,
- fix obejmuje FifaScreen, StatsScreen i AwardsScreen, bo wszystkie korzystają z `getPng()`.

Test `mobile_png_export_sdk57_smoke.py` PASS. Pełny `npm install && npm run check` nie został oznaczony PASS, bo instalacja zależności przekroczyła limit czasu.

**Wymaga fizycznego retestu w zbudowanym APK**: zapis i share podsumowania turnieju, rozliczenia oraz Awards/sezonu.

## R24 — AI screenshot parser / Events / scorer validation / shoot-out
Naprawiono i wzmocniono cały celowany obszar R24:
- direct red ma teraz mocniejszą regułę wizualną: czerwona prostokątna karta = `red_card`,
- dwa żółte wiersze tego samego piłkarza pozostają dwoma `yellow_card`; backend nadal wyprowadza jedno `second_yellow_red`,
- injury vs penalty miss zachowuje rozróżnienie medical pictogram vs goal/net + X,
- znaleziono realny błąd techniczny: resolver nazwisk działał na surowych eventach bez przypisanej drużyny; teraz działa na `fifa_night.events` po mapowaniu LEFT/RIGHT → HOME/AWAY,
- scorer `ambiguous/unresolved` przy golu ustawia odczyt jako `needs_review` i blokuje cichy zapis,
- Mobile i Streamlit pozwalają poprawić nazwisko; unresolved można ręcznie potwierdzić, gdy lista kadry jest niepełna,
- API również blokuje niepotwierdzonego scorera z AI,
- dla jawnego shoot-out backend odcina wielowierszową sekwencję karnych `120'` od zwykłych eventów,
- jawny przykład `3:3 + karne 7:6` jest zapisany jako zwykły wynik 3:3 + osobne penalties 7:6.

Testy:
- `event_parser_r24_smoke.py` PASS,
- penalty-miss / second-yellow / manual-event smokes PASS,
- `mobile_api_smoke.py` **52/52 PASS**,
- Python compile PASS,
- zmieniony TSX nie ma błędów składni,
- pełny `npm run check` nadal nie jest oznaczony PASS, bo `npm install` przekroczył limit i brak `node_modules`.

**Wymaga fizycznego retestu na prawdziwych screenshotach**, szczególnie direct red, scorer mismatch i długa seria karnych.

---

# 2. CO JEST JESZCZE DO ZROBIENIA — PRIORYTET

## R23 — APK: zapis grafik PNG — ZROBIONE
- wspólny fix w `mobile/src/export.ts`,
- import MediaLibrary przeniesiony do `expo-media-library/legacy` dla Expo SDK 57,
- wszystkie wywołania `getPng()` korzystają z poprawki,
- celowany smoke PASS,
- nadal wymagany fizyczny retest w APK.

## R24 — AI screenshot parser / Events / trudne karne — ZROBIONE
- direct red prompt wzmocniony,
- second-yellow nadal jako dwa yellow rows + backendowy `second_yellow_red`,
- injury / penalty miss doprecyzowane,
- scorer resolution przeniesione na zmapowane eventy z właściwą drużyną,
- błędny / niejednoznaczny scorer wymaga korekty lub świadomego potwierdzenia,
- score i shoot-out są separowane,
- `3:3 + 7:6` ma celowany smoke test,
- backend regression 52/52 PASS.

Wymagany jeszcze fizyczny retest na realnych screenshotach.

## R25 — Advanced Stats + porządek w Klasyfikacjach — GOTOWE
Dodano pierwsze wykorzystanie Summary jako osobny, nie-galowy moduł.

### Advanced Stats w profilu
Streamlit i PWA/APK pokazują (jeśli dane istnieją):
- xG/mecz, xGA/mecz, xGD/mecz,
- strzały/mecz i strzały rywala/mecz,
- średnie posiadanie,
- faule/mecz.

**Nie pokazujemy użytkownikowi liczby meczów z Summary.** Brak starych danych jest neutralny — nie jest zerem.

### Klasyfikacje po R25
Docelowa lista głównej sekcji Klasyfikacje:
1. Król 1 vs 1
2. Król Wild Cardów
3. Najbardziej Regularny
4. Najostrzejszy Gracz
5. Najwięcej pierwszych goli
6. Król Nerwówek
7. Kliniczny
8. Król Posiadania
9. Dominator
10. Złodziej Meczów

Z głównej listy wyjęto: Symulant, Penaldo, Samobóje, Niewykorzystane karne, Król Minimalistów i Pechowiec. Dane nie są kasowane — można później wykorzystać je jako ciekawostki/odznaki.

### Formuły
- **Król Nerwówek:** % meczów zakończonych różnicą 1 gola lub po karnych; tie-break = liczba takich meczów; min. 5 meczów turniejowych.
- **Kliniczny:** `(gole - xG)/mecz` na dokładnie tych samych meczach Summary; tylko dodatnie overperformance; min. 5.
- **Król Posiadania:** średnie possession; min. 5.
- **Dominator:** `xGD/mecz = xG - xGA`; min. 5.
- **Złodziej Meczów:** wygrana mimo niższego xG: 0.25–0.49 = 1 pkt, 0.50–0.99 = 2 pkt, >=1.00 = 3 pkt; ranking po pkt/mecz; min. 5.

### Wiarygodne Summary
R25 opiera nowe elementy na: xG, shots, possession, fouls. SOT nie jest podstawą nowych rankingów i został usunięty z bonusów Summary dla Widowiskowego/Meczu Sezonu. Parsowanie SOT może pozostać dla przyszłości, jeśli ekran poda jawny numer.

### Testy R25
- Python compile PASS
- nowy `summary_classifications_r25_smoke.py` PASS
- Awards fairness/logic PASS
- mobile Awards season PASS
- Gala counters PASS
- pełny `mobile_api_smoke.py` 52/52 PASS
- parser TypeScript dla zmienionych TSX PASS
- pełny `npm run check` nadal do finalnego builda, bo handoff nie zawiera node_modules.

---


## R26 — porządek w Klasyfikacjach po realnym podglądzie UI — GOTOWE
Po obejrzeniu R25 na realnych danych użytkownik zaakceptował `Advanced Stats` bez zmian.

`Marnotrawca` został usunięty z głównej sekcji Klasyfikacje, ponieważ jest matematycznie tą samą osią co `Kliniczny`, tylko odwróconą (`xG-gole` vs `gole-xG`). Raw Summary nie jest kasowane i może później zasilać ciekawostki/rekordy.

Publiczne opisy Klasyfikacji zostały uproszczone. Mają mówić ogólnie, **co dana klasyfikacja pokazuje**, ale nie ujawniać w UI wzorów, wag, progów, minimalnej próbki ani technicznego sposobu liczenia. Szczegółowa mechanika pozostaje tylko w kodzie/handoffie. Uogólniono też tekst wprowadzający sekcję Klasyfikacje w PWA/APK i Streamlit.

Aktualna lista głównych Klasyfikacji ma **10 pozycji**:
1. Król 1 vs 1
2. Król Wild Cardów
3. Najbardziej Regularny
4. Najostrzejszy Gracz
5. Najwięcej pierwszych goli
6. Król Nerwówek
7. Kliniczny
8. Król Posiadania
9. Dominator
10. Złodziej Meczów

Testy R26: compile PASS, summary classifications PASS (w tym kontrola nietechnicznych opisów), Awards/Gala smokes PASS, `mobile_api_smoke.py` 52/52 PASS. Android `versionCode` nadal 15.

---

## R27 — 18 nowych odznak + kategorie katalogu — GOTOWE
Po pełnym audycie istniejących 35 odznak użytkownik wybrał 18 nowych. Katalog ma teraz **53 odznaki**. Nie zmieniono Awards/Gali, Klasyfikacji ani formatów turniejów.

### Podział katalogu w UI
`category` jest wyłącznie metadanymi prezentacyjnymi. Streamlit i PWA/APK grupują katalog na:
- 📈 Progres i serie
- 🎮 Mecz
- 🧩 Events
- 📊 Summary
- ⚔️ H2H
- 🏆 Turnieje i kariera
- 👕 Drużyny
- 💰 Finanse

### Nowe odznaki R27
1. Pełna kontrola — wygrana + ≥60% possession + xGD ≥1.00 + przewaga strzałów ≥5.
2. Napad stulecia — wygrana mimo xG gorszego o ≥1.50.
3. Oblężenie — ≥15 strzałów i ≥3.00 xG w jednym meczu.
4. Zmarnowana jedenastka — wygrana mimo penalty miss w trakcie gry.
5. Sam sobie utrudnił — wygrana mimo własnego samobója.
6. Wieczny finalista — 3 przegrane finały bez tytułu pomiędzy.
7. Nemezis — 5 kolejnych zwycięstw H2H nad tym samym rywalem.
8. Przełamanie klątwy — 3 kolejne porażki H2H, następnie 3 kolejne zwycięstwa z tym samym rywalem.
9. Pogromca wszystkich — pokonani wszyscy rywale z min. 3 H2H, przy min. 4 kwalifikujących rywalach.
10. Podwójna korona — tytuł klubem i reprezentacją.
11. Mistrz wielu barw — tytuły trzema różnymi drużynami.
12. Wielki skok — **+200 zł netto lub więcej w jednym turnieju**, nie historycznie; 1v1 wyłączone.
13. Powrót na tron — nowy tytuł po min. 5 własnych kolejnych FIFA Night bez tytułu, po wcześniejszym mistrzostwie.
14. Klubowa legenda — 3 tytuły tym samym klubem; reprezentacje nie liczą się.
15. One Man Army — wygrana, min. 3 gole, wszystkie autorstwa jednego realnego piłkarza zwycięzcy.
16. Gaz do dechy — 3+ gole w 5 kolejnych oficjalnie rozegranych meczach.
17. Pięciopak — 5 goli jednego realnego piłkarza w jednym oficjalnym meczu.
18. Z pudła do bohatera — ten sam piłkarz pudłuje karnego i później zdobywa gola na wagę zwycięstwa.

### Ważne zasady
- stare mecze bez Summary są neutralne,
- nie używać SOT do tych odznak,
- shoot-out nie zwiększa zwykłych goli/scorer badges,
- syntetyczny DE +1 nie jest realnym golem,
- istniejących 35 odznak nie zmieniano poza przypisaniem kategorii UI.

### Testy R27
- `achievement_badges_r27_smoke.py` PASS — wszystkie 18 badge + 53 katalog + UI groups + próg Wielkiego skoku +200 zł,
- `summary_classifications_r26_smoke.py` PASS,
- Awards/Gala smokes PASS,
- `mobile_api_smoke.py` **52/52 PASS**,
- `versioning_alias_smoke.py` PASS,
- R24 Events parser / penalty miss / second yellow smokes PASS,
- Python compile PASS,
- zmieniony `StatsScreen.tsx` + kontrolnie `AwardsScreen.tsx` przechodzą parser TypeScript,
- pełny `npm run check` nadal do finalnego one-click builda (brak `node_modules` w paczce roboczej).

Android `versionCode` nadal **15**.

---

# 3. CO TRZEBA ZROBIĆ NA SAMYM KOŃCU, GDY WSZYSTKIE POPRAWKI BĘDĄ GOTOWE

## A. Pełny test regresji
Nie wystarczy tylko compile. Na finalnym checkpointcie uruchomić m.in.:
- Python compile głównych plików,
- mobile TypeScript `npm run check`,
- `expo-doctor`,
- mobile/API smoke,
- FC27 draw weights,
- FC27 small wheel 3/4/5,
- Real-ban,
- national mode,
- team repeat x0.10,
- season close,
- Gala payload/counters,
- visible tiebreak,
- Swiss,
- scheduler/BYE,
- cards/suspensions,
- screenshot parser tests po R24.

Jeżeli pełny `mobile_api_smoke.py` znowu grozi timeoutem, puszczać osobno / zwiększyć limit lokalnie, ale nie oznaczać PASS, jeśli test nie doszedł do końca.

## B. Fizyczny test na urządzeniach
Po finalnym deployu przejść przynajmniej jeden pełny wieczór/test:
- 3 graczy FC27 — koło + WC,
- 4 graczy FC27 — koło + WC,
- 5 graczy FC27 — koło + WC,
- 6 graczy — standardowe pełne koło,
- Real-ban OFF/ON,
- sprawdzić repeat-team x0.10 w kolejnych turniejach,
- sprawdzić Streamlit auto-detect nowego turnieju,
- sprawdzić pozycję koła na laptopie bez scrollowania,
- sprawdzić AUTO po zakończeniu losowań,
- sprawdzić zapis i share PNG w finalnym APK,
- sprawdzić Summary + Events na prawdziwych zdjęciach,
- sprawdzić zawieszenia za kartki,
- sprawdzić trudny shootout,
- przejść pełną testową Galę,
- zresetować laureatów bez zamknięcia sezonu,
- osobno testowo sprawdzić `Zakończ sezon` na kopii/test mode i powstanie Sezonu 2.

## C. Finalny APK
Po ostatniej zmianie mobilnej przygotować świeżą paczkę one-click i zbudować APK.

W tej paczce jest skrypt:
`ZBUDUJ_APK_1_KLIK.cmd`

Ma wykonać:
1. `npm install`,
2. verify lokalnych herbów,
3. TypeScript check,
4. Expo Doctor,
5. login EAS, jeśli trzeba,
6. `eas build --platform android --profile preview`.

Aktualny Android `versionCode = 15`.
- jeśli **V15 nie był jeszcze zainstalowany/dystrybuowany**, końcowy build po R23/R24 może nadal być V15,
- jeśli V15 zostanie wcześniej zainstalowany, każda kolejna binarka wymagająca upgrade’u powinna dostać V16.

## D. Deploy
Po finalnym patchu:
- wrzucić backend/Streamlit na GitHub/Render,
- PWA zbudować/deployować z tego samego finalnego checkpointu,
- APK budować dopiero z dokładnie tej samej wersji źródeł,
- nie mieszać backendu z wcześniejszym klientem mobilnym.

---

# 4. AKTUALNE ZASADY LOSOWANIA DRUŻYN

## EA FC 27 — kluby
Normalnie, Real-ban OFF, koło bazowe:
1. Real Madrid
2. PSG
3. Bayern
4. Barcelona
5. Arsenal
6. Wild Card

Pierwsza typowa propozycja WC: Manchester City.

### Real-ban ON
Koło:
- Manchester City
- PSG
- Bayern
- Barcelona
- Arsenal
- Wild Card

Real nie może wtedy wystąpić ani na kole, ani jako ręczny WC. City jest neutralne i nie przejmuje handicapu Realu.

## FC27 dla 3/4/5 osób
Od R8/R21:
- nadal **pełne 6 pól**: pięć nazwanych drużyn + WC,
- losuje tylko tylu realnych graczy, ilu gra,
- niewykorzystane pola przepadają,
- ostatni realny gracz nadal kręci, jeżeli zostało kilka pól,
- WC dla realnego gracza w partial wheel ma **x0.10**, dlatego częściej „spada” na niewykorzystany slot.

## Globalny anti-repeat drużyny
Od R15:
**dokładnie ta sama drużyna co w poprzednim turnieju = x0.10 normalnej wagi.**

Dotyczy wspólnego mechanizmu losowania, m.in. FC26/FC27 kluby i reprezentacje. To soft penalty, nie hard-ban.

## Real — dodatkowy handicap FC27
Dla Real Madrid w FC27 clubs:
- poprzedni mistrz: **x0.25**,
- poprzedni finalista: **x0.45**.

PSG pozostaje:
- mistrz: x0.40,
- finalista: x0.60.

## Ukryta korekta profilu losowania Realu
R13/R14:
- dostępna tylko w Streamlit po przejęciu sterowania/admin password,
- sekcja publicznie nazywa się neutralnie `Korekta profilu losowania`,
- brak limitu 3 graczy — można dodać dowolną liczbę kwalifikujących się graczy,
- każdy może mieć dodatkową redukcję Realu 0–90%,
- korekta jest po player ID,
- działa tylko dla nowych turniejów FC27 clubs,
- PWA/APK nie pokazują tej funkcji i mobile setup nie ujawnia snapshotu,
- Real-ban jest nadrzędny.

Przykład: poprzedni mistrz + korekta 50% → Real x0.25 × 0.50 = x0.125 przed dalszymi mnożnikami.

## Live Team Rating
Działa na stałe drużyny z koła. Dla TOP3 z poprzedniego turnieju:
- mistrz coef 0.018,
- finalista 0.012,
- 3. miejsce 0.006,
- inni 0.

Formuła:
`weight *= exp((50-rating)*coef)`

## FC27 reprezentacje
Koło główne:
- Hiszpania
- Anglia
- Brazylia
- Niemcy
- Portugalia
- WC

Francja jest wykluczona z bazowego założenia tego trybu.
Strong national teams:
- Hiszpania / Brazylia
- mistrz x0.50
- finalista x0.70
- 3. miejsce x0.85

## Wild Card — poprzednie placement weights
Historyczna preferencja WC pozostaje:
- poprzedni mistrz 1.70
- finalista 1.45
- 3. miejsce 1.15
- inni 1.00

W partial wheel R21 mnożnik real-player-WC x0.10 składa się z tym mechanizmem.

---

# 5. FORMATY TURNIEJÓW — NIE DODAWAĆ NICZEGO „QUICK” DLA 5/6/7 BEZ NOWEJ PROŚBY

Aktualne formaty:
- 3: `league3_final`
- 4: `league4_final`, `double4`
- 5: `double5`, `league5_final`
- 6: `groups6`, `groups6_full`, `double6`
- 7: `double7`, `groups7`, `groups7_sf`
- 8: `groups8_sf`, `knockout8`, `double8`, `groups8_barrage`, `swiss8`
- 9: `groups9_final4`, `groups9_barrage_final3`, `groups9_top8`, `double9`
- 10: `groups10_sf`, `swiss10`, `double10`

Użytkownik wcześniej rozważał szybkie formaty 5/6/7, ale powiedział **„nic nie dodajemy z tego”**. Nie przywracać bez nowej prośby.

8-player quick KO:
- brak meczu o 3. miejsce,
- 3. miejsce z bilansu,
- przy idealnym remisie mogą być dwa 3. miejsca.

9-player ulubiony wariant:
- 3 grupy po 3 + Final Four,
- 12 meczów.

---

# 6. TIEBREAK / LOSOWANIA ROZSTRZYGAJĄCE

R5 pozostaje bazą:
Jeżeli po wszystkich sportowych kryteriach jest remis wpływający na awans/bracket/podium:
1. downstream stop,
2. Streamlit/TV pokazuje `LOSOWANIE ROZSTRZYGAJĄCE`,
3. telefon/kontroler uruchamia losowanie,
4. reveal kolejności,
5. `ZATWIERDŹ WYNIK LOSOWANIA`,
6. dopiero ACK zapisuje wynik i turniej idzie dalej.

Nieistotne remisy nie uruchamiają losowania.

Grupa/liga:
pts → GD → GF → H2H/mini-table → fair play → visible draw.

Swiss:
pts → Buchholz → GD → goals → H2H gdzie możliwe → draw.

Specjalny dokładny remis w ostatnim bezpośrednim meczu grupowym nadal może być rozstrzygany ET + karne zgodnie z istniejącą regułą — nie zastępować go loterią.

---

# 7. REST / BYE / SCHEDULER

Dynamic BYE/Lucky repeat penalty:
- 0 wcześniejszych BYE: 1.00
- 1: 0.25
- 2: 0.10
- 3+: 0.05

Anti-marathon scheduler:
- jeżeli są >=2 legalne gotowe mecze, preferuje odpoczynek,
- mocniej karze 2+ mecze z rzędu,
- patrzy na workload ostatnich 4 rozegranych spotkań,
- nie zmienia legalności bracketu — tylko kolejność gotowych meczów.

Poprzedni mistrz/finalista nie powinni otwierać nowego turnieju, jeżeli istnieje legalna alternatywa. Newcomer priority nie może tego nadpisać.

---

# 8. AWARDS / GALA — AKTUALNY STAN

## Kolejność 18 kategorii
1. Supersnajper Sezonu
2. Drużyna Sezonu
3. Rekin Finansowy
4. Debiut Sezonu
5. Największy Progres
6. Najlepszy spoza dominatorów
7. Rywalizacja Sezonu
8. Fair Play
9. Najbardziej Uniwersalny Gracz
10. Comeback King
11. Król Końcówek
12. Najbardziej Widowiskowy Gracz
13. Mecz Sezonu
14. Clutch Player Sezonu
15. Król Strzelców FIFA Night
16. Beton Sezonu
17. Ofensywny Gracz Sezonu
18. Gracz Sezonu

Gala wybiera od najważniejszej do najmniej ważnej, ale publiczny show idzie odwrotnie, żeby **Gracz Sezonu był ostatni**.

## Fizyczne statuetki
Łącznie: **16**.

Bez fizycznej statuetki, ale nadal pełnoprawne Awards/Gala/laureat:
- Rywalizacja Sezonu
- Drużyna Sezonu
- Supersnajper Sezonu

Mecz Sezonu:
- 2 fizyczne statuetki — po jednej dla obu uczestników zwycięskiego meczu.

## Nominees
- TOP3 bez punktów/metryk w teaserze,
- laureat może pokazać pełne metryki.

## R9 fairness — ważne
Kategorie znormalizowane, żeby nie premiować głównie liczby rozegranych meczów:
- Najlepszy spoza dominatorów: W% + GD/mecz + % turniejów z finałem,
- Rywalizacja: frequency bonus cap po 6 H2H + balance/stakes/drama,
- Uniwersalny: % drużyn z sukcesem + ograniczony diversity bonus,
- Comeback: punkty/mecz + max comeback,
- Król Końcówek: gole 85+/mecz + mały capped total bonus,
- Clutch: smoothed success rate, nie surowe clutch wins,
- Beton: GA/mecz + clean-sheet % + xGA/mecz,
- Ofensywny: goals/mecz + wysokie zwycięstwa + max margin + xG/mecz + shots/mecz,
- Gracz Sezonu: bez bonusu za sam start w turnieju.

## Comeback scoring
Deficyt 1:
- win 1
- draw / lost shootout 0.5

Deficyt 2:
- win 2
- draw / lost shootout 1

Deficyt 3:
- win 4
- draw / lost shootout 2

Deficyt 4:
- win 7
- draw / lost shootout 3.5

Equalize + shootout win = pełne punkty; shootout loss = połowa.

---

# 9. 1 VS 1 — NIE ZMIENIAĆ, UŻYTKOWNIK POWIEDZIAŁ „JEST GIT”

1v1 jest oficjalnym meczem statystycznym, ale nie turniejem.

Liczy się do:
- meczów ogółem,
- W/D/L,
- GF/GA/GD,
- W%,
- forma last 5,
- H2H,
- profil/historia,
- rankingi all-time zależne od wins/GD/goals,
- ogólne rekordy / Hall of Fame,
- generic badges,
- milestones ogólne,
- team stats,
- Live Team Rating,
- Supersnajper,
- Drużyna Sezonu,
- Rekin Finansowy, jeżeli płatne,
- osobny Król 1 vs 1.

Nie liczy się do:
- tytułów/finałów/liczby turniejów,
- Gracza Sezonu,
- większości tournament-specific Awards (Ofensywny, Beton, Clutch, Comeback itd.),
- Rywalizacji Sezonu,
- Króla Strzelców FIFA Night tournament-specific,
- zawieszeń turniejowych.

Kartki 1v1 nie przenoszą zawieszenia do kolejnego turnieju.

---

# 10. EVENTS / KARTKI / SUMMARY — STAN PO R24

## Kartki
- 2 żółte w różnych meczach → pauza w następnym faktycznie rozegranym meczu,
- 2 żółte w jednym meczu → `second_yellow_red` i jedna pauza,
- nie tworzyć sztucznej podwójnej czerwonej/statystyki.

## Penalty miss vs injury
Istniejący parser rozróżnia:
- bramka/siatka/piłka z X → `penalty_miss`,
- bandaż/plaster/medyczna ikonka → `injury`.

R24 zachowuje to rozróżnienie i dodatkowo wymusza `unknown` zamiast zgadywania, gdy ikona jest niejednoznaczna. Nadal wymagany realny retest screenshotów.

## Scorers
- manual suggestions tylko z kadry bieżącej drużyny,
- free text nadal dozwolony,
- aliasy typu `B. Saka → Bukayo Saka`,
- R24: resolver działa na eventach już przypisanych do właściwego teamu,
- `ambiguous/unresolved` scorer przy golu blokuje automatyczne zatwierdzenie,
- unresolved można ręcznie potwierdzić, jeżeli lista kadry nie obejmuje danego zawodnika.

## Shootout
- karne po 120' przechowywane osobno,
- próby serii nie zwiększają zwykłych goli/scorer stats,
- R24: jawny shoot-out + wielowierszowe karne `120'` są odfiltrowywane z normalnych eventów,
- przykład 3:3 + 7:6 ma osobny celowany smoke test.

## 90+
EA potrafi pokazywać 90 zamiast 90+, dlatego metryka „najpóźniejszy gol” została uznana za niewiarygodną i nie powinna wracać.

---

# 11. TEAM VISUALS / TV / REFRESH

Herby/flagi pokazują się tylko w:
1. wyniku losowania drużyny,
2. aktualnym meczu,
3. `Następny mecz`.

Nie rozszerzać ich na tabelę, bracket ani zwykłe listy meczów bez prośby.

Assety są lokalne, spakowane w projekt.
- kluby = herby,
- reprezentacje = flagi,
- fallback = inicjały dla nieznanego/ręcznego WC.

Chelsea została świadomie pominięta — użytkownik powiedział, żeby jej nie dodawać.

Refresh:
- draw/setup ~1 s,
- LIVE ~5 s,
- AUTO ~30 s,
- R22 dodatkowo co 2 s wykrywa zmianę aktywnego tournament ID.

---

# 12. MILESTONES

Istnieją m.in.:
- pierwsza czerwona kartka,
- pierwszy gol w dogrywce,
- pierwszy samobój,
- pierwszy mistrz DE,
- pierwszy mistrz Swiss,
- pierwszy mistrz KO.

Nie wracać do starej pomyłki „first win Swiss/KO” — użytkownik chciał **pierwszego mistrza formatu**, nie pierwszego zwycięzcę meczu.

---

# 13. FINANSE / TURNIEJ BEZ STAWKI

Oficjalny turniej może być rozegrany bez pieniędzy:
- wystarczy ustawić **stake = 0 zł**,
- statystyki/Awards/historia nadal działają,
- nie trzeba dodatkowo wyłączać flag cash u każdego gracza.

---

# 14. CO ZOSTAŁO FIZYCZNIE SPRAWDZONE, A CO NIE

Nie pisać użytkownikowi, że coś było fizycznie przetestowane, jeżeli przeszło tylko test automatyczny.

### Historycznie użytkownik potwierdzał fizycznie m.in.
- multi-device (ok. 5 urządzeń + controller),
- PWA Events + Summary,
- wcześniejsze uploady APK,
- alias merging,
- Supersnajper / Król Strzelców,
- Comeback King,
- Król Końcówek,
- Awards active/live,
- forfeit,
- Gala testowana wcześniej,
- większość draw flow.

### Aktualnie wymaga fizycznego retestu po najnowszych zmianach
- R17 TOP3/TOP5 counters na realnych danych,
- R19/R20 Sezon 1 / Sezon 2,
- testowa Gala → reset laureatów bez zamknięcia sezonu,
- `Zakończ sezon` → snapshot + Sezon 2,
- R21 WC balance w 3/4/5,
- R21 poprawne koło przed pierwszym spinem,
- R22 automatyczne wykrycie nowego turnieju,
- R22 brak dużego scrollowania do koła,
- final-team visibility,
- previous finalists opener,
- NEXT projection,
- Real-ban w finalnym V15 APK,
- Events/cards na realnych screenshotach,
- trudny shootout,
- PNG save/share po R23.

---

# 15. TESTY OSTATNICH CHECKPOINTÓW

R17:
- gala_counters_smoke PASS
- Python compile PASS

R18:
- gala_counters_smoke PASS
- awards_logic_patch_smoke PASS
- awards_frequency_fairness_smoke PASS
- gala_tv_payload_smoke PASS
- gala_closeout_smoke PASS

R19:
- awards_season_close_smoke PASS
- gala_counters_smoke PASS
- gala_tv_payload_smoke PASS
- awards_logic_patch_smoke PASS
- compile PASS

R20:
- endpointy sezonowe / snapshots / dedupe testowane,
- zmienione TS/TSX przeszły parser,
- pełny `npm run check` w roboczej kopii nie został oznaczony PASS, bo brakowało `node_modules`; finalny build script instaluje zależności i musi wykonać pełny check.

R21:
- compile PASS
- fc27_partial_wheel_wc_bias_smoke PASS
- tv_partial_wheel_idle_source_smoke PASS
- fc27_small_wheel_smoke PASS
- fc27_draw_weight_tuning_smoke PASS
- team_repeat_penalty_smoke PASS
- mobile_api_smoke nie doszedł do końca przez limit czasu; brak zaobserwowanej regresji przed timeoutem, ale nie oznaczono pełnego PASS.

R22:
- compile PASS
- streamlit_auto_tournament_compact_tv_smoke PASS
- tv_partial_wheel_idle_source_smoke PASS
- milestones_refresh_modes_smoke PASS
- fc27_small_wheel_smoke PASS

R23:
- mobile_png_export_sdk57_smoke PASS
- pełny npm check NIE oznaczony PASS (brak node_modules / timeout npm install)

R24:
- Python compile PASS
- event_parser_r24_smoke PASS
- penalty_miss_icon_prompt_smoke PASS
- second_yellow_red_counters_smoke PASS
- manual_event_scorer_draw_smoke PASS
- mobile_api_smoke 52/52 PASS
- TSX parser: brak błędów składni
- pełny npm check NIE oznaczony PASS (npm install timeout / brak node_modules)

---

# 16. PLIKI KLUCZOWE

Backend / logika:
- `database.py`
- `logic.py`
- `mobile_api.py`
- `app.py`
- `ui.py`
- `export_utils.py`

Mobile/PWA:
- `mobile/src/FifaScreen.tsx`
- `mobile/src/StatsScreen.tsx`
- `mobile/src/AwardsScreen.tsx`
- `mobile/src/export.ts`
- `mobile/src/export.web.ts`
- `mobile/src/api.ts`
- `mobile/src/types.ts`
- `mobile/app.json`

Build:
- `ZBUDUJ_APK_1_KLIK.cmd`
- `BUILD_APK_WINDOWS.cmd`
- `mobile/build-preview.ps1`

Assets:
- `assets/teams/...`
- `mobile/assets/teams/...`

---

# 17. ZASADY PRACY W KOLEJNEJ ROZMOWIE

1. Zacząć od pełnej paczki R27 z tym handoffem.
2. R23 — APK PNG jest zrobione; przed finalem wykonać fizyczny retest.
3. R24 — AI parser jest zrobiony automatycznie; wymaga fizycznego retestu na realnych screenshotach.
4. R25/R26 — Advanced Stats + oczyszczone Klasyfikacje są wdrożone; Marnotrawca usunięty, a opisy Klasyfikacji są celowo nietechniczne.
5. R27 — 18 nowych odznak i podział 53-pozycyjnego katalogu są wdrożone; przed dalszym rozszerzaniem obejrzeć je fizycznie na realnych danych. Nie dokładać nowych kategorii do Gali bez nowej decyzji użytkownika.
6. Na samym końcu pełny regression + fizyczny test + finalny one-click APK.

Jeżeli user napisze po prostu „działaj dalej” po zaakceptowaniu R27, najbliższy konkretny task to:
**najpierw zebrać fizyczny feedback z realnego katalogu 53 odznak / kategorii; dopiero później projektować ewentualne rekordy lub ciekawostki, bez dokładania nowych kategorii Gali.**

---

# 18. WAŻNE RZECZY, KTÓRYCH NIE ZMIENIAĆ PRZY OKAZJI

- Nie dodawać quick formatów 5/6/7.
- Nie zmieniać 1v1 — user zaakceptował obecne działanie.
- Nie przywracać „Roku”; używać „Sezonu”.
- Rywalizacja Sezonu **zostaje** w Awards, laureatach i Gali; tylko nie ma fizycznej statuetki.
- Drużyna Sezonu i Supersnajper Sezonu też są normalnymi kategoriami Gali bez statuetki przypisanej graczowi FIFA Night.
- Nie usuwać wewnętrznej sample-size correction z Clutch; tylko nie pokazywać jej w UI.
- Exact team repeat pozostaje x0.10 globalnie.
- R21 WC partial-wheel bias pozostaje x0.10 dla real-player WC owner.
- Ukryta korekta Realu ma pozostać niewidoczna w PWA/APK.
- Nie ujawniać tego feature’u w mobile setup payload.
- Chelsea nadal pominięta.
- Herby/flagi tylko w 3 ustalonych miejscach.
- Nie inferować SOT z shot accuracy.

---

# 19. AKTUALNY BUILD APK

`mobile/app.json`:
- app version: `1.1.3`
- package: `pl.fifanight.flex`
- Android `versionCode`: **15**

R20 wymaga finalnie nowego APK V15, bo zmienił mobile UI sezonów.
R21/R22/R23/R24 nie wymagały kolejnego bumpa w tej gałęzi, ponieważ V15 nie został w tej rozmowie potwierdzony jako zainstalowany/dystrybuowany.

Wcześniejszy V14/R16 build source nie jest już bazą do dalszej pracy.

