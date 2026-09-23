from pathlib import Path
ui=(Path(__file__).resolve().parents[1]/'ui.py').read_text(encoding='utf-8')
for token in [
    "goal_progress", "before-after ${phase==='winner_animation'?'anim':''}",
    "equation ${phase==='winner_animation'?'anim':''}", "late-clock",
    "rivalry_vs", "match_vs", "hero-metric ${phase==='winner_animation'?'anim':''}",
    "setInterval(poll,500)",
    "READY_ENDPOINT",
    "ackTvReady",
]:
    assert token in ui, token
print('GALA TV FX SOURCE SMOKE PASS')
