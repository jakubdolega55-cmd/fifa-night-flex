from logic import wildcard_assignment_weights, strong_team_multiplier

weights = wildcard_assignment_weights({"champ": 1, "runner": 2, "third": 3, "other": 4})
assert weights["champ"] == 1.70
assert weights["runner"] == 1.45
assert weights["third"] == 1.15
assert weights["other"] == 1.00

assert strong_team_multiplier("PSG", 1, "FC27", "clubs") == 0.40
assert strong_team_multiplier("PSG", 2, "FC27", "clubs") == 0.60
assert strong_team_multiplier("PSG", 3, "FC27", "clubs") == 1.00

# Real is now handicapped more strongly than PSG for the previous champion/finalist.
assert strong_team_multiplier("Real Madryt", 1, "FC27", "clubs") == 0.25
assert strong_team_multiplier("Real Madryt", 2, "FC27", "clubs") == 0.45
assert strong_team_multiplier("Real Madryt", 3, "FC27", "clubs") == 1.00

# Real-ban replacement City stays neutral.
assert strong_team_multiplier("Manchester City", 1, "FC27", "clubs") == 1.00
assert strong_team_multiplier("Manchester City", 2, "FC27", "clubs") == 1.00

# National-team balance is intentionally unchanged.
for team in ("Hiszpania", "Brazylia"):
    assert strong_team_multiplier(team, 1, "FC27", "national") == 0.50
    assert strong_team_multiplier(team, 2, "FC27", "national") == 0.70

print("FC27 DRAW WEIGHT TUNING SMOKE PASS")
