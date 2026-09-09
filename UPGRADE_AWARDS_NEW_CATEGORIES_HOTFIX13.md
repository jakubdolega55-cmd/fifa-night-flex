# Hotfix 13 — nowe Awards + przeniesienie 1v1/Wild Card do Rankingów

## Zmiany

- `Król 1 vs 1` został przeniesiony z oficjalnych Awards do sekcji `Rankingi`.
- `Król Wild Cardów` został przeniesiony z oficjalnych Awards do sekcji `Rankingi`.
- Dodano nowe oficjalne Awards oparte na szczegółowych wydarzeniach EA FC:
  - `🪓 Najostrzejszy Gracz` — żółta = 1 pkt, czerwona = 3 pkt.
  - `⏰ Król Końcówek` — gole od 85. minuty; przy remisie liczą się gole 90+ i najpóźniejszy gol.
  - `🔄 Comeback King` — wygrane po odrobieniu straty; 1 gol straty = 1 pkt, 2 = 4 pkt, 3 = 9 pkt itd.
  - `😇 Fair Play` — najmniej punktów dyscyplinarnych na mecz; minimum 3 mecze ze szczegółowym przebiegiem.
- Comeback King jest liczony wyłącznie dla meczów, w których szczegółowa lista zdarzeń zawiera pełny komplet goli zgodny z wynikiem.
- Stare mecze bez `match_events` nie są traktowane jako mecze bez kartek lub bez późnych goli.

## Pliki do podmiany

- `app.py`
- `database.py`
