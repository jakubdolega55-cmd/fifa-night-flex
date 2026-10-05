import os,sys,tempfile,types,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_awards_freq_'); os.chdir(WORK); sys.path.insert(0,str(ROOT)); os.environ.pop('DATABASE_URL',None)
try: import streamlit
except ModuleNotFoundError:
    st=types.ModuleType('streamlit'); st.secrets={}; st.cache_resource=lambda *a,**k:(lambda f:f); sys.modules['streamlit']=st
try: import psycopg
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg'); rows=types.ModuleType('psycopg.rows'); rows.dict_row=object(); ps.rows=rows; sys.modules['psycopg']=ps; sys.modules['psycopg.rows']=rows
from database import Database, now_iso
DB=Database(); DB.init_schema(); now=now_iso(); year=int(now[:4]); tid='freq-fairness'
players=['A','B','C','D','X','Y','E','F','G','H']
with DB.connect() as c:
    for pid in players:
        c.execute(DB._sql('INSERT INTO players (id,name,normalized_name,created_at) VALUES (?,?,?,?)'),(pid,pid,pid.casefold(),now))
    c.execute(DB._sql("INSERT INTO tournaments (id,status,phase,is_test,is_current,game_version,groups_revealed,created_at) VALUES (?,?,?,?,?,?,?,?)"),(tid,'active','active',0,1,'FC27',1,now))
    c.execute(DB._sql("INSERT INTO flex_tournament_meta (tournament_id,player_count,format_key,team_pool_json,draw_json,extra_json,draw_revealed,redraw_count) VALUES (?,?,?,?,?,?,?,?)"),(tid,len(players),'league5_final','[]','{}','{}',1,0))
    for i,pid in enumerate(players,1):
        c.execute(DB._sql("INSERT INTO tournament_players (tournament_id,player_id,team,team_reveal_order,team_revealed,group_name,tie_order) VALUES (?,?,?,?,?,?,?)"),(tid,pid,f'Team {pid}',i,1,'',i))
    no=1
    def add(h,a,hs,ass,stage='LEAGUE'):
        nonlocal_no=None
        global no
        winner=h if hs>ass else (a if ass>hs else None)
        c.execute(DB._sql("INSERT INTO matches (id,tournament_id,match_no,stage,group_name,home_player_id,away_player_id,home_score,away_score,winner_player_id,played_at,match_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"),(str(uuid.uuid4()),tid,no,stage,'',h,a,hs,ass,winner,now,'played'))
        no+=1
    # Same quality profile, different volume: A=10 matches, B=20 matches.
    pattern=[(3,0),(2,1),(2,1),(1,2),(1,2)]
    for _ in range(2):
        for hs,ass in pattern:add('A','X',hs,ass)
    for _ in range(4):
        for hs,ass in pattern:add('B','Y',hs,ass)
    # Clutch: 5/5 vs 12/14. With smoothing, the larger strong sample should edge the perfect tiny one.
    for _ in range(5):add('C','X',5,4,'QF')
    for i in range(14):add('D','Y',5 if i<12 else 4,4 if i<12 else 5,'QF')
    # Rivalry volume cap: 6 and 12 H2Hs should receive the same pure volume bonus.
    for _ in range(6):add('E','F',1,1,'LEAGUE')
    for _ in range(12):add('G','H',1,1,'LEAGUE')

aw=DB.annual_awards(year)
by={c['key']:c for c in aw['categories']}
def cand(key,pid):
    return next(x for x in by[key]['candidates'] if x['id']==pid)

for key in ('offensive','outsider','player_year'):
    a,b=cand(key,'A'),cand(key,'B')
    assert abs(float(a['score'])-float(b['score']))<1e-9,(key,a['score'],b['score'])
# Defense is also purely per-match/rate based. B's 20-match profile is exactly
# the doubled version of A's 10-match profile and must score the rate-only value.
bdef=cand('defense','B')
assert abs(float(bdef['score'])-82.0)<1e-9,bdef

c,d=cand('clutch','C'),cand('clutch','D')
assert c['clutch_pct']==100.0 and d['clutch_pct']<100.0
assert float(d['score'])>float(c['score']),(c,d)
assert d['clutch_adjusted_pct']>c['clutch_adjusted_pct']

rivs=by['rivalry']['candidates']
rf=next(x for x in rivs if set(x['participant_ids'])=={'E','F'})
rh=next(x for x in rivs if set(x['participant_ids'])=={'G','H'})
assert rf['volume_bonus']==18 and rh['volume_bonus']==18,(rf,rh)
print('AWARDS FREQUENCY FAIRNESS PASS')
