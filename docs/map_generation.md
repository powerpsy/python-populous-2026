# Génération et rendu de la carte — Populous (Amiga)

*Transcription directe du listing `reference/tetracorp/populous_prg.asm` (adresses
hexa = offset dans le programme original).  Les numéros de ligne (`L####`) renvoient
à ce listing.  Les valeurs ont été vérifiées en exécutant la logique transcrite
(`tools/probe_terrain.py`).*

---

## 1. Données

| Symbole | Adresse | Taille | Contenu |
|---|---|---|---|
| `_alt` | `0x54274` | 4225 mots = 8450 o | grille d'altitude **65 × 65** (indices 0..64) |
| `_map_blk` | `0x56376` | 4096 o | type de pente / matière par case |
| `_map_alt` | `0x57376` | 4096 o | altitude d'affichage par case (octet) |
| `_map_bk2` | `0x58376` | 4096 o | couche « décor » (arbres) par case |
| `_map_who` | `0x5B376` | 4096 o | index+1 de l'habitant sur la case |
| `_map_steps` | `0x5B376+0x1000` | 8192 o | mots, indexés par **mot** (`idx*2`) |
| `_build_count` | `0x5C376` | mot | compteur d'altérations du relief |
| `_xmin/_xmax/_ymin/_ymax` | `0x5C378..7E` | 4 mots | boîte englobante du relief construit |
| `_seed` / `_start_seed` | `0x52DD0/D2` | 2 mots | graine du générateur |
| `_ground_in` | `0x52DD4` | mot | type de sol 0..3 (herbe/désert/neige/volcan) |
| `_screen_origin` | `0x51630` | long | décalage (en **octets**) de l'origine isométrique = `2582` = `0xA16` |
| `_xoff` / `_yoff` | `0x52DDE / 0x52DE0` | 2 mots | coin haut-gauche de la fenêtre 8 × 8 (0..56) |
| `_map_colour` | `0x5175E` | 31 o + 1 | couleur du mini-carte par `map_blk` |
| `_blk_data` | pointeur `0x52C5E` | 70 × 480 o | tuiles isométriques (fichier `LANDn`) |
| `_sprite_data` | pointeur `0x52C56` | n × 160 o | sprites 16 × 16 masqués |

Toutes les tables `map_*` font 64 × 64 = 4096 cases, **indexées `y*64 + x`**.
`_alt` est en revanche **65 × 65** (stride `0x41`) : ce sont les sommets du
terrain, les 4 sommets d'une case définissant son losange.

---

## 2. Chaîne d'initialisation — `_setup_display(a, b)` (L380)

```
_setup_display(a, b):
    if in_conquest != -1:                       # partie Conquête
        _seed = _start_seed = (in_conquest & 7) + conq_08_seed
        _ground_in = conq_05_terrain            # octet 0..3
        load_ground(_ground_in, 0)
        clear_map()
        stats[1].+0x0C = conq_byte0             # 0..10
        stats[1].+0x10 = conq_01_speed
        stats[1].+0x0E = (conq_02_enemypow << 3) | 7   # pouvoirs ennemi
        stats[0].+0x0E = (conq_03_yourpow << 3) | 7    # pouvoirs joueur
        _game_mode = conq_04_mode
    else:                                        # partie libre
        _start_seed = _seed
        if _seed != 0 and (newrand() & 1) and b == -1:
            _ground_in = (_ground_in + 1) mod 4
            load_ground(_ground_in, 0)
        if b != -1 and b != _ground_in:
            load_ground(_ground_in, 0)
        clear_map()

    if a == 0:                       # « (re)générer le relief »
        make_alt()                   #   relief brut
        make_map(0, 0, 0x3F, 0x3F)   #   -> map_blk / map_alt
        make_woods_rocks()           #   -> rochers + arbres

    ... recopie de l'écran, dessin ...
    draw_map(0, 0, 0x3F, 0x3F)       # mini-carte (Book of Worlds)
    place_first_people()
    _seed += 1                       # la graine avance d'un cran par partie
```

