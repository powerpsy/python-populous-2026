# Logique de jeu de *Populous* (Bullfrog, 1989) — lecture du désassemblage 68000

> Document établi par lecture directe du désassemblage fourni dans `reference/tetracorp/`.
> Toute affirmation est suivie, entre parenthèses, du **numéro de ligne** du fichier
> `populous_prg.asm` et, quand c'est utile, de l'**adresse machine** (`$xxxxxx`).
> Le pseudocode Python est une *reconstitution fidèle* des instructions, pas une copie
> du code source C original (le désassemblage indique lui-même que le jeu « appears to
> have been written in C », en-tête lignes 33‑38).
>
> ⚠️ Les points non vérifiables sont rassemblés dans **§9 — Incertitudes** et marqués
> dans le texte par **[?]**.

---

## 0. Sources, conventions de lecture

### 0.1 Fichiers

| Fichier | Rôle |
|---|---|
| `reference/tetracorp/populous_prg.asm` | désassemblage principal (25 698 lignes) — **toutes** les citations renvoient ici |
| `reference/tetracorp/populous_prg.cnf` | table symbole → adresse |
| `reference/tetracorp/symbols_prg.txt` | liste plate des symboles (701 entrées) |
| `reference/tetracorp/populous_main.asm` / `.cnf` | desassemblage de l'hunk `populous` : c'est **l'introduction** (Phase 84), pas une seconde version du jeu |
| `readme.md` | notes du désassembleur |

### 0.2 Pièges de lecture du désassemblage

* **Base A4** : `A4 = BASEADR $000593EE`. Un déplacement `(sym,A4)` vaut `sym − $593EE`.
  Ex. `_stats` est codé `41ec 82b6` → `$593EE + $82B6 = $516A4` (ligne 17955).
  Un `LEA (LAB_xxxx,A4)` dont le déplacement vaut `_stats + n` désigne donc
  `_stats + n`.
* **Arguments de pile** : `LINK A5,#n` place l'argument 1 en `(8,A5)`, l'argument 2 en
  `($A,A5)`, etc. L'argument 1 est le **dernier** `MOVE …,-(A7)` avant le `JSR`.
  Exemple de vérification croisée : `_do_magnet` lit `(8,A5)` comme indice de joueur
  (`ASL.L #4` puis indexation `_magnet`, ligne 6771‑6775) et `($A,A5)` comme *x*
  (plafonné à `0x3F`, ligne 6794‑6796) ; l'appelant pousse `y`, `x`, `tribe`
  (lignes 17983‑17985 pour `_do_raise_point`, même schéma).
* **Arguments en bytes** : `(9,A5)` est l'octet de poids fort d'un mot passé en `(8,A5)`
  (big‑endian) ; pareil pour `($B,A5)`, `($D,A5)`.
* **Découpages du listing** : 8 endroits portent la mention `lines cut here` —
  lignes **3582, 4317, 7354, 9004, 14405, 14437, 16368, 16504**. Ce sont des trous
  réels du désassemblage (voir §9.1).
* **Tailles de structure** : tribu = `MULS #$2E` (46 B), joueur = `ASL.L #4` (16 B),
  peep = `MULS #$16` (22 B), ligne de carte = `ASL.W #6` (64), ligne d'alti =
  `MULS #$41` (65).

### 0.3 Arborescence des chapitres

1. §1 Annexes — structures de données
2. §2 **Chapitre 1** — Unités : structure, vie, déplacement, combat
3. §3 **Chapitre 2** — Bâtiments et villes
4. §4 **Chapitre 3** — Mana et sorts
5. §5 **Chapitre 4** — IA adverse et `level.dat`
6. §6 **Chapitre 5** — Écrans de victoire / défaite
7. §7 **Chapitre 6** — Gestion du temps
8. §8 Carte des symboles utiles
9. §9 Incertitudes

---

# 1. Annexes — structures de données

## A.1. La carte (64 × 64)

Indice d'une case : `idx = y*64 + x` (`ASL.W #6` puis `ADD.W x`, p. ex. lignes 18051‑18052).

| Symbole | Adresse | Taille | Contenu |
|---|---|---|---|
| `_map_blk` | `$00056376` | 4096 B | type de bloc |
| `_map_alt` | `$00057376` | 4096 B | altitude (0 = eau ; `< 7` = constructible) |
| `_map_bk2` | `$00058376` | 4096 B | 2ᵉ plan / sprite bâtiment‑ville |
| `_map_steps` | `$00059376` | 4096 B | coût de déplacement (et tampon `mouths.pic`) |
| *(anonyme `$5A376`)* | `$0005A376` | 4096 B | **[?]** non référencé par un symbole nommé |
| `_map_who` | `$0005B376` | 4096 B | **1 + index du peep** présent (0 = vide) |
| `_build_count` | `$0005C376` | mot | compteur de cases modifiées par un relèvement |

Codes `_map_blk` observés :

| Valeur | Signification | Référence |
|---|---|---|
| `$0F` | case à plat (constructible) | lignes 18138, 20987, 5900 |
| `$1F + tribu` (`$1F`, `$20`) | bâtiment / ville de la tribu | ligne 5893‑5897, 5973 |
| `$2F … $31` | rochers (3 variantes) | lignes 18100‑18103, 18130‑18134 |
| `$35` | marais (*swamp*) | ligne 4069, 8295+ |
| `$42` | ruines après bataille | ligne 6207+ (`_battle_over`) |

Codes `_map_bk2` observés :

| Valeur | Signification | Référence |
|---|---|---|
| `$21 … $2C` | bâtiment / ville | ligne 21019‑21022 |
| `$29 … $2C` | grande ville (case centrale `$2A`) | lignes 5876, 21010‑21013 |
| `$32 … $34` | arbres (rotation) | lignes 18063‑18076 |
| `0` | vide | lignes 18152, 5889 |

`_map_alt < 7` ⇒ case non submergée / constructible (lignes 18054, 18091).

## A.2. `_offset_vector` — les 25 voisins ($0005181A, ligne 24274)

Table de 25 **mots** = décalages `dy*64 + dx` sur la carte :

```
idx  décalage  (dx,dy)        idx  décalage  (dx,dy)      idx  décalage  (dx,dy)
 0       0     ( 0, 0)         9    -128     (-2, 0)      18     -62     (-1,+2)
 1     -64     ( 0,-1)        10      +2     ( 0,+2)      19     +66     (+1,+2)
 2      +1     (+1, 0)        11    +128     (+2, 0)      20    +129     (+2,+1)
 3     +64     ( 0,+1)        12      -2     ( 0,-2)      21    +127     (+2,-1)
 4      -1     (-1, 0)        13    -126     (-2,+2)      22     +62     (+1,-2)
 5     -63     (+1,-1)        14    +130     (+2,+2)      23     -66     (-1,-2)
 6     +65     (+1,+1)        15    +126     (+2,-2)      24    -129     (-2,-1)
 7     +63     (-1,+1)        16    -130     (-2,-2)
 8     -65     (-1,-1)        17    -127     (-2,+1)
```

Décodage ligne 24275‑24278 (`DC.L $0000ffc0, $00010040, …`).

* Indices **0‑8** : le carré 3×3 (centre + 8 voisins immédiats).
* Indices **9‑16** : les 8 cases à distance 2 « droites et diagonales » `(±2,0) (0,±2) (±2,±2)`.
* Indices **17‑24** : les 8 cases en « L » `(±2,±1) (±1,±2)`.

**Découpage 17 / 25** (voir §3.2) : les 17 premières cases forment une *ville*,
les 25 forment une *grande ville* (test `CMP.W #$0011` ligne 5937, `CMP.W #$0019`
lignes 5904 et 5978).

Tables voisines :
* `_to_offset` `$0005180A` (ligne 24272) : 8 mots = les 8 directions
  (N, NE, E, SE, S, SW, O, NO) sous forme de décalages.
* `_dir_sprite` `$00051850` (ligne 24281) : même chose, ordre NO,N,NE,E,SE,S,SW,O.
* `_big_city` `$00051862` (ligne 24284) : `2A 2C 2B 2C 2B 29 29 29 29` — les 9 sprites
  des cases internes d'une grande ville.

## A.3. `_peeps` — la fiche d'unité (22 octets, `$00053014`, max 208 = `$D0`)

| Dép. | Type | Nom de travail | Contenu (vérifié) |
|---|---|---|---|
| `+0x00` | octet | `state` | masque de bits, **voir ci‑dessous** |
| `+0x01` | octet | `tribe` | 0 ou 1 (`LAB_53015`) |
| `+0x02` | octet | `offspring` | nombre de descendants, plafonné à **4** (ligne 3986‑3989) |
| `+0x03` | octet | `weapons` | niveau d'arme, écrit depuis `_weapons_add[âge]` (ligne 3882) |
| `+0x04` | mot | `life` | vie/population ; init **45** (`$2D`, ligne 7026) ; `<= 0` = mort |
| `+0x06` | mot | `born_turn` | tour de naissance — lu comme `_game_turn - peep+6` (lignes 3712, 3723, 3744) |
| `+0x08` | mot | `block` | case courante = `y*64+x` (ligne 7031‑7033) |
| `+0x0A` | mot | `prev_block` | case précédente (effacée à la naissance, ligne 3951) |
| `+0x0C` | mot | `frame` | `0x20 + âge`, `0x2A` (= 42) = état « grande ville », `0xFF` à la création **[?]** |
| `+0x0E` | long | `target` | pointeur vers un peep adverse (0 = aucun) |
| `+0x12` | mot | `spawn_block` | case de naissance (recopiée du parent, ligne 3961) |
| `+0x14` | octet | `make_level_res` | retour de `_make_level` (ligne 3797) |

Bits de `state` (`+0x00`) :

| Bit | Masque | Sens | Preuve |
|---|---|---|---|
| 0 | `01` | **villageois** | test `CMPI.B #$01,(A0)` (ligne 3602) ; effacé ligne 3622 |
| 1 | `02` | **explorateur** | `BSET #1` (ligne 3624) ; l'état initial d'un nouveau‑né est `$02` (ligne 3946) |
| 2 | `04` | animation en cours | `BTST #2` (ligne 3586) |
| 3 | `08` | en bataille | (non relu ici) **[?]** |
| 4 | `10` | **se noie** | `BTST #4` (ligne 3482) → `_zero_population` (ligne 3488) |
| 7 | `80` | compte à rebours de mort | (non relu ici) **[?]** |

## A.4. `_stats` — fiche par tribu (46 octets, `$000516A4`)

Offsets recalculés à partir de `_stats = $000516A4` (`populous_prg.cnf` ligne 676) et
des symboles nommés (`symbols_prg.txt`).

| Dép. | Symbole/LABEL | Type | Rôle vérifié |
|---|---|---|---|
| `+0x00` | `_stats` | octet | **code d'action** en attente (0 = rien), dispatch §4.1 |
| `+0x01` | `LAB_516A5` | octet | paramètre 1 (**x** pour les actions 1‑13) |
| `+0x02` | `LAB_516A6` | octet | paramètre 2 (**y** pour 1‑13 ; **sous‑commande** pour 14) |
| `+0x06` | `LAB_516AA` | mot | `== 1` ⇒ la tribu émet des actions de construction (lignes 17934, 3498, 3831) |
| `+0x08` | `LAB_516AC` | mot | « action déjà en file » ; remis à 1 quand `_game_turn % (+0x10) == 0` (lignes 17940‑17951) |
| `+0x0C` | `LAB_516B0` | mot | seuil, comparé à 4 (ligne 7669) **[?]** |
| `+0x0E` | `LAB_516B2` | mot | **masque de pouvoirs** de la tribu 0 (`good`); `<<3 | 7` au chargement (lignes 420‑423) |
| `+0x10` | `LAB_516B4` | mot | **période** (en tours) des décisions IA ; `game_turn % période` (lignes 17944, 12419) |
| `+0x14` | `good_castles` `$516B8` | mot | châteaux « bons » |
| `+0x16` | `good_towns` `$516BA` | mot | villes « bonnes » |
| `+0x18`, `+0x1A`, `+0x1C` | `$516BC/BE/C0` | mots | seuils IA **[?]** |
| `+0x1E` | `$516C2` | mot | **[?]** |
| `+0x20` | `LAB_516C4` | mot | **couleur** de la tribu (utilisée par `___a_putpixel`, ligne 4031‑4035, et par `_animate` ligne 708‑711) |
| `+0x22` | `LAB_516C6` | long | pointeur vers le **peep ennemi le plus fort** (lignes 3702‑3703) |
| `+0x26` | `LAB_516CA` | long | pointeur peep, testé ligne 4092‑4094 **[?]** |
| `+0x2A` | `LAB_516CE` | long | pointeur peep « le plus longtemps sans naître » (lignes 3757‑3763) |
| `+0x12` | `$516B6` | mot | **[?]** effacé/lu à part entière |

Copie miroir « mauvaise » tribu : `bad_castles = $000516E6 = _stats[1]+0x14`,
`bad_towns = $000516E8 = _stats[1]+0x16` (`symbols_prg.txt` 496‑497).
Donc `_stats[1]` commence en `$516D2`.

> **Note de correction** : un relevé antérieur plaçait `good_castles` en `+0x12` et la
> couleur en `+0x1E`. Le fichier de symboles et les `LEA` montrent **`+0x14`** et
> **`+0x20`** ; ce document utilise ces valeurs.

## A.5. `_magnet` — fiche par joueur (16 octets, `$00052DE4`)

| Dép. | Symbole | Type | Rôle |
|---|---|---|---|
| `+0` | `_magnet` | mot | index **+1** du peep « aimanté » (0 = aucun) (ligne 6782) |
| `+4` | `LAB_52DE8` | mot | commande en attente (écrit par action 1, ligne 18402) |
| `+6` | `LAB_52DEA` | mot | compteur de peeps « town », remis à 0 chaque tour (ligne 3295), incrémenté ligne 3661 |
| `+8` | `good_pop` | long | population totale, **recalculée chaque tour** (lignes 3301, 3474) |
| `+12` | `LAB_52DF0` | long | **réserve de mana** |

`_player` `$00052DE2` (0 ou 1), `_not_player` `$00051648` = l'autre.

## A.6. `_conquest` — enregistrement `level.dat` (10 octets, `$000518AA`, ligne 24329)

```
+0  _conquest        octet   (colonne 0, valeurs 01..0a)
+1  conq_01_speed    octet   → _stats[1]+0x10 : PÉRIODE des décisions IA
+2  conq_02_enemypow octet   → _stats[1]+0x0E : pouvoirs de l'ennemi  (<<3 | 7)
+3  conq_03_yourpow  octet   → _stats[0]+0x0E : pouvoirs du joueur    (<<3 | 7)
+4  conq_04_mode     octet   → _game_mode
+5  conq_05_terrain  octet   → _ground_in (0 herbe, 1 désert, 2 neige, 3 roche)
+6  conq_06_yourpop  octet   → population initiale du joueur
+7  conq_07_enemypop octet   → population initiale de l'ennemi
+8  conq_08_seed     mot     → graine de génération
```

En-tête commenté du désassemblage, lignes 24316‑24327 et **12320‑12339** : les valeurs
admises colonne par colonne sont listées explicitement.

---

# 2. Chapitre 1 — Unités : structure, vie, déplacement, combat

## 2.1 Création : `_place_people(tribe, x, y, magnet)` — ligne 6982 ($43164)

```python
def place_people(tribe, x, y, magnet):           # L6982  $43164
    if no_peeps >= 0xD0:                          # L6984  208 peeps max
        return
    if magnet != 0 and magnet[tribe] != 0:        # L6990‑6997
        j = magnet[tribe] - 1                     # L7002‑7004  réutilise l'aimant
        zero_population(peeps[j], j)              # L7005‑7011  l'ancien est tué
    else:
        j = no_peeps; no_peeps += 1               # L7015‑7017
    peeps[j].born_turn = 0          (+6)          # L7019‑7022
    peeps[j].life      = 0x2D       (+4)  # = 45  # L7023‑7026
    peeps[j].block     = y*64 + x   (+8)          # L7027‑7033
    map_who[peeps[j].block] = j + 1               # L7035‑7041  (1 + index)
    # … suite : état, tribu, etc.                 # L7042+
```

* Quatrième argument = drapeau **aimant** : si non nul, on *remplace* le peep désigné
  par `_magnet[tribe]` au lieu d'en allouer un nouveau (lignes 6990‑7013).
* `_map_who` contient **l'index + 1** ; c'est pourquoi toutes les lectures font
  `SUBQ.W #1` (lignes 18163‑18164, 3669).

### Les 4 points d'apparition

| Code `_stats+0` | Appel | Ligne |
|---|---|---|
| 7 | `place_people(0, x, y, magnet=0)` | 18018‑18022 |
| 8 | `place_people(1, x, y, magnet=0)` | 18026‑18030 |
| 9 | `place_people(0, x, y, magnet=1)` | 18034‑18038 |
| 10 | `place_people(1, x, y, magnet=1)` | 18042‑18046 |

