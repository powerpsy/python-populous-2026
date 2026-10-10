# -*- coding: utf-8 -*-
"""Controle independant de `PowerEngine.devil_effect` (L9300-9522).

Reference ecrite en labels depuis le listing, puis comparaison au port :
``(act, p1, p2, queued, t12)`` + les appels de ``_do_computer_effect`` +
le label de sortie.

Trois points structurels que ce controle porte, et que la Phase 60 a
transcrits :

* **seule une branche qui reussit rend la main** : L9317/L9326/L9343
  pointent vers ``LAB_44DE4`` (le ``BTST #7`` suivant), pas vers
  l'epilogue ``LAB_44D76`` ;
* le bloc **``act = 4``** (``LAB_44ED8``, L9419-9491, l'inondation), dit
  inatteignable jusqu'a la Phase 60 ;
* ``CMPI.B #$01,(A0)`` (L9503) = ``peeps[p26].state == 1``.

``_do_computer_effect`` (L9526-9597) est **neutralise** : ce controle
porte sur la structure de ``_devil_effect``, pas sur le placement de
l'effet.

Les six ``BTST`` portent sur un octet memorise ; sur 68000 le mot est
gros-boutiste, donc ``BTST #n,(W)`` lit les bits 15-8 et ``BTST #n,(W+1)``
les bits 7-0. D'ou ``L9316 -> $0100`` (seul test a porter sur ``(-6,A5)``)
et ``L9349..L9505 -> $0080/$0020/$0040/$0010/$0008`` (``(-5,A5)``).

Le port est **paye** en dehors des tests : on ne relit pas ``powers.py``
pour construire la reference.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from populous.constants import PEEP_SLOTS  # noqa: E402
from populous.powers import PowerEngine  # noqa: E402

# --- seuils, reconstitues des ADD.L du listing -------------------------------
TH_QUAKE = 80_000 + 0x3E7            # L9322-9323  LAB_51894 + $3E7 = 80 999
TH_FLOOD = 40_000 + 0x7CF            # L9355-9356  LAB_51890 + $7CF = 41 999
TH_MAGNET = 7_500 + 0x1F4            # L9387-9388  LAB_51888 + $1F4 =  7 999
TH_VPC = 10_000 + 0x1F4              # L9404-9405  LAB_5188C + $1F4 = 10 499
TH_ATTACK = 5_000 + 0x1F4            # L9424-9425  LAB_51884 + $1F4 =  5 499
                                       # L9497-9498  LAB_51880 + $1F4
VIE_AIMANT = 0x0BB8                  # L9381 CMPI.W #$0bb8
ETAT_VILLAGER = 1                     # L9503 CMPI.B #$01,(A0)

KEYS = ("act", "p1", "p2", "queued", "t12")

CHEMINS = set([
    "44D76-epilogue", "44DE2-quake", "44E1A-flood", "44E88-aimant",
    "44ED4-vpc", "44FC6-act4", "4500E-act3", "45026-rien",
])

N_ALEA = 600


def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def table(defaut, **cells):
    """Table de ``PEEP_SLOTS`` entrees, ``iNN`` force la case NN."""
    t = [defaut] * PEEP_SLOTS
    for k, v in cells.items():
        t[int(k[1:])] = v
    return t


def cas(**kw):
    """Entree par defaut : rien n'est ecrit, les sorties partent sentinelle."""
    e = dict(tribe=0, queued=0, power_mask=0, mana=0,
             pop_self=0, pop_other=0, magnet_self=0, magnet_other=0,
             p26=-1, t12=0, t1a=0, t18=0,
             act=0x7F, p1=0x5A, p2=0x6B,
             vie=None, etat=None, bloc=None)
    e.update(kw)
    if e["bloc"] is None:
        e["bloc"] = [0] * PEEP_SLOTS
        e["bloc"][0] = 0x0521             # p1 = $21, p2 = $14
    if e["vie"] is None:
        e["vie"] = [0] * PEEP_SLOTS
    if e["etat"] is None:
        e["etat"] = [0] * PEEP_SLOTS
    return e


