# -*- coding: utf-8 -*-
"""Controle de l'ecran deux joueurs — `_two_players` (asm L11265).

La table des seize panneaux est relue **dans le listing** et comparee a
`populous/two_players.py`. La machine a etats est ensuite verifiee sur son
comportement : boucle, trace, CANCEL, et le leveur nomme quand on tente de se
connecter.

Usage::

    python tools/check_two_players.py
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

from populous.game import Game  # noqa: E402

ENC = "utf-8"
ASM = os.path.join(ROOT, "reference", "tetracorp", "populous_prg.asm")
BASE = 0x525DA          # _serial_text
STRIDE = 0x2E
NB = 16                 # (0x528ba - 0x525da) / 0x2e = 736 / 46

TOTAL = [0]
KO = [0]


def check(label, cond, detail=""):
    TOTAL[0] += 1
    if not cond:
        KO[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "KO", label,
                           ("  -> " + detail) if detail else ""))


def extraire():
    lines = io.open(ASM, "r", encoding=ENC, newline="").read().splitlines()
    debut = next(i for i, l in enumerate(lines) if l.startswith("_serial_text:"))
    fin = next(i for i, l in enumerate(lines) if l.startswith("LAB_528BA:"))
    buf = bytearray()
    addr = BASE

    def emit(data):
        nonlocal addr
        buf.extend(data)
        addr += len(data)

    for l in lines[debut:fin]:
        m = re.search(r";([0-9a-f]{5})\s*$", l)
        if m and not l.lstrip().startswith(";"):
            addr = int(m.group(1), 16)
        body = l.split(";")[0].strip()
        if not body or body.endswith(":"):
            continue
        m = re.match(r"^(DC|DS)\.([WLB])\s+(.*)$", body)
        if not m:
            continue
        genre, taille, vals = m.group(1), m.group(2), m.group(3)
        if genre == "DS":
            n = int(vals.split(",")[0].strip().replace("$", ""), 16)
            emit(b"\x00" * n * {"W": 2, "L": 4, "B": 1}[taille])
            continue
        for v in vals.split(","):
            v = v.strip()
            if not v:
                continue
            if v.startswith('"'):
                emit(v.strip('"').encode("latin-1"))
            elif v.startswith("$"):
                emit(int(v.replace("$", ""), 16).to_bytes(
                    {"W": 2, "L": 4, "B": 1}[taille], "big"))
            else:
                emit(b"\x00")
    return bytes(buf)


def main():
    from populous.two_players import (SERIAL_BOXE, SERIAL_ETAT_INITIAL,
                                       SERIAL_ETATS, SERIAL_NB,
                                       SERIAL_OPTIONS_DATALINK,
                                       SERIAL_OPTIONS_MODEM, SERIAL_TEXTE,
                                       SERIAL_W, SERIAL_X, SERIAL_Y)

    brut = extraire()
    print("table `_serial_text` : %d octets, %d entrees de 0x%X, base $%05X"
          % (len(brut), NB, STRIDE, BASE))
    check("L24930-25040 : le bloc fait exactement %d octets" % (NB * STRIDE),
          len(brut) == NB * STRIDE == 0x528BA - BASE,
          "%d lus" % len(brut))

    for i in range(NB):
        e = brut[i * STRIDE:(i + 1) * STRIDE]
        x = int.from_bytes(e[0:2], "big")
        y = int.from_bytes(e[2:4], "big")
        w = int.from_bytes(e[4:6], "big")
        txt = e[6:].split(b"\x00")[0].decode("latin-1")
        lisible = txt.replace("\x80", "[ ]").replace("\x81", "[X]")
        check("entree %2d : x=%-4d y=%-4d w=%-4d %r" % (i, x, y, w, lisible),
              (SERIAL_X[i], SERIAL_Y[i], SERIAL_W[i], SERIAL_TEXTE[i])
              == (x, y, w, txt),
              "port x=%d y=%d w=%d %r" % (SERIAL_X[i], SERIAL_Y[i],
                                          SERIAL_W[i], SERIAL_TEXTE[i]))

    check("L24930 : les seize entrees sont declarees",
          SERIAL_NB == 16 == len(SERIAL_X) == len(SERIAL_TEXTE))
    check("L24930-25016 : toutes les colonnes sont a x = 16",
          all(v == 16 for v in SERIAL_X))
    check("L11323-L11346 : les panneaux 2, 3 et 4 sont les trois etats de "
          "la machine",
          (SERIAL_TEXTE[2], SERIAL_TEXTE[3], SERIAL_TEXTE[4])
          == ("BAUD RATE", "\x80 DATALINK", "\x80 FULL SERIAL CHECKING"))
    check("L11363-L11413 : les panneaux 5 et 6 sont les options modem",
          SERIAL_TEXTE[5] == "\x80 I AM GOOD"
          and SERIAL_TEXTE[6] == "\x81 USE THIS LANDSCAPE")
    check("L11698-11713 : la serie datalink est 3..7",
          SERIAL_OPTIONS_DATALINK == (3, 4, 5, 6, 7))
    check("L11717-11725 : la serie modem est 8..11",
          SERIAL_OPTIONS_MODEM == (8, 9, 10, 11))
    check("L25017-25039 : les quatre messages d'etat sont 12..15",
          SERIAL_ETATS == (12, 13, 14, 15))
    check("L11287-11294 : la boite fait $100 de large sur $80 de haut",
          SERIAL_BOXE == (0x20, 0x2E, 0x100, 0x80))
    check("L11267 : l'etat initial vaut $3E7 = 999",
          SERIAL_ETAT_INITIAL == 0x3E7 == 999)

    # ---- la machine a etats -------------------------------------------
    g = Game(59, 0, 3)
    g.sim.serial_off = 0

    def scenario(pas):
        n = [0]

        def pompe():
            if n[0] >= len(pas):
                return
            mx, my, presse = pas[n[0]]
            n[0] += 1
            g.mouse = (mx, my)
            g._raw_left = presse
            g._read_buttons()

        g._pompe = pompe

    ok, cancel = g._cadres_boutons(*SERIAL_BOXE)
    check("L9991-10246 : les deux cadres de la boite serie sont calcules",
          cancel[0] > ok[0], "ok=%s cancel=%s" % (str(ok), str(cancel)))

    # CANCEL : la boite se referme et rend 1
    scenario([(0, 0, False), (cancel[0] + 4, cancel[1] + 8, True)])
    r = g.two_players()
    del g._pompe
    check("L11886-11892 : CANCEL sort de la boucle et rend 1", r == 1,
          "r=%d" % r)

    # OK : la connexion passe par `_try_serial`, qui leve
    scenario([(0, 0, False), (ok[0] + 4, ok[1] + 8, True)])
    leve, detail = False, ""
    try:
        g.two_players()
    except NotImplementedError as exc:
        leve, detail = True, str(exc)
    del g._pompe
    check("L11884-11885 : OK tente la connexion et leve en nommant "
          "`_try_serial`", leve and "_try_serial" in detail,
          detail or "aucune leve")
    check("L11884 : le leveur cite aussi le port serie, pas un ecart muet",
          leve and ("_write_serial" in detail and "_set_baud_rate" in detail))

    # ---- le trace des seize panneaux ----------------------------------
    trace_ok, detail = True, ""
    try:
        for e in range(SERIAL_NB):
            g._trace_two_players(e)
    except Exception as exc:
        trace_ok, detail = False, "%s: %s" % (type(exc).__name__, exc)
    check("L11284-11413 : les seize panneaux se tracent sans lever",
          trace_ok, detail)

    # ---- la ligne 2 de GAME SETUP ouvre desormais l'ecran --------------
    g._redessiner = False
    appele = []
    vrai = g.two_players

    def espion():
        appele.append(True)
        return 1

    g.two_players = espion
    try:
        sortie = g._exec_game_setup(2)
    finally:
        g.two_players = vrai
    check("L13021 : la ligne 2 ouvre `_two_players` et sort de la boite",
          appele == [True] and sortie is True,
          "appele %s, sortie %s" % (appele, sortie))

    # ---- L13028 : la branche desactivee ------------------------------
    # `TST.W (_serial_off) ; BEQ` (L13009-13010) : quand la liaison serie
    # est **active** - donc deux joueurs - la ligne 2 ne fait que poser
    # `bring_up_two` et rendre la main, sans ouvrir l'ecran.
    g.sim.serial_off = 1
    g.sim.bring_up_two = 0
    sortie = g._exec_game_setup(2)
    check("L13009-L13028 : liaison active -> la ligne 2 pose `bring_up_two` "
          "et sort sans ouvrir l'ecran",
          sortie is True and g.sim.bring_up_two == 1 and appele == [True],
          "bring_up_two=%d, appels %d" % (g.sim.bring_up_two, len(appele)))

    print("\n%d controles, %d echec(s)" % (TOTAL[0], KO[0]))
    return 1 if KO[0] else 0


if __name__ == "__main__":
    sys.exit(main())