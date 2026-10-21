import json, os, sys, tempfile, types, uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_r26_summary_')
os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try:
    import streamlit
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try:
    import psycopg
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows

from database import Database, CLASSIFICATION_DISPLAY_ORDER, now_iso

DB=Database();DB.init_schema();now=now_iso();year=int(now[:4]);tid='r25-summary';A='A';B='B'
with DB.connect() as c:
    for pid,name in [(A,'Ala'),(B,'Bartek')]:
        c.execute(DB._sql('INSERT INTO players (id,name,normalized_name,created_at) VALUES (?,?,?,?)'),(pid,name,name.casefold(),now))
    c.execute(DB._sql("INSERT INTO tournaments (id,status,phase,is_test,is_current,game_version,groups_revealed,created_at) VALUES (?,?,?,?,?,?,?,?)"),(tid,'active','active',0,1,'FC27',1,now))
    c.execute(DB._sql("INSERT INTO flex_tournament_meta (tournament_id,player_count,format_key,team_pool_json,draw_json,extra_json,draw_revealed,redraw_count) VALUES (?,?,?,?,?,?,?,?)"),(tid,2,'league4_final','[]','{}','{}',1,0))
    for i,(pid,team) in enumerate([(A,'Arsenal'),(B,'Bayern')],1):
        c.execute(DB._sql("INSERT INTO tournament_players (tournament_id,player_id,team,team_reveal_order,team_revealed,group_name,tie_order) VALUES (?,?,?,?,?,?,?)"),(tid,pid,team,i,1,'',i))

    for no in range(1,6):
        c.execute(DB._sql("INSERT INTO matches (id,tournament_id,match_no,stage,group_name,home_player_id,away_player_id,home_score,away_score,winner_player_id,played_at,match_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"),
                  (str(uuid.uuid4()),tid,no,'LEAGUE','',A,B,2,1,A,now,'played'))
        stats={
            'home':{'expected_goals':1.2,'possession':60,'shots':7,'fouls':1},
            'away':{'expected_goals':2.4,'possession':40,'shots':12,'fouls':3},
            'usable_for_awards':True,
        }
        c.execute(DB._sql("INSERT INTO match_summary_stats (tournament_id,match_no,game_version,parser_version,stats_json,confidence_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)"),
                  (tid,no,'FC27','r25-test',json.dumps(stats),'{}',now,now))
        # Only the first event is needed here to prove the first-goal ranking remains.
        c.execute(DB._sql("INSERT INTO match_events (id,tournament_id,match_no,event_order,event_type,minute,stoppage,minute_label,actor_player_id,credited_player_id,footballer_name,synthetic_de,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"),
                  (str(uuid.uuid4()),tid,no,1,'normal_goal',10,0,'10',A,A,'Bukayo Saka',0,now))

aw=DB.annual_awards(year)
views=[c for c in aw['categories'] if not c.get('award')]
keys=[c['key'] for c in views]
assert keys==CLASSIFICATION_DISPLAY_ORDER,(keys,CLASSIFICATION_DISPLAY_ORDER)
for removed in ('minimalist','unlucky','simulator','penaldo','own_goals','penalty_misses','wasteful'):
    assert removed not in keys,removed
by={c['key']:c for c in views}

# Public classification descriptions should explain the idea, not expose formulas,
# thresholds, minimum samples or ranking mechanics.
for category in views:
    desc=str(category.get('description') or '').casefold()
    for forbidden in ('minimum', 'ranking po', 'liczymy', 'xgd', 'xg =', 'pkt/mecz'):
        assert forbidden not in desc,(category['key'],category.get('description'))

first=by['first_goals']['candidates'][0]
assert first['id']==A and first['score']==5,first

clinical=by['clinical']['candidates'][0]
assert clinical['id']==A and abs(clinical['goals_minus_xg_per_match']-0.8)<1e-9,clinical
poss=by['possession_king']['candidates'][0]
assert poss['id']==A and poss['possession_pct']==60.0,poss
dom=by['dominator']['candidates'][0]
assert dom['id']==B and abs(dom['xgd_per_match']-1.2)<1e-9,dom
thief=by['match_thief']['candidates'][0]
assert thief['id']==A and thief['steal_points']==15.0 and thief['stolen_wins']==5 and thief['steal_points_per_match']==3.0,thief
nerve=by['nerve_king']['candidates']
assert len(nerve)>=2 and all(x['close_match_pct']==100.0 for x in nerve[:2]),nerve

profile=DB.player_profile(A)
adv=profile.get('advanced_stats') or {}
assert 'summary_matches' not in adv,adv
assert adv=={
    'xg_per_match':1.2,
    'xga_per_match':2.4,
    'xgd_per_match':-1.2,
    'shots_per_match':7.0,
    'shots_against_per_match':12.0,
    'possession_pct':60.0,
    'fouls_per_match':1.0,
},adv

# Trusted R25 Summary metrics must not use SOT in spectacle/MOTY scoring anymore.
source=(ROOT/'database.py').read_text()
assert '_sso=' not in source and '_sov=' not in source
print('SUMMARY CLASSIFICATIONS R26 PASS')