Population de départ : `_place_first_people` (ligne 7652, **transcrit en Phase 78**).

**Nombre de villageois** (`(-4,A5)`, L7654‑7678 / L7756‑7780) :
* **conquête** (ou tutoriel `_start_of_game == 3`, L7656 / L7758) :
  `conq_06_yourpop` / `conq_07_enemypop` (octets 6 et 7 de `level.dat`) ;
* **deux joueurs** (`serial_off == 0`, L7664‑7666 / L7766‑7768) : **1** par tribu ;
* **sinon** : `2 * (seuil > 4) + 1` — la tribu Amiga (`.data` `threshold` = 5)
  demarre avec **3**, la tribu humaine (`.data` = 1) avec **1**.

**Score** : `+10` points par villageois pose, tribu jouee seulement (L7680‑7686 /
L7782‑7788).

**Balayage tribu 0** (L7688‑7754) : depart bloc `$80` (x=0, y=2), avance vers
`$FFF` ; retient `_map_blk == $0F`. Chaque case consomme un villageois ;
le **dernier** a `magnet = 1`.

**Balayage tribu 1** (L7790‑7856) : depart bloc `$0F80` (x=0, y=62), recule
vers `$80` ; meme logique.

**Second balayage** (L7718‑7754 / L7820‑7856) : si des villageois restent
(aucune case `$0F` trouvee), on prend n'importe quelle case non vide et
non occupee (`_map_who == 0`).

**ECART declares** :
* La tribu 1 initialise son second balayage a `$1000 = 4096`, **hors**
  des 4096 cases — debordement reel du listing. Le byte lu est
  `_map_alt[0]` (tableau qui suit `_map_blk` en memoire) et
  `_map_who[4096]` un mot d'une autre table. Le port ne garde pas
  `_map_alt` (4096 octets ≠ 4225 sommets de `disp_alt`) : il modele
  cette case comme vide (boucle effective a partir de `$FFF`).
* Dans le second balayage tribu 1, le test `magnet` est fait **avant**
  de decremente `(-4,A5)` (L7833‑7839), contrairement a la tribu 0.

## 2.2 Boucle d'un tour : `_move_peeps` — ligne 3245 ($4059A)

```python
def move_peeps():                                 # L3245  $4059A
    game_turn += 1                                # L3250

    # (a) IA « démoniaque »
    for t in (0, 1):                              # L3252‑3273
        if stats[t].p8 == 0:                      # LAB_516AC == 0
            set_devil_magnet(t)                   # L3259
            devil_effect(t)                       # L3268

    # (b) réinitialisations par tribu
    for t in (0, 1):                              # L3275‑3344
        local_score[t] = 3*good_castles[t] + good_towns[t]   # L3283‑3289
        LAB_52DEA[t]  = 0                         # L3295  compteur « town »
        good_pop[t]   = 0                         # L3301  sera reconstruit
        if toggle:            # tous les 2 tours  # L3302
            mana[t] += 1                          # L3308  +1 mana / 2 tours
        stats[t].p2A = 0                          # L3313  LAB_516CE
        stats[t].p26 = 0                          # L3317  LAB_516CA
        stats[t].p22 = 0                          # L3321  LAB_516C6  cible
        local_best[t]   = 0                       # L3326  (-40,A5)
        local_age_turn[t]= 0                      # L3331  (-28,A5)
        local_age_max[t] = 0                      # L3336  (-24,A5)
        local_min[t]     = 0x4E1F                 # L3341  (-36,A5) = 19999

    # (c) compacter les peeps morts en fin de tableau
    while no_peeps > 0 and peeps[no_peeps-1].life == 0:   # L3346‑3356
        no_peeps -= 1

    # (d) vider les aimants dont la cible a un pointeur nul
    for i in (player, not_player):                # L3358‑3424
        if magnet[i] != 0 and peeps[magnet[i]-1].target != 0:
            set_magnet_to(i, peeps[magnet[i]-1].block)   # L3382‑3385
            magnet[i] = 0

    # (e) en cas de guerre globale, tous les aimants valent 0x0820
    if war:                                       # L3426‑3432
        LAB_52DF6 = LAB_52DE6 = god_magnet = devil_magnet = 0x0820

    # (f) boucle sur les peeps
    for i in range(no_peeps):                     # L3458‑3461
        p = peeps[i]
        if p.life <= 0:        continue           # L3463
        good_pop[p.tribe] += p.life               # L3472‑3474  SOMME DES VIES
        tile = &map_blk[p.block]                  # L3476‑3480
        ...
```

**Point clé** : `good_pop` n'est pas un compteur d'unités, c'est la **somme des `life`**
de tous les peeps vivants de la tribu (ligne 3474). D'où les grands nombres affichés.

## 2.3 L'entretien à chaque tour

```python
        if p.state & 0x10:                        # L3482  noyade
            if bit0(LAB_518A7):
                zero_population(p, i)             # L3488
            continue

        # (g) un villageois sans place → émission d'une action IA
        if (stats[p.tribe].p06 == 1 and not bit2(LAB_518A7)) or war:   # L3497‑3504
            stats[p.tribe].act = 1                # L3512  = relèver le point
            stats[p.tribe].x   = p.block & 0x3F   # L3515‑3524
            stats[p.tribe].y   = p.block >> 6     # L3526‑3536
            stats[p.tribe].p08 = 1                # L3543

        # (h) usure de la marche
        p.life -= 2 * walk_death                   # L3546‑3548  (mot, fichier LAND*)
        if map_blk[p.block] != 0:                 # L3549‑3551  sur un bâtiment
            p.state &= ~0x10 ; set_frame(p)       # L3553‑3555
        elif p.state & 0x01:                      # L3566‑3571  villageois sur case vide
            set_town(p, 1)                        #        il construit
            p.state = 0x12                        # L3575  = 0x10|0x02 ?
            if p.frame >= 8:  p.frame = 0         # L3577‑3580
        if p.state & 0x04:                        # L3586  animation
            if set_frame(p) != 0:                 # L3591
                p.state &= ~0x04 ; set_frame(p)   # L3594‑3596
            continue                              # L3599
```

> ⚠️ La **ligne 3582 porte `large number of lines cut`** : une portion du traitement
> « sur case vide » manque au listing. Le passage `p.state = 0x12` puis test `frame >= 8`
> est lu *après* le trou ; l'ordre exact des affectations est donc **[?]** (§9.1).

## 2.4 Le villageois : `_check_life` et la naissance

```python
        if p.state == 0x01:                       # L3602  villageois
            score = check_life(p.tribe, p.block)  # L3604‑3612
            if score <= 0 or p.target != 0 or war:  # L3613‑3619
                p.state = (p.state & ~0x01) | 0x02 # L3622‑3624  → EXPLORATEUR
                p.frame = 0 ; p.prev_block = 0     # L3626‑3628
                set_town(p, 1)                     # L3631  dernière tentative
                continue
            old_frame = p.frame                    # L3636
            if score >= 0x0BEA:                    # L3637  3050 = grande ville
                local_best_n[p.tribe] += 1         # L3644
                p.frame = 0x2A                     # L3646  42 → « grande ville »
            else:
                p.frame = 0x20 + score*10 // 0x131 # L3649‑3655  âge = 0..10
                LAB_52DEA[p.tribe] += 1            # L3661
            age = p.frame - 0x20                   # L3663‑3666  (0..10)
            if map_who[p.block] == 0:              # L3668‑3671
                map_who[p.block] = i + 1           # L3672‑3677
```

### `_check_life(tribe, block)` — ligne 20958 ($4DD56), décodée intégralement

```python
def check_life(tribe, block):                      # L20958  $4DD56
    own        = tribe + 0x1F                      # L20961‑20962  type « mon bâtiment »
    score      = 0                                 # D4
    all_of_city= 0 ; a_flat_block = 0              # L20965, L20970  globals
    centre_bk2 = map_bk2[block]
    for k in range(17):                            # L21029  D5 = 0..16
        off   = offset_vector[k]                   # L20972
        r     = valid_move(block, off)             # L20975
        nb    = block + off                        # L20984
        if r == 0:
            if   map_blk[nb] == own:               # L20985
                pass                               #   → « comptable »
            elif map_blk[nb] == 0x0F:              # L20987
                a_flat_block = 1                   # L20989
                pass
            else:                                  # L20997
                if k == 0: return 0                # L20998‑21002  centre NON constructible
            if score == 0: score = 0x32            # L20991‑20993  50 de base
            score += 0x0F                          # L20995  +15
        elif r == 2:                               # L20979‑20981
            score -= 0x0F                          # L20981  −15
        # r == 1 : neutre, rien
        d1 = map_bk2[nb]                           # L21005
        if k < 9 and centre_bk2 == 0x2A and 0x29 <= d1 <= 0x2C:   # L21006‑21013
            all_of_city += 1                       # L21014
        elif k > 0 and 0x20 < d1 <= 0x2C:          # L21017‑21022
            return 0                               # L21023‑21025  enclavé par un bâtiment
    if score < 0x23:  score = 0                    # L21031‑21033  < 35 → 0
    if score == 0x131: score = 0x0BEA              # L21035‑21037  305 → 3050
    return score                                   # L21039
```

**Lecture** : le score mesure la *surface exploitable* autour du peep.
Le centre doit être soit « mon » bâtiment, soit à plat (sinon 0).
Chaque case valable vaut **+15**, la première valable vaut **+50**.
Maximum atteint = `50 + 16×15 = 305`, remappé sur **3050** = « grande ville ».
Minimum retenu non nul : 35 (donc en pratique 50, 65, 80 …).

### Tous les 8 tours : mana, armes, croissance, scission — lignes 3819‑4014

```python
        if (game_turn & 7) != 0:                   # L3819‑3821  ← rythme 8 tours
            goto suite                             # L4015

        threshold = score                          # (-12,A5) hérite de check_life (L3612)
        if p.frame == 0x2A and stats[p.tribe].p06 == 1 \
           and p.life > 0x131 and stats[p.tribe].p08 == 0:   # L3823‑3851
            threshold = 0x131                      # L3844  305
            stats[p.tribe].p08 = 1
        if cheat != 0 and p.tribe == cheat - 1:    # L3853‑3862
            threshold = 0x32                       # 50  → triche de croissance

        mana[p.tribe] += mana_add[age]             # L3864‑3876  mot signé → long
        p.weapons = weapons_add[age]               # L3877‑3882  octet

        if p.life > threshold:                     # L3883‑3886  SCISSON
            j = premier emplacement libre (life<=0)     # L3887‑3900  (0..207)
            child.life   = p.life - threshold // 2      # L3904‑3908
            p.life       = threshold // 2               # L3909‑3912
            # corrections d'indices
            if magnet[p.tribe]-1 == i: magnet[p.tribe] = j+1   # L3915‑3929
            if view_who-1     == i: view_who       = j+1       # L3931‑3937
            child.offspring = p.offspring               (+2)    # L3941
            child.block     = p.block                   (+8)    # L3944
            child.state     = 0x02     # EXPLORATEUR             # L3946
            child.tribe     = p.tribe                     (+1)   # L3949
            child.prev_block= 0                           (+0x0A)# L3951
            child.frame     = 0                           (+0x0C)# L3953
            child.weapons   = p.weapons                   (+3)   # L3956
            child.target    = 0                           (+0x0E)# L3958
            child.spawn_block= p.block                    (+0x12)# L3961
            child.make_level_res = 0                      (+0x14)# L3963
            map_who[child.block] = j+1                    # L3965‑3983
            if p.offspring < 4: p.offspring += 1          # L3986‑3989
            if j == 0xD0 and not funny_done:              # L3999‑4006
                do_place_funny(1); funny_done = 1

        p.life += population_add[age]               # L4008‑4014  TOUJOURS
```

**Synthèse de la croissance** : la « population » d'un joueur (`good_pop`) est une
**somme de vies**. Chaque peep gagne `population_add[âge]` tous les 8 tours ; il se
*divise* quand sa vie dépasse le score `_check_life` de sa case, en conservant
`threshold/2` et en donnant l'excédent à un explorateur. Les tables
`mana_add / weapons_add / population_add / walk_death / battle_add1 / battle_add2`
sont **chargées depuis le disque** (§4.4) : leurs valeurs ne sont **pas** dans le
listing.

### Poursuite du tour : rendu, `set_town`

```python
        if not toggle:                             # L4016  un tour sur deux
            if p.tribe == player or serial_off:    # L4021‑4024
                a_putpixel(p.block, stats[p.tribe].colour)   # L4031‑4035
        if p.frame != old_frame or a_flat_block != 0 \
           or (p.frame == 0x2A and all_of_city < 9):          # L4038‑4048
            set_town(p, 0)                         # L4052
```

## 2.5 L'explorateur

État `0x02` (ligne 4058). Court jusqu'à ce que `_set_frame` renvoie non nul, puis :

```python
        if map_blk[p.block] == 0x35:               # L4069  MARAIS
            zero_population(p, i)                  # L4073
            effect = 0x42                          # L4075  (son)
            if not bit1(LAB_518A7):
                map_blk[p.block] = 0x0F            # L4079  le marais disparaît
```

Autres routines : `_move_explorer` (ligne 4398), `_where_do_i_go` (ligne 4622),
`_get_heading` (ligne 5469), `_move_magnet_peeps` (ligne 4905),
`_set_frame` (ligne 5724), `_zero_population` (ligne 5645).

## 2.6 Le combat

### `_do_battle(attacker, idx)` — ligne 6066

