import os, sys, tempfile, types
from pathlib import Path
from collections import defaultdict, Counter

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_de910_')
os.chdir(WORK);sys.path.insert(0,str(ROOT));os.environ.pop('DATABASE_URL',None)
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
        b=db.setup_bundle(tid); phase=b['tournament']['phase']
        if phase=='team_draw':
            r=db.reveal_next_team(tid)
            if r and r.get('wildcard'):
                for team in db.wildcard_team_suggestions('FC27'):
                    try: db.confirm_wildcard_team(tid,r['player_id'],team);break
                    except ValueError: continue
            if all(bool(p['team_revealed']) for p in db.setup_bundle(tid)['players']): db.start_structure_draw(tid)
        elif phase=='structure_draw':
            db.reveal_structure(tid);db.confirm_structure(tid);return
        elif phase=='active': return
    raise AssertionError('setup loop')


def play_de(n,fmt,expected):
    db=Database();db.init_schema(); names=[f'{fmt}_{i+1}' for i in range(n)]
    tid=db.create_tournament(names,n,fmt,allowed_teams(n,'FC27'),True,0,[True]*n,'FC27')
    drive_setup(db,tid)
    losses=defaultdict(int); draw_events=[]; played_pairs=[]
    for _ in range(200):
        b=db.bundle(tid)
        if b['tournament']['status']=='completed': break
        ev=db.big_visible_draw_state(tid)
        if ev:
            assert int(ev.get('candidate_count') or 0)>1, ev
            if ev.get('bye_player_id'):
                ids={str(x.get('player_id')) for x in ev.get('bye_candidates') or []}
                assert str(ev['bye_player_id']) in ids
                assert len(ids)>1
            draw_events.append(ev)
            db.ack_big_visible_draw(tid,ev['kind']);continue
        ready=[m for m in b['matches'] if m.get('home_score') is None and m.get('home_player_id') and m.get('away_player_id')]
        assert ready,[(m['match_no'],m['stage']) for m in b['matches'] if m.get('home_score') is None]
        # Follow the actual scheduler, not logical match numbers.
        m=db.current_match_from(b['matches'],b['meta'].get('extra') or {})
        assert m
        h,a=str(m['home_player_id']),str(m['away_player_id'])
        assert losses[h] < 2,(fmt,m['match_no'],'home already eliminated',h,losses[h])
        assert losses[a] < 2,(fmt,m['match_no'],'away already eliminated',a,losses[a])
        played_pairs.append((int(m['match_no']),str(m['stage']),h,a))
        # Home wins every played match. For the GF this also preserves the WB champion's +1 policy.
        db.save_result(tid,int(m['match_no']),2,0)
        losses[a]+=1
    else: raise AssertionError('play loop')

    done=db.bundle(tid); assert done['tournament']['status']=='completed'
    assert sum(m.get('home_score') is not None for m in done['matches'])==expected
    summary=db.tournament_summary(tid); champ=summary.get('champion')
    assert summary.get('third_place',{}).get('name'),(fmt,summary)
    assert summary.get('fourth_place',{}).get('name'),(fmt,summary)
    champion_pid=next(p['player_id'] for p in done['players'] if p.get('name')==champ)
    assert losses[str(champion_pid)]<2
    assert sum(1 for pid,v in losses.items() if v>=2)==n-1,(fmt,dict(losses),champ)
    with db.connect() as conn:
        order=db._placement_order_conn(conn,tid)
    assert len(order)==n and len(set(order))==n,(fmt,order)
    top_names=[next(p['name'] for p in done['players'] if str(p['player_id'])==str(pid)) for pid in order[:4]]
    assert top_names[0]==summary.get('champion') and top_names[1]==summary.get('runner_up'),(fmt,top_names,summary)
    assert top_names[2]==summary.get('third_place',{}).get('name') and top_names[3]==summary.get('fourth_place',{}).get('name'),(fmt,top_names,summary)

    kinds=[str(x.get('kind')) for x in draw_events]
    if fmt=='double9':
        for k in ('double9_d9_bye1','double9_d9_bye2','double9_lb_bye3','double9_lb_bye4'):
            assert k in kinds,(k,kinds)
    else:
        # R1/cross are shown only when 2+ equally-good full pairings survive the
        # rematch/rest filter. The LB BYE always has 3 legal weighted candidates.
        assert 'double10_lb_bye_cross' in kinds,kinds
        bye=next(x for x in draw_events if x.get('kind')=='double10_lb_bye_cross')
        assert len(bye.get('bye_candidates') or [])==3
        for x in draw_events:
            if x.get('kind') in ('double10_lb_r1','double10_lb_bye_cross','double10_lb_cross'):
                assert int(x.get('candidate_count') or 0)>1

    print('PASS',fmt,expected,'matches',len(draw_events),'visible draws','two-loss elimination OK')
    return db


