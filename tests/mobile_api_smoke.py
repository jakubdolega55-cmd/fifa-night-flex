import os, sys, types, tempfile, json, traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.mkdtemp(prefix='fifa_backend_smoke_')
os.chdir(WORK)
sys.path.insert(0,str(ROOT))

# The production requirements provide streamlit/psycopg. Minimal CI/sandbox images may
# omit them; the SQLite smoke path does not use their external services, so lightweight
# import fallbacks keep this test runnable there as well.
try:
    import streamlit  # noqa: F401
except ModuleNotFoundError:
    st=types.ModuleType('streamlit')
    class Secrets(dict):
        def get(self,k,d=None): return d
    st.secrets=Secrets()
    def cache_resource(*a,**kw):
        def deco(fn): return fn
        return deco
    st.cache_resource=cache_resource
    sys.modules['streamlit']=st
try:
    import psycopg  # noqa: F401
except ModuleNotFoundError:
    ps=types.ModuleType('psycopg')
    rows=types.ModuleType('psycopg.rows'); rows.dict_row=object()
    ps.rows=rows
    sys.modules['psycopg']=ps; sys.modules['psycopg.rows']=rows

os.environ['ADMIN_PASSWORD']='test-admin'
os.environ['MOBILE_TOKEN_SECRET']='test-secret'
os.environ.pop('DATABASE_URL',None)

from fastapi.testclient import TestClient
import mobile_api
mobile_api.db.init_schema()
client=TestClient(mobile_api.app)

RESULTS=[]
def ok(name, detail=''):
    RESULTS.append((name,'PASS',detail)); print('PASS',name,detail)
def fail(name, detail=''):
    RESULTS.append((name,'FAIL',detail)); print('FAIL',name,detail)

def req(method,path,*,json_data=None,headers=None,expect=200):
    r=client.request(method,path,json=json_data,headers=headers or {})
    if r.status_code!=expect:
        body=r.text[:800]
        raise AssertionError(f'{method} {path}: expected {expect}, got {r.status_code}: {body}')
    try: return r.json(), r
    except Exception: return None,r

# health/config/auth
try:
    d,_=req('GET','/api/v1/health'); assert d['api_version']=='1.0.2'; ok('health')
    d,_=req('GET','/api/v1/config'); assert all(str(n) in d['formats'] for n in range(3,9)); ok('config formats 3-8')
    _,_=req('POST','/api/v1/tournaments',json_data={'player_names':['A','B','C'],'player_count':3,'format_key':'league3_final','is_test':False},expect=401); ok('official create requires controller')
    d,_=req('POST','/api/v1/auth/controller',json_data={'password':'test-admin'}); token=d['token']; AUTH={'Authorization':f'Bearer {token}'}; ok('controller login')
    d,_=req('GET','/api/v1/auth/me',headers=AUTH); assert d.get('controller') is True; ok('controller me')
except Exception as e:
    fail('bootstrap',repr(e)); raise


def current():
    d,_=req('GET','/api/v1/live'); return d.get('tournament')

# Phone -> TV event queue: a draw must be available immediately and in a replayable feed.
try:
    d,_=req('POST','/api/v1/tournaments',json_data={'player_names':['TV A','TV B','TV C','TV D','TV E'],'player_count':5,'format_key':'double5','is_test':True})
    tv_tid=d['id']
    r,_=req('POST',f'/api/v1/tournaments/{tv_tid}/teams/reveal')
    feed,_=req('GET',f'/api/v1/tv/feed/{tv_tid}')
    ev=[x for x in feed.get('events',[]) if x.get('kind')=='team_wheel']
    assert ev and ev[-1].get('payload',{}).get('player_id')==r.get('revealed',{}).get('player_id')
    assert ev[-1].get('payload',{}).get('team')
    ok('phone draw is queued for synchronized TV replay')
    req('POST',f'/api/v1/tournaments/{tv_tid}/reset')
except Exception as e:
    fail('phone draw is queued for synchronized TV replay',repr(e)); traceback.print_exc()

