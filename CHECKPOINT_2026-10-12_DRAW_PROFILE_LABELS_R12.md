# CHECKPOINT 2026-10-12 — DRAW PROFILE LABELS R12

Base: R11.

## Change
Only user-facing naming for the FC27 per-player Real weighting control in Streamlit was neutralized.

Visible labels now use:
- Korekta profilu losowania
- Współczynnik korekcyjny
- Zapisz korektę profilu

No visible copy in this control mentions Real, handicap, reduction or probability.
Internal function/setting names remain unchanged to minimize regression risk.

## Logic
No draw weights or behavior changed from R11.

## Validation
- Python compile: PASS (existing ui.py invalid escape SyntaxWarning remains)
- targeted grep for old visible labels: PASS

APK: NO — Streamlit/backend copy only.
