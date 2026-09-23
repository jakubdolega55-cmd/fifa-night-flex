import os, sys, tempfile, types
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_gala_closeout_')
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

import database as mod
from database import Database, GALA_AWARD_ORDER

db=Database();db.init_schema()

def cat(key):
    return {'key':key,'title':key,'award':True,'candidates':[
        {'id':f'{key}-1','name':f'{key} A','score':99,'reason':'A'},
        {'id':f'{key}-2','name':f'{key} B','score':98,'reason':'B'},
        {'id':f'{key}-3','name':f'{key} C','score':97,'reason':'C'},
    ]}

cats=[cat(k) for k in GALA_AWARD_ORDER]
sels={k:{'id':f'{k}-2','name':f'{k} B'} for k in GALA_AWARD_ORDER}
fake={'year':2026,'categories':cats,'overview':{},'selections':sels,'nomination_summary':[]}
db.annual_awards=lambda year: fake

# Full final readiness.
out=db.awards_gala_status(2026)
assert out['ready'] is True and out['selected_count']==18 and out['required_count']==18
assert out['unavailable']==[] and out['missing_selection_details']==[]

# Winner must be frozen at START. Changing organizer selections during the show
# must not rewrite the already-started ceremony.
started=db.start_awards_gala(2026)
assert started['current_category']['winner']['id']=='superscorer-2'
fake['selections']['superscorer']={'id':'superscorer-3','name':'superscorer C'}
refreshed=db.awards_gala_status(2026)
assert refreshed['current_category']['winner']['id']=='superscorer-2'

# Missing-candidate category is skipped in TEST rehearsal rather than showing an
# empty nominee/winner screen. Missing winner uses a frozen statistical leader.
db.reset_awards_gala(2026)
fake2={'year':2026,'categories':[cat(k) for k in GALA_AWARD_ORDER if k!='fair_play'],'overview':{},
       'selections':{k:{'id':f'{k}-2'} for k in GALA_AWARD_ORDER if k not in ('fair_play','progress')},'nomination_summary':[]}
db.annual_awards=lambda year: fake2
mod.GALA_TEST_MODE=True
idle=db.awards_gala_status(2026)
assert idle['available'] is True and idle['ready'] is False
assert 'fair_play' in idle['unavailable_keys'] and 'progress' in idle['missing_selections']
trial=db.start_awards_gala(2026)
assert 'fair_play' not in trial['order'] and trial['total_categories']==17
assert trial['order'][0]=='superscorer'
# Jump to progress and confirm frozen leader fallback.
st=db._gala_load_state(2026);st['current_index']=trial['order'].index('progress');st['category_started_at']=(datetime.now(timezone.utc)-timedelta(seconds=40)).isoformat();db._gala_save_state(2026,st)
progress=db.awards_gala_status(2026)
assert progress['current_category']['winner']['id']=='progress-1'
assert progress['current_category']['winner_is_test_fallback'] is True

# Production gate: hidden/unavailable until all 18 valid selections exist.
db.reset_awards_gala(2026)
mod.GALA_TEST_MODE=False
prod=db.awards_gala_status(2026)
assert prod['available'] is False and prod['ready'] is False
try:
    db.start_awards_gala(2026)
    raise AssertionError('production gala should be blocked')
except ValueError:
    pass

# Invalid/stale selected id is also not considered ready.
fake3={'year':2026,'categories':[cat(k) for k in GALA_AWARD_ORDER],'overview':{},
       'selections':{k:{'id':f'{k}-2'} for k in GALA_AWARD_ORDER},'nomination_summary':[]}
fake3['selections']['defense']={'id':'deleted-candidate'}
db.annual_awards=lambda year: fake3
invalid=db.awards_gala_status(2026)
assert invalid['ready'] is False and 'defense' in invalid['invalid_selections'] and invalid['selected_count']==17

# Fully valid production state opens the gala and uses all 18 categories.
fake3['selections']['defense']={'id':'defense-2'}
ready=db.awards_gala_status(2026)
assert ready['ready'] is True and ready['available'] is True and ready['selected_count']==18
final_start=db.start_awards_gala(2026)
assert final_start['total_categories']==18 and final_start['order']==GALA_AWARD_ORDER


# Navigation gate is cheap and follows the same final rule.
with db.connect() as conn:
    db._setting_set_conn(conn,'flex_award_selections_2027','{}')
assert db.awards_gala_nav_visible(2027) is False
with db.connect() as conn:
    db._setting_set_conn(conn,'flex_award_selections_2027',__import__('json').dumps({k:{'id':f'{k}-1'} for k in GALA_AWARD_ORDER}))
assert db.awards_gala_nav_visible(2027) is True

print('GALA CLOSEOUT SMOKE PASS')
