import os, sys, tempfile, types
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_gala_backend_')
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

from database import Database, GALA_AWARD_ORDER, AWARD_PRIORITY_GROUPS

db=Database();db.init_schema()
assert 'rivalry' in AWARD_PRIORITY_GROUPS[2][2] and 'rivalry' not in AWARD_PRIORITY_GROUPS[3][2]

def force_hold(year=2026):
    state=db._gala_load_state(year)
    state['category_started_at']=(datetime.now(timezone.utc)-timedelta(seconds=40)).isoformat()
    db._gala_save_state(year,state)
    out=db.awards_gala_status(year)
    assert out['display_phase']=='winner_hold'
    assert out['can_advance'] is True and out['can_replay'] is True
    return out

cats=[];sels={}
for i,key in enumerate(GALA_AWARD_ORDER):
    candidates=[]
    for j in range(1,4):
        candidates.append({'id':f'{key}-{j}','name':f'{key.upper()} {j}','score':100-j,'reason':f'reason {j}'})
    cats.append({'key':key,'title':f'🏆 {key}','award':True,'candidates':candidates,'engraving':None})
    sels[key]={'id':f'{key}-2','name':f'{key.upper()} 2'}

fake={'year':2026,'categories':cats,'overview':{},'selections':sels,'nomination_summary':[]}
db.annual_awards=lambda year: fake

idle=db.awards_gala_status(2026)
assert idle['status']=='idle' and idle['total_categories']==18 and idle['ready'] is True

started=db.start_awards_gala(2026)
assert started['status']=='running' and started['current_index']==0
assert started['current_category']['key']=='superscorer'
assert started['current_category']['winner']['id']=='superscorer-2'
nom_ids=[x['id'] for x in started['current_category']['nominees']]
assert sorted(nom_ids)==sorted([f'superscorer-{j}' for j in range(1,4)])
assert started['display_phase']=='intro_pending'
ready=db.mark_awards_gala_tv_ready(2026,0);assert ready['display_phase']=='intro'

state=db._gala_load_state(2026)
state['category_started_at']=(datetime.now(timezone.utc)-timedelta(seconds=10)).isoformat();db._gala_save_state(2026,state)
nom=db.awards_gala_status(2026)
assert nom['display_phase']=='nominees' and nom['nominees_revealed']>=1

# Server-side guard: phone/API cannot skip a category before the winner HOLD.
try:
    db.advance_awards_gala(2026)
    raise AssertionError('advance should be blocked before winner_hold')
except ValueError:
    pass

hold=force_hold()
assert hold['current_category']['winner']['id']=='superscorer-2'

# Replay is also only legal after reveal and restarts the complete automatic cycle.
replayed=db.replay_awards_gala_category(2026)
assert replayed['display_phase']=='intro_pending' and replayed['current_index']==0
db.mark_awards_gala_tv_ready(2026,0)
force_hold()

# Full 1 -> 18 run. Every category must reach HOLD before NEXT is accepted.
for expected_index in range(1,18):
    nxt=db.advance_awards_gala(2026)
    assert nxt['current_index']==expected_index and nxt['current_category']['key']==GALA_AWARD_ORDER[expected_index]
    assert nxt['display_phase']=='intro_pending' and nxt['can_advance'] is False
    ready=db.mark_awards_gala_tv_ready(2026,expected_index);assert ready['display_phase']=='intro'
    force_hold()
last=db.awards_gala_status(2026)
assert last['current_index']==17 and last['next_label']=='ZAKOŃCZ GALĘ'
finale=db.advance_awards_gala(2026)
assert finale['status']=='finale' and finale['display_phase']=='finale' and finale['can_advance'] is True
finished=db.advance_awards_gala(2026)
assert finished['status']=='finished'
reset=db.reset_awards_gala(2026)
assert reset['status']=='idle'

# Testing mode permits UI development before all winners are selected and clearly marks fallback.
fake_missing=dict(fake);fake_missing['selections']={k:v for k,v in sels.items() if k!='superscorer'}
db.annual_awards=lambda year: fake_missing
st2=db.start_awards_gala(2026)
assert st2['ready'] is False and st2['available'] is True and st2['current_category']['winner_is_test_fallback'] is True

print('GALA BACKEND SMOKE PASS')