def setup_tournament(count,fmt,is_test=True,auth=None,stake=0):
    names=[f'P{count}_{i+1}' for i in range(count)]
    payload={'player_names':names,'player_count':count,'format_key':fmt,'is_test':is_test,'stake_per_player':stake,'cash_flags':[True]*count}
    d,_=req('POST','/api/v1/tournaments',json_data=payload,headers=auth)
    tid=d['id']
    # drive setup to active
    for guard in range(100):
        s,_=req('GET',f'/api/v1/tournaments/{tid}/setup')
        phase=s['phase']
        if phase=='draft_order':
            req('POST',f'/api/v1/tournaments/{tid}/draft/reveal',headers=auth)
            # one reroll exercises endpoint while still legal
            req('POST',f'/api/v1/tournaments/{tid}/draft/reroll',headers=auth)
            req('POST',f'/api/v1/tournaments/{tid}/draft/confirm',headers=auth)
        elif phase=='team_draft':
            players=sorted([p for p in s['players'] if not p['team_revealed']],key=lambda p:p['team_reveal_order'])
            if not players: break
            p=players[0]
            avail=s.get('available_draft_teams') or s.get('draft_available') or []
            fixed=[x for x in avail if x!='🃏 Wild Card']
            if fixed:
                body={'player_id':p['player_id'],'slot':fixed[0],'wildcard_name':''}
            else:
                suggestion=(s.get('wildcard_suggestions') or ['Ajax'])[0]
                body={'player_id':p['player_id'],'slot':'🃏 Wild Card','wildcard_name':suggestion}
            req('POST',f'/api/v1/tournaments/{tid}/draft/pick',json_data=body,headers=auth)
        elif phase=='team_draw':
            d,_=req('POST',f'/api/v1/tournaments/{tid}/teams/reveal',headers=auth)
            rev=d.get('revealed')
            if rev and rev.get('wildcard'):
                s2=d.get('setup') or {}
                suggestion=(s2.get('wildcard_suggestions') or ['Ajax'])[0]
                req('POST',f'/api/v1/tournaments/{tid}/wildcard/confirm',json_data={'player_id':rev['player_id'],'team_name':suggestion},headers=auth)
            # If all have been revealed, finish; otherwise continue revealing.
            s3,_=req('GET',f'/api/v1/tournaments/{tid}/setup')
            if all(bool(p.get('team_revealed')) for p in s3.get('players',[])):
                req('POST',f'/api/v1/tournaments/{tid}/teams/finish',headers=auth)
        elif phase=='structure_draw':
            req('POST',f'/api/v1/tournaments/{tid}/structure/reveal',headers=auth)
            req('POST',f'/api/v1/tournaments/{tid}/structure/reroll',headers=auth)
            req('POST',f'/api/v1/tournaments/{tid}/structure/confirm',headers=auth)
            break
        elif phase=='active':
            break
        else:
            raise AssertionError(f'unknown setup phase {phase}')
    t=current(); assert t and t['id']==tid and t['phase']=='active', (fmt,t)
    return tid


def resolve_special(tid,t,auth=None):
    sp=t.get('special_event') or t.get('special_draw')
    if not sp: return False
    kind=sp.get('kind')
    if not sp.get('selected') and kind!='group_playoffs':
        req('POST',f'/api/v1/tournaments/{tid}/special/{kind}/reveal',headers=auth)
    req('POST',f'/api/v1/tournaments/{tid}/special/{kind}/ack',headers=auth)
    return True


