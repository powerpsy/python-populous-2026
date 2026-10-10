# -*- coding: utf-8 -*-
"""Controle independant de `Sim.place_people` et des codes 7..10.

Deux objets, un seul fichier :

1. **`_place_people` (L6982-7087)** - reference en labels ecrite depuis le
   listing. Ce controle nait de la Phase 61 : `frame` valait ``0`` au lieu
   de ``$00FF`` (L7053), `weapons` valait ``0`` au lieu de ``1`` (L7065),
   l'ecriture `_magnet[tribu] = j + 1` (L7070-7078) manquait, et l'appel
   final `_set_frame` (L7080-7086) n'etait pas transcrit - sans lui,
   ``$00FF`` laisserait le peep a l'age 10 (``FRAME_AGE = $20``, d'ou
   ``age = 255 - 32``). On espionne donc `set_frame` **et**
   `zero_population` : comparer le resultat final ne suffirait pas,
   ``frame = 0`` sans l'appel donne exactement le meme octet.

2. **`_get_message` codes 7..10 (L18017-18046)** - la table `LAB_4B81A`
   (L18210-18213) conduit les quatre codes a un `_place_people(tribu, x, y,
   magnet)`. Le port n'avait aucune branche : les icones ``(0, 0)`` et
   ``(1, 1)`` de la palette armaient ``st.act`` sans jamais rien executer.

Ecart de contrat : l'asm rend le ``D0`` de `_set_frame` (0/1), le port
l'index du peep cree - compte a part.

Le port est **paye** en dehors des tests : on ne relit pas `sim.py` pour
construire la reference.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from populous.constants import (  # noqa: E402
    ACT_PLACE0, ACT_PLACE0_M, ACT_PLACE1, ACT_PLACE1_M, MAX_PEEPS,
)
from populous.powers import PowerEngine  # noqa: E402

ST_EXPLORER = 0x02                    # L7049 `MOVE.B #$02,(_peeps)`
VIE_INIT = 0x2D                       # L7024 `MOVE.W #$002D,(4,A0,D0.L)`
FRAME_INIT = 0x00FF                   # L7053 `MOVE.W #$00ff,(LAB_53020,...)`

CHAMPS = ("w6", "life", "block", "tribe", "state", "frame", "offspring",
          "prev_block", "weapons", "target")

N_ALEA = 492


# ---------------------------------------------------------------------------
# 1. _place_people (L6982-7087) en labels
# ---------------------------------------------------------------------------
def reference(e):
    """`_place_people` reecrit en labels depuis le listing."""
    t = e["tribe"]
    mag_own = e["mag0"] if t == 0 else e["mag1"]
    o = {"pleine": False, "zero": None, "set_frame": False,
         "no_peeps": e["no_peeps"], "magnet": mag_own,
         "who": e["who_block"], "j": None, "champs": None, "retour": None}
    pc = "L6984"

    while True:
        if pc == "L6984":                     # CMPI.W #$00d0 / BLT
            pc = "L6990" if e["no_peeps"] < MAX_PEEPS else "LAB_43170"
        elif pc == "LAB_43170":               # L6986-6988 : sortie nue
            o["pleine"] = True
            return o

        elif pc == "L6990":                   # TST.W ($E,A5) - arg magnet
            pc = "L6998" if e["magnet_arg"] else "LAB_431BE"
        elif pc == "L6998":                   # TST.W _magnet[tribu]
            pc = "L7004" if mag_own != 0 else "LAB_431BE"
        elif pc == "L7004":                   # L7004-7013 : l'ancien est tue
            o["j"] = mag_own - 1
            o["zero"] = mag_own - 1
            pc = "L7019"
        elif pc == "LAB_431BE":               # L7014-7016 : slot neuf
            o["j"] = e["no_peeps"]
            o["no_peeps"] = e["no_peeps"] + 1
            pc = "L7019"

        elif pc == "L7019":                   # L7019-7069 : les ecritures
            j = o["j"]
            o["champs"] = {
                "w6": 0,                      # L7019-7022 CLR.W (6,...)
                "life": VIE_INIT,             # L7023-7026
                "block": e["block"],          # L7027-7033
                "tribe": t,                   # L7042-7045
                "state": ST_EXPLORER,         # L7046-7049
                "frame": FRAME_INIT,          # L7050-7053
                "offspring": 1,               # L7054-7057
                "prev_block": 0,              # L7058-7061 CLR.W ($A,...)
                "weapons": 1,                 # L7062-7065 MOVE.B #$01,(3,...)
                "target": 0,                  # L7066-7069 CLR.L (14,...)
            }
            o["who"] = j + 1                  # L7034-7041
            pc = "L7070"

        elif pc == "L7070":                   # TST.W ($E,A5) / BEQ
            if e["magnet_arg"]:               # L7071-7078 _magnet[t] = j+1
                o["magnet"] = o["j"] + 1
            pc = "L7080"

        elif pc == "L7080":                   # L7080-7086 : _set_frame(peep)
            o["set_frame"] = True
            # state vient d'etre ecrit a $02 et life vaut $002D : seule la
            # branche ST_EXPLORER de `_set_frame` (L5730-5743) est
            # atteinte, et elle n'ecrit que (12,peep) = frame.
            old = o["champs"]["frame"]
            frame = (old + 1) & 0xFFFF        # L5732-5733
            ret = 0
            if old >= 7:                      # L5734 `CMP.W #$0007,D0`
                frame = 0                     # L5736 `CLR.W (12,A2)`
                ret = 1                       # L5737 `MOVEQ #1,D0`
            o["champs"]["frame"] = frame
            o["retour"] = ret
            return o

        else:
            raise AssertionError("label inconnu %r" % pc)


# ---------------------------------------------------------------------------
# etat synthetique
# ---------------------------------------------------------------------------
class FauxJeu:
    """``PowerEngine`` n'a besoin que de ``.sim`` ; pas de rendu ici."""

    def __init__(self, sim):
        self.sim = sim


