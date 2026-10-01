# CHECKPOINT 2026-10-01 — FC27 DRAW WEIGHT TUNING

Changes:
- Wild Card assignment weights: champion 1.70, runner-up 1.45, third 1.15, others 1.00.
- FC27 club strong-team handicap (PSG + Real Madrid): champion x0.40, runner-up x0.60.
- Exact previous-team repeat penalty remains x0.35.
- Live team rating strength adjustment remains unchanged.
- FC27 Real-ban mode: City stays neutral; only PSG receives the club strong-team handicap.
- FC27 national mode remains unchanged for Spain/Brazil: champion x0.50, runner-up x0.70.
- No APK rebuild required; this patch changes backend draw logic only.

Validation:
- Python compile PASS
- fc27_draw_weight_tuning_smoke.py PASS
- national_mode_fc27_smoke.py PASS
- fc27_real_ban_switch_smoke.py PASS
- fc27_real_ban_mobile_settings_smoke.py PASS
- club_pool_and_test_reset_smoke.py PASS
- mobile_api_smoke.py 51/51 PASS
- smart_scheduler_smoke.py PASS
- de9_de10_smoke.py PASS
- group_tiebreak_smoke.py PASS
- swiss_smoke.py PASS
- forfeit_smoke.py PASS
- next_match_projection_smoke.py PASS
