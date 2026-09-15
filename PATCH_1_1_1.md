# FIFA Night Flex 1.1.1 — patch po teście DE10

Patch na bazie 1.1.0 BIG PATCH.

## Poprawione
- Koło drużyn kurczy się po każdym zatwierdzonym picku we wszystkich trybach korzystających z koła.
- Wskaźnik koła i faktycznie zapisany slot/drużyna są zgodne; Wild Card nie może wizualnie wypaść jako inna drużyna.
- Wild Card suggestions są dobierane wg wersji gry turnieju; FC27 zaczyna m.in. od Liverpoolu zgodnie z ustaloną hierarchią WC.
- Streamlit/TV: większe i czytelniejsze koło, skrócone etykiety slotów WC.
- Startowe losowanie DE/Swiss pokazuje konkretne pary meczów, a nie samą listę A/B/C; DE10 oznacza M1/M2 jako PLAY-IN i M3–M6 jako WB QF.
- Losowania pomiędzy meczami na Streamlit/TV pokazują duże karty par z numerem i typem meczu.
- Drabinka pokazuje faktycznie wylosowane źródła (np. Przegrany M5 / Zwycięzca M13), zanim placeholder rozstrzygnie się do nazwiska.
- DE10: BYE/Bridge i przyszłe crossy M14/M15 są jednym spójnym losowaniem zamiast dwóch ekranów jeden po drugim.
- Podsumowanie DE9/DE10 pokazuje 3. i 4. miejsce.
- Pełna klasyfikacja historyczna DE9/DE10 ma poprawne miejsca 1..N.
- API/mobile podniesione do 1.1.1; Android versionCode 6.

## Walidacja
- Python py_compile: PASS
- mobile_api_smoke: 51/51 PASS
- big_patch_smoke: 8/8 PASS
- Swiss smoke: PASS
- DE4/5/6 draw smoke: PASS
- DE9/DE10 full smoke: PASS
- visible draw policy: PASS
- smart scheduler: PASS
- versioning/Awards/Real/WC: PASS
- wheel shrink smoke: PASS (10 -> 0, visual target == backend target)
- TS/TSX parser: 13 files, 0 syntax errors

Pełny npm install / expo-doctor wymaga środowiska z zależnościami i pozostaje krokiem przed buildem APK.