> `_seed` n'est **pas** incrémenté entre les tirages : `_newrand` le fait
> (`seed = ((seed * 0x24A1) & 0xFFFF0000 | ...) & 0xFFFF7FFF`).
> `clear_map()` consomme **4 tirages** (2 par joueur) avant `make_alt()`.

---

## 3. `_clear_map` (L1023)

* si `start_of_game == 0` : `set_mode_icons(6,1)`, `set_tend_icons(4,3)`
* `peeps[i].mot0 = 0` pour `i < 0xD3` (211 slots), `no_peeps = 0`
* `pointer = (player == 1 ? 3 : 0) + 1` ; `funny_done = 0` ; `score = 0`
* pour `i ∈ {0,1}` :
  * `magnet_record[i].+0 = 0` (`_magnet`), `.+2 = 0x0820`, `.+4 = 1`
  * `battle_won[i] = 0`
  * `stats[i].+0x12 = 0`, `stats[i].+0x1C = 0`
  * `stats[i].+0x1A = newrand() % 3`
  * `stats[i].+0x18 = stats[i].+0x1A + (newrand() % 5) + 1`
  * `_devil_magnet = _god_magnet = 0x0820`
* `clear_send()` ; `game_turn = 0`, `mode = 2`, `surender = -1`, `war = 0`,
  `left/right_button = 2`, `inkey = 0`
* **`_alt[i] = 0` pour les 4225 mots** (`CMP #$1081`)
* `map_blk = map_alt = map_bk2 = map_who = 0` et `map_steps = 0` (4096 cases)

→ **Tout le terrain démarre à altitude 0 (mer plate)** ; le relief est
entièrement bâti par `_make_alt`.

---

## 4. `_make_alt` / `_make_thing` / `_raise_point` (L1189 / L1208 / L1274)

### 4.1 `_make_alt` (L1189)

```python
make_thing(2, 4)     # pas max : x ± 2, y ± 4
make_thing(4, 2)     # x ± 4, y ± 2
make_thing(3, 3)     # x ± 3, y ± 3
```
(l'ordre des arguments vient du sens d'empilement : premier argument = sommet de pile)

### 4.2 `_make_thing(a, b)` (L1208) — la « marche » qui construit une colline

```python
x = newrand() % 64          # DIVS #$40 ; SWAP  -> reste 0..63
y = newrand() % 64
while True:
    if raise_point(x, y) == 6:      # stop dès qu'une case atteint 6
        break
    x += (newrand() % (2*a + 1)) - a
    y += (newrand() % (2*b + 1)) - b
    x = clamp(x, 0, 64)             # bornes INCLUSES (0..64)
    y = clamp(y, 0, 64)
```

`_newrand` force bit 15 à zéro, donc le reste du `DIVS` est **toujours positif**
(0..63) : pas de cas particulier négatif.

### 4.3 `_raise_point(x, y)` (L1274) — incrément + lissage

```python
def raise_point(x, y):                       # renvoie la NOUVELLE altitude
    if not (0 <= x <= 0x40 and 0 <= y <= 0x40):
        return 0                             # hors carte
    i = y * 65 + x                           # MULS #$41 + ASL #1
    if alt[i] >= 8:                          # déjà au maximum
        return alt[i]                        # -> LAB_3F0AC
    build_count += 1
    alt[i] += 1

    # A3 = pointeur de cellule, D4/D5 = coordonnées ; ils restent synchro'ses
    A3 = &alt[i + 1]; D4 = x + 1; D5 = y
    # les 8 voisins, dans l'ordre : E, SE, S, SW, W, NW, N, NE
    for (delta, d4, d5) in ((+1,  x+1, y   ),      # A3 = i+1
                            (+65, x+1, y+1 ),      # A3 = i+66
                            (-1,  x,   y+1 ),      # A3 = i+65
                            (-1,  x-1, y+1 ),      # A3 = i+64
                            (-65, x-1, y   ),      # A3 = i-1
                            (-65, x-1, y-1 ),      # A3 = i-66
                            (+1,  x,   y-1 ),      # A3 = i-65
                            (+1,  x+1, y-1 )):     # A3 = i-64
        A3 += delta; D4 = d4; D5 = d5
        if alt[i] - alt[A3] > 1:            # pente trop raide -> lisser
            raise_point(D4, D5)

    xmin/xmax/ymin/ymax ← bornes de (x, y)   # sur les paramètres D'ENTRÉE
    return alt[i]                            # (A2), pas la valeur lissée
```

