# CHECKPOINT R31 — 2026-10-21 — profil odznak + nowy podział kategorii

## Cel
Po fizycznym feedbacku usunięto długą listę zdobytych odznak bezpośrednio z profilu gracza i przebudowano techniczne grupy R27 na czytelne kategorie użytkowe.

## Profil gracza
Sekcja `🎖️ Odznaki` jest teraz kompaktowa:
- pokazuje wyraźnie `X/53` zdobytych,
- ma tylko dwa wejścia:
  - `🎖️ ZOBACZ MOJE`,
  - `🏅 ZOBACZ WSZYSTKIE`,
- nie renderuje już kilkunastu/kilkudziesięciu rozwijanych odznak bezpośrednio na profilu.

`ZOBACZ MOJE` pokazuje wyłącznie zdobyte odznaki gracza. `ZOBACZ WSZYSTKIE` pokazuje pełny katalog wraz z warunkami i postępem. Oba widoki korzystają z kafelków kategorii i pokazują licznik `zdobyte / wszystkie` dla wybranej kategorii.

## Nowe kategorie — 53 odznaki
- 🏅 Kariera — 10
- 🔥 Forma i rywalizacja — 9
- 🎮 Mecze — 10
- 🎯 Bohaterowie i wydarzenia — 8
- 🏆 Turnieje — 8
- 👕 Drużyny — 5
- 💰 Finanse — 3

Usunięto z publicznego podziału techniczne nazwy `Summary`, `Events`, `H2H`, `Progres i serie` i `Turnieje i kariera`. Warunki zdobywania odznak nie zostały zmienione — zmienia się wyłącznie prezentacja / przypisanie kategorii.

## Streamlit
Profil Streamlit również nie pokazuje już pełnej ściany odznak. Zamiast tego ma dwa popovery `Zobacz moje` i `Zobacz wszystkie`, z tym samym semantycznym podziałem kategorii i licznikami.

## Testy
- `achievement_categories_profile_r31_smoke.py` — PASS
- `achievement_badges_r27_smoke.py` — PASS
- `records_summary_turnaround_r28_smoke.py` — PASS
- `achievement_badge_details_r29_smoke.py` — PASS
- `achievement_badge_context_r30_smoke.py` — PASS
- `summary_classifications_r26_smoke.py` — PASS
- `mobile_api_smoke.py` — 52/52 PASS
- Python compile: `database.py`, `app.py` — PASS
- `StatsScreen.tsx` TypeScript transpile/syntax parse — PASS
- pełny `npm run check` nadal nieoznaczony jako PASS, bo paczka nie zawiera `mobile/node_modules`.

Android `versionCode` pozostaje 15.
