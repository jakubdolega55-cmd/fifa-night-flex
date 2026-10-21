# FIFA NIGHT FLEX — handoff R32 — 2026-10-21

Baza: R31. Android versionCode pozostaje 15.

R32 jest małym hotfixem panelu Awards/Streamlit:
1. naprawa `NameError` przez dodanie `award_owner_name()`;
2. reset wszystkich laureatów + Gali dostępny dla odblokowanego organizatora niezależnie od flagi testowej, z potwierdzeniem `RESET`;
3. sekcja zamknięcia sezonu zawsze widoczna; przed pełnym zakończeniem Gali przycisk jest disabled i pokazuje status, po `finished` działa dotychczasowy flow `ZAKOŃCZ SEZON`.

Nie zmieniono scoringu Awards, kandydatów, kolejności Gali, odznak, klasyfikacji, rekordów ani Android versionCode.