Reconstitution (contrat d'arguments reconstitué, voir §9.2) :

```python
def do_battle(atk, i):
    opp = peeps[atk.field6]                 # L6066+  adversaire indexé par +0x06
    roll_atk = (newrand() % 3 + 1) * atk.life
    roll_opp = (newrand() % 3 + 1) * opp.life
    loser = atk if roll_atk > roll_opp else opp
    winner = opp if loser is atk else atk
    dmg = loser.weapons * (max(roll_atk, roll_opp) // 100) + 10   # [?] ordre ___divs/___mulu
    loser.life -= dmg
    set_frame(atk) ; set_frame(opp)
    if atk.life <= 0: zero_population(atk, i)
    if opp.life  <= 0: zero_population(opp, opp_index)
    if loser died:
        battle_over(winner_index, loser_index)   # L6207
```

> **[?] L'ordre des opérandes de `___divs` / `___mulu` n'est pas vérifié** : la
> formule exacte du dégât (`weapons * (roll/100) + 10`) est plausible mais pas démontrée.

### `_battle_over(winner, loser)` — ligne 6207

```python
def battle_over(w, l):
    loser_tribe = peeps[l].tribe
    winner_tribe= peeps[w].tribe
    battle_won[winner_tribe] += 1               # L6478 (symbole _battle_won $54268)
    age = clamp(peeps[l].frame - 0x20, 0, 10)
    mana += battle_add1[age] if 0 <= age <= 10 else 100   # L6538‑6545
    # destruction de la zone : 17 (ville) ou 25 (grande ville) cases autour
    for k in range(n):                          # n = 17 ou 25 selon la taille
        map_blk[nb] = 0x42                      # RUINES
        map_bk2[nb] += 0x15                     # +21 → bascule vers la variante ruinée
    set_town / check_life en secours            # L6207+
```

* `_mana_values[0] = -250` (`$FFFFFF06`, ligne 24288) est le **plancher de mana**
  appliqué en cas de défaite (lignes 6538‑6545).
* `_battle_won` `$00054268` : mots par tribu, affichés sur l'écran final (lignes 14050‑14065).

### Fusion : `_join_forces` (5540) et `_join_battle` (6663)

```python
def join_forces(src, dst):
    dst.life = min(dst.life + src.life, 0x7D00)   # 32000
    magnet[dst.tribe] = magnet[src.tribe]         # transfert de l'aimant
    dst.weapons = max(dst.weapons, src.weapons)
    if src_index > dst_index:                     # réindexation
        good_pop -= src.life
    src.life = 0                                  # effacé
```

### Les autres rutines de combat

| Symbole | Ligne | Rôle |
|---|---|---|
| `_set_battle` | 6568 | déclenche une bataille sur une case |
| `_join_battle` | 6663 | un peep rejoint un combat en cours |
| `_join_forces` | 5540 | fusion de deux peeps |
| `_zero_population` | 5645 | tue un peep et nettoie `_map_who` |

---

# 3. Chapitre 2 — Bâtiments et villes

## 3.1 Codes et tables

* Case à plat : `_map_blk = $0F`, `_map_bk2 = 0`.
* Bâtiment de tribu : `_map_blk = $1F + tribu` (lignes 5893, 5973).
* Ville : `_map_bk2 ∈ [$21, $2C]` ; **grande ville** : `_map_bk2 == $2A` au centre
  (lignes 5876, 5984, 21008) et `$29…$2C` sur les 8 cases internes (lignes 21010‑21013).
* La table `_big_city` (ligne 24284) donne les 9 sprites internes :
  `2A 2C 2B 2C 2B 29 29 29 29`.
* Arbres : `_map_bk2 ∈ [$32,$34]`, rotation cyclique gérée par `_last_tree` `$5164A`
  (lignes 18063‑18078).
* Rochers : `_map_blk ∈ [$2F,$31]`, rotation cyclique `_last_rock` `$5164C`
  (lignes 18100‑18115).

## 3.2 `_set_town(peep, grow)` — ligne 5865 ($4243C)

```python
def set_town(p, grow):                       # L5865  $4243C
    b = p.block                              # L5869  (8,p)
    if grow != 0:                            # L5872  ← mode « agrandir »
        if map_bk2[b] == 0x2A:               # L5876  déjà une grande ville
            for k in range(25):              # L5904  CMP #$19
                if valid_move(b, offset_vector[k]) != 1:      # L5880‑5885
                    nb = b + offset_vector[k]
                    map_bk2[nb] = 0                          # L5889
                    if map_blk[nb] == p.tribe + 0x1F:        # L5893‑5897
                        map_blk[nb] = 0x0F   # L5900  on DÉTRUIT le bâtiment
        else:                                # L5907  ville normale
            for k in range(17):              # L5937  CMP #$11
                if valid_move(b, offset_vector[k]) != 1:      # L5910‑5915
                    nb = b + offset_vector[k]
                    if k < 9:
                        map_bk2[nb] = 0                      # L5920‑5921
                    if map_blk[nb] == p.tribe + 0x1F:        # L5925‑5930
                        map_blk[nb] = 0x0F                   # L5933
            map_bk2[b] = 0                                   # L5941
    else:                                    # L5944  ← mode « construire »
        if p.frame == 0x2A:                  # L5946  grande ville (42)
            for k in range(25):              # L5978  CMP #$19
                if valid_move(b, offset_vector[k]) != 1:
                    nb = b + offset_vector[k]
                    if k < 9:
                        map_bk2[nb] = _big_city[k]           # L5958‑5965
                    if map_blk[nb] == 0x0F:                  # L5968
                        map_blk[nb] = p.tribe + 0x1F         # L5972‑5974  CONSTRUCTION
        elif map_bk2[b] == 0x2A: …           # L5984  (suite non relue intégralement) [?]
        else: …                              # L5981+
```

**Règles essentielles**

1. **17 cases = ville, 25 cases = grande ville.** Ce sont les deux premiers
   découpages de `_offset_vector` (§A.2).
2. `grow=1` *rase* : elle efface `_map_bk2` et remet `_map_blk` à `$0F` quand il
   valait `$1F+tribu`. Elle sert à la fois à « déménager » un peep et à la destruction
   post‑bataille.
3. `grow=0` *construit* : elle pose `_map_blk = $1F+tribu` sur les cases à plat, et
   remplit `_map_bk2` avec les sprites de `_big_city` (grande ville) ou avec le
   séquenceur de sprites de ville.
4. Les appels sont faits depuis `_move_peeps` : `set_town(p, 1)` quand un villageois
   perd sa place (lignes 3571, 3631) et `set_town(p, 0)` quand le peep a grandi
   (ligne 4052).

## 3.3 `_place_building` / `_add_settlement`

Les symboles `_place_building`, `_add_settlement` n'existent **pas** sous ce nom dans
`populous_prg.asm`. La construction passe par `_set_town` + les codes d'action
7‑10 de `_get_message` (§4.1). Toute référence à ces deux noms est donc à relier à
`_set_town` / `_settlement_creation` (ligne 7359). **[?]**

## 3.4 Destruction

* **Bataille** : `_battle_over` convertit 17 ou 25 cases en `$42` (ruines) et ajoute
  `+0x15` à `_map_bk2` (§2.6).
* **Sort « enlever » (action 13)** : ligne 18123‑18182 —
  si `_map_blk ∈ [$2F,$31]` → `$0F` + `___make_map(x, y, x+1, y+1)` (lignes 18130‑18148) ;
  `_map_bk2 = 0` ; si `_map_who ≠ 0` → `_zero_population(peep)` puis
  `_map_who = 0`, `_map_bk2 = 0` (lignes 18149‑18182).
* **Marais** : un explorateur qui meurt dans le `$35` le ramène à `$0F` (ligne 4079).

---

# 4. Chapitre 3 — Mana et sorts

## 4.1 Le tableau `_mana_values` — `$00051874`, ligne 24287

| idx | adresse | valeur | usage vérifié |
|---|---|---|---|
| 0 | `$51874` | **−250** (`$FFFFFF06`) | plancher de mana en cas de défaite (lignes 6538‑6545) |
| 1 | `$51878` | **10** | coût de base relèver/abaisser (`_do_raise_point` ligne 7187) |
| 2 | `$5187C` | **200** | `_do_magnet` (lignes 6776, 6792‑6793) |
| 3 | `$51880` | **2 500** | `_do_quake` (ligne 7863+) |
| 4 | `$51884` | **5 000** | `_do_swamp` (ligne 8295+) |
| 5 | `$51888` | **7 500** | `_do_knight` (ligne 8392+) |
| 6 | `$5188C` | **10 000** | `_do_volcano` (ligne 8046+) |
| 7 | `$51890` | **40 000** | `_do_flood` (ligne 7567+) |
| 8 | `$51894` | **80 000** | `_do_war` (ligne 8482+) |
| 9 | `$51898` | **160 000** | seuil du 9ᵉ cran de la jauge |
| 10 | `$5189C` | **2 000 063** (`$001E847F`) | **[?]** plafond probable |

`_move_mana` (ligne 3164, `$404CC`) confirme la lecture : c'est la **jauge de mana**.

```python
def move_mana():                                   # L3164  $404CC
    m = mana[player]                               # L3180
    for d4 in range(11):                           # L3168‑3184
        if m > _mana_values[d4]: continue          # L3181‑3182  on cherche le 1er cran atteint
        if d4 > 9:                                 # L3183‑3184  mana > tout = jauge pleine
            draw_sprite(0x45, 0x137, 0x57)         # L3232‑3236
            return
        # cran partiel : position dans le segment
        prev = _mana_values[d4 - 1]                # L3196
        sub  = ((m - prev) * 8) // (_mana_values[d4] - prev)   # L3197‑3210  0..7
        x = (d4-1)*16 + sub*2 + 0xA0               # L3219‑3225
        y = (d4-1)*8  + sub   + 8                  # L3213‑3217
        draw_sprite(0x45, x, y)                    # L3228
        return
```

**Conséquence gameplay** : les 9 crans de la jauge sont exactement les seuils
10 / 200 / 2 500 / 5 000 / 7 500 / 10 000 / 40 000 / 80 000 / 160 000, et ils
correspondent 1‑à‑1 aux coûts des pouvoirs, dans l'ordre :
**relèver‑abaisser, aimant, séisme, marais, chevalier, volcan, déluge, guerre**.

## 4.2 Le coût réel de relèver / abaisser

```python
def do_raise_point(tribe, x, y):                   # L7180  $433EA
    if mana[tribe] < 10 and not paint_map and not war:   # L7182‑7192
        return                                      #  refus si trop peu de mana
    xmin = xmax = x ; ymin = ymax = y               # L7197‑7200
    build_count = 0                                 # L7201
    raise_point(x, y)                               # L7202‑7204  modifie le relief
    if not paint_map and not war:                   # L7206‑7209
        mana[tribe] -= 4 * build_count + 10         # L7210‑7219  coût VARIABLE
```

* Coût = **`10 + 4 × (nombre de cases modifiées)`** (lignes 7215‑7219 : `ASL.W #2`
  puis `ADD #0xA`, `SUB.L D0,(A0)`).
* `_do_lower_point` (ligne 7091) : même chose, même saut du contrôle de mana quand
  `_paint_map` est actif.
* En période de **guerre** (`_war`), le contrôle et le paiement sont sautés
  (lignes 7189‑7192, 7206‑7209).

## 4.3 Le canal de commandes : `_get_message` — ligne 17707 ($4B23A)

Le jeu n'appelle **jamais** directement les effets : une tribu écrit `(code, x, y)`
dans `_stats[tribe]`, et `_get_message`, appelé **en fin de tour** (ligne 1011),
décode et exécute.

```python
def get_message():                                  # L17707  $4B23A
    my   = &_stats[player]                          # L17712‑17716
    foe  = &_stats[not_player]                      # L17717‑17721
    my.x = min(my.x, 0x3F) ; my.y = min(my.y, 0x3F) # L17722‑17732  clamp à 63
    if quick_io:  … échange série/compression …      # L17734‑17836
    else:         … échange par canal plein …        # L17837‑17928
    for t in (0, 1):                                # L17930  D4 = tribu
        if stats[t].p06 == 1 and game_turn % stats[t].p10 == 0:   # L17934‑17947
            stats[t].p08 = 0                        # L17951  on (re)libère l'action
        act = stats[t].act                          # L17957
        if act == 0: continue                       # L17959
        p1 = stats[t].x ; p2 = stats[t].y           # L17962‑17971
        dispatch(act)                               # L17972‑17974 → LAB_4B838
    # le dispatch saute dans la table de L18202 (LAB_4B81A), bornée à 15 (L18219)
```

### Table de dispatch `_get_message` (15 entrées, lignes 18202‑18217)

| code | étiquette | exécution | ligne |
|---|---|---|---|
| 0 | `LAB_4B818` | no‑op | 18200 |
| 1 | `LAB_4B586` | `___do_raise_point(tribe, x, y)` | 17982‑17988 |
| 2 | `LAB_4B59A` | `___do_lower_point(tribe, x, y)` | 17989‑17995 |
| 3 | `LAB_4B5AE` | `___do_quake(tribe, x, y)` | 17996‑18002 |
| 4 | `LAB_4B5C2` | `___do_swamp(tribe, x, y)` | 18003‑18009 |
| 5 | `LAB_4B572` | `___do_magnet(tribe, x, y)` | 17975‑17981 |
| 6 | `LAB_4B5D6` | `___do_volcano(tribe, x, y)` | 18010‑18016 |
| 7 | `LAB_4B5EA` | `place_people(0, x, y, magnet=0)` | 18017‑18024 |
| 8 | `LAB_4B600` | `place_people(1, x, y, magnet=0)` | 18025‑18032 |
| 9 | `LAB_4B618` | `place_people(0, x, y, magnet=1)` | 18033‑18040 |
| 10 | `LAB_4B630` | `place_people(1, x, y, magnet=1)` | 18041‑18048 |
| 11 | `LAB_4B64A` | **planter un arbre** | 18049‑18085 |
| 12 | `LAB_4B6C2` | **poser un rocher** | 18086‑18122 |
| 13 | `LAB_4B73A` | **enlever + tuer** | 18123‑18184 |
| 14 | `LAB_4B7FA` | `_do_action(tribe, p1, p2)` | 18185‑18193 |
| 15 | `LAB_4B816` | no‑op | 18198 |

**11 — planter un arbre** (lignes 18049‑18085) : n'agit que si `_map_alt < 7` (18054).
Lit `_map_bk2` ; s'il n'est pas déjà un arbre (`$32…$34`) on prend `_last_tree`,
sinon on fait tourner `$34 → $32`, `$32 → $33`, sinon `$33 → $34`+1 ; on écrit
`_map_bk2 = valeur` et on mémorise `_last_tree`.

**12 — poser un rocher** : même logique sur `_map_blk ∈ [$2F,$31]` et `_last_rock`.

**13 — enlever** : voir §3.4.

### Les arments de l'interface : `_zoom_map` (ligne 1658, `$3F2F6`)

`_get_message` ne choisit rien : elle lit trois octets de la fiche
`_stats[player]` (`_stats+0` = `act`, `+1`/`+2` = `p1`/`p2`, L17955-17958) et
aiguille. Qui les ecrit ? Deux routines seulement, appelees toutes deux
depuis la boucle d'image (L963-1013).

**La palette d'outils** `LAB_3F666` (L1928-2133), 9 entrees, atteinte quand
`v >= $92` et que la case n'est pas dans le pave de defilement
(`up > 5 ou up < 3 ou vp < 0 ou vp > 2`, L1838-1845) :

| (up, vp) | `act` | `p1` | `p2` | effet | lignes |
|---|---|---|---|---|---|
| (0, 0) | 14 | - | 4 | `_do_flood` | 1942/1944 |
| (1, 0) | 14 | - | 3 | `_do_war` (seulement si `!_paint_map`) | 1959/1961 |
| (1, 1) | 6 | `_xoff & $FF` | `_yoff & $FF` | `_do_volcano` | 1972/1974/1976 |
| (2, 0) | 3 | `_xoff & $FF` | `_yoff & $FF` | `_do_quake` | 1989/1991/1993 |
| (2, 1) | 14 | - | 5 | `_do_knight` | 2005/2007 |
| (2, 2) | - | - | - | sculptage : `mode = (mode & 3) | 8`, `_pointer = 5` | 2012-2042 |
| (3, 3) | 14 | 0 | 1 | relief, direction 0 | 2049/2051/2053 |
| (4, 3) | 14 | 1 | 1 | relief, direction 1 | 2060/2062/2064 |
| (4, 4) | 14 | 3 | 1 | relief, direction 3 | 2070/2072/2074 |
| (5, 3) | 14 | 2 | 1 | relief, direction 2 | 2081/2083/2085 |
| (6, 0..2) | - | - | - | selecteur de mode | 2088-2131 |

Un octet que la branche n'ecrit pas garde la valeur de la commande
precedente (`LAB_3F6A0` saute a l'epilogue sans toucher a `p1`, L1946).

`_xoff`/`_yoff` sont des **mots** ; les etiquettes `LAB_52DDF`/`LAB_52DE1`
(L25313-25318) designent leur octet bas, seul lu (L1974/1976, L1991/1993).

**La barre d'icones**, zone A `u > $112` (L1706) - `DIVS` vers zero, donc
`col = (u-$110)/16`, `row = (v-$20)/16` (L1711/L1716) :

| (col, row) | `act` | `p1` | `p2` | lignes |
|---|---|---|---|---|
| (0, 0) | 14 | `d0` | 7 | 1729/1731/1733 |
| (1, 1) | 14 | - | 8 | 1795/1797 |
| (1, 3) | 14 | - | 6 | 1803/1805 |
| (2, 2) | 14 | - | 2 | 1820/1822 |

`(9,A5)` est l'octet **bas** du mot pousse par l'appelant (L988) : avec
`LINK A5,#-14`, ce mot occupe A5+8..9 et l'adresse de retour A5+4..7, donc
`(9,A5)` = `d0` lui-meme.

**Le clic sur la carte**, `_sculpt` (L7452-7561), une seule fois par clic
(`_left_button == 0`, L7452) : c'est **le clic** qui choisit l'action, pas la
palette.

| test | ecrits | lignes |
|---|---|---|
| `mode & $08` | `act=4`, `p1=x-1`, `p2=y-1` | 7454-7489 |
| `mode & $04` | `act=5`, `p1=x-1`, `p2=y-1` | 7491-7526 |
| defaut | `act=1`, `p1=x`, `p2=y` | 7527-7540 |
| clic droit, `mode == 2` | `act=2`, `p1=x`, `p2=y` | 7542-7561 |

`p1`/`p2` sont `LAB_516A5/6[player]`, memes octets que `stats+1/+2`.

`bitfield_51645` (0x51645, L24141) n'est **pas** un champ independant :
`_mode` est l'octet 0x51644 (L24139) et le listing ecrit le **mot** -
`MOVE.W #$0002,(_mode,A4)` (L1148) pose `00` puis `02`, exactement les deux
octets initiaux du `.data`. D'ou `BTST #2` = `mode & $04`,
`BTST #3` = `mode & $08`, et les `BSET #3` / `BSET #2` de la palette
(L2040, L2127) qui arment marais et aimant ; les `BCLR` (L7479, L7516) les
desarment apres usage. Ces bits ne sont poses **que** par la palette.

**Le sens du relief** : le code 1 de `_do_action` (L18381-18403) remet la
croix `_tend_x[p1]`/`_tend_y[p1]` (L2455-2522), puis ecrit
`LAB_52DE8[tribu*16] = p1` (`command[player]`). Aucun cout, aucun modelage du
terrain : choisir une direction n'est pas lever le sol.

Le code 2 de `_do_action` - arme par (2,2) de la barre - n'a pas ete
transcrit : il est la liaison serie. Les codes 7 et 8, armes par (0,0) et
(1,1), le sont depuis les phases 68 et 69.

Les colonnes 7 et 8 de `LAB_3F666` n'arment rien : elles deplacent la
fenetre et le suivi.

| (up, vp) | routine | effet | lignes |
|---|---|---|---|
| (7, 0) | `LAB_3F924` | suit l'aimant : centre sur la case du peep aimantee (`_peeps+8`) si `_magnet[player] != 0`, avec `_set_temp_view` ; sinon sur `LAB_52DE6` (= `_magnet_to`) | 2134-2226 |
| (7, 1) | `LAB_3FA40` | balayage circulaire depuis `_view_fight+1`, retient `state & $08` et `life != 0`, ecrit `_view_fight` puis `_set_temp_view(i+1)` | 2227-2296 |
| (8, 0) | `LAB_3FB26` | balayage depuis `_view_people+1` : clic gauche -> `TST.L (LAB_53022)` (le peep a une cible) ; clic droit -> `state == 1`. Tribu du joueur et vivants | 2297-2405 |

Le `TST.W (8,A5)` du L2306 ne branche pas : residu sans effet. Les deux
`TST.W (8,A5)` qui comptent (L2143, L2345) testent le **mot pousse par
l'appelant** (L988), nul sauf sur l'image du clic gauche.

`_set_temp_view` (L404ac) : si `_view_timer == 0`, `_old_view_who =
_view_who` ; `_view_timer = 10` ; `_view_who = who`.

## 4.4 `_do_action` — seconde table (16 entrées, ligne 18376 `$4B9E0`, table 19008‑19023)

```python
def do_action(tribe, p1, p2):                       # L18376  $4B9E0
    # (8,A5)=tribe  ($A,A5)=p1  ($C,A5)=p2
    dispatch_on(p2)                                 # L18378‑18380 → LAB_4C18A, borné à 16
```

> ⚠️ Le `switch` porte sur le **3ᵉ argument** (`($C,A5)`, ligne 18378), c'est‑à‑dire
> `_stats[tribe]+2`, alors que pour les codes 1‑13 ce champ est `y`. Pour le code 14,
> `+1` devient un *paramètre* et `+2` la *sous‑commande*. C'est ce que montre le code ;
> l'intention d'origine est **[?]** (§9.3).

| sous | étiquette | effet | ligne |
|---|---|---|---|
| 0 | `LAB_4C168` | no‑op | 19005 |
| 1 | `LAB_4B9EE` | `_set_tend_icons(tend_y[p1], tend_x[p1])` si `tribe==player` ; `LAB_52DE8[tribe] = p1` | 18381‑18403 |
| 2 | `LAB_4BA34` | chat série (écrit/relit `_message`) | 18404+ |
| 3 | `LAB_4BC38` | `_do_war(tribe)` | 18576‑18580 |
| 4 | `LAB_4BC46` | `___do_flood(tribe)` | 18581‑18585 |
| 5 | `LAB_4BC54` | `_do_knight(tribe)` | 18586‑18590 |
| 6 | `LAB_4BC62` | **pause** : bascule `_pause` 0/1 + icône, `_toggle = 0` | 18591‑18606 |
| 7 | `LAB_4BC94` | règle croisée entre joueurs (test `stats.x == 7/14`) **[?]** | 18607‑18728 |
| 8 | `LAB_4BE12` | **[?]** (non relu) | 18729 |
| 9 | `LAB_4C0B8` | mana du joueur 0 : `mana //= 2` si `p1 != 0`, sinon `mana = min(mana*2+500, 100 000)` | 18943‑18959 |
| 10 | `LAB_4C0EC` | idem sur `LAB_52E00` (joueur 1) | 18960‑18976 |
| 11 | `LAB_4C11E` | `___rotate_all_map()` | 18977‑18979 |
| 12 | `LAB_4C124` | `___clear_all_map()` | 18980‑18982 |
| 13 | `LAB_4C12A` | `_ground_in = p1` ; `_load_ground(p1, 1)` ; `_draw_map(0,0,0x3F,0x3F)` | 18983‑18999 |
| 14 | `LAB_4C168` | no‑op | 19022 |
| 15 | `LAB_4C15C` | **triche** : `_cheat = p1 + 1` | 19000‑19004 |

Le retour non nul de `_do_action` déclenche `_clear_send` (ligne 18191‑18193).

Les trois codes qui ne sont pas transcrits, avec ce qu'il leur manque :

| code | handler | ligne | routine requise |
|---|---|---|---|
| 2 | `LAB_4BA34` | 18400 | **fait** — no-op quand `_serial_off != 0`, sinon liaison série |
| 7 | `LAB_4BC94` | 18607 | `Game.options` (`_options`, L13617) - **fait** |
| 8 | `LAB_4BE12` | 18729 | `Game.game_setup` (`_game_options`, L12801) - **fait** |

Les **seize** codes de la table sont donc transcrits. L'entree `(2,2)` de la
barre arme le code 2 (L1820), `(0,0)` le code 7 (L1729) et `(1,1)` le code 8
(L1795) ; l'icone `(2,2)` est sans effet visible en un seul joueur, parce que
le handler rend la main sur `TST.W _serial_off ; BNE` (L18405-18406).

`_options` (L13617, `$48188`) est le handler du **code 7** de `_do_action`
(L18607-18728), arme par l'entree `(0,0)` de la barre d'icones. Boucle
modale : dessiner, attendre un clic,appliquer, recommencer.

| etape | lignes | detail |
|---|---|---|
| sauvegarde | 13619-13632 | copie des **46 octets** de `_stats[player]` en local (`LINK A5,#-56`) |
| inversion | 13643-13660 | `LAB_516B0[player] = 10 - LAB_516B0[player]` ; idem `LAB_516B4[player]` - les curseurs sont stockes en complement |
| boite | 13634-13642 | `_requester(d_screen, $10, $10, $120, $A6,
      _end_ok, _end_cancel)` - **sept** arguments, les deux derniers
      etant des structures `(x0, y0, x1)` remplies par la routine |
| noms | 13669-13688 | `LAB_51922[0]` = "GOOD" si `player == 0`, sinon "EVIL" (`___strcpy`) |
| traces | 13661-13784 | boucle `i` de 0 a 13 (`CMPI.W #$0E`, L13783) |
| attente | 13785-13789 | tourne tant que `_left_button != 0` |
| survol | 13790-13832 | premiere ligne dont `_option_text[i]+$10 <= mousex <= _option_text[i]+LAB_51914[i]+$10` **et** `LAB_51912[i]+$10 <= mousey <= LAB_51912[i]+$18` |
| application | 13833-13893 | si `_in_conquest == -1` seulement |
| boutons | 13894-13938 | `_check_cancel(_end_ok, _end_cancel)` |
| sortie | 13939-13942 | `_return_to_game` (L13954) |

**Les 9 cases a cocher** (entrees 1 a 9, L13690-13710) : le masque part de
`1` et decale a gauche (`ASL (-4,A5)` L13740) ; l'octet de la coche vaut
`$80` eteint, `$81` allume ; un clic fait `EOR.W` de `1 << (i-1)` sur
`LAB_516B2[player]` (`_stats + $0E`, `power_mask`) - L13836-13848.

**Les deux curseurs** : entree 11 = AGGRESSION (`LAB_516B0`, `_stats+$0C`,
`threshold`), entree 13 = RATE (`LAB_516B4`, `_stats+$10`, **la periode des
decisions IA**, L17939 `DIVU`). La valeur vient de
`(mousex - (_option_text[i] + $28)) / 8` pour 11, `+ $30` pour 13,
bornee a `0..9` (`TST.W` / `CMPI.W #$9`, L13863-13866).

**`_check_cancel`** (L12106) renvoie `0` tant qu'aucun des deux cadres n'est
 touche, `1` pour OK et `2` pour CANCEL - chacun teste une boite de 16 px de
 haut (L12125-12129). Le `0` renvoie au trace (L13938), le `2` restaure les
 46 octets, le `1` re-inverse les deux curseurs (L13916-13933) : la double
 inversion annule celle de l'entree.

Les quatorze lignes vivent dans une table de 14 entrees de `0x2E` (46) octets
a partir de `_option_text` (L24363) : `+0` x, `+2` y, `+4` largeur du test,
`+6` la chaine (40 octets, octet 0 = la coche). Elle est transcrite dans
`populous/options.py` et verifiee par `tools/check_options.py`, qui la relit
dans le listing.

## 4.4 ter Le code 2 — `LAB_4BA34` (L18404) — la liaison série

Deux instruction ouvrent le handler :

```python
if _serial_off:                     # L18405-18406  TST.W / BNE.W LAB_4C19C
    return
```

`_serial_off` valant **1** en un seul joueur (L12768), **c'est le chemin que
prend la totalité des parties** : le code 2 est un no-op, et l'icone `(2,2)`
de la barre ne fait rien. C'est transcrit tel quel.

Reste la branche à deux Amiga, non transcrite — elle lève
`NotImplementedError` :

* gardes `LAB_516A6[...] == 2` puis `_stats[...] == $0E` (L18416-18428) ;
* **émission** (L18430-18468) : `_get_a_message(_message)`, puis
  `_write_serial(&_message[k], 1, 1)` pour chaque octet non nul, un dernier
  appel pour le terminateur `$65`, puis remise à zéro ;
* **réception** (L18470-18606) : `_requester(d_screen, $28, $3C, $100, $50,
  _end_ok, 0)` — **sept** arguments avec `_end_cancel` **nul**, c'est-à-dire la
  voie « OK seul » de la routine (`LAB_45744`, où `end_ok.x1` est bien écrit,
  L10246, contrairement à la voie avec CANCEL) ; puis une boucle de 100
  octets (`CMPI.W #$0064`) de `_read_serial`, chacun rendu par
  `_text(d_screen, k*8 + $30, $4C, &_message[k])`, `$65` marquant la fin,
  enfin une attente de clic et `_check_cancel`.

## 4.4 bis `_game_options` — ligne 12801 (`$47722`) — le dialogue *GAME SETUP*

Handler du **code 8** de `_do_action` (`LAB_4BE12`, L18729), arme par l'entree
`(1,1)` de la barre d'icones (L1795). Meme boucle modale que `_options` :
sauvegarde, trace, attente du clic, survol, saut dans le handler de la ligne,
`_check_cancel`, `_return_to_game`.

| etape | lignes | detail |
|---|---|---|
| sauvegarde | 12803-12811 | cinq mots : `_serial_off`, `_paint_map`, `_player`, `_stats[_player]` et `_in_conquest` |
| `_bring_up_two` | 12812 | remis a zero |
| les dix coches | 12813-12884 | les variables `strOnePlayer` .. `strCustomGame` sont **dans** `strGameSetup` : c'est l'octet 0 de la chaine de l'entree |
| boite | 12886-12898 | `_requester(d_screen, $10, $10, $120, $B0, _end_ok, _end_cancel)` - **`$B0`**, et non `$A6` comme pour `_options`, parce que la colonne de droite est a x = 152 |
| traces | 12901-12924 | boucle `i` de 0 a 16 (`CMPI.W #$0011`) |
| attente | 12927-12929 | tourne tant que `_left_button != 0` |
| survol | 12866-12982 | comme `_options`, mais la boite y est `[y+$10, y+$18]` et la neutralisation de conquete (L12974-12978) renvoie l'index `$13`, hors tableau |
| dispatch | 13292-13308 | table de **17 sauts relatifs**, un par ligne |
| boutons | 13316-13324 | `_check_cancel(_end_ok, _end_cancel)` ; `0` retrace, `2` restaure et sort, `1` sort |
| sortie | 13356-13358 | `_return_to_game` (L13954) |

**La table unique.** `_game_text` (L24494), `LAB_51BDE` (L24496) et
`LAB_51BE0` (L24498) ne sont pas trois tables mais trois vues du meme bloc de
**782 octets**, indexees avec le pas `0x2E` et decalees de 0, 2 et 4 octets :

```
LAB_51BDE = 0x51bde = strGameSetup (0x51be2) - 4
LAB_51BE0 = 0x51be0 = strGameSetup - 2
_game_text = 0x51bdc = strGameSetup - 6
```

Chaque entree est donc `{WORD x ; WORD y ; WORD w ; char texte[40]}`, l'octet
0 de `texte` etant la coche - `$81` pour la ligne active, `$80` pour l'autre.
Le bloc finit a 0x51eea, ou commence `_c_text` (L24622). Les dix premieres
lignes sont cinq paires de boutons radio (x = 16 et x = 152), les sept
dernieres les actions (x = 80, largeur 128). Table transcrite dans
`populous/game_setup.py`, relue dans le listing par
`tools/check_game_setup.py`.

**`_serial_off` vaut 1 au depart** (L12768, comme L11240) : le nom est
trompeur, `1` signifie « liaison série **coupée** », donc un seul joueur. Le
prologue en fait `strOnePlayer = $80 + serial_off` (L12813-12815). Le port
l'initialisait a 0, ce qui le faisait partir sur la voie série du code 8.
Corige.

**Cinq lignes sur dix-sept lèvent encore** `NotImplementedError`, en nommant
la routine manquante - mieux vaut une erreur nommée qu'un écart muet :

| ligne | étiquette | branche active | routine |
|---|---|---|---|
| 2 | TWO PLAYERS | `serial_off == 0` | `_two_players` (L11265), L13021 |
| 9 | CONQUEST | `serial_off != 0` | `_show_world` (L12190), L13237 |
| 12 | SAVE A GAME | toujours | `_save_load(1)` (L10493), L13261 |
| 13 | LOAD A GAME | `serial_off == 0` | `_save_load(0)` (L10493), L13071 |
| 15 | RESTART THIS MAP | toujours | `_new_map = _ground_in + 2`, L13282-13284 |

La ligne 11 (*GAME OPTIONS*) est transcrite depuis la Phase 71 : elle ouvre
`_set_options`, décrit en §4.4 quater.

Noter l'**inverse** des branches 2 et 9 : TWO PLAYERS n'ouvre son écran que si
la liaison est **active**, CONQUEST ne part que si elle est **coupée**
(L13009-13010 contre L13225-13226).

La queue commune du handler, `LAB_4C070` (L18917-18942), consomme `_new_map`
(`___setup_display(0, new_map - 2)`, L18924) puis `_bring_up_two`
(`_two_players(1)`, L18936). La ligne 15 et cette queue sont transcrits
depuis la **Phase 77** : L13282-13284 pose `_new_map`, L18917-18931 le lit
et restaure `_seed = _start_seed` (L18922) seulement si `_new_map != 1`.

## 4.4 quater `_set_options` — ligne 13362 (`$47E56`) — l'écran *SET GAME OPTIONS*

Ligne 11 du dialogue précédent. Cinq paires de choix **exclusifs**, un bit de
`_game_mode` chacune.

| étape | lignes | détail |
|---|---|---|
| sauvegarde | 13364 | `_game_mode` dans `(-46,A5)` |
| boîte | 13365-13373 | `_requester(d_screen, $20, $18, $100, $70, ...)` — plus petite que celle de *GAME SETUP*, car les deux colonnes sont à x = 16 |
| titre | 13374-13383 | `strGameOptions[0]` à `(_set_text[0]+$20, LAB_523B0[0]+$18)` |
| les cinq paires | 13384-13446 | pour `j` de 0 à 4, colonne `1` ou `2` selon `(1 << j) & _game_mode` (L13386-13396) ; index `2*j + colonne` ; `_blank` puis le texte |
| rustine de debug | 13447-13482 | le listing la marque « new code added here » : « LANDSCAPE NO » puis le numéro de terrain à `buf + 13`, affiché sous la dernière paire avec un y de `+ $22` et non `+ $18` |
| attente | 13483-13488 | `_left_button = 2`, puis on tourne |
| survol | 13490-13587 | indices **impairs** 1, 3, 5, 7, 9 (`ADDQ.W #2`, `CMPI.W #$000A`) ; **entièrement neutralisé en conquête** (L13500-13501) |
| bascule | 13530-13546 | `bit = 1 << (i >> 1)` ; `_game_mode ^= bit` ; la coche part sur `i + 1` si le bit est désormais à 1, sur `i` sinon |
| boutons | 13489-13601 | `_check_cancel` ; `0` retrace, `2` restaure `_game_mode`, `1` sort |

**La table.** Comme pour *GAME SETUP* (§4.4 bis), un seul bloc de **506
octets** : `_set_text` (0x523ae, x), `LAB_523B0` (0x523b0, y), `LAB_523B2`
(0x523b2, largeur) et `strGameOptions` (0x523b4, les chaînes). Onze entrées,
dont le titre. Les dix autres sont cinq paires à x = 16, **de même y**,
largeur **8** : la zone cliquable ne couvre que les huit pixels de la coche.

**Deux particularités du listing, reproduites telles quelles** :

* le décalage de `$20` n'apparaît **qu'une fois** dans le test de survol, à
  gauche (L13496) : `x1 = _set_text[i] + LAB_523B2[i] + $20 = x0 + w`.
  Contrairement à `_options` et `GAME SETUP`, la zone fait donc 8 px, pas 40 ;
* le cadre **OK** (`x ∈ [48, 96]`, `y ∈ [97, 113]`) **recouvre la neuvième
  ligne** (`x ∈ [48, 56]`, `y ∈ [104, 112]`). Comme le listing teste les
  lignes *avant* `_check_cancel`, cliquer OK dans cette bande allume au
  passage la cinquième paire.

**Les deux colonnes d'une paire partagent x et y.** Redessiner l'une efface
donc l'autre — ce qui est voulu, puisque `_blank` est justement tracé pour
cela. Mais `_blank` ne fait que onze caractères (`^^^^^^^^^^^`, L24918) alors
que « SWAMPS BOTTOMLESS » en compte dix-sept : le reste de l'ancien texte peut
subsister. Fidèlement reproduit, cosmétique et sans conséquence.

**`_game_mode`** est un `DS.B 1` (L24310) : il démarre à zéro, et le prologue
affiche alors les cinq colonnes 1 décochées. Il est alimenté par
`conq_04_mode` au chargement d'un palier (L425-427) — seul endroit du port où
le champ est écrit.

## 4.4 quinquies `_get_name` — ligne 10307 (`$458D0`) — le champ de saisie

C'est la **seule** routine de saisie du jeu : *WORLD TO CONQUER*, les deux
champs de *SAVE/LOAD*, les deux champs de l'écran de liaison, et la boîte
de `_get_a_message` passent toutes par elle.

```text
_get_name(texte, x, y, maxlen, end_ok, end_cancel) -> texte (en place)
```

Les six appels empilent les mêmes **sept arguments, 22 octets**
(`4+4+2+2+2+4+4`) : L10798 tiroir `($58,$8D,$10)`, L10814 nom de fichier
`($58,$A0,$10)`, L11177 `($30,$64,$1C)` après un `CLR.B (A0)`, L11628 et
L11675 les deux champs de `_two_players` (`maxlen = $11` et `$06`,
`end_cancel = NULL` — la voie « OK seul »), L12249 `_message`
`($20,$2C,$10)` avec les deux cadres de *WORLD TO CONQUER*.

### Le cadre (`LINK.W A5,#-46`, L10308)

`scratch` occupe les 40 octets de `(-40,A5)`. Trois mots se partagent le
reste, **le même emplacement servant à deux usages successifs** :

| offset | pendant le remplissage | ensuite |
|---|---|---|
| `(-46,A5)` | `curseur` = `strlen(texte)` (L10310-10312) | `curseur` |
| `(-44,A5)` | `apres_fin` (L10313, écrit à L10321) | compteur `t` du clignotement (L10355-10358) |
| `(-42,A5)` | index `i` (L10317-10340) | `rr` de `_check_cancel` (L10443), puis `i` du trim (L10472) |

### Remplissage (L10313-10347)

Tant que `i != maxlen` (L10339-10341) : si `texte[i] <= $20` **ou** si le
premier zéro est déjà passé (`(-44)` posé à L10321), l'octet devient
`$82` (L10325-10332) ; `scratch[i]` reçoit `$82` de toute façon (L10336).
Puis `texte[maxlen] = 0` et `scratch[maxlen] = 0` (L10344-10347).

Deux conséquences vérifiées par `tools/check_get_name.py` :

* l'espace **interne** d'un nom (« POP SAVES ») devient `$82` — c'est un
  glyphe de remplissage, pas un blanc ;
* les sept appels dessinent **exactement `maxlen` glyphes**, jamais un de
  plus, même quand la chaîne d'entrée est plus longue que le champ.

### La souris vit dans la boucle

`_setup_interrupt` (L187-207) enregistre `___mouse` par
`___AddIntServer(..., 5.W)` — l'interruption VERTB. Le port n'a donc **pas**
un champ « gelé » : `_read_buttons` tourne pendant la saisie, et
`_check_cancel` (L10441) teste réellement `_left_button`, mis à 2 en
entrée (L10348) avant même le premier dessin.

### Boucle (LAB_4597A, L10356-10459)

1. clignotement (L10356-10380) : écrit seulement si `t % (maxlen + 20) == 0`,
   et met `$83` si l'octet valait déjà `$82`, `$82` sinon — le curseur
   alterne. Avec `maxlen = 8`, la période est 28 images ;
2. `_text(texte)` (L10382-10387) ;
3. `_keyboard` (L10388) — **une touche par image**, 0 sinon ;
4. frappe : `$20..$7A` seulement (L10392-10395), refusée dès que
   `curseur >= maxlen - 1` (L10396-10400). On pose `$82` à la position et
   on **redessine avant** d'écrire la lettre (L10403-10408), puis on force
   la majuscule par `SUBI #$20` (L10410-10414) ;
5. `$08` **et** `$7f` font la même chose (L10422-10425) : `curseur != 0`,
   décrément, `$82` à l'ancienne place (L10427-10432) ;
6. `$0D` sort directement à `LAB_45ABA` (L10435-10437) ;
7. `_check_cancel(end_ok, end_cancel)` (L10439) :
   * `rr == 0` → reboucle, en remettant `left_button = 2` si le clic
     venait de finir (L10454-10457) ;
   * `rr == 2` (CANCEL) → `texte[0] = 0`, rend la main (L10445-10451) ;
   * sinon → validation.

### Validation (L10460-10489)

`texte[curseur] = $82` puis un dernier `_text` (L10463-10468) — le curseur
reste visible à l'instant de la validation. On part de `i = maxlen - 1`
(L10470-10472) et on remonte tant que `texte[i] > $80` (L10479-10487),
effaçant au passage : seuls les `$82` de fin disparaissent.

**Lecture hors tampon modélisée à 0** : le test `texte[i]` (L10480-10484)
a lieu **avant** `i >= 0` (L10486), donc le listing lit `texte[-1]`. Le
port ne reproduit pas cette lecture et traite l'indice négatif comme un
octet nul, ce qui arrête exactement la même boucle.

### Ce que le port y a ajouté

* `Game.get_name(...)` et, avec, `Game.afficher()` — sur l'Amiga `_text`
  écrit dans le plan que le copper balaye, l'effet est immédiat ; le port
  doit faire `frame → screen` puis `flip` à chaque image, sinon la boucle
  modale reste figée sur la dernière image du jeu ;
* `handle()` déverse les `KEYDOWN` dans `_touches` dès que `_saisie`, et
  `_keyboard()` en retire **un** par appel, tronqué à `& 0xFF` (même
  troncature que le `MOVE.B` de L19062). **ECART déclaré** : le port
  clavier Amiga est du matériel, comme la liaison série — seul le contrat
  est transcrit, la table `keycodes` (L19085) étant remplacée par
  `ev.unicode`.

## 4.5 Les effets

### `_do_magnet` (ligne 6769, `$42F34`) — coût 200

```python
def do_magnet(tribe, x, y):                         # L6769  $42F34
    if mana[tribe] < 200:                 return    # L6771‑6777  (LAB_5187C)
    if magnet[tribe] == 0:               return    # L6778‑6783  il faut une cible
    if war:                              return    # L6784‑6785
    effect = 0x4D                                   # L6786  (son)
    mana[tribe] -= 200                              # L6792‑6793
    x = min(x, 0x3F) ; … clamps                     # L6794‑6796
    set_magnet_to(tribe, x, y)                      # → _set_magnet_to (ligne 8271)
```

`_set_magnet_to` (ligne 8271) écrit `LAB_52DE6` et alimente `_god_magnet`
(`$00054266`) / `_devil_magnet` (`$00054264`).

### `_do_flood` (ligne 7567) — 40 000
Soutrait 1 à `_map_alt` des **4 225** cases et ajoute **+250** au score.

### `_do_quake` (ligne 7863) — 2 500
Zone 10 × 10 ; par case, `newrand() % 5` décide relèver/abaisser ; **+25** points.

### `_do_volcano` (ligne 8046) — 10 000
Cône de rayon 5 → 0, `_map_blk = $2F` (rocher au sommet) ; **+100** points.

### `_do_swamp` (ligne 8295) — 5 000
30 essais : `x = rand, y = rand` ±3 ; la case doit être `$0F`/`$1F`/`$20`/`$42` et vide ;
elle devient `$35` ; **+50** points.

### `_do_knight` (ligne 8392) — 7 500
Prend le peep `_magnet[tribe]-1` et force son `+0x12` (spawn_block) à **1** ; **+150** points.
**[?] le sens exact de `+0x12 = 1` n'est pas démontré.**

### `_do_war` (ligne 8482) — 80 000
Efface `+0x12` de **tous** les peeps, pose `_war = 1` ; **+5 000** points.
En guerre : les coûts de relèvement sont ignorés (§4.2) et tous les aimants valent
`0x0820` (ligne 3428‑3432).

## 4.6 Les tables chargées depuis le disque : `_load_ground` — ligne 16468 ($4A23E)

```python
def load_ground(land, unused):                      # L16468  $4A23E
    name = "LAND" + chr(0x30 + land)                # L16472‑16475  strLAND + chiffre
    fh = Open(name, 0x3ED)                          # L16477‑16482
    Read(fh, &_walk_death,      2)                  # L16483‑16487
    Read(fh, &_population_add, 0x16)                # L16488‑16492  22 B = 11 mots
    Read(fh, &_mana_add,       0x16)                # L16493‑16497
    Read(fh, &_weapons_add,    0x16)                # L16498‑16502
    # ─── L16504 : « lines cut here » (trou de désassemblage) ───      # §9.1
    Read(fh, &_battle_add1,    0x16)                # L16506‑16510
    Read(fh, &_battle_add2,     6)                  # L16511‑16515
    Read(fh, &_map_colour,     0x10)                # L16516‑16520
    Read(fh, &tmp,              2)                  # L16521‑16525
    Read(fh, &_blk_data,     0x8340)                # L16526‑16530  graphismes de terrain
    Close(fh)                                       # L16531‑16533
    # puis expansion de la palette _map_colour[i] → [i+16]             # L16543‑16547
```

* Adresses BSS : `_walk_death $0005C39E`, `_mana_add $0005C3A4`,
  `_weapons_add $0005C3BA`, `_population_add $0005C3D0`,
  `_battle_add1 $0005C3E8`, `_battle_add2 $0005C3FE`, `_cheat $0005C3A2`.
* Chaque table indexée par l'âge fait **22 octets = 11 mots = âges 0…10**, ce qui
  confirme le découpage `frame = 0x20 + âge`, `0 ≤ âge ≤ 10`.
* **Les valeurs de ces tables ne sont pas dans le listing** : elles viennent du fichier
  `LAND0…LAND9`. Voir §9.2.
* Le fichier est choisi par `conq_05_terrain` (lignes 395‑403) ou par la sous‑commande
  `_do_action` 13 (ligne 18985‑18987).

---

# 5. Chapitre 4 — IA adverse et `level.dat`

## 5.1 `level.dat`

**Chargement** (lignes 12320‑12363) :

```python
def load_level_entry(selected_level):               # L12315‑12363
    entry = selected_level // 0x19                  # L12318  ÷25 → index d'entrée
    fh = Open("level.dat", 0x3ED)                   # L12340‑12344
    Seek(fh, entry * 10, OFFSET_CURRENT)            # L12347‑12354  10 octets par entrée
    Read(fh, &_conquest, 10)                        # L12358‑12362
    Close(fh)
```

* **990 octets = 99 entrées × 10 octets** (commentaire du désassemblage, ligne 12322).
* « The game has 99 * 5 = 495 levels » (ligne 12323).
* Le numéro de monde affiché est `selected_level // 5` (ligne 12391).
* Les 10 colonnes et leurs valeurs admises sont listées lignes 12324‑12338
  (copie quasi identique en 24316‑24327) — par exemple la colonne 5 (`terrain`)
  n'accepte que `00 01 02 03`, la colonne 4 (`mode`) `00 01 03 04 08 0a 10 11 12`.
* Le nom du fichier est en dur : `"level.dat"` (lignes 11012, 12797).

## 5.2 Application des paramètres : `_setup_display` — ligne 380 ($3E5CE)

```python
def setup_display(a, ground):                                  # L380  $3E5CE
    if in_conquest != -1:                                      # L382‑383
        seed = start_seed = (in_conquest & 7) + conq_08_seed   # L388‑392
        ground_in = conq_05_terrain                            # L399  0..3
        load_ground(ground_in, 0) ; clear_map()                # L400‑404
        stats[1].threshold  = _conquest[0]                     # L407‑408
        stats[1].period     = conq_01_speed                    # L410‑411
        stats[1].power_mask = (conq_02_enemypow << 3) | 7      # L414‑418
        stats[0].power_mask = (conq_03_yourpow  << 3) | 7      # L419‑423
        _game_mode          = conq_04_mode                     # L425‑427
        goto LAB_3E6AE                                         # L428
    else:                                                      # L429‑458
        start_seed = seed                                      # L430
        if seed != 0:                                          # L431‑432
            seed = newrand()                                   # L433  tirage NON conditionné
            if (seed & 1) != 0 and ground == -1:               # L434‑437
                ground_in += 1                                 # L438
                if ground_in > 3: ground_in = 0                # L439‑441  BLE
                load_ground(ground_in, 0)                      # L443‑446
        if ground != ground_in and ground != -1:               # L448‑456
            load_ground(ground_in, 0)
        clear_map()                                            # L458
    if a != 0: goto LAB_3E6CE                                  # L460‑461
    make_alt() ; make_map(0,0,63,63) ; make_woods_rocks()      # L462‑469
LAB_3E6CE:                                                     # L471‑487
    Setscreen ×2 ; draw_map(0,0,63,63) ; copy_screen ×2        # rendu
    place_first_people()                                       # L495
    seed += 1                                                  # L496
```

* `conq_01_speed` → `_stats[1]+0x10` = **période, en tours, entre deux décisions de
  l'IA**. C'est le vrai « niveau de difficulté ».
* `<<3 | 7` : les 3 bits de poids faible sont toujours à 1 (actions de base toujours
  autorisées), les 8 bits suivants sont les pouvoirs.
* `_game_mode` bits testés en 12488‑12546 : `bit0…bit4` =
  construire sur gens / villes / uniquement en haut / marais / eau **[?] ordre exact**.

### Les cinq appels, et le rôle des deux arguments

`a` = `(8,A5)` (premier argument), `ground` = `($A,A5)` (second). Les cinq
appels du listing passent **tous** `a == 0` : `_animate` L511 `(0, 1)`,
L552 `(0, -1)`, `_two_players` L11815 `(0, -2)`, `_won_conquest` L14432
`(0, -1)` et `_do_action` code 8 L18928 `(0, _new_map - 2)`. La branche
`a != 0` (L460‑461), qui sauterait `make_alt` / `make_map` /
`make_woods_rocks` après `_clear_map`, n'est donc jamais atteinte.

`ground`, lui, **n'est jamais affecté à `_ground_in`** : il ne sert qu'aux
deux tests des L436 et L448‑451. Il autorise, il ne prescrit pas.

Trois conséquences, toutes vérifiées par `tools/check_setup_display.py`
(Phase 77) :

* `ground == -1` est la seule valeur qui puisse faire tourner le terrain
  — et seulement si `seed != 0` **et** si le bit0 du prochain `newrand`
  vaut 1. `ground == ground_in` (le « RESTART THIS MAP », `_new_map - 2`
  avec `_new_map = _ground_in + 2`) regénère le même relief.
* L433 tire **avant** de tester : le `newrand` a lieu même si
  `ground != -1`, donc il n'est jamais conditionné.
* L496 (`seed += 1`) est la toute dernière écriture de la routine, après
  `_place_first_people`.

### Ce que le port en fait (`Game.setup_display`, Phase 77)

Le port ne peut pas découper `Terrain.build` (clear + alt + map + bois en
une passe) et doit reconstruire `Terrain` + `Renderer` + `Sim` d'un bloc.
`set_ground(..., conserver_etat=True)` reprend alors, sur la fiche
neuve, tout ce que la routine n'a jamais touché — `_in_conquest`,
`_stats`, `_player`, `_serial_off`, `_game_mode`, les coches de GAME
SETUP — et `Game.start_seed` porte `_start_seed` (L430, L392, L18922).
`_ground_in` vit dans `Game.ground`, avec `sim.ground_in` en miroir (le
champ que `_save_game` / `_load_game` écrivent).

## 5.3 Le rythme de l'IA : `_get_message` + `_move_peeps`

```python
# chaque tour :                                               L17934‑17951
if stats[t].p06 == 1 and game_turn % stats[t].p10 == 0:
    stats[t].p08 = 0                 # l'action précédente est consommée

# à chaque peep villageois :                                  L3497‑3543
if (stats[t].p06 == 1 and not bit2(LAB_518A7)) or war:
    stats[t].act = 1                 # 1 = relever le point
    stats[t].x, stats[t].y = pos du peep
    stats[t].p08 = 1                 # « en file d'attente »
```

Donc **l'IA ne « réfléchit » pas** : elle choisit la case d'un de ses villageois et
publie l'action `1` (relèver) dans `_stats`. Le reste (choix du pouvoir, cible) passe
par `_do_computer_effect`.

## 5.4 Routines IA

| Symbole | Ligne | Rôle |
|---|---|---|
| `_make_level` | 9017 | calcule le relief/`+0x14` d'une case ; retour stocké en `peep+0x14` (lignes 3794‑3797, 3816) |
| `_one_block_flat` | 9148 | aplatit une case : exige `mana ≥ 20` et un compteur `≤ 50` |
| `_devil_effect` | 9300 | effets « démon » du tour (appelé ligne 3268 si `stats[t].p08 == 0`) |
| `_set_devil_magnet` | 9601 | choisit la cible de l'aimant ennemi (appelé ligne 3259) |
| `_do_computer_effect` | 9526 | choisit et publie le pouvoir utilisé par l'ordinateur |
| `_place_first_people` | 7652 | population initiale (§2.1) |
| `_make_woods_rocks` | 8535 | peuple la carte d'arbres/rochers |
| `_settlement_creation` | 7359 | création des implantations |
| `_do_funny` | 8630 | créatures animées (voir §7.4) |

Champs IA effacés **chaque tour** (lignes 3313‑3321) :
`_stats[t]+0x22` (meilleur peep ennemi), `+0x26`, `+0x2A` (peep le plus « mûr »).

Suivi des cibles pendant le tour (lignes 3679‑3763) :

```python
    # meilleur score _check_life :                               L3679‑3703
    if check_life_score > best[tribe]:
        best[tribe] = check_life_score
        stats[1 - tribe].p22 = p              # L3701‑3703  l'AUTRE tribu le cible
    # âge maximal (game_turn − peep+6) :                          L3705‑3735
    if min[tribe] > game_turn - p.born_turn:
        min[tribe] = game_turn - p.born_turn
        stats[1 - tribe].p26 = p              # L3733‑3735
    # ancienneté maximale :                                       L3737‑3763
    if max[tribe] <= game_turn - p.born_turn:
        max[tribe] = game_turn - p.born_turn
        stats[tribe].p2A = p                  # L3757‑3763  stocké pour sa propre tribu
```

---

# 6. Chapitre 5 — Écrans de victoire et de défaite

## 6.1 `_start_game` — ligne 13966 ($485EC)

```python
def start_game():                                   # L13966
    CloseWorkBench() ; open_channels()              # L13968‑13969
    load_sound("gmusic1")                           # L13970‑13972
    read_back_scr() ; create_mouse()                # L13973‑13974
    if start_of_game == 3:                          # L13975  mode tutoriel
        copy _tutorial  → _stats        (11 longs + 1 mot = 46 B)   # L13977‑13983
        copy LAB_5172E → strABC                     # L13984‑13990
        _pause = 1                                  # L13991  le tutoriel démarre en pause
        toggle_icon(1, 3, 0x17E4)                   # L13992‑13996
        _seed = _start_seed = 0x69BC                # L13998‑13999
        _game_mode = _tutorial_game_mode            # L14000
    _pointer = 1 ; _left_button = 2                 # L14002‑14003
    Setscreen(back_scr, back_scr, -1)               # L14004‑14007
```

## 6.1.1 `_start_of_game` — mot de configuration initial (L3E2A2, L4860A)

`_start_of_game` est initialise au tout debut du programme (`_main`,
L3E28C-3E2B6) :

```asm
CMPI.W  #$0002,(8,A5)          ; argc == 2 ?
BNE.S   LAB_3E2A8
MOVEA.L ($A,A5),A0             ; argv
MOVE.L  (4,A0),-(A7)           ; argv[1]
JSR     (___atoi,A4)           ; atoi(argv[1])
MOVE.W  D0,(_start_of_game,A4)
...
LAB_3E2A8:
MOVE.L  #$00000042,(-6,A5)     ; $42 = adresse du packet de demarrage Amiga
MOVEA.L (-6,A5),A0
MOVE.W  (2,A0),(_start_of_game,A4)   ; champ 2 du packet OS
```

Trois valeurs ont un sens dans le jeu :

| Valeur | Nom | Effet |
|---|---|---|
| **0** (defaut) | Partie normale | `_clear_map` pose `_set_mode_icons(1,6)` et `_set_tend_icons(3,4)` (L1026-1035) |
| **2** | Choix monde direct | `_animate` L3E7B0-3E7E3 : `___clr_wsc`, `___swap_screens`, boucle `_show_world` jusqu'a choix, puis `_return_to_game` + `_setup_display(0,-1)` |
| **3** | Tutoriel/demo | `_start_game` L4860A-48660 : copie `_tutorial` (46 octets) sur `_stats`, `LAB_5172E` sur `strABC`, `_pause=1`, `_seed=_start_seed=0x69BC`, `_game_mode=1`, `toggle_icon(1,3,0x17E4)` |

`_place_first_people` (L7656, L7758) teste aussi `_start_of_game == 3` pour utiliser les colonnes `conq_06/07` de `level.dat` comme en conquete.

Le port expose `Game.start_of_game` (defaut 0), definissable par le 6e argument CLI.

## 6.2 `_end_game` — ligne 14019 ($48698)

Table de 7 entrées (lignes 14284‑14290, dispatch borné à 7 en 14291‑14297) :

| cas | étiquette | ligne | contenu affiché |
|---|---|---|---|
| 0 | `LAB_486AA` | 14027‑14037 | **`strLost`/`strWon`** copié dans `strLOST` (tableau de 46 B, indexé `MULU #$2E`) |
| 1 | `LAB_489CA` | 14281 | no‑op |
| 2 | `LAB_486EC` | 14049‑14066 | `_battle_won[player]` et `_battle_won[not_player]` convertis en chaînes |
| 3 | `LAB_48724` | 14067‑14108 | compte les peeps avec `target != 0` **et** `life != 0`, séparés par tribu |
| 4 | `LAB_487A6` | 14109+ | compte les peeps avec `state == 1` (villageois), `life != 0`, `frame != 0x2A` |
| 5 | `LAB_4883E` | 14155-14203 | compte les peeps avec `state == 1` (villageois), `life != 0` et `frame == 0x2A` (grande ville), separes par tribu |
| 6 | `LAB_488DC` | 14204-14280 | **le score** (voir ci-dessous) |

**Calcul du score** (lignes 14204-14271), transcrit dans
`populous/endtext.py:score_final` :

```python
    if _battle_won[player] > _battle_won[not_player]:
        score += 5000                    # L14205-14217
    masque = 8                           # L14219
    while True:                          # L14220-14241  six bits, 3..8
        if not (_stats[player].power_mask & masque):       score += 1000
        if     (_stats[not_player].power_mask & masque):   score += 1000
        masque <<= 1
        if masque > 0x100: break
    if _serial_off:                      # L14242-14243   solo
        score += 15 * (10 - _stats[not_player].p10)   # L14244-14252
    if arg1 == 0:                        # victoire
        score *= 10                      # L14254-14260
    if score < 500:      score = 500          # L14263-14265
    if score > 555_555:  score = 515_090      # L14268-14270
    long_asc(score, &strScoreboard[idx*46])   # L14272-14278
```

**Remplissage des lignes 2 a 5** (lignes 14299-14336) : `word_asc`
(L21054-21101) ne pose **aucun espace** ; c'est L14303-14320 qui complete le
premier nombre **a cinq caracteres, avec des espaces derriere lui**, puis
`___strcpy` + `___strcat` posent le second. `strScoreboard` =
`strGAME_ + 19` (L24803) : le chiffre s'ecrit donc a l'octet 19 du gabarit,
et le zero final tronque tout ce qui suivait.

**Ligne 5, ecriture morte** : L14202 recopie `(-14,A5)` dans `(-10,A5)`
**apres** les deux `___word_asc` ; les chaines sont deja ecrites, l'ecriture
n'a aucun effet a l'ecran.

**Titre de la boite** (lignes 14341-14354) : `strTryItAgain` si `perdu != 0`
**et** `_in_conquest != -1`, `strNew_Game` sinon. Chaines visibles :
`GAME LOST` / `GAME WON` (le `GAME ` de `strGAME_` reste en tete),
`LOST`, `WON`, `TRY IT AGAIN`, `NEW GAME`.

**La boite elle-meme** (lignes 14356-14364) : **une seule**
`_requester(_d_screen, $10, $10, $120, $A6, (-60,A5), NULL)`, puis **sept**
`_text(_d_screen, x + $10, y + $10, chaine)` (lignes 14365-14389) sur les
sept enregistrements de `_end_text` / `LAB_5226E` (46 octets chacun).

## 6.3 `_won_conquest(score)` — ligne 14460 ($48BAC)

```python
def won_conquest(score):                             # L14460  $48BAC
    old = _level_number                              # L14463
    _level_number += score // 5000 + 1               # L14465‑14469   (constante 0x1388)
    if _level_number % 5 != 0:                       # L14472‑14476  DIVS #5 / SWAP
        _level_number += 5 - (_level_number % 5)     # L14477‑14483  → multiple de 5
    if _level_number > 0x9A6:                        # L14485  2470
        if old == 0x9A6:                             # L14487
            _level_number = 0 ; flag = 1             # L14489‑14491  boucle du jeu
        else:
            _level_number = 0x9A6                    # L14493‑14495  plafond « WEAVUSPERT »
    _seed = _level_number                            # L14497
    newrand() ; code(newrand(), &_message)           # L14498‑14502
    save_music_off/effect_off ; both = 0 ; kill_effect(4, 0)   # L14503‑14510
    if read_lord() != 0:                             # L14511‑14513
        read_mouth()                                 # L14514
        free_all_sounds() ; load_sound("gwords")     # L14515‑14517
        _seed = old                                  # L14519
```

**Lecture** : le score convertit en un nombre d'« étapes » (`score/5000 + 1`), le
compteur est ensuite **arrondi au multiple de 5 supérieur**, ce qui saute toujours un
niveau quand il n'est pas déjà aligné (commentaire : « Presumably skips 1 level per
50,000 points », ligne 14471 — le diviseur réel est **5000**). Maximum `0x9A6 = 2470`.

## 6.4 Les deux écrans animés

### `_read_lord` — ligne 16631
Charge `lord.pic` : 32 000 octets dans `_w_screen` (L16640‑16643), puis 32
octets — 16 mots — dans `_tcmap[0..15]` (L16645‑16648). Retourne 0 si
l'ouverture échoue (test en 14512) ; c'est ce que teste L14513, et dans ce
cas `LAB_48F84` saute tout le discours.

**Le point clé** : `_tcmap[0..15]` devient la palette du portrait. Toute
image dessinée dans `_w_screen` pendant le discours — donc les bouches
**et** les glyphes de `_text` — se teinte avec elle, pas avec `_palette`.
La boucle L14590‑14603 recopie ensuite `_palette[i]` dans `_tcmap[i+16]`
(couleurs des sprites) et appelle `_make_copper` **une seule fois** : il n'y
a aucun cycle de palette par image.

### `_read_mouth` — ligne 16668
Charge `mouths.pic` (0x13B0 = 5 040 B) dans **`_map_steps`** (le tampon est réutilisé,
`$00059376`).

### `_draw_mouth` — ligne 19894

```python
def draw_mouth(ecran, x, y, compte, index):            # L19894
    dst = ecran + x + y * 40
    src = _map_steps + index * 840                     # MULU #$348, L19906
    for _ in range(compte):                            # DBF, L19920
        for plan in range(4):                          # +0, $1F40, $3E80, $5DC0
            ecran[dst + plan * $1F40 : +6] = src[0:6]
            src += 6
        dst += 40                                      # ADDA.L #$28, L19919
```

`0x13B0 = 5040 = 6 × 840` → **6 bouches** au total (indices 0-4 + yeux).

**Format des donnees** :
* Fichier `mouths.pic` : 5040 octets = 6 bouches × 35 lignes × 24 octets.
* Une ligne = 24 octets = 4 bitplanes × 6 octets = 48 pixels.
* Les 4 bitplanes se combinent bit a bit pour former un index 4 bits (0-15)
  par pixel : `idx = bp0 | (bp1<<1) | (bp2<<2) | (bp3<<3)`.
* Les appels du listing passent `compte = 0x23 = 35` : **toute** la bouche,
  d'un bloc. Aucun masque n'est teste (L19911‑19917 sont six `MOVE`
  inconditionnels) : l'index 0 est **opaque** et écrase le fond.

### Les deux appels

| ce que l'on pose | arguments | ligne | colonne en pixels |
|---|---|---|---|
| les yeux (bouche n. 5) | `_draw_mouth(_w_screen, $10, $4B, $23, 5)` | L14652‑14658 | 128 |
| la bouche | `_draw_mouth(_w_screen, $12, $87, $23, (-108))` | L14721‑14727 | 144 |

**`x` est un offset d'octets, pas de pixels.** `_draw_mouth` fait
`ADDA.L D0,A0` (L19900) sans le `LSR.W #3` que `_text` applique (L19978) :
la colonne se compte donc en octets, et une ligne fait `$28 = 40` octets
pour 320 pixels. `$10` vaut ainsi **128 px** et `$12` **144 px** — prendre
les valeurs au pied de la lettre met la bouche sur le bandeau de gauche du
portrait.

Les yeux sont posés **une seule fois**, quand le compteur `(-120)` vaut 16
dans la branche « mode termine » (L14650) ; comme l'asm écrit dans l'écran
déjà affiché, ils restent. La bouche est redessinée à **chaque** itération :
comme 35 lignes couvrent exactement les 35 lignes de l'image précédente,
osciller entre les bouches 0..4 donne l'impression d'une bouche qui parle.

### La boucle du discours (L14619‑14742)

Une itération = les **quatre** `_waittof` de L14717‑14720, puis le dessin,
puis :

```python
if _check_effect(2) == 0:              # L14731‑14732 : la voie sonne encore
    (-108) += (-110)                   # L14733‑14734
    if (-108) >= 4 or (-108) <= 0:     # L14735‑14738
        (-110) = -(-110)               # L14740
```

Les deux branches « hors fenêtre de mots » remettent `(-108) = 0` et
`(-110) = 1` (L14661‑14662 et L14714‑14715), de sorte que la bouche ne peut
osciller que pendant les itérations où l'on dit un mot — précisément celles
où `c` **n'avance pas** faute de canal libre (`_check_effect(2) == 0`).

* mode termine (`(-122) != 0`) : `_end_words[c-10]` aux compteurs 10..14 ;
* sinon : `_words[monde*2]` et `_words[monde*2+1]` aux compteurs 11 et 12,
  les `$FFFF` étant sautés (L14691) ; le compteur 10 joue le son 0 sans
  condition.

### Le texte

Deux `_text` **nus** — pas de `_requester` — en `x = 8` **pixels** (le
listing fait `LSR.W #3`, L19978) et `y = $B2` / `$BA` (L14526, L14559,
L14588) :

* première ligne : `strWellDoneConq` si le mode est bouclé, sinon
  `strWellDone` + `_con_text[level/250 + 0x18]` + `strYouConquered` —
  où `_con_text[0x18 + monde]` est la **note** (`MORTAL` … `ETERNAL GOD`,
  L21353‑21392) ;
* seconde ligne : `strBattleOverTry`, ou `GENESIS` si `_seed == 0` sinon
  `_code(newrand())`, puis `strNowBattleAt`, puis `_message`.

`_code` (L14793‑14889) assemble trois syllabes : `_start[graine & 0x1F]`,
 `_mid[(graine >> 5) & 0x1F]`, `_end[(graine >> 10) & 0x1F]` — exactement
 les tables que `decode()` inverse.

## 6.5 `_show_world` et le choix du monde

Deux appels. Dès l'amorce de la partie (lignes 537‑553), si
`_start_of_game == 2` :

```python
    if _start_of_game != 2: goto LAB_3E7E4           # L537‑538
    _start_of_game = 0 ; clr_wsc() ; swap_screens()  # L539‑541
    while True:                                      # L542‑547
        in_conquest = show_world()
        if in_conquest != -1: break
    return_to_game() ; setup_display(0, -1)           # L549-553
```

Le bouclage sur `-1` est le raccourci numerique : une saisie entierement
numerique est une **graine**, pas un monde, et la boite se rouvre aussitot.
Le second appel est la ligne 9 de *GAME SETUP* (L13237‑13240), qui lui
**ne boucle pas** :

```python
    in_conquest = show_world(); new_map = 1           # L13237‑13239
    goto LAB_47E4E                                    # _return_to_game
```

### Structure (L12190‑12773)

Trois boucles emboitees :

| label | ligne | rôle |
|---|---|---|
| `LAB_47064` | L12207 | `_requester($10,$18,$120,$A0, end_ok, end_cancel)` + titre |
| `LAB_470AC` | L12227 | trait, champ de saisie, lecture de la saisie |
| `LAB_47236` | L12377 | trace des **14** lignes (i = 1..14), attente du clic |

La saisie (L12240‑12313) a trois issues :

1. **numerique** — `atoi(_message) != 0` : le nombre est range en **mot**
   (`$FFF4` pour -12), `_message` efface, et la routine rend **-1 sans
   ouvrir `level.dat`** (L12262‑12273) ;
2. **`GENESIS`** → indice 0 (L12281‑12288, `strGENESIS1` L12782 et
   `strGENESIS2` L12786 sont les memes sept octets) ;
3. **nom** → `_decode` (L14900‑15119). Tant que l'indice est negatif, on
   trace `NO SUCH WORLD` et on reboucle **sans lire le clavier**
   (L12297‑12312) : dans l'original c'est une attente infinie.

L'indice devient ensuite l'entree de `level.dat` :
`index = monde / 25` (`DIVS #$0019`, L12315‑12319), lue par
`Open / Seek(index*10, 1) / Read($A) / Close` (L12340‑12367). Une entree
hors fichier rend zero octet et le tampon `_conquest` garde son contenu
precedent.

### `saisi` — le mot `(-22,A5)`

Efface a l'ouverture (L12192), mis a 1 des qu'un monde est valide
(L12314), relu en L12240 : la ou `_get_name` (L10307) prendrait la main.
Seul **un** chemin le laisse a 1 :

| ligne | effet |
|---|---|
| L12314 | `saisi = 1` |
| L12370 / L12376 | echec du disque : `saisi = 0`, retour a `LAB_47064` |
| L12758 | *NEW GAME* : retour a `LAB_47064` **sans y toucher** |

Donc la saisie clavier n'est reachable qu'apres un premier monde accepte,
en passant par *NEW GAME*.

### `_decode` (L14900‑15119)

Trois tables de 32 syllabes — `_start` L25075, `_end` L25108,
`_mid` L25141 — balayees **dans l'ordre start, mid, end** (neuf `LEA`,
L14914 à L15069). Pour chaque table, `_passe` prend la **premiere** syllabe
prefixe de la chaine a l'endroit du curseur (pas la plus longue), puis
avance de sa longueur. Le code en resulte :