# ---------------------------------------------------------------------------
# Reference : _devil_effect (L9300-9522) en labels
# ---------------------------------------------------------------------------
def reference(e):
    o = {"act": e["act"], "p1": e["p1"], "p2": e["p2"],
         "queued": e["queued"], "t12": e["t12"]}
    effets = []
    m = e["power_mask"]
    mana = e["mana"]
    vie, etat, bloc = e["vie"], e["etat"], e["bloc"]
    i1 = i2 = -1
    pc = "L9308"

    while True:
        # ---------------------------------------------------------- entree
        if pc == "L9308":                      # TST.W (8,A2)
            pc = "LAB_44D76" if e["queued"] else "L9315"
        elif pc == "LAB_44D76":                # MOVEA/UNLK/RTS
            return o, effets, "44D76-epilogue"

        # ------------------------------------------------- (1) le seisme
        elif pc == "L9315":                    # MOVE.W ($E,A2),(-6,A5)
            pc = "L9316"
        elif pc == "L9316":                    # BTST #0,(-6,A5) -> $0100
            pc = "L9318" if (m & 0x0100) else "LAB_44DE4"
        elif pc == "L9318":                    # mana > 80 999 ?
            pc = "L9327" if mana > TH_QUAKE else "LAB_44DE4"
        elif pc == "L9327":                    # good_pop[tribe] > [1-tribe]
            pc = "L9344" if e["pop_self"] > e["pop_other"] else "LAB_44DE4"
        elif pc == "L9344":                    # L9344-9347
            o.update(act=0x0E, p2=3, queued=1)
            return o, effets, "44DE2-quake"

        # ------------------------------------------------- (2) le deluge
        elif pc == "LAB_44DE4":
            pc = "L9349"
        elif pc == "L9349":                    # BTST #7,(-5,A5) -> $0080
            pc = "L9351" if (m & 0x0080) else "LAB_44E1E"
        elif pc == "L9351":                    # mana > 41 999 ?
            pc = "L9360" if mana > TH_FLOOD else "LAB_44E1E"
        elif pc == "L9360":                    # L9360-9363
            o.update(act=0x0E, p2=4, queued=1)
            return o, effets, "44E1A-flood"

        # -------------------------------------------- (3) l'aimant (mana)
        elif pc == "LAB_44E1E":
            pc = "L9365"
        elif pc == "L9365":                    # BTST #5,(-5,A5) -> $0020
            pc = "L9367" if (m & 0x0020) else "LAB_44E8C"
        elif pc == "L9367":                    # TST.W _magnet[tribe]
            pc = "L9377" if e["magnet_self"] != 0 else "LAB_44E8C"
        elif pc == "L9377":                    # life > $0BB8 ?
            pc = "L9383" if vie[e["magnet_self"] - 1] > VIE_AIMANT \
                else "LAB_44E8C"
        elif pc == "L9383":                    # mana > 7 999 ?
            pc = "L9392" if mana > TH_MAGNET else "LAB_44E88"
        elif pc == "L9392":                    # L9392-9394
            o.update(act=0x0E, p2=5, queued=1)
            pc = "LAB_44E88"
        elif pc == "LAB_44E88":                # L9395-9396 : retour systematique
            return o, effets, "44E88-aimant"

        # -------------------------------------------- (4) l'effet vise p26
        elif pc == "LAB_44E8C":
            pc = "L9398"
        elif pc == "L9398":                    # TST.L ($26,A2)
            pc = "L9400" if e["p26"] >= 0 else "LAB_45026"
        elif pc == "L9400":                    # mana > 10 499 ?
            pc = "L9409" if mana > TH_VPC else "LAB_44ED8"
        elif pc == "L9409":                    # BTST #6,(-5,A5) -> $0040
            pc = "L9411" if (m & 0x0040) else "LAB_44ED8"
        elif pc == "L9411":                    # L9411-9418
            o.update(act=0x06, queued=1, t12=0)
            effets.append((0x06, e["tribe"]))
            return o, effets, "44ED4-vpc"

        # --------------------------------------- (5) le bloc act = 4
        elif pc == "LAB_44ED8":
            pc = "L9420"
        elif pc == "L9420":                    # mana > 5 499 ?
            pc = "L9429" if mana > TH_ATTACK else "LAB_44FCA"
        elif pc == "L9429":                    # BTST #4,(-5,A5) -> $0010
            pc = "L9431" if (m & 0x0010) else "LAB_44FCA"
        elif pc == "L9431":                    # t12 >= t1a ?
            pc = "LAB_44F16" if e["t12"] >= e["t1a"] else "L9434"
        elif pc == "L9434":                    # BTST #3,(-5,A5) -> $0008
            pc = "LAB_44FCA" if (m & 0x0008) else "LAB_44F16"
        elif pc == "LAB_44F16":
            pc = "L9437"
        elif pc == "L9437":                    # t12 <= t18 ?
            pc = "LAB_44F2A" if e["t12"] <= e["t18"] else "L9440"
        elif pc == "L9440":                    # BTST #6,(-5,A5) -> $0040
            pc = "LAB_44FCA" if (m & 0x0040) else "LAB_44F2A"
        elif pc == "LAB_44F2A":                # L9443-9462 : les deux index
            i1 = e["magnet_other"] - 1         # magnet[1-tribu] - 1
            i2 = e["magnet_self"] - 1          # magnet[tribu]   - 1
            pc = "LAB_44FCA" if i1 == -1 else "L9465"
        elif pc == "L9465":                    # L9465-9475
            pc = "LAB_44F90" if (i2 == -1 or vie[i1] > vie[i2]) \
                else "LAB_44FCA"
        elif pc == "LAB_44F90":                # L9477-9491
            o["t12"] += 1
            o["act"] = 0x04
            blk = bloc[i1]
            o["p1"] = blk & 0x3F
            o["p2"] = s16(blk) >> 6
            return o, effets, "44FC6-act4"

        # --------------------------------------- (6) le bloc act = 3
        elif pc == "LAB_44FCA":
            pc = "L9493"
        elif pc == "L9493":                    # mana > 5 499 ?
            pc = "L9502" if mana > TH_ATTACK else "LAB_45026"
        elif pc == "L9502":                    # CMPI.B #$01,(A0)
            pc = "L9505" if etat[e["p26"]] == ETAT_VILLAGER else "LAB_45026"
        elif pc == "L9505":                    # BTST #3,(-5,A5) -> $0008
            pc = "L9507" if (m & 0x0008) else "LAB_45026"
        elif pc == "L9507":                    # t12 < t1a ?
            pc = "LAB_4500E" if e["t12"] < e["t1a"] else "L9510"
        elif pc == "L9510":                    # MOVE.W (-6,A5) / AND #$0050
            pc = "LAB_4500E" if (m & 0x0050) == 0 else "LAB_45026"
        elif pc == "LAB_4500E":                # L9514-9520
            o["act"] = 0x03
            effets.append((0x03, e["tribe"]))
            o["queued"] = 1
            o["t12"] += 1
            return o, effets, "4500E-act3"     # L9521-9522 : BRA l'epilogue
        elif pc == "LAB_45026":                # L9521-9522 : retour
            return o, effets, "45026-rien"

        else:
            raise AssertionError("label inconnu %r" % pc)


