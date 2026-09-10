# Hotfix 21 — TV: broadcastowe „Stawki meczu”

Podmień tylko `app.py`.

## Zmiany
- usunięto zwykły box `Stawka meczu: ...` z `st.info`,
- zamiast niego TV pokazuje średniej wielkości hero-card dopasowany do etapu,
- bez dodatkowego paska statusu,
- różne tło, obramowanie, ikona, nagłówek i opis zależnie od stawki,
- delikatny glow/puls zamiast agresywnych animacji.

## Warianty
- Grand Final / finał: złoty — `WALKA O TYTUŁ` / `MISTRZOSTWO NA STAWCE`,
- Losers / eliminacja: czerwony — `MECZ O WSZYSTKO`,
- Winners: zielony — `UTRZYMAJ SIĘ NA GÓRZE`,
- półfinał: fioletowy — `GRA O FINAŁ`,
- QF/baraż: pomarańczowy — `WYGRYWAJ ALBO ODPADASZ`,
- grupa/liga: niebieski — `WALKA O PUNKTY`,
- 1 vs 1: niebieski — `TYLKO JEDEN ZWYCIĘZCA`.

Nie zmienia logiki turnieju ani bazy danych.
