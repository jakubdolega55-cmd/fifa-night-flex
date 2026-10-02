import os,sys,tempfile,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_visible_tb_');os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try: import streamlit
except ModuleNotFoundError:
 st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try: import psycopg
except ModuleNotFoundError:
 ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows
from database import Database
from logic import allowed_teams

def setup(db,n,fmt,names):
 tid=db.create_tournament(names,n,fmt,allowed_teams(n,'FC27'),True,0,[True]*n,'FC27')
 for _ in range(160):
  b=db.setup_bundle(tid);ph=b['tournament']['phase']
  if ph=='draft_order':db.reveal_draft_order(tid);db.confirm_draft_order(tid)
  elif ph=='team_draft':
   p=next(x for x in db.tournament_players(tid) if not x.get('team_revealed'));avail=[x for x in db.available_draft_teams(tid) if x!='🃏 Wild Card'];db.draft_pick(tid,p['player_id'],avail[0])
  elif ph=='team_draw':
   r=db.reveal_next_team(tid)
   if r and r.get('wildcard'):
    for team in db.wildcard_team_suggestions('FC27'):
     try:db.confirm_wildcard_team(tid,r['player_id'],team);break
     except ValueError:pass
   if all(bool(p['team_revealed']) for p in db.setup_bundle(tid)['players']):db.start_structure_draw(tid)
  elif ph=='structure_draw':db.reveal_structure(tid);db.confirm_structure(tid);return tid
  elif ph=='active':return tid
 raise AssertionError('setup')

def play_ready_draws(db,tid,limit):
 done=0
 for _ in range(300):
  state=db.big_visible_draw_state(tid)
  if state:
   if state.get('draw_mode')=='tiebreak': return state,done
   # normal visible pairing reveal is already selected in non-DE modes; just ACK
   if not state.get('selected'): db.reveal_big_visible_draw(tid,state['kind'])
   db.ack_big_visible_draw(tid,state['kind']);continue
  bundle=db.bundle(tid);meta=bundle.get('meta') or {};extra=meta.get('extra') or {};m=db.current_match_from(bundle['matches'],extra)
  if not m:
   pending=[x for x in bundle['matches'] if x.get('home_player_id') and x.get('away_player_id') and x.get('home_score') is None]
   if not pending:return None,done
   m=pending[0]
  db.save_result(tid,int(m['match_no']),0,0);done+=1
  if done>=limit:
   return db.big_visible_draw_state(tid),done
 raise AssertionError('loop')

def reveal_ack(db,tid,state):
 assert state and state.get('draw_mode')=='tiebreak' and not state.get('selected'),state
 db.reveal_big_visible_draw(tid,state['kind'])
 shown=db.big_visible_draw_state(tid);assert shown.get('selected') and len(shown.get('selected_order') or [])>=2,shown
 db.ack_big_visible_draw(tid,state['kind'])
 return shown

db=Database();db.init_schema()

# 1) League: three 0:0 draws => all exact; final must wait for visible lot.
tid=setup(db,3,'league3_final',['L1','L2','L3'])
for no in (1,2,3):db.save_result(tid,no,0,0)
st=db.big_visible_draw_state(tid);assert st and st.get('draw_mode')=='tiebreak',st
final=next(x for x in db.matches(tid) if int(x['match_no'])==4);assert not final.get('home_player_id') and not final.get('away_player_id'),final
reveal_ack(db,tid,st)
final=next(x for x in db.matches(tid) if int(x['match_no'])==4);assert final.get('home_player_id') and final.get('away_player_id'),final
print('PASS league visible tiebreak')

# 2) groups9_final4: all group matches 0:0. Resolve A/B/C group lots, then cross-group best runner lot.
tid=setup(db,9,'groups9_final4',[f'G{i}' for i in range(1,10)])
for no in range(1,10):db.save_result(tid,no,0,0)
seen=[]
for _ in range(6):
 st=db.big_visible_draw_state(tid)
 if not st:break
 if st.get('draw_mode')=='tiebreak':
  seen.append(st['kind']);reveal_ack(db,tid,st)
 else:
  # stop before the later semifinal pairing draw
  break
print('GROUP9 TIE DRAWS',seen)
assert any('_A' in x for x in seen) and any('_B' in x for x in seen) and any('_C' in x for x in seen),seen
assert any('runner' in x for x in seen),seen
# After all ranking lots there must be no further tiebreak pending; the normal SF
# pairing can be deterministic or separately visible depending on legal variants.
st=db.big_visible_draw_state(tid);assert not st or st.get('draw_mode')!='tiebreak',st
print('PASS groups9 cross-group visible tiebreak')

# 3) Swiss8: play all three Swiss rounds as 0:0, acknowledging normal round-pairing reveals.
tid=setup(db,8,'swiss8',[f'S{i}' for i in range(1,9)])
st,done=play_ready_draws(db,tid,12)
assert done==12,(done,st)
# normal round3 pairing may have just been ACKed by helper; TOP4 exact tie must now be visible.
if st and st.get('draw_mode')!='tiebreak':
 if not st.get('selected'):db.reveal_big_visible_draw(tid,st['kind'])
 db.ack_big_visible_draw(tid,st['kind']);st=db.big_visible_draw_state(tid)
assert st and st.get('draw_mode')=='tiebreak',st
assert len(st.get('candidates') or [])>=2,st
reveal_ack(db,tid,st)
print('PASS swiss TOP4 visible tiebreak')
print('VISIBLE TIEBREAK DRAW SMOKE PASS')