def complete_active(tid,auth=None,exercise=False):
    did_undo=False; did_defer=False; did_add_scorer=False; did_conflict=False; did_skip=False
    played=0
    for guard in range(300):
        t=current(); assert t and t['id']==tid
        if t['status']=='completed':
            return {'played':played,'undo':did_undo,'defer':did_defer,'scorer':did_add_scorer,'conflict':did_conflict,'skip':did_skip,'summary':t.get('summary')}
        if resolve_special(tid,t,auth):
            continue
        m=t.get('current_match')
        if not m:
            # refresh once in case special state or dependency just resolved
            t=current(); m=t.get('current_match') if t else None
            if not m:
                raise AssertionError(f'active tournament stuck with no current match: {t}')
        no=int(m['match_no'])
        if exercise and not did_defer and (t.get('defer') or {}).get('allowed'):
            before=no
            d,_=req('POST',f'/api/v1/tournaments/{tid}/matches/{no}/defer',headers=auth)
            after=(d.get('tournament') or {}).get('current_match') or {}
            assert int(after.get('match_no') or 0)!=before
            did_defer=True
            continue
        if exercise and not did_skip and (t.get('skip') or {}).get('allowed'):
            req('POST',f'/api/v1/tournaments/{tid}/matches/{no}/skip',headers=auth)
            did_skip=True
            continue
        if exercise and not did_add_scorer:
            opts,_=req('GET',f'/api/v1/tournaments/{tid}/matches/{no}/scorer-options')
            req('POST',f'/api/v1/tournaments/{tid}/matches/{no}/scorers',json_data={'side':'home','name':'Smoke Scorer'},headers=auth)
            opts2,_=req('GET',f'/api/v1/tournaments/{tid}/matches/{no}/scorer-options')
            assert any(str(x.get('name','')).casefold()=='smoke scorer' for x in opts2['home']['options'])
            did_add_scorer=True
        payload={'home_score':2,'away_score':0,'scorers':{'home':{'team':m.get('home_team') or '','items':[{'name':'Smoke Scorer','goals':1}]} if did_add_scorer else {'team':m.get('home_team') or '','items':[]},'away':{'team':m.get('away_team') or '','items':[]}}}
        d,_=req('POST',f'/api/v1/tournaments/{tid}/matches/{no}/result',json_data=payload,headers=auth)
        played+=1
        if exercise and not did_conflict:
            _,_=req('POST',f'/api/v1/tournaments/{tid}/matches/{no}/result',json_data={'home_score':1,'away_score':0},headers=auth,expect=409)
            did_conflict=True
        if exercise and not did_undo:
            ud,_=req('POST',f'/api/v1/tournaments/{tid}/undo-last',headers=auth)
            assert int(ud.get('undone_match_no') or 0)==no
            did_undo=True
            # resave same match, no scorer detail required
            req('POST',f'/api/v1/tournaments/{tid}/matches/{no}/result',json_data={'home_score':2,'away_score':0},headers=auth)
            played+=1
    raise AssertionError('completion guard exceeded')

formats={
3:['league3_final'],4:['league4_final','double4'],5:['double5','league5_final'],6:['groups6','groups6_full','double6'],7:['double7','groups7','groups7_sf'],8:['groups8_sf','double8','groups8_barrage']}

# Every supported test format through full setup + completion.
format_details=[]
for count,keys in formats.items():
    for fmt in keys:
        try:
            tid=setup_tournament(count,fmt,True,None)
            info=complete_active(tid,None,exercise=(fmt=='groups6_full'))
            h,_=req('GET',f'/api/v1/history/{tid}')
            assert h['tournament']['status']=='completed'
            assert h['matches']
            format_details.append((fmt,info['played']))
            ok(f'full test flow {fmt}',f"played={info['played']} flags={info}")
            # release current pointer before next tournament
            req('POST',f'/api/v1/tournaments/{tid}/new')
        except Exception as e:
            fail(f'full test flow {fmt}',repr(e))
            traceback.print_exc()
            try:
                t=current()
                if t: req('POST',f"/api/v1/tournaments/{t['id']}/reset")
            except Exception: pass

