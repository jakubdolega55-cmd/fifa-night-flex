# CHECKPOINT 2026-10-21 — R26 porządek w Klasyfikacjach po realnym podglądzie

## Decyzja po fizycznym podglądzie R25
Użytkownik zaakceptował wygląd `Advanced Stats` w profilu i poprosił, aby pozostawić je bez zmian.

Po obejrzeniu realnych danych uznano, że `Kliniczny` i `Marnotrawca` są tą samą osią xG oglądaną w dwie strony. `Marnotrawca` został więc usunięty z głównej sekcji `Klasyfikacje`.

## Co zmieniono
- usunięto `wasteful` z `CLASSIFICATION_DISPLAY_ORDER`,
- backend nie tworzy już kategorii `🗑️ Marnotrawca`,
- usunięto nieużywany quip `wasteful` ze Streamlit i PWA/APK,
- raw Summary/xG pozostaje bez zmian — dane można później wykorzystać np. w rekordzie/ciekawostce pojedynczego meczu,
- `Advanced Stats` pozostają bez zmian.
- uproszczono publiczne opisy wszystkich Klasyfikacji: opis mówi teraz ogólnie, **co dana klasyfikacja pokazuje**, bez wzorów, progów, minimalnej próbki i technicznego tłumaczenia rankingu,
- uogólniono również tekst wprowadzający sekcję Klasyfikacje w PWA/APK i Streamlit.

## Aktualne główne Klasyfikacje
1. ⚔️ Król 1 vs 1
2. 🎲 Król Wild Cardów
3. 🎯 Najbardziej Regularny
4. 🪓 Najostrzejszy Gracz
5. 🥇 Najwięcej pierwszych goli
6. 🎢 Król Nerwówek
7. 🎯 Kliniczny
8. 👑 Król Posiadania
9. 📈 Dominator
10. 🦹 Złodziej Meczów

## Testy
PASS:
- `python -m py_compile database.py app.py mobile_api.py`
- `tests/summary_classifications_r26_smoke.py` — obejmuje też kontrolę, że publiczne opisy nie ujawniają mechaniki rankingu
- `tests/awards_frequency_fairness_smoke.py`
- `tests/awards_logic_patch_smoke.py`
- `tests/mobile_awards_season_smoke.py`
- `tests/gala_counters_smoke.py`
- `tests/mobile_api_smoke.py` — 52/52 PASS

Pełny `npm run check` pozostaje do finalnego builda; zmiana w `AwardsScreen.tsx` dotyczy tylko tekstu/quipu i nie zmienia struktury komponentów.

## Android
`versionCode` pozostaje 15.

## Następny temat
Projektowanie odznak/rekordów/ciekawostek na podstawie wiarygodnego Summary. Nie dokładać nowych kategorii Gali bez osobnej decyzji użytkownika.
