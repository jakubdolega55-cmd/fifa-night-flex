import json, os, sys, tempfile, types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_mobile_season_')
os.chdir(WORK); sys.path.insert(0,str(ROOT))
os.environ['ADMIN_PASSWORD']='test-admin'; os.environ['MOBILE_TOKEN_SECRET']='test-secret'; os.environ.pop('DATABASE_URL',None)
try:
    import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit'); st.secrets={}; st.cache_resource=lambda *a,**k:(lambda f:f); sys.modules['streamlit']=st
try:
    import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg'); rows=types.ModuleType('psycopg.rows'); rows.dict_row=object(); ps.rows=rows
    sys.modules['psycopg']=ps; sys.modules['psycopg.rows']=rows

from fastapi.testclient import TestClient
import mobile_api
mobile_api.db.init_schema(); c=TestClient(mobile_api.app)

# Active Season 1 is exposed explicitly.
d=c.get('/api/v1/awards-seasons').json(); assert d['current']['season_no']==1
assert c.get('/api/v1/awards-season/1').json()['season']['season_no']==1
assert c.get('/api/v1/gala-season/1').json()['closed'] is False

# Simulate R19 frozen Season 1 + active Season 2.
snapshot={'year':2026,'season':{'season_no':1,'label':'Sezon 1','started_at':'2026-01-01T00:00:00+00:00','ended_at':'2026-06-30T00:00:00+00:00','closed':True},'categories':[],'overview':{'matches':12,'tournaments':3,'goals':42,'players':5},'selections':{},'nomination_summary':[],'gala':{'status':'finished','winner_summary':[]}}
with mobile_api.db.connect() as conn:
    mobile_api.db._setting_set_conn(conn,'flex_awards_season_snapshot_1',json.dumps(snapshot))
    mobile_api.db._setting_set_conn(conn,'flex_awards_season_history_v1',json.dumps([snapshot['season']]))
    mobile_api.db._setting_set_conn(conn,'flex_awards_current_season_no','2')
    mobile_api.db._setting_set_conn(conn,'flex_awards_current_season_started_at','2026-07-01T00:00:00+00:00')
d=c.get('/api/v1/awards-seasons').json(); assert [x['season_no'] for x in d['seasons']]==[1,2]
assert c.get('/api/v1/awards-season/1').json()['overview']['matches']==12
assert c.get('/api/v1/gala-season/1').json()['closed'] is True

# Closed seasons are read-only from mobile Gala controls.
token=c.post('/api/v1/auth/controller',json={'password':'test-admin'}).json()['token']; H={'Authorization':f'Bearer {token}'}
assert c.post('/api/v1/gala-season/1/start',headers=H).status_code==409

# Season-native share cards are available.
for suffix in ('summary.png','awards.png'):
    r=c.get(f'/api/v1/exports/season/1/{suffix}'); assert r.status_code==200 and r.headers['content-type'].startswith('image/png') and len(r.content)>1000

print('MOBILE AWARDS SEASON SMOKE PASS')