# Scanner semantics without calling OpenAI: side mapping, own goals, penalties, DE technical bonus.
try:
    ctx={
        'stage':'FINAL','format_key':'double4','de_wb_bonus':0,'de_wb_advantage_player_id':None,'de_wb_advantage_team':None,
        'participants':[
            {'slot':'home','player_id':'H','player_name':'Home','team':'Barcelona'},
            {'slot':'away','player_id':'A','player_name':'Away','team':'Bayern'},
        ],
    }
    scan={
        'left_label':'Bayern','right_label':'Barcelona','score_left':1,'score_right':2,'match_clock':'90:00','score_confidence':'high',
        'left_participant_slot':'away','right_participant_slot':'home','mapping_confidence':'high','shootout_left':None,'shootout_right':None,
        'event_list_complete':True,'needs_more_images':False,'notes':[],
        'events':[
            {'image_indices':[1],'minute':10,'stoppage':None,'minute_label':'10','side':'right','event_type':'normal_goal','player':'Raphinha','own_goal_by':None,'related_player':None,'credited_side':'right','confidence':'high'},
            {'image_indices':[1],'minute':20,'stoppage':None,'minute_label':'20','side':'left','event_type':'own_goal','player':'Kane','own_goal_by':None,'related_player':None,'credited_side':'left','confidence':'high'},
            {'image_indices':[1],'minute':30,'stoppage':None,'minute_label':'30','side':'left','event_type':'penalty_goal','player':'Kane','own_goal_by':None,'related_player':None,'credited_side':'left','confidence':'high'},
            {'image_indices':[1],'minute':40,'stoppage':None,'minute_label':'40','side':'right','event_type':'penalty_miss','player':'Lewandowski','own_goal_by':None,'related_player':None,'credited_side':'right','confidence':'high'},
        ],
    }
    mapped=mobile_api._map_scan_to_fifa_context(scan,ctx)['fifa_night']
    assert mapped['mapping_ok'] is True and mapped['home_score']==2 and mapped['away_score']==1
    assert mapped['goal_validation']['complete'] is True
    og=next(e for e in mapped['events'] if e['event_type']=='own_goal')
    assert og['footballer_name']=='Kane' and og['actor_player_id']=='A' and og['credited_player_id']=='H'
    miss=next(e for e in mapped['events'] if e['event_type']=='penalty_miss')
    assert miss['credited_player_id'] is None
    ok('scan mapping: own goal + penalty semantics')

    overlap={
        'score_left':0,'score_right':1,
        'events':[
            {'image_indices':[1],'minute':12,'stoppage':None,'minute_label':'12','side':'right','event_type':'normal_goal','player':'Raphinha','own_goal_by':None,'related_player':None,'credited_side':'right','confidence':'medium'},
            {'image_indices':[2],'minute':12,'stoppage':None,'minute_label':'12','side':'right','event_type':'normal_goal','player':'Raphinha','own_goal_by':None,'related_player':None,'credited_side':'right','confidence':'high'},
        ],
    }
    overlap=mobile_api._normalize_and_validate_event_scan_result(overlap)
    assert len(overlap['events'])==1 and overlap['events'][0]['image_indices']==[1,2] and overlap['goal_validation']['complete'] is True
    ok('overlapping scan images deduplicate the same event')

    ctx_de={**ctx,'de_wb_bonus':1,'de_wb_advantage_player_id':'H','de_wb_advantage_team':'Barcelona'}
    de_scan={**scan,'score_left':0,'score_right':1,'events':[
        {'image_indices':[1],'minute':2,'stoppage':None,'minute_label':'2','side':'left','event_type':'own_goal','player':'Kane','own_goal_by':None,'related_player':None,'credited_side':'left','confidence':'high'},
    ]}
    de_mapped=mobile_api._map_scan_to_fifa_context(de_scan,ctx_de)['fifa_night']
    assert de_mapped['goal_validation']['complete'] is True
    assert de_mapped['events'][0]['synthetic_de'] is True
    assert de_mapped['events'][0]['credited_player_id']=='H'
    ok('scan mapping: DE technical own goal flagged synthetic')
except Exception as e:
    fail('scanner semantics suite',repr(e)); traceback.print_exc()

# scan-preview is preview-only: without server key it fails before any match write.
try:
    from io import BytesIO
    from PIL import Image
    tid=setup_tournament(3,'league3_final',True,None)
    t=current(); m=t['current_match']; no=int(m['match_no'])
    bio=BytesIO(); Image.new('RGB',(16,16)).save(bio,format='JPEG'); raw=bio.getvalue()
    r=client.post(f'/api/v1/tournaments/{tid}/matches/{no}/scan-preview',files=[('images',('screen.jpg',raw,'image/jpeg'))])
    assert r.status_code==503 and 'Odczyt zdjęć' in r.text
    after=current(); am=after['current_match']
    assert int(am['match_no'])==no and am.get('home_score') is None and am.get('away_score') is None
    ok('scan-preview never writes before user confirmation')
    req('POST',f'/api/v1/tournaments/{tid}/reset')
