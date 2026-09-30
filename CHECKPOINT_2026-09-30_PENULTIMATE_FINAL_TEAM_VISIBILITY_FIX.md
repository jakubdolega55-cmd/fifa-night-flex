# Checkpoint 2026-09-30 — penultimate/final team visibility fix

## Problem
In Streamlit team wheel setup, after the penultimate spin the controller immediately consumed the final deterministic slot and reran into structure draw. Because that rerun happened in the same interaction, the browser could lose the just-rendered penultimate wheel, making it look like both the 8th and 9th assignments were skipped.

## Fix
- The penultimate wheel is never followed by an immediate backend rerun.
- When exactly one slot remains, Streamlit shows `POKAŻ OSTATNI PRZYDZIAŁ` instead of spinning again.
- The final normal team is auto-assigned without a wheel and shown on a dedicated `OSTATNI PRZYDZIAŁ • BEZ LOSOWANIA` card.
- Structure draw starts only after the user sees that final assignment and presses the continue button.
- Final Wild Card still skips the wheel and opens the Wild Card picker; after confirmation its chosen team is also shown before structure draw.

## Scope
Streamlit only (`app.py`). Backend assignment semantics are unchanged. No APK rebuild required.
