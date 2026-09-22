import os, sys, tempfile, types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = tempfile.mkdtemp(prefix='fifa_audit_regression_')
os.chdir(WORK)
sys.path.insert(0, str(ROOT))
os.environ.pop('DATABASE_URL', None)

try:
    import streamlit  # noqa: F401
except ModuleNotFoundError:
    st = types.ModuleType('streamlit')
    st.secrets = {}
    st.cache_resource = lambda *a, **k: (lambda f: f)
    sys.modules['streamlit'] = st
try:
    import psycopg  # noqa: F401
except ModuleNotFoundError:
    ps = types.ModuleType('psycopg')
    rows = types.ModuleType('psycopg.rows')
    rows.dict_row = object()
    ps.rows = rows
    sys.modules['psycopg'] = ps
    sys.modules['psycopg.rows'] = rows

from database import Database, MatchAlreadyDecidedError
from logic import allowed_teams


def drive_setup(db: Database, tid: str) -> None:
    for _ in range(100):
        bundle = db.setup_bundle(tid)
        phase = bundle['tournament']['phase']
        if phase == 'draft_order':
            db.reveal_draft_order(tid)
            db.confirm_draft_order(tid)
        elif phase == 'team_draft':
            player = next(p for p in db.tournament_players(tid) if not p.get('team_revealed'))
            fixed = [x for x in db.available_draft_teams(tid) if x != '🃏 Wild Card']
            db.draft_pick(tid, player['player_id'], fixed[0])
        elif phase == 'team_draw':
            revealed = db.reveal_next_team(tid)
            if revealed and revealed.get('wildcard'):
                for team in db.wildcard_team_suggestions('FC27'):
                    try:
                        db.confirm_wildcard_team(tid, revealed['player_id'], team)
                        break
                    except ValueError:
                        pass
            if all(bool(p['team_revealed']) for p in db.setup_bundle(tid)['players']):
                db.start_structure_draw(tid)
        elif phase == 'structure_draw':
            db.reveal_structure(tid)
            db.confirm_structure(tid)
            return
        elif phase == 'active':
            return
    raise AssertionError('setup guard exceeded')


def expect_value_error(fn, contains: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert contains.casefold() in str(exc).casefold(), (contains, str(exc))
        return
    raise AssertionError(f'Expected ValueError containing {contains!r}')


db = Database()
db.init_schema()

# League: penalties are never valid, even if the score is tied.
tid = db.create_tournament(['A', 'B', 'C', 'D'], 4, 'league4_final', allowed_teams(4, 'FC27'), True, 0, [True] * 4, 'FC27')
drive_setup(db, tid)
bundle = db.bundle(tid)
m = db.current_match_from(bundle['matches'], bundle['meta'].get('extra') or {})
no = int(m['match_no'])
expect_value_error(lambda: db.save_result(tid, no, 1, 1, 5, 4), 'tylko w fazie pucharowej')

# Manual scorer team labels from a client are ignored in favour of server assignment.
home_team = str(m.get('home_team') or '')
db.save_result(tid, no, 2, 1, scorers={
    'home': {'team': 'FAKE CLIENT TEAM', 'items': [{'name': 'Tester', 'goals': 1}]},
    'away': {'team': 'OTHER FAKE TEAM', 'items': []},
})
with db.connect() as conn:
    scorer = db._fetchone(conn, 'SELECT team_name FROM match_scorers WHERE tournament_id=? AND match_no=?', (tid, no))
assert scorer and scorer['team_name'] == home_team, (home_team, scorer)

# A second direct database write must not overwrite the first result.
try:
    db.save_result(tid, no, 0, 3)
except MatchAlreadyDecidedError:
    pass
else:
    raise AssertionError('Second save_result overwrote an already played match')
with db.connect() as conn:
    stored = db._fetchone(conn, 'SELECT home_score,away_score,match_status FROM matches WHERE tournament_id=? AND match_no=?', (tid, no))
assert stored == {'home_score': 2, 'away_score': 1, 'match_status': 'played'}, stored

# Knockout: penalties require a tied match, two values and a non-tied shoot-out.
duel = db.create_duel(['K1', 'K2'], ['PSG', 'Bayern Monachium'], False, 0, [True, True], 'FC27')
dm = db.matches(duel)[0]
dno = int(dm['match_no'])
expect_value_error(lambda: db.save_result(duel, dno, 2, 1, 5, 4), 'tylko przy remisie')
expect_value_error(lambda: db.save_result(duel, dno, 1, 1, 5, None), 'dla obu stron')
expect_value_error(lambda: db.save_result(duel, dno, 1, 1, 5, 5), 'nie może być remisowy')
expect_value_error(lambda: db.save_result(duel, dno, 1, 1), 'remis wymaga karnych')
db.save_result(duel, dno, 1, 1, 5, 4)
with db.connect() as conn:
    stored = db._fetchone(conn, 'SELECT home_score,away_score,home_penalties,away_penalties,match_status FROM matches WHERE tournament_id=? AND match_no=?', (duel, dno))
assert stored == {'home_score': 1, 'away_score': 1, 'home_penalties': 5, 'away_penalties': 4, 'match_status': 'played'}, stored

print('AUDIT REGRESSION SMOKE PASS')
