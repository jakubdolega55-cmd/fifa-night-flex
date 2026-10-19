import os, sys, tempfile, types, json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_awards_season_')
os.chdir(WORK)
sys.path.insert(0,str(ROOT))
os.environ.pop('DATABASE_URL',None)
try:
    import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try:
    import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows
    sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows

from database import Database, GALA_AWARD_ORDER

db=Database();db.init_schema();year=datetime.now(timezone.utc).year
s1=db.current_awards_season();assert s1['season_no']==1 and str(s1['started_at']).startswith(str(year))

# Existing pre-season selections from the current year migrate to Season 1 once.
legacy={k:{'id':f'{k}-1','name':f'{k} winner'} for k in GALA_AWARD_ORDER}
with db.connect() as conn:
    db._setting_set_conn(conn,f'flex_award_selections_{year}',json.dumps(legacy))
assert db.award_selections(year)==legacy

cats=[]
snapshot={}
for key in GALA_AWARD_ORDER:
    cand={'id':f'{key}-1','name':f'{key} winner','score':1,'reason':'test'}
    cats.append({'key':key,'title':key,'award':True,'candidates':[cand],'engraving':None})
    snapshot[key]={'key':key,'title':key,'engraving':None,'nominees':[cand],'winner':cand,'winner_is_test_fallback':False}
fake={'year':year,'season':s1,'categories':cats,'overview':{'matches':12,'tournaments':3},'selections':legacy,'nomination_summary':[]}
real_annual=db.annual_awards
db.annual_awards=lambda _year: fake
state={'year':year,'status':'finished','current_index':len(GALA_AWARD_ORDER)-1,'order':list(GALA_AWARD_ORDER),
       'nominee_order':{},'winner_ids':{k:f'{k}-1' for k in GALA_AWARD_ORDER},'categories_snapshot':snapshot,
       'base_meta':{'available':True,'ready':True,'test_mode':False,'selected_count':18,'required_count':18,'missing_selections':[],
                    'missing_selection_details':[],'invalid_selections':[],'invalid_selection_details':[],'unavailable_keys':[],'unavailable':[]}}
db._gala_save_state(year,state)
result=db.close_current_awards_season()
assert result['closed']['season_no']==1 and result['current']['season_no']==2
assert len(db.awards_season_history())==1
assert db.awards_season_snapshot(1)['overview']['matches']==12
# New season gets clean organizer selections/Gala state automatically.
assert db.award_selections(year)=={}
db.annual_awards=real_annual
fresh=db.annual_awards(year)
assert fresh.get('season',{}).get('season_no')==2
assert fresh['overview']['matches']==0 and fresh['categories']==[]
assert db.awards_gala_status(year)['status']=='idle'
print('AWARDS SEASON CLOSE SMOKE PASS')