* **Garantie obtenue** : après `_make_alt`, deux cases voisines (hors bords)
  diffèrent d'**au plus 1** en altitude. C'est ce qui rend le reste cohérent
  (voir §7 et §9).
* `A3 = i+64` pour `x = 0` pointe en réalité sur `(64, y)` (débordement de
  rangée, exact comme sur le 68000) ; `i-66` peut être négatif (octets situés
  *avant* `_alt`) — `tools/probe_terrain.py` lit alors 0 (la mémoire voisine
  `map_blk` est encore nulle à ce stade).
* `_lower_point` (L2571) est le miroir exact : garde `alt[i] == 0`, `alt[i] -= 1`,
  et test `alt[A3] - alt[i] > 1`.

### 4.4 Résultat observé (`tools/probe_terrain.py 1`, graine 1)

```
alt>0 : 2243/4225 sommets   max=6   build_count=4387
histogramme : 0:2114  1:982  2:649  3:388  4:180  5:41  6:3
cases eau (map_blk=0) : 1450 / 4096   cases plates (map_blk=15) : 181
```
≈ 65 % de terre, relief lisse en escalier de 0 à 6 — conforme au jeu.

---

## 5. `_make_map(x0, y0, x1, y1)` (L1420) — sommet → case

Pour chaque case `(x, y)` de la zone :

```python
i      = y * 65 + x                       # sommet haut-gauche
avg    = (alt[i+1] + alt[i+65] + alt[i+66] + alt[i]) >> 2   # moyenne des 4 sommets
mask   = 0
if alt[i]     > avg: mask |= 1            # haut-gauche
if alt[i+1]   > avg: mask |= 2            # haut-droit
if alt[i+66]  > avg: mask |= 4            # bas-droit
if alt[i+65]  > avg: mask |= 8            # bas-gauche

if map_blk[idx] == 0x2F and (mask != 0 or avg != 0):
    mask = 0x2F                           # case « protégée » conservée telle quelle
else:
    map_blk[idx] = mask

if avg != 0 and mask == 0:                # les 4 sommets sont égaux et > 0
    avg -= 1                              #   -> plaine plane
    mask = 0x0F
if avg == 0 and mask != 0x0F and mask != 0:
    mask += 0x10                          # pente quasi-nulle -> variante « eau »

map_alt[idx] = avg
if map_blk[idx] != 0x2F:
    map_blk[idx] = mask
if mask == 0:
    map_bk2[idx] = 0                      # pas d'arbre sur l'eau
map_steps[idx] = 0                        # mot !
```

### Codes `map_blk`

| Valeur | Signification |
|---|---|
| **0** | eau plate (les 4 sommets sont nuls) |
| **1..14** | masque de pente (bit0 = N-O, bit1 = N-E, bit2 = S-E, bit3 = S-O : sommets **au-dessus** de la moyenne) |
| **15** | **plaine parfaitement plate** (case constructible, `_where_do_i_go` exige `$0F`) |
| **16..30** | variante « rive » : pente dont l'arrondi de la moyenne tombe à 0 |
| **47** (`0x2F`) | case protégée (rocher/obstacle posé à la main ou en fichier) — ignorée par la régénération |
| **47..49** | rochers (écrits par `_make_woods_rocks`) |
| **50..52** | non pas dans `map_blk` mais dans **`map_bk2`** : arbres |

