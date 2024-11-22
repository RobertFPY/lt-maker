import random

growth_points = 0

def _dynamic_levelup(level: int, growth: int) -> dict:
    """
    Does not support leveling down 100% because it keeps state
    """
    variance = 10
    global growth_points
    stat_changes = 0
    if growth > 0:
        free_stat_ups = growth // 100
        stat_changes += free_stat_ups
        new_growth = growth % 100
        start_growth = new_growth + growth_points
        if random.randint(0, 99) < int(start_growth):
            stat_changes += 1
            growth_points -= (100 - new_growth) / variance
        else:
            growth_points += new_growth / variance

    elif growth < 0:
        growth = -growth
        free_stat_downs = growth // 100
        stat_changes -= free_stat_downs
        new_growth = growth % 100
        start_growth = new_growth + growth_points
        if random.randint(0, 99) < int(start_growth):
            stat_changes -= 1
            growth_points -= (100 - new_growth) / variance
        else:
            growth_points += new_growth / variance

    return stat_changes

if __name__ == '__main__':
    num_trials = 2000
    random_totals = []
    dynamic_totals = []
    for _ in range(num_trials):
        level = 1
        totals = 0
        while level < 20:
            stat = _dynamic_levelup(level, 50)
            # stat = random.randint(0, 1)
            level += 1
            totals += stat
        print(totals)
        dynamic_totals.append(totals)

    for _ in range(num_trials):
        level = 1
        totals = 0
        while level < 20:
            stat = _dynamic_levelup(level, 50)
            stat = random.randint(0, 1)
            level += 1
            totals += stat
        print(totals)
        random_totals.append(totals)
