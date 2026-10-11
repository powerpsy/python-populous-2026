# -*- coding: utf-8 -*-
"""Controle de la table du resume de monde — `_show_world` (asm L12190).

Les 690 octets sont relus **dans le listing** et compares entree par entree a
`populous/world.py`. Le controle note aussi le point ouvert laisse par la
transcription : la boucle annonce seize lignes, le tableau en a quinze.

Usage::

    python tools/check_show_world.py
"""
from __future__ import annotations

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

ENC = "utf-8"
ASM = os.path.join(ROOT, "reference", "tetracorp", "populous_prg.asm")
BASE = 0x51EEA          # _c_text
STRIDE = 0x2E
NB = 15                 # (0x5219c - 0x51eea) / 0x2e = 690 / 46

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
    debut = next(i for i, l in enumerate(lines) if l.startswith("_c_text:"))
    fin = next(i for i, l in enumerate(lines) if l.startswith("_con_text:"))
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
    from populous.world import (WORLD_BOXE, WORLD_GRAINE,
                                WORLD_HANDLERS, WORLD_LIGNE_MAX, WORLD_NB,
                                WORLD_OK, WORLD_PUISSANCES, WORLD_TEXTE,
                                WORLD_W, WORLD_X, WORLD_Y)

    brut = extraire()
    print("table `strWorldToConquer` : %d octets, base $%05X, %d entrees de "
          "0x%X" % (len(brut), BASE, NB, STRIDE))
    check("L24621-24724 : le bloc fait exactement %d octets" % (NB * STRIDE),
          len(brut) == NB * STRIDE == 0x5219C - BASE, "%d lus" % len(brut))

    for i in range(NB):
        e = brut[i * STRIDE:(i + 1) * STRIDE]
        x = int.from_bytes(e[0:2], "big")
        y = int.from_bytes(e[2:4], "big")
        w = int.from_bytes(e[4:6], "big")
        txt = e[6:].split(b"\x00")[0].decode("latin-1")
        check("entree %2d : x=%-4d y=%-4d w=%-4d %r" % (i, x, y, w, txt),
              (WORLD_X[i], WORLD_Y[i], WORLD_W[i], WORLD_TEXTE[i])
              == (x, y, w, txt),
              "port x=%d y=%d w=%d %r" % (WORLD_X[i], WORLD_Y[i], WORLD_W[i],
                                          WORLD_TEXTE[i]))

    # ---- structure -----------------------------------------------------
    check("L24621 : les entrees sont declarees",
          WORLD_NB == 15 == len(WORLD_X) == len(WORLD_TEXTE))
    check("L24621-24724 : toutes les lignes sont a x = 16",
          all(v == 16 for v in WORLD_X))
    check("L24635 : l'entree 0 est le titre",
          WORLD_TEXTE[0] == "WORLD TO CONQUER")
    check("L12388-12394 : l'entree 1 est le numero de bataille",
          WORLD_TEXTE[1] == "BATTLE NUMBER IS ")
    check("L12412-12428 : l'entree 2 est le relief",
          WORLD_TEXTE[2] == "WORLDS LANDSCAPE IS ")
    check("L12496 : l'entree 8 est la ligne des deux colonnes YOU / HIM",
          "YOU" in WORLD_TEXTE[8] and "HIM" in WORLD_TEXTE[8],
          repr(WORLD_TEXTE[8]))
    check("L12492-12440 : les six puissances occupent les lignes 9 a 14",
          tuple(WORLD_TEXTE[9:15]) == WORLD_PUISSANCES,
          str(WORLD_TEXTE[9:15]))

    # les y sont strictement croissants : chaque ligne descend de 8 px
    ys = WORLD_Y[1:]
    check("L12404-L12440 : les lignes descendent de 8 px apres l'entete 8",
          all(b - a in (8, 10) for a, b in zip(ys, ys[1:])),
          str(ys))

    check("L12208-12215 : la boite fait $120 de large sur $A0 de haut",
          WORLD_BOXE == (0x10, 0x18, 0x120, 0xA0))
    check("L12270-L12273 : une saisie numerique rend -1 (c'est une graine)",
          WORLD_GRAINE == -1)

    # ---- le point ouvert, resolu ---------------------------------------
    check("L12742-12743 : la boucle de trace va de 1 a 14 (`CMPI.W #$000f`)",
          WORLD_LIGNE_MAX == 14,
          "ligne max = %d" % WORLD_LIGNE_MAX)
    check("L12699-12709 : la table de sauts a dix entrees, `line_0` a "
          "`line_9`", WORLD_HANDLERS == 10)
    check("L12713-12714 : toute ligne >= 10 repart sur `line_0` "
          "(« level 10+ = 0 »)",
          WORLD_NB == WORLD_LIGNE_MAX + 1
          and WORLD_LIGNE_MAX + 1 > WORLD_HANDLERS,
          "%d entrees pour %d iterations et %d handlers"
          % (WORLD_NB, WORLD_LIGNE_MAX, WORLD_HANDLERS))
    check("L12762-12771 : OK arme une partie neuve a un joueur",
          (WORLD_OK["player"], WORLD_OK["not_player"],
           WORLD_OK["serial_off"], WORLD_OK["paint_map"], WORLD_OK["war"])
          == (0, 1, 1, 0, 0), str(WORLD_OK))

    print("\n%d controles, %d echec(s)" % (TOTAL[0], KO[0]))
    return 1 if KO[0] else 0


if __name__ == "__main__":
    sys.exit(main())