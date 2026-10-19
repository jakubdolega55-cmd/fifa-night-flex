import random
from logic import allowed_teams, is_wildcard_slot, weighted_team_assignments_with_unused

# The partial 3/4/5-player FC27 wheel still contains 5 named clubs + 1 WC,
# but WC should usually land on an unused technical slot. These thresholds
# are deliberately loose; they catch a regression to the old ~50/67/83%
# WC usage without depending on exact RNG frequencies.
LIMITS={3:0.22,4:0.30,5:0.48}
SAMPLES=90
for n in (3,4,5):
    pool=allowed_teams(n,'FC27','clubs',False)
    pids=[f'p{i}' for i in range(n)]
    wc_used=0
    fixed_counts={team:0 for team in pool if not is_wildcard_slot(team)}
    for seed in range(SAMPLES):
        out=weighted_team_assignments_with_unused(
            pids,pool,{},random.Random(10000+n*1000+seed),{}, {},'FC27','clubs',{}
        )
        teams=list(out.values())
        if any(is_wildcard_slot(t) for t in teams): wc_used+=1
        for team in teams:
            if team in fixed_counts: fixed_counts[team]+=1
    rate=wc_used/SAMPLES
    assert rate < LIMITS[n],(n,rate,LIMITS[n])
    # Every named club must appear more often than WC in the sample.
    assert all(count>wc_used for count in fixed_counts.values()),(n,wc_used,fixed_counts)
    print(f'PASS FC27 {n}: WC used in {rate:.1%}; named teams clearly preferred')
