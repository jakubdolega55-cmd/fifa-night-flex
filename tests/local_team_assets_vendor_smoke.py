from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'team_crest_sources.json').read_text(encoding='utf-8'))
py=(ROOT/'vendor_team_crests.py').read_text(encoding='utf-8')
js=(ROOT/'mobile/scripts/vendor-team-crests.mjs').read_text(encoding='utf-8')
visual=(ROOT/'mobile/src/teamVisuals.tsx').read_text(encoding='utf-8')
pyvisual=(ROOT/'team_visuals.py').read_text(encoding='utf-8')
expected={
'real-madrid','paris-saint-germain','bayern-munchen','barcelona','arsenal','manchester-city','liverpool','atletico-madrid','inter','manchester-united','borussia-dortmund','napoli','chelsea','tottenham','milan','bayer-leverkusen'
}
assert set(manifest)==expected
for slug in expected:
    assert f"clubs/{slug}.png" in visual
assert "assets' / 'teams'" in pyvisual and "'clubs'" in pyvisual
assert 'football-logos.cc' not in visual and 'football-logos.cc' not in pyvisual
assert 'footylogos.com' not in visual and 'footylogos.com' not in pyvisual
assert 'PNG_MAGIC' in py and 'PNG' in js
assert 'football-logos.cc' in py and 'footylogos.com' in py
assert 'football-logos.cc' in js and 'footylogos.com' in js
print('local_team_assets_vendor_smoke: PASS')
