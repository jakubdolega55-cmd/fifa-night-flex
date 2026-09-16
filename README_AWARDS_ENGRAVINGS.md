# FIFA Night — Awards engravings hotfix (1.1.1)

Zakres: tylko prezentacja nazw grawerów przy oficjalnych kategoriach Awards.
Logika liczenia rankingów, nominacji i wyboru laureatów nie została zmieniona.

## Mapowanie z tabeli pucharów

- Gracz Roku -> Player of the Year
- Ofensywny Gracz Roku -> Best Offensive
- Beton Roku -> Best Defensive
- Król Strzelców FIFA Night -> Top Scorer
- Clutch Player Roku -> Mr. Clutch
- Comeback King -> Never Say Die
- Król Końcówek -> Last Minute King
- Fair Play -> Fair Play
- Najbardziej Widowiskowy Gracz -> Showman of the Year
- Najbardziej Uniwersalny Gracz -> All-Rounder of the Year
- Debiut Roku -> Flying Start
- Najlepszy spoza dominatorów -> Best of the Rest
- Rekin Finansowy -> Financial Shark
- Mecz Roku -> Match of the Year
- Największy Progres -> Most Improved Player

Kategorie, które w tabeli mają `-` w kolumnie GRAWER, pozostają bez dodatkowej nazwy:
Rywalizacja Roku, Drużyna Roku, Supersnajper Roku.

## Pliki do podmiany w repo

Zachowaj dokładnie strukturę:

- `database.py`
- `app.py`
- `mobile/src/AwardsScreen.tsx`

Po pushu:
1. API/Render wykona auto-deploy (pole `engraving` będzie zwracane przez `/api/v1/awards/{year}`).
2. Streamlit po aktualizacji pokaże nazwę graweru w kartach Awards i w panelu wyboru laureatów.
3. PWA po swoim auto-deployu pokaże `GRAWER • ...` pod nazwą kategorii.
4. Jeśli chcesz mieć tę zmianę także w zainstalowanym APK, kolejny build APK musi zawierać ten zaktualizowany `mobile/src/AwardsScreen.tsx`.

## Walidacja

- `python -m py_compile app.py database.py mobile_api.py logic.py export_utils.py scorer_seeds.py ui.py` — PASS
- `python tests/mobile_api_smoke.py` — 51/51 PASS
