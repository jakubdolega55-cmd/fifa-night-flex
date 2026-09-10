# Hotfix 18 — jubileusze LIVE/TV + dokładny jubileuszowy gol

## Co zmienia

- TV i ekran prowadzenia meczu pokazują bliskie globalne jubileusze:
  - jeśli bieżący mecz będzie 50./100./200... oficjalnym meczem FIFA Night,
  - jeśli następny mecz po bieżącym będzie takim jubileuszem,
  - jeśli do 50./100./200... gola zostało maksymalnie 5 bramek,
  - jeśli aktualny turniej jest jubileuszowym 10./25./50./100. FIFA Night.
- Liczniki LIVE uwzględniają już rozegrane mecze z aktywnego oficjalnego turnieju i ignorują turnieje testowe.
- Techniczny +1 w finale Double Elimination nie zwiększa globalnego licznika prawdziwych goli.
- Dla nowych meczów zapisanych ze szczegółowym `match_events` aplikacja potrafi automatycznie ustalić dokładny jubileuszowy gol, jego minutę, strzelca oraz gracza FIFA Night.
- Jeśli jubileuszowym golem jest samobój, historia zapisuje go jako samobój i nie tworzy fikcyjnego strzelca.
- Stare mecze bez kolejności wydarzeń nadal korzystają z dotychczasowego ręcznego wskazania autora jubileuszowego gola.

## Pliki do podmiany

- `app.py`
- `database.py`
