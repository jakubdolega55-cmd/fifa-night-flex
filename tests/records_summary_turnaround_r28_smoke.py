import json, os, sys, tempfile, types, uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_r28_records_')
os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try:
    import streamlit
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try:
    import psycopg
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows

from database import Database
DB=Database();DB.init_schema()
BASE=datetime(2026,1,1,tzinfo=timezone.utc);clock=0

def stamp():
    global clock
    clock+=1
    return (BASE+timedelta(minutes=clock)).isoformat()

def player(pid):
    with DB.connect() as c:c.execute(DB._sql('INSERT INTO players (id,name,normalized_name,created_at) VALUES (?,?,?,?)'),(pid,pid,pid.casefold(),stamp()))

def tournament(tid):
    with DB.connect() as c:
        c.execute(DB._sql('INSERT INTO tournaments (id,status,phase,is_test,is_current,game_version,groups_revealed,created_at,completed_at,champion_player_id) VALUES (?,?,?,?,?,?,?,?,?,?)'),(tid,'completed','completed',0,0,'FC27',1,stamp(),stamp(),'A'))
        c.execute(DB._sql('INSERT INTO flex_tournament_meta (tournament_id,player_count,format_key,team_pool_json,draw_json,extra_json,draw_revealed,redraw_count) VALUES (?,?,?,?,?,?,?,?)'),(tid,2,'league4_final','[]','{}','{}',1,0))
        for i,p in enumerate(('A','B'),1):
            c.execute(DB._sql('INSERT INTO tournament_players (tournament_id,player_id,team,team_reveal_order,team_revealed,group_name,tie_order) VALUES (?,?,?,?,?,?,?)'),(tid,p,f'Team {p}',i,1,'',i))

def match(tid,no,hs,aws):
    with DB.connect() as c:c.execute(DB._sql('INSERT INTO matches (id,tournament_id,match_no,stage,group_name,home_player_id,away_player_id,home_score,away_score,winner_player_id,played_at,match_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)'),(str(uuid.uuid4()),tid,no,'LEAGUE','', 'A','B',hs,aws,'A' if hs>aws else 'B',stamp(),'played'))

def ev(tid,no,order,pid,minute):
    with DB.connect() as c:c.execute(DB._sql('INSERT INTO match_events (id,tournament_id,match_no,event_order,event_type,minute,stoppage,minute_label,actor_player_id,credited_player_id,footballer_name,normalized_footballer,synthetic_de,confidence,source_images_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'),(str(uuid.uuid4()),tid,no,order,'normal_goal',minute,0,str(minute),pid,pid,f'F {pid}',f'f {pid}',0,'high','[]',stamp()))

def summary(tid,no,h,a):
    payload={'home':h,'away':a,'usable_for_awards':True}
    with DB.connect() as c:
        now=stamp();c.execute(DB._sql('INSERT INTO match_summary_stats (tournament_id,match_no,game_version,parser_version,stats_json,confidence_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)'),(tid,no,'FC27','r28-test',json.dumps(payload),'{}',now,now))

for p in ('A','B'):player(p)
tid='r28';tournament(tid)
# A comes back from 0:3 to win 4:3. Also supplies max possession/xG.
match(tid,1,4,3)
for i,(pid,minute) in enumerate([('B',5),('B',10),('B',15),('A',30),('A',40),('A',50),('A',60)],1):ev(tid,1,i,pid,minute)
summary(tid,1,{'expected_goals':4.20,'possession':72,'shots':19},{'expected_goals':2.10,'possession':28,'shots':9})
# Lower values in another match should not replace records.
match(tid,2,2,0)
summary(tid,2,{'expected_goals':2.50,'possession':61,'shots':11},{'expected_goals':0.70,'possession':39,'shots':5})

r=DB.all_time_records();z=r['detailed_records']
assert z['max_xg']['player_name']=='A' and z['max_xg']['value']==4.2,z['max_xg']
assert z['max_possession']['player_name']=='A' and z['max_possession']['value']==72.0,z['max_possession']
assert z['biggest_turnaround']['winner_name']=='A',z['biggest_turnaround']
assert z['biggest_turnaround']['loser_name']=='B',z['biggest_turnaround']
assert z['biggest_turnaround']['deficit']==3,z['biggest_turnaround']
assert z['biggest_comeback']['deficit']==3 and z['biggest_blown_lead']['lead']==3
print('records_summary_turnaround_r28_smoke PASS')
