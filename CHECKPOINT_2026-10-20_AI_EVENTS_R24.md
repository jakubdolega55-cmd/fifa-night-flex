# CHECKPOINT 2026-10-20 — R24 — AI Events / scorer validation / shoot-out

## Zakres
Celowana poprawka parsera screenshotów EA FC bez ruszania Awards, losowań ani nowych odznak.

Naprawione obszary:
1. bezpośrednia czerwona vs druga żółta,
2. injury vs penalty miss,
3. błędny scorer przypisany do niewłaściwej drużyny,
4. długi mecz remisowy + seria karnych, np. 3:3 + 7:6.

## Najważniejszy znaleziony błąd
Po mapowaniu LEFT/RIGHT ekranu EA FC na HOME/AWAY FIFA Night funkcja `_resolve_scan_footballer_names()` nadal analizowała surowe `result.events`.
Surowe eventy nie mają `actor_team_name`, więc resolver nie mógł realnie sprawdzić nazwiska względem kadry przypisanej drużyny.

R24 przenosi resolution na `result.fifa_night.events`, czyli na eventy już zmapowane do konkretnego gracza i teamu.

## Direct red / second yellow
Prompt został wzmocniony:
- widoczna CZERWONA prostokątna kartka = `red_card`,
- nie wolno jej degradować do yellow tylko dlatego, że zawodnik wcześniej miał żółtą,
- dwa osobne żółte wiersze tego samego piłkarza pozostają dwoma `yellow_card`,
- backend nadal wyprowadza z nich jedno `second_yellow_red`, bez sztucznej dodatkowej czerwonej.

## Penalty miss / injury
Zachowano dotychczasową regułę ikon:
- goal/net/ball + X = `penalty_miss`,
- wyraźnie medyczny symbol = `injury`,
- niepewny symbol = `unknown` zamiast zgadywania.

## Scorer validation
Po mapowaniu teamu:
- aliasy `remembered/exact/auto` nadal rozwiązują się automatycznie,
- `ambiguous` albo `unresolved` scorer przy golu ustawia `goal_validation.status = needs_review`,
- taki odczyt nie jest już uznawany za kompletny tylko dlatego, że suma goli zgadza się z wynikiem,
- Mobile i Streamlit pokazują korektę/wybór,
- unresolved nazwisko może być świadomie potwierdzone ręcznie, bo lokalna lista kadry może być niepełna,
- API przy zapisie również blokuje niepotwierdzone `ambiguous/unresolved` nazwisko z AI.

## 3:3 + karne 7:6
Prompt dostał jawny przykład:
- zwykły wynik = 3:3,
- seria = 7:6,
- nigdy 10:9,
- próby shoot-out nie trafiają do normalnych eventów/scorer stats.

Dodatkowo backend ma ochronę: jeśli istnieje jawny nieremisowy wynik shoot-out i AI mimo to zwróci wielowierszową sekwencję karnych `120'` z obu stron, ta sekwencja jest odfiltrowywana przed walidacją goli. Pojedynczy karny w 120' pozostaje, bo może być prawdziwym karnym w dogrywce.

## Zmienione pliki
- `mobile_api.py`
- `app.py`
- `mobile/src/FifaScreen.tsx`
- `tests/event_parser_r24_smoke.py` — nowy test

## Testy
PASS:
- Python compile: `mobile_api.py`, `app.py`, `database.py`, `logic.py`
- `tests/event_parser_r24_smoke.py`
  - direct red,
  - second yellow,
  - injury,
  - penalty miss,
  - wrong-team scorer review,
  - 3:3 + pens 7:6,
  - mobile confirmation UI
- `tests/penalty_miss_icon_prompt_smoke.py`
- `tests/second_yellow_red_counters_smoke.py`
- `tests/manual_event_scorer_draw_smoke.py`
- `tests/mobile_api_smoke.py` — 52/52 PASS
- zmieniony `FifaScreen.tsx` — parser TypeScript: brak błędów składni

NOT FULL PASS:
- pełny `npm install && npm run check` — `npm install` ponownie przekroczył limit środowiska; paczka nie zawiera `node_modules`, więc pełnego TypeScript check nie oznaczono jako PASS.

## Wersjonowanie
- app version: `1.1.3`
- Android `versionCode`: `15`
- bez bumpa, ponieważ po R23 użytkownik nie potwierdził jeszcze instalacji/dystrybucji V15.

## Fizyczny retest
Na prawdziwych screenshotach sprawdzić:
1. direct red,
2. dwie żółte tego samego piłkarza,
3. injury,
4. penalty miss,
5. scorer spoza kadry / skrót nazwiska,
6. mecz remisowy z długą serią karnych,
7. zapis wyniku po ręcznej korekcie/potwierdzeniu scorera.

## Następny task
R25 — nowe odznaki / klasyfikacje na podstawie Summary, ale dopiero po ewentualnych poprawkach z fizycznego retestu R24.