except Exception as e:
    fail('scan-preview never writes before user confirmation',repr(e)); traceback.print_exc()
    try:
        t=current()
        if t and t.get('status')=='active': req('POST',f"/api/v1/tournaments/{t['id']}/reset",headers=AUTH)
    except Exception: pass

# API hard-stop for incomplete/corrupt scan corrections; server re-derives goal credit.
try:
    tid=setup_tournament(3,'league3_final',True,None)
    t=current();m=t['current_match'];no=int(m['match_no']);hp=str(m['home_player_id']);ap=str(m['away_player_id'])
    one_goal=[{'event_type':'normal_goal','minute':10,'minute_label':"10'",'footballer_name':'Scorer A','actor_player_id':hp,'credited_player_id':ap}]
    req('POST',f'/api/v1/tournaments/{tid}/matches/{no}/result',json_data={'home_score':2,'away_score':0,'events':one_goal},expect=422)
    after=current();assert int(after['current_match']['match_no'])==no and after['current_match']['home_score'] is None
    ok('API rejects incomplete scanned goal list')
    corrected=[
        {'event_type':'normal_goal','minute':10,'minute_label':"10'",'footballer_name':'Scorer A','actor_player_id':hp,'credited_player_id':ap},
        {'event_type':'own_goal','minute':20,'minute_label':"20'",'footballer_name':'Own Goal Guy','actor_player_id':ap,'credited_player_id':ap},
        {'event_type':'penalty_miss','minute':30,'minute_label':"30'",'footballer_name':'Miss Guy','actor_player_id':ap,'credited_player_id':ap},
    ]
    req('POST',f'/api/v1/tournaments/{tid}/matches/{no}/result',json_data={'home_score':2,'away_score':0,'events':corrected})
    stored=mobile_api.db.match_events(tid,no)
    normal=next(e for e in stored if e['event_type']=='normal_goal');own=next(e for e in stored if e['event_type']=='own_goal');miss=next(e for e in stored if e['event_type']=='penalty_miss')
    assert str(normal['credited_player_id'])==hp and str(own['credited_player_id'])==hp and miss.get('credited_player_id') is None
    assert not own['synthetic_de']
    ok('API canonicalizes corrected scan credit safely')
    req('POST',f'/api/v1/tournaments/{tid}/reset')
except Exception as e:
    fail('scan correction API suite',repr(e));traceback.print_exc()
    try:
        t=current()
        if t and t.get('status')=='active':req('POST',f"/api/v1/tournaments/{t['id']}/reset",headers=AUTH)
    except Exception:pass

# Red card/injury from scanned events creates a one-next-actual-match absence and then consumes it.
try:
    tid=setup_tournament(4,'league4_final',True,None)
    t=current();m=t['current_match'];no=int(m['match_no']);hp=str(m['home_player_id']);ap=str(m['away_player_id'])
    events=[
        {'event_type':'normal_goal','minute':10,'minute_label':"10'",'footballer_name':'Goal Guy','actor_player_id':hp},
        {'event_type':'red_card','minute':50,'minute_label':"50'",'footballer_name':'Red Guy','actor_player_id':hp},
        {'event_type':'injury','minute':60,'minute_label':"60'",'footballer_name':'Injured Guy','actor_player_id':ap},
    ]
    req('POST',f'/api/v1/tournaments/{tid}/matches/{no}/result',json_data={'home_score':1,'away_score':0,'events':events})
    active=mobile_api.db.active_absences(tid)
    assert {(str(x['player_id']),x['reason']) for x in active}=={(hp,'red_card'),(ap,'injury')}
    origins={hp:no,ap:no};served={}
    for _ in range(8):
        t=current();m=t.get('current_match');assert m
        participants={str(m.get('home_player_id') or ''),str(m.get('away_player_id') or '')}
        before={str(x['player_id']) for x in mobile_api.db.active_absences(tid)}
        req('POST',f"/api/v1/tournaments/{tid}/matches/{m['match_no']}/result",json_data={'home_score':1,'away_score':0})
        after={str(x['player_id']) for x in mobile_api.db.active_absences(tid)}
        for pid in (hp,ap):
            if pid in before and pid in participants:
                assert pid not in after;served[pid]=int(m['match_no'])
            elif pid in before and pid not in participants:
                assert pid in after
        if len(served)==2:break
    assert len(served)==2
    all_abs=mobile_api.db.tournament_absences(tid,include_served=True)
    by={(str(x['player_id']),x['reason']):x for x in all_abs}
    assert int(by[(hp,'red_card')]['served_match_no'])==served[hp]
    assert int(by[(ap,'injury')]['served_match_no'])==served[ap]
    ok('scan red card/injury absence lasts exactly next actual match')
    req('POST',f'/api/v1/tournaments/{tid}/reset')
