# Disposition de l'écran de jeu — transcription de l'asm

Toutes les adresses renvoient à `reference/tetracorp/populous_prg.asm` (L = numéro
de ligne du listing). Les éléments marqués **[à confirmer]** n'ont pas encore été
recoupés ligne à ligne.

---

## 1. Les deux écrans : `_w_screen` et `_back_scr`

| symbole | rôle |
|---|---|
| `_w_screen` | écran de travail, celui qui est **redessiné à chaque image** |
| `_back_scr` | arrière-plan, rempli par **qaz.pic** — mais aussi *modifié* en place |

* `_read_back_scr` (**L16359**) ouvre `strQaz` = `"qaz.pic"` et lit `0x7D00`
  = **32000 octets** (4 plans × 8000) dans `_back_scr`.
* `_clr_wsc` (**L16282**) fait `memcpy(_w_screen, _back_scr, 8000)`
  (`MOVE.W #$1f3f,D0` + boucle de `MOVE.L (A1)+,(A0)+`) : **toute** l'image.
* `_copy_screen(src, dst)` (**L16297**) : même copie de 8000 octets, générique.

> **Conséquence fondamentale.** Le « chrome » de l'écran (cadre de la mini-carte,
> colonne d'icônes, pavé de défilement, flèches) n'est **pas** redessiné : il est
> peint **dans qaz.pic**. Chaque image ne fait que :
> 1. recopier le fond,
> 2. rejouer la fenêtre isométrique 8×8,
> 3. rafraîchir les barres / icônes / portraits,
> 4. **réécrire la mini-carte dans `_back_scr`** (donc elle aussi persistante),
> 5. basculer en XOR certains boutons **dans `_back_scr`** (`_toggle_icon`).

### Environnement graphique

* 320×200, 4 plans **plan-major** : stride 40 octets/ligne, 8000 octets/plan,
  plans aux décalages `0, 0x1F40, 0x3E80, 0x5DC0`.
* `_palette` = `0000 0444 0666 0888 0aaa 0ccc 0620 0840 0a00 0a60 0aa0 04a0 0280 0262 0248 026c`.
* `_screen_origin = 2582 (0xA16)` (constante `DC.L $00000a16`, L24123), temporairement
  décalée de `±0x28 / ±0x78` pendant l'effet de tremblement de terre.

---

## 2. Ordre d'une image (boucle principale, L604‑660)

1. `_clr_wsc` — fond → écran de travail
2. `_move_mana`
3. `_draw_it(xoff, yoff)` — les 3 passes de la fenêtre (L15794)
4. `_move_sprite` (via `_draw_it`) — les habitants
5. `_draw_map` — la mini-carte, **dans `_back_scr`** (L1543)
6. `_show_the_shield`, `_draw_bar`, `_draw_icon` — **dans `_w_screen`** (L2769…)

---

## 3. Primitives de dessin

### 3.1 `_pixel(screen, x, y, colour)` — L19140

```
clip : 0 <= x < 320 et 0 <= y < 200, sinon rien
bit  = 7 - (x & 7)                       # MSB = x le plus petit
A0   = screen + y*40 + x/8
pour p = 0..3 :  D4 >>= 1 ; carry = bit p de `colour`
                 carry ? BSET bit,(plan p) : BCLR bit,(plan p)
```
Écriture **totale** (passe à 0 ou à 1) : c'est un `putpixel` exact.
`_draw_map` s'en sert pour la mini-carte.

### 3.2 `_draw_icon(screen, x, y, icon)` — L19184

```
A0   = screen + (x << 1) + y*40        # x est en blocs de 16 px -> px = 16*x
A1   = _icon_data + icon*128           # 128 = 16 lignes x 4 mots
16 lignes x (4 mots -> plan 0..3), A0 += 40 entre les lignes
```
* Pas de masque : le bloc 16×16 est **entièrement réécrit**.
* `_icon_data` = 30 icônes × 128 o extraites par `tools/extract_icon_data.py`
  (base `0x3DDE4`, offset DAD `0x106E2`).
