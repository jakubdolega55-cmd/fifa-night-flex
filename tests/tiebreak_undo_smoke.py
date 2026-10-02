import os,sys,tempfile,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; WORK=tempfile.mkdtemp(prefix='undotb_');os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try: import streamlit
except ModuleNotFoundError:
 st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try: import psycopg
except ModuleNotFoundError:
 ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows
from database import Database
from logic import allowed_teams

def setup(db):
 db.init_schema();tid=db.create_tournament(['A','B','C'],3,'league3_final',allowed_teams(3,'FC27'),True,0,[True]*3,'FC27')
 for _ in range(100):
  b=db.setup_bundle(tid);ph=b['tournament']['phase']
  if ph=='draft_order':db.reveal_draft_order(tid);db.confirm_draft_order(tid)
  elif ph=='team_draft':
   pp=next(x for x in db.tournament_players(tid) if not x.get('team_revealed'));avail=[x for x in db.available_draft_teams(tid) if x!='🃏 Wild Card'];db.draft_pick(tid,pp['player_id'],avail[0])
  elif ph=='team_draw':
   r=db.reveal_next_team(tid)
   if r and r.get('wildcard'):
    for t in db.wildcard_team_suggestions('FC27'):
     try:db.confirm_wildcard_team(tid,r['player_id'],t);break
     except ValueError:pass
   if all(p['team_revealed'] for p in db.setup_bundle(tid)['players']):db.start_structure_draw(tid)
  elif ph=='structure_draw':db.reveal_structure(tid);db.confirm_structure(tid);return tid
  elif ph=='active':return tid
 raise AssertionError

db=Database();tid=setup(db)
for no in (1,2,3):db.save_result(tid,no,0,0)
st=db.big_visible_draw_state(tid);assert st and st['draw_mode']=='tiebreak'
db.reveal_big_visible_draw(tid,st['kind']);db.ack_big_visible_draw(tid,st['kind'])
with db.connect() as conn:
 _,ex=db._meta_extra_conn(conn,tid);assert ex.get('group_lot_order',{}).get('L')
print('lot stored')
no=db.undo_last_result(tid);assert no==3,no
with db.connect() as conn:
 _,ex=db._meta_extra_conn(conn,tid)
 print('after undo extra',ex)
 assert not (ex.get('group_lot_order') or {}).get('L')
 assert not any(e.get('draw_mode')=='tiebreak' for e in ex.get('visible_draws') or [])
final=next(m for m in db.matches(tid) if int(m['match_no'])==4)
assert not final.get('home_player_id') and not final.get('away_player_id'),final
# replay final group match as 0-0 => visible tie draw recreated
db.save_result(tid,3,0,0);st=db.big_visible_draw_state(tid);assert st and st.get('draw_mode')=='tiebreak',st
print('UNDO TIEBREAK RESET PASS')
