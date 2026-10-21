# CHECKPOINT 2026-10-21 — R27 — NOWE ODZNAKI + PODZIAŁ KATALOGU

## Zakres
R27 dodaje zaakceptowany przez użytkownika zestaw **18 nowych odznak** bez zmian w Awards/Gali, Klasyfikacjach, losowaniu drużyn ani formatach turniejów.

Katalog rośnie z **35 do 53 odznak**. Każda odznaka ma pole prezentacyjne `category`, a ekran „Jak zdobywać odznaki?” w Streamlit oraz PWA/APK pokazuje je grupami:
- 📈 Progres i serie
- 🎮 Mecz
- 🧩 Events
- 📊 Summary
- ⚔️ H2H
- 🏆 Turnieje i kariera
- 👕 Drużyny
- 💰 Finanse

## 18 nowych odznak — finalne warunki

1. **👑 Pełna kontrola** — wygrana + ≥60% posiadania + przewaga xG ≥1,00 + co najmniej 5 strzałów więcej od rywala.
2. **🦹 Napad stulecia** — wygrana mimo xG niższego od rywala o ≥1,50. Wygrana po karnych też może spełnić warunek, bo zwycięzca meczu jest brany z oficjalnego wyniku.
3. **💣 Oblężenie** — w jednym meczu ≥15 strzałów i ≥3,00 xG. Wynik meczu nie ma znaczenia.
4. **😬 Zmarnowana jedenastka** — wygrana mimo `penalty_miss` własnej drużyny podczas gry; seria karnych nie liczy się jako penalty_miss.
5. **🤦 Sam sobie utrudnił** — wygrana mimo samobója własnej drużyny.
6. **🥈 Wieczny finalista** — 3 przegrane finały bez zdobycia tytułu pomiędzy nimi. Turniej bez finału nie resetuje serii; tytuł resetuje.
7. **👻 Nemezis** — 5 kolejnych zwycięstw H2H z tym samym rywalem. Mecze z innymi nie przerywają serii. Remis/porażka z tym rywalem resetuje.
8. **🔄 Przełamanie klątwy** — 3 kolejne porażki H2H z jednym rywalem, a następnie 3 kolejne zwycięstwa z nim.
9. **🌐 Pogromca wszystkich** — pokonaj każdego rywala, z którym masz co najmniej 3 oficjalne H2H, przy minimum 4 takich rywalach. Po zdobyciu badge nie jest odbierany przez późniejsze pojawienie się nowego kwalifikującego rywala.
10. **🌎 Podwójna korona** — co najmniej jeden tytuł klubem i co najmniej jeden tytuł reprezentacją.
11. **👕 Mistrz wielu barw** — tytuły co najmniej trzema różnymi drużynami.
12. **💸 Wielki skok** — **+200 zł netto lub więcej w jednym FIFA Night / turnieju**. Nie jest to bilans historyczny i nie liczy 1v1.
13. **👑 Powrót na tron** — po wcześniejszym tytule co najmniej 5 kolejnych własnych FIFA Night bez mistrzostwa, a następnie ponowny tytuł. Liczą się tylko turnieje, w których gracz uczestniczył.
14. **🏛️ Klubowa legenda** — 3 tytuły tym samym klubem. Reprezentacje nie liczą się do tej odznaki.
15. **🦸 One Man Army** — wygrana, minimum 3 gole i wszystkie gole zwycięzcy zdobyte przez tego samego realnego piłkarza. Samobój rywala wyklucza warunek „wszystkie gole jednego piłkarza”. Karne w serii nie są golami.
16. **🔥 Gaz do dechy** — co najmniej 3 gole w 5 kolejnych oficjalnych meczach. Nie trzeba wygrać tych spotkań. Forfeit nie jest traktowany jako normalnie rozegrany mecz.
17. **✋ Pięciopak** — jeden realny piłkarz zdobywa 5 goli w jednym oficjalnym meczu. Gole z karnego podczas gry liczą się; seria karnych nie.
18. **🚫 Z pudła do bohatera** — ten sam piłkarz najpierw nie wykorzystuje karnego, a później zdobywa gola na wagę zwycięstwa w tym samym meczu.

## Zasady danych
- Summary badges korzystają tylko z zapisanych, `usable_for_awards` danych Summary; brak starych danych jest neutralny.
- Nie inferujemy SOT. R27 nie potrzebuje SOT.
- Event badges powstają tylko, gdy istnieje kompletna, wiarygodna oś realnych goli dla warunków wymagających kolejności/strzelca.
- Syntetyczny +1 w DE Grand Final jest wyłączony z odznak strzeleckich.
- Gole z serii karnych nie zwiększają zwykłych statystyk scorerów ani tych odznak.
- 1v1 nadal może zdobywać ogólne match/progress/H2H badge, ale nie turniejowe; `Wielki skok` celowo nie liczy 1v1.

## UI
- `app.py`: katalog Streamlit pogrupowany według kategorii.
- `mobile/src/StatsScreen.tsx`: modal „Jak zdobywać odznaki?” pogrupowany tak samo.
- Nie zmieniono zasad istniejących 35 odznak — dodano jedynie `category` jako metadane prezentacyjne.

## Testy
- `achievement_badges_r27_smoke.py` — PASS; pokrywa pozytywnie wszystkie 18 nowych odznak, 53-pozycyjny katalog, poprawne kategorie, podział UI oraz finalny próg Wielkiego skoku +200 zł.
- `summary_classifications_r26_smoke.py` — PASS.
- `awards_logic_patch_smoke.py` — PASS.
- `awards_frequency_fairness_smoke.py` — PASS.
- `gala_counters_smoke.py` — PASS.
- `gala_tv_payload_smoke.py` — PASS.
- `mobile_api_smoke.py` — **52/52 PASS**.
- `versioning_alias_smoke.py` — PASS.
- `event_parser_r24_smoke.py` — PASS.
- `penalty_miss_icon_prompt_smoke.py` — PASS.
- `second_yellow_red_counters_smoke.py` — PASS.
- Python compile głównych plików — PASS (istnieje wcześniejsze `SyntaxWarning` w `ui.py`, bez błędu kompilacji).
- `StatsScreen.tsx` i `AwardsScreen.tsx` — TypeScript syntax/transpile parser PASS przez globalny TypeScript.
- Pełny `npm run check` nie jest oznaczony PASS, bo paczka robocza nie zawiera `node_modules`; finalny one-click build ma nadal wykonać pełny check i Expo Doctor.

## Build
- FIFA NIGHT FLEX: **1.1.3**
- checkpoint: **R27**
- Android `versionCode`: **15** (bez bumpa w tej gałęzi, ponieważ V15 nie został potwierdzony jako wcześniej zainstalowany/dystrybuowany)
