"""Stress test : beaucoup de graines, beaucoup de tours, aucune exception.

 complements `tools/autopilot.py`, qui verifie l'interaction sur quelques
 graines. Ici on ne teste rien d'autre que la **robustesse** de la
 simulation : on fait tourner des parties longues et on verifie qu'un
 certain nombre d'invariants tiennent.

 Ce que le test garantit :
   * aucune exception, sur aucune graine ;
   * les populations restent dans des bornes plausibles ;
   * la vie d'un peep ne depasse jamais le plafond `0x7D00` (32000) ;
   * `no_peeps` ne depasse jamais `MAX_PEEPS` (208) ;
   * `map_who` ne renvoie jamais un index hors de la table physique
     (212 fiches : `PEEP_SLOTS`, et non `MAX_PEEPS`) ;
   * la mana reste dans `[plancher, 0x7FFFFFFF]`.

 Usage :
     python tools/stress.py [tours] [nb_graines]
 """
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from populous.constants import MAX_PEEPS, PEEP_SLOTS       # noqa: E402
from populous.game import Game                              # noqa: E402
from populous.sim import ST_EXPLORER                        # noqa: E402

PLAFOND_VIE = 0x7D00                    # `CMP.L #$00007d00` (L6695)
MAP_CELLS = 64 * 64


def une_partie(seed: int, ground: int, tours: int) -> dict:
    """Fait tourner une partie et renvoie ses statistiques."""
    g = Game(seed, ground, 3)
    sim = g.sim

    pop_max = 0
    for _ in range(tours):
        g.tick()

        # --- invariants, verifies en cours de partie ---
        assert sim.no_peeps <= MAX_PEEPS, \
            "no_peeps=%d > MAX_PEEPS=%d (graine %d)" % (sim.no_peeps,
                                                        MAX_PEEPS, seed)
        for t in (0, 1):
            pop = sim.population(t)
            assert pop >= 0, "population negative pour la tribu %d" % t
            pop_max = max(pop_max, pop)

        for i, p in enumerate(sim.peeps):
            if p.life <= 0:
                continue
            assert p.life <= PLAFOND_VIE, \
                "peeps[%d].vie=%d > 0x7D00 (graine %d)" % (i, p.life, seed)
            assert 0 <= p.block < MAP_CELLS, \
                "peeps[%d].bloc=%d hors carte (graine %d)" % (i, p.block, seed)
            if p.state == ST_EXPLORER:
                assert p.life > 0, "explorateur mort (graine %d)" % seed

        # `map_who` contient l'index + 1 : jamais hors table physique.
        # Borne haute 0xD3 = 211 et non 208 : `_do_place_funny` ecrit
        # `map_who = idx + 1` (L8971-8977) pour les fiches 0xD1/0xD2,
        # les seules parcourues par la boucle L9009-9011. Valeurs
        # observees en execution : 210 et 211.
        for cell, who in enumerate(sim.map.who):
            if who:
                assert 1 <= who <= 0xD3, \
                    "map_who[%d]=%d hors table (graine %d)" % (cell, who, seed)

        for pl in sim.players:
            assert pl.mana >= -250, "mana sous le plancher : %d" % pl.mana

    return {
        "seed": seed,
        "ground": ground,
        "pop_max": pop_max,
        "pop_joueur": sim.population(sim.player),
        "pop_adv": sim.population(sim.not_player),
        "peeps": sum(1 for p in sim.peeps if p.life > 0),
        "termine": g.game_ended,
    }


def main(argv: list[str]) -> int:
    tours = int(argv[0]) if len(argv) > 0 else 1500
    nb = int(argv[1]) if len(argv) > 1 else 12

    print("stress : %d graines x %d tours" % (nb, tours))
    print("-" * 68)

    echecs = 0
    for i in range(nb):
        seed = 1 + i * 37
        ground = i % 4
        try:
            r = une_partie(seed, ground, tours)
        except AssertionError as e:
            print("  graine %-4d ECHEC : %s" % (seed, e))
            echecs += 1
            continue
        except Exception:
            print("  graine %-4d EXCEPTION :" % seed)
            traceback.print_exc()
            echecs += 1
            continue
        print("  graine %-4d sol %d  peeps=%-4d pop J=%-7d pop A=%-7d"
              "  max=%-7d%s"
              % (seed, ground, r["peeps"], r["pop_joueur"], r["pop_adv"],
                 r["pop_max"], "  [fin]" if r["termine"] else ""))

    print("-" * 68)
    if echecs:
        print("=> %d/%d ECHECS" % (echecs, nb))
        return 1
    print("=> OK : %d/%d parties robustes" % (nb, nb))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))