`map_alt` est l'arrondi inférieur de la moyenne, **–1 quand la case est plate**.
Les cases « rive » (16..30) ont donc `map_alt == 0` tout en étant de la terre.

`_mod_map` (L1594) refait exactement la même conversion pour une zone
(utile après `raise_point`/`lower_point` du joueur) mais ne touche ni `map_bk2`
ni `map_steps`… si, il remet `map_steps = 0`.

---

## 6. `_make_woods_rocks()` (L8535)

```python
for k in range(0x16):                 # 22 amas
    thresh = 0x32 - (3 if k < 7 else 0)      # 47 pour k<7, sinon 50
    x0 = newrand() % 0x3B                    # 0..58
    y0 = newrand() % 0x3B
    for _ in range(0x1E):                    # 30 essais
        x = x0 + newrand() % 9
        y = y0 + newrand() % 9
        if not (0 <= x < 64 and 0 <= y < 64): continue
        if map_blk[y*64+x] == 0:   continue   # jamais sur l'eau
        if map_blk[y*64+x] == 0x2F: continue   # jamais sur un rocher
        v = thresh + newrand() % 3            # 47,48,49 ou 50,51,52
        if thresh == 0x2F:
            map_blk[y*64+x] = v               # k < 7  -> ROCHERS (avant-plan)
        else:
            map_bk2[y*64+x] = v               # k >= 7 -> ARBRES  (couche décor)
```

7 amas de rochers (tuiles 47-49) + 15 amas d'arbres (tuiles 50-52 dans `map_bk2`).

---

## 7. Fichier `LANDn` — en-tête de 114 octets **décodé** (`_load_ground`, L16468)

Le programme ouvre `LAND0`..`LAND3` (`strLAND` + `'0'+n`, mode `0x3ED`) et lit,
dans l'ordre du fichier :

| Offset | Taille | Destination | Contenu |
|---|---|---|---|
| 0 | 2 | `_walk_death` | mot |
| 2 | 22 | `_population_add` | 22 octets (un par population) |
| 24 | 22 | `_mana_add` | bonus de manna |
| 46 | 22 | `_weapons_add` | bonus d'armes |
| 68 | 22 | `_battle_add1` | bonus de bataille |
| 90 | 6 | `_battle_add2` | bonus de bataille (suite) |
| 96 | 16 | **`_map_colour`** | 16 couleurs du mini-carte (blocs 0..15) |
| 112 | 2 | variable locale | mot lu puis ignoré ici |
| 114 | 33600 | `_blk_data` | **70 tuiles × 480 octets** |

`2+22+22+22+22+6+16+2 = 114` — exactement l'en-tête relevé dans les fichiers
extraits, et `70 × 480 = 33600` pour le corps. ✅ Format confirmé.

### `_map_colour` (défaut ROM, `0x5175E`)

