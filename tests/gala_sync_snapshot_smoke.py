import os, sys, tempfile, types
from pathlib import Path
from datetime import datetime, timezone, timedelta
ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_gala_sync_');os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try:
    import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try:
    import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows
from database import Database,GALA_AWARD_ORDER

db=Database();db.init_schema()
cats=[];sels={}
for key in GALA_AWARD_ORDER:
    cs=[{'id':f'{key}-{i}','name':f'{key}-{i}','score':10-i,'reason':'x'} for i in range(1,4)]
    cats.append({'key':key,'title':key,'award':True,'candidates':cs});sels[key]={'id':f'{key}-2','name':'x'}
fake={'year':2026,'categories':cats,'overview':{},'selections':sels,'nomination_summary':[]}
calls={'n':0}
def annual(_year):calls['n']+=1;return fake
db.annual_awards=annual
start=db.start_awards_gala(2026)
assert calls['n']==1, calls
state=db._gala_load_state(2026)
assert state.get('categories_snapshot') and state.get('base_meta')
# From now on LIVE status must not rebuild Awards at all.
def explode(_year):raise AssertionError('annual_awards called during running gala')
db.annual_awards=explode
for _ in range(5):
    out=db.awards_gala_status(2026);assert out['display_phase']=='intro_pending'
out=db.mark_awards_gala_tv_ready(2026,0);assert out['display_phase']=='intro'
state=db._gala_load_state(2026);state['category_started_at']=(datetime.now(timezone.utc)-timedelta(seconds=40)).isoformat();db._gala_save_state(2026,state)
out=db.advance_awards_gala(2026)
assert out['current_index']==1 and out['display_phase']=='intro_pending'
out=db.mark_awards_gala_tv_ready(2026,1);assert out['display_phase']=='intro'
print('GALA SYNC SNAPSHOT SMOKE PASS')
