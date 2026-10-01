from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
expected={
'real-madrid','paris-saint-germain','bayern-munchen','barcelona','arsenal','manchester-city','liverpool','atletico-madrid','inter','manchester-united','borussia-dortmund','tottenham','milan','bayer-leverkusen'
}
PNG_MAGIC=b"\x89PNG\r\n\x1a\n"
for base in [ROOT/'assets/teams/clubs', ROOT/'mobile/assets/teams/clubs']:
    found={x.stem for x in base.glob('*.png')}
    assert expected <= found, (base, expected-found)
    for slug in expected:
        raw=(base/f'{slug}.png').read_bytes()
        assert raw.startswith(PNG_MAGIC), slug
visual=(ROOT/'mobile/src/teamVisuals.tsx').read_text(encoding='utf-8')
pyvisual=(ROOT/'team_visuals.py').read_text(encoding='utf-8')
ui=(ROOT/'ui.py').read_text(encoding='utf-8')
pkg=json.loads((ROOT/'mobile/package.json').read_text(encoding='utf-8'))
for slug in expected:
    assert f"clubs/{slug}.png" in visual
assert "'chelsea':require" not in visual and "'napoli':require" not in visual
assert "'chelsea': 'chelsea'" not in pyvisual and "'napoli': 'napoli'" not in pyvisual
assert 'football-logos.cc' not in visual and 'football-logos.cc' not in pyvisual and 'football-logos.cc/logos/' not in ui
assert pkg['scripts']['verify:teams']=='node scripts/verify-team-assets.mjs'
for key in ['start','android','build:apk','web','build:web']:
    assert 'verify:teams' in pkg['scripts'][key], (key,pkg['scripts'][key])
    assert 'vendor:teams' not in pkg['scripts'][key], (key,pkg['scripts'][key])
print('local_team_assets_packed_smoke: PASS')