def cas(**kw):
    e = dict(no_peeps=0, tribe=0, block=0, mag0=0, mag1=0, magnet_arg=0,
             who_block=0,
             vie=None, etat=None, ptribe=None, pblock=None, pw6=None,
             pframe=None, ptarget=None, pspawn=None, pres=None)
    e.update(kw)
    for k, d in (("vie", 0x100), ("etat", 2), ("ptribe", 0), ("pblock", 0),
                 ("pw6", 0), ("pframe", 0), ("ptarget", -1), ("pspawn", 0),
                 ("pres", 0)):
        if e[k] is None:
            e[k] = [d] * MAX_PEEPS
    return e


def appliquer(g, e):
    g.no_peeps = e["no_peeps"]
    g.players[0].magnet = e["mag0"]
    g.players[1].magnet = e["mag1"]
    g.map.who[e["block"]] = e["who_block"]
    for i in range(MAX_PEEPS):
        p = g.peeps[i]
        p.life = e["vie"][i]
        p.state = e["etat"][i]
        p.tribe = e["ptribe"][i]
        p.block = e["pblock"][i]
        p.w6 = e["pw6"][i]
        p.frame = e["pframe"][i]
        p.target = e["ptarget"][i]
        p.spawn_block = e["pspawn"][i]
        p.make_level_res = e["pres"][i]


def alea(rng):
    return cas(
        no_peeps=rng.choice((0, 1, 5, 100, 206, 207, 207, 208)),
        tribe=rng.randrange(2),
        block=rng.randrange(0, 0x1000),
        mag0=rng.randrange(0, MAX_PEEPS + 1),
        mag1=rng.randrange(0, MAX_PEEPS + 1),
        magnet_arg=rng.choice((0, 0, 1)),
        who_block=rng.randrange(0, 0x100),
        vie=[rng.randrange(0, 0x3000) for _ in range(MAX_PEEPS)],
        etat=[rng.choice((1, 2, 2, 4, 8, 0x10)) for _ in range(MAX_PEEPS)],
        ptribe=[rng.randrange(2) for _ in range(MAX_PEEPS)],
        pblock=[rng.randrange(0, 0x1000) for _ in range(MAX_PEEPS)],
        pw6=[rng.randrange(MAX_PEEPS) for _ in range(MAX_PEEPS)],
        pframe=[rng.randrange(0, 0x70) for _ in range(MAX_PEEPS)],
        ptarget=[rng.randrange(-1, MAX_PEEPS) for _ in range(MAX_PEEPS)],
        pspawn=[rng.randrange(0, 0x1000) for _ in range(MAX_PEEPS)],
        pres=[rng.randrange(0, 8) for _ in range(MAX_PEEPS)],
    )


CASES = [
    ("table_pleine", cas(no_peeps=MAX_PEEPS, tribe=0, block=7, magnet_arg=1,
                         mag0=3)),
    ("neuf_simple", cas(no_peeps=0, tribe=0, block=0x123, magnet_arg=0)),
    ("neuf_dernier_slot", cas(no_peeps=MAX_PEEPS - 1, tribe=1, block=0x3FF)),
    ("aimant_absent", cas(no_peeps=4, tribe=0, mag0=0, magnet_arg=1, block=99)),
    ("aimant_reutilise", cas(no_peeps=0, tribe=0, mag0=5, magnet_arg=1,
                             block=64)),
    ("aimant_preconstruit", cas(no_peeps=7, tribe=1, mag1=3, magnet_arg=1,
                                block=128)),
    ("aimant_sans_arg", cas(no_peeps=0, tribe=0, mag0=7, magnet_arg=0,
                            block=12)),
    ("aimant_max", cas(no_peeps=0, tribe=1, mag1=MAX_PEEPS, magnet_arg=1,
                       block=5)),
    ("aimant_1", cas(no_peeps=3, tribe=0, mag0=1, magnet_arg=1, block=200)),
]


