import os, sys, tempfile, types, random
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_club_pool_')
os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try: import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try: import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows

import database as dbmod
from database import Database
from logic import fixed_teams_for_version,wildcard_suggestions_for_version,weighted_team_assignments

fixed=fixed_teams_for_version('FC27')
assert fixed==['PSG','Bayern Monachium','FC Barcelona','Arsenal','Manchester City'],fixed
wc=wildcard_suggestions_for_version('FC27')
assert wc==['Atletico','Liverpool','Man United','Inter','BVB','Napoli','Chelsea','Tottenham','AC Milan'],wc
assert all(x.casefold() not in {'real madrid','real madryt'} for x in wc)
assert not ({x.casefold() for x in fixed}&{x.casefold() for x in wc})
print('PASS FC27 fixed five + ranked Wild Card list')

counts={pid:0 for pid in ['champ','runner','third','p4','p5']}
placements={'champ':1,'runner':2,'third':3,'p4':4,'p5':5}
rng=random.Random(20260923)
for _ in range(2400):
    out=weighted_team_assignments(list(counts),fixed,placements,rng,team_ratings={t:50 for t in fixed},previous_team_by_player_id={})
    for pid,team in out.items():
        if team=='PSG':counts[pid]+=1
assert counts['champ']<counts['third'],counts
assert counts['runner']<counts['third'],counts
assert counts['champ']<counts['runner'],counts
print('PASS PSG is softer for previous champion/finalist',counts)

db=Database();db.init_schema()
db.set_award_selection(2026,'player_year','p1','P1')
db.set_award_selection(2026,'offensive','p2','P2')
with db.connect() as c:
    db._setting_set_conn(c,'flex_awards_gala_2026','{"status":"running"}')
dbmod.GALA_TEST_MODE=True
removed=db.clear_all_award_selections_for_test(2026)
assert removed==2,removed
assert db.award_selections(2026)=={}
assert db._gala_load_state(2026).get('status')=='idle'
print('PASS test-only reset clears all laureates + gala state')

dbmod.GALA_TEST_MODE=False
try:
    db.clear_all_award_selections_for_test(2026)
    raise AssertionError('production reset should be blocked')
except ValueError:
    pass
print('PASS reset-all is blocked outside gala test mode')
print('CLUB POOL + TEST RESET SMOKE PASS')
