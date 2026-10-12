import os, sys, tempfile, types, random
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_real_player_handicap_')
os.chdir(WORK); sys.path.insert(0,str(ROOT)); os.environ.pop('DATABASE_URL',None)
try: import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit'); st.secrets={}; st.cache_resource=lambda *a,**k:(lambda f:f); sys.modules['streamlit']=st
try: import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg'); rows=types.ModuleType('psycopg.rows'); rows.dict_row=object(); ps.rows=rows; sys.modules['psycopg']=ps; sys.modules['psycopg.rows']=rows

from database import Database
from logic import (
    allowed_teams, fixed_teams_for_version, strong_team_multiplier,
    fc27_real_player_multiplier, weighted_fixed_team_matching,
)

# Global FC27 club balance: Real is harder than PSG for last champion/finalist.
assert strong_team_multiplier('Real Madryt',1,'FC27','clubs') == 0.25
assert strong_team_multiplier('Real Madryt',2,'FC27','clubs') == 0.45
assert strong_team_multiplier('PSG',1,'FC27','clubs') == 0.40
assert strong_team_multiplier('PSG',2,'FC27','clubs') == 0.60

# Manual handicap applies only to Real in FC27 clubs and stacks as a multiplier.
manual={'P1':0.50}
assert fc27_real_player_multiplier('Real Madryt','P1','FC27','clubs',manual) == 0.50
assert fc27_real_player_multiplier('PSG','P1','FC27','clubs',manual) == 1.00
assert fc27_real_player_multiplier('Real Madryt','P1','FC27','national',manual) == 1.00
assert fc27_real_player_multiplier('Real Madryt','P2','FC27','clubs',manual) == 1.00

# Statistical smoke: with otherwise neutral inputs, a 90% custom reduction must
# materially lower P1's Real frequency while keeping it possible.
teams=fixed_teams_for_version('FC27','clubs',False)
pids=['P1','P2','P3','P4','P5']
def count_real(custom):
    rng=random.Random(20261012)
    c=0
    for _ in range(4000):
        out=weighted_fixed_team_matching(pids,teams,{}, {t:50 for t in teams}, {}, rng, 'FC27','clubs',custom)
        c += (out['P1']=='Real Madryt')
    return c
base=count_real({})
reduced=count_real({'P1':0.10})
assert base>500,(base,reduced)
assert 0<reduced<base/3,(base,reduced)

# Persistent admin settings: only players with prior official tournament history,
# max 3, 0-90%, and a snapshot is taken when the next tournament is created.
db=Database(); db.init_schema()
first=db.create_tournament(['A','B','C'],3,'league3_final',allowed_teams(3,'FC27','clubs',False),False,0,[True]*3,'FC27','clubs')
with db.connect() as conn:
    conn.execute(db._sql("UPDATE tournaments SET status='completed', completed_at=? WHERE id=?"),('2026-10-01T00:00:00+00:00',first))
rows=db.fc27_real_handicap_candidates()
assert {r['name'] for r in rows}=={'A','B','C'},rows
ids={r['name']:str(r['id']) for r in rows}
saved=db.set_fc27_real_player_handicaps({ids['A']:50,ids['B']:65,ids['C']:80})
assert saved=={ids['A']:50,ids['B']:65,ids['C']:80},saved
assert db.fc27_real_player_handicaps()==saved
try:
    db.set_fc27_real_player_handicaps({ids['A']:50,ids['B']:60,ids['C']:70,'missing':80})
    raise AssertionError('Accepted more than 3 manual Real handicaps')
except ValueError as e:
    assert 'maksymalnie' in str(e).casefold(),e

second=db.create_tournament(['A','B','C'],3,'league3_final',allowed_teams(3,'FC27','clubs',False),False,0,[True]*3,'FC27','clubs')
b=db.setup_bundle(second)
snap=b['meta']['extra'].get('fc27_real_player_handicap_snapshot') or {}
assert snap==saved,(snap,saved)

print('FC27 REAL PLAYER HANDICAP SMOKE PASS')
