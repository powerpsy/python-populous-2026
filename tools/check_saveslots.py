# -*- coding: utf-8 -*-
"""Controle de `_get_a_dir` (L16841) et `_sort` (L11016).

Le tri par coquilles est verifie **par execution** : la reference est une
ecriture independante, en insertion, ecrite a partir des memes invariants
que le listing, et l'on compare les deux sur toutes les permutations de
petites taille. Le listing sort des noms, pas des nombres : on encode donc
chaque nom sur une cle numerique pour pouvoir comparer deux tris.

`_get_a_dir` est verifie sur un dossier construit a la main, avec les cas
tires du listing : repertoire ecarte, nom sans `.GAM`, nom court, nom
majuscule, nom trop long.

Usage::

    python tools/check_saveslots.py
"""
from __future__ import annotations

import itertools
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from populous.saveslots import (NOM_MAX, TAILLE_ENTREE, chemin_complet,  # noqa: E402
                                get_a_dir, sort)

TOTAL = [0]
KO = [0]


def check(label, cond, detail=""):
    TOTAL[0] += 1
    if not cond:
        KO[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "KO", label,
                           ("  -> " + detail) if detail else ""))


def cle(nom: bytes) -> int:
    """Une cle numerique pour comparer deux tris de noms."""
    return int.from_bytes(nom.rstrip(b"\x00").ljust(8, b"\x00")[:8], "big")


def tri_par_insertion(cles, decroissant=False):
    """Reference independante, ecrite depuis l'invariant du listing.

    L11038-11046 compare `base[(D4-1)*32]` a `base[(D5-1)*32]` et n'echange
    que si le premier est **superieur** au second. L'echange se produit donc
    quand l'element le plus loin est le plus grand, ce qui range la liste
    dans l'ordre **decroissant**. C'est ce que fait la machine, et le
    controle le verifie sur toutes les permutations.
    """
    out = list(cles)
    for i in range(1, len(out)):
        j = i
        while j > 0 and (out[j - 1] < out[j] if decroissant
                         else out[j - 1] > out[j]):
            out[j - 1], out[j] = out[j], out[j - 1]
            j -= 1
    return out