def main():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    from populous.sim import Game

    zeroes, frames = [], []
    orig_zero = Game.zero_population
    orig_frame = Game.set_frame

    def spy_zero(self, i):
        zeroes.append(i)
        return orig_zero(self, i)

    def idx_of(self, p):
        for i in range(MAX_PEEPS):
            if self.peeps[i] is p:
                return i
        return None

    def spy_frame(self, p):
        frames.append(idx_of(self, p))
        return orig_frame(self, p)

    Game.zero_population = spy_zero
    Game.set_frame = spy_frame

    g = Game(seed=7)
    eng = PowerEngine(FauxJeu(g))
    rng = random.Random(20261011)

    n = 0
    ok = True
    echecs = []
    declares = set([
        "target (CLR.L $0 dans l'asm, -1 dans le port)",
        "spawn_block/make_level_res (jamais ecrits par L6982-7087)",
        "valeur de retour (D0 de _set_frame vs index du peep)",
    ])

    def verifier(nom, e):
        nonlocal n, ok
        ref = reference(e)
        appliquer(g, e)
        del zeroes[:]
        del frames[:]
        ret = g.place_people(e["tribe"], e["block"], e["magnet_arg"])
        n += 1

        obs_scal = {
            "pleine": ret is None,
            "zero": zeroes[0] if zeroes else None,
            "set_frame": frames,
            "no_peeps": g.no_peeps,
            "magnet": g.players[e["tribe"]].magnet,
            "who": g.map.who[e["block"]],
            "j": ret,
        }
        for k in ("pleine", "zero", "no_peeps", "magnet", "who", "j"):
            if ref[k] != obs_scal[k]:
                ok = False
                if len(echecs) < 6:
                    echecs.append((nom, k, ref[k], obs_scal[k]))

        voulu = [ret] if ret is not None else []
        if obs_scal["set_frame"] != voulu:
            ok = False
            if len(echecs) < 6:
                echecs.append((nom, "set_frame", voulu,
                               obs_scal["set_frame"]))

        if ref["champs"] is not None and ret is not None:
            p = g.peeps[ret]
            for f in CHAMPS:
                if f == "target":
                    continue                       # ecart declare
                got = getattr(p, f)
                if ref["champs"][f] != got:
                    ok = False
                    if len(echecs) < 6:
                        echecs.append((nom, f, ref["champs"][f], got))

    for nom, e in CASES:
        verifier(nom, e)
    for k in range(N_ALEA):
        verifier("alea %d" % k, alea(rng))

    # ---- les deux octets qui motivent la Phase 61 ---------------------
    appliquer(g, cas(no_peeps=0, tribe=0, block=1))
    del frames[:]
    g.place_people(0, 1, 0)
    p = g.peeps[0]
    if (p.frame, p.weapons, frames) != (0, 1, [0]):
        ok = False
        echecs.append(("post-condition", "frame/weapons/set_frame",
                       (0, 1, [0]), (p.frame, p.weapons, frames)))

    # ---- 2. codes 7..10 : table LAB_4B81A -----------------------------
    places = []
    orig_place = Game.place_people

    def spy_place(self, tribe, block, magnet):
        places.append((tribe, block, magnet))
        return orig_place(self, tribe, block, magnet)

    Game.place_people = spy_place
    n_disp = 0
    attendu = {ACT_PLACE0: (0, 0), ACT_PLACE1: (1, 0),
               ACT_PLACE0_M: (0, 1), ACT_PLACE1_M: (1, 1)}
    for act in sorted(attendu):
        t_voulu, m_voulu = attendu[act]
        for x, y in ((0, 0), (63, 63), (17, 42), (1, 62)):
            del places[:]
            st = g.stats[0]
            st.act, st.p1, st.p2 = act, x, y
            got = eng.dispatch(0, act, x, y)
            n_disp += 1
            voulu = [(t_voulu, (y << 6) | x, m_voulu)]
            if places != voulu or got is not True or st.act != 0:
                ok = False
                if len(echecs) < 6:
                    echecs.append(("dispatch act=%d (%d,%d)" % (act, x, y),
                                   "appels/retour/act",
                                   (voulu, True, 0),
                                   (places, got, st.act)))
    Game.place_people = orig_place

    print("check_place : %d cas _place_people + %d cas dispatch - %s"
          % (n, n_disp, "OK" if ok else "ECART"))
    print("  ecarts declares : %d (%s)" % (len(declares),
                                           "; ".join(sorted(declares))))
    for nom, champ, ref, obs in echecs:
        print("  %-26s %-18s ref=%r obs=%r" % (nom, champ, ref, obs))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
