import json, os, sys, tempfile, types, uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_r27_badges_')
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
BASE=datetime(2026,1,1,tzinfo=timezone.utc)
clock=0

def stamp():
    global clock
    clock+=1
    return (BASE+timedelta(minutes=clock)).isoformat()

def add_player(pid):
    with DB.connect() as c:
        c.execute(DB._sql('INSERT INTO players (id,name,normalized_name,created_at) VALUES (?,?,?,?)'),(pid,pid,pid.casefold(),stamp()))

def add_tournament(tid,pids,status='completed',champ=None,mode='clubs',teams=None,stake=0,fmt='league4_final',completed_at=None):
    teams=teams or {pid:f'Team {pid}' for pid in pids}
    created=stamp();done=completed_at or (stamp() if status=='completed' else None)
    extra={'team_mode':mode,'stake_per_player':float(stake)}
    if stake:
        extra['cash_player_ids']=list(pids)
    with DB.connect() as c:
        c.execute(DB._sql('INSERT INTO tournaments (id,status,phase,is_test,is_current,game_version,groups_revealed,created_at,completed_at,champion_player_id) VALUES (?,?,?,?,?,?,?,?,?,?)'),
                  (tid,status,'completed' if status=='completed' else 'active',0,0,'FC27',1,created,done,champ))
        c.execute(DB._sql('INSERT INTO flex_tournament_meta (tournament_id,player_count,format_key,team_pool_json,draw_json,extra_json,draw_revealed,redraw_count) VALUES (?,?,?,?,?,?,?,?)'),
                  (tid,len(pids),fmt,'[]','{}',json.dumps(extra),1,0))
        for i,pid in enumerate(pids,1):
            c.execute(DB._sql('INSERT INTO tournament_players (tournament_id,player_id,team,team_reveal_order,team_revealed,group_name,tie_order) VALUES (?,?,?,?,?,?,?)'),
                      (tid,pid,teams.get(pid,f'Team {pid}'),i,1,'',i))
    return tid

def add_match(tid,no,home,away,hs,aws,stage='LEAGUE',played=None,pens=None):
    when=played or stamp(); winner=None
    if pens is not None:
        winner=home if pens[0]>pens[1] else away
    elif hs!=aws:
        winner=home if hs>aws else away
    with DB.connect() as c:
        c.execute(DB._sql('INSERT INTO matches (id,tournament_id,match_no,stage,group_name,home_player_id,away_player_id,home_score,away_score,home_penalties,away_penalties,winner_player_id,played_at,match_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)'),
                  (str(uuid.uuid4()),tid,no,stage,'',home,away,hs,aws,pens[0] if pens else None,pens[1] if pens else None,winner,when,'played'))
    return when

def add_event(tid,no,order,typ,actor,credited,footballer,minute):
    with DB.connect() as c:
        c.execute(DB._sql('INSERT INTO match_events (id,tournament_id,match_no,event_order,event_type,minute,stoppage,minute_label,actor_player_id,credited_player_id,footballer_name,normalized_footballer,synthetic_de,confidence,source_images_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'),
                  (str(uuid.uuid4()),tid,no,order,typ,minute,0,str(minute),actor,credited,footballer,footballer.casefold() if footballer else '',0,'high','[]',stamp()))

def add_summary(tid,no,home,away):
    stats={'home':home,'away':away,'usable_for_awards':True}
    with DB.connect() as c:
        now=stamp();c.execute(DB._sql('INSERT INTO match_summary_stats (tournament_id,match_no,game_version,parser_version,stats_json,confidence_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)'),
            (tid,no,'FC27','r27-test',json.dumps(stats),'{}',now,now))

def add_final(tid,no,champ,runner):
    add_match(tid,no,champ,runner,2,0,stage='FINAL')

# Players used by all scenarios.
players=['A','B','C','D','E','G','FNL','RT','R1','R2','CH','X1','X2','X3','X4','X5','X6']
for p in players:add_player(p)

# --- Match / Summary / Events / H2H ---
active='active-badges'
add_tournament(active,['A','B','C','D','E','G'],status='active',teams={p:f'Club {p}' for p in ['A','B','C','D','E','G']})
no=1
# Full control + Oblężenie.
add_match(active,no,'A','B',4,0)
add_summary(active,no,{'expected_goals':3.4,'possession':65,'shots':18},{'expected_goals':1.0,'possession':35,'shots':8});no+=1
# Napad stulecia.
add_match(active,no,'A','B',1,0)
add_summary(active,no,{'expected_goals':0.5,'possession':42,'shots':6},{'expected_goals':2.2,'possession':58,'shots':13});no+=1
# One Man Army + Pięciopak + missed penalty + own goal recovery + miss-to-hero.
add_match(active,no,'A','B',5,1)
add_event(active,no,1,'penalty_miss','A',None,'Hero',5)
add_event(active,no,2,'own_goal','A','B','Defender A',10)
for i,minute in enumerate((20,30,40,50,60),3):add_event(active,no,i,'normal_goal','A','A','Hero',minute)
no+=1
# Finish a five-match 3+ goals streak for A. The 1:0 heist reset the streak, so
# the 5:1 event match plus four consecutive 3+ goal games earn it.
for opp in ('C','D','E','C'):
    add_match(active,no,'A',opp,3,0);no+=1

