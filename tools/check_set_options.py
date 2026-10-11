# -*- coding: utf-8 -*-
"""Controle de la table de l'ecran *SET GAME OPTIONS* (asm L13362 / L24845).

Les onze lignes sont decrites par **un seul** tableau de 11 entrees de 0x2E
(46) octets a partir de `_set_text` (L24845), dont `LAB_523B0` (y) et
`LAB_523B2` (largeur) sont des vues decalees de 2 et 4 octets avec le meme
pas.

Ce script relit les 506 octets **dans le listing** et les compare a la copie
transcrite dans `populous/set_options.py` : une divergence est un echec.

Usage::

    python tools/check_set_options.py
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
BASE = 0x523AE          # _set_text
STRIDE = 0x2E           # 46
NB = 11                 # le titre + cinq paires de deux

TOTAL = [0]
KO = [0]


def check(label: str, cond: bool, detail: str = "") -> None:
    TOTAL[0] += 1
    if not cond:
        KO[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "KO", label,
                           ("  -> " + detail) if detail else ""))


def extraire() -> bytes:
    """Lit les 506 octets du tableau dans le listing."""
    lines = io.open(ASM, "r", encoding=ENC, newline="").read().splitlines()
    debut = fin = None
    for i, l in enumerate(lines):
        if l.startswith("_set_text:"):
            debut = i
        if debut is not None and fin is None and l.startswith("_blank:"):
            fin = i
    if debut is None or fin is None:
        raise SystemExit("bloc `_set_text` introuvable")

    buf = bytearray()
    addr = BASE
    limite = BASE + NB * STRIDE

    def emit(data: bytes) -> None:
        nonlocal addr
        if addr + len(data) > limite:
            data = data[:limite - addr]
        if data:
            buf.extend(data)
            addr += len(data)

    for l in lines[debut:fin]:
        m = re.search(r";([0-9a-f]{5})\s*$", l)
        if m and not l.lstrip().startswith(";"):
            addr = int(m.group(1), 16)      # l'adresse du commentaire gagne
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
                n = int(v.replace("$", ""), 16)
                emit(n.to_bytes({"W": 2, "L": 4, "B": 1}[taille], "big"))
            else:
                emit(b"\x00")
    if len(buf) != limite - BASE:
        raise SystemExit("table tronquee : %d octets lus, %d attendus"
                         % (len(buf), limite - BASE))
    return bytes(buf)


def main() -> int:
    from populous.set_options import (SET_OPTIONS_BLANC, SET_OPTIONS_BOXE,
                                       SET_OPTIONS_NB, SET_OPTIONS_PAIRES,
                                       SET_OPTIONS_PASTICHE,
                                       SET_OPTIONS_SURVOL, SET_OPTIONS_TEXTE,
                                       SET_OPTIONS_W, SET_OPTIONS_X,
                                       SET_OPTIONS_Y)

    brut = extraire()
    print("table `strGameOptions` : %d octets, %d entrees de 0x%X, base $%05X"
          % (len(brut), NB, STRIDE, BASE))

    for i in range(NB):
        e = brut[i * STRIDE:(i + 1) * STRIDE]
        x = int.from_bytes(e[0:2], "big")
        y = int.from_bytes(e[2:4], "big")
        w = int.from_bytes(e[4:6], "big")
        txt = e[6:].split(b"\x00")[0].decode("latin-1")
        lisible = txt.replace("\x80", "[ ]").replace("\x81", "[X]")
        check("entree %2d : x=%-4d y=%-4d w=%-4d %r" % (i, x, y, w, lisible),
              (SET_OPTIONS_X[i], SET_OPTIONS_Y[i], SET_OPTIONS_W[i],
               SET_OPTIONS_TEXTE[i]) == (x, y, w, txt),
              "port x=%d y=%d w=%d %r"
              % (SET_OPTIONS_X[i], SET_OPTIONS_Y[i], SET_OPTIONS_W[i],
                 SET_OPTIONS_TEXTE[i]))

    # ---- structure -------------------------------------------------------
    check("L13385-13446 : la boucle trace j = 0..4, deux colonnes par ligne",
          SET_OPTIONS_PAIRES == 5 and SET_OPTIONS_NB == 11)

    # cinq paires : meme y, meme x, meme largeur 8
    paires = all(SET_OPTIONS_X[1 + 2 * k] == SET_OPTIONS_X[2 + 2 * k] == 16
                 and SET_OPTIONS_Y[1 + 2 * k] == SET_OPTIONS_Y[2 + 2 * k]
                 and SET_OPTIONS_W[1 + 2 * k] == SET_OPTIONS_W[2 + 2 * k] == 8
                 for k in range(5))
    check("L24845-24913 : les dix lignes de choix sont cinq paires a x=16",
          paires, "y = %s" % SET_OPTIONS_Y[1:11])

    # la zone cliquable ne couvre que les huit pixels de la coche
    check("L13507-13510 : la largeur du test est 8 - la coche seule",
          all(SET_OPTIONS_W[i] == 8 for i in range(1, 11)))

    # le survol ne teste que les colonnes impaires
    check("L13490/L13585-13587 : le survol avance de deux en deux jusqu'a 10",
          SET_OPTIONS_SURVOL == (1, 3, 5, 7, 9))

    # le titre n'a pas de coche, les dix autres en ont une
    check("L24855 : le titre n'a pas de coche",
          not SET_OPTIONS_TEXTE[0].startswith(("\x80", "\x81")))
    check("L24858-24913 : les dix lignes de choix portent une coche",
          all(SET_OPTIONS_TEXTE[i].startswith(("\x80", "\x81"))
              for i in range(1, 11)))

    # avec `_game_mode == 0` (sa valeur BSS, L24310) c'est la colonne 1 de
    # chaque paire qui s'allume - et c'est ce que porte le ROM.
    premieres = all(SET_OPTIONS_TEXTE[1 + 2 * k].startswith("\x80")
                    and SET_OPTIONS_TEXTE[2 + 2 * k].startswith("\x81")
                    for k in range(5))
    check("L13386-13396 : `_game_mode == 0` -> colonne 1 active (coche $80)",
          premieres)

    check("L13367-13372 : la boite fait 0x100 de large sur 0x70 de haut",
          SET_OPTIONS_BOXE == (0x20, 0x18, 0x100, 0x70))

    check("L24915-24918 : `_blank` vaut onze carats, pas des espaces",
          SET_OPTIONS_BLANC == "^" * 11 and len(SET_OPTIONS_BLANC) == 11)

    # la rustine de debug : "LANDSCAPE NO " puis le numero a l'offset 13
    prefixe, decalage = SET_OPTIONS_PASTICHE
    check("L13451-13458 : la rustine ecrit le numero a `buf + 13`, juste apres "
          "l'espace final",
          prefixe == "LANDSCAPE NO " and decalage == len(prefixe) == 13,
          "prefixe=%r (%d car.) decalage=%d" % (prefixe, len(prefixe), decalage))

    print("\n%d controles, %d echec(s)" % (TOTAL[0], KO[0]))
    return 1 if KO[0] else 0


if __name__ == "__main__":
    sys.exit(main())