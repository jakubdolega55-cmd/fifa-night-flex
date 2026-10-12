# R14 — remove stale 3-player draw-profile limit

Hotfix only. The deployed Streamlit UI was already R13, but `database.py` was still from R12 and retained the validation:
`Korektę profilu można ustawić maksymalnie dla 3 graczy.`

Changes:
- `database.py`: no maximum number of player profile corrections.
- Existing eligibility rule remains: a player must have official tournament history.
- Range remains 0–90% per player.
- No PWA/APK UI changes.

Deployment: replace `database.py` with this version and redeploy/restart the backend/Streamlit service.
