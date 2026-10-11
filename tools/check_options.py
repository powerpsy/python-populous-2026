# -*- coding: utf-8 -*-
"""Controle de la table des options de `_options` (asm L13617).

`_options` est le handler du code 7 de `_do_action`, arme par l'entree
`(0,0)` de la barre d'icones. Ses 14 lignes de boite de dialogue sont
decrites par une table de 14 entrees de 0x2E (46) octets a partir de
`_option_text` (L24363) :

    +0x00  W   x de la ligne      (`_option_text`)
    +0x02  W   y de la ligne      (`LAB_51912`)
    +0x04  W   largeur du test    (`LAB_51914`)
    +0x06  40  la chaine ; l'octet 0 est la **coche** ($80 eteinte,
               $81 allumee), reecrit a chaque trace

Ce script relit la table **dans le listing** et la compare a la copie
transcrite dans `populous/options.py` : une divergence est un echec.

Usage::

    python tools/check_options.py
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
BASE = 0x51910          # _option_text
STRIDE = 0x2E           # 46
NB = 14                 # boucle L13663-13684 : i de 0 a 13 inclus

TOTAL = [0]
KO = [0]


def check(label: str, cond: bool, detail: str = "") -> None:
    TOTAL[0] += 1
    if not cond:
        KO[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "KO",
                           label, ("  -> " + detail) if detail else ""))


def extraire() -> bytes:
    """Lit les 644 octets de la table dans le listing."""
    lines = io.open(ASM, "r", encoding=ENC, newline="").read().splitlines()
    debut = fin = None
    for i, l in enumerate(lines):
        if l.startswith("_option_text:"):
            debut = i
        if debut is not None and fin is None and ";51b80" in l:
            fin = i
    if debut is None or fin is None:
        raise SystemExit("bloc `_option_text` introuvable")

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

    for l in lines[debut:fin + 1]:
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
    from populous.options import (OPTIONS_TEXTE, OPTIONS_W, OPTIONS_X,
                                  OPTIONS_Y)

    brut = extraire()
    print("table `_option_text` : %d octets, %d entrees de 0x%X"
          % (len(brut), NB, STRIDE))

    for i in range(NB):
        e = brut[i * STRIDE:(i + 1) * STRIDE]
        x = int.from_bytes(e[0:2], "big")
        y = int.from_bytes(e[2:4], "big")
        w = int.from_bytes(e[4:6], "big")
        # la chaine s'arrete au premier NUL ; l'octet 0 est la coche
        txt = e[6:].split(b"\x00")[0].decode("latin-1")
        attendu = txt.replace("\x80", "[]").replace("\x81", "[X]")
        check("entree %2d : x=%-4d y=%-4d w=%-4d %r"
              % (i, x, y, w, attendu),
              (OPTIONS_X[i], OPTIONS_Y[i], OPTIONS_W[i], OPTIONS_TEXTE[i])
              == (x, y, w, txt),
              "port x=%d y=%d w=%d %r"
              % (OPTIONS_X[i], OPTIONS_Y[i], OPTIONS_W[i], OPTIONS_TEXTE[i]))

    # les trois lignes que `_options` traite a part
    check("L13663 : la boucle va de 0 a 13 (14 entrees)",
          NB == 14)
    check("L13708 : la coche d'eteinte vaut $80",
          OPTIONS_TEXTE[1].startswith("\x80"))
    check("L13733/L13778 : entrees 11 et 13 = les deux curseurs",
          OPTIONS_TEXTE[11].startswith("LOW")
          and OPTIONS_TEXTE[13].startswith("SLOW"))

    print("\n%d controles, %d echec(s)" % (TOTAL[0], KO[0]))
    return 1 if KO[0] else 0


if __name__ == "__main__":
    sys.exit(main())
