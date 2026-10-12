# -*- coding: utf-8 -*-
"""Le resume d'un monde — la table de ``_show_world`` (asm L12190).

`_show_world` est l'ecran *WORLD TO CONQUER* : le joueur y saisit un monde,
la routine lit `level.dat` et remplit **seize lignes** decrivant ce monde -
numero de bataille, relief, vitesse, sol, reactions, et les six puissances.

Comme partout ailleurs dans ce jeu, c'est **un seul tableau** d'entrees de
0x2E (46) octets, ici **15 entrees, 690 octets**, a partir de `_c_text`
(L24621) :

    +0x00  W   x de la ligne   (`_c_text`,     0x51eea)
    +0x02  W   y de la ligne   (`LAB_51EEC`,   0x51eec)
    +0x04  W   largeur         (`LAB_51EEE`,   0x51eee)
    +0x06  40  la chaine       (`strWorldToConquer`, 0x51ef0)

|_show_world`` ecrit chaque ligne avec ``_put_in_string`` (L12406, L12427,
...), qui y colle le nom d'une valeur de `level.dat` : le libelle est donc
la partie fixe, et `_con_text` (L24725) donne le texte de chaque valeur.

**Le point ouvert est resolu.** La boucle de L12381-L12384 annonce « loop 1 to
16 », et la boucle de trace s'arrete a `CMPI.W #$000f ; BLT` (L12742-12743) -
soit quatorze iterations, `(-20)` de 1 a 14. Le dispatch est `LAB_4760C`
(L12710-12719) :

```python
if (-20) >= 10:        # CMP.L #$0000000a ; BCC.W line_0
    return ligne_0     # le commentaire du listing dit « level 10+ = 0 »
return SAUTS[(-20)]    # dix entrees, line_0 a line_9
```

Il y a donc **quinze entrees** (0 a 14), **quatorze iterations**, et **dix
handlers** seulement : les lignes 10 a 14 - les six puissances et la ligne
YOU/HIM - passent toutes par `line_0`, avec un indice different dans
`_con_text`. Ce n'est donc pas une erreur de transcription, c'est la
machine.

La verification est dans ``tools/check_show_world.py``.
"""
# transcrit de L24621-24724
WORLD_X = [16] * 15
WORLD_Y = [10, 30, 38, 46, 54, 62, 70, 78, 88, 96, 104, 112, 120, 128, 136]
WORLD_W = [16, 17, 20, 18, 14, 5, 15, 9, 72, 120, 120, 120, 120, 120, 120]
WORLD_TEXTE = [
    "WORLD TO CONQUER",          # 0  le titre
    "BATTLE NUMBER IS ",         # 1  `(-18) / 5`, en decimal (L12388-12394)
    "WORLDS LANDSCAPE IS ",      # 2  `conq_05_terrain` (L12412-12428)
    "HIS REACTIONS ARE ",        # 3  `conq_01_speed` (L12433)
    "HIS RATING IS ",            # 4
    "LAND ",                     # 5  le relief
    "THE SWAMPS ARE ",           # 6
    "WATER IS ",                 # 7
    "               YOU    HIM",  # 8  la ligne des deux colonnes
    "POPULATION",                # 9  les six puissances, deux colonnes
    "EARTHQUAKES",
    "SWAMPS",
    "KNIGHTS",
    "VOLCANOS",
    "FLOODS",
]

WORLD_NB = 15

# La boucle de trace va de 1 a 14 (L12742-12743, `CMPI.W #$000f ; BLT`), et
# `LAB_4760C` renvoie `line_0` pour toute ligne >= 10 (L12713-12714). Donc dix
# handlers pour quatorze iterations.
WORLD_LIGNE_MAX = 14
WORLD_HANDLERS = 10

# `_requester(d_screen, $10, $18, $120, $A0, (-118), (-72))` (L12208-12215)
WORLD_BOXE = (0x10, 0x18, 0x120, 0xA0)

