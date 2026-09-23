# FIFA Night 1.1.3 — Gala / Summary / FC27 Test Candidate

## Zakres
- Gala Awards: backend, zapis stanu, Streamlit TV, PWA controller, timingi, efekty, replay/reset, gating.
- Testowy reset wszystkich laureatów.
- Summary backend i przygotowana warstwa Awards.
- Rywalizacja Roku przeniesiona do etapu 3 wyboru laureatów.
- Największy Progres jako pełnoprawny Award.
- FC27: Real normalnie na kole, Manchester City do Wild Cardów.
- FC27: opcjonalny tryb reprezentacji; FC26 pozostaje club-only.
- FC27 national pool i France ban.
- Handicap mocnych drużyn: PSG+Real w klubach, Hiszpania+Brazylia w reprezentacjach.

## Znany stan testów
- Backend/regresja Python: PASS.
- Mobile API: 51/51 PASS.
- Wheel shrink po zmianie puli FC27: PASS po aktualizacji starego oczekiwania testu.
- npm/Expo build nie został wykonany lokalnie w tym checkpointcie.
- `package-lock.json` nie jest dołączony; próba wygenerowania locka nie została ukończona w bezpiecznym limicie czasu. Render nadal używa `npm install`.
