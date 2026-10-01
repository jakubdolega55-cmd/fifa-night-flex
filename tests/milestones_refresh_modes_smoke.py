import os,sys,tempfile,types,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.chdir(tempfile.mkdtemp(prefix='fifa_milestones_refresh_'));sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try: import streamlit
except ModuleNotFoundError:
 st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try: import psycopg
except ModuleNotFoundError:
 ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows
from database import Database,now_iso
DB=Database();DB.init_schema();now=now_iso();tid='milestone-firsts';p1='p1';p2='p2'
with DB.connect() as c:
 for pid,name in ((p1,'Ala'),(p2,'Ola')):
  c.execute(DB._sql('INSERT INTO players (id,name,normalized_name,created_at) VALUES (?,?,?,?)'),(pid,name,name.casefold(),now))
 c.execute(DB._sql("INSERT INTO tournaments (id,status,phase,is_test,is_current,game_version,groups_revealed,created_at,completed_at,champion_player_id) VALUES (?,'completed','completed',0,0,'FC27',1,?,?,?)"),(tid,now,now,p1))
 c.execute(DB._sql("INSERT INTO flex_tournament_meta (tournament_id,player_count,format_key,team_pool_json,draw_json,extra_json,draw_revealed,redraw_count) VALUES (?,2,'league3_final','[]','{}','{}',1,0)"),(tid,))
 c.execute(DB._sql("INSERT INTO tournament_players (tournament_id,player_id,team,team_reveal_order,team_revealed,group_name,tie_order) VALUES (?,?,?,1,1,'',1)"),(tid,p1,'Arsenal'))
 c.execute(DB._sql("INSERT INTO tournament_players (tournament_id,player_id,team,team_reveal_order,team_revealed,group_name,tie_order) VALUES (?,?,?,2,1,'',2)"),(tid,p2,'Bayern Monachium'))
 c.execute(DB._sql("INSERT INTO matches (id,tournament_id,match_no,stage,home_player_id,away_player_id,home_score,away_score,winner_player_id,played_at,match_status) VALUES (?,?,1,'FINAL',?,?,?,?,?,?,'played')"),(str(uuid.uuid4()),tid,p1,p2,3,2,p1,now))
 events=[
  ('own_goal',12,p1,p2,'Gabriel'),
  ('red_card',55,p2,None,'Kane'),
  ('normal_goal',105,p1,p1,'Saka'),
 ]
 for i,(et,minute,actor,credited,footballer) in enumerate(events,1):
  c.execute(DB._sql("INSERT INTO match_events (id,tournament_id,match_no,event_order,event_type,minute,stoppage,minute_label,actor_player_id,credited_player_id,actor_team_name,credited_team_name,footballer_name,normalized_footballer,related_footballer_name,synthetic_de,confidence,source_images_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"),(str(uuid.uuid4()),tid,1,i,et,minute,0,str(minute),actor,credited,'','','%s'%footballer,DB._norm_scorer_name(footballer),'',0,'high','[]',now))
ms=DB.global_milestones();by_key={x['key']:x for x in ms['timeline']}
assert by_key['own_goals_1']['title']=='Pierwszy zarejestrowany samobój',by_key.get('own_goals_1')
assert by_key['red_cards_1']['title']=='Pierwsza zarejestrowana czerwona kartka',by_key.get('red_cards_1')
assert by_key['extra_time_goals_1']['title']=='Pierwszy zarejestrowany gol w dogrywce',by_key.get('extra_time_goals_1')
app=(ROOT/'app.py').read_text(encoding='utf-8')
assert '@st.fragment(run_every="1s")\ndef render_setup_tv_watch' in app
assert '@st.fragment(run_every="5s")\ndef _render_tv_live_fragment' in app
assert '@st.fragment(run_every="30s")\ndef _render_tv_auto_fragment' in app
print('PASS first red / extra-time goal / own-goal milestones + 1s setup / 5s LIVE / 30s AUTO')
