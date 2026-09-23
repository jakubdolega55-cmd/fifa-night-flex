from pathlib import Path
root=Path(__file__).resolve().parents[1]
api=(root/'mobile/src/api.ts').read_text(encoding='utf-8')
aw=(root/'mobile/src/AwardsScreen.tsx').read_text(encoding='utf-8')
app=(root/'mobile/App.tsx').read_text(encoding='utf-8')
for token in ['galaStart','galaNext','galaReplay','galaReset','/api/v1/gala/${year}']:
    assert token in api, token
for token in ['Pilot Gali Awards','PREZENTACJA W TOKU','NA EKRANIE','POWTÓRZ KATEGORIĘ','winner_hold','nominees_revealed']:
    assert token in aw, token
assert '<AwardsScreen controller={controller}/>' in app
print('gala mobile controller smoke: PASS')