except Exception as e:
    fail('scan red card/injury absence lasts exactly next actual match',repr(e));traceback.print_exc()
    try:
        t=current()
        if t and t.get('status')=='active':req('POST',f"/api/v1/tournaments/{t['id']}/reset",headers=AUTH)
    except Exception:pass

# Defer must move the current match by exactly one legal playable match.
try:
    tid=setup_tournament(4,'league4_final',True,None)
    before=current(); original=int(before['current_match']['match_no'])
    sched=[m for m in before.get('schedule',[]) if m.get('ready') and m.get('match_status')=='pending']
    req('POST',f'/api/v1/tournaments/{tid}/matches/{original}/defer')
    after=current(); shifted=int(after['current_match']['match_no'])
    assert shifted!=original
    req('POST',f'/api/v1/tournaments/{tid}/matches/{shifted}/result',json_data={'home_score':1,'away_score':0})
    returned=current(); assert int(returned['current_match']['match_no'])==original, (original,shifted,returned.get('current_match'))
    ok('defer postpones by exactly one playable match')
    req('POST',f'/api/v1/tournaments/{tid}/reset')
except Exception as e:
    fail('defer postpones by exactly one playable match',repr(e)); traceback.print_exc()
    try:
        t=current()
        if t and t.get('status')=='active': req('POST',f"/api/v1/tournaments/{t['id']}/reset",headers=AUTH)
    except Exception: pass

# An official setup action cannot be driven without controller authorization.
try:
    payload={'player_names':['OA','OB','OC'],'player_count':3,'format_key':'league3_final','is_test':False,'stake_per_player':0,'cash_flags':[True,True,True]}
    d,_=req('POST','/api/v1/tournaments',json_data=payload,headers=AUTH); tid=d['id']
    s0,_=req('GET',f'/api/v1/tournaments/{tid}/setup'); assert s0['phase']=='draft_order'
    req('POST',f'/api/v1/tournaments/{tid}/draft/reveal',expect=401)
    req('POST',f'/api/v1/tournaments/{tid}/draft/reveal',headers=AUTH)
    ok('official setup requires controller')
    req('POST',f'/api/v1/tournaments/{tid}/reset',headers=AUTH)
except Exception as e:
    fail('official setup requires controller',repr(e)); traceback.print_exc()
    try:
        t=current()
        if t and t.get('status')=='active': req('POST',f"/api/v1/tournaments/{t['id']}/reset",headers=AUTH)
    except Exception: pass

# Dedicated positive skip proof: only last irrelevant league match may be skipped.
try:
    tid=setup_tournament(4,'league4_final',True,None)
    t0=current(); league_matches=[m for m in (t0.get('schedule') or []) if m.get('stage')=='LEAGUE']
    assert len(league_matches)==6
    last_league=max(league_matches,key=lambda m:int(m['match_no']))
    weak={last_league['home_name'],last_league['away_name']}
    strong={p['name'] for p in t0.get('players',[]) if p['name'] not in weak}
    assert len(strong)==2 and len(weak)==2
    skipped=False
    for _ in range(10):
        t=current(); assert t and t['id']==tid
        if (t.get('skip') or {}).get('allowed'):
            m=t['current_match']; assert m['stage']=='LEAGUE'
            assert int(m['match_no'])==int(last_league['match_no'])
            no=int(m['match_no'])
            d,_=req('POST',f'/api/v1/tournaments/{tid}/matches/{no}/skip')
            nt=(d.get('tournament') or {})
            assert nt.get('current_match',{}).get('stage')=='FINAL'
            finalists=set((t.get('skip') or {}).get('finalists') or [])
            assert finalists==strong
            skipped=True
            break
        m=t.get('current_match'); assert m and m['stage']=='LEAGUE'
        hn=m.get('home_name'); an=m.get('away_name')
        # Strong pair beats the weak pair decisively; their mutual match can go either way.
        if hn in strong and an in weak: hs,as_=9,0
        elif an in strong and hn in weak: hs,as_=0,9
        elif hn in strong and an in strong: hs,as_=1,0
        else: hs,as_=1,0
        req('POST',f"/api/v1/tournaments/{tid}/matches/{m['match_no']}/result",json_data={'home_score':hs,'away_score':as_})
    assert skipped
    ok('skip only after finalists are mathematically fixed')
    req('POST',f'/api/v1/tournaments/{tid}/reset')
