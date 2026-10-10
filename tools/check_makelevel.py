# -*- coding: utf-8 -*-
"""Controle d'execution de ``_make_level`` (L9017-9144).

Deux ecritures independantes du meme code :

* ``reference`` - une **reecriture du listing faite ici**, exprimee comme le
  desassemblage : des labels (``L9035``, ``LAB_44AC8``, ``LAB_44B38``...) et
  des sauts explicites dans une machine a etats, pas des ``if`` imbriques.
  Aucun code n'est partage avec ``populous/``.
* ``Game.make_level`` - le port.

On construit des terrains au hasard (relief en plateaux + cases eparses) plus
un cas cible par chemin de sortie, on applique les deux, et on compare le rendu
**et** les quatre champs ``act``/``p1``/``p2``/``queued`` **et** les cases
``blk`` / ``_map_alt`` modifiees.

Trois points sont verifies a part :

1. la table ``_a_flat`` (L25174-25185) est **redecodee depuis le listing**
   a chaque execution : l'ordre des lignes de ``dx`` (``-4, -3, +4, +3, -2,
   +2, -1, +1, 0``) decide laquelle des 81 cases ouvre le terrain ;
2. le debordement ``idx >= 4096`` : les bornes ``0..$40`` de L9062-9069
   laissent passer ``yy == 64``, ``idx`` vaut alors jusqu'a 4160 et le 68000
   lit/ecrit ``_map_alt[idx-4096]``. La preuve vient de la table ``.bss`` :
   ``_map_blk`` $56376 ``DS.L $400`` puis ``_map_alt`` $57376 (L25431-25434),
   soit exactement +$1000 octets ;
3. les deux rendus de la porte d'entree (L9026-9029) : 0xA4 / 0xD2, octets
   bas des adresses ``&stats[0]`` / ``&stats[1]``.

Et deux derives de la meme porte, qui ne sont pas dans ``_make_level`` mais
dont il depend : le global ``_a_flat_block`` / ``_all_of_city`` pose par
``_check_life`` (L20965-L20989) et le compteur de pression ``3*castles +
towns`` lu a L3806.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from populous.constants import (A_FLAT, N_A_FLAT, BLK_FLAT, BLK_ROCK,
                                BLK_RUINS, BLK_SWAMP, MAP_CELLS,
                                OFFSET_VECTOR, ST_VILLAGER)
from populous.sim import Game
from populous.terrain import ALT_W, Terrain

CHEMIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASM = os.path.join(CHEMIN, "reference", "tetracorp", "populous_prg.asm")


# ---------------------------------------------------------------------------
# La table _a_flat, lue dans le listing et pas dans populous/constants.
# ---------------------------------------------------------------------------
def lire_a_flat(path=ASM):
    """Les 162 octets de ``_a_flat`` (L25174-25185), en valeur signee."""
    with open(path, encoding="utf-8") as f:
        lignes = f.read().split("\n")
    i = next(k for k, l in enumerate(lignes) if l.startswith("_a_flat:")) + 1
    octets = []
    while lignes[i].strip().startswith("DC."):
        corps = lignes[i].split("DC.", 1)[1].split(None, 1)[1].split(";")[0]
        for mot in corps.split(","):
            mot = mot.strip().lstrip("$")
            for k in range(0, len(mot), 2):
                octets.append(int(mot[k:k + 2], 16))
        i += 1
    return [o - 256 if o > 127 else o for o in octets]


AF = lire_a_flat()


def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


# ---------------------------------------------------------------------------
# Reference independante : labels et sauts, ecrits a partir du listing.
# ---------------------------------------------------------------------------
def reference(e):
    """``(champs, octets modifies, chemin)`` pour l'entree ``e``."""
    t = dict(act=e["act"], p1=e["p1"], p2=e["p2"], queued=e["queued"])
    # copie de travail des deux tableaux : la reference decide seule de ce
    # qui est ecrit, le port ne doit pas avoir le dernier mot.
    blk = bytearray(e["blk"])
    disp = bytearray(e["map_alt"])
    alt = e["alt"]
    env = dict(xx=0, yy=0, idx=0, v=0, delta=0, k=0, x=0, y=0, centre=0)

    def lu(idx):
        # _map_blk $56376 DS.L $400, _map_alt $57376 (L25431-25434)
        return blk[idx] if idx < MAP_CELLS else disp[idx - MAP_CELLS]

    def ecrire(idx, val):
        if idx < MAP_CELLS:
            blk[idx] = val & 0xFF
        else:
            disp[idx - MAP_CELLS] = val & 0xFF

    def poser(act, xx, yy):
        t["act"] = act
        t["p1"] = xx
        t["p2"] = yy
        t["queued"] = 1

    pc = "L9019"
    while True:
        if pc == "L9019":
            # L9026-9029 : BTST #0,($F,A0) = octet +0x0F = bits 7-0 du
            # mot +0x0E ; BTST #2,(LAB_518A7) = flags bit 2.
            if (e["power_mask"] & 0x0001) == 0 or (e["flags"] & 0x04):
                pc = "LAB_449F8"
            else:
                pc = "L9035"

        elif pc == "LAB_449F8":
            # D0 vaut &stats[tribe] : octets bas de $516A4 / $516D2.
            return t, None, "449F8-garde", \
                0xA4 if e["tribe"] == 0 else 0xD2

        elif pc == "L9035":
            env["x"] = e["block"] & 0x3F                      # ANDI.W #$3F
            env["y"] = s16(e["block"]) >> 6                   # ASR.W #6
            env["centre"] = alt[env["y"] * ALT_W + env["x"]]  # MOVE.W _alt
            env["k"] = 0
            pc = "L9049"

        elif pc == "L9049":
            # LAB_44A32 : D6 de 0 a $A2, pas de 2 -> 81 paires.
            if env["k"] >= N_A_FLAT:
                pc = "L9143"
            else:
                env["xx"] = env["x"] + AF[2 * env["k"]]
                env["yy"] = env["y"] + AF[2 * env["k"] + 1]
                pc = "L9062"

        elif pc == "L9062":
            # TST/CMP borne a [0, $40] **inclusif** : 64 passe.
            if 0 <= env["xx"] <= 0x40 and 0 <= env["yy"] <= 0x40:
                pc = "L9070"
            else:
                pc = "LAB_44B68"

        elif pc == "L9070":
            env["idx"] = (env["yy"] << 6) + env["xx"] & 0xFFFF  # MOVE.W
            env["v"] = lu(env["idx"])
            pc = "L9074"

        elif pc == "L9074":
            pc = "L9078" if env["v"] == BLK_ROCK else "LAB_44AC8"

        elif pc == "L9078":
            pc = "L9080" if not (e["flags"] & 0x08) else "LAB_44AC8"

        elif pc == "L9080":
            # ADDQ.B #1,(0,A0,D0.W) : le rocher monte d'un cran, en
            # memoire, **avant** l'action.
            ecrire(env["idx"], lu(env["idx"]) + 1)
            poser(2, env["xx"], env["yy"])                     # L9084-9090
            return t, (blk, disp), "44A94-rocher", 0

        elif pc == "LAB_44AC8":
            # MULS #$41, ADD.W xx, EXT.L, ASL.L #1 -> sommet (yy, xx)
            # deja bornes par L9062 : pas de hors-table ici.
            env["delta"] = s16(env["centre"] - alt[env["yy"] * ALT_W
                                                   + env["xx"]])
            pc = "L9103"

        elif pc == "L9103":
            # TST.W / BLE -> strictly positive seulement.
            if env["delta"] > 0:
                pc = "L9105"
            else:
                pc = "LAB_44B12"

        elif pc == "L9105":
            poser(1, env["xx"], env["yy"])                     # L9106-9112
            return t, (blk, disp), "44AEA-relever", 0

        elif pc == "LAB_44B12":
            # TST.W / BLT -> strictement negatif.
            if env["delta"] < 0:
                pc = "LAB_44B38"
            else:
                pc = "L9118"

        elif pc == "L9118":
            # A altitude egale, seule une case $42 ou $35 merite un
            # passage par LAB_44B38.
            if env["v"] == BLK_RUINS:
                pc = "LAB_44B38"
            elif env["v"] == BLK_SWAMP:
                pc = "LAB_44B38"
            else:
                pc = "LAB_44B68"

        elif pc == "LAB_44B38":
            # BTST #3,(LAB_518A7) : le bit 3 bloque, mais pas le bit 1
            # du relevve (L9105 n'a pas ce test).
            if e["flags"] & 0x08:
                pc = "LAB_44B68"
            else:
                poser(2, env["xx"], env["yy"])                 # L9130-9136
                return t, (blk, disp), "44B40-creuser", 0

        elif pc == "LAB_44B68":
            env["k"] += 1                                      # ADDQ.W #2
            pc = "L9049"

        elif pc == "L9143":
            return t, (blk, disp), "44B72-epuise", 1


