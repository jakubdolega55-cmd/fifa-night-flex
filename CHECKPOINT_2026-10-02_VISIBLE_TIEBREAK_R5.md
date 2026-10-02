# FIFA NIGHT FLEX 1.1.3 V14 — R5 Visible Tiebreak Draw

## Cel
Usunięcie ukrytych/technicznych losowań z sytuacji, w których absolutny remis po wszystkich kryteriach sportowych realnie decyduje o awansie, rozstawieniu albo podium.

## Nowa zasada
Jeżeli wszystkie kryteria sportowe są identyczne i remis wpływa na dalszy turniej:
1. turniej zatrzymuje rozwiązywanie odpowiedniego slotu/drabinki,
2. Streamlit/TV pokazuje `LOSOWANIE ROZSTRZYGAJĄCE`,
3. controller/telefon pokazuje kandydatów i przycisk `LOSUJ ROZSTRZYGNIĘCIE`,
4. dopiero kliknięcie uruchamia reveal kolejności,
5. `ZATWIERDŹ WYNIK LOSOWANIA` zapisuje kolejność na stałe,
6. dopiero wtedy odblokowuje się dalsza faza.

Losowanie nie jest uruchamiane dla remisów na pozycjach, które nie mają znaczenia dla dalszego turnieju.

## Zakres
- ligi 3/4/5 — pozycje używane do finału,
- grupy 6/7/8/10 — miejsca używane do SF/QF/barażu,
- 9 osób / 3 grupy:
  - remisy wewnątrz grup na istotnych pozycjach,
  - `groups9_final4`: remis o najlepsze 2. miejsce,
  - `groups9_top8`: remis o miejsca z 3. pozycji,
  - `groups9_barrage_final3`: absolutny remis w Final Three,
- Swiss8/Swiss10 — absolutny remis wpływający na TOP4/rozstawienie TOP4.

## Kryteria pozostają bez zmian
- grupa/liga: pkt -> bilans -> gole -> H2H/mini-tabela -> Fair Play -> jawne losowanie,
- cross-group 9 osób: pkt -> bilans -> gole -> Fair Play -> jawne losowanie,
- Swiss: pkt -> Buchholz -> bilans -> gole -> H2H (gdy ma zastosowanie) -> jawne losowanie,
- Final Three: pkt -> bilans -> gole -> H2H (gdy rozstrzyga 2 osoby) -> jawne losowanie.

Specjalna zasada ostatniego meczu grupowego dla dokładnie dwóch idealnie równych graczy pozostaje bez zmian: jeśli ten mecz bezpośrednio decyduje o awansie, jest dogrywka, a następnie ewentualnie karne.

## Undo
`Cofnij wynik` czyści zapisane rozstrzygnięcie powiązane z cofniętą fazą (grupa/liga, Swiss lub Final Three) i usuwa stare losowanie rozstrzygające. Po ponownym rozegraniu meczu, jeśli absolutny remis nadal istnieje, tworzony jest nowy jawny draw.

## Testy
PASS:
- visible tiebreak: liga,
- groups9_final4: grupy + najlepsze 2. miejsce,
- Swiss TOP4,
- Final Three 3-way exact tie + zakończenie turnieju po ACK,
- undo/replay losowania rozstrzygającego,
- group tiebreak / last-match ET+pens,
- visible draw policy,
- Swiss 3-1-0 + Swiss8/10,
- DE manual draw,
- KO8,
- mobile API smoke 52/52,
- Python compile: logic.py, database.py, mobile_api.py, app.py, ui.py.

## Pliki produkcyjne zmienione względem R4
- logic.py
- database.py
- mobile_api.py
- app.py
- ui.py
- mobile/src/FifaScreen.tsx

## APK
TAK — controller/mobile UI obsługuje nowy typ jawnego losowania rozstrzygającego.
