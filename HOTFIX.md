# FIFA Night Flex v1.6.7 — hotfix spójności plików

Podmień wszystkie pliki z tej paczki:
- app.py
- ui.py
- database.py
- logic.py
- export_utils.py
- requirements.txt

Hotfix naprawia ImportError związany z `render_double_wb_pairing_draw`, który pojawia się, gdy `app.py` pochodzi z v1.6.6/1.6.7, a `ui.py` pozostał ze starszej wersji.