```
blocs 0..15 : 0e 0c 0b 0b 0c 0c 0b 0b 0d 0d 0c 0c 0d 0d 0c 0c
blocs 16..30 : 0e 0c 0b 0b 0c 0c 0b 0b 0d 0d 0c 0c 0d 0d 0c    (copie alignée)
blocs 31..   : 19 19 19 ...   -> la valeur 0x19 est remplacée par LAB_5177D = 0x0C
```
Seules les **16 premières** octets sont réécrites par `LANDn` ; les blocs 16..30
gardent donc la couleur par défaut (quirk : les rives gardent la couleur de
l'herbe même sur les autres sols). Palette indices : 14 = bleu (eau), 11/12/13 =
verts (herbe).

---

## 8. Mini-carte (Book of Worlds) — `_draw_map(x0,y0,x1,y1)` (L1543)

```python
colour = _map_colour[map_blk[idx]]
if colour == 0x19:
    colour = _map_colour[0x1F]        # = 0x0C
pixel(back_scr,
      x = (X - Y) + 64,               # X,Y = coordonnées de case
      y = (X + Y) >> 1,
      colour)
```
Projection losange : la mini-carte occupe `x ∈ [1,127]`, `y ∈ [0,63]`.

Clic inverse (`_zoom_map`, L1660) :

```python
u = mousex//2 + mousey - 32      # -> case X
v = mousey - mousex//2 + 32      # -> case Y
if 0 <= u < 64 and 0 <= v < 64:
    xoff = clamp(u - 3, 0, 0x38)         # recentre la vue
    yoff = clamp(v - 3, 0, 0x38)
```
Vérification : `u - v + 64 = mousex`, `(u + v)//2 = mousey` ✓.
Hors du losange (ou `> 0x112` en X) la souris tombe sur la barre d'icônes :
`col = (mousex - 0x110) // 16`, `row = (mousey - 0x20) // 16` → grille **3 × 10**
= 30 icônes, ce qui correspond aux 30 icônes extraites.

---

## 9. Rendu isométrique

### 9.1 Projection

Pour une case de la fenêtre `(d0, d1)` d'altitude `a` (avec `d0 = X - xoff`,
`d1 = Y - yoff`) :