```python
    code = start_i | mid_i << 5 | end_i << 10       # L15026‑15099
    for g in range(0, 5001, 5):                     # force brute, L15101
        jeu.seed = g
        if Rng(g).raw() & 0xFFFF == code: return g
    return -5
```

Retours : `-1` pas de syllabe de depart, `-2` pas de milieu, `-3` pas de
fin, `-4` (`strlen != curseur`), `-5` code jamais atteignable.

### Les 15 lignes de `strWorldToConquer`

`level.dat` apporte dix octets, interpretes par dix handlers (les
`line_1 … line_9`, `line_0`) :

| i | ligne | valeur |
|---|---|---|
| 0 | WORLD TO CONQUER | — (titre, trace en L12217) |
| 1 | BATTLE NUMBER IS | `monde / 5` |
| 2 | WORLDS LANDSCAPE IS | `_con_text[conq_05_terrain]` |
| 3 | HIS REACTIONS ARE | `_con_text[((10 - conq_01_speed) >> 1) + 4]` |
| 4 | HIS RATING IS | `_con_text[((10 - _conquest[0]) >> 1) + 9]` |
| 5 | LAND | `_con_text[14..17]` selon les bits 2/4/3 de `conq_04_mode` |
| 6 | THE SWAMPS ARE | bit 1 → BOTTOMLESS, sinon SHALLOW |
| 7 | WATER IS | bit 0 → FATAL, sinon HARMFUL |
| 8 | `…YOU   HIM` | — (entete de colonnes) |
| 9 | POPULATION | `conq_06_yourpop` / `conq_07_enemypop` |
| 10‑14 | EARTHQUAKES…FLOODS | YES/NO sur le bit `i-10` de `conq_03_yourpow` puis `conq_02_enemypow` |

