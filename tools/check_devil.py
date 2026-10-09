# -*- coding: utf-8 -*-
"""Controle d'execution de ``_set_devil_magnet`` (L9601-9897).

Deux ecritures independantes du meme code :

* ``reference(e)`` - une **reecriture du listing faite ici**, exprimee comme
  le desassemblage : des labels (``L9611``, ``LAB_45196``, ...) et des sauts
  explicites, pas des ``if`` imbriques. Aucun code n'est partage avec
  ``populous/``.
* ``PowerEngine.set_devil_magnet`` - le port.

On construit des etats de tribu au hasard (plusieurs centaines) plus un cas
cible par chemin de sortie, on applique les deux, et on compare les six
champs que la routine peut ecrire : ``act``, ``p1``, ``p2``, ``queued``,
``t1c``, ``t1e``.

Trois points sont verifies a part :

1. ``DIVU #$5A`` + ``SWAP`` (L9622-9623) : le registre contient le **reste**
   de la division, donc ``game_turn % 90`` et pas ``game_turn // 90`` ;
2. ``BLT LAB_4515A`` (L9616-9617) : l'action directe est le cas
   ``total < seuil``, et non l'inverse ;
3. ``BEQ LAB_453F2`` (L9798) : quand ``releve`` est vrai mais que le bit
   ``$400`` est nul, on **retourne** - LAB_453F6 n'est pas atteint.

Les deux ecarts assumes du port (pointeur nul, fiche hors table) sont
reperes par ``reference`` et comptes separement : le port et la reference
appliquent la meme convention, ``block = 0``.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from populous.powers import PowerEngine          # noqa: E402
from populous.sim import Game                    # noqa: E402

PEEP_SLOTS = 212
CHAMPS = ("act", "p1", "p2", "queued", "t1c", "t1e")

# En quoi l'entree franchit le test de periode (L9611-9627) :
#   seuil = 0*2+15 = 15 ; total 16+4 = 20 >= 15
#   reste = 100 % 90 = 10 >= threshold+10 = 10   -> LAB_45196
PASSE = dict(threshold=0, towns=16, castles=4, game_turn=100)


def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


# ---------------------------------------------------------------------------
# Reference independante : labels et sauts, ecrits a partir du listing.
# ---------------------------------------------------------------------------
def reference(e):
    """Retourne ``(champs, ecarts, chemin)`` pour l'entree ``e``."""
    t = dict((c, e[c]) for c in CHAMPS)
    ecarts = []
    env = {}

    def releve():
        t["act"] = 0x0E
        t["p2"] = 0x01
        t["p1"] = 0
        t["queued"] = 1

    def amener(x):
        t["act"] = 0x05
        t["p1"] = x & 0x3F
        t["p2"] = s16(x) >> 6
        t["queued"] = 1

    def fiche(idx, quoi):
        """Champ `strongest` / `p2a` : un indice, ou le bloc 0 si nul."""
        if idx == -1:
            return 0, "nul"          # ECART : l'asm derobe l'adresse 8
        if not 0 <= idx < PEEP_SLOTS:
            return 0, "hors-table"   # ECART : l'asm lit une fiche hors table
        return e[quoi], None

    pc = "L9611"
    while True:
        if pc == "L9611":
            # L9611-9617 : total = towns+castles, seuil = threshold*2+$0F
            if (e["towns"] + e["castles"]) < e["threshold"] * 2 + 0x0F:
                pc = "L9615A"
            else:
                pc = "L9618"

        elif pc == "L9618":
            # L9618-9623 : DIVU #$5A / SWAP -> le mot bas est le RESTE.
            if e["game_turn"] % 0x5A >= e["threshold"] + 0x0A:
                pc = "LAB_45196"
            else:
                pc = "L9615A"

        elif pc == "L9615A":
            # L9628-9643 : le releve de terrain.
            if e["command_own"] == 0:
                t["act"] = 0x0E
                t["p2"] = 0x01
                t["p1"] = 1 + e["rand3"]
                t["queued"] = 1
            return t, ecarts, "4515A"

        elif pc == "LAB_45196":
            # L9604 : SUBA.L A3,A3 ; L9605 : MOVEQ #0,D4 - les deux
            # pointeurs nuls avant les lectures. L9649-9676 : D4 = le peep
            # vise par l'aimant de l'**autre** tribu. L9678-9693 : A3 = le
            # peep vise par l'aimant de **cette** tribu.
            je, jo = e["mag_other"] - 1, e["mag_own"] - 1
            env["pe"] = (je, e["block_other"], e["life_other"]) \
                if 0 <= je < PEEP_SLOTS else None
            if je != -1 and not 0 <= je < PEEP_SLOTS:
                ecarts.append("magnet[autre]-hors-table")
            env["pa"] = (jo, e["block_own"], e["life_own"]) \
                if 0 <= jo < PEEP_SLOTS else None
            if jo != -1 and not 0 <= jo < PEEP_SLOTS:
                ecarts.append("magnet[cette-tribu]-hors-table")
            pc = "L9695"

        elif pc == "L9695":
            # L9695-9709 : A3 nul -> releve si une commande attend.
            if env["pa"] is None:
                if e["command_own"] != 0:
                    releve()
                    t["t1c"] = 0
                return t, ecarts, "4695"
            pc = "LAB_45238"

        elif pc == "LAB_45238":
            # L9710-9718
            _idx, bloc, vie = env["pa"]
            if bloc == t["t1e"] and t["t1c"] != 0:
                t["t1c"] -= 1
            pc = "LAB_45318" if vie >= 0x1770 else "L9720"

        elif pc == "L9720":
            # L9720-9737
            if t["t1c"] == 0:
                pc = "LAB_45298"
            elif e["magto_own"] != t["t1e"]:
                amener(t["t1e"])
                return t, ecarts, "4737"
            else:
                pc = "LAB_452EE"

        elif pc == "LAB_45298":
            # L9740-9762 : nouvelle course, sur `p2a`
            cible, note = fiche(e["p2a_idx"], "p2a")
            if note:
                ecarts.append("p2a-" + note)
            if e["magto_own"] != cible:
                t["act"] = 0x05
                t["p1"] = cible & 0x3F
                t["p2"] = s16(cible) >> 6
                t["t1e"] = cible
                t["t1c"] = 2
                t["queued"] = 1
                return t, ecarts, "4749"
            pc = "LAB_452EE"

        elif pc == "LAB_452EE":
            # L9763-9775
            if e["command_own"] != 0:
                releve()
            return t, ecarts, "452EE"

        elif pc == "LAB_45318":
            # L9776-9798 : D4 nul / vie trop faible / commande ennemie
            # sautent a LAB_453F6 ; sinon L9797 `BTST #2,($F,A2)` = bit 10
            # du mot +0x0E = $400, et L9798 `BEQ LAB_453F2` = retour direct.
            pe, pa = env["pe"], env["pa"]
            releve_b = (pe is not None
                        and pa[2] > pe[2] + 0x1F4
                        and e["command_other"] == 0)
            if not releve_b:
                pc = "LAB_453F6"
            elif not (e["power_mask"] & 0x400):
                return t, ecarts, "4798"
            else:
                pc = "L9810"

        elif pc == "L9810":
            # L9799-9855 : LAB_45380
            if e["command_own"] != 0:
                releve()
                return t, ecarts, "4805"
            if e["magto_own"] == e["magto_other"]:
                return t, ecarts, "4827"
            amener(e["magto_other"])
            return t, ecarts, "4828"

        elif pc == "LAB_453F6":
            # L9858-9897
            if not (e["power_mask"] & 0x200):
                return t, ecarts, "4860"
            cible, note = fiche(e["strongest_idx"], "strongest")
            if note:
                ecarts.append("strongest-" + note)
            if e["magto_own"] != cible and t["t1c"] == 0:
                t["act"] = 0x05
                t["p1"] = cible & 0x3F
                t["p2"] = s16(cible) >> 6
                t["t1e"] = cible
                t["t1c"] = 2
                t["queued"] = 1
                return t, ecarts, "4871"
            # LAB_4545A
            if e["command_own"] != 0:
                releve()
                return t, ecarts, "4892"
            return t, ecarts, "4896"

        else:
            raise AssertionError("label inconnu %r" % pc)


