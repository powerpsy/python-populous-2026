# -*- coding: utf-8 -*-
"""Controle de `_con_text` (asm L24726) et de `_put_in_string` (L12163).

Les **39 entrees** de la table sont relues dans le listing - d'abord la
table de pointeurs, puis les octets **a l'adresse vers laquelle chaque
entree pointe** - et comparees a `populous/con_text.py`. Le controle est
donc une lecture de la memoire du jeu, pas une relecture de nos propres
noms.

Trois formes d'adresse coexistent dans le listing ; le lecteur les
reconnait toutes les trois :

- `;46ff2: 4a6d0010`  - en fin de ligne de code ;
- `;4e1b4` seul sur sa ligne, juste au-dessus de `DC.B "GRASS PLANES",0` ;
- `;4e28a` en fin de ligne de donnee, sans les deux-points.

Usage::

    python tools/check_con_text.py
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

TOTAL = [0]
KO = [0]


def check(label, cond, detail=""):
    TOTAL[0] += 1
    if not cond:
        KO[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "KO", label,
                           ("  -> " + detail) if detail else ""))


def lignes():
    return io.open(ASM, "r", encoding=ENC, newline="").read().splitlines()


# --------------------------------------------------------------------------
# l'image memoire du listing : adresse -> octet
# --------------------------------------------------------------------------
TAILLE_DC = {"B": 1, "W": 2, "L": 4}


def image(ls):
    """Reconstruit la memoire du listing, octet par octet."""
    mem, cur = {}, None
    for l in ls:
        # (1) l'adresse peut être en fin de ligne, avec deux-points
        m = re.search(r";\s*([0-9a-f]{5})\s*:", l)
        if m is not None:
            cur = int(m.group(1), 16)
            continue
        # (2) ... ou seule sur sa ligne, au-dessus de la donnee
        m = re.match(r"^\s*;([0-9a-f]{5})\s*$", l)
        if m is not None:
            cur = int(m.group(1), 16)
            continue

        corps = l.split(";")[0].rstrip()
        if not corps.strip():
            continue
        est_donnee = bool(re.match(r"^\s*(DC|DS)\.", corps))

        # (3) sur une ligne de donnee, l'adresse peut etre en fin de ligne
        #     sans les deux-points : `DC.B $59 ;4e28a`
        if est_donnee:
            m = re.search(r";\s*([0-9a-f]{5})\s*$", l)
            if m is not None:
                cur = int(m.group(1), 16)
        if cur is None:
            continue

        def ecrire(data):
            for i, c in enumerate(data):
                mem[cur + i] = c
            return len(data)

        # `DC.B "texte"`, `DC.B "texte",0`, `DC.B "texte",0,0`
        m = re.match(r'^\s*DC\.B\s+"(.*)"((?:,0)*)\s*$', corps)
        if m:
            cur += ecrire(m.group(1).encode("latin-1")
                          + b"\x00" * (len(m.group(2)) // 2))
            continue
        # `DC.B $xx`, `DC.W $xxxx`, `DC.L $xxxxxxxx`
        m = re.match(r"^\s*(DC\.[BWL])\s+\$([0-9a-fA-F]+)\s*$", corps)
        if m:
            n = TAILLE_DC[m.group(1)[3]]
            v = int(m.group(2), 16)
            cur += ecrire(bytes((v >> (8 * (n - 1 - i))) & 0xFF
                                for i in range(n)))
            continue
        # `DS.B 1`, `DS.W 1` ... la valeur peut etre en decimal
        m = re.match(r"^\s*(DS\.[BWL])\s+(\d+)\s*$", corps)
        if m:
            n = TAILLE_DC[m.group(1)[3]] * int(m.group(2), 10)
            cur += ecrire(b"\x00" * n)
            continue
    return mem


def chaine(mem, ptr, garde=64):
    out = bytearray()
    for k in range(garde):
        c = mem.get(ptr + k, 0)
        if c == 0:
            break
        out.append(c)
    return out.decode("latin-1")


def main():
    from populous.con_text import (CON_FIN_PARTIE, CON_NIVEAUX, CON_RELIEFS,
                                   CON_TEXT, CON_TEXT_NB, CON_VITESSES,
                                   put_in_string)

    ls = lignes()
    mem = image(ls)

    # ---- la table de pointeurs (L24726-24780) ---------------------------
    # Le commentaire de chaque `DC.L` porte la valeur du pointeur :
    # `;5219c: 0004e1b4` est l'entree 0, qui pointe `strGrassPlanes`.
    i0 = next(k for k, l in enumerate(ls) if l.startswith("_con_text:"))
    i1 = next(k for k, l in enumerate(ls) if l.startswith("_go_protect:"))
    table, adr = [], 0x5219C
    for l in ls[i0:i1]:
        corps = l.split(";")[0].strip()
        m = re.match(r"^DC\.L\s+(\w+)\s*$", corps)
        if not m:
            continue
        val = re.search(r";([0-9a-f]{5}):\s+([0-9a-f]{8})\s*$", l)
        if val is None:
            continue
        if int(val.group(1), 16) != adr:
            check("L24727 : l'entree %d est a l'adresse $%05x, pas $%05x"
                  % (len(table), int(val.group(1), 16), adr), False)
            break
        table.append((m.group(1), int(val.group(2), 16)))
        adr += 4

    print("`_con_text` : %d entrees de 4 octets, $%05X-$%05X"
          % (len(table), 0x5219C, adr))
    check("L24726-24780 : la table compte 39 entrees de 4 octets, soit 156 "
          "octets",
          len(table) == CON_TEXT_NB == 39 and len(table) * 4 == 0x9C,
          "%d entrees" % len(table))
    check("L24726-24780 : les adresses sont contigues depuis $5219c, et la "
          "table finit sur `_go_protect` ($52238)",
          adr == 0x5219C + 4 * len(table) == 0x52238,
          "fin a $%05X" % adr)
    check("L24726-24780 : autant de libelles transcrits que d'entrees",
          len(CON_TEXT) == len(table))
    if len(table) != CON_TEXT_NB:
        print("  table illisible, abandon")
        return 1

    # ---- les chaines, lues a leur adresse -------------------------------
    for i, (nom, ptr) in enumerate(table):
        attendu = chaine(mem, ptr)
        check("entree %2d : %-22s $%06x -> %r" % (i, nom, ptr, attendu),
              CON_TEXT[i] == attendu, "port %r" % CON_TEXT[i])

    # le bloc des cinq libelles de fin de partie est **contigu** : c'est
    # l'alignement du listing qui le prouve, pas notre lecture.
    for k in CON_FIN_PARTIE:
        if k + 1 >= len(table):
            continue                      # 38 est la derniere : rien apres
        nk = k + 1
        fin = table[k][1] + len(CON_TEXT[k]) + 1
        check("L24772-24780 : l'entree %d finit exactement sur l'adresse de "
              "l'entree %d ($%06x)" % (k, nk, table[nk][1]),
              fin == table[nk][1], "fin a $%06x" % fin)

    # ---- la coherence des index ------------------------------------------
    check("L12417-L12421 : les quatre reliefs sont les quatre premieres "
          "entrees",
          tuple(CON_TEXT[CON_RELIEFS[0]:CON_RELIEFS[-1] + 1])
          == ("GRASS PLANES", "DESERT", "SNOW AND ICE", "ROCKY"))
    check("L12440-L12443 : les cinq vitesses suivent",
          tuple(CON_TEXT[CON_VITESSES[0]:CON_VITESSES[-1] + 1])
          == ("VERY SLOW", "SLOW", "MEDIUM", "FAST", "VERY FAST"))
    check("L12466-L12470 : les cinq niveaux suivent",
          tuple(CON_TEXT[CON_NIVEAUX[0]:CON_NIVEAUX[-1] + 1])
          == ("VERY POOR", "POOR", "AVERAGE", "GOOD", "VERY GOOD"))
    check("L12488-L12503 : les quatre regles de construction",
          tuple(CON_TEXT[14:18])
          == ("CANNOT BE BUILT", "BUILT JUST ON TOWNS", "ONLY BUILT UP",
              "BUILT ON PEOPLE"))
    check("L12522-L12527 : les deux etats des marais",
          tuple(CON_TEXT[18:20]) == ("SHALLOW", "BOTTOMLESS"))
    check("L21347-L21352 : `strYes` est ecrit $59 $45 $53 et `strNo` "
          "$4e $4f, chacun suivi d'un zero",
          CON_TEXT[22] == "YES" and CON_TEXT[23] == "NO"
          and mem[table[22][1] + 3] == 0 and mem[table[23][1] + 2] == 0,
          "%r / %r" % (CON_TEXT[22], CON_TEXT[23]))

    # ---- `_put_in_string` (L12163-12186) --------------------------------
    def ligne(prefixe, n, texte, fond="", taille=40):
        """Une ligne de 40 octets, puis `_put_in_string` dessus."""
        buf = bytearray(prefixe.encode("latin-1"))
        buf += b"\x00" * (taille - len(buf))
        if fond:                                  # remplissage non nul,
            for i in range(len(prefixe), len(buf)):   # pour voir le debordement
                buf[i] = ord(fond)
        put_in_string(buf, n, texte)
        return bytes(buf).split(b"\x00")[0].decode("latin-1")

    check("L12173-L12184 : a la colonne 0, la valeur remplace tout",
          ligne("", 0, "ABC", ".") == "ABC", repr(ligne("", 0, "ABC", ".")))
    check("L12166-L12171 : le decompte est un DECALAGE en colonne, ce qui "
          "precede est conserve",
          ligne("XX", 4, "ABC", ".") == "XX..ABC",
          repr(ligne("XX", 4, "ABC", ".")))
    check("L12166-L12171 : le libelle fixe garde son espace final quand on "
          "ecrit juste apres",
          ligne("XX ", 3, "ABC") == "XX ABC", repr(ligne("XX ", 3, "ABC")))
    check("L12184 : une chaine vide laisse le libelle fixe intact",
          ligne("XX", 2, "") == "XX", repr(ligne("XX", 2, "")))

    # le debordement : le tampon fait 40 octets, donc une valeur trop longue
    # pour la colonne est coupee, comme le serait un `strcpy`.
    check("un debordement est tronque au tampon de 40 octets",
          ligne("." * 36, 36, "ABCDEFG") == "." * 36 + "ABCD",
          repr(ligne("." * 36, 36, "ABCDEFG")))
    check("une valeur qui deborde ne depasse jamais la garde de 40",
          len(ligne("." * 30, 30, "X" * 40)) <= 40,
          repr(ligne("." * 30, 30, "X" * 40)))

    # le cas reel : `_put_in_string(ligne, LAB_51EEE[i], libelle)` sur une
    # ligne deja remplie par le libelle fixe de `strWorldToConquer`. Le champ
    # `LAB_51EEE[i]` vaut la largeur de la colonne - le libelle fixe garde
    # donc son espace final, et la valeur vient a la suite.
    from populous.world import WORLD_TEXTE, WORLD_W
    for i, valeur in ((6, "SHALLOW"), (3, "MEDIUM"), (1, "7")):
        attendu = WORLD_TEXTE[i] + valeur
        obtenu = ligne(WORLD_TEXTE[i], WORLD_W[i], valeur)
        check("L12433-12435 : `%s` + `%s` a la colonne %d"
              % (WORLD_TEXTE[i].rstrip(), valeur, WORLD_W[i]),
              obtenu == attendu, "obtenu %r, attendu %r" % (obtenu, attendu))
        check("L12433-12435 : la colonne %d vaut la largeur du libelle fixe "
              "`%s`" % (WORLD_W[i], WORLD_TEXTE[i].rstrip()),
              WORLD_W[i] == len(WORLD_TEXTE[i]),
              "%d != %d" % (WORLD_W[i], len(WORLD_TEXTE[i])))

    print("\n%d controles, %d echec(s)" % (TOTAL[0], KO[0]))
    return 1 if KO[0] else 0


if __name__ == "__main__":
    sys.exit(main())