def test_bye_weighting():
    db=Database()
    # Three hypothetical candidates: r played most recently, o waited longest.
    mm={
      10:{'match_no':10,'home_player_id':'o','away_player_id':'x','home_score':1},
      11:{'match_no':11,'home_player_id':'m','away_player_id':'y','home_score':1},
      12:{'match_no':12,'home_player_id':'r','away_player_id':'z','home_score':1},
    }
    c=Counter()
    for _ in range(1600):
        pick,_=db._dynamic_lb_bye_choice(['o','m','r'],mm);c[pick]+=1
    assert c['r']>c['o']*1.45,c
    assert c['m']>c['o']*1.10,c
    print('PASS dynamic LB BYE weighting',dict(c))



def test_de_rematch_policy():
    db=Database()
    # A-B have just played each other: if another complete pairing exists,
    # they must not be paired again immediately.
    mm={
      20:{'match_no':20,'home_player_id':'a','away_player_id':'b','home_score':2,'away_score':0},
    }
    for _ in range(250):
        pairs,_=db._choose_de_pairing(['a','b','c','d'],mm)
        assert frozenset(('a','b')) not in {frozenset(x) for x in pairs},pairs

    # Once A and B have each played somebody else, their old H2H carries no
    # penalty. A later LB rematch is a normal draw outcome.
    mm2={
      20:{'match_no':20,'home_player_id':'a','away_player_id':'b','home_score':2,'away_score':0},
      21:{'match_no':21,'home_player_id':'a','away_player_id':'x','home_score':2,'away_score':0},
      22:{'match_no':22,'home_player_id':'b','away_player_id':'y','home_score':2,'away_score':0},
    }
    old_rematch=0
    for _ in range(600):
        pairs,_=db._choose_de_pairing(['a','b','c','d'],mm2)
        if frozenset(('a','b')) in {frozenset(x) for x in pairs}: old_rematch+=1
    assert old_rematch>100,old_rematch
    print('PASS DE rematch policy immediate-only; older rematches stay random',old_rematch)


def test_bye_uses_actual_play_order():
    db=Database()
    # Logical numbers deliberately lie about chronology: 'old' owns M99 but played
    # first, while 'recent' owns M1 but played last. BYE weighting must use played_at.
    mm={
      99:{'match_no':99,'home_player_id':'old','away_player_id':'x','home_score':1,'played_at':'2026-09-15T10:00:00+00:00'},
      50:{'match_no':50,'home_player_id':'mid','away_player_id':'y','home_score':1,'played_at':'2026-09-15T10:10:00+00:00'},
      1:{'match_no':1,'home_player_id':'recent','away_player_id':'z','home_score':1,'played_at':'2026-09-15T10:20:00+00:00'},
    }
    c=Counter()
    for _ in range(1800):
        pick,_=db._dynamic_lb_bye_choice(['old','mid','recent'],mm);c[pick]+=1
    assert c['recent']>c['old']*1.45,c
    assert c['mid']>c['old']*1.10,c
    print('PASS LB BYE uses actual played_at order, not logical match_no',dict(c))


def test_de10_early_cross_route_draw():
    db=Database();db.init_schema(); names=[f'cross10_{i+1}' for i in range(10)]
    tid=db.create_tournament(names,10,'double10',allowed_teams(10,'FC27'),True,0,[True]*10,'FC27')
    drive_setup(db,tid)

    # M1+M2 are enough to reveal the first LB route; accept it, then complete M1-M6.
    for no in (1,2):
        b=db.bundle(tid); m=next(x for x in b['matches'] if int(x['match_no'])==no)
        assert m.get('home_player_id') and m.get('away_player_id'),m
        db.save_result(tid,no,2,0)
    ev=db.big_visible_draw_state(tid);assert ev and ev.get('kind')=='double10_lb_r1',ev
    db.ack_big_visible_draw(tid,ev['kind'])
    for no in (3,4,5,6):
        b=db.bundle(tid);m=next(x for x in b['matches'] if int(x['match_no'])==no)
        assert m.get('home_player_id') and m.get('away_player_id'),(no,m)
        db.save_result(tid,no,2,0)

    # All three LB R1 matches are now resolvable; finish them before WB M7/M8.
    for no in (10,11,12):
        b=db.bundle(tid);m=next(x for x in b['matches'] if int(x['match_no'])==no)
        assert m.get('home_player_id') and m.get('away_player_id'),(no,m)
        db.save_result(tid,no,2,0)
    ev=db.big_visible_draw_state(tid);assert ev and ev.get('kind')=='double10_lb_bye_cross',ev
    # BYE + Bridge + future M14/M15 cross are one coherent public reveal.
    assert len(ev.get('bye_candidates') or [])==3,ev
    pairs=ev.get('pairs') or [];assert len(pairs)==3,pairs
    by_no={int(x.get('match_no') or 0):x for x in pairs}
    assert set(by_no)=={13,14,15},by_no
    entries=[]
    for row in (by_no[14],by_no[15]):
        entries.extend([(row.get('home_player_id'),row.get('home_name'),row.get('home_source')),
                        (row.get('away_player_id'),row.get('away_name'),row.get('away_source'))])
    assert sum(1 for pid,_,_ in entries if pid)==1,entries
    placeholders=[name for pid,name,_ in entries if not pid]
    assert sorted(placeholders)==['Przegrany M7','Przegrany M8','Zwycięzca M13'],placeholders
    db.ack_big_visible_draw(tid,ev['kind'])
    # There must not be a second immediate draw screen for the same routing step.
    assert db.big_visible_draw_state(tid) is None
    bb=db.bundle(tid);src=(bb['meta'].get('extra') or {}).get('big_sources') or {}
    assert all(src.get(f'D10:L{no}{side}') for no in (14,15) for side in ('H','A')),src
    mm2={int(x['match_no']):x for x in bb['matches']}
    labels=[mm2[no].get(side+'_source_display') for no in (14,15) for side in ('home','away') if not mm2[no].get(side+'_player_id')]
    assert labels and all(x!='Czeka na rozstrzygnięcie' for x in labels),labels
    assert {'Zwycięzca M13','Przegrany M7','Przegrany M8'}.intersection(labels),labels
    print('PASS DE10 combined BYE/cross draw + symbolic bracket labels')