# ---------------------------------------------------------------------------
# Etat synthetique + pilotage du port
# ---------------------------------------------------------------------------
class FauxJeu:
    """``PowerEngine`` attend ``populous.game.Game``, qui porte juste ``.sim``.

    On n'a besoin d'aucun rendu pour ce controle : on fabrique le porte-
    efets minimal plutot que de construire l'interface complete.
    """

    def __init__(self, sim):
        self.sim = sim


class FauxRng:
    """Remplace `sim.rng` pour que `p1 = 1 + below(3)` soit reproductible."""

    def __init__(self, valeur):
        self.valeur = valeur

    def below(self, n):
        assert n == 3, n
        return self.valeur


def coherer(e):
    """Une meme fiche ne peut porter deux blocs : aligne les lectures.

    ``appliquer`` ecrit d'abord les cases de `p2a` / `strongest`, puis celles
    des aimants : si les indices se recouvrent, le port lit la derniere
    valeur ecrite, donc la reference doit lire la meme.
    """
    jo, je = e["mag_own"] - 1, e["mag_other"] - 1
    for cle, idx in (("p2a", "p2a_idx"), ("strongest", "strongest_idx")):
        j = e[idx]
        if j == jo:
            e[cle] = e["block_own"]
        elif j == je:
            e[cle] = e["block_other"]
    if (e["p2a_idx"] == e["strongest_idx"]
            and 0 <= e["p2a_idx"] < PEEP_SLOTS):
        e["strongest"] = e["p2a"]
    return e