def lire_port(g, e):
    st = g.stats[e["tribe"]]
    return dict(act=st.act, p1=st.p1, p2=st.p2, queued=st.queued)


# ---------------------------------------------------------------------------
# Construction des entrees.
# ---------------------------------------------------------------------------
def relief(rng):
    """``_alt`` : plateau de base + quelques buttes, pour que les trois
    cas ``delta > 0`` / ``< 0`` / ``== 0`` sortent tous."""
    alt = [rng.randint(0, 2) for _ in range(ALT_W * ALT_W)]
    for _ in range(rng.randint(0, 6)):
        h = rng.randint(1, 30)
        x0, y0 = rng.randint(0, 60), rng.randint(0, 60)
        for y in range(y0, min(y0 + rng.randint(1, 6), ALT_W)):
            for x in range(x0, min(x0 + rng.randint(1, 6), ALT_W)):
                alt[y * ALT_W + x] += h
    return alt


def sol(rng):
    """``_map_blk`` + la moitie de ``_map_alt``, pour que le debordement
    ait quelque chose a lire."""
    pool = (0x00, 0x0F, 0x2F, 0x35, 0x42, 0x30, 0x31, 0x44, 0x20, 0x41)
    blk = bytearray(MAP_CELLS)
    disp = bytearray(MAP_CELLS)
    for _ in range(rng.randint(0, 400)):
        v = rng.choice(pool)
        blk[rng.randrange(MAP_CELLS)] = v
    for _ in range(rng.randint(0, 200)):
        disp[rng.randrange(65)] = rng.choice(pool)
    return blk, disp


