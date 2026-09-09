# FIFA Night Flex v1.8.0 — Hotfix 11: profile graczy z eventami

## Co dodano

W zakładce **Statystyki → Gracze** profil gracza pokazuje teraz nową sekcję **Dyscyplina, karne i minuty** opartą wyłącznie na nowych meczach zapisanych ze szczegółowym przebiegiem (`match_events`).

Liczone są:
- żółte kartki,
- czerwone kartki,
- karne otrzymane przez drużynę gracza FIFA Night (trafione + niewykorzystane),
- gole z karnych,
- niewykorzystane karne,
- samobóje popełnione przez drużynę gracza (bez technicznego samobója DE),
- najszybszy gol,
- najpóźniejszy gol,
- gole w doliczonym czasie 90+,
- gole w dogrywce.

## Zgodność ze starymi turniejami

Stare mecze bez `match_events` nadal działają bez zmian. Nie są traktowane jako mecze z zerem kartek czy zerem karnych. Profil pokazuje liczbę oficjalnych meczów, dla których rzeczywiście mamy szczegółowe dane.

## Ważne reguły

- gole z karnych normalnie liczą się piłkarzowi,
- niewykorzystany karny zwiększa `Karne otrzymane`, ale nie gole,
- seria karnych po meczu nie trafia do tych liczników,
- samobój techniczny w finale Double Elimination nie jest liczony jako samobój drużyny,
- rekordy minutowe obejmują gole zwykłe i gole z karnych, nie samobóje.

## Pliki

Podmień:
- `app.py`
- `database.py`
