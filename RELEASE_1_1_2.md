# FIFA Night Flex 1.1.2 — FULL FINAL

## Nowe / poprawione
- Poddanie meczu: turniejowe 3:0 / 0:3, ale poza bieżącym turniejem mecz nie istnieje statystycznie.
- Undo obsługuje poddanie.
- Rozdzielone akcje: Przesuń mecz na później / Nie rozgrywaj meczu / Poddaj mecz.
- Swiss 8/10: obowiązkowy ekran par po pełnej rundzie, ręczne zatwierdzenie przed startem kolejnej rundy.
- Swiss 8/10: poprawne 3. i 4. miejsce bez osobnego meczu o brąz.
- Streamlit: poprawione tabele L/S/A/B/C/F3; usunięty KeyError `tables["A"]` w Swiss.
- Wild Card: lekki boost TOP3 poprzedniego turnieju: 1.55 / 1.35 / 1.15 / 1.00.
- Awards: w wyborze laureata kandydat pokazuje statystyki / "dlaczego jest wysoko".
- Awards: można usunąć/resetować laureata pojedynczej kategorii i wybrać ponownie.
- Awards: nazwy grawerów przy kategoriach.
- DE Grand Final: techniczne +1 rozstrzyga tylko mecz zawodnika/drabinkę; nie jest prawdziwym golem w GF/GA, drużynach, Awards itd.
- Mecz Roku: nowsze mecze z kompletną osią wydarzeń dostają mały bonus (maks. +0.06) za wymianę ciosów, wyrównania i zmiany prowadzenia. Starsze mecze bez osi wydarzeń nie są karane.
- Copy/UI: skrócone sztywne opisy; więcej luźnych tekstów FIFA Night, mniej instrukcji brzmiących jak regulamin elektrowni.

## Walidacja
- Python compile: PASS
- forfeit_smoke: PASS
- swiss_smoke: PASS (Swiss8 + Swiss10)
- mobile_api_smoke: 51/51 PASS

Nie wykonano fizycznego EAS build / instalacji APK na urządzeniu w tym środowisku.