def alea(rng, **sur):
    e = {}
    e["tribe"] = rng.choice((0, 1))
    # le bit 0 du mot ouvre ; on force aussi les cas ou il est ferme.
    e["power_mask"] = rng.choice((0x0000, 0x0001, 0x0003, 0xFFFF,
                                  rng.randint(0, 0xFFFF)))
    # bit 2 = gele l'IA, bit 3 = bloque le creusement et les rochers.
    e["flags"] = rng.choice((0x00, 0x10, 0x04, 0x08, 0x0C, 0x1C, 0x05,
                             rng.randint(0, 255) & 0x1F))
    e["block"] = rng.choice((
        rng.randint(0, 4095),
        rng.randint(0, 63),                       # bord "haut"
        rng.randint(4032, 4095),                  # bord "bas" -> yy = 64
        (rng.randint(0, 63) << 6) | 63,           # bord "droit" -> xx = 64
        (rng.randint(0, 63) << 6),                # bord "gauche"
        0, 63, 4032, 4095,
    ))
    e["alt"] = relief(rng)
    e["blk"], e["map_alt"] = sol(rng)
    e["act"] = rng.randint(0, 15)
    e["p1"] = rng.randint(0, 63)
    e["p2"] = rng.randint(0, 63)
    e["queued"] = rng.choice((0, 1))
    for k, v in sur.items():
        e[k] = v
    return e


