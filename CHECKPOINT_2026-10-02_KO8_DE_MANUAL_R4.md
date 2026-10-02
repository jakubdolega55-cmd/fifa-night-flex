# FIFA NIGHT FLEX 1.1.3 V14 — KO8 + DE MANUAL DRAW R4

Date: 2026-10-02

## New format: knockout8
- Additional format for exactly 8 players.
- Classic single elimination: 4 QF + 2 SF + Final = 7 matches.
- No third-place match.
- Third place is calculated between the two semifinal losers using:
  1. tournament goal difference,
  2. goals scored.
- If both are still equal, both receive 3rd place ex aequo; there is no 4th place.
- Bracket is drawn at tournament setup and then follows QF -> SF -> Final.
- KO8 final starts 0:0; DE Winners-Bracket final bonus rules do not apply.
- Added to backend, Streamlit, mobile/PWA, history/summary and export.

## DE draw manual trigger
- Dynamic DE bracket draws no longer reveal automatically when the draw screen appears.
- TV/Streamlit waits for the controller/phone.
- Controller shows the draw/reveal action.
- ACK before reveal is blocked.
- After reveal + ACK the bracket continues normally.
- Applies to the dynamic DE draw flow including DE7/8/9/10 where applicable.

## Preserved earlier V14 fixes
- Swiss R1-R3 draws: 3-1-0, no ET/pens in Swiss rounds.
- FC27 default for new tournaments.
- Dynamic NEXT/public M1-M2 projection fixes.
- DE BYE future-slot resolution.
- Streamlit wide TV layout and delayed crest/name reveal.
- AUTO after final team draw.

## Automated verification
PASS:
- Python compile: logic.py, database.py, mobile_api.py, app.py, export_utils.py
- tests/knockout8_smoke.py
- tests/de_manual_draw_trigger_smoke.py
- tests/de456_draw_smoke.py
- tests/de9_de10_smoke.py
- tests/mobile_api_smoke.py: 52 passed / 0 failed, including knockout8 full flow in 7 matches

## Mobile TypeScript note
The unpacked test environment does not contain the Expo/React node_modules / expo tsconfig required for a meaningful `npm run check`. No dependency install was attempted to avoid changing the project environment. Mobile format wiring was checked structurally and is covered through backend/API regression; final physical APK/PWA test remains required.

## Build
APK rebuild: YES, because knockout8 adds/changes mobile UI format handling.
Android versionCode can remain 14 if the first V14 APK has not yet been shipped/built as the release baseline.
