from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
logic=(ROOT/'logic.py').read_text(encoding='utf-8')
api=(ROOT/'mobile_api.py').read_text(encoding='utf-8')
app=(ROOT/'mobile/App.tsx').read_text(encoding='utf-8')
client=(ROOT/'mobile/src/api.ts').read_text(encoding='utf-8')
appjson=(ROOT/'mobile/app.json').read_text(encoding='utf-8')
assert 'Manchester City replaces Real' not in logic
assert 'does NOT inherit Real' in logic
assert '/api/v1/settings/fc27-real-ban' in api
assert 'setFc27RealBan' in client
assert 'Zbanuj Real Madryt w EA FC 27' in app
assert 'fc27RealBanned' in app
assert '"versionCode": 14' in appjson
print('fc27_real_ban_mobile_settings_smoke: PASS')