# Les six puissances resumees, dans l'ordre des lignes 9 a 14 : c'est
# exactement l'ordre de `power_mask` (les neuf cases de l'ecran des options
# de tribu, L13690-13710) *ramenee aux six bits du fichier de sauvegarde*.
WORLD_PUISSANCES = ("POPULATION", "EARTHQUAKES", "SWAMPS", "KNIGHTS",
                    "VOLCANOS", "FLOODS")

# L12270-L12271 : une saisie entierement numerique est prise comme une
# **graine**, pas comme un monde - `_start_seed = _seed = n`, et la routine
# rend -1 (L12273) sans jamais lire `level.dat`.
WORLD_GRAINE = -1

# Ce que fait OK a la sortie (L12762-12771) : une partie neuve a un joueur,
# avec le niveau choisi.
#
#     _player = 0 ; _not_player = 1
#     _stats[1].can_build = 1 ; _stats[0].act = 0 ; _stats[0].queued = 1
#     _stats[1].queued = 0
#     _serial_off = 1 ; _paint_map = 0 ; _war = 0
#     _level_number = monde ; et la routine rend ce monde (L12772-12773)
#
# C'est exactement la meme sequence que le demarrage d'une partie simple
# (L12762-12770), et c'est aussi ce qui pose `serial_off = 1` que la Phase 69
# a retabli.
WORLD_OK = {
    "player": 0,
    "not_player": 1,
    "can_build1": 1,
    "act0": 0,
    "queued0": 1,
    "queued1": 0,
    "serial_off": 1,
    "paint_map": 0,
    "war": 0,
}


# ------------------------------------------------------------------ chaines
# `strStartGame` (L12774) et `strNewGame` (L12778) : ce sont les **textes des
# boutons**, ecrits par `_requester` dans ses deux structures de boutons. Le
# listing les recopie a `(-72)` et `(-118)` (L12193-12200) - deux blocs de 46
# octets, soit l'ecart entre `-72` et `-118`, texte a `+6` (L789-796).
WORLD_OK_TEXTE = "START GAME"        # copie a (-72), -66 = texte
WORLD_CANCEL_TEXTE = "NEW GAME"      # copie a (-118), -112 = texte
# `strGENESIS1` (L12782), pose dans `_message` quand la boite s'ouvre (L12203).
WORLD_GENESIS = "GENESIS"
# `strNoSuchWorld` (L12790) : affiche quand `_decode` rend nul.
WORLD_PAS_DE_MONDE = "NO SUCH WORLD"
# `str_level_dat` (L12794) : le fichier ouvert en L12340.
WORLD_LEVEL_DAT = "level.dat"
# `LAB_525C8` (L24927) : seize octets $82, le trait horizontal trace au-dessus
# du champ de saisie (`___text(d, $20, $2C, ...)` L12228-12233). Le $82 est un
# glyphe du jeu, pas un caractere ASCII.
WORLD_TRAIT = "\x82" * 16
# `_blank` (L24915) : onze cares, souligne le nom saisi (L12251-12259).
WORLD_BLANK = "^" * 11


# ------------------------------------------------------------ les 15 lignes
def _valeur_5(mode: int) -> int:
    """La regle de construction : `line_5` (L12487-12503)."""
    if mode & (1 << 2):
        return 14                     # `BTST #2` -> LAB_521D4
    if mode & (1 << 4):
        return 15                     # `BTST #4` -> LAB_521D8
    if mode & (1 << 3):
        return 16                     # `BTST #3` -> LAB_521DC
    return 17                         # LAB_521E0


def _valeur_6(mode: int) -> int:
    """Les marais : `line_6` (L12521-12527)."""
    return 19 if mode & (1 << 1) else 18    # BOTTOMLESS / SHALLOW


def _valeur_7(mode: int) -> int:
    """L'eau : `line_7` (L12545-12551)."""
    return 21 if mode & (1 << 0) else 20    # FATAL / HARMFUL


