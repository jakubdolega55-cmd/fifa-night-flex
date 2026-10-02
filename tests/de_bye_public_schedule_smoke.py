import os,sys,tempfile,types,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_de_bye_public_');os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try: import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try: import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows
from database import Database
from logic import allowed_teams

def drive_setup(db,tid):
    for _ in range(120):
        b=db.setup_bundle(tid);phase=b['tournament']['phase']
        if phase=='team_draw':
            r=db.reveal_next_team(tid)
            if r and r.get('wildcard'):
                for team in db.wildcard_team_suggestions('FC27'):
                    try: db.confirm_wildcard_team(tid,r['player_id'],team);break
                    except ValueError: continue
            if all(bool(p['team_revealed']) for p in db.setup_bundle(tid)['players']):db.start_structure_draw(tid)
        elif phase=='structure_draw':db.reveal_structure(tid);db.confirm_structure(tid);return
        elif phase=='active':return
    raise AssertionError('setup loop')

def main():
    db=Database();db.init_schema();tid=db.create_tournament([f'bye_{i+1}' for i in range(10)],10,'double10',allowed_teams(10,'FC27'),True,0,[True]*10,'FC27');drive_setup(db,tid)
    for no in (1,2):db.save_result(tid,no,2,0)
    ev=db.big_visible_draw_state(tid);db.ack_big_visible_draw(tid,ev['kind'])
    for no in (3,4,5,6):db.save_result(tid,no,2,0)
    for no in (10,11,12):db.save_result(tid,no,2,0)
    ev=db.big_visible_draw_state(tid);bye=str(ev['bye_player_id']);db.ack_big_visible_draw(tid,ev['kind'])
    b=db.bundle(tid);future=[m for m in b['matches'] if int(m['match_no']) in (14,15)]
    mbye=next((m for m in future if bye in (str(m.get('home_player_id') or ''),str(m.get('away_player_id') or ''))),None)
    assert mbye,mbye
    other=mbye.get('away_player_id') if str(mbye.get('home_player_id') or '')==bye else mbye.get('home_player_id')
    assert not other,mbye  # known BYE player is persisted before the opponent resolves
    schedule=db.live_schedule_from(b['matches'],b['meta']['extra']);disp={int(m['match_no']):int(m['display_match_no']) for m in schedule}
    labels=[]
    for m in schedule:
        for k in ('home_source_display','away_source_display'):
            if m.get(k): labels.append(re.sub(r'\bM(\d+)\b',lambda x:f"M{disp.get(int(x.group(1)),int(x.group(1)))}",str(m[k])))
    assert labels
    print('DE BYE PUBLIC SCHEDULE SMOKE PASS')
if __name__=='__main__':main()