except Exception as e:
    fail('skip only after finalists are mathematically fixed',repr(e))
    traceback.print_exc()
    try:
        t=current()
        if t and t.get('status')=='active': req('POST',f"/api/v1/tournaments/{t['id']}/reset",headers=AUTH)
    except Exception: pass

# Dedicated official/security/abandon/history/finance checks.
try:
    tid=setup_tournament(4,'double4',False,AUTH,stake=10)
    t=current(); no=int(t['current_match']['match_no'])
    # official gameplay requires token
    req('POST',f'/api/v1/tournaments/{tid}/matches/{no}/result',json_data={'home_score':1,'away_score':0},expect=401)
    ok('official gameplay requires controller')
    # test mode change requires token
    req('POST',f'/api/v1/tournaments/{tid}/test-mode',json_data={'is_test':True},expect=401)
    req('POST',f'/api/v1/tournaments/{tid}/test-mode',json_data={'is_test':True},headers=AUTH)
    req('POST',f'/api/v1/tournaments/{tid}/test-mode',json_data={'is_test':False},headers=AUTH)
    ok('test↔official requires controller')
    # save one official match, then abandon
    req('POST',f'/api/v1/tournaments/{tid}/matches/{no}/result',json_data={'home_score':1,'away_score':0},headers=AUTH)
    req('POST',f'/api/v1/tournaments/{tid}/abandon',headers=AUTH)
    hist,_=req('GET','/api/v1/history')
    item=next(x for x in hist['items'] if x['id']==tid)
    assert item['unfinished'] is True and item['status']=='abandoned'
    det,_=req('GET',f'/api/v1/history/{tid}')
    assert det['tournament']['unfinished'] is True and det['summary'] is None
    assert any(m.get('home_score') is not None for m in det['matches'])
    ok('abandon keeps played matches, no champion summary')
    fin,_=req('GET','/api/v1/finance/tournaments')
    assert not any(x.get('id')==tid for x in fin.get('items',[]))
    ok('unfinished excluded from settlement')
    # unfinished tournament PNG correctly unavailable
    req('GET',f'/api/v1/exports/tournament/{tid}/summary.png',expect=422)
    ok('unfinished has no final PNG')
    # delete history requires token
    req('DELETE',f'/api/v1/history/{tid}',expect=401)
    req('DELETE',f'/api/v1/history/{tid}',headers=AUTH)
    ok('history delete controller-only')
except Exception as e:
    fail('official/abandon suite',repr(e)); traceback.print_exc()

