# CHECKPOINT 2026-10-20 — R25 Advanced Stats + Klasyfikacje Summary

## Zakres
R25 porządkuje sekcję `Klasyfikacje` i wykorzystuje wiarygodne dane EA FC Summary bez dokładania nowych kategorii do Gali/Awards.

## Advanced Stats w profilu gracza
Dodane w Streamlit i PWA/APK:
- xG / mecz,
- xGA / mecz,
- xGD / mecz,
- strzały / mecz,
- strzały rywala / mecz,
- średnie posiadanie,
- faule / mecz.

Profil celowo NIE pokazuje liczby meczów z Summary. Starsze mecze bez Summary są ignorowane, a nie traktowane jako zera. Advanced Stats są liczone ze wszystkich oficjalnych meczów gracza (tak jak profil all-time), jeśli Summary ma poprawne mapowanie HOME/AWAY.

## Klasyfikacje — nowy docelowy zestaw
1. ⚔️ Król 1 vs 1
2. 🎲 Król Wild Cardów
3. 🎯 Najbardziej Regularny
4. 🪓 Najostrzejszy Gracz
5. 🥇 Najwięcej pierwszych goli
6. 🎢 Król Nerwówek
7. 🎯 Kliniczny
8. 🗑️ Marnotrawca
9. 👑 Król Posiadania
10. 📈 Dominator
11. 🦹 Złodziej Meczów

Usunięte z głównej sekcji Klasyfikacji (dane nadal istnieją w Events/statystykach i mogą później zostać wykorzystane jako ciekawostki/odznaki):
- Największy symulant,
- Penaldo,
- Samobóje,
- Niewykorzystane karne,
- Król Minimalistów,
- Pechowiec Sezonu.

## Zasady nowych klasyfikacji
### 🎢 Król Nerwówek
- mecz na styku = różnica dokładnie 1 gola LUB rozstrzygnięcie po karnych,
- ranking po odsetku takich meczów,
- przy remisie decyduje liczba takich spotkań,
- minimum 5 oficjalnych meczów turniejowych.

### 🎯 Kliniczny
- `(gole z meczów Summary - xG) / mecz`,
- gole i xG pochodzą dokładnie z tego samego zestawu spotkań,
- kandydat tylko przy dodatnim overperformance,
- minimum 5 wiarygodnych meczów Summary.

### 🗑️ Marnotrawca
- `(xG - gole z meczów Summary) / mecz`,
- kandydat tylko przy dodatnim underperformance,
- minimum 5 wiarygodnych meczów Summary.

### 👑 Król Posiadania
- średnie possession %,
- minimum 5 wiarygodnych meczów Summary.

### 📈 Dominator
- `xGD/mecz = xG własne - xG rywala`,
- minimum 5 wiarygodnych meczów Summary.

### 🦹 Złodziej Meczów
Wygrana mimo niższego xG:
- deficit xG 0.25–0.49 = 1 pkt,
- 0.50–0.99 = 2 pkt,
- >= 1.00 = 3 pkt,
- ranking po punktach kradzieży / mecz,
- minimum 5 wiarygodnych meczów Summary.

## Summary — zasada jakości
Do R25 używamy jako wiarygodne: xG, shots, possession, fouls. SOT nadal może być parsowany i zapisany, ale został usunięty z bonusów Summary dla Widowiskowego / Meczu Sezonu i nie jest podstawą nowych rankingów.

## Testy
PASS:
- `python -m py_compile database.py app.py mobile_api.py`
- `tests/summary_classifications_r25_smoke.py`
- `tests/awards_frequency_fairness_smoke.py`
- `tests/awards_logic_patch_smoke.py`
- `tests/mobile_awards_season_smoke.py`
- `tests/gala_counters_smoke.py`
- `tests/mobile_api_smoke.py` — 52/52 PASS
- parser TypeScript (`transpileModule`) dla `mobile/src/StatsScreen.tsx` i `mobile/src/AwardsScreen.tsx` — PASS

Nie oznaczono pełnego `npm run check` jako PASS, ponieważ paczka handoff nie zawiera `node_modules`. Finalny one-click build nadal ma wykonać instalację zależności + pełny check + Expo Doctor.

## Android
`versionCode` pozostaje 15. Użytkownik nie zgłosił, że finalny V15 został już zainstalowany/dystrybuowany.

## Następny krok
Najpierw obejrzeć R25 na realnych danych / w UI i ocenić, czy 11 klasyfikacji oraz karta Advanced Stats są czytelne. Dopiero potem przejść do osobnego etapu odznak/rekordów opartych na Summary — bez dokładania nowych kategorii Gali.