```
pixel_x = origin_x + 16 * (d0 - d1)
pixel_y = origin_y +  8 * (d0 + d1) -  8 * a
octet   = _screen_origin + 322*d0 + 318*d1 - 320*a
```
(`322 = 40*8 + 2` → 8 lignes d'écran + 16 px ; `318 = 40*8 - 2`.)
`_screen_origin = 2582 = 40*64 + 22` : le coin (0,0) de la fenêtre est donc
**fixe** à l'écran — `_xoff/_yoff` ne choisissent que *quelle* portion de la
carte occupe ce losange fixe (bornée à 0..56, soit `64-8`).

### 9.2 Tuiles et sprites — formats binaires

* **Tuile** (`_blk_data[idx * 480]`) : 24 lignes × (masque `long` + 4 plans ×
  `long`) = 24 × 20 = **480 octets**. Largeur utile 32 px, hauteur 24.
* **Sprite** (`_sprite_data[idx * 160]`) : 16 lignes × (masque `mot` + 4 plans ×
  `mot`) = 16 × 10 = **160 octets**, 16 × 16 px.
* Plans aux décalages `0, 0x1F40, 0x3E80, 0x5DC0` (= 0, 8000, 16000, 24000) dans
  l'écran, stride 40 octets/ligne.

### 9.3 `_drw_blk` / `SUB_49938` (L15737) — blitter d'une tuile

```python
def drw_blk(x, y, z, tile):        # z = altitude*8
    A0 = work_screen + screen_origin
    A0 += 322*x + 318*y - 40*z
    if A0 < 0: return              # (test SUBA.L D2,A0 / BGE)
    A6 = blk_data + tile * 480
    for row in range(24):
        mask = long(A6)                      # D4
        for p in (0, 0x1F40, 0x3E80, 0x5DC0):
            scr[p] = (scr[p] & mask) | long(A6)   # OR donnees de ce plan
        A0 += 40
```
Donc `A0 -= 40*z` → `z = alt*8` décale de `8*alt` lignes vers le haut.

**Sémantique exacte** : `ecran = (ecran AND masque) OR donnees`, avec un **seul**
masque par ligne, commun aux 4 plans :

| bit masque | donnees | résultat |
|---|---|---|
| `0` | `0`  | **0 (noir)** — pixel réécrit |
| `0` | `≠0` | la couleur des données — pixel réécrit |
| `1` | `0`  | `ecran` — **transparent** (cas présent partout) |
| `1` | `≠0` | `ecran OR donnees` — *jamais présent dans les fichiers livrés* |

Conséquence mesurée sur `land0` : **2444 pixels** (sur 53 760) ont `masque=0` et
données nulles → ils sont peints en **indice 0 (noir)** ; idem **3553** sur les
147 sprites de `sprites0.dat`.

**Choix retenu dans le remake.** Comparer les deux lectures sur l'écran complet
(`tools/compare_blit.py`) ne change que **128 px sur 64 000** : `qaz.pic` est
noir à 97 % sous le losange, donc « peint en noir » et « transparent » donnent
le même résultat à l'écran. On a donc gardé la lecture **la moins coûteuse** :

```python
opaque = (donnees != 0)      # le masque n'est meme plus lu
```

Ce qui permet en prime de retirer le masque du pipeline de décodage. Voir
`populous/assets.py::OPAQUE_FROM_MASK` (remettre `True` pour retrouver le
comportement exact de la ROM) et `tools/check_assets.py`, qui vérifie le
décodeur pixel à pixel contre la transcription naive sur tous les fichiers.

### 9.4 `_draw_it(xoff, yoff)` (L15794) — la vue complète

Trois passes, dans cet ordre :

**Passe 1 — les 64 losanges de haut** (`d1` = ligne 0..7, `d0` = colonne 0..7) :

```python
blk = map_blk[Y*64 + X]
if blk == 0 and _toggle == 0:
    blk = 0x10                      # _toggle alterne à chaque image :
                                    # animation d'eau 2 états (tuiles 0 / 16)
drw_blk(d0, d1, alt*8, blk)         # losange de terrain
if map_bk2[...]:
    drw_blk(d0, d1, alt*8 + 8, bk2) # decor (arbre) tracé 8 px plus haut
if map_who[...]:
    move_sprite(...)                # habitant (si screen_origin == 0xA16)
if idx == _devil_magnet: drw_blk(..., 0x2E)   # marqueur « mal »  (tuile 46)
if idx == _god_magnet:   drw_blk(..., 0x2D)   # marqueur « bien » (tuile 45)
```

**Passe 2 — face avant *droite* de la dernière colonne** (`X = xoff+7`,
`Y = yoff..yoff+7`) : `map_alt[Y*64+X]` copies du sprite **77**
(`_sprite_data + 0x3020`), chacune remontée de 8 lignes, ancrées à
`ancrage + 8 lignes + 16 px` (moitié droite de la tuile).

**Passe 3 — face avant *gauche* de la dernière ligne** (`Y = yoff+7`,
`X = xoff+7 → xoff`) : `map_alt[...]` copies du sprite **76**
(`_sprite_data + 0x2F80`), ancrées à `ancrage + 8 lignes` (moitié gauche).

*Les passes 2 et 3 ne traitent que les bords de la fenêtre, et c'est quasi
exact :* l'asymétrie de `_raise_point` garantit que deux cases voisines
diffèrent d'au plus 1, et pour les cases *intérieures* la chaîne de losanges des
cases vers l'avant (alternance 16 px de descente / 8 px par niveau d'altitude)
recouvre **presque** toute la face `[R−8a+16, R+23]`. Dessiner ces faces serait
donc redondant et mal occlus ; seules les faces dont le voisin avant est *hors
fenêtre* doivent être tracées — celles de la dernière colonne et de la dernière
ligne. La case d'angle reçoit les deux.

**Mesuré** (`tools/check_render.py`, 168 fenêtres : 7 graines × 4 sols × 6
positions) : le rendu 3 passes et un rendu « falaises partout » diffèrent en
moyenne de **7,7 pixels** par fenêtre (1287 px au total sur 10,7 M px, soit
0,012 % ; maximum 202 sur une fenêtre, 0,3 %). Ces quelques pixels sont ceux où
une falaise *intérieure* serait visible et que l'original laisse donc
**transparaître** — ce n'est pas une erreur de transcription : les ancres des
passes 2 et 3 ont été recalées octet à octet sur l'asm
(`5158 + 318·d₁` et `7382 − 322·k`). Avec le décodeur « masque exact » (§9.3)
ce résidu tombe à **0,9 px/fenêtre** (150 px au total, max 21) parce que les
trous sont alors peints en noir au lieu de laisser voir le fond.