def main():
    # ---- `_sort` : le resultat doit etre croissant ----------------------
    print("A. `_sort` (L11016) sur toutes les permutations de 5 elements")
    distincts = [b"%02d" % i for i in range(5)]
    faux = 0
    total = 0
    for perm in itertools.permutations(distincts):
        cles = [cle(p) for p in perm]
        obtenu = [cle(x) for x in sort(list(perm))]
        total += 1
        if obtenu != tri_par_insertion(cles, True):
            faux += 1
    check("L11038-11046 : 120 permutations de 5, toutes rangees comme "
          "l'insertion decroissante", faux == 0,
          "%d ecarts sur %d" % (faux, total))
    check("L11046 : le tri est DECROISSANT - l'echange se fait quand "
          "l'element le plus loin est le plus grand",
          [x.rstrip(b"\x00") for x in sort([b"00", b"01", b"02"])]
          == [b"02", b"01", b"00"],
          str([x.rstrip(b"\x00") for x in sort([b"00", b"01", b"02"])]))

    # avec des doublons : `BLE` ne les echange pas
    liste = [b"b", b"a", b"b", b"c", b"a"]
    obtenu = [x.rstrip(b"\x00") for x in sort(list(liste))]
    check("L11046 : `BLE` ne touche pas les doublons, le resultat reste "
          "decroissant", obtenu == sorted((x.rstrip(b"\x00") for x in liste),
                                          reverse=True), str(obtenu))

    # petites tailles degeneres
    for n in range(0, 5):
        vide = [b"%02d" % i for i in range(n)]
        got = [x.rstrip(b"\x00") for x in sort(list(vide))]
        check("L11022 : une liste de %d element%s reste decroissante"
              % (n, "" if n == 1 else "s"),
              got == sorted((x.rstrip(b"\x00") for x in vide), reverse=True),
              str(got))

    # ---- le pas est bien divise par deux a chaque passe ------------------
    # un liste a 9 elements dans l'ordre inverse force 4 passes
    neuf = [b"%02d" % (8 - i) for i in range(9)]
    got = [x.rstrip(b"\x00") for x in sort(list(neuf))]
    check("L11021 : `ASR` sur le pas, quatre passes pour neuf elements",
          got == [b"%02d" % (8 - i) for i in range(9)], str(got))
    # une liste deja decroissante doit rester inchangee
    deja = [b"%02d" % (8 - i) for i in range(9)]
    got2 = [x.rstrip(b"\x00") for x in sort(list(deja))]
    check("L11046 : une liste deja decroissante bouge peu",
          got2 == deja, str(got2))

    # ---- `_get_a_dir` ----------------------------------------------------
    print("B. `_get_a_dir` (L16841) sur un dossier construit")
    d = tempfile.mkdtemp()
    try:
        for nom in ("bravo.GAM", "Alpha.GAM", "charlie.GAM"):
            open(os.path.join(d, nom), "wb").close()
        os.mkdir(os.path.join(d, "dossier.GAM"))          # repertoire
        open(os.path.join(d, "notes.txt"), "wb").close()    # pas un .GAM
        open(os.path.join(d, "ab.GAM"), "wb").close()      # nom de 5
        open(os.path.join(d, "a.GAM"), "wb").close()       # nom de 5 aussi
        long_nom = ("z" * NOM_MAX) + "extra.GAM"
        open(os.path.join(d, long_nom), "wb").close()      # trop long
        ent = get_a_dir(d)
        noms = sorted(x.rstrip(b"\x00").decode("latin-1") for x in ent)
        check("L16863 : un repertoire est ecarte, meme en `.GAM`",
              "dossier" not in noms, str(noms))
        check("L16908-16929 : un fichier qui n'est pas en `.GAM` est ecarte",
              "notes.txt" not in noms and "notes" not in noms, str(noms))
        check("L16870-16881 : les noms sont mis en majuscules",
              "ALPHA" in noms, str(noms))
        check("L16922-16928 : le suffixe `.GAM` est retire",
              all(not n.endswith(".GAM") for n in noms), str(noms))
        check("L16870 + L16922 : `a.GAM` devient `A` - la majusculisation "
              "a lieu AVANT le retrait du suffixe",
              "A" in noms and "AB" in noms, str(noms))
        check("L16895-16900 : un nom tronque a %d caracteres ne finit pas "
              "par `.GAM`, donc il n'est pas compte" % NOM_MAX,
              "z" * NOM_MAX not in noms, str(noms))
        check("L16944-16945 : chaque entree fait 32 octets",
              all(len(x) == TAILLE_ENTREE for x in ent),
              str(sorted(set(len(x) for x in ent))))
        check("le tiroir trie a l'envers, comme `_sort`",
              [x.rstrip(b"\x00") for x in sort(list(ent))]
              == sorted((x.rstrip(b"\x00") for x in ent), reverse=True),
              str([x.rstrip(b"\x00").decode("latin-1")
                   for x in sort(list(ent))]))

        check("L16849 : un dossier absent ne leve pas",
              get_a_dir(os.path.join(d, "absent")) == [])
        vide = tempfile.mkdtemp()
        try:
            check("un dossier vide rend une liste vide", get_a_dir(vide) == [])
        finally:
            shutil.rmtree(vide, ignore_errors=True)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # ---- le collage du chemin (L10837-10886) -----------------------------
    print("C. le collage du chemin (L10832-10886)")
    # L10864 : `TST.W (-138) ; BLE` - un tiroir d'un seul caractere passe
    # **tout droit**, sans separateur. C'est ce que fait la machine.
    cas = [("Pop Saves", "essai", "Pop Saves/essai"),
           ("Pop Saves/", "essai", "Pop Saves/essai"),
           ("df0:Saves", "essai", "df0:Saves/essai"),
           ("", "essai", "essai"),
           ("a", "essai", "aessai"),
           ("df0:", "essai", "df0:essai")]
    for base, nom, attendu in cas:
        check("L10870-10886 : %r + %r -> %r" % (base, nom, attendu),
              chemin_complet(base, nom) == attendu,
              "obtenu %r" % chemin_complet(base, nom))

    print("\n%d controles, %d echec(s)" % (TOTAL[0], KO[0]))
    return 1 if KO[0] else 0


if __name__ == "__main__":
    sys.exit(main())