* **Seuls deux sites** appellent `_draw_icon` : `_show_the_shield` (2 appels,
  L2794 et L2821) et `_requester` (21 appels, L9922‑L10253). **La barre
  d'icônes de droite n'utilise donc pas `_draw_icon`** : elle est peinte dans
  qaz.pic et retouchée en XOR (§5.4).

### 3.3 `_draw_bar(screen, x, y, total, value, colour)` — L19213

Signature pile : `(screen, x, y, total, value, colour)`.

```
A0 = screen + x + y*40
value = clamp(value, 0, total)
D5 = total - value
lignes y-value+1 .. y      -> `couleur`    (remplissage par le BAS)
lignes y-total+1 .. y-value -> couleur 2   (0x0666, gris)
```
Largeur : **4 px**, les bits 2..5 de l'octet `x` → pixels `8x+2 … 8x+5`
(les autres plans/bits sont laissés intacts).

Barres relevées :

| usage | `x` | `y` | `total` | `value` | `couleur` | pixels x | lignes |
|---|---|---|---|---|---|---|---|
| population « bonne » | `0x20` (32) | 31 | 32 | `good_pop*31/50000 + 1` | `0x0F` | 258‑261 | 0‑31 |
| population « mauvaise » | `0x27` (39) | 31 | 32 | `bad_pop*31/50000 + 1` | 8 | 314‑317 | 0‑31 |
| écusson, équilibre d'un combat, A | `0x24` (36) | 37 | 16 | voir §5 | `0x0F` | 290‑293 | 22‑37 |
| écusson, équilibre d'un combat, B | `0x25` (37) | 37 | 16 | voir §5 | 8 | 298‑301 | 22‑37 |
| écusson, jauge de vie | `0x24` (36) | 37 | 16 | `vie*16/305` (ou 16 si vie = `0x0BEA`) | `0x0A` | 290‑293 | 22‑37 |

### 3.4 `_draw_sprite(screen, x, y, sprite)` — L19283

```
x, y en PIXELS
clip : y < 0 -> rien ; y > 184 -> ne garder que 200-y lignes
A0 = screen + y*40 + (x >> 4)*2 ; décalage de bits x & 15 (ROR.L D0,…)
A1 = _sprite_data + sprite*160
masque mot + 4 plans mot, sémantique identique au blit de tuiles (§ 9.3 de
map_generation.md) : ecran = (ecran AND masque) OR donnees
```
Renvoie aussi la longueur de rangée utilisée pour la 2ᵉ moitié (`D7` = `0x26` si
`x <= 0x130`, sinon `0x28`) **[à confirmer]**.

### 3.5 `_toggle_icon(screen, x, y, mask)` — L19493

```
A0 = screen + 322*x + 318*y + mask
16 EOR.L successifs, A0 += 40 entre chacun
table LAB_4C750 : 16 longs formant un losange 32x16
   00000000 / 0000c000 / 0003f000 / 000ffc00 / 003fff00 / 00ffffc0 /
   03fffff0 / 0ffffffc / 3fffffff / puis miroir
```
* `322 = 40*8+2` et `318 = 40*8-2` : `x` et `y` sont en **demi-cellules
  isométriques** (+16 px / −16 px).
* **Seul le plan 0 est XORé** : l'opération ne change que le bit 0 de l'indice de
  couleur (±1). C'est un simple « surlignage » d'un bouton déjà présent dans
  qaz.pic.
* Appelé avec `_back_scr` : l'état on/off du bouton est donc **persistant**.

---

## 4. Zones de l'écran

