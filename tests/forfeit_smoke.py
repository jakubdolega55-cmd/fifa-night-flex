import os,sys,tempfile,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_forfeit_'); os.chdir(WORK); sys.path.insert(0,str(ROOT)); os.environ.pop('DATABASE_URL',None)
try: import streamlit
except ModuleNotFoundError:
 st=types.ModuleType('streamlit'); st.secrets={}; st.cache_resource=lambda *a,**k:(lambda f:f); sys.modules['streamlit']=st
try: import psycopg
except ModuleNotFoundError:
 ps=types.ModuleType('psycopg'); rows=types.ModuleType('psycopg.rows'); rows.dict_row=object(); ps.rows=rows; sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows
from database import Database
from logic import allowed_teams

def setup(db,tid):
 for _ in range(100):
  b=db.setup_bundle(tid); phase=b['tournament']['phase']
  if phase=='draft_order': db.reveal_draft_order(tid); db.confirm_draft_order(tid)
  elif phase=='team_draft':
   players=[p for p in db.tournament_players(tid) if not p.get('team_revealed')]
   if players:
    avail=[x for x in db.available_draft_teams(tid) if x!='🃏 Wild Card']; db.draft_pick(tid,players[0]['player_id'],avail[0])
  elif phase=='team_draw':
   r=db.reveal_next_team(tid)
   if r and r.get('wildcard'):
    for team in db.wildcard_team_suggestions('FC27'):
     try: db.confirm_wildcard_team(tid,r['player_id'],team); break
     except ValueError: pass
   if all(bool(p['team_revealed']) for p in db.setup_bundle(tid)['players']): db.start_structure_draw(tid)
  elif phase=='structure_draw': db.reveal_structure(tid); db.confirm_structure(tid); return
  elif phase=='active': return
 raise AssertionError('setup')

db=Database(); db.init_schema(); names=['A','B','C','D']
tid=db.create_tournament(names,4,'league4_final',allowed_teams(4,'FC27'),False,0,[True]*4,'FC27'); setup(db,tid)
m=db.current_match_from(db.bundle(tid)['matches'],db.bundle(tid)['meta'].get('extra') or {})
loser=str(m['away_player_id']); winner=str(m['home_player_id'])
db.forfeit_match(tid,int(m['match_no']),loser)
L=db.standings(tid)['L']; by={r['player_id']:r for r in L}
assert by[winner]['pts']==3 and by[winner]['gf']==3 and by[winner]['ga']==0,by[winner]
assert by[loser]['pts']==0 and by[loser]['gf']==0 and by[loser]['ga']==3,by[loser]
db.abandon_tournament(tid)
stats={r['player_id']:r for r in db.all_time_stats()}
sw=stats.get(winner); sl=stats.get(loser)
assert sw is None or (sw['w']==0 and sw['gf']==0 and sw['ga']==0),sw
assert sl is None or (sl['l']==0 and sl['gf']==0 and sl['ga']==0),sl
ctx=db.match_context(winner,loser); assert int(ctx.get('meetings') or 0)==0,ctx
assert db.tournament_summary(tid)['forfeit_count']==1
print('FORFEIT SMOKE PASS')
