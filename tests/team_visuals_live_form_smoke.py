from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'app.py').read_text(encoding='utf-8')
ui=(ROOT/'ui.py').read_text(encoding='utf-8')
mobile=(ROOT/'mobile/src/FifaScreen.tsx').read_text(encoding='utf-8')
visual=(ROOT/'mobile/src/teamVisuals.tsx').read_text(encoding='utf-8')
pyvisual=(ROOT/'team_visuals.py').read_text(encoding='utf-8')
appjson=json.loads((ROOT/'mobile/app.json').read_text(encoding='utf-8'))
manifest=json.loads((ROOT/'team_crest_sources.json').read_text(encoding='utf-8'))
package=json.loads((ROOT/'mobile/package.json').read_text(encoding='utf-8'))
assert 'showTeamVisuals' in mobile
assert '<MatchCard m={t.current_match} current showTeamVisuals/>' in mobile
assert '<MatchCard m={t.next_match} showTeamVisuals/>' in mobile
assert '● FORMA LIVE' in mobile and 'formWin' in mobile and 'formLoss' in mobile and 'formDraw' in mobile
assert "v==='D'||v==='R'?'R'" in mobile and "v==='L'||v==='P'?'P'" in mobile
assert 'TeamVisual team={result}' in mobile
# Local flags
assert "spain:require('../assets/teams/flags/spain.png')" in visual
assert "england:require('../assets/teams/flags/england.png')" in visual
assert "'hiszpania':FLAG_ASSETS.spain" in visual and "'brazylia':FLAG_ASSETS.brazil" in visual
assert 'team_flag_data_uri' in pyvisual and "'assets' / 'teams'" in pyvisual
for slug in ['spain','england','brazil','germany','portugal','italy','argentina','netherlands','belgium','croatia','denmark','morocco','turkey','switzerland']:
    a=ROOT/'assets/teams/flags'/f'{slug}.png'
    m=ROOT/'mobile/assets/teams/flags'/f'{slug}.png'
    assert a.exists() and m.exists(), slug
    assert a.read_bytes().startswith(b'\x89PNG\r\n\x1a\n') and m.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'), slug
# Local club crests: runtime code has no remote URL; static requires/data URI only.
assert 'team_logo_data_uri' in pyvisual and "'clubs' / f'{slug}.png'" in pyvisual
assert 'CLUB_ASSETS' in visual and 'export const teamLogo=' in visual
assert "require('../assets/teams/clubs/real-madrid.png')" in visual
assert "require('../assets/teams/clubs/manchester-city.png')" in visual
assert "require('../assets/teams/clubs/bayer-leverkusen.png')" in visual
assert 'football-logos.cc' not in visual and 'footylogos.com' not in visual
assert 'football-logos.cc' not in pyvisual and 'footylogos.com' not in pyvisual
assert "'lombardia fc':'inter'" in visual and "'atlético de madrid':'atletico-madrid'" in visual
# Vendor step is wired before mobile starts/builds; source URLs live only in vendor tooling.
assert len(manifest)==16
assert (ROOT/'vendor_team_crests.py').exists()
assert (ROOT/'mobile/scripts/vendor-team-crests.mjs').exists()
assert package['scripts']['vendor:teams']=='node scripts/vendor-team-crests.mjs'
for script in ('start','android','build:apk','web','build:web'):
    assert 'vendor:teams' in package['scripts'][script], script
assert 'render_live_form' in app and 'team_visual_html(cur.get("home_team"),64)' in app
assert "<div class='crest'>{team_visual_html(display_result,72)}</div>" in ui
assert appjson['expo']['android']['versionCode']==14
print('team_visuals_live_form_smoke: PASS')

assert 'Array(Math.max(0,5-xs.length)).fill(null)' in mobile
assert "recent=[None]*max(0,5-len(recent))+recent" in app