def alea(rng, **sur):
    """Construit une entree aleatoire, les cles de `sur` sont forcees."""
    e = {}
    e["tribe"] = rng.choice((0, 1))
    # seuil = threshold*2+15 <= 16 : seul threshold=0 laisse une chance
    # d'atteindre LAB_45196 (total <= 16+4).
    e["threshold"] = rng.choice((0, 0, 0, 1, 2))
    e["towns"] = rng.randint(0, 16)
    e["castles"] = rng.randint(0, 4)
    e["game_turn"] = rng.randint(0, 359)
    e["command_own"] = rng.choice((0, 0, 1, 1, 3))
    e["command_other"] = rng.choice((0, 0, 1, 7))
    # aimants : 0 (pointeur nul), une fiche valide, ou hors table ($0820)
    e["mag_own"] = rng.choice((0, 0, rng.randint(1, PEEP_SLOTS), 0x0820))
    e["mag_other"] = rng.choice((0, 0, rng.randint(1, PEEP_SLOTS), 0x0820))
    if e["mag_other"] == e["mag_own"] and e["mag_own"]:
        e["mag_other"] = 0
    e["magto_own"] = rng.randint(0, 4095)
    e["magto_other"] = rng.randint(0, 4095)
    e["power_mask"] = rng.choice(
        (0x0000, 0x0007, 0x0200, 0x0400, 0x0600, 0xFFFF,
         rng.randint(0, 0xFFFF)))
    e["t1c"] = rng.choice((0, 0, 1, 2))
    e["t1e"] = rng.randint(0, 4095)
    e["p2a_idx"] = rng.choice((-1, -1, 0, rng.randint(0, PEEP_SLOTS - 1),
                               0x0820))
    e["strongest_idx"] = rng.choice((-1, -1, 0,
                                     rng.randint(0, PEEP_SLOTS - 1), 0x0820))
    e["act"] = rng.choice((0, 1, 5, 15))
    e["p1"] = rng.randint(0, 63)
    e["p2"] = rng.randint(0, 63)
    e["queued"] = rng.choice((0, 1))
    e["rand3"] = rng.randint(0, 2)
    e["block_own"] = rng.randint(0, 4095)
    e["block_other"] = rng.randint(0, 4095)
    e["life_own"] = rng.randint(0, 9999)
    e["life_other"] = rng.randint(0, 9999)
    e["p2a"] = rng.randint(0, 4095)
    e["strongest"] = rng.randint(0, 4095)
    for k, v in sur.items():
        e[k] = v
    # deux aimants ne peuvent pas viser la meme fiche : on ne corrige que
    # la valeur qui n'a pas ete forcee par l'appel.
    if e["mag_own"] and e["mag_other"] == e["mag_own"]:
        if "mag_other" not in sur:
            e["mag_other"] = 0
        elif "mag_own" not in sur:
            e["mag_own"] = 0
    return coherer(e)


