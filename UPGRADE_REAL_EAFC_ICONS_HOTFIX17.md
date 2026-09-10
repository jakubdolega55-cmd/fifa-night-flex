# FIFA Night — Hotfix 17: real EA FC event icons

Zmiana dotyczy wyłącznie rozpoznawania wydarzeń ze screenów EA FC w `mobile_api.py`.

## Potwierdzone reguły ikon

- zwykła biała piłka → `normal_goal`
- ikona bramki/siatki z ptaszkiem na dole → `penalty_goal`
- ikona bramki/siatki z X na dole → `penalty_miss`
- czerwona ikona piłki → `own_goal`
- żółty prostokąt → `yellow_card`
- czerwony prostokąt → `red_card`
- zielona/czerwona strzałka → `substitution`
- medyczna ikona kontuzji (np. plaster/opatrunek z plusem albo karetka/medyczny symbol z plusem) → `injury`; oba poziomy urazu są dla FIFA Night równoważne

## Samobój — kluczowa reguła

EA FC pokazuje samobój po stronie drużyny/piłkarza, który go popełnił. Gol jest jednak zaliczany przeciwnikowi.

Dlatego:

- `side` = strona piłkarza popełniającego samobój,
- `own_goal_by` = nazwisko tego piłkarza,
- `player = null`,
- `credited_side` = przeciwna strona,
- samobój nie trafia do klasyfikacji strzelców.

Reguła technicznego samobója w Grand Final Double Elimination pozostaje po stronie backendu i nie jest zgadywana przez model.

## Niewykorzystany karny

`penalty_miss` jest zapisywany jako zdarzenie po stronie wykonawcy, ale nie zwiększa wyniku ani liczby goli zawodnika. Nadal może zwiększać późniejszy licznik "otrzymanych karnych" gracza FIFA Night.

## Wdrożenie

Podmień tylko `mobile_api.py`, zrób commit i poczekaj na deploy Rendera. Nie trzeba zmieniać kluczy API, bazy ani Streamlita.
