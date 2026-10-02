import os,sys,tempfile,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; WORK=tempfile.mkdtemp(prefix='final3tb_'); os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try: import streamlit
except ModuleNotFoundError:
 st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try: import psycopg
except ModuleNotFoundError:
 ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows
from database import Database
from logic import allowed_teams

def setup(db):
 db.init_schema(); names=[f'P{i}' for i in range(1,10)]
 tid=db.create_tournament(names,9,'groups9_barrage_final3',allowed_teams(9,'FC27'),True,0,[True]*9,'FC27')
 for _ in range(160):
  b=db.setup_bundle(tid);ph=b['tournament']['phase']
  if ph=='team_draw':
   r=db.reveal_next_team(tid)
   if r and r.get('wildcard'):
    for team in db.wildcard_team_suggestions('FC27'):
     try:db.confirm_wildcard_team(tid,r['player_id'],team);break
     except ValueError:pass
   if all(p['team_revealed'] for p in db.setup_bundle(tid)['players']):db.start_structure_draw(tid)
  elif ph=='structure_draw':db.reveal_structure(tid);db.confirm_structure(tid);return tid
  elif ph=='active':return tid
 raise AssertionError('setup')

def ack_any(db,tid):
 ev=db.big_visible_draw_state(tid)
 if ev:
  if not ev.get('selected'):db.reveal_big_visible_draw(tid,ev['kind'])
  db.ack_big_visible_draw(tid,ev['kind']); return True
 return False

db=Database();tid=setup(db)
# groups decisive; use scheduler order rather than match no
for _ in range(9):
 while ack_any(db,tid): pass
 b=db.bundle(tid);m=db.current_match_from(b['matches'],(b.get('meta') or {}).get('extra') or {})
 assert m and int(m['match_no'])<=9,(m and m['match_no'])
 db.save_result(tid,int(m['match_no']),2,0)
# acknowledge barrage draw
while ack_any(db,tid): pass
# play barrage M10-12 2:0, whichever ready
for no in (10,11,12):
 b=db.bundle(tid);m=next(x for x in b['matches'] if int(x['match_no'])==no);assert m.get('home_player_id') and m.get('away_player_id'),m
 db.save_result(tid,no,2,0)
# cyclic final3 exact: M13 H>A 1:0, M14 H>A 1:0, M15 away wins 1:0
for no,hs,aw in ((13,1,0),(14,1,0),(15,0,1)):
 b=db.bundle(tid);m=next(x for x in b['matches'] if int(x['match_no'])==no);assert m.get('home_player_id') and m.get('away_player_id'),(no,m)
 db.save_result(tid,no,hs,aw)
st=db.big_visible_draw_state(tid)
print('state',st)
assert st and st.get('draw_mode')=='tiebreak' and st.get('apply_scope')=='final3',st
b=db.bundle(tid);assert b['tournament']['status']=='active',b['tournament']
db.reveal_big_visible_draw(tid,st['kind']);shown=db.big_visible_draw_state(tid);assert shown.get('selected')
first=shown['selected_order'][0]['player_id']
db.ack_big_visible_draw(tid,st['kind'])
b=db.bundle(tid);print('completed',b['tournament']['status'],b['tournament']['champion_player_id'],first)
assert b['tournament']['status']=='completed' and b['tournament']['champion_player_id']==first
print('FINAL3 VISIBLE TIEBREAK PASS')
