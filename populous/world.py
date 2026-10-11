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

**Point ouvert** : la boucle de L12381-L12384 annonce « loop 1 to 16 » et le
saut `LAB_4760C` dispatche seize cas, alors que le bloc tel qu'il est dans le
listing fait **quinze** entrees de 46 octets avant `_con_text` (L24725). La
seizieme ligne utiliserait donc une entree qui empiete sur la suite du
bloc. A verifier en relisant la table de sauts.

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