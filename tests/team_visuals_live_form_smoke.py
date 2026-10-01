from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'app.py').read_text(encoding='utf-8')
ui=(ROOT/'ui.py').read_text(encoding='utf-8')
mobile=(ROOT/'mobile/src/FifaScreen.tsx').read_text(encoding='utf-8')
visual=(ROOT/'mobile/src/teamVisuals.tsx').read_text(encoding='utf-8')
pyvisual=(ROOT/'team_visuals.py').read_text(encoding='utf-8')
appjson=json.loads((ROOT/'mobile/app.json').read_text(encoding='utf-8'))
assert 'showTeamVisuals' in mobile
assert '<MatchCard m={t.current_match} current showTeamVisuals/>' in mobile
assert '<MatchCard m={t.next_match} showTeamVisuals/>' in mobile
assert '● LIVE FORM' in mobile and 'formWin' in mobile and 'formLoss' in mobile and 'formDraw' in mobile
assert "v==='D'||v==='R'?'R'" in mobile and "v==='L'||v==='P'?'P'" in mobile
assert 'TeamVisual team={result}' in mobile
assert "'hiszpania':'🇪🇸'" in visual and "'brazylia':'🇧🇷'" in visual
assert 'football-logos.cc/logos/' in visual and 'football-logos.cc/logos/' in pyvisual
assert 'render_live_form' in app and 'team_visual_html(cur.get("home_team"),64)' in app
assert "<div class='crest'>{team_visual_html(display_result,72)}</div>" in ui
assert appjson['expo']['android']['versionCode']==14
print('team_visuals_live_form_smoke: PASS')