def appliquer(g, e):
    """Pose l'entree dans la partie : memes octets que la reference."""
    t = e["tribe"]
    o = 1 - t
    st = g.stats[t]
    st.threshold = e["threshold"]
    st.towns = e["towns"]
    st.castles = e["castles"]
    st.act = e["act"]
    st.p1 = e["p1"]
    st.p2 = e["p2"]
    st.queued = e["queued"]
    st.t1c = e["t1c"]
    st.t1e = e["t1e"]
    st.power_mask = e["power_mask"]
    st.p2a = e["p2a_idx"]
    st.strongest = e["strongest_idx"]
    g.players[t].magnet = e["mag_own"]
    g.players[t].magnet_to = e["magto_own"]
    g.players[t].command = e["command_own"]
    g.players[o].magnet = e["mag_other"]
    g.players[o].magnet_to = e["magto_other"]
    g.players[o].command = e["command_other"]
    g.game_turn = e["game_turn"]

    for idx, blk in ((e["p2a_idx"], e["p2a"]),
                     (e["strongest_idx"], e["strongest"])):
        if 0 <= idx < PEEP_SLOTS:
            g.peeps[idx].block = blk
    jo, je = e["mag_own"] - 1, e["mag_other"] - 1
    if 0 <= jo < PEEP_SLOTS:
        g.peeps[jo].block = e["block_own"]
        g.peeps[jo].life = e["life_own"]
    if 0 <= je < PEEP_SLOTS:
        g.peeps[je].block = e["block_other"]
        g.peeps[je].life = e["life_other"]


def lire(g, t):
    st = g.stats[t]
    return dict((c, getattr(st, c)) for c in CHAMPS)


# ---------------------------------------------------------------------------
# Les chemins de sortie : un cas cible pour chacun.
# ---------------------------------------------------------------------------
def cibles():
    c = []
    # --- periode (L9611-9643)
    c.append(dict(towns=0, castles=0, threshold=3, command_own=0))
    c.append(dict(towns=16, castles=4, threshold=0, game_turn=90,
                  command_own=3))
    # --- A3 nul (L9695)
    c.append(dict(mag_own=0, command_own=0))
    c.append(dict(mag_own=0, command_own=4))
    # --- LAB_45238 / L9720-9775
    c.append(dict(mag_own=1, block_own=777, life_own=100, t1c=2, t1e=777,
                  magto_own=1000))                  # decrement + 4737
    c.append(dict(mag_own=1, life_own=100, t1c=2, t1e=777, magto_own=777,
                  command_own=0))                   # 452EE (sans releve)
    c.append(dict(mag_own=1, life_own=100, t1c=2, t1e=777, magto_own=777,
                  command_own=2))                   # 452EE (avec releve)
    c.append(dict(mag_own=1, life_own=100, t1c=0, magto_own=1,
                  p2a_idx=-1))                      # 4749, p2a nul
    c.append(dict(mag_own=1, life_own=100, t1c=0, magto_own=2000,
                  p2a_idx=5, p2a=1234))            # 4749
    c.append(dict(mag_own=1, life_own=100, t1c=0, magto_own=1234,
                  p2a_idx=5, p2a=1234, command_own=0))   # 452EE
    # --- LAB_45318 : le peep vise a >= 6000 points de vie
    # cond fausse (pas d'aimant ennemi) et bit 9 nul -> LAB_453F6 -> 4860
    c.append(dict(mag_own=1, life_own=6000, mag_other=0, power_mask=0x0000))
    # cond fausse (vie ennemie trop haute) -> 4860
    c.append(dict(mag_own=1, life_own=6000, mag_other=2, life_other=5600,
                  power_mask=0x0000))
    # cond vraie (vie ennemie basse, aucune commande ennemie), bit 10 nul
    # -> retour direct (L9798), **pas** LAB_453F6
    c.append(dict(mag_own=1, life_own=6000, mag_other=2, life_other=0,
                  command_other=0, power_mask=0x0000, t1c=1))    # 4798
    c.append(dict(mag_own=1, life_own=6000, mag_other=2, life_other=5000,
                  command_other=0, power_mask=0x0200, t1c=1))    # 4798
    # LAB_45380
    c.append(dict(mag_own=1, life_own=6000, mag_other=2, life_other=0,
                  command_other=0, power_mask=0x0400, command_own=9))
    c.append(dict(mag_own=1, life_own=6000, mag_other=2, life_other=0,
                  command_other=0, power_mask=0x0400, command_own=0,
                  magto_own=3000, magto_other=3000))
    c.append(dict(mag_own=1, life_own=6000, mag_other=2, life_other=0,
                  command_other=0, power_mask=0x0400, command_own=0,
                  magto_own=3000, magto_other=3001))
    # LAB_453F6 (bit 9)
    c.append(dict(mag_own=1, life_own=6000, mag_other=0, power_mask=0x0200,
                  t1c=0, magto_own=3000, strongest_idx=9, strongest=2500))
    c.append(dict(mag_own=1, life_own=6000, mag_other=0, power_mask=0x0200,
                  t1c=0, magto_own=3000, strongest_idx=-1))
    c.append(dict(mag_own=1, life_own=6000, mag_other=0, power_mask=0x0200,
                  t1c=1, magto_own=3000, strongest_idx=9, strongest=2500,
                  command_own=1))
    c.append(dict(mag_own=1, life_own=6000, mag_other=0, power_mask=0x0200,
                  t1c=1, magto_own=3000, strongest_idx=9, strongest=2500,
                  command_own=0))
    # tous les cas ci-dessus passent le test de periode, sauf les deux
    # premiers qui le testent eux-memes.
    return [dict(PASSE, **kv) for kv in c]