def _valeur_niveau(premier: int) -> int:
    """Le niveau : `line_4` (L12465-12470), `((10 - _conquest[0]) >> 1) + 9`."""
    return ((10 - premier) >> 1) + 9


def _vitesse(speed: int) -> int:
    """La vitesse : `line_3` (L12438-12443), `((10 - speed) >> 1) + 4`."""
    return ((10 - speed) >> 1) + 4


# Les tampons de `strWorldToConquer` : la table est modifiee **en place** par
# `_put_in_string` (L12406, L12427, ...) et le resultat reste lisible ensuite.
# C'est le meme effet de bord qu'en `.data` dans l'original.
_BUF = [bytearray(t.encode("latin-1")) + bytearray(40 - len(t))
        for t in WORLD_TEXTE]


def tampons() -> list:
    """Une copie fraiche des quinze tampons (les tests en ont besoin)."""
    return [bytearray(b) for b in _BUF]


def reinit() -> None:
    """Remet `strWorldToConquer` dans son etat d'origine."""
    for i, t in enumerate(WORLD_TEXTE):
        _BUF[i][:] = bytearray(t.encode("latin-1")) + bytearray(40 - len(t))


def resumer(brut: bytes, monde: int) -> list:
    """Les quinze lignes affichees, apres `_put_in_string`.

    ``brut`` sont les dix octets lus dans ``level.dat`` (ou encore vides :
    le tampon `_conquest` est **reutilise**, L12360). ``monde`` est le
    mot `(-18)`, qui devient `_level_number` (L12771).

    Les lignes 1 a 7 sont le libelle fixe plus la valeur, colles a la
    colonne `WORLD_W[i]` - qui vaut exactement la longueur du libelle
    (16, 17, 20, 18, 14, 5, 15, 9). Les lignes 8 a 14 ne passent pas par
    `_put_in_string` : leurs valeurs sont tracees a part (`line_9` et
    `line_0` font deux ``___text`` chacun).
    """
    from populous.con_text import CON_TEXT, put_in_string

    val = {
        1: str(monde // 5),                     # `DIVS #$0005` (L12391)
        2: CON_TEXT[brut[5]],                   # conq_05_terrain
        3: CON_TEXT[_vitesse(brut[1])],         # conq_01_speed
        4: CON_TEXT[_valeur_niveau(brut[0])],   # _conquest[0]
        5: CON_TEXT[_valeur_5(brut[4])],        # conq_04_mode
        6: CON_TEXT[_valeur_6(brut[4])],        # conq_04_mode bit 1
        7: CON_TEXT[_valeur_7(brut[4])],        # conq_04_mode bit 0
    }
    for i in (1, 2, 3, 4, 5, 6, 7):
        put_in_string(_BUF[i], WORLD_W[i], val[i])
    return [bytes(_BUF[i]).split(b"\x00")[0].decode("latin-1")
            for i in range(WORLD_NB)]


def valeurs_colonnes(brut: bytes):
    """Les valeurs des lignes 9 a 14, tracées a part par les handlers.

    Renvoie une liste de quinze ``(you, him)`` : `(None, None)` sauf pour
    les deux colonnes. `line_9` (L12574-12627) affiche les deux
    populations, `line_0` (L12631-12698) affiche YES/NO selon le bit
    ``i - 10`` de `conq_03_yourpow` puis `conq_02_enemypow`.
    """
    from populous.con_text import CON_TEXT
    out = [(None, None)] * WORLD_NB
    out[9] = (str(brut[6]), str(brut[7]))       # conq_06 / conq_07
    for i in range(10, WORLD_NB):
        bit = i - 10                            # `SUB.W #$000a` (L12520)
        vous = CON_TEXT[22] if brut[3] & (1 << bit) else CON_TEXT[23]
        lui = CON_TEXT[22] if brut[2] & (1 << bit) else CON_TEXT[23]
        out[i] = (vous, lui)
    return out
