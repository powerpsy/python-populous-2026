# -*- coding: utf-8 -*-
"""Controle du format de sauvegarde — `_save_game` (asm L17123-17373).

Ce script relit la liste des ecritures **dans le listing** : pour chaque
`___Write(handle, source, taille)` de la routine, il extrait la taille et la
source reelles, et les compare a la copie transcrite dans
`populous/savegame.py`. Une divergence est un echec, pas une notice.

Il verifie aussi `_checksum` (L17389) et les quatre blocs qu'elle recoit
(L17161-17185).

Usage::

    python tools/check_savegame.py
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


def check(label: str, cond: bool, detail: str = "") -> None:
    TOTAL[0] += 1
    if not cond:
        KO[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "KO", label,
                           ("  -> " + detail) if detail else ""))


def lignes():
    return io.open(ASM, "r", encoding=ENC, newline="").read().splitlines()


def texte(l: str) -> str:
    return l.split(";")[0].strip()


# le listing ecrit la taille soit en hexadécimal (`PEA $2102.W`), soit en
# décimal (`PEA 2.W`) selon la constante ; les deux sont admises.
PEA_TAILLE = re.compile(r"^PEA\s+(\$[0-9a-fA-F]+|[0-9]+)\.W$")


def extraire_writes(debut: int, fin: int):
    """(taille, source, ligne) pour chaque `___Write` entre deux lignes."""
    ls = lignes()
    out = []
    for k in range(debut - 1, fin):
        m = PEA_TAILLE.match(texte(ls[k]))
        if m is None:
            continue
        taille = int(m.group(1).lstrip("$"), 16) \
            if m.group(1).startswith("$") else int(m.group(1))
        # la source est la ligne suivante, le handle celle d'apres, puis le JSR
        src = re.match(r"^PEA\s+(.+)$", texte(ls[k + 1]))
        ecri = re.match(r"^JSR\s+\(_Write,PC\)$", texte(ls[k + 3]))
        if not src or not ecri:
            continue
        out.append((taille, src.group(1), k + 1))
    return out


def extraire_checksums(debut: int, fin: int):
    ls = lignes()
    out = []
    for k in range(debut - 1, fin):
        m = PEA_TAILLE.match(texte(ls[k]))
        if m is None:
            continue
        n = int(m.group(1).lstrip("$"), 16) \
            if m.group(1).startswith("$") else int(m.group(1))
        src = re.match(r"^PEA\s+\((.+),A4\)$", texte(ls[k + 1]))
        if not src:
            continue
        if not re.match(r"^JSR\s+\(_checksum,PC\)$", texte(ls[k + 2])):
            continue
        out.append(("(%s,A4)" % src.group(1), n, k + 1))
    return out


def _refuse_trop_court() -> bool:
    """`_checksum` ne doit jamais lire hors du tampon."""
    from populous.savegame import checksum
    try:
        checksum(b"\x00\x00" * 2, 8)
    except ValueError:
        return True
    return False


def main() -> int:
    from populous.savegame import (BLOCS_CHECKSUM, CHAMPS, MAGIE, SUFFIXE,
                                   TAILLE, checksum, nom_de_fichier,
                                   terrain_checksum)

    # ---- les 25 `Write` de `_save_game` ---------------------------------
    brut = extraire_writes(17188, 17365)
    print("`Write` releves : %d (attendus %d)" % (len(brut), len(CHAMPS)))
    check("L17190-17364 : la routine ecrit exactement 25 champs",
          len(brut) == len(CHAMPS) == 25,
          "%d releves, %d transcrits" % (len(brut), len(CHAMPS)))

    for i, (taille, src, ligne) in enumerate(brut):
        if i >= len(CHAMPS):
            break
        nom, port_src, port_taille, port_ligne = CHAMPS[i]
        check("champ %2d $%04X %-12s (L%d)" % (i, taille, src, ligne),
              (port_taille, port_src, port_ligne) == (taille, src, ligne),
              "port $%04X %s L%d" % (port_taille, port_src, port_ligne))

    # ---- la taille totale ------------------------------------------------
    total_asm = sum(t for t, _, _ in brut)
    check("L17190-17364 : le fichier fait %d octets" % total_asm,
          TAILLE == total_asm,
          "port : %d" % TAILLE)

    # ---- les quatre blocs de `_checksum` --------------------------------
    blocs = extraire_checksums(17160, 17190)
    print("`_checksum` appele %d fois (attendus %d)"
          % (len(blocs), len(BLOCS_CHECKSUM)))
    for i, (src, n, ligne) in enumerate(blocs):
        nom, port_n = BLOCS_CHECKSUM[i]
        gote = [c for c in CHAMPS if c[1] == src]
        check("checksum %d : %s sur $%04X (L%d)" % (i, src, n, ligne),
              port_n == n and gote and gote[0][0] == nom,
              "port %s = $%04X" % (nom, port_n))

    check("L17171-17182 : les quatre cartes sont chacune en $800",
          [n for _, n, _ in blocs[1:]] == [0x800, 0x800, 0x800, 0x800])
    check("L17161 : `_alt` est passe sur $1081 = 4225, un nombre impair",
          blocs[0][1] == 0x1081 == 4225, "$%04X" % blocs[0][1])

    # ---- `_checksum` elle-meme -------------------------------------------
    # la boucle fait `n` iterations et lit les mots a 0, 2, 4, ... : le
    # tampon doit faire 2n octets (ASL.L #1 sur l'adresse, L17396).
    check("L17389 : la somme est initialisee a zero",
          checksum(b"\x00\x00" * 4, 4) == 0,
          "0x%04X" % checksum(b"\x00\x00" * 4, 4))
    check("L17395-17399 : quatre mots $FFFF donnent $FFFC, en 16 bits",
          checksum(b"\xff\xff" * 4, 4) == 0xFFFC,
          "0x%04X" % checksum(b"\xff\xff" * 4, 4))
    # $1081 : 4225 iterations sur 8450 octets
    n = 0x1081
    donnees = bytes((i * 37) & 0xFF for i in range(2 * n))
    attendu = 0
    for i in range(n):
        j = i * 2
        attendu = (attendu + ((donnees[j] << 8) | donnees[j + 1])) & 0xFFFF
    check("L17395-17404 : $1081 itere 4225 fois sur 8450 octets",
          checksum(donnees, n) == attendu,
          "0x%04X contre 0x%04X" % (checksum(donnees, n), attendu))
    check("L17389 : un tampon trop court est refuse, pas tronque",
          _refuse_trop_court(),
          "aucune erreur levee")

    # le checksum du terrain, ordre des additions compris
    faux = {nom: bytes(2 * n) for nom, n in BLOCS_CHECKSUM}
    faux["alt"] = b"\xff\xff" * 0x1081               # 4225 mots $FFFF
    faux["map_blk"] = b"\x00\x01" * 0x800            # 2048 mots $0001
    faux["good_pop"], faux["bad_pop"] = 0x1234, 0x1111
    # attendu, recalcule sans passer par `checksum` : 4225 mots $FFFF, puis
    # 2048 mots $0001 sur map_blk, le reste a zero.
    def somme_mots(nb, mot):
        return (nb * mot) & 0xFFFF

    attendu_terrain = somme_mots(0x1081, 0xFFFF)
    attendu_terrain = (attendu_terrain + somme_mots(0x800, 0x0001)) & 0xFFFF
    attendu_terrain = (attendu_terrain + 0x1234 + 0x1111) & 0xFFFF
    check("L17161-17188 : les quatre cartes puis les populations, dans "
          "l'ordre",
          terrain_checksum(faux) == attendu_terrain,
          "0x%04X contre 0x%04X" % (terrain_checksum(faux), attendu_terrain))

    # ---- l'en-tete et le suffixe -----------------------------------------
    ls = lignes()
    tete = [texte(l) for l in ls if re.match(r"^MOVE\.L\s+#\$ffff[0-9a-f]{4},\(-8,A5\)",
                                             texte(l))]
    check("L17125 : le mot d'en-tete vaut $FFFFB615",
          tete == ["MOVE.L\t#$ffffb615,(-8,A5)"] and MAGIE == 0xFFFFB615,
          "listing : %s" % (tete or "absent"))
    for ligne in (17377, 17381, 17385):
        m = re.search(r'DC\.B\s+"([^"]*)"', ls[ligne - 1])
        check("L%d : le suffixe du fichier vaut `.GAM`" % ligne,
              m and m.group(1).startswith(".GAM"),
              "listing : %r" % (m.group(1) if m else None))
    check("le suffixe transcrit est `.GAM`", SUFFIXE == ".GAM")

    # ---- le nom de fichier (L17130-17153) --------------------------------
    check("L17136-17140 : un nom deja en `.GAM` n'est pas re-suffixe",
          nom_de_fichier("save.GAM") == "save.GAM")
    check("L17143-17146 : un nom sans `.GAM` en recoit un",
          nom_de_fichier("save") == "save.GAM")
    check("L17135-17137 : le suffixe commence a l'octet 4, pas 3",
          nom_de_fichier("abc.GAM") == "abc.GAM.GAM",
          "abc.GAM -> %r" % nom_de_fichier("abc.GAM"))
    check("L17150-17153 : un nom de moins de quatre caracteres est suffixe",
          nom_de_fichier("ab") == "ab.GAM")

    print("\n%d controles, %d echec(s)" % (TOTAL[0], KO[0]))
    return 1 if KO[0] else 0


if __name__ == "__main__":
    sys.exit(main())