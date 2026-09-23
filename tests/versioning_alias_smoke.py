import os, sys, tempfile, types, sqlite3, uuid, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_versioning_')
os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
try: import streamlit  # noqa
except ModuleNotFoundError:
    st=types.ModuleType('streamlit');st.secrets={};st.cache_resource=lambda *a,**k:(lambda f:f);sys.modules['streamlit']=st
try: import psycopg  # noqa
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg');rows=types.ModuleType('psycopg.rows');rows.dict_row=object();ps.rows=rows;sys.modules['psycopg']=ps;sys.modules['psycopg.rows']=rows

from database import Database, now_iso


def migration_test():
    Path('.local').mkdir(exist_ok=True)
    path=Path('.local/fifa_night_shared.db')
    con=sqlite3.connect(path)
    con.execute("""CREATE TABLE tournaments (
        id TEXT PRIMARY KEY,status TEXT NOT NULL,phase TEXT NOT NULL,is_test INTEGER NOT NULL DEFAULT 0,
        is_current INTEGER NOT NULL DEFAULT 0,groups_revealed INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,completed_at TEXT,champion_player_id TEXT)""")
    con.execute("INSERT INTO tournaments (id,status,phase,is_test,is_current,groups_revealed,created_at) VALUES ('old1','completed','completed',0,0,0,?)",(now_iso(),))
    con.commit();con.close()
    db=Database();db.init_schema()
    with db.connect() as c:
        row=db._fetchone(c,"SELECT game_version FROM tournaments WHERE id='old1'")
    assert row and row['game_version']=='FC26',row
    print('PASS historical migration -> FC26')


def fresh_db():
    # separate database for rating / alias tests
    import shutil
    shutil.rmtree('.local',ignore_errors=True)
    db=Database();db.init_schema();return db


def add_match(db, version, home_team, away_team, hs, ass, idx):
    tid=f'{version}_{idx}_{uuid.uuid4().hex[:6]}';hp=f'h_{tid}';ap=f'a_{tid}'
    with db.connect() as c:
        c.execute(db._sql("INSERT INTO players (id,name,normalized_name,created_at) VALUES (?,?,?,?)"),(hp,f'H{idx}',hp,now_iso()))
        c.execute(db._sql("INSERT INTO players (id,name,normalized_name,created_at) VALUES (?,?,?,?)"),(ap,f'A{idx}',ap,now_iso()))
        c.execute(db._sql("INSERT INTO tournaments (id,status,phase,is_test,is_current,game_version,groups_revealed,created_at,completed_at) VALUES (?,'completed','completed',0,0,?,0,?,?)"),(tid,version,now_iso(),now_iso()))
        c.execute(db._sql("INSERT INTO tournament_players (tournament_id,player_id,team,team_reveal_order,team_revealed,group_name,tie_order) VALUES (?,?,?,1,1,'',1)"),(tid,hp,home_team))
        c.execute(db._sql("INSERT INTO tournament_players (tournament_id,player_id,team,team_reveal_order,team_revealed,group_name,tie_order) VALUES (?,?,?,2,1,'',2)"),(tid,ap,away_team))
        winner=hp if hs>ass else ap if ass>hs else None
        c.execute(db._sql("INSERT INTO matches (id,tournament_id,match_no,stage,home_player_id,away_player_id,home_score,away_score,winner_player_id,played_at,match_status) VALUES (?,?,1,'DUEL',?,?,?,?,?,?,'played')"),(str(uuid.uuid4()),tid,hp,ap,hs,ass,winner,now_iso()))
    return tid


