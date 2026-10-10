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
| `reference/tetracorp/populous_main.asm` / `.cnf` | désassemblage secondaire (non consulté) |
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

Population de départ : `_place_first_people` (ligne 7652) prend `conq_06_yourpop` en
mode conquête/tutoriel (ligne 7660), sinon 1 (mode série, ligne 7666) ou
`2*(LAB_516B0 > 4) + 1` (lignes 7669‑7678). Le joueur 0 gagne `10 * population_initiale`
points (lignes 7680‑7686).

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
def setup_display(a5_1):                             # L380  $3E5CE
    if in_conquest != -1:                            # L382  mode conquête
        seed = start_seed = (_in_conquest & 7) + conq_08_seed   # L388‑392
        ground_in = conq_05_terrain                  # L395‑399   0..3
        load_ground(ground_in, 0) ; clear_map()      # L400‑404
        LAB_516DE = _conquest[0]                     # L407‑408   _stats[1]+0x0C
        LAB_516E2 = conq_01_speed                    # L410‑411   _stats[1]+0x10  PÉRIODE IA
        LAB_516E0 = (conq_02_enemypow << 3) | 7      # L415‑418   pouvoirs ennemis
        LAB_516B2 = (conq_03_yourpow  << 3) | 7      # L420‑423   pouvoirs joueur
        _game_mode = conq_04_mode                    # L426‑427   bits : gens/villes/haut/marais/eau
    else:                                            # L429  partie libre
        start_seed = seed                            # L430
        if seed != 0 and (newrand() & 1) and a5_1 == -1:   # L431‑437
            ground_in = (ground_in + 1) % 4          # L438‑441  terrain aléatoire
            load_ground(ground_in, 0)                # L443‑445
```

* `conq_01_speed` → `_stats[1]+0x10` = **période, en tours, entre deux décisions de
  l'IA**. C'est le vrai « niveau de difficulté ».
* `<<3 | 7` : les 3 bits de poids faible sont toujours à 1 (actions de base toujours
  autorisées), les 8 bits suivants sont les pouvoirs.
* `_game_mode` bits testés en 12488‑12546 : `bit0…bit4` =
  construire sur gens / villes / uniquement en haut / marais / eau **[?] ordre exact**.

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

## 6.2 `_end_game` — ligne 14019 ($48698)

Table de 7 entrées (lignes 14284‑14290, dispatch borné à 7 en 14291‑14297) :

| cas | étiquette | ligne | contenu affiché |
|---|---|---|---|
| 0 | `LAB_486AA` | 14027‑14037 | **`strLost`/`strWon`** copié dans `strLOST` (tableau de 46 B, indexé `MULU #$2E`) |
| 1 | `LAB_489CA` | 14281 | no‑op |
| 2 | `LAB_486EC` | 14049‑14066 | `_battle_won[player]` et `_battle_won[not_player]` convertis en chaînes |
| 3 | `LAB_48724` | 14067‑14108 | compte les peeps avec `target != 0` **et** `life != 0`, séparés par tribu |
| 4 | `LAB_487A6` | 14109+ | compte les peeps avec `state == 1` (villageois), `life != 0`, `frame != 0x2A` |
| 5 | `LAB_4883E` | — | **[?] non relu** |
| 6 | `LAB_488DC` | 14230‑14252 | bonus de pouvoirs : `+0x3E8 (1000)` par bit de `LAB_516B2[not_player]` (lignes 14234‑14237) ; `+15 × (10 − stats[not_player].p10)` (lignes 14244‑14252) |

**Calcul du score** (lignes 14254‑14278) :

```python
    if arg1 == 0:                     # victoire
        score *= 10                   # L14256‑14260  « x10 points for winning »
    if score < 500:     score = 500          # L14263‑14265  minimum
    if score > 555_555: score = 515_090      # L14268‑14270  plafond
    long_asc(score, &strScoreboard[idx*46])  # L14272‑14278
```

Chaînes visibles : **`LOST`**, **`WON`**, **`TRY IT AGAIN`**, **`NEW GAME`**
(relevé antérieur ; non re‑vérifié dans cette session **[?]**).
Cases 2‑5 : les chaînes sont complétées par des espaces (lignes 14299‑14314).

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
Charge `lord.pic` (0x7D00 octets = 32 000 B) dans `_w_screen`, + 32 octets dans `_tcmap`
(palette). Retourne 0 si l'ouverture échoue (test en 14512).

### `_read_mouth` — ligne 16668
Charge `mouths.pic` (0x13B0 = 5 040 B) dans **`_map_steps`** (le tampon est réutilisé,
`$00059376`).

### `_draw_mouth` — ligne 19894

```python
def draw_mouth(index):                               # L19894
    # 1 « bouche » = 6 octets × 4 lignes = 24 B ; pas de ligne = 840 B (MULU #$348)
    src = _map_steps + index * 840
    # 35 lignes de haut                                   # [?] découpage exact non relu
```

`0x13B0 = 5040 = 6 × 840` → **6 bouches** au total.

## 6.5 `_show_world` et le choix du monde

Appelé depuis `_animate` en début de partie (lignes 542‑553) :

```python
    while True:                                      # L542‑547
        in_conquest = show_world()
        if in_conquest != -1: break
    return_to_game() ; setup_display(-1, 0)           # L549‑553
```

`show_world` est l'écran de sélection de monde, qui affiche les 16 lignes issues de
`level.dat` (dispatch en 12384 → `line_1 … line_16`, lignes 12388‑12797) :
numéro de monde, terrain (`_con_text[conq_05_terrain]`), vitesse, pouvoirs,
populations, mode de jeu…

---

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
        return_to_game() ; setup_display(-1, 0)      # L549‑553
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
* `_do_action` sous‑commandes 7 (ligne 18607) et 8 (`LAB_4BE12`, ligne 18729) : non
  décodées.
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