Les lignes 1 a 7 passent par `_put_in_string(buffer, LAB_51EEE[i], texte)`;
les lignes 9 a 14 tracent elles-memes **deux fois** chacune, en
`(WORLD_X[i] + WORLD_W[i] + $10) >> 3` et `+ $48`, `y = WORLD_Y[i] + $18`.

### Ce que fait OK (L12762‑12771)

`_player = 0` ; `_not_player = 1` ; `stats[1].can_build = 1` ;
`stats[0].act = 0` ; `stats[0].queued = 1` ; `stats[1].queued = 0` ;
`_serial_off = 1` ; `_paint_map = 0` ; `_war = 0` ; `_level_number = monde`.
La routine rend alors ce monde.

---

## 6.6 L’introduction — écran titre, chute des cases, crédits (Phase 84)

Sur la disquette de 1989 le fichier `populous` (29 116 octets) **est** le
programme d’intro : il charge les ressources, joue l’attract, puis lance
`populous.prg` par `SUB_16E`. Le port est `populous/intro.py` ; le listing est
`tetracorp/populous_main.asm`, hunk S_0 `0x0000..0x6D27`, base A4 =
`SECSTRT_1+$7FFE` = `0xED26` (`SUB_65F0` ;65f0), d’où les offsets négatifs du
type `(-32074,A4)` = `0x6F52`.