def plat(**sur):
    """Un terrain entierement plat et vide : le point de depart des cas
    cibles, qui ne changent qu'une case ou un sommet."""
    e = alea(random.Random(0))
    e["alt"] = [0] * (ALT_W * ALT_W)
    e["blk"] = bytearray(MAP_CELLS)
    e["map_alt"] = bytearray(MAP_CELLS)
    e["block"] = 0
    e["flags"] = 0x10
    e["power_mask"] = 0xFFFF
    e["act"], e["p1"], e["p2"], e["queued"] = 7, 51, 52, 1
    for k, v in sur.items():
        e[k] = v
    return e


def cibles():
    """Un cas par chemin de sortie."""
    return [
        # ( etiquette, entree )
        ("garde : power_mask bit0 nul",
         plat(power_mask=0xFFFE)),
        ("garde : flags bit2 (gele l'IA)",
         plat(flags=0x14)),
        # block 0 -> x=0, y=0 ; la 1re paire en rangee est (dx=-4,dy=-4)
        # hors borne, la 1re en rangee dx=+4 est (4, 0) -> idx 4.
        ("rocher en (4,0) : ADDQ.B puis act=2",
         plat(blk=_set(4, BLK_ROCK))),
        ("delta > 0 (centre plus haut) : act=1",
         plat(alt=_spike(0, 4, 5))),
        ("delta < 0 (voisin plus haut) : act=2",
         plat(alt=_spike(4, 0, 5))),
        ("delta < 0 mais flags bit3 : rien",
         plat(alt=_spike(4, 0, 5), flags=0x18)),
        ("egal + ruines ($42) : act=2",
         plat(blk=_set(4, BLK_RUINS))),
        ("egal + marais ($35) : act=2",
         plat(blk=_set(4, BLK_SWAMP))),
        ("egal + case ordinaire : epuise, ret 1",
         plat()),
        ("debordement : rocher dans _map_alt",
         debordement()),
        ("garde : les deux a la fois",
         plat(power_mask=0x0000, flags=0x04)),
        ("rocher bloques par flags bit3 -> passe au suivant",
         plat(blk=_set(4, BLK_ROCK), flags=0x18)),
    ]


def _set(idx, v):
    b = bytearray(MAP_CELLS)
    b[idx] = v
    return b


def _spike(dx, dy, h):
    """``_alt`` plat sauf le sommet ``(dx, dy)`` (centre en (0,0))."""
    alt = [0] * (ALT_W * ALT_W)
    alt[dy * ALT_W + dx] = h
    return alt


def debordement():
    """block 4095 -> x=63, y=63. dx=-4/dy=+1 -> (59, 64), idx = 64*64+59
    = 4155 >= 4096 : le 68000 lit et ecrit ``_map_alt[59]``."""
    disp = bytearray(MAP_CELLS)
    disp[4155 - MAP_CELLS] = BLK_ROCK
    return plat(block=4095, map_alt=disp)


# ---------------------------------------------------------------------------
# Application au port.
# ---------------------------------------------------------------------------
class TerrainVierge(Terrain):
    """Terrain sans relief : ``Game.terrain`` est `None` par defaut."""

    def __init__(self):
        super().__init__(seed=1, ground=0)


def partie():
    t = TerrainVierge()
    g = Game(seed=1, map=t.game_map())
    g.terrain = t
    return g


def appliquer(g, e):
    t = g.terrain
    t.alt[:] = e["alt"]
    t.blk[:] = e["blk"]
    t.disp_alt[:] = e["map_alt"]
    st = g.stats[e["tribe"]]
    st.act, st.p1, st.p2, st.queued = e["act"], e["p1"], e["p2"], e["queued"]
    st.power_mask = e["power_mask"]
    g.flags = e["flags"]