# ---------------------------------------------------------------------------
# Etat synthetique + pilotage du port
# ---------------------------------------------------------------------------
class FauxJeu:
    """``PowerEngine`` n'a besoin que de ``.sim`` ; pas de rendu ici."""

    def __init__(self, sim):
        self.sim = sim


def run(e, eng, appels):
    tribe = e["tribe"]
    sim = eng.g.sim
    peeps = sim.peeps
    for i in range(PEEP_SLOTS):
        p = peeps[i]
        p.life = e["vie"][i]
        p.state = e["etat"][i]
        p.block = e["bloc"][i]
    pl = sim.players[tribe]
    pl.mana = e["mana"]
    pl.magnet = e["magnet_self"]
    pl.pop = e["pop_self"]
    po = sim.players[1 - tribe]
    po.magnet = e["magnet_other"]
    po.pop = e["pop_other"]
    st = sim.stats[tribe]
    st.act = e["act"]
    st.p1 = e["p1"]
    st.p2 = e["p2"]
    st.queued = e["queued"]
    st.t12 = e["t12"]
    st.t1a = e["t1a"]
    st.t18 = e["t18"]
    st.p26 = e["p26"]
    st.power_mask = e["power_mask"]
    del appels[:]
    eng.devil_effect(tribe)
    obs = tuple(getattr(st, k) for k in KEYS)
    return obs, list(appels)


def alea(rng):
    return cas(
        tribe=rng.randrange(2),
        queued=rng.choice((0, 0, 0, 1)),
        power_mask=rng.randrange(0x10000),
        mana=rng.randrange(0, 120_000),
        pop_self=rng.randrange(0, 400),
        pop_other=rng.randrange(0, 400),
        magnet_self=rng.randrange(0, PEEP_SLOTS + 1),
        magnet_other=rng.randrange(0, PEEP_SLOTS + 1),
        p26=rng.randrange(-1, PEEP_SLOTS),
        t12=rng.randrange(0, 20),
        t1a=rng.randrange(0, 3),
        t18=0,
        act=rng.randrange(0, 16),
        p1=rng.randrange(0, 64),
        p2=rng.randrange(-4, 70),
        vie=[rng.randrange(0, 0x3000) for _ in range(PEEP_SLOTS)],
        etat=[rng.choice((1, 1, 1, 2, 4, 16)) for _ in range(PEEP_SLOTS)],
        bloc=[rng.randrange(0, 0x1000) for _ in range(PEEP_SLOTS)],
    )