# H2H curse breaker then Nemesis: L L L W W W W W vs G.
for score in [(0,1)]*3+[(1,0)]*5:
    add_match(active,no,'A','G',score[0],score[1]);no+=1

# Ensure at least four qualified H2H opponents, all beaten by A. B already has 3 meetings above.
# C/D/E have one each above, add two more wins against each.
for opp in ('C','D','E'):
    for _ in range(2):
        add_match(active,no,'A',opp,1,0);no+=1

# --- Eternal finalist ---
for idx,champ in enumerate(('X1','X2','X3'),1):
    tid=f'final-loss-{idx}';add_tournament(tid,['FNL',champ],champ=champ,teams={'FNL':'Ever FC',champ:f'Club {champ}'})
    add_final(tid,1,champ,'FNL')

# --- Return to throne: title, five entered tournaments without title, title again. ---
tid='rt-first';add_tournament(tid,['RT','R1'],champ='RT',teams={'RT':'Roma','R1':'Milan'});add_final(tid,1,'RT','R1')
for idx in range(5):
    tid=f'rt-drought-{idx+1}';add_tournament(tid,['RT','R1','R2'],champ='R1',teams={'RT':'Roma','R1':'Milan','R2':'Inter'});add_final(tid,1,'R1','R2')
tid='rt-return';add_tournament(tid,['RT','R1'],champ='RT',teams={'RT':'Roma','R1':'Milan'});add_final(tid,1,'RT','R1')

# --- Club legend + many colors + double crown + Big jump. ---
# Three Arsenal titles, then Bayern, then Spain (national). Last event has six cash players at 40 zł each => +200 zł net.
for idx,team in enumerate(('Arsenal','Arsenal','Arsenal','Bayern'),1):
    tid=f'ch-club-{idx}';add_tournament(tid,['CH','X4'],champ='CH',mode='clubs',teams={'CH':team,'X4':'PSG'});add_final(tid,1,'CH','X4')
tid='ch-national';cash_players=['CH','X1','X2','X3','X4','X5'];add_tournament(tid,cash_players,champ='CH',mode='national',teams={p:('Hiszpania' if p=='CH' else f'Rep {p}') for p in cash_players},stake=40);add_final(tid,1,'CH','X1')

ach=DB.achievement_center();by_player={p['player_id']:{x['key'] for x in p['unlocked']} for p in ach['players']}
A=by_player['A']
for key in ('full_control','century_heist','siege','missed_penalty_win','own_goal_recovery','nemesis_h2h','curse_breaker','conquer_everyone','one_man_army','gas_to_floor','five_pack','miss_to_hero'):
    assert key in A,(key,sorted(A))
assert 'eternal_finalist' in by_player['FNL'],by_player['FNL']
assert 'return_to_throne' in by_player['RT'],by_player['RT']
for key in ('double_crown','many_colors_champion','club_legend','big_jump'):
    assert key in by_player['CH'],(key,by_player['CH'])

catalog=ach['catalog'];keys={x['key'] for x in catalog}
new_keys={
 'full_control','century_heist','siege','missed_penalty_win','own_goal_recovery','eternal_finalist','nemesis_h2h','curse_breaker',
 'conquer_everyone','double_crown','many_colors_champion','big_jump','return_to_throne','club_legend','one_man_army','gas_to_floor','five_pack','miss_to_hero'
}
assert new_keys<=keys,new_keys-keys
assert len(catalog)==53,len(catalog)
allowed={'career','rivalry','match','hero','tournament','teams','finance'}
assert all(x.get('category') in allowed for x in catalog),[(x['key'],x.get('category')) for x in catalog if x.get('category') not in allowed]

# UI grouping + final Wielki skok threshold stay aligned with the approved R27 design.
mobile_stats=(ROOT/'mobile'/'src'/'StatsScreen.tsx').read_text(encoding='utf-8')
streamlit_app=(ROOT/'app.py').read_text(encoding='utf-8')
database_src=(ROOT/'database.py').read_text(encoding='utf-8')
for label in ('🏅 Kariera','🔥 Forma i rywalizacja','🎮 Mecze','🎯 Bohaterowie i wydarzenia','🏆 Turnieje','👕 Drużyny','💰 Finanse'):
    assert label in mobile_stats,label
    assert label in streamlit_app,label
assert 'co najmniej +200 zł netto' in database_src
assert '/ +200 zł' in database_src
assert '/ +100 zł' not in database_src
print('ACHIEVEMENT BADGES R27 PASS')