# Duel: official, public control, no controller required.
try:
    # Ensure no active pointer.
    t=current()
    if t and t.get('status')=='active': req('POST',f"/api/v1/tournaments/{t['id']}/reset",headers=AUTH)
    d,_=req('POST','/api/v1/duels',json_data={'player_names':['Duel A','Duel B'],'team_names':['Barcelona','Bayern'],'stake_per_player':5,'cash_flags':[True,True]})
    tid=d['id']; t=current(); assert t['is_test'] is False and t['format_key']=='duel1v1'
    m=t['current_match'];no=int(m['match_no']);hp=str(m['home_player_id']);ap=str(m['away_player_id'])
    duel_events=[
        {'event_type':'normal_goal','minute':10,'minute_label':"10'",'footballer_name':'Home One','actor_player_id':hp},
        {'event_type':'normal_goal','minute':20,'minute_label':'20','footballer_name':'Home Two','actor_player_id':hp},
        {'event_type':'penalty_goal','minute':30,'minute_label':"30'",'footballer_name':'Home Three','actor_player_id':hp},
        {'event_type':'normal_goal','minute':90,'stoppage':2,'minute_label':"90+2'",'footballer_name':'Away One','actor_player_id':ap},
    ]
    req('POST',f'/api/v1/tournaments/{tid}/matches/{no}/result',json_data={'home_score':3,'away_score':1,'events':duel_events})
    t=current(); assert t['status']=='completed'
    ok('1v1 official + public gameplay')
    profile,_=req('GET',f'/api/v1/players/{hp}')
    fg=(profile.get('event_stats') or {}).get('fastest_goal') or {}
    assert fg.get('minute_label')=='10' and "'" not in str(fg.get('minute_label') or '') and '′' not in str(fg.get('minute_label') or '')
    ok('player event minute labels are punctuation-free for UI formatting')
    detail,_=req('GET',f'/api/v1/history/{tid}')
    saved_events=(detail.get('matches') or [])[0].get('events') or []
    late=next(e for e in saved_events if e.get('footballer_name')=='Away One')
    assert late.get('minute')==90 and late.get('stoppage')==2 and late.get('minute_label')=='90+2'
    ok('stoppage time survives correction as canonical 90+2')
    assert late.get('actor_player_name')=='Duel B'
    ok('history events include FIFA Night player names')
    fin,_=req('GET','/api/v1/finance/tournaments'); assert any(x['id']==tid for x in fin.get('items',[]))
    sett,_=req('POST','/api/v1/finance/settlement',json_data={'tournament_ids':[tid]}); assert sett is not None
    ok('finance + settlement read')
    req('POST','/api/v1/finance/settled',json_data={'tournament_ids':[tid],'settled':True},expect=401)
    req('POST','/api/v1/finance/settled',json_data={'tournament_ids':[tid],'settled':True},headers=AUTH)
    ok('mark settled controller-only')
    # completed PNG generation
    _,r=req('GET',f'/api/v1/exports/tournament/{tid}/summary.png'); assert r.headers.get('content-type','').startswith('image/png') and len(r.content)>1000
    ok('completed tournament PNG')
except Exception as e:
    fail('duel/finance suite',repr(e)); traceback.print_exc()

# 1v1 stays official but becomes free if either player opts out of cash.
try:
    d,_=req('POST','/api/v1/duels',json_data={'player_names':['Free A','Free B'],'team_names':['Inter','Milan'],'stake_per_player':25,'cash_flags':[True,False]})
    tid=d['id']; t=current(); assert t['is_test'] is False and float(t.get('stake_per_player') or 0)==0
    m=t['current_match']; req('POST',f"/api/v1/tournaments/{tid}/matches/{m['match_no']}/result",json_data={'home_score':1,'away_score':0})
    hist,_=req('GET','/api/v1/history'); item=next(x for x in hist['items'] if x['id']==tid)
    assert not bool(item['is_test']) and bool(item['is_duel'])
    fin,_=req('GET','/api/v1/finance/tournaments'); row=next(x for x in fin.get('items',[]) if x['id']==tid)
    assert float(row.get('stake_per_player') or 0)==0 and int(row.get('contribution_cents') or 0)==0 and int(row.get('prize_cents') or 0)==0
    ok('1v1 cash opt-out stays official and becomes free')
except Exception as e:
    fail('1v1 cash opt-out stays official and becomes free',repr(e)); traceback.print_exc()

# Stats/Awards/Milestones endpoints must return JSON after accumulated data.
for name,path in [('players','/api/v1/stats/players'),('records','/api/v1/stats/records'),('teams','/api/v1/stats/teams'),('scorers','/api/v1/stats/scorers'),('milestones','/api/v1/milestones'),('awards','/api/v1/awards/2026')]:
    try:
        d,_=req('GET',path); assert isinstance(d,(dict,list)); ok(f'stats {name}')
    except Exception as e: fail(f'stats {name}',repr(e))

print('\n=== SUMMARY ===')
passed=sum(1 for _,s,_ in RESULTS if s=='PASS'); failed=sum(1 for _,s,_ in RESULTS if s=='FAIL')
print(json.dumps({'passed':passed,'failed':failed,'formats':format_details,'workdir':WORK},ensure_ascii=False,indent=2))
if failed: sys.exit(1)
