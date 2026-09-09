# Hotfix 12 — Awards / Rankingi

Zmiany:

- sekcja FIFA Night Awards ma teraz 3 podsekcje: `Awards`, `Rankingi`, `Kamienie milowe`,
- `Najbardziej Regularny` i `Największy Progres` przeniesione z Awards do Rankingów,
- usunięto bieżący Award `Król Karnych` oparty o serie karnych,
- `Drużyna Roku` i `Najgorsza Drużyna Roku` połączone w jedną kategorię `Drużyny Roku`; oficjalny wybór dotyczy najlepszej drużyny, a najgorsza jest pokazywana jako drugi biegun rankingu,
- dodano rankingi bez nagrody:
  - Największy symulant — wszystkie karne przyznane graczowi FIFA Night (trafione + niewykorzystane),
  - Penaldo — gole z karnych w trakcie meczu,
  - Najwięcej pierwszych goli,
  - Samobóje,
  - Niewykorzystane karne,
  - istniejące Król Minimalistów i Pechowiec Roku pozostają rankingami,
- rankingi oparte na nowych wydarzeniach liczą tylko mecze posiadające szczegółowy `match_events`; seria karnych po meczu nie jest liczona,
- techniczny samobój z finału Double Elimination nie jest liczony do rankingu samobójów ani pierwszych goli,
- nominacje i panel wyboru laureatów nie uwzględniają kategorii przeniesionych do Rankingów.

Pliki do podmiany:

- `app.py`
- `database.py`

Rekordy nie są jeszcze zmieniane w tym hotfixie. Obecna zakładka Rekordy już zawiera m.in. największe zwycięstwo i najbardziej bramkowy mecz; rekordy oparte na minutach/przebiegu meczu będą kolejnym osobnym krokiem.