### L’écran titre — `SUB_456` ( ;0456-052a)

* `SUB_17B2("load.pic")` ( ;045e-0466) charge les 40 064 octets (320×200×5
  plans + 64 octets de palette) et `SUB_549A(..., 5)` ( ;046c-0480) les
  affiche sur **cinq** plans, soit 32 couleurs, alors que `SUB_15FA` ;15fa
  n’alloue que des bitmaps à quatre plans.
* La boucle `LAB_4A0` ( ;04a0-051c) compte dans `(-6,A5)` et sort sur
  `CMP.L #$00055730,D0 ; BGT` ( ;04a8) avec le choix encore à 0.
* `TST.W (-32004,A4) ; BNE` ( ;04b0-04b4) ne sonde les zones **que si ce mot
  vaut 0**. Il vaut 2 à l’entrée ( ;0492) et repasse à 2 à la sortie
  ( ;051e) : le test n’a donc lieu qu’avec le bouton enfoncé.
* Les trois zones ( ;04b6-0512) comparent dans l’ordre : `[$9C,$AA[` ×
  `y ≥ $E7` → 3, `[$AA,$B8[` × `y ≥ $E7` → 2, `x ≥ $B8` × `y ≥ $F1` → 1 ;
  sinon la boucle reboucle sans rien rendre. C’est `intro.zone_titre`.
