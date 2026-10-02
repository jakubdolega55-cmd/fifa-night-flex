# CHECKPOINT 2026-10-02 — DRAW REVEAL + TV WIDE R3

Base: FIFA NIGHT FLEX 1.1.3 / V14 / TEST FIXES R2.

## Changes
- Synced Streamlit team wheel: winning crest and winning team name stay hidden while the wheel spins.
- Both are revealed together just after the 10.0 s wheel animation finishes (10.05 s reveal delay).
- Streamlit TV layout widened further for monitor/TV use: main content up to 1880 px / nearly full viewport.
- Synced draw TV panel no longer has a 1500 px internal max-width.
- Wheel area can use more horizontal space on large screens.

## Unchanged
- Tournament logic, scheduler, DB, API, Swiss, DE, NEXT logic, mobile/PWA are unchanged.
- APK rebuild is NOT required for this patch.

## Checks
- Python compile: PASS.
- Draw visual timing smoke: PASS.
