"""Test de fumée de la simulation : carte plate, deux tribus, N tours."""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from populous.constants import BLK_FLAT, MAP_CELLS
from populous.sim import Game


def flat_game(seed=12345):
    g = Game(seed=seed)
    for i in range(MAP_CELLS):
        g.map.blk[i] = BLK_FLAT
        g.map.alt[i] = 0
        g.map.bk2[i] = 0
        g.map.who[i] = 0
    g.stats[0].can_build = 1
    g.stats[1].can_build = 1
    g.stats[0].colour = 11
    g.stats[1].colour = 14
    return g


def report(g, label):
    pops = [g.population(t) for t in (0, 1)]
    cnts = [g.count_peeps(t) for t in (0, 1)]
    frames = Counter(p.frame for _, p in g.living())
    print("%-12s tour=%5d  peeps=%3d  vie=%s  unités=%s  mana=%s  villes=%s"
          % (label, g.game_turn, g.no_peeps, pops, cnts,
             [pl.mana for pl in g.players],
             [pl.town_count for pl in g.players]))
    return frames


def main():
    g = flat_game()
    g.place_people(0, g.map.index(8, 8), 0)
    g.place_people(1, g.map.index(56, 56), 0)
    frames = report(g, "init")
    for n in (50, 200, 1000, 3000):
        while g.game_turn < n:
            g.move_peeps()
        frames = report(g, "tour %d" % n)
        print("   frames:", dict(sorted(frames.items())))

    # vérifications structurelles
    assert g.no_peeps <= 208
    living_idx = {i for i, _ in g.living()}
    stray = [i for i, v in enumerate(g.map.who) if v and (v - 1) not in living_idx]
    print("map_who pointant un peep mort :", stray[:10], "(%d)" % len(stray))
    occ = [i for i, v in enumerate(g.map.who) if v]
    print("cases occupées: %d, cases modifiées de blk: %d, bk2: %d"
          % (len(occ),
             sum(1 for v in g.map.blk if v != BLK_FLAT),
             sum(1 for v in g.map.bk2 if v != 0)))


if __name__ == "__main__":
    sys.exit(main())
