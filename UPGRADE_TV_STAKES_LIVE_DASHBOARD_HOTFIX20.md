# Hotfix 20 — TV: stawka meczu + „FIFA Night na żywo”

Podmień w repozytorium tylko:

- `app.py`
- `database.py`

## 1. Stawka meczu na TV

Przy aktualnym spotkaniu TV pokazuje krótki komunikat zależny od etapu, m.in.:

- faza grupowa / liga — punkty do tabeli,
- ćwierćfinał / baraż — zwycięzca do półfinału, przegrany odpada,
- półfinał — zwycięzca do finału, przegrany odpada,
- finał — zwycięzca zostaje Mistrzem FIFA Night,
- Double Elimination Winners — przegrany spada do Losers,
- Double Elimination Losers — przegrany odpada,
- finały Winners / Losers — pokazują drogę do Wielkiego Finału,
- Wielki Finał DE — pokazuje stawkę mistrzowską i przypomina o starcie Winners Bracket od 1:0.

Nie ma skomplikowanych wyliczeń typu „potrzebuje X punktów”.

## 2. Czwarty ekran AUTO — „📊 FIFA Night na żywo”

Rotacja AUTO ma teraz 4 ekrany (po około 10 s każdy):

1. Teraz / Następny
2. Sytuacja turnieju
3. Wyniki i strzelcy
4. FIFA Night na żywo

Nowy ekran pokazuje statystyki tylko bieżącego turnieju:

- rozegrane mecze,
- gole,
- średnią goli na mecz,
- rzuty karne przyznane w trakcie meczu,
- żółte kartki,
- czerwone kartki,
- samobóje,
- gole w dogrywce,
- liczbę meczów ze szczegółowo zapisanymi wydarzeniami,
- najbardziej bramkostrzelny mecz bieżącego turnieju.

Kartki / karne / samobóje / gole w dogrywce korzystają wyłącznie z `match_events` — aplikacja nie zgaduje danych dla meczów zapisanych bez szczegółowego przebiegu.

Techniczny gol +1 w Wielkim Finale Double Elimination nie jest liczony jako prawdziwy gol ani w sumie goli, ani przy najbardziej bramkostrzelonym meczu.

## Test po deployu

1. Otwórz TV.
2. Sprawdź aktualny mecz — pod etapem powinna pojawić się „⚔️ Stawka meczu”.
3. Włącz AUTO.
4. Poczekaj do 4. ekranu „📊 FIFA Night na żywo”.
5. Sprawdź czy liczba meczów/goli odpowiada bieżącemu turniejowi.
