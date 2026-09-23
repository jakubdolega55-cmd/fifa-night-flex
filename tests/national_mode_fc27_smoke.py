import os, sys, tempfile, types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_national_mode_')
os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try: import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try: import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows

from database import Database
from logic import (
    fixed_teams_for_version,wildcard_suggestions_for_version,allowed_teams,
    banned_team_names,real_helper_available,effective_team_mode,strong_team_multiplier,
)

FC27_FIXED=['Real Madryt','PSG','Bayern Monachium','FC Barcelona','Arsenal']
FC27_WC=['Manchester City','Atletico','Liverpool','Man United','Inter','BVB','Napoli','Chelsea','Tottenham','AC Milan']
NAT_FIXED=['Hiszpania','Anglia','Brazylia','Niemcy','Portugalia']
NAT_WC=['Włochy','Argentyna','Holandia','Belgia','Chorwacja','Dania','Maroko','Turcja','Szwajcaria']

assert fixed_teams_for_version('FC27','clubs')==FC27_FIXED
assert wildcard_suggestions_for_version('FC27','clubs')==FC27_WC
assert 'real madryt' not in banned_team_names('FC27','clubs')
assert not real_helper_available('FC27','clubs')
assert allowed_teams(5,'FC27','clubs')==FC27_FIXED
assert len([x for x in allowed_teams(10,'FC27','clubs') if 'Dowolna drużyna' in x])==5
print('PASS FC27 club pool: Real wheel, Man City WC, Real unbanned')

assert effective_team_mode('FC26','national')=='clubs'
assert fixed_teams_for_version('FC26','national')!=NAT_FIXED
print('PASS national mode is intentionally unavailable in FC26')

assert effective_team_mode('FC27','national')=='national'
assert fixed_teams_for_version('FC27','national')==NAT_FIXED
assert wildcard_suggestions_for_version('FC27','national')==NAT_WC
assert {'france','francja'}<=banned_team_names('FC27','national')
assert allowed_teams(5,'FC27','national')==NAT_FIXED
pool10=allowed_teams(10,'FC27','national')
assert pool10[:5]==NAT_FIXED and len([x for x in pool10 if 'Dowolna reprezentacja' in x])==5,pool10
assert all('Francja banned' in x for x in pool10[5:])
print('PASS FC27 national pool + France ban')

for team in ('PSG','Real Madryt'):
    assert strong_team_multiplier(team,1,'FC27','clubs')==0.50
    assert strong_team_multiplier(team,2,'FC27','clubs')==0.70
    assert strong_team_multiplier(team,3,'FC27','clubs')==1.0
assert strong_team_multiplier('Arsenal',1,'FC27','clubs')==1.0
for team in ('Hiszpania','Brazylia'):
    assert strong_team_multiplier(team,1,'FC27','national')==0.50
    assert strong_team_multiplier(team,2,'FC27','national')==0.70
assert strong_team_multiplier('Anglia',1,'FC27','national')==1.0
print('PASS strong-team handicap: FC27 PSG+Real / nationals Spain+Brazil')

db=Database();db.init_schema()
assert db.team_mode_setting()=='clubs'
assert db.set_team_mode('national')=='national'
assert db.team_mode_setting()=='national'
print('PASS persistent setting defaults to clubs and can switch to nationals')

# FC26 collapses a stored national preference back to clubs.
tid26=db.create_duel(['A','B'],['Bayern Monachium','PSG'],stake_per_player=10,cash_flags=[True,True],game_version='FC26',team_mode='national')
assert db.bundle(tid26)['meta']['extra']['team_mode']=='clubs'
print('PASS FC26 remains clubs when national preference is stored')

# FC27 clubs: Real works normally.
tid=db.create_duel(['A','B'],['Real Madryt','PSG'],stake_per_player=10,cash_flags=[True,True],game_version='FC27',team_mode='clubs')
b=db.bundle(tid)
assert b['meta']['extra']['team_mode']=='clubs',b['meta']['extra']
assert {p['team'] for p in b['players']}=={'Real Madryt','PSG'}
print('PASS FC27 Real works as a normal paid duel club')

# FC27 national: France rejected, fixed national duel accepted.
try:
    db.create_duel(['C','D'],['Francja','Hiszpania'],game_version='FC27',team_mode='national')
    raise AssertionError('France accepted in national mode')
except ValueError as e:
    assert 'banned' in str(e).casefold(),e

tid2=db.create_duel(['C','D'],['Hiszpania','Brazylia'],game_version='FC27',team_mode='national')
assert db.bundle(tid2)['meta']['extra']['team_mode']=='national'
print('PASS FC27 national duel stores mode and France is blocked')

# FC26 club legacy Real helper still exists; FC27 helper is rejected.
tid3=db.create_tournament(['P1','P2','P3','P4','P5'],5,'league5_final',allowed_teams(5,'FC26','clubs'),True,0,[False,True,True,True,True],'FC26','clubs')
b3=db.setup_bundle(tid3)
no_cash=next(p for p in b3['players'] if p['player_id'] not in set(b3['meta']['extra'].get('cash_player_ids') or []))
db.assign_real_helper(tid3,no_cash['player_id'])
assert next(p for p in db.setup_bundle(tid3)['players'] if p['player_id']==no_cash['player_id'])['team']=='Real Madryt'
try:
    db.assign_real_helper(tid,no_cash['player_id'])
    raise AssertionError('FC27 helper accepted')
except ValueError:
    pass
print('PASS Real helper remains FC26-clubs-only')

# Curated WC suggestions must not leak clubs into national mode.
assert db.wildcard_team_suggestions('FC27','national')==NAT_WC,db.wildcard_team_suggestions('FC27','national')
assert db.wildcard_team_suggestions('FC26','national')==db.wildcard_team_suggestions('FC26','clubs')
print('PASS mode-aware WC suggestions')

print('NATIONAL MODE + FC27 REAL SMOKE PASS')
