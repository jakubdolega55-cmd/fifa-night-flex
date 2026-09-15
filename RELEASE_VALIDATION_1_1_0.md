# FIFA Night Flex 1.1.0 — validation checklist

Release powinien zostać uznany za gotowy do wdrożenia po:

- [ ] `python -m py_compile app.py database.py logic.py mobile_api.py export_utils.py scorer_seeds.py ui.py`
- [ ] `python tests/mobile_api_smoke.py`
- [ ] `python tests/big_patch_smoke.py`
- [ ] `python tests/swiss_smoke.py`
- [ ] `python tests/de9_de10_smoke.py`
- [ ] `python tests/smart_scheduler_smoke.py`
- [ ] `python tests/versioning_alias_smoke.py`
- [ ] `python tests/visible_draw_policy_smoke.py`
- [ ] `python tests/de456_draw_smoke.py`
- [ ] `cd mobile && npm install`
- [ ] `npm run check`
- [ ] `npx expo-doctor`
- [ ] `npm run build:web`

W bieżącym środowisku finalnego składania release testy Python są wykonywane ponownie. Walidacja npm/expo wymaga kompletnego `node_modules` i powinna być wykonana na środowisku build/deploy przed publikacją APK/PWA.

## Wynik finalnej regresji w środowisku release

- Python compile: **PASS**
- `mobile_api_smoke.py`: **51/51 PASS**
- `big_patch_smoke.py`: **8/8 PASS**
- `swiss_smoke.py`: **PASS**
- `de9_de10_smoke.py`: **PASS**
- `smart_scheduler_smoke.py`: **PASS**
- `versioning_alias_smoke.py`: **PASS**
- `visible_draw_policy_smoke.py`: **PASS**
- `de456_draw_smoke.py`: **PASS**

Pełny `npm install / npm run check / expo-doctor / build:web` pozostaje krokiem deploymentowym, ponieważ bieżące środowisko nie ma kompletnego `mobile/node_modules`.