* `(-32002)` (x) et `(-32000)` (y) viennent du pilote souris, plafonnés à
  `$27F` puis divisés par deux (`LAB_529A` ;52a6-52ac) : les deux axes vivent
  dans `0..319`. C’est `intro.souris_amiga`.

### La chute des 100 cases — `SUB_1186` ( ;1186-1236)

1. `SUB_10A2(100)` ( ;11c4-11cc) range les colonnes dans `[232,244]` et les
   vitesses dans `[0,9[`, puis `SUB_1D0E` ( ;11d4) remet le curseur de
   crédits à zéro.
2. La boucle `LAB_11D8` ( ;11d8-120c) : `SUB_110A(100)` avance les cases
   (l’arrêt est détecté par `TST.W (-2,A5)` en ;114c, **pas** par un indice :
   le retour est le premier `D5` non nul, bug reproduit), `SUB_58CA` recopie
   `$1F40` mots entre deux tampons ( ;58ca), `SUB_1C12` dessine, `SUB_358`
   échange `(-32078)` et `(-32074)` puis appelle `SUB_308(..., $FFFF)`
   ( ;0358-0380), et `SUB_5792` lit `CIAA_SDR` — le clavier, **pas** les
   crédits.
3. La case `i` va en `x = (col-rang)*16 + $90` et
   `y = (col+rang)*8 + $20 - colonne[i] - hauteur[i]` ( ;1c32-1c4c), puis
   `MULU LAB_7226` + `LSR.W #7` ( ;1c5c-1c6a). `MULU` est non signé et `LSR.W`
   ne décale que le mot de poids faible : le résultat tient sur neuf bits, un
   `y` négatif revient en `y+512`. Sur les portées réelles (`x` dans
   `0..288`, `y` dans `-236..176`) ce repli vaut toujours `276..511`, donc
   `>= 200`, et `SUB_19EE` refuse d’y dessiner — mais la formule appliquée est
   celle du listing (`intro.echelle_pos`).
4. Si `DRAPEAU[i] != 0`, un second sprite recouvre la case huit lignes plus
   haut ; le `SUBQ.W #8` ( ;1c7c) porte sur l’ordonnée **brute**, avant mise
   à l’échelle, puisque ;1c70 recharge `D0/D1` sauvés en ;1c52.

La chute dure 58 tours ; au repos les colonnes valent 0 et les 100 cases
tiennent dans le losange `x` dans `0..288`, `y` dans `8..176`.

### Le dépassement de ligne dans `SUB_19EE`

Un paquet de 16 pixels tient sur **un** mot par couche : cinq mots
(masque + quatre plans) pour 10 octets, deux paquets pour les 32 pixels
( ;1a3a-1a42 puis ;1aaa-1ab2). Le débordement de `dec` pixels part dans le mot
suivant (`SWAP` puis `ADDA.W #2`, ;1a6e-1a78), et le paquet suivant repart à
cet endroit même : le pas entre paquets est de **2 octets**. Comme `A0` avance
sans reboucler de ligne, une sprite placée à `x >= 288` (`colonne + 4 >= 40`)
écrit les deux octets suivants au début de la ligne suivante — comportement
reproduit, pas corrigé. Le masque, lui, est chargé dans un registre pré-réglé
`$FFFFFFFF` ( ;1a2c) : c’est son mot haut qui fournit les bits de conservation
des `dec` premiers pixels.

### Le rouleau de crédits — `SUB_536` et `SUB_714`

* `SUB_536` ( ;0540-0556) désigne les deux tampons `LAB_1FA2`/`LAB_25E2` et
  arme les deux compteurs à `$4B` et `$32`.
* Le corps `LAB_76A` ( ;076a-0824), pour chaque slot :
  1. si `compteur == $32`, `SUB_1D1A(tampon)` trace la ligne suivante ;
  2. `p = compteur` ; `p > $19` → `p = $32 - p` ; `p < 0` → `p = 0`
     ( ;0790-07b8) : le fondu monte puis redescend ;
  3. `SUB_5026(tampon, ecran + compteur*$28, p)` ( ;07bc-07e8) ;
  4. `compteur - 1`, et `-1` → `$32` ( ;07f0-0824). Un cycle complet vaut
     `$32 + 1` = 51 tours, sauf le départ : `$4B - $32` = 25.

`SUB_5026` ( ;5026-50ae) applique `dest = (dest & conserv) |
(source & ~conserv)` plan par plan, avec `conserv = plan0_source |
FADE[fade]`. Comme `SUB_1D1A` met le plan 0 à `$FF` partout sauf dans les
glyphes, le fond est conservé et seuls les glyphes reçoivent le tramage.
`FADE` (`LAB_1F62`, neuf longs suivis d’une `DS.L 6`, soit 18 mots) va de
`$FFFF` (invisible) à `$0010` : ce n’est pas une rampe monotone, c’est un
tramage dont la densité de bits baisse.

Les 23 chaînes sont en `LAB_1DCE` (L2372-2394) ; le dump d’octets que le
désassembleur a mis en commentaires (L2346-2371) redonne les mêmes 402
octets, et le marqueur de fin est `DC.W $FF00` en ;1f60 : le `$FF` reboucle
sur la première chaîne.

### Ce qui reste ouvert (Phase 85)

`SUB_714` ( ;0714-...) : l’interpréteur de script à 16 lignes (`SUB_50B2`,
`SUB_50E6`, `SUB_1910`, lignes `LAB_15B6`→`LAB_15F6`, données `0x1272..0x15B4`),
`SUB_16E` (exécute `populous.prg`) et la glue OS/cuivre (`SUB_358`/`SUB_308`,
`SUB_58CA`). Les écrans d’attract `demo.pic` et `sprites0.dat` sont chargés par
l’original mais pas encore rejoués ici.

# 7. Chapitre 6 — Gestion du temps

## 7.1 Architecture : `_main` → `_animate`

```python
def main(argc, argv):                                # L42  $3E1EE
    AllocMem(...)          # sprites, blk_data, back_scr, écrans, copper …  # L45‑84
    start_of_game = atoi(argv[2]) if argc == 2 else word_at(0x42)[1]       # L85‑96
    open_screen() ; read_sprites() ; sprite_to_amiga()                      # L98‑102
    start_game()                                                          # L103
    setup_serial_interrupt() ; baud = 0x2580 ; set_serial()                # L105‑108
    animate()            # ← BOUCLE PRINCIPALE, ne revient qu'à la fin     # L109
    closeall()                                                            # L110
```

**`_animate` (ligne 502, `$3E730`) est la boucle de jeu.** Elle ne contient pas de
`RTS` interne : la boucle va du label `LAB_3E7E8` (ligne 556) au `BRA.W LAB_3E7E8`
(ligne 1013). Un tour = **une image**.

## 7.2 Corps d'une image

```python
def animate():                                       # L502
    setup_display(0, 1) ; toggle_icon(...)           # L509‑536
    if start_of_game == 2:                           # L537
        clr_wsc() ; swap_screens()
        while (in_conquest := show_world()) == -1: pass   # L542‑547
        return_to_game() ; setup_display(0, -1)      # L549-553
    start_of_game = 0                                # L555

  LOOP:                                              # L556  LAB_3E7E8
    # ── (A) tempo musical (§7.3) ─────────────────────────────────
    # ── (B) rendu ────────────────────────────────────────────────
    clr_wsc() ; no_sprites = 0 ; ok_to_build = 0 ; sound_effect = 0  # L611‑614
    move_mana()                       # jauge de mana                # L622
    draw_it(xoff, yoff)               # la carte                     # L623‑626
    for s in sprites: draw_sprite/draw_s_32                          # L627‑657
    draw_sprite(curseur)                                            # L658‑675
    # ── (C) simulation ───────────────────────────────────────────
    if not pause and not paint_map:                   # L676‑679
        do_funny()      # créatures décoratives       # L680
        move_peeps()    # ← LE TOUR DE JEU            # L681
    else:                                             # L683  (pause / carte peinte)
        for p in peeps:           # on ne fait que REDRAW, pas de simulation
            if p.life <= 0: continue                  # L690
            if p.tribe != player and not serial_off: continue  # L695‑698
            if p.state & 1:                           # L701
                draw_sprite(p.block, colour[stats[p.tribe].p20])  # L706‑711
    # ── (D) vue / événements ─────────────────────────────────────
    if view_timer: view_timer -= 1 ; …                # L740‑750
    if game_turn == 0x1000:                           # L752  tour 4096
        do_place_funny(start_seed & 3)                # L755‑758
    show_the_shield() ; swap_screens()                # L761‑762
    #   ^ tempo de la boucle : swap_screens → _swap_screens (L16743) →
    #     _Setscreen (L16695) → _show_screen (L19782‑19790), qui publie la
    #     liste de cuivre puis tourne sur `INTREQR & $0020` (vblank).
    #     Un tour par image, plafond 50 Hz PAL. Phase 62.
    # ── (E) entrées ──────────────────────────────────────────────
    # ── (E) entrées ──────────────────────────────────────────────
    keyboard()                                        # L764
    #   pavé numérique → défilement (scroll_n/nw/w/sw/ne/s/se/e)  L770‑833
    #   Échap  → quitte animate (return_3EB2A)                    L938
    #   F9     → display_debug                                    L866‑868
    #   '*'    → triche (si souris en haut à droite)              L873‑910
    #   'A'    → gagne la partie immédiatement                    L837‑858
    #   sinon  → paint_the_map(stats[player])                     L911‑919
    if mode & 0xE: sculpt() else: interogate()        # L963‑974
    zoom_map(...)                                     # L976‑990
    left_button  = (left_button  == 2) + 1            # L992‑1000
    right_button = (right_button == 2) + 1            # L1001‑1009
    get_message()    # ← exécute les commandes de _stats          # L1010‑1012
    goto LOOP                                         # L1013  BRA.W LAB_3E7E8
```

**Faits structurants :**

1. **Un tour de jeu = une image.** `_game_turn` n'est incrémenté que dans
   `_move_peeps` (ligne 3250), donc **le temps s'arrête en pause et en mode
   « carte peinte »** (`_paint_map`).
2. **La pause ne fige pas le rendu** : les peeps sont redessinés (boucle lignes 684‑737)
   mais `move_peeps` n'est pas appelé.