CHEMINS = set(["4515A", "4695", "4737", "452EE", "4749", "4798", "4805",
               "4827", "4828", "4860", "4871", "4892", "4896"])


def main():
    rng = random.Random(20261009)
    g = Game(seed=7)
    eng = PowerEngine(FauxJeu(g))
    rng_reel = g.rng

    vus = set()
    ecarts_total = []
    erreurs = []

    def un(e, etiquette):
        want, ecarts, chemin = reference(e)
        appliquer(g, e)
        g.rng = FauxRng(e["rand3"])
        eng.set_devil_magnet(e["tribe"])
        g.rng = rng_reel
        got = lire(g, e["tribe"])
        vus.add(chemin)
        ecarts_total.extend(ecarts)
        if want != got:
            erreurs.append("chemin %s - %s\n  entree    %r\n"
                           "  reference %r\n  port      %r"
                           % (chemin, etiquette, e, want, got))

    cases = [alea(rng, **kv) for kv in cibles()]
    for i, e in enumerate(cases):
        un(e, "cible #%d" % i)

    n_rand = 600
    for i in range(n_rand):
        un(alea(rng), "hasard #%d" % i)

    manquants = sorted(CHEMINS - vus)
    hors = sorted(vus - CHEMINS)

    print("chemins de sortie      : %d/%d %s"
          % (len(CHEMINS & vus), len(CHEMINS),
             "" if not manquants else "MANQUANTS %s" % manquants))
    if hors:
        print("chemins inattendus     : %s" % hors)
    print("ecarts assumes vus     : %d (%s)"
          % (len(ecarts_total),
             ", ".join(sorted(set(ecarts_total))) or "aucun"))
    print("cas compares           : %d (%d cibles + %d aleatoires)"
          % (len(cases) + n_rand, len(cases), n_rand))

    if erreurs:
        print("\n%d ECART(S) : %d" % (len(erreurs), len(erreurs)))
        for m in erreurs[:5]:
            print(m)
        return 1
    if manquants:
        print("\nchemins non couverts")
        return 1
    print("=> OK : reference et port donnent les memes six champs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
