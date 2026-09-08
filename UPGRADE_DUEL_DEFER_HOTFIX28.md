# Hotfix 28 — 1 vs 1 zawsze oficjalny + minimalne przesunięcie meczu

- Każdy mecz **1 vs 1** jest oficjalny, niezależnie od stawki.
- 1 vs 1 można utworzyć i prowadzić bez przejmowania sterowania.
- Usunięto tryb testowy z formularza 1 vs 1.
- Warstwa bazy również wymusza `is_test = 0` dla nowych 1 vs 1, więc starszy klient/API nie utworzy przypadkiem testowego duelu.
- Aktywne testowe 1 vs 1 utworzone w starszym hotfixie jest przy otwarciu normalizowane do oficjalnego. Historyczne stare testy nie są masowo przepisywane.
- `🕒 PRZESUŃ MECZ NA PÓŹNIEJ` przesuwa aktualny mecz dokładnie o **jeden następny grywalny mecz**, zamiast za wszystkie spotkania gotowe w tej chwili.
- Dzięki temu algorytm nadal ustala kolejność, a ręczne przesunięcie jest tylko minimalną awaryjną korektą.