def rating_test(db):
    # Strong FC26 prior for PSG.
    add_match(db,'FC26','PSG','Liverpool',4,0,1)
    add_match(db,'FC26','PSG','Liverpool',3,0,2)
    with db.connect() as c:
        fc26=db._live_team_ratings_for_version_conn(c,'FC26')
        combined=db._live_team_ratings_conn(c,'FC27')
    assert abs(combined['PSG']-fc26['PSG'])<1e-9
    print('PASS FC27 n=0 uses 100% FC26 prior')

    for n in range(1,6):
        add_match(db,'FC27','PSG','Arsenal',0,2,100+n)
        with db.connect() as c:
            r26=db._live_team_ratings_for_version_conn(c,'FC26')
            r27=db._live_team_ratings_for_version_conn(c,'FC27')
            blend=db._live_team_ratings_conn(c,'FC27')
        alpha=n/5.0
        expected=(1-alpha)*float(r26.get('PSG',50.0))+alpha*float(r27.get('PSG',50.0))
        assert abs(blend['PSG']-expected)<1e-8,(n,blend['PSG'],expected)
        print(f'PASS FC27 blend n={n}: {1-alpha:.1f}/{alpha:.1f}')

    rows={x['team']:x for x in db.live_team_ratings('FC27')}
    assert rows['PSG']['matches']==5,rows['PSG']
    assert 'Liverpool' not in rows, 'FC26-only stats leaked into FC27 public rating table'
    print('PASS public FC27 rating stats do not mix FC26 matches')

    add_match(db,'FC27','PSG','Real Madryt',2,1,999)
    rows={x['team']:x for x in db.live_team_ratings('FC27')}
    assert rows['Real Madryt']['matches']==1,rows.get('Real Madryt')
    assert rows['PSG']['matches']==6
    print('PASS FC27 Real is a normal rated club')


def alias_test(db):
    db.add_team_scorers('PSG',['João Neves'])
    r=db.resolve_footballer_name('FC27','PSG','J. Neves')
    assert r['status']=='auto' and r['name']=='João Neves',r
    r2=db.resolve_footballer_name('FC27','PSG','J. Neves')
    assert r2['status']=='remembered' and r2['name']=='João Neves',r2
    print('PASS unique abbreviation auto-resolves and is remembered')

    db.add_team_scorers('Alias FC',['John Smith','James Smith'])
    amb=db.resolve_footballer_name('FC27','Alias FC','J. Smith')
    assert amb['status']=='ambiguous' and set(amb['candidates'])=={'John Smith','James Smith'},amb
    db.remember_footballer_alias('FC27','Alias FC','J. Smith','James Smith')
    assert db.resolve_footballer_name('FC27','Alias FC','J. Smith')['name']=='James Smith'
    # Same visible alias can legitimately point elsewhere in another EA FC version.
    db.remember_footballer_alias('FC26','Alias FC','J. Smith','John Smith')
    assert db.resolve_footballer_name('FC26','Alias FC','J. Smith')['name']=='John Smith'
    assert db.resolve_footballer_name('FC27','Alias FC','J. Smith')['name']=='James Smith'
    print('PASS ambiguous aliases require choice and memory is version-aware')

    with db.connect() as c:
        real_rows=db._fetchall(c,"SELECT game_version,COUNT(*) AS c FROM footballer_rosters WHERE normalized_team=? GROUP BY game_version",(db._norm_team_name('Real Madryt'),))
    counts={r['game_version']:int(r['c']) for r in real_rows}
    assert counts.get('FC26',0)>=5 and counts.get('FC27',0)>=5,counts
    print('PASS Real roster baseline exists for FC26 helper and FC27 normal club')



def add_official_event(db, tid, version, p1, p2, team1, team2, when, hs=2, ass=0, champion=True):
    with db.connect() as c:
        for pid,name in ((p1,p1.upper()),(p2,p2.upper())):
            c.execute(db._sql("INSERT INTO players (id,name,normalized_name,created_at) VALUES (?,?,?,?) ON CONFLICT(id) DO NOTHING"),(pid,name,pid,when))
        champ=p1 if champion else None
        c.execute(db._sql("INSERT INTO tournaments (id,status,phase,is_test,is_current,game_version,groups_revealed,created_at,completed_at,champion_player_id) VALUES (?,'completed','completed',0,0,?,0,?,?,?)"),(tid,version,when,when,champ))
        c.execute(db._sql("INSERT INTO flex_tournament_meta (tournament_id,player_count,format_key,team_pool_json,draw_json,extra_json,draw_revealed,redraw_count) VALUES (?,2,'league3_final','[]','{}','{}',1,0)"),(tid,))
        c.execute(db._sql("INSERT INTO tournament_players (tournament_id,player_id,team,team_reveal_order,team_revealed,group_name,tie_order) VALUES (?,?,?,1,1,'',1)"),(tid,p1,team1))
        c.execute(db._sql("INSERT INTO tournament_players (tournament_id,player_id,team,team_reveal_order,team_revealed,group_name,tie_order) VALUES (?,?,?,2,1,'',2)"),(tid,p2,team2))
        c.execute(db._sql("INSERT INTO matches (id,tournament_id,match_no,stage,home_player_id,away_player_id,home_score,away_score,winner_player_id,played_at,match_status) VALUES (?,?,1,'FINAL',?,?,?,?,?,?,'played')"),(str(uuid.uuid4()),tid,p1,p2,hs,ass,p1 if hs>ass else p2 if ass>hs else None,when))


