# Gala TV handshake fix — 2026-09-23

Problem: START/NEXT/REPLAY started the category timer before the TV had actually received/rendered the new category. Network/render delay could consume most/all of the opening quote.

Fix:
- START/NEXT/REPLAY arm the category with no running timer.
- TV renders the intro immediately as `intro_pending`.
- TV calls public idempotent POST `/api/v1/gala/{year}/tv-ready?current_index=...`.
- Backend starts the category clock only after this acknowledgement.
- Stale ACK for another category index is ignored.
- Intro extended from 6s to 9s.
- Nominees shortened from 15s to 11s.
- Nominees still reveal every 2.5s, leaving ~6s with all 3 visible.
- TV polling changed 650ms -> 500ms.

Targeted tests PASS:
- Python compile
- gala_tv_handshake_smoke
- gala_backend_smoke
- gala_sync_snapshot_smoke
- gala_tv_fx_source_smoke
- gala_closeout_smoke
- gala_mobile_controller_smoke

Full mobile_api regression was not rerun to completion in this checkpoint due time limit; no tournament logic was changed in this fix.
