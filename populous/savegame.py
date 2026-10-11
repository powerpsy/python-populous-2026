# -*- coding: utf-8 -*-
"""Format du fichier de sauvegarde — ``_save_game`` (asm L17123-17373).

Le format est ecrit **champ par champ** dans le listing, avec la taille de
chaque `Write` comparee a la valeur demandee. Il est donc entierement connu :
25 ecritures, dans un ordre impose, 29 646 octets au total.

| # | source | taille | contenu |
|---|---|---|---|
| 1 | `(-8,A5)` | 4 | la constante `$FFFFB615` (L17125) |
| 2 | `_alt` | `$2102` | 4225 sommets x 16 bits (65 x 65) |
| 3 | `_map_alt` | `$1000` | altitude d'affichage, 64 x 64 octets |
| 4 | `_map_blk` | `$1000` | `_map_blk` |
| 5 | `_map_bk2` | `$1000` | `_map_bk2` |
| 6 | `_map_who` | `$1000` | `_map_who` |
| 7 | `_magnet` | `$20` | 16 mots |
| 8 | `_peeps` | `$1222` | 211 peeps x 22 octets |
| 9 | `_stats` | `$2E` | la fiche de la tribu 0 |
| 10 | `strABC` | `$2E` | la fiche de la tribu 1 |
| 11 | `_mode` | 2 | |
| 12 | `_seed` | 2 | |
| 13 | `_start_seed` | 2 | |
| 14 | `_player` | 2 | |
| 15 | `_ground_in` | 2 | |
| 16 | `_war` | 2 | |
| 17 | `_game_turn` | 2 | |
| 18 | `_conquest` | `$A` | 5 mots |
| 19 | `_in_conquest` | 2 | |
| 20 | `_paint_map` | 2 | |
| 21 | `_battle_won` | 4 | un long |
| 22 | `_game_mode` | 2 | |
| 23 | `_level_number` | 2 | |
| 24 | `_score` | 4 | un long |
| 25 | `(-14,A5)` | 2 | le checksum du terrain |

**Le checksum du terrain** (L17161-17189) est ecrit deux fois : une fois dans
la variable globale `_land_checksum`, une fois en **dernier** champ du fichier.
C'est lui que `_load_game` relit pour verifier que le terrain a bien ete
sauvegarde avec le bon relief :

```python
total  = _checksum(alt, 0x1081)      # 4225 mots... non, 4225 itérations
total += _checksum(map_alt, 0x800)
total += _checksum(map_blk, 0x800)
total += _checksum(map_bk2, 0x800)
total += _checksum(map_who, 0x800)
total += (good_pop + bad_pop) & 0xFFFF    # L17186-17188
```

Noter le `$1081` de `_alt` : c'est **4225**, un nombre impair, alors que la
lecture se fait par mots a l'adresse `base + 2*i` (L17395-17398). La boucle
tourne donc jusqu'a `i = 4224` et lit deux octets a partir de l'offset 4224 —
le deuxieme sort du bloc ecrit de `$2102` octets, sans consequence en RAM.
Reproduit tel quel.

**Le nom du fichier** (L17130-17153) recoit systematiquement le suffixe
`.GAM` : si le nom fait moins de quatre caracteres, on concatene `.GAM` ; sinon
on ne le fait que si `name[4:] != ".GAM"`.

**La valeur de retour** est inversee par rapport a l'usage : `_save_game`
renvoie **0** en cas de succes et **1** en cas d'echec. L'echec est
l'absence du `Open` (L17159-17160) **ou** une ecriture de taille incorrecte
(LAB_4AE00). `(-12,A5)` vaut 1 au depart (L17126) et n'est mis a zero qu'apres
le dernier `Write` reussi (L17365).

La verification est dans ``tools/check_savegame.py``, qui relit la liste des
25 `Write` directement dans le listing.
"""

# le mot d'en-tete, ecrit en premier (L17125)
MAGIE = 0xFFFFB615

# suffixe ajoute au nom du fichier (L17133, L17143, L17150)
SUFFIXE = ".GAM"