Ordre de dessin : passe 1 (tous les hauts) → passes 2/3 (les faces visibles) ;
la fenêtre suivante est dessinée après, ce qui recouvre correctement ces faces.

### 9.5 `_move_sprite` (L15951)

```
D4 = 16*d0 - 16*d1           # X pixel
D5 =  8*d0 +  8*d1 - alt*8   # Y pixel
```
puis, selon `peeps[i].state` (octet 0) : `+0xC0/+0x40` pour un villageois en
marche, `+0xB8/+0x40` et frame `(game_turn & 3) + 0x69` pour l'état 7 (animé),
etc. La table `_ok_to_build |= (peep[0] & 0xF8 | 1 si allié et +0x12 != 0)` est
calculée ici pour le curseur de construction.

---

## 10. Défilement et fenêtre

* `_xoff`, `_yoff` ∈ `[0, 0x38]` = `[0, 56]` (= 64 − 8), toujours par pas de 1.
* Clic sur la mini-carte → recalcul ci-dessus (§8).
* Curseur sur la zone principale → défilement (L1865-L1925, L2158-L2440), borné
  de la même façon.
* `_screen_origin` est constant (`2582`) ; il n'est décalé que de ±40 / ±120
  octets autour d'un `_draw_it` supplémentaire (L7899-L7924), puis restauré.

---

## 11. Éditeur de carte — `_paint_the_map` (L15123)

Traite `_inkey` quand `_paint_map != 0` et remplit un paquet 3 octets
`(commande, param1, param2)` :

| Touche | Octets | Effet |
|---|---|---|
| F1 | `07` | poser un homme |
| Maj+F1 | `09` | poser un leader |
| F2 | `08` | poser un ennemi |
| Maj+F2 | `0A` | poser un leader ennemi |
| F3 | `0B` | poser un arbre |
| F4 | `0C` | poser un rocher |
| F5 | `0D` | supprimer un objet |
| F6 | `0E, p1=LAB_5C4EF, p2=09` | commande éditeur 9 |
| F7 | `0E, p1=…, p2=0A` | commande éditeur 10 |
| F8 | `0E, p2=0B` | miroir du paysage |
| Del | `0E, p2=0C` | tout effacer |
| `1..9` | `0E, p1=(0x10-(touche-0xED))>>1, p2=0D` | type de sol 1..9 (herbe, désert, neige, volcan, 5 persos.) |

`_make_level(pos, joueur)` (L9017) cherche dans un carré 9 × 9 (`_a_flat`, 81
paires d'offsets) une case convenant au départ du joueur, en ignorant les
positions déjà pourvues (`stats[j].+8 != 0`) ; il repousse de 1 le bloc `0x2F`
et remplit `stats[j] = {type, x, y, +8=1}`.

---

## 12. Points restants à vérifier

1. **Rendu réel** : transcrire `_draw_it` en Python et comparer pixel à pixel
   avec une capture d'écran du jeu original (les tuiles 480 o et sprites 160 o
   sont déjà extraits).
2. Identité exacte des sprites 76/77 (faces gauche/droite) — à confirmer visuellement.
3. `_map_colour[16..30]` : dépend de la mémoire ROM par défaut, pas du fichier `LANDn`.
4. Position et dimensions exactes du panneau de la mini-carte, de la barre
   d'icônes et de la barre de manna (le losange de jeu occupe
   `x ∈ [48,320]`, `y ∈ [64,200]` avec `_screen_origin = 2582`).
5. `_make_level` / `_one_block_flat` (L9148) : à finir (logique de placement
   initial et d'aplanissement).
6. `_make_copper` (L19699), `_rotate_all_map` (L6823), `_clear_all_map` (L6926).
