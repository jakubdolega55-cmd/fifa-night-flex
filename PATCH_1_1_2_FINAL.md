# FIFA Night Flex 1.1.2 — FINAL

## Najważniejsze zmiany
- Poddanie meczu: 3:0/0:3 tylko dla logiki bieżącego turnieju; poza turniejem mecz nie istnieje w W/L, H2H, formie, GF/GA, ratingach, Awards, rekordach ani milestone'ach.
- Undo poddania.
- Czytelne akcje: Przełóż mecz / Nie rozgrywaj meczu / Poddaj mecz.
- Swiss 8 i Swiss 10: obowiązkowy ekran par między rundami, ręczne ZATWIERDŹ PARY / ROZPOCZNIJ RUNDĘ.
- Swiss 8/10: poprawne 3. i 4. miejsce bez osobnego meczu o brąz.
- Streamlit: naprawiony KeyError "A" dla Swiss; poprawne tabele S oraz grupy A/B/C.
- Wild Card: lekki boost dla TOP3 poprzedniego turnieju: 1.55 / 1.35 / 1.15.
- Laureaci Awards: dropdown pokazuje statystyki / "dlaczego jest wysoko"; można usunąć/resetować laureata pojedynczej kategorii.
- Mecz Roku: mały bonus za realny przebieg meczu, tylko gdy mamy kompletną kolejność goli. Maks. +0.06 za zmiany prowadzenia, wyrównania, wymianę ciosów i odrabianie strat. Starsze mecze bez timeline'u nie są karane.
- Techniczne +1 w finale DE nadal rozstrzyga W/L zawodnika, ale nie jest golem i nie wpływa na bilans drużyn/goli/Awards.
- Widoczne teksty i helpery są krótsze i luźniejsze; nazwy faktycznych providerów OCR/vision pozostają tam, gdzie są potrzebne technicznie.

## Walidacja
- Python compile: PASS
- forfeit_smoke.py: PASS
- swiss_smoke.py: PASS (Swiss8 + Swiss10)
- mobile_api_smoke.py: 51/51 PASS

## Mobile
- version: 1.1.2
- Android versionCode: 7
- package: pl.fifanight.flex