3. `_toggle` change d'état à **chaque image** (lignes 604‑609) : tout ce qui teste
   `_toggle` est « un tour sur deux » — c'est le cas de `mana += 1` (ligne 3302‑3308)
   et du `putpixel` de la carte (ligne 4016).
4. Les entrées clavier sont lues **après** la simulation, la commande `_stats` est
   exécutée **en tout dernier** via `get_message` (ligne 1011) — d'où la latence
   d'un tour entre un clic et son effet.

## 7.3 Tempo et fréquence cardiaque

```python
def compute_tempo():                                 # L563‑597
    if good_pop[player] == 0:                        # L561‑562
        tempo = 0 ; beat_two = 1                     # L596‑597
        return
    opp = 1 - player                                 # L563‑568
    ratio = good_pop[opp] // good_pop[player]        # L574‑581  (D0/D1 → ___divs)
    tempo = 50 - 2 * ratio                           # L582‑585
    if tempo < 7: tempo = 7                          # L586‑588
    beat_two = tempo // 3                            # L590‑593
    if tempo_now > tempo: tempo_now = tempo          # L599‑602
```

Ces compteurs sont consommés par **l'interruption verticale**, pas par la boucle de
jeu (lignes 19648‑19672) :

```python
    if tempo == 0: return
    tempo_now += 1                                   # L19653‑19655
    if tempo_now >= tempo:                           # L19656‑19657
        PlaySound(0x47, 0) ; tempo_now = 0           # L19658‑19662  « battement »
    elif tempo_now == tempo - beat_two:               # L19664‑19668
        PlaySound(0x48, 0)                           # L19669‑19671  contretemps
```

**Interprétation** : `tempo` est le nombre d'images entre deux battements du cœur.
Plus la population ennemie domine la vôtre, plus `tempo` est petit (plancher 7) :
**le cœur bat plus vite quand vous êtes en train de perdre**. Si vous n'avez plus
de population, `tempo = 0` et le cœur s'arrête.

## 7.4 Autres régulateurs

| Variable | Adresse | Rôle | Référence |
|---|---|---|---|
| `_game_turn` | `$00054258` | compteur de tours, `+1` par image où `_move_peeps` tourne | 3250 |
| `_toggle` | `$52DFA` *(LAB)* | inversement à chaque image | 604‑609, 3302, 4016 |
| `_pause` | `$00053010` | fige la simulation (bouton action 6) | 676, 18598‑18603 |
| `_paint_map` | `$00053012` | fige la simulation + désactive le contrôle de mana | 678, 7189, 7206 |
| `_war` | `$0005426E` | guerre globale : coût ignoré, aimants forcés | 3426‑3432, 7191, 8482 |
| `_speed` / `conq_01_speed` | `$516D2+0x10` | période des décisions IA | 410‑411 |
| `_view_timer` | `$0005424E` | temporisation de la vue | 740‑750 |
| `_game_turn == 0x1000` | — | à 4096 tours, `do_place_funny(start_seed & 3)` | 752‑758 |
| `_funny_done` | `$54270` | les créatures « funny » n'apparaissent qu'une fois | 4001‑4006 |

### `_do_funny` — ligne 8630 ($444EC)
Parcourt une table de **209 entrés** (`CMP.W #$00d1`, ligne 8634) commençant en
`LAB_5420A` :

```python
    e.active = 0 : next                              # L8637‑8638
    e.counter += 1                                   # L8640
    step = e.speed        (+0x15, octet signé)       # L8642‑8644
    e.pos += step         (+6, mot)                  # L8646‑8647
    if e.pos < e.min (+2) or e.pos > e.max (+3):     # L8648‑8661
        step = -step ; e.speed = step                # L8663‑8665  rebond
    if e.counter > 7:                                # L8668‑8669
        e.counter = 0                                # L8671
        if map_who[e.block] - 1 == courant: map_who[e.block] = 0   # L8673‑8683
        if e.field_A == 0:                           # L8686
            e.field_A = funny[e.field_14 * 12]       # L8689‑8696
```

---

# 8. Table des symboles les plus cités

| Symbole | Adresse | Déf. ligne |
|---|---|---|
| `_stats` | `$000516A4` | 25…(cnf 676) |
| `good_castles` | `$000516B8` | — |
| `good_towns` | `$000516BA` | — |
| `_conquest` | `$000518AA` | 24329 |
| `_offset_vector` | `$0005181A` | 24274 |
| `_mana_values` | `$00051874` | 24287 |
| `_player` | `$00052DE2` | 25319 |
| `_magnet` | `$00052DE4` | 25323 |
| `good_pop` | `$00052DEC` | — |
| `_pause` | `$00053010` | — |
| `_paint_map` | `$00053012` | 25361 |
| `_peeps` | `$00053014` | — |
| `_no_peeps` | `$0005424C` | — |
| `_game_turn` | `$00054258` | — |
| `_score` | `$00054260` | — |
| `_battle_won` | `$00054268` | 25418 |
| `_level_number` | `$0005426C` | 25422 |
| `_war` | `$0005426E` | 25424 |
| `_map_blk` / `_map_alt` / `_map_bk2` | `$56376` / `$57376` / `$58376` | — |
| `_map_steps` / `_map_who` | `$59376` / `$5B376` | — |
| `_build_count` | `$0005C376` | 25446 |
| `_walk_death` | `$0005C39E` | 25467 |
| `_cheat` | `$0005C3A2` | 25471 |
| `_mana_add` | `$0005C3A4` | 25473 |
| `_weapons_add` | `$0005C3BA` | 25476 |
| `_population_add` | `$0005C3D0` | 25479 |
| `_battle_add1` | `$0005C3E8` | 25484 |
| `_battle_add2` | `$0005C3FE` | 25487 |

Routines principales : `_animate` 502 · `_move_peeps` 3245 · `_move_mana` 3164 ·
`_set_town` 5865 · `_do_battle` 6066 · `_battle_over` 6207 · `_zero_population` 5645 ·
`_do_magnet` 6769 · `_set_magnet_to` 8271 · `_place_people` 6982 ·
`_do_lower_point` 7091 · `_do_raise_point` 7180 · `_sculpt` 7271 ·
`_place_first_people` 7652 · `_do_flood` 7567 · `_do_quake` 7863 ·
`_do_volcano` 8046 · `_do_swamp` 8295 · `_do_knight` 8392 · `_do_war` 8482 ·
`_make_woods_rocks` 8535 · `_do_funny` 8630 · `_do_place_funny` 8862 ·
`_make_level` 9017 · `_one_block_flat` 9148 · `_devil_effect` 9300 ·
`_do_computer_effect` 9526 · `_set_devil_magnet` 9601 · `_setup_display` 380 ·
`_start_game` 13966 · `_end_game` 14019 · `_won_conquest` 14460 ·
`_show_world` 12190 · `_read_lord` 16631 · `_read_mouth` 16668 ·
`_load_ground` 16468 · `_get_message` 17707 · `_do_action` 18376 ·
`_draw_mouth` 19894 · `_check_life` 20958.

---

# 9. Incertitudes

## 9.1 Les huit trous du désassemblage

Le listing porte, à huit endroits, la mention `lines cut here` :

| Ligne | Contexte | Impact |
|---|---|---|
| **3582** | au milieu de `_move_peeps`, traitement du villageois sur case vide (`large number of lines cut`) | **important** — l'enchaînement exact `state = 0x12` / `frame ≥ 8` n'est pas lu en entier |
| **4317** | dans `_move_explorer` / `_where_do_i_go` | déplacement des explorateurs incomplet |
| **7354** | avant `_settlement_creation` | création d'implantation |
| **9004** | avant `_make_level` | génération de relief |
| **14405** | dans `_end_game` | affichage final |
| **14437** | dans `_end_game` / `_won_conquest` | idem |
| **16368** | avant `_load_ground` | chargement des données de terrain |
| **16504** | **dans `_load_ground`**, entre `_weapons_add` et `_battle_add1` | **une lecture disque manque** — sans doute un tableau de 2 octets situé en `$5C3E6` (juste avant `_battle_add1`) |

**Conséquence** : toute table chargée depuis un fichier `LAND*` a un contenu
**inconnu du listing** (§9.2).

## 9.2 Tables dont les valeurs ne sont pas dans le listing

`_walk_death`, `_mana_add`, `_weapons_add`, `_population_add`, `_battle_add1`,
`_battle_add2`, `_map_colour`, `_blk_data` sont des zones `DS` (BSS, lignes
25467‑25492) **remplies à l'exécution** par `_load_ground` (ligne 16468).

Ce que l'on sait *pour certain* :

* `_walk_death` = **1 mot** (lecture de 2 octets, ligne 16484).
* `_mana_add`, `_weapons_add`, `_population_add`, `_battle_add1` = **11 mots
  (âges 0…10)** (lectures de 22 octets, lignes 16488, 16493, 16498, 16506).
* `_battle_add2` = **6 octets = 3 mots** (ligne 16511).
* `_mana_add[âge]` s'ajoute au mana **tous les 8 tours** (ligne 3876).
* `_weapons_add[âge]` **remplace** le niveau d'arme (ligne 3882).
* `_population_add[âge]` **s'ajoute** à `life` tous les 8 tours (ligne 4014).
* `_battle_add1[âge]` s'ajoute au mana après une bataille (lignes 6538‑6545).

**Non connues** : les valeurs numériques. Elles varient en plus avec le terrain
(`LAND0…LAND9`).

**Autre formule non démontrée** : les dégâts de `_do_battle`
(`weapons * (roll/100) + 10`) — l'ordre des opérandes de `___divs`/`___mulu` n'a pas
été vérifié. Voir §2.6.

## 9.3 Champs dont le rôle n'est pas établi

* `_stats+0x0C` (`LAB_516B0`) : comparé à 4 (ligne 7669) et utilisé comme seuil — rôle **[?]**.
* `_stats+0x18/+0x1A/+0x1C/+0x1E` : effacés/lus sans que leur usage n'ait été tracé **[?]**.
* `_stats+0x26` (`LAB_516CA`) : pointeur peep écrit en 3735, testé en 4092 — **[?]**.
* Pourquoi `_do_action` **bascule sur son 3ᵉ argument** alors que les codes 1‑13
  utilisent ce champ comme `y` (§4.4) : le comportement machine est certain,
  l'intention d'origine ne l'est pas.
* `_do_action` sous‑commandes 7 (ligne 18607) et 8 (`LAB_4BE12`, ligne 18729) :
  **transcrites** (phases 68 et 69). Les seize codes de la table le sont
  maintenant, queue de L18917‑18942 comprise depuis la **Phase 77**.
  `_two_players` (L11265), `_show_world` (L12190), `_set_options` (L13362),
  `_save_load` (L10493) et `_setup_display` (L380) sont tous transcrits.
  Seules routines appelées en aval encore **non** transcrites, qui lèvent
  `NotImplementedError` et sont nommées dans le message :
  `_write_serial` (L20141) / `_read_serial` (L20080) pour la liaison série.
* `_end_game` cas 5 (`LAB_4883E`) : non relu.
* `peep+0x0C == 0x2A (42)` : utilisé comme marqueur « grande ville » par `_set_town`
  (ligne 5946) et filtré dans `_end_game` (ligne 14128). Le lien exact entre ce champ
  et le sprite affiché (`_set_frame`, ligne 5724) n'a pas été tracé **[?]**.
* Bits 3 (`0x08`, bataille) et 7 (`0x80`, compte à rebours) de `peep+0x00` : issus
  d'un relevé antérieur, non re‑vérifiés ici **[?]**.
* `_place_building` / `_add_settlement` : **symboles inexistants** dans
  `populous_prg.asm` (§3.3).
* Anomalie de nommage : le commentaire de `_conquest` dit « levels**.**dat »
  (ligne 24316) alors que le code ouvre « `level.dat` » (lignes 11012, 12797).
* Tableau anonyme en `$5A376` entre `_map_steps` et `_map_who` : jamais référencé par
  un symbole nommé **[?]**.

## 9.4 Ce qui n'a pas été relu intégralement

`_where_do_i_go` (à partir de la ligne 4738), `_move_magnet_peeps` (4905),
`_get_heading` (5469), `_do_funny` (à partir de 8700), `_interogate` (2719),
`_zoom_map` (1658), `_paint_the_map` (15123), les branches `LAB_4BE12`,
`LAB_4C0B8`‑`LAB_4C12A` n'ont été lues que partiellement, et `populous_main.asm`
n'a pas été consulté.

---

# 10. Corrections apportées par relecture directe (implémentation Python)

Ces points, d'abord lus dans ce document, ont été tranchés en recoupant le
désassemblage ligne à ligne lors de l'implémentation de ``populous/sim.py``.
**Ils priment sur §2‑§3 ci-dessus.**

1. **``_peeps+0x0A`` n'est pas la case précédente mais le déplacement.**
   ``_move_explorer`` fait ``block += delta`` puis ``prev_block = delta``
   (asm 4168E‑41696). ``_zero_population`` efface donc
   ``map_who[p.block - p.prev_block]`` = l'ancienne case (asm 42258‑4227E).
2. **``_do_battle``** : les **deux** combattants encaissent, tous deux calculés
   sur ``min(roll_atk, roll_opp)`` — non sur le maximum et non pour le seul
   perdant (asm 42704‑42758) :
   ```python
   low = min(roll_atk, roll_opp)
   opp.life -= atk.weapons * (low // 100) + 10
   atk.life -= opp.weapons * (low // 100) + 10
   ```
   Le premier tirage est ``roll_opp`` (opp en argument indirect), le second
   ``roll_atk`` (asm 6084‑6101).
3. **``_zero_population(p, i)`` complète** (asm 5645‑5720) :
   ``life = 0`` ; si ``state == 0x08`` l'adversaire ``peeps[p.w6]`` perd le bit 3 ;
   si ``state & 1`` → ``set_town(p, 1)`` ; ``map_who`` effacé sur la case
   courante **et** sur ``block - prev_block`` ; ``magnet[tribe]`` et
   ``view_who`` remis à 0 s'ils pointaient sur ``i``.
4. **``+0x06`` est surchargé** : ``_set_battle`` y écrit l'index de l'adversaire
   (asm 42D04/42D0E), ``_move_explorer`` y écrit ``_game_turn`` au moment où
   l'explorateur s'installe (asm 4162C), et ``_move_peeps`` s'en sert de compteur
   (``> 14`` ⇒ ``state &= $9F``, asm 4251‑4253). Un seul champ, trois usages.
5. **L'usure ``2 * walk_death``** n'est appliquée **qu'aux peeps noyés**
   (``state & $10``), asm 40964‑4096E — pas à tous les peeps (§2.3 l'avait mal
   placée). Les villageois posés sur un bloc non nul ne perdent rien ; les
   explorateurs perdent ``walk_death`` par pas (asm 410DA) et les peeps « occupés »
   aussi (asm 4121E).
6. **``_set_frame``** (asm 422D2‑42438) est entièrement décodée : explorateur
   exactement ``$02`` ⇒ compteur 0‑7 (**un pas tous les 8 tours**,
   retour 1 quand l'ancienne valeur ≥ 7) ; noyade ``0x5D..0x60`` ; bataille
   plage ``D4..D4+2`` avec ``D4 ∈ {0x46,0x82,0x86,0x8A}`` selon les cibles ;
   villageois exactement ``$01`` ⇒ ``frame`` recalculé depuis ``_check_life`` ;
   animation ``0x55..0x57`` ; occupé (bits 5‑6) ``0x65..0x66``.
7. **``_where_do_i_go``** (asm 416A0) : pour s'installer, le peep doit être sur
   une case ``_map_blk == $0F`` **à plat** (asm 41740) et ``_check_life != 0``
   (asm 41766‑41770) ; la direction est tirée avec ``newrand() & 7 + 1`` quand
   ``D5 == 0`` (asm 416DE‑416E8). Un explorateur ne s'installe donc jamais sur
   le bâtiment de ses parents.
8. **``_map_steps``** est indexé en **mots** (``ASL.L #1`` puis
   ``ADDQ.W #1,(0,A0,D0.L)``, asm 4165A) : 8196 octets réels, pas 4096.
9. **``_set_town(grow=1)``** efface ``_map_bk2`` sur les 9 premières cases pour
   une ville normale (``k < 9``) et sur les 25 pour une grande ville, puis
   remet ``_map_bk2[b] = 0`` seulement dans le cas « ville normale ».
10. **Mini-carte** : la couleur ``_a_putpixel`` est ``15`` pour la tribu 0 et
    ``8`` pour la tribu 1 dans la branche explorateur (asm 411A6‑411B2).

---

*Fin du document. Toute affirmation non suivie d'une ligne de référence doit être
considérée comme issue d'un relevé antérieur et traitée comme **[?]**.*