```
 y
 0   +--------------------------------+----------------------+
     | mini-carte (Book of Worlds)    |  barre de population  |
     |  x = X-Y+64 , y = (X+Y)>>1     |  x 258-261  x 314-317 |
 64  +        losange de la vue       +----------------------+
     |        x 64..319               |                      |
     |                                |   écusson + barres    |
136  |                                |   (x 268..301)        |
     |                                |                      |
200  +--------------------------------+----------------------+
                                             x=320
```

* **Mini-carte** : `x ∈ [1,127]`, `y ∈ [0,63]` — losange isométrique de la carte
  64×64. Voir §8 de `map_generation.md`.
* **Fenêtre isométrique** : losange inscrit dans `x ∈ [64,320)`, `y ∈ [64,200)`
  (les tuiles d'eau commencent 7 px plus bas : leur sommet est à la ligne 7 de
  la tuile, celles de terre à la ligne 0).
* **`xoff`, `yoff` ∈ [0, 0x38]** = `[0,56]` (= `64-8`).

---

## 5. `_show_the_shield` (L2769) — l'écusson

Affiche la fiche de `_view_who` (l'unité sélectionnée) :

```
A2 = _peeps + (_view_who - 1) * 0x16        # fiche d'unité de 22 octets
si (A2+4) <= 0 : _view_who = 0, retour
```

### Fiche `_peeps` (22 octets) — champs utilisés ici

| offset | taille | contenu |
|---|---|---|
| `+0` | octet | `state` — bit 3 = engagé dans un combat |
| `+1` | octet | `tribe` (0 = joueur « bon », 1 = « mauvais ») |
| `+3` | octet | `weapons` — index dans `_weapons_order` |
| `+4` | mot | `life` |
| `+6` | mot | index de l'adversaire |
| `+0xC` | mot | `frame` = index du sprite à afficher |

(Ces décalages correspondent champ à champ à `populous/sim.py::Peep`.)

### Ce qui est dessiné

| ligne | routine | position | contenu |
|---|---|---|---|
| L2790‑2794 | `_draw_icon` | px **(272, 4)** | icône `tribe` (0‑5 : couleurs de joueur) |
| L2817‑2821 | `_draw_icon` | px **(288, 4)** | icône `weapons_order` + 1 (armes, 2‑11) |
| L2826‑2830 | `_draw_sprite` | px **(272, 22)** | sprite `frame` de l'unité (si `state&8`) |
| L2896‑2900 | `_draw_sprite` | px **(268, 22)** | sprite `0x40 + 2*tribe + _toggle` (si `state==1`) |
| L2871‑2877 | `_draw_bar` | x 36, y 37, total 16, couleur `0x0F` | part de vie de l'adversaire |
| L2879‑2885 | `_draw_bar` | x 37, y 37, total 16, couleur 8 | part de vie de l'unité |
| L2915‑2921 | `_draw_bar` | x 36, y 37, total 16, couleur `0x0A` | valeur 16 si `vie == 0x0BEA` |
| L2925‑2937 | `_draw_bar` | x 36, y 37, total 16, couleur `0x0A` | `vie*16/305` |
| L3042‑3051 | `_draw_bar` | x 36, y 37, total 16, couleur `0x0A` | `D4/1024` (`D4 = (A2+4)` si `> 0x1000`) |
| L3053‑3063 | `_draw_bar` | x 37, y 37, total 16, couleur 9 | `D4 mod 1024` |
| L3065‑3144 | `_draw_bar` | voir le listing | branches restantes **[à confirmer]** |
| L3033‑3037 | `_draw_sprite` | px **(272, 22)** | sprite calculé `D4` (portrait/animation) |

Les deux barres à `y = 31, total = 32` (population) et celles de `y = 37` sont
**empilées** : la première occupe les lignes 0‑31, la seconde les lignes 22‑37.

---

## 6. Clics — `_zoom_map` (L1658)

### 6.1 Mini-carte

```python
u = mousex // 2 + mousey - 32      # -> X
v = mousey - mousex // 2 + 32      # -> Y
if 0 <= u < 64 and 0 <= v < 64:            # rectangle 128x64 de la mini-carte
    xoff = clamp(u - 3, 0, 0x38)
    yoff = clamp(v - 3, 0, 0x38)
```
Vérification : `u - v + 64 = mousex`, `(u + v) // 2 = mousey` ✓.

### 6.2 Barre d'icônes (`u > 0x112`)

```python
col = (u - 0x110) >> 4             # 0..2   (3 colonnes)
row = (v - 0x20) >> 4              # 0..9   (10 lignes)
```
Grille **3 × 10 = 30** cellules (les 30 icônes de `_icon_data`).
Centres isométriques des boutons : `(304 + 16*(col-row), 160 + 8*(col+row))`.

Cellules déjà identifiées :

| (col,row) | action |
|---|---|
| (0,0) | bascule `_d_screen`, masque `0x17e4` |
| (0,3) | musique on/off |
| (0,4) | effets on/off |
| (1,1), (1,3), (2,2) | **[à confirmer]** |

Les cellules non traitées retombent sur `LAB_3F666` **[à confirmer]**.

### 6.3 Pavé de défilement (`v >= 0x90`)

```python
vp = (v - 0x90) >> 4               # 0..2
up = (u - 0x60) >> 4               # 3..4
```
Neuf losanges isométriques centrés en `(64,168)`, le centre étant `(up=4, vp=1)`
→ `_view_who` ( sélectionne l'unité ). Ensuite :

* `col == 5` → `xoff += 1` … `col == 3` → `xoff -= 1`
* `row == 2` → `yoff += 1` … `row == 0` → `yoff -= 1`

**[à confirmer : le découpage exact 3×3 et le sens des flèches]**

---

## 7. Outils et fichiers associés

| fichier | rôle |
|---|---|
| `populous/game.py` | **fenêtre + boucle d'image + déplacement de la vue** (`python -m populous.game`) |
| `tools/render_screen.py` | compose **l'écran complet** : qaz.pic + mini-carte + fenêtre 8×8 + barres |
| `tools/render_map.py` | vue isométrique seule, carte complète, mini-carte |
| `tools/ascii_view.py` | dump ASCII d'une image par fourchette de couleur |
| `tools/check_render.py` | vérifie `cell_px == cell_abs` et les 3 passes |
| `tools/check_assets.py` | vérifie le décodeur PIL contre la transcription naive, pixel à pixel, + chrono |
| `tools/compare_blit.py` | compare les deux lectures du masque des tuiles/sprites (voir §3 de `map_generation.md`) |
| `tools/extract_icon_data.py` | les 30 icônes de `_icon_data` |
| `assets/qaz.png` | aperçu décodé de qaz.pic |
| `out_png/screen_seed*.png` | derniers rendus |

Lancement :

```
python tools\render_screen.py <graine> <sol> <xoff> <yoff>
python -m populous.game  <graine> <sol> <zoom>
```

`populous/game.py` applique les règles de ce document : `_xoff/_yoff` bornés à
`[0, 0x38]`, clic sur la mini-carte → `u = mx//2 + my - 32`,
`v = my - mx//2 + 32` puis recentrage `clamp(cible - 3, 0, 0x38)`, clic dans le
losange → inversion `d0 - d1 = (mx-176)/16` et `d0 + d1 = (my-64)/8`. Le fond
`qaz.pic` et la mini-carte sont composés **dans `_back_scr`** avant le blit,
comme dans la boucle d'image originale.

---

## 8. Points restants à décoder

1. Toutes les branches de `_show_the_shield` (L3065‑L3144) → quelles grandeurs
   mesurent les barres restantes.
2. Les cellules `(col,row)` non identifiées de la barre d'icônes (§6.2).
3. `_paint_the_map` (L15123) — le panneau du Book of Worlds / éditeur.
4. Le découpage exact du pavé de défilement (§6.3).
5. `_requester` (L9901) — le cadre de dialogue et ses 21 icônes.
