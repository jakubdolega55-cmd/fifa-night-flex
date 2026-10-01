from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
api = (root / 'mobile' / 'src' / 'api.ts').read_text(encoding='utf-8')
app = json.loads((root / 'mobile' / 'app.json').read_text(encoding='utf-8'))

assert "File as ExpoFile" in api
assert "fetch as expoFetch" in api
assert "new ExpoFile(image.uri)" in api
assert "form.append('images',{uri:image.uri" not in api
assert app['expo']['android']['versionCode'] == 14
print('mobile_formdata_sdk57_source_smoke: PASS')