# ---------------------------------------------------------------------------
# Controles annexes : _check_life et le compteur de fin de tour.
# ---------------------------------------------------------------------------
def verif_check_life():
    """``_a_flat_block`` (L20989) et ``_all_of_city`` (L21014) sont des
    globaux remis a zero a **chaque** appel (L20965 / L20970)."""
    g = partie()
    terr = g.terrain
    terr.alt[:] = [0] * (ALT_W * ALT_W)
    terr.blk[:] = bytes([BLK_FLAT]) * MAP_CELLS
    terr.bk2[:] = bytes(MAP_CELLS)
    centre = g.map.index(32, 32)
    # les **dix-sept** voisins (OFFSET_VECTOR, dont huit a distance 2) :
    # ne pas en couvrir un laisserait une $0F et fixerait a_flat_block.
    voisins = [centre + o for o in OFFSET_VECTOR]
    erreurs = []

    # tous en $1F (propre tribu), aucun $0F : a_flat_block = 0.
    for nb in voisins:
        terr.blk[nb] = 0x1F
    g.check_life(0, centre)
    if g.a_flat_block != 0:
        erreurs.append("a_flat_block devrait etre 0 (pas de $0F) : %r"
                       % g.a_flat_block)
    if g.all_of_city != 0:
        erreurs.append("all_of_city devrait etre 0 : %r" % g.all_of_city)

    # un voisin en $0F : a_flat_block = 1, et **reinitialise** au tour
    # d'apres quand il n'y en a plus.
    terr.blk[centre - 64] = BLK_FLAT
    g.check_life(0, centre)
    if g.a_flat_block != 1:
        erreurs.append("a_flat_block devrait etre 1 : %r" % g.a_flat_block)
    terr.blk[centre - 64] = 0x1F
    g.check_life(0, centre)
    if g.a_flat_block != 0:
        erreurs.append("a_flat_block non remis a zero : %r" % g.a_flat_block)

    # _all_of_city : k=0 lit bk2[centre] lui-meme, donc le centre compte.
    terr.bk2[centre] = 0x2A
    terr.bk2[centre - 64] = 0x29
    g.check_life(0, centre)
    if g.all_of_city != 2:
        erreurs.append("all_of_city devrait valoir 2 : %r" % g.all_of_city)
    terr.bk2[centre - 64] = 0x28                      # hors [29, 2C]
    g.check_life(0, centre)
    if g.all_of_city != 1:
        erreurs.append("all_of_city devrait valoir 1 : %r" % g.all_of_city)
    terr.bk2[centre] = 0x20                           # centre_bk2 != $2A
    g.check_life(0, centre)
    if g.all_of_city != 0:
        erreurs.append("all_of_city non remis a zero : %r" % g.all_of_city)
    return erreurs


def verif_snapshot():
    """L4361-4370 : ``good_towns[t] = town_count[t]`` et
    ``good_castles[t] = (-40,A5)[t]`` a la fin de chaque tour."""
    g = partie()
    t = g.terrain
    t.alt[:] = [0] * (ALT_W * ALT_W)
    t.blk[:] = bytes([BLK_FLAT]) * MAP_CELLS
    t.disp_alt[:] = bytes(MAP_CELLS)
    g.stats[0].can_build = g.stats[1].can_build = 1
    g.place_people(0, g.map.index(8, 8), 0)
    g.place_people(1, g.map.index(56, 56), 0)
    erreurs = []
    vu_castle = False
    for _ in range(40):
        g.move_peeps()
        for k in (0, 1):
            if g.stats[k].towns != g.players[k].town_count:
                erreurs.append("stats[%d].towns=%d != town_count=%d"
                               % (k, g.stats[k].towns,
                                  g.players[k].town_count))
            if g.stats[k].castles:
                vu_castle = True
    return erreurs, vu_castle