# ---------------------------------------------------------------------------
# Cas cibles
# ---------------------------------------------------------------------------
CASES = [
    # un par chemin de sortie
    ("epilogue-queued", cas(queued=1, power_mask=0xFFFF, p26=2)),
    ("quake", cas(power_mask=0x0100, mana=TH_QUAKE + 1,
                  pop_self=5, pop_other=4, p26=2)),
    ("chute1-2_mana", cas(power_mask=0x0180, mana=TH_FLOOD + 1, p26=2)),
    ("chute1-2_pop", cas(power_mask=0x0180, mana=TH_QUAKE + 1,
                         pop_self=0, pop_other=9, p26=2)),
    ("flood", cas(power_mask=0x0080, mana=TH_FLOOD + 1, p26=2)),
    ("aimant_act5", cas(power_mask=0x0020, mana=TH_MAGNET + 1,
                        magnet_self=1, p26=2, vie=table(0, i0=0x0BB9))),
    ("aimant_retour", cas(power_mask=0x0020, mana=TH_MAGNET,
                          magnet_self=1, p26=2, vie=table(0, i0=0x0BB9))),
    ("chute3-4_vie", cas(power_mask=0x0060, mana=TH_VPC + 1,
                         magnet_self=1, p26=2)),
    ("vpc", cas(power_mask=0x0040, mana=TH_VPC + 1, p26=2)),
    ("p26_nul", cas(power_mask=0x0040, mana=TH_VPC + 1, p26=-1)),
    ("act4_sans_aimant_propre", cas(power_mask=0x0018, mana=TH_ATTACK + 1,
                                    magnet_other=1, magnet_self=0, p26=2)),
    ("act4_vies", cas(power_mask=0x0010, mana=TH_ATTACK + 1,
                      magnet_other=1, magnet_self=2, p26=2,
                      vie=table(0, i0=100, i1=10))),
    ("act4_vies_inverse", cas(power_mask=0x0010, mana=TH_ATTACK + 1,
                              magnet_other=1, magnet_self=2, p26=2,
                              vie=table(0, i0=10, i1=100),
                              etat=table(0, i2=1))),
    ("act4_i1_nul", cas(power_mask=0x0010, mana=TH_ATTACK + 1,
                        magnet_other=0, magnet_self=1, p26=2,
                        etat=table(0, i2=1))),
    ("act4_ferme_bit3", cas(power_mask=0x0018, mana=TH_ATTACK + 1,
                            t12=0, t1a=1, t18=2, p26=2)),
    ("act3", cas(power_mask=0x0008, mana=TH_ATTACK + 1, t12=0, t1a=1,
                 p26=2, etat=table(0, i2=1))),
    ("act3_bloque_50", cas(power_mask=0x0058, mana=TH_ATTACK + 1,
                           t12=0, t1a=0, t18=0, magnet_other=0, p26=2,
                           etat=table(0, i2=1))),
    ("etat_non_villageois", cas(power_mask=0x0008, mana=TH_ATTACK + 1,
                                t12=0, t1a=1, p26=2, etat=table(0, i2=2))),
    ("masque_nul", cas(p26=2)),
    ("mana_bas_partout", cas(power_mask=0xFFFF, mana=TH_ATTACK, p26=2,
                             magnet_self=1, pop_self=9, pop_other=0,
                             vie=table(0, i0=0x0BB9))),
]


def main():
    # SDL en tete : l'import de `populous.game` initialise pygame.
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    # `populous.sim.Game` est la simulation ; `populous.game.Game` est
    # l'interface. On pilote la premiere, seule porteuse de `.stats`.
    from populous.sim import Game

    appels = []

    def neutre(self, tribe, st):
        appels.append((st.act, tribe))

    PowerEngine.do_computer_effect = neutre

    g = Game(seed=7)
    eng = PowerEngine(FauxJeu(g))
    rng = random.Random(20261010)

    n = 0
    ok = True
    chemins = set()
    echecs = []

    def verifier(nom, e):
        nonlocal n, ok
        ref, ref_eff, ch = reference(e)
        obs, obs_eff = run(e, eng, appels)
        n += 1
        chemins.add(ch)
        ref_t = tuple(ref[k] for k in KEYS)
        if (ref_t, ref_eff) != (obs, obs_eff):
            ok = False
            if len(echecs) < 6:
                echecs.append((nom, (ref_t, ref_eff, ch), (obs, obs_eff)))

    for nom, e in CASES:
        verifier(nom, e)
    for k in range(N_ALEA):
        verifier("alea %d" % k, alea(rng))

    manquants = sorted(CHEMINS - chemins)
    if manquants:
        ok = False

    print("check_devil_effect : %d cas - chemins %d/%d%s - %s"
          % (n, len(chemins & CHEMINS), len(CHEMINS),
             (" manquants %s" % ",".join(manquants)) if manquants else "",
             "OK" if ok else "ECART"))
    for nom, ref, obs in echecs:
        print("  %-24s ref=%s" % (nom, ref))
        print("  %-24s obs=%s" % ("", obs))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
