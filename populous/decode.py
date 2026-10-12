# -*- coding: utf-8 -*-
"""`_decode` (asm L14900-15119) : le nom d'un monde, ramene a son indice.

L'ecran *WORLD TO CONQUER* accepte deux formes de saisie (L12262-12312) :

* un entier -> c'est une **graine** : `_start_seed = _seed = n`, et
  ``_show_world`` rend -1 sans lire ``level.dat`` (L12270-12273) ;
* sinon c'est un **nom**, qui passe par ``_decode`` : trois syllabes
  collées sans espace, choisies dans trois tables de 32, comme
  ``RINGVERYHILL`` ou ``SHADIEOLD``.

Le nom code **15 bits**, cinq bits par syllabe :

.. code-block:: none

    code = depart | milieu << 5 | fin << 10     (L1491FC, L15002, L15099)

Ces 15 bits sont ensuite cherches parmi les 1001 **graines** valides :
``_seed = 0, 5, 10, ... 5000`` puis ``_newrand()`` ; la premiere dont la
sortie egale ``code`` rend sa graine (L15104-15117). C'est pourquoi la
legende du listing dit *« 1,000 valid level codes - calculated by
advancing the random seed each time and adding 5 »*.

Les cinq retours negatifs du listing sont conserves tels quels :

===== ================================ ==========================
Code  Cause                            Ligne
===== ================================ ==========================
-1    aucune syllabe de depart          L14962
-2    aucune syllabe du milieu          L15023
-3    aucune syllabe de fin             L15085
-4    le nom est plus long que les 3    L15093
-5    aucune graine ne donne ce code    L15118
===== ================================ ==========================

La comparaison se fait **octet par octet** contre la fin de la syllabe
(``TST.B`` puis ``CMP.W`` sur un octet etendu, L14919-L14939) : un nom
tronque comme ``RIN`` ne correspond donc pas a ``RING``, puisque la
syllabe a encore un caractere et que le zero de fin de ``s`` ne vaut pas
``G``. La boucle avance `D5` tant que les caracteres sont egaux, puis
rend la main sur ``LAB_49134`` - soit le mot consomme entier, soit un
desaccord qui fait passer au syllabe suivante.

La verification est dans ``tools/check_decode.py``.
"""
from __future__ import annotations

#: ``_start`` (asm L25075-25107, $52972) - 32 syllabes de depart.
START = (
    "RING", "VERY", "KILL", "SHAD", "HURT", "WEAV", "MIN", "EOA",
    "COR", "JOS", "ALP", "HAM", "BUR", "BIN", "TIM", "BAD",
    "FUT", "MOR", "SAD", "CAL", "IMM", "SUZ", "NIM", "LOW",
    "SCO", "HOB", "DOU", "BIL", "QAZ", "SWA", "BUG", "SHI",
)

#: ``_mid`` (asm L25141-25173, $52a72) - 32 syllabes de milieu.
MID = (
    "OUT", "QAZ", "ING", "OGO", "QUE", "LOP", "SOD", "HIP",
    "KOP", "WIL", "IKE", "DIE", "IN", "AS", "MP", "DI",
    "OZ", "EA", "US", "GB", "CE", "ME", "DE", "PE",
    "OX", "A", "E", "I", "O", "U", "T", "Y",
)

#: ``_end`` (asm L25108-25140, $529f2) - 32 syllabes de fin.
END = (
    "HILL", "TORY", "HOLE", "PERT", "MAR", "CON", "LOW", "DOR",
    "LIN", "ING", "HAM", "OLD", "PIL", "BAR", "MET", "END",
    "LAS", "OUT", "LUG", "ILL", "ICK", "PAL", "DON", "ORD",
    "OND", "BOY", "JOB", "ER", "ED", "ME", "AL", "T",
)

NB = 32                  # `CMP.W #$0020,D4 ; BCS` (L14956)
GRAINES_MAX = 0x1388     # 5000, `CMP.W #$1388,D4 ; BLS` (L15117)
GRAINES_PAS = 5          # `ADDQ.W #5,D4` (L15114)


def _octet(texte: str, i: int) -> int:
    """Le caractere `i`, ou 0 au-dela du zéro de fin (`TST.B` sur `s`)."""
    if 0 <= i < len(texte):
        return ord(texte[i])
    return 0


def _passe(table, texte: str, pos: int):
    """Un passage de `_decode` : ``assemblage_de_code(texte[pos:])``.

    Renvoie ``(index, nouvelle_pos)``. L'index vaut 32 quand **aucune**
    syllabe ne correspond - c'est ``LAB_4915C`` (`CMP.W #$0020,D4`).
    ``nouvelle_pos`` n'avance que sur une correspondance complete
    (``ADD.W D5,(-4,A5)``, L14951).
    """
    d4 = 0
    while d4 < NB:
        mot = table[d4]
        d5 = 0
        while True:
            if d5 >= len(mot):              # `TST.B (mot,D5)` == 0
                return d4, pos + d5         # L14949-14951 : mot consomme
            if _octet(texte, pos + d5) != ord(mot[d5]):
                break                       # `CMP.W D1,D0 ; BNE` (L14938)
            d5 += 1                         # `ADDQ.W #1,D5` (L14909)
        d4 += 1                             # L14954
    return NB, pos


def _graine(code: int, jeu=None):
    """La recherche de graine (L15104-15119).

    ``_seed`` est ecrit **a chaque tentative** : le port le refait aussi,
    car c'est l'effet de bord visible de la routine - au retour, `jeu.seed`
    vaut le tirage effectue pour la derniere tentative.
    """
    from populous.rng import Rng
    g = 0
    while True:
        if jeu is not None:
            jeu.seed = g                     # `MOVE.W D4,(_seed)` (L15106)
        rng = Rng(g)
        valeur = rng.raw() & 0xFFFF          # `JSR ___newrand ; MOVE.W D0,D5`
        if jeu is not None:
            jeu.seed = rng.seed              # `_seed` a deja avance
        if valeur == code:
            return g                         # L15111-15112 : `MOVE.W D4,D0`
        g += GRAINES_PAS                     # L15114
        if g > GRAINES_MAX:
            return -5                        # L15118


def decode(texte: str, jeu=None) -> int:
    """``_decode(texte)`` (asm L14900-15119).

    ``jeu`` est l'objet dont la graine est manipulee : L15106 ecrit
    `_seed` au fil de la recherche. L'argument est facultatif pour les
    tests, qui n'ont pas d'etat a observer.

    Les 1001 noms valides sont obtenus a l'envers dans
    ``tools/check_decode.py`` : on prend la graine ``g``, on tire
    ``_newrand()``, on decoupe les 15 bits en trois syllabes, et on
    verifie que ``decode`` rend bien ``g``.
    """
    pos = 0
    d4, pos = _passe(START, texte, pos)          # L14905-14956
    if d4 == NB:
        return -1                                # L14962
    code = d4                                    # `MOVE.W D4,(-2)` (L14966)

    d4, pos = _passe(MID, texte, pos)            # L14971-15019
    if d4 == NB:
        return -2                                # L15023
    code |= d4 << 5                              # `ASL.W #5 ; OR.W` (L15026-15028)

    d4, pos = _passe(END, texte, pos)            # L15031-15081
    if d4 == NB:
        return -3                                # L15085
    if len(texte) != pos:                        # `___strlen` (L15088-15094)
        return -4
    code |= d4 << 10                             # `ASL.W #10 ; OR.W` (L15096-15099)

    return _graine(code, jeu)                    # L15104-15119
