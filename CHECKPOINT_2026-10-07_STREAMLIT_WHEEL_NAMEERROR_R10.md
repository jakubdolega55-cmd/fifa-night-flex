# FIFA NIGHT FLEX — R10 Streamlit wheel NameError hotfix

Date: 2026-10-07
Base: R9 Awards Fairness / FC27 small-player wheel

## Problem
Streamlit crashed when rendering the team wheel (observed on FC27 4-player tournament) in `ui.py -> render_wheel()` with a NameError.

## Root cause
Two CSS blocks inside a Python f-string used single braces instead of escaped double braces:
- `.crest{...}`
- `.team{...}`

Python therefore interpreted the contents as f-string expressions at runtime.

## Fix
Changed them to escaped f-string CSS braces:
- `.crest{{...}}`
- `.team{{...}}`

No tournament logic, draw weights, pools, Awards, mobile API, or APK code was changed.

## Verification
- `python -m py_compile ui.py` — PASS (existing unrelated invalid escape SyntaxWarning remains around line 391)
- runtime `render_wheel()` smoke with mocked Streamlit renderer — PASS for shrinking FC27 wheel pools and Wild Card result

## APK
NO. Streamlit/UI server-side hotfix only.
