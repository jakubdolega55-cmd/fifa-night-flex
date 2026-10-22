import json, os, sys, tempfile, types, uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_r33_recent_')
os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try:
    import streamlit
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try:
    import psycopg
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows

from database import Database, now_iso

DB=Database();DB.init_schema();now=now_iso();T='r33-history';A='A';B='B'
with DB.connect() as c:
    for pid,name in [(A,'Ala'),(B,'Bartek')]:
        c.execute(DB._sql('INSERT INTO players (id,name,normalized_name,created_at) VALUES (?,?,?,?)'),(pid,name,name.casefold(),now))
    c.execute(DB._sql("INSERT INTO tournaments (id,status,phase,is_test,is_current,game_version,groups_revealed,created_at,completed_at) VALUES (?,?,?,?,?,?,?,?,?)"),(T,'completed','completed',0,0,'FC27',1,now,now))
    c.execute(DB._sql("INSERT INTO flex_tournament_meta (tournament_id,player_count,format_key,team_pool_json,draw_json,extra_json,draw_revealed,redraw_count) VALUES (?,?,?,?,?,?,?,?)"),(T,2,'league4_final','[]','{}','{}',1,0))
    for i,(pid,team) in enumerate([(A,'Arsenal'),(B,'Bayern')],1):
        c.execute(DB._sql("INSERT INTO tournament_players (tournament_id,player_id,team,team_reveal_order,team_revealed,group_name,tie_order) VALUES (?,?,?,?,?,?,?)"),(T,pid,team,i,1,'',i))
    for no in range(1,17):
        home_a=no%2==1
        h,a=(A,B) if home_a else (B,A)
        hs,ass=(3,1) if home_a else (1,4)
        c.execute(DB._sql("INSERT INTO matches (id,tournament_id,match_no,stage,group_name,home_player_id,away_player_id,home_score,away_score,winner_player_id,played_at,match_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"),(str(uuid.uuid4()),T,no,'LEAGUE','',h,a,hs,ass,A,now,'played'))
    stats={'home':{'expected_goals':0.9,'shots':7,'possession':43,'fouls':2},'away':{'expected_goals':2.6,'shots':14,'possession':57,'fouls':1},'usable_for_awards':True}
    c.execute(DB._sql("INSERT INTO match_summary_stats (tournament_id,match_no,game_version,parser_version,stats_json,confidence_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)"),(T,16,'FC27','r33-test',json.dumps(stats),'{}',now,now))
    c.execute(DB._sql("INSERT INTO match_events (id,tournament_id,match_no,event_order,event_type,minute,stoppage,minute_label,actor_player_id,credited_player_id,actor_team_name,credited_team_name,footballer_name,synthetic_de,source_images_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"),(str(uuid.uuid4()),T,16,1,'normal_goal',12,0,'12',A,A,'Arsenal','Arsenal','Saka',0,'[]',now))

p=DB.player_profile(A)
assert p and len(p['history'])==15,len(p.get('history') or [])
latest=p['history'][0]
assert latest['match_no']==16,latest
assert latest['event_context']=='FIFA Night #1',latest
assert latest['player_score']=='4:1',latest
assert latest['opponent']=='Bartek' and latest['team']=='Arsenal' and latest['opponent_team']=='Bayern',latest
assert latest['summary']['xg_for']==2.6 and latest['summary']['xg_against']==0.9,latest['summary']
assert latest['events'][0]['footballer_name']=='Saka',latest['events']

mobile=(ROOT/'mobile'/'src'/'StatsScreen.tsx').read_text(encoding='utf-8')
app=(ROOT/'app.py').read_text(encoding='utf-8')
assert 'function RecentMatches' in mobile
assert "([5,10,15] as const)" in mobile
assert '<RecentMatches history={p.history||[]}/>' in mobile
assert 'Brak zapisanych szczegółów Summary / Events dla tego meczu.' in mobile
assert 'st.segmented_control("Pokaż ostatnie",[5,10,15],default=5' in app
assert '#### 🕘 Ostatnie mecze' in app
print('player_recent_matches_r33_smoke PASS')
