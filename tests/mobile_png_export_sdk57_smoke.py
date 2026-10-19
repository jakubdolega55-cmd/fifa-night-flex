from pathlib import Path
import json

src = Path('mobile/src/export.ts').read_text(encoding='utf-8')
assert "from 'expo-media-library';" in src
assert 'Asset.create(result.uri)' in src
assert "requestPermissionsAsync(true,['photo'])" in src
assert 'saveToLibraryAsync' not in src
assert 'MediaLibrary.' not in src

app = json.loads(Path('mobile/app.json').read_text(encoding='utf-8'))
plugins = app['expo']['plugins']
ml = next(x for x in plugins if isinstance(x, list) and x[0] == 'expo-media-library')
opts = ml[1]
assert opts['granularPermissions'] == ['photo']
assert opts['savePhotosPermission']

uses = []
for f in ['mobile/src/FifaScreen.tsx','mobile/src/StatsScreen.tsx','mobile/src/AwardsScreen.tsx']:
    s=Path(f).read_text(encoding='utf-8')
    assert "from './export'" in s
    uses.append((f,s.count('getPng(')))
assert sum(n for _,n in uses) >= 4, uses
print('PASS mobile PNG export SDK57:', uses)