# les 25 ecritures, dans l'ordre exact du listing :
# ( etiquette, source d'asm, taille en octets, ligne de listing )
CHAMPS = [
    ("magic",      "(-8,A5)",     0x0004, 17190),
    ("alt",        "(_alt,A4)",         0x2102, 17197),
    ("map_alt",    "(_map_alt,A4)",     0x1000, 17204),
    ("map_blk",    "(_map_blk,A4)",     0x1000, 17211),
    ("map_bk2",    "(_map_bk2,A4)",     0x1000, 17218),
    ("map_who",    "(_map_who,A4)",     0x1000, 17225),
    ("magnet",     "(_magnet,A4)",      0x0020, 17232),
    ("peeps",      "(_peeps,A4)",       0x1222, 17239),
    ("stats0",     "(_stats,A4)",       0x002E, 17246),
    ("stats1",     "(strABC,A4)",       0x002E, 17253),
    ("mode",       "(_mode,A4)",        0x0002, 17260),
    ("seed",       "(_seed,A4)",        0x0002, 17267),
    ("start_seed", "(_start_seed,A4)",  0x0002, 17274),
    ("player",     "(_player,A4)",      0x0002, 17281),
    ("ground_in",  "(_ground_in,A4)",   0x0002, 17288),
    ("war",        "(_war,A4)",         0x0002, 17295),
    ("game_turn",  "(_game_turn,A4)",   0x0002, 17302),
    ("conquest",   "(_conquest,A4)",    0x000A, 17309),
    ("in_conquest", "(_in_conquest,A4)",  0x0002, 17316),
    ("paint_map",  "(_paint_map,A4)",   0x0002, 17323),
    ("battle_won", "(_battle_won,A4)",  0x0004, 17330),
    ("game_mode",  "(_game_mode,A4)",   0x0002, 17337),
    ("level_number", "(_level_number,A4)",  0x0002, 17344),
    ("score",      "(_score,A4)",       0x0004, 17351),
    ("checksum",   "(-14,A5)",    0x0002, 17358),
]

# taille totale du fichier
TAILLE = sum(c[2] for c in CHAMPS)

# les blocs passes a `_checksum` (L17161-17185) et l'ordre des additions
# (L17186-17188) : les quatre cartes d'abord, la somme des populations
# ensuite.
BLOCS_CHECKSUM = [
    ("alt",     0x1081),   # 4225 : impair, la boucle lit un mot de trop
    ("map_alt", 0x0800),
    ("map_blk", 0x0800),
    ("map_bk2", 0x0800),
    ("map_who", 0x0800),
]


def checksum(data: bytes, n_octets: int) -> int:
    """``_checksum(pointeur, n_octets)`` (L17389-17407).

    .. code-block:: none

        s = 0; i = 0
        while i != n_octets:
            s += mot_be(pointeur + 2*i)   # MOVE.W (0,A0,D0.L)
            i += 1                      # ADDQ.L #1
        return s

    Le compteur est un **long** (`(-6,A5)`) mais l'adresse est formee par
    ``ASL.L #1``, donc l'index avance de deux a chaque tour. La comparaison
    finale est faite avec ``CMP.L``, sur le nombre d'**octets** : la boucle
    fait donc ``n_octets / 2`` iterations quand `n_octets` est pair, et une de
    plus, lisant un octet de plus, quand il est impair — comme `$1081`.

    La somme est un mot : `ADD.W` (L17399) et `ADD.W D0,(-14,A5)` (L17170...)
    travaillent sur 16 bits.

    Le compteur est un long mais l'adresse est formee par `ASL.L #1` : la
    boucle fait donc `n_octets` iterations et lit les mots a `0, 2, 4, ...`
    jusqu'a `2*n_octets - 2`. Le tampon doit donc faire au moins
    `2 * n_octets` octets - ce qui est le cas de tous les blocs du listing
    (`_alt` : 4225 iterations pour `$2102 = 8450` octets).
    """
    if len(data) < 2 * n_octets:
        raise ValueError("checksum : tampon de %d octets pour %d iterations "
                         "(il en faut %d)" % (len(data), n_octets,
                                              2 * n_octets))
    s = 0
    for i in range(n_octets):
        j = i * 2
        s = (s + ((data[j] << 8) | data[j + 1])) & 0xFFFF
    return s


def terrain_checksum(blocs: dict) -> int:
    """Le checksum du terrain (L17161-17189). Rend un mot de 16 bits."""
    total = 0
    for nom, n in BLOCS_CHECKSUM:
        total = (total + checksum(blocs[nom], n)) & 0xFFFF
    # L17186-17188 : `D0 = good_pop ; D0 += bad_pop ; ADD.W D0,(-14,A5)`
    return (total + (blocs["good_pop"] + blocs["bad_pop"])) & 0xFFFF


def nom_de_fichier(nom: str) -> str:
    """Le nom du fichier (L17130-17153) : suffixe `.GAM`, une seule fois."""
    if len(nom) >= 4:
        if nom[4:] == SUFFIXE:      # `strcmp(name+4, strGAM1) == 0`
            return nom              # LAB_4AAB8 : rien a faire
        return nom + SUFFIXE        # L17143-17146
    return nom + SUFFIXE            # L17150-17153