def verif_pression():
    """L3806 : ``(-32)[t] = 3*castles + towns`` ; au dela de 3,
    ``_make_level`` n'est plus appelee sur une case submergee."""
    orig = Game.make_level
    appels = []

    def compteur(self, block, tribe):
        appels.append(block)
        return orig(self, block, tribe)

    Game.make_level = compteur
    try:
        vu = {}
        for castles, towns in ((0, 0), (1, 0), (0, 3), (0, 2)):
            g = partie()
            t = g.terrain
            t.alt[:] = [0] * (ALT_W * ALT_W)
            t.blk[:] = bytes([BLK_FLAT]) * MAP_CELLS
            # map_alt non nul a la case du villageois : c'est la branche
            # LAB_40C84, celle qui lit (-32,A5).
            t.disp_alt[:] = bytes(MAP_CELLS)
            t.disp_alt[g.map.index(8, 8)] = 40
            g.stats[0].can_build = g.stats[1].can_build = 1
            g.stats[0].queued = g.stats[1].queued = 0
            g.stats[0].castles, g.stats[0].towns = castles, towns
            g.game_turn = 0x00FB                       # +1 -> 0xFC > 0xFA
            j = g.place_people(0, g.map.index(8, 8), 0)
            g.peeps[j].state = ST_VILLAGER             # place_people met EXPLORER
            del appels[:]
            g.move_peeps()
            vu[(castles, towns)] = len(appels)
    finally:
        Game.make_level = orig
    erreurs = []
    if not vu[(0, 0)]:
        erreurs.append("pression 0 : _make_level n'a jamais ete appelee")
    for cle in ((1, 0), (0, 3)):
        if vu[cle]:
            erreurs.append("pression %d : appelee %d fois alors que "
                           "3*castles+towns >= 3 doit fermer la porte"
                           % (3 * cle[0] + cle[1], vu[cle]))
    if not vu[(0, 2)]:
        erreurs.append("pression 2 : _make_level devrait etre appelee")
    return erreurs, vu


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    erreurs = []

    # 1. la table, depuis le listing.
    paires = list(zip(AF[::2], AF[1::2]))
    if paires != list(A_FLAT):
        erreurs.append("_a_flat du port != _a_flat decode du listing")
    print("_a_flat            : %d paires, dx = %s"
          % (len(paires), sorted(set(d for d, _ in paires))))

    # 2. make_level vs reference.
    rng = random.Random(20261010)
    g = partie()
    vus = set()
    n = 0

    def un(e, etiquette):
        nonlocal n
        n += 1
        want, eco, chemin, ret = reference(e)
        appliquer(g, e)
        got_ret = g.make_level(e["block"], e["tribe"])
        got = lire_port(g, e)
        got_eco = (bytes(g.map.blk), bytes(g.map.alt))
        vus.add(chemin)
        if (want != got or ret != got_ret
                or (eco is not None and eco != got_eco)):
            erreurs.append("%s - %s\n  entree    blk=%r alt=%r\n"
                           "  reference %r ret=%r %s\n  port      %r ret=%r %s"
                           % (chemin, etiquette, e["blk"][:8], e["alt"][:8],
                              want, ret, chemin, got, got_ret, chemin))

    for i, (lab, e) in enumerate(cibles()):
        un(e, "cible %s" % lab)
    for i in range(800):
        un(alea(rng), "hasard #%d" % i)

    CHEMINS = set(["449F8-garde", "44A94-rocher", "44AEA-relever",
                   "44B40-creuser", "44B72-epuise"])
    print("cas compares       : %d (%d cibles + 800 aleatoires)" % (n, 12))
    print("chemins de sortie  : %d/%d %s"
          % (len(CHEMINS & vus), len(CHEMINS),
             "" if not (CHEMINS - vus) else "MANQUANTS %s"
             % sorted(CHEMINS - vus)))
    if vus - CHEMINS:
        erreurs.append("chemins inattendus %s" % sorted(vus - CHEMINS))

    # 3. les derives.
    e = verif_check_life()
    print("_check_life        : a_flat_block / all_of_city %s"
          % ("ok" if not e else "ECART"))
    erreurs.extend(e)

    e, castle = verif_snapshot()
    print("snapshot fin tour  : stats.towns == town_count %s"
          % ("ok" if not e else "ECART"))
    erreurs.extend(e)

    e, vu = verif_pression()
    print("pression L3806     : appels par cas %r %s"
          % (vu, "ok" if not e else "ECART"))
    erreurs.extend(e)

    if erreurs:
        print("\n%d ECART(S)" % len(erreurs))
        for m in erreurs[:6]:
            print(" ", m)
        return 1
    print("\n=> OK : reference et port donnent les memes octets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