def continuous_history_and_wc_test(db):
    import shutil
    shutil.rmtree('.local',ignore_errors=True)
    db=Database();db.init_schema()
    # Same club across FC26 + FC27 stays one historical team/stat line.
    add_official_event(db,'hist26','FC26','hist','opp','Arsenal','PSG','2026-01-01T12:00:00+00:00')
    add_official_event(db,'hist27','FC27','hist','opp','Arsenal','PSG','2026-01-02T12:00:00+00:00')
    all_time={x['player_id']:x for x in db.all_time_stats()}
    assert all_time['hist']['matches']==2,all_time['hist']
    teams={x['team']:x for x in db.team_stats()}
    assert teams['Arsenal']['matches']==2,teams.get('Arsenal')
    print('PASS player/team history continues across FC26 + FC27')

    # FC27 Arsenal is normal; Liverpool is WC. The Wild Card achievement must wait
    # for the Liverpool title rather than treating Arsenal using legacy FC26 rules.
    add_official_event(db,'wc_normal','FC27','wcguy','opp2','Arsenal','PSG','2026-02-01T12:00:00+00:00')
    add_official_event(db,'wc_real','FC27','wcguy','opp2','Liverpool','PSG','2026-02-02T12:00:00+00:00')
    center=db.achievement_center(); player=next(x for x in center['players'] if x['player_id']=='wcguy')
    wild=next(x for x in player['unlocked'] if x['key']=='wild_one')
    assert wild['tournament_id']=='wc_real',wild
    print('PASS FC27 normal/WC semantics are version-aware in achievements')

    milestones=db.global_milestones()
    first_wc=next(x for x in milestones.get('timeline',[]) if x.get('key')=='first_wc_champion')
    # hist26 Arsenal is legitimately a FC26 Wild Card and therefore remains the first WC moment.
    assert first_wc['tournament_id']=='hist26',first_wc
    print('PASS global WC milestone respects each tournament game version')

    # Annual Awards: three Arsenal FC27 matches do not count as WC; three Liverpool
    # FC27 matches do. Real is a normal FC27 wheel club and can enter Team of Year.
    for i in range(3):
        add_official_event(db,f'aw_a{i}','FC27','award','ao','Arsenal','PSG',f'2026-03-0{i+1}T12:00:00+00:00')
    for i in range(3):
        add_official_event(db,f'aw_l{i}','FC27','award','ao','Liverpool','PSG',f'2026-03-1{i+1}T12:00:00+00:00')
    for i in range(5):
        add_official_event(db,f'aw_r{i}','FC27','realuser','ro','Real Madryt','PSG',f'2026-04-0{i+1}T12:00:00+00:00')
    awards=db.annual_awards(2026)
    cats={x['key']:x for x in awards['categories']}
    wcand=next(x for x in cats['wildcards']['candidates'] if x['id']=='award')
    assert 'WC: 3/3 W' in wcand['reason'],wcand
    team_names={x['name'] for x in cats['team_best']['candidates']}
    assert 'Real Madryt' in team_names,team_names
    print('PASS Awards stay cross-version while WC classification is version-aware and FC27 Real is normal')


def main():
    migration_test();db=fresh_db();rating_test(db);alias_test(db);continuous_history_and_wc_test(db)
    print('VERSIONING + ALIAS + CONTINUITY SMOKE PASS')

if __name__=='__main__':main()
