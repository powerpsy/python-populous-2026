# -*- coding: utf-8 -*-
"""Controle de la boucle modale de `_show_world` (asm L12190-12773).

On ne teste pas les pixels mais la **logique** : ce que l'ecran
*WORLD TO CONQUER* rend, et ce qu'il change dans l'etat du jeu.
``Game._pompe`` est remplace par un scenario de clics, ce qui permet de
faire tourner la vraie ``Game.show_world()`` de bout en bout.

Quatre chemins sont provoques :

============================  ==========================================
Chemin                        Preuve
============================  ==========================================
graine numerique (L12262)     rend -1 sans ouvrir ``level.dat``
``GENESIS`` + START GAME      rend 0, les neuf ecritures de L12762-12770
nom valide + START GAME       ``_decode`` rend sa graine, index = g / 25
NEW GAME (L12758)             reboucle avec ``saisi = 1`` -> ``_get_name``
============================  ==========================================

Un nom inconnu dessine ``NO SUCH WORLD`` (L12299-12312) : la boucle est
infinie dans l'original, puisqu'aucun clavier n'est lu la - le controle
remplit `_message` au moment voulu, comme aurait fait l'utilisateur.

Usage::

    python tools/check_show_world_modal.py
"""
from __future__ import annotations

import io
import os
import re
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

ASM = os.path.join(ROOT, "reference", "tetracorp", "populous_prg.asm")
DAT = os.path.join(ROOT, "reference", "original", "extracted", "level.dat")

from populous.decode import END, MID, START, decode  # noqa: E402
from populous.game import Game  # noqa: E402
from populous.rng import Rng  # noqa: E402
from populous.world import (WORLD_BOXE, WORLD_CANCEL_TEXTE, WORLD_GRAINE,  # noqa: E402
                            WORLD_NB, WORLD_OK_TEXTE, WORLD_PAS_DE_MONDE,
                            WORLD_TEXTE, WORLD_TRAIT, WORLD_X, WORLD_Y)

TOTAL = [0]
KO = [0]


def check(label, cond, detail=""):
    TOTAL[0] += 1
    if not cond:
        KO[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "KO", label,
                           ("  -> " + detail) if detail else ""))


def scenario(g, pas, cles=""):
    """Remplace `Game._pompe` par une sequence de (mx, my, presse).

    `cles` est la frappe a fournir : une touche par image, des que
    `_saisie` est vrai - c'est-a-dire des que `_get_name` tourne. C'est
    ce que fait `handle` avec un vrai `KEYDOWN`.
    """
    n = [0]
    k = [0]

    def pompe():
        if cles and g._saisie and k[0] < len(cles):
            g._touches.append(cles[k[0]])
            k[0] += 1
        if n[0] >= len(pas):
            return
        mx, my, presse = pas[n[0]]
        n[0] += 1
        g.mouse = (mx, my)
        g._raw_left = presse
        g._read_buttons()

    g._pompe = pompe


def nom_de(graine: int) -> str:
    """Le nom d'une graine : code = `_newrand(graine)`, trois syllabes."""
    c = Rng(graine).raw() & 0xFFFF
    return START[c & 31] + MID[(c >> 5) & 31] + END[c >> 10]


def lire_fichier(index):
    with open(DAT, "rb") as f:
        f.seek(index * 10)
        return f.read(0xA)


