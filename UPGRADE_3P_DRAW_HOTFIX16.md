# Hotfix 16 — losowanie turnieju 3-osobowego

Naprawia `ValueError` w `render_structure_draw()` dla formatu `league3_final`.

Przyczyna: `_draw_layout()` nie obsługiwał turnieju 3-osobowego i zwracał puste `groups`, po czym `max(...)` w rendererze próbował policzyć maksimum z pustej sekwencji.

Zmiany:
- dodano układ losowania dla `league3_final` (sloty A/B/C),
- dodano zabezpieczenie w `render_structure_draw()`, aby nie wywalać całej aplikacji, jeśli kiedyś pojawi się nieobsługiwany format.

Do wdrożenia: podmień tylko `ui.py` na branchu `main`.
