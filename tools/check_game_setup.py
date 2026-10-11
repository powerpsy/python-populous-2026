# -*- coding: utf-8 -*-
"""Controle de la table du dialogue ``GAME SETUP`` (asm L12801 / L24494).

Les dix-sept lignes du dialogue sont decrites par **un seul** tableau de 17
entrees de 0x2E (46) octets a partir de `_game_text` (L24494), dont les
vues `LAB_51BDE` (y) et `LAB_51BE0` (largeur) sont decalees de 2 et 4
octets avec le meme pas.

Ce script relit les 782 octets **dans le listing** et les compare a la copie
transcrite dans `populous/game_setup.py` : une divergence est un echec. Il
verifie aussi la coherence de la table de sauts (L13292-13308) avec la
géométrie (paires radio, lignes d'action centrees).

Usage::

    python tools/check_game_setup.py
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
BASE = 0x51BDC          # _game_text
STRIDE = 0x2E           # 46
NB = 17                 # boucle L12901-12924 : i de 0 a 16 inclus

TOTAL = [0]
KO = [0]


def check(label: str, cond: bool, detail: str = "") -> None:
    TOTAL[0] += 1
    if not cond:
        KO[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "KO", label,
                           ("  -> " + detail) if detail else ""))


def extraire() -> bytes:
    """Lit les 782 octets du tableau dans le listing."""
    lines = io.open(ASM, "r", encoding=ENC, newline="").read().splitlines()
    debut = fin = None
    for i, l in enumerate(lines):
        if l.startswith("_game_text:"):
            debut = i
        if debut is not None and fin is None and ";51ee8" in l:
            fin = i
    if debut is None or fin is None:
        raise SystemExit("bloc `_game_text` introuvable")

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
    from populous.game_setup import (GAME_SETUP_BOXE, GAME_SETUP_CONQUEST_MAX,
                                     GAME_SETUP_HANDLERS, GAME_SETUP_NB,
                                     GAME_SETUP_TEXTE, GAME_SETUP_W,
                                     GAME_SETUP_X, GAME_SETUP_Y)

    brut = extraire()
    print("table `strGameSetup` : %d octets, %d entrees de 0x%X, base $%05X"
          % (len(brut), NB, STRIDE, BASE))

    for i in range(NB):
        e = brut[i * STRIDE:(i + 1) * STRIDE]
        x = int.from_bytes(e[0:2], "big")
        y = int.from_bytes(e[2:4], "big")
        w = int.from_bytes(e[4:6], "big")
        txt = e[6:].split(b"\x00")[0].decode("latin-1")
        lisible = txt.replace("\x80", "[X]").replace("\x81", "[ ]")
        check("entree %2d : x=%-4d y=%-4d w=%-4d %-20r"
              % (i, x, y, w, lisible),
              (GAME_SETUP_X[i], GAME_SETUP_Y[i], GAME_SETUP_W[i],
               GAME_SETUP_TEXTE[i]) == (x, y, w, txt),
              "port x=%d y=%d w=%d %r"
              % (GAME_SETUP_X[i], GAME_SETUP_Y[i], GAME_SETUP_W[i],
                 GAME_SETUP_TEXTE[i]))

    # ---- structure -------------------------------------------------------
    check("L12901-12924 : la boucle va de 0 a 16 (17 entrees)",
          GAME_SETUP_NB == 17 == len(GAME_SETUP_X) == len(GAME_SETUP_TEXTE))
    check("L13292-13308 : la table de sauts a une entree par ligne",
          len(GAME_SETUP_HANDLERS) == NB)
    check("L13292 : la ligne 0 est le titre, son handler est un no-op",
          GAME_SETUP_HANDLERS[0] == "LAB_47D94"
          and GAME_SETUP_TEXTE[0] == "GAME SETUP")

    # cinq paires de boutons radio en deux colonnes (x = 16 et x = 152)
    paires = all(GAME_SETUP_X[1 + 2 * k] == 16
                 and GAME_SETUP_X[2 + 2 * k] == 152
                 and GAME_SETUP_Y[1 + 2 * k] == GAME_SETUP_Y[2 + 2 * k]
                 and GAME_SETUP_W[1 + 2 * k] == GAME_SETUP_W[2 + 2 * k] == 8
                 for k in range(5))
    check("L24494-24583 : les dix premieres lignes sont cinq paires radio",
          paires,
          "x = %s" % GAME_SETUP_X[1:11])

    # sept lignes d'action centrees, de largeur 128
    actions = all(GAME_SETUP_X[i] == 80 and GAME_SETUP_W[i] == 128
                  for i in range(11, 17))
    check("L24584-24620 : les sept dernieres lignes sont centrees (x=80, w=128)",
          actions)

    # la boite est plus large que celle d'`_options` ($B0 contre $A6)
    check("L12891-12896 : la boite fait 0x120 de large sur 0xB0 de haut",
          GAME_SETUP_BOXE == (0x10, 0x10, 0x120, 0xB0))

    # la coche : $80 allumee, $81 eteinte (L12987 / L12992)
    cases = [i for i in range(1, 17)]
    check("L12987/L12992 : les 16 lignes selectables portent une coche $80",
          all(GAME_SETUP_TEXTE[i].startswith("\x80") for i in cases))
    check("L12987 : la ligne 0 (titre) n'a pas de coche",
          not GAME_SETUP_TEXTE[0].startswith(("\x80", "\x81")))

    # la coupure de la conquete porte sur les neuf premieres lignes
    check("L12974-12978 : en conquete, les lignes 0..8 sont neutralisees",
          GAME_SETUP_CONQUEST_MAX == 9)

    print("\n%d controles, %d echec(s)" % (TOTAL[0], KO[0]))
    return 1 if KO[0] else 0


if __name__ == "__main__":
    sys.exit(main())