def test_de9_waits_for_real_bye_candidates():
    db=Database();db.init_schema(); names=[f'guard9_{i+1}' for i in range(9)]
    tid=db.create_tournament(names,9,'double9',allowed_teams(9,'FC27'),True,0,[True]*9,'FC27')
    drive_setup(db,tid)
    # Four of five first WB/play-in results are not enough to choose the 5-player
    # LB BYE fairly. DE9 intentionally waits for the complete candidate set.
    for no in (1,2,3,4):
        b=db.bundle(tid);m=next(x for x in b['matches'] if int(x['match_no'])==no)
        assert m.get('home_player_id') and m.get('away_player_id'),(no,m)
        db.save_result(tid,no,2,0)
    ev=db.big_visible_draw_state(tid)
    assert not ev or ev.get('kind')!='double9_d9_bye1',ev
    src=(db.bundle(tid)['meta'].get('extra') or {}).get('big_sources') or {}
    assert 'D9:L9H' not in src and 'D9:L10H' not in src,src
    print('PASS DE9 does not preselect weighted BYE before all 5 candidates are known')

def main():
    play_de(9,'double9',16)
    play_de(10,'double10',18)
    test_bye_weighting()
    test_bye_uses_actual_play_order()
    test_de_rematch_policy()
    test_de10_early_lb_route_draw()
    test_de10_early_cross_route_draw()
    test_de9_waits_for_real_bye_candidates()
    print('DE9/DE10 SMOKE PASS')



def test_de10_early_lb_route_draw():
    db=Database();db.init_schema(); names=[f'early10_{i+1}' for i in range(10)]
    tid=db.create_tournament(names,10,'double10',allowed_teams(10,'FC27'),True,0,[True]*10,'FC27')
    drive_setup(db,tid)

    # Play exactly two ready WB/play-in games. The first LB route draw must already
    # exist, even though four of its six source matches are still unresolved.
    for _ in range(2):
        b=db.bundle(tid)
        m=db.current_match_from(b['matches'],b['meta'].get('extra') or {})
        assert m and int(m['match_no']) in range(1,7),m
        db.save_result(tid,int(m['match_no']),2,0)

    ev=db.big_visible_draw_state(tid)
    assert ev and ev.get('kind')=='double10_lb_r1',ev
    assert int(ev.get('candidate_count') or 0)==15,ev
    pairs=ev.get('pairs') or []
    assert len(pairs)==3,pairs
    entries=[]
    for row in pairs:
        entries.extend([(row.get('home_player_id'),row.get('home_name'),row.get('home_source')),
                        (row.get('away_player_id'),row.get('away_name'),row.get('away_source'))])
    # Exactly two losers are known; the other four slots must be readable placeholders.
    assert sum(1 for pid,_,_ in entries if pid)==2,entries
    unresolved=[name for pid,name,_ in entries if not pid]
    assert len(unresolved)==4 and all(str(x).startswith('Przegrany M') for x in unresolved),entries
    db.ack_big_visible_draw(tid,ev['kind'])
    b=db.bundle(tid)
    src=(b['meta'].get('extra') or {}).get('big_sources') or {}
    assert all(src.get(f'D10:L{no}{side}') for no in (10,11,12) for side in ('H','A')),src
    print('PASS DE10 early LB route draw after two entrants; unresolved sources visible')

if __name__=='__main__':main()