def main():
    g = Game(59, 0, 3)
    sim = g.sim
    st = sim.stats

    # ---- 0. la geometrie des deux boutons --------------------------------
    # `_cadres_boutons` prend la longueur des deux textes : ici
    # "START GAME" (10) et "NEW GAME" (8), et non "OK"/"CANCEL".
    ok, cancel = g._cadres_boutons(*WORLD_BOXE, WORLD_OK_TEXTE,
                                   WORLD_CANCEL_TEXTE)
    check("L12193-12200 : les deux boutons portent START GAME (10) et "
          "NEW GAME (8), donc deux largeurs differentes",
          ok == (32, 145, 32 + 14 * 8) and cancel == (192, 145, 192 + 12 * 8),
          "ok=%s cancel=%s" % (str(ok), str(cancel)))
    check("L9991-10246 : le bouton NEW GAME est a droite de START GAME, "
          "tous deux sur la ligne y = 145",
          cancel[0] > ok[0] and ok[1] == cancel[1] == 145,
          "ok=%s cancel=%s" % (str(ok), str(cancel)))

    # ---- 1. les espions, poses une seule fois ----------------------------
    indexes = []
    vrai_lire = g._lire_level_dat

    def lire(index):
        indexes.append(index)
        return vrai_lire(index)

    g._lire_level_dat = lire

    # ---- 2. le raccourci numerique (L12262-12273) ------------------------
    indexes[:] = []
    g._message = "1234"
    r = g.show_world()
    check("L12263-12273 : une saisie entierement numerique rend -1",
          r == WORLD_GRAINE == -1, "ret=%d" % r)
    check("L12270-12271 : `_start_seed = _seed = n` (le port n'a qu'un seul "
          "mot de graine - ECART deja declare)",
          g.seed == 1234, "seed=%d" % g.seed)
    check("L12272 : `_message` est efface avant de rendre la main",
          g._message == "", "message=%r" % g._message)
    check("L12273 : `level.dat` n'est pas ouvert du tout",
          indexes == [], "indexes=%s" % indexes)
    check("le raccourci numerique s'arrete avant L12762 : `_level_number` "
          "n'a pas bouge",
          g._monde == -1, "monde=%d" % g._monde)

    # L12265 fait `TST.W D0` et L12270 `MOVE.W D0,(_start_seed)` : c'est
    # le **mot** qui est range, donc -12 s'ecrit $FFF4 et vaut 65524 pour
    # le generateur.
    g._message = "-12"
    r = g.show_world()
    check("L12265/L12270 : un nombre negatif est range en tant que mot - "
          "$FFF4, soit 65524",
          r == WORLD_GRAINE and g.seed == 0xFFF4,
          "ret=%d seed=%d" % (r, g.seed))

    # ---- 3. GENESIS + START GAME (L12281-12288, L12762-12773) ------------
    st[0].act, st[0].queued = 1, 0
    st[1].can_build, st[1].queued = 0, 1
    sim.serial_off, sim.paint_map, sim.war = 0, 1, 1
    sim.player, sim.not_player = 1, 0
    indexes[:] = []
    g._message = "GENESIS"
    scenario(g, [(0, 0, False), (ok[0] + 4, ok[1] + 8, True)])
    try:
        r = g.show_world()
    finally:
        del g._pompe
    check("L12281-12288 : GENESIS donne le monde 0 sans passer par `_decode`",
          r == 0, "ret=%d" % r)
    check("L12315-12319 : l'entree de `level.dat` vaut monde / 25 = 0",
          indexes == [0], "indexes=%s" % indexes)
    check("L12358-12363 : `_conquest` contient exactement les dix octets de "
          "l'entree 0",
          bytes(g._conquest) == lire_fichier(0),
          "%r vs %r" % (bytes(g._conquest), lire_fichier(0)))
    check("L12762 : _player = 0", sim.player == 0, "player=%d" % sim.player)
    check("L12763 : _not_player = 1",
          sim.not_player == 1, "not_player=%d" % sim.not_player)
    check("L12764 : LAB_516D8 (stats[1]) can_build = 1",
          st[1].can_build == 1, "can_build=%d" % st[1].can_build)
    check("L12765 : LAB_516AA (stats[0]) act = 0",
          st[0].act == 0, "act=%d" % st[0].act)
    check("L12766 : LAB_516AC (stats[0]) queued = 1",
          st[0].queued == 1, "queued=%d" % st[0].queued)
    check("L12767 : LAB_516DA (stats[1]) queued = 0",
          st[1].queued == 0, "queued=%d" % st[1].queued)
    check("L12768 : _serial_off = 1", sim.serial_off == 1)
    check("L12769 : _paint_map = 0", sim.paint_map == 0)
    check("L12770 : _war = 0", sim.war == 0)
    check("L12771 : _level_number = le monde rendu",
          g._monde == 0, "monde=%d" % g._monde)

    # ---- 4. un nom valide (L12290-12295, L12315-12319) --------------------
    graine = 100
    nom = nom_de(graine)
    indexes[:] = []
    g._message = nom
    scenario(g, [(0, 0, False), (ok[0] + 4, ok[1] + 8, True)])
    try:
        r = g.show_world()
    finally:
        del g._pompe
    check("L12290-12295 : `_decode` rend bien la graine pour %r" % nom,
          decode(nom) == graine and r == graine,
          "decode=%d rendu=%d" % (decode(nom), r))
    check("L12315-12319 : l'entree de `level.dat` vaut %d / 25 = 4"
          % graine,
          indexes == [4], "indexes=%s" % indexes)
    check("L12358-12363 : `_conquest` contient l'entree 4",
          bytes(g._conquest) == lire_fichier(4), "")

    # ---- 5. NEW GAME reboucle avec `saisi = 1` (L12755-12758) ------------
    # C'est le seul retour a `LAB_47064` qui laisse `(-22)` a 1 : L12376,
    # l'autre, est precede de L12370 qui l'efface.
    indexes[:] = []
    g._message = "GENESIS"
    saisis = []
    vrai_get_name = g.get_name

    def espion(texte, x, y, n, ok2, cancel2):
        saisis.append((texte, x, y, n))
        return vrai_get_name(texte, x, y, n, ok2, cancel2)

    g.get_name = espion
    # 12 images : 2 pour le premier LAB_47236, 8 pour les huit lettres de
    # `_get_name` ("GENESIS" + RETOUR), 2 pour le deuxieme LAB_47236.
    pas = [(0, 0, False), (cancel[0] + 4, cancel[1] + 8, True)]
    pas += [(0, 0, False)] * 8
    pas += [(0, 0, False), (ok[0] + 4, ok[1] + 8, True)]
    scenario(g, pas, cles="GENESIS\r")
    try:
        r = g.show_world()
        erreurs = ""
    except Exception as exc:                      # noqa: BLE001
        r, erreurs = None, "%s: %s" % (type(exc).__name__, exc)
    finally:
        del g._pompe
        del g.get_name
    check("L12755-12758 : NEW GAME efface `_message` avant de rouvrir la "
          "boite - `_get_name` recoit donc un champ vide",
          saisis == [("", 0x20, 0x2C, 0x10)],
          "saisis=%s%s" % (saisis, erreurs))
    check("L12314 puis L12240-12249 : la deuxieme visite a `saisi = 1`, donc "
          "elle seule passe par `_get_name` - une seule fois, avec les sept "
          "arguments x = $20, y = $2C, maxlen = $10",
          len(saisis) == 1 and saisis[0][1:] == (0x20, 0x2C, 0x10),
          "saisis=%s" % (saisis,))
    check("Le nom tape au clavier est rendu a `_message` puis valide comme "
          "n'importe quelle premiere saisie : monde 0, level.dat relu",
          r == 0 and indexes == [0, 0] and g._message == "GENESIS",
          "ret=%r indexes=%s message=%r%s" % (r, indexes, g._message,
                                              erreurs))

    # ---- 6. la structure du listing qui rend ce chemin possible ---------
    ls = io.open(ASM, "r", encoding="utf-8", newline="").read().splitlines()
    d = next(i for i, l in enumerate(ls) if l.startswith("_show_world:"))
    f = next(i for i, l in enumerate(ls) if l.startswith("strStartGame:"))
    corps = ls[d:f]

    def ou(p):
        """Les lignes de la routine qui contiennent `p`, 1-based."""
        return [d + i + 1 for i, l in enumerate(corps) if p in l]

    ecrits = ou("#$0001,(-22,A5)")            # L12314  saisi = 1
    effaces = ou("CLR.W\t(-22,A5)")            # L12192, L12370
    retours = ou("BRA.W\tLAB_47064")           # L12376, L12758
    check("L12192 et L12370 : `saisi` n'est efface qu'a l'ouverture et sur "
          "l'echec du disque",
          effaces == [12192, 12370], "effaces=%s" % effaces)
    check("L12314 : `saisi = 1` n'est ecrit qu'une seule fois",
          ecrits == [12314], "ecrits=%s" % ecrits)
    check("L12370 < L12376 < L12758 : les deux retours a `LAB_47064` sont "
          "l'echec du disque, qui efface `saisi`, et l'abandon NEW GAME, "
          "qui ne l'efface pas",
          effaces[0] < ecrits[0] < effaces[1] < retours[0] < retours[1]
          and not any(retours[0] < n < retours[1] for n in effaces),
          "effaces=%s ecrits=%s retours=%s" % (effaces, ecrits, retours))
    check("d'ou NEW GAME est le seul chemin qui rejoue `LAB_470AC` avec "
          "`saisi = 1`, donc le seul qui appelle `_get_name` (L12249)",
          retours == [12376, 12758], "retours=%s" % retours)

    # ---- 7. un nom inconnu : NO SUCH WORLD, puis la boucle (L12299-12312) -
    traces = []
    vrai_draw = g.ren.draw_text

    def draw(dest, x, y, txt):
        traces.append((x, y, txt))
        if txt == WORLD_PAS_DE_MONDE:
            # La boucle de L12312 ne lit aucun clavier : dans l'original
            # c'est une attente infinie. On fournit ici la saisie que
            # l'utilisateur aurait faite.
            g._message = "GENESIS"
        return vrai_draw(dest, x, y, txt)

    import populous.decode as mod_decode
    vrai_decode = mod_decode.decode
    appeles = []

    def espion(s, jeu=None):
        appeles.append(s)
        return vrai_decode(s, jeu)

    g.ren.draw_text = draw
    mod_decode.decode = espion
    indexes[:] = []
    g._message = "ZZZZ"
    scenario(g, [(0, 0, False), (ok[0] + 4, ok[1] + 8, True)])
    try:
        r = g.show_world()
        erreurs = ""
    except Exception as exc:                      # noqa: BLE001
        r, erreurs = None, "%s: %s" % (type(exc).__name__, exc)
    finally:
        del g._pompe
        g.ren.draw_text = vrai_draw
        mod_decode.decode = vrai_decode
    check("L12291 : `_decode` recoit le nom tape, qui echoue",
          appeles == ["ZZZZ"], "appeles=%s%s" % (appeles, erreurs))
    check("L12299-12309 : `NO SUCH WORLD` est trace une fois au-dessus du "
          "champ",
          sum(1 for _, _, t in traces if t == WORLD_PAS_DE_MONDE) == 1,
          "%d trace(s)" % sum(1 for _, _, t in traces
                              if t == WORLD_PAS_DE_MONDE))
    check("L12312 : la boucle repart, puis GENESIS valide et START GAME "
          "rend 0",
          r == 0 and indexes == [0], "ret=%r indexes=%s" % (r, indexes))

    # ---- 8. le trait et les quinze lignes --------------------------------
    traces[:] = []
    g.ren.draw_text = draw
    g._message = "GENESIS"
    scenario(g, [(0, 0, False), (ok[0] + 4, ok[1] + 8, True)])
    try:
        g.show_world()
    finally:
        del g._pompe
        g.ren.draw_text = vrai_draw
    textes = [t for _, _, t in traces]
    check("L12228-12233 : le trait de seize $82 precede le champ de saisie, "
          "tous deux en (4, 44)",
          any(t == WORLD_TRAIT and x == 4 and y == 0x2C
              for x, y, t in traces),
          "%d traits" % textes.count(WORLD_TRAIT))
    check("L12217-12226 : le titre est l'entree 0 de `strWorldToConquer`, "
          "trace en (4, 34)",
          any(t == WORLD_TEXTE[0] and x == 4 and y == WORLD_Y[0] + 0x18
              for x, y, t in traces), "")
    positions = {(x, y) for x, y, _ in traces}
    manquantes = [i for i in range(WORLD_NB)
                  if ((WORLD_X[i] + 0x10) >> 3, WORLD_Y[i] + 0x18)
                  not in positions]
    check("L12720-12740 : les quinze lignes (0 a 14) sont tracees en "
          "x = (16 + 16) >> 3 = 4, y = y[i] + $18",
          not manquantes, "lignes absentes %s" % manquantes)
    tracees = [i for i in range(1, WORLD_NB)
               if any(x == (WORLD_X[i] + 0x10) >> 3
                      and y == WORLD_Y[i] + 0x18 and t
                      for x, y, t in traces)]
    check("L12741-12743 : la boucle va de i = 1 a i = 14 (`CMPI.W #$000f ; "
          "BLT`), jamais i = 0 - le titre est trace a part, en L12217",
          tracees == list(range(1, WORLD_NB)),
          "lignes tracees %s" % tracees)

    # ---- 9. level.dat hors champ -----------------------------------------
    avant = bytes(g._conquest)
    lu = g._lire_level_dat(98)
    check("L12358-12363 : la derniere entree (98) est lue telle quelle",
          lu is True and bytes(g._conquest) == lire_fichier(98), "")
    lu = g._lire_level_dat(200)
    check("L12347-12363 : une entree hors fichier rend zero octet, et le "
          "tampon garde son contenu precedent - c'est le `Read` de l'Amiga",
          lu is True and bytes(g._conquest) == lire_fichier(98),
          "lu=%r" % bytes(g._conquest))

    del g._lire_level_dat
    print("\n%d controles, %d echec(s)" % (TOTAL[0], KO[0]))
    return 1 if KO[0] else 0


if __name__ == "__main__":
    sys.exit(main())
