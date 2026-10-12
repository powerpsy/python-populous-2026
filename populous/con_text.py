# -*- coding: utf-8 -*-
"""Les libelles des valeurs de `level.dat` — ``_con_text`` (asm L24726).

`_show_world` (L12190) remplit son resume avec `_put_in_string`, qui ecrit
un libelle dans une ligne de `strWorldToConquer`. Le libelle vient presque
toujours de ``_con_text``, une table de **39 pointeurs** (0x5219c a 0x52238,
soit 156 octets) vers les chaines du jeu.

L'indexation est celle du listing, `ASL.L #2` puis `MOVE.L (0,A0,D0.L)` :
l'index est donc en **longs**, et non en octets.

Les chaines elles-memes sont en L21257-21392 ; les deux seules ecrites
caractere par caractere sont `strYes` (`$59 $45 $53 $00`, L21347-21348) et
`strNo` (`$4E $4F $00`, L21351-21352).

L'ordre est significatif : les quatre premiers sont les **reliefs**
(`conq_05_terrain`, L12417-12421), les cinq suivants les **vitesses**
(`conq_01_speed` indexe par `((10 - v) >> 1) + 4`, L12440-12443), puis les
cinq **niveaux** (`((10 - _conquest[0]) >> 1) + 9`, L12466-12470), puis les
quatre **regles de construction**, les deux **marais**, les deux **eaux**, et
enfin les **dieux** pour l'ecran de fin de partie (L24759-24770).

La verification est dans ``tools/check_con_text.py``.
"""
# transcrit de L24726-24770, dans l'ordre du tableau
CON_TEXT = [
    "GRASS PLANES",        # 0  conq_05_terrain  L12417
    "DESERT",              # 1
    "SNOW AND ICE",        # 2
    "ROCKY",               # 3
    "VERY SLOW",           # 4  conq_01_speed    L12440
    "SLOW",                # 5
    "MEDIUM",              # 6
    "FAST",                # 7
    "VERY FAST",           # 8
    "VERY POOR",           # 9  _conquest[0]     L12466
    "POOR",                # 10
    "AVERAGE",             # 11
    "GOOD",                # 12
    "VERY GOOD",           # 13
    "CANNOT BE BUILT",     # 14 conq_04_mode bit 2   L12488-12490
    "BUILT JUST ON TOWNS", # 15 conq_04_mode bit 4   L12493-12495
    "ONLY BUILT UP",       # 16 conq_04_mode bit 3   L12498-12500
    "BUILT ON PEOPLE",     # 17 par defaut           L12503
    "SHALLOW",             # 18 conq_04_mode bit 1 = 0   L12527
    "BOTTOMLESS",          # 19 conq_04_mode bit 1 = 1   L12524
    "HARMFUL",             # 20
    "FATAL",               # 21
    "YES",                 # 22
    "NO",                  # 23
    "MORTAL",              # 24  les divinites, L24761
    "IMMORTAL",            # 25
    "ETERNAL",             # 26
    "DEVA",                # 27
    "GREATER BEING",       # 28
    "DEITY",               # 29
    "GREATER DEITY",       # 30
    "MORTAL GOD",          # 31
    "GREATER GOD",         # 32
    "ETERNAL GOD",         # 33
    # Les cinq libelles de fin de partie (LAB_52224 a LAB_52234) sont ecrits
    # avec leurs espaces, exactement comme dans le listing. Leur bloc est
    # **contigu** - 0x4e2f2+11 = 0x4e2fd, +16 = 0x4e30d, +16 = 0x4e31d,
    # +33 = 0x4e33f - ce qui est la preuve de l'alignement.
    "WELL DONE ",                       # 34 LAB_52224
    " YOU CONQUERED ",                  # 35 LAB_52228
    " NOW BATTLE AT ",                  # 36 LAB_5222C
    "WELL DONE YOU HAVE CONQUERED EVIL",  # 37 LAB_52230
    "THE BATTLE IS OVER BUT TRY ",      # 38 LAB_52234
]

CON_FIN_PARTIE = range(34, 39)

CON_TEXT_NB = 39             # 0x9C octets / 4

# Les quatre reliefs, dans l'ordre de `conq_05_terrain`.
CON_RELIEFS = (0, 1, 2, 3)
# Les cinq vitesses : l'index est `((10 - conq_01_speed) >> 1) + 4`
# (L12440-12443), donc une vitesse de 10 donne l'index 4, « VERY SLOW ».
CON_VITESSES = (4, 5, 6, 7, 8)
# Les cinq niveaux : `((10 - _conquest[0]) >> 1) + 9` (L12466-12470).
CON_NIVEAUX = (9, 10, 11, 12, 13)


def put_in_string(ligne: bytearray, n: int, texte: str) -> None:
    """``_put_in_string(ligne, n, texte)`` (L12163-12186).

    .. code-block:: none

        while n != 0:            # LAB_46FF2, TST.W ($10,A5) ; BEQ
            ligne += b"\\x00"     #   ADDQ.L #1,(8,A5)
            n -= 1               #   SUBQ.W #1,($10,A5)
        while texte[0] != 0:     # LAB_47006, TST.B (A0) ; BEQ
            ligne.append(texte[0])
        ligne.append(0)          # LAB_47022, CLR.B (A0)

    Le premier argument est un **pointeur** (`ADDQ.L #1,(8,A5)`) et le
    second un nombre d'**octets** a sauter : la premiere boucle avance le
    pointeur de `n` sans rien ecrire. Ce n'est donc pas un remplissage de
    zéros - c'est un **décalage en colonne**. C'est `LAB_51EEE[i]` que les
    `line_N` passent, et ce champ vaut exactement la longueur du libelle
    fixe de la ligne : le zero de fin de « THE SWAMPS ARE » est donc
    **recouvert** par la valeur, ce qui est le but.

    En Python la ligne est un tampon de 40 octets déjà rempli du libelle
    fixe ; `_put_in_string` y écrit la valeur a partir de la colonne `n`
    et y remet un zero final. Un debordement est **tronque**, comme le
    serait un `strcpy` dans le tampon d'origine.
    """
    octets = texte.encode("latin-1") + b"\x00"
    for i, c in enumerate(octets):
        if n + i < len(ligne):
            ligne[n + i] = c