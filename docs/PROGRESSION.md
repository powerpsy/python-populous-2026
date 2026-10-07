# État d'avancement du remake

Mise à jour : ce fichier décrit ce qui est **jouable** aujourd'hui et ce qui
reste à faire. `python -m populous.game` lance le jeu.

---

## Ce qui marche (testé)

| étape | état | test |
|---|---|---|
| Génération du terrain | ✅ | `tools/probe_terrain.py`, `render_map.py` |
| Rendu isométrique (3 passes) | ✅ | `check_render.py` → 0 écart projection |
| Décodage des assets (PIL, cache) | ✅ | `check_assets.py` → 0 pixel différent |
| Fenêtre + boucle d'image + scroll | ✅ | `populous/game.py` |
| Mini-carte (Book of Worlds) cliquable | ✅ | clic → recentrage |
| **Habitants** (peeps) rendus | ✅ | 11 sprites dans un village |
| **Bâtiments** (villes via sprite frame + `bk2`) | ✅ | ville frame 42 + murs 41-44 |
| Mana (accumulation + jauge) | ✅ | 210 840 à t=20000 |
| **8 pouvoirs** + arbre/rocher | ✅ | 9 actions testées OK |
| IA adverse (choix + mana) | ✅ | agit ~25 fois / 40 tours |
| **Équilibre des 2 tribus** | ✅ | 6495 vs 4494, 4459 vs 9268, … |

## Comment jouer (à ce jour)

```
python -m populous.game [graine] [sol] [zoom]
```

* Les deux tribus se fondent, croissent, se divisent, bâtissent.
* L'IA ennemie joue (releve, plante, pose des pierres) et accumule de la mana.
* Pas encore de pouvoir jouable à la souris (l'IA s'en sert, le joueur non).

### Touches
`flèches`/`WASD` déplacer · `clic` recentrer · `molette`/`+ -` zoom ·
`Tab` sol · `N` graine · `P` animation eau · `F1` plein écran · `Échap`/`Q` quitter.

---

## Bugs corrigés cette session (importants)

1. **`map_who` orphelins** — `move_explorer` marquait la case quittée sans la
   libérer ; un peep mort laissait une traînée de marqueurs (178 orphelins à
   20 000 tours). Corrigé : libération de la case quittée.
2. **Peeps entrant sur rochers/eau** — `where_do_i_go` pouvait renvoyer un
   décalage vers un bloc `$2F..$31` ; le peep se retrouvait planté sur un
   rocher, incapable de fonder. Corrigé dans `move_explorer`.
3. **Explorateur bloqué** — il visitait 6 cases en 463 tours sans jamais trouver
   de `$0F` constructible. Ajout d'un **regard à distance** (`_find_flat_ahead`,
   rayon 3) qui guide l'explorateur vers de la vraie plaine. Les deux tribus
   sont maintenant **parfaitement équilibrées** (5998 vs 5998 sans IA).
4. **Double `game_turn`** — `tick()` incrémentait `game_turn`/`toggle` alors que
   `move_peeps` le fait déjà ; la machine d'animation ne tournait jamais.
5. **Coûts des pouvoirs faux** — `COST_*` pointaient sur les *indices* de
   `MANA_VALUES` (1,2,3…) au lieu des *valeurs* (10, 200, 2500…).
6. **IA destructrice** — l'IA posait arbres/rochers sur la plaine du voisin
   (bloc `$2F`) et l'empêchait de fonder. Elle ne touche désormais que des
   cases constructibles et désertes, jamais près de l'adversaire.
7. **Index hors carte** dans `do_swamp` et `do_volcano`.
8. **Action IA bloquante** — une action non payable restait en attente
   indéfiniment et figeait l'IA (`st.act` est maintenant toujours libéré).

---

## Reste à faire

| # | étape | difficulté | état |
|---|---|---|---|
| A | **Pouvoirs jouables** (barre d'icônes → `_stats`) | moyenne | phase 4, à faire |
| B | **Son** (`popsam`, module Amiga) | **haute** | pas commencé |
| C | **Musique** (`gmusic1`) | **haute** | pas commencé |
| D | **Conquest** | - | donnees, textes et boite de dialogue |
| E | Interface complete | moyenne | OK : blason, jauges, `_text`, `_requester` |

---

## Phases 1 à 3 — validées

### Phase 1 - Modele d'interaction OK **68/68** (`tools/autopilot.py`)

**Le point le plus important** : `_zoom_map` et `_interogate` ne sont
**appelees que sur l'image ou un bouton vaut 0**, c'est-a-dire **une seule
image par clic**. La sequence de la boucle d'image (L962-1013) est :

```
LAB_3EC20  if (_mode & 0x0E) : _sculpt()
           elif _left_button == 0 or _right_button == 0 : _interogate()
LAB_3EC40  if not (_left_button and _right_button) :
               _zoom_map(1 if _left_button == 0 else 0)
LAB_3EC60  _left_button  = 2 if _left_button  == 2 else 1
           _right_button = 2 if _right_button == 2 else 1
LAB_3EC88  _get_message(0)
```

`_left_button` n'est donc **jamais** « bouton maintenu » : c'est un etat a
quatre valeurs (`0x40` relache, `0` clic, `1` stable, `2` bloque) et `0` ne
dure qu'une image. L'epilogue de `_zoom_map` (L2442) met `2`, et `_mouse`
(L19584) ne l'accepte qu'apres un relachement : c'est l'anti-rebond.

#### `_sculpt` - la souris designe une case (L7271)

C'est **la** fonction de selection, entierement recalculee :

```
zone        : not _war ; 0x3E <= u <= 0x10A ; -0x40 <= v <= 0x88 ; mx >= 0x40
diagonale   : d4 = (mousex - 0x38) >> 4
zigzag      : d4 > 8  -> base += d4-8,      step += (d4-8)*8,   nb = 0x11-d4
              d4 < 8  -> base += (8-d4)*0x41, step += (8-d4)*8, nb = d4+1
balayage    : top_i = step_i - alt*8 ; on retient la DERNIERE case
              telle que top_i <= mousey+4   (CMP.W D1,D2 / BGT)
curseur     : sprite 0x54 a (d4*16+0x3D, top-3), seulement si top-3 < 0xC0
```

**Valide par execution** : sur un terrain mis a plat, les 64 cases de la fenetre
8x8 sont **toutes** atteignables et chacune occupe **exactement 256 px**, soit
un bloc de 16 x 16 px — la demi-colonne d'un losange de 32 x 16. Avec le relief
les bandes se resserrent ou se chevauchent selon l'altitude, exactement comme
dans l'original, qui ne balaie que 9 cases par diagonale (L7325) : une falaise
peut donc masquer la case suivante.

#### La palette d'outils (LAB_3F666, table de 9 entrees)

Le dispatch final de `_zoom_map` est une **table de sauts indexee par
`up = (u - 0x60) >> 4`**, le second parametre etant `vp = (v - 0x90) >> 16`.
A l'ecran cela occupe le parallélogramme `x dans [0,160)`, `y dans [120,200)` :
la colonne d'icones du bas-gauche. Centre de la case `(up, vp)` :

```
mousex = 16*(up - vp + 1)          mousey = 128 + 8*(up + vp)
```

Les codes ecrits dans `stats+2` **coincident exactement** avec nos constantes
`ACT_*` - confirmation independante de la table :

| entree | stats+2 | constante | mana |
|---|---|---|---|
| `(0,0)` | 4 | `ACT_SWAMP` | 5 000 |
| `(1,0)` | 3 | `ACT_QUAKE` | 2 500 |
| `(2,1)` | 5 | `ACT_MAGNET` | 200 |
| `(3,3)` `(4,3)` `(4,4)` `(5,3)` | 1 | `ACT_RAISE` (+ direction) | 10 |
| icone `(0,0)` | 7 | poser un peuple | - |
| icone `(1,1)` | 8 | poser un peuple | - |
| icone `(1,3)` | 6 | `ACT_VOLCANO` | 10 000 |
| icone `(2,2)` | 2 | `ACT_LOWER` | 10 |

Le joueur **arme** une action avec la palette, puis **cible** une case avec un
clic : le mana est decompte au cout exact et le terrain change (verifie pour
relever / aimanter / seisme / marais).

#### Deux ecarts assumes, documentes dans le code

1. **`LAB_516A5` (cible X)** : le listing ecrit `MOVE.B (-1,A5)`, qui lit le
   demi-mot **haut** de `cur_x` - toujours nul puisque `cur_x < 64`. La cible
   serait donc toujours la colonne 0 ; on prend `cur_x` entier.
2. **`bitfield_51645`** : l'offset `A4+0x8257` est juste apres `_mode`
   (`0x8256`), c'est donc le **demi-mot haut** de `_mode` (bits 11 et 10). Ces
   deux bits ne sont poses nulle part dans le listing, et la branche par defaut
   `LAB_43828` ecrase `stats.act` avec 1 - ce qui supprimerait toute action
   choisie a la palette. On ne l'ecrase donc que si l'un des deux bits est
   reellement pose.

#### Transcription (tableau recapitulatif)

| element | asm | transcription |
|---|---|---|
| souris | anti-rebond 4 etats, `0` = 1 image | `poll_mouse` |
| dispatch | `_sculpt` si `_mode & 0x0E`, sinon `_interogate` | `poll_mouse` |
| | `_zoom_map` seulement si un bouton vaut 0 | `zoom_map` |
| mini-carte | `clamp(u-3,0,0x38)` (L1679) | OK |
| barre d'icones | `(0,0)(0,3)(0,4)(1,1)(1,3)(2,2)` (L1706-1824) | OK |
| pave | `up dans [3,5]`, `vp dans [0,2]`, +/- 1 case (L1825-1927) | OK |
| palette | table de 9 entrees (LAB_3FC92) | `palette` |
| survol | boite 12x8 sur `_sprite[]` (L2719) | `interogate` |
| curseur | sprite `0x54`, **pas** un losange invente | `_draw_cursor` |

**Supprime** parce que l'asm ne l'a pas : les raccourcis Z/X/C/V, le clic
gauche qui applique un pouvoir directement, le losange jaune de surlignage, le
pas de defilement de 4.

### Phase 2 — Tribuns ✅

Machine d'animation vérifiée : `frame` 0→6 (7 poses), `frame` 7 = pause,
retour à 0 avec `retour = 1` qui déclenche le pas. **8 images par pas**, donc
0,27 s à 30 fps.

Cycle de marche mesuré sur une vraie partie : 12 images pour se déplacer d'une
case, puis fondation de ville (`state 2 → 1`, `frame = 0x2A`).

### Phase 3 — Constructions ✅

**Bug trouvé et corrigé** : `_big_city` dans `constants.py` contenait des
**chaînes** (`'0x2a'`) au lieu d'entiers — vérifié contre l'asm :

```
_big_city:  DC.L $002a002c,$002b002c,$002b0029,$00290029 ; DC.W $0029
```

Résultat : après 4000 tours, 9 bâtiments de ville sont posés
(0x29 murs ×4, 0x2A château, 0x2B/0x2C ×4).

Le sprite **0x54** est la **croix de sélection** de `_sculpt` — ce n'est pas le
pointeur système mais un sprite du jeu (vérifié : 9 pixels, forme de croix).

### Phase 4 — Pouvoirs du joueur ✅ (partiel)

Les 4 actions vérifiées de bout en bout (palette → cible → mana → terrain) :

| action | `stats+2` | mana | effet observé |
|---|---|---|---|
| relever | 1 | 10 | sommet +1, `map_blk` recalculé |
| abaisser | 2 | 10 | sommet −1 |
| aimanter | 5 | 200 | `sim.set_magnet_to` |
| séisme | 3 | 2 500 | 28 codes de case modifiés |
| marais | 4 | 5 000 | une case `blk=0x35` |

### Phase 5 - Interface : primitives et ecusson

`_draw_icon` (L19184), `_draw_bar` (L19213) et `_show_the_shield` (L2769) sont
transcrits, avec les 30 icones de `_icon_data` chargees par `assets.load_icon`.

**Addressing.** L'ecran fait 320x200 en 4 bitplans plane-major : 1 octet = 8
pixels, 1 plan = 8000 octets (0x1F40), 1 ligne = +0x28 = 40 octets.

| primitive | asm | `x` recu | pixel |
|---|---|---|---|
| `_draw_sprite` | L19283 | unites de 16 px (`LSL.W #1`) | `x*16` |
| `_draw_icon` | L19184 | unites de 16 px (`LSL.W #1`) | `x*16` |
| `_draw_bar` | L19213 | **offset en octets** (pas de `LSL`) | `x*8` |

C'est une piege : les deux premiers recoivent `x*2` octets, le dernier `x`.
Verifie a l'execution — `draw_bar(36, ...)` ecrit bien au pixel 288.

**`_draw_bar`** : la barre se remplit **vers le haut** a partir de `y` ; les
`filled` premieres lignes portent les `flags` du caller, le reste porte
`flags = 2` (L19242). Pour chaque plan `p`, `BTST #p` choisit entre
`ORI.B #$3c` et `ANDI.B #$c3`, c'est-a-dire les bits 2 a 5 de l'indice de
couleur. Verifie : `filled=10` donne exactement 10 lignes bleues puis 6 lignes
grises (le `flags=2` eteint le plan 0 et allume le plan 1 — un motif, pas du
fond).

**`_show_the_shield`** : le panneau de l'habitant suivi. `_view_who == 0` ->
rien (L2772) ; `life <= 0` -> oublie l'habitant (L2780) ; `_draw_icon(0x11,
0x04, tribu)` pose le blason (L2790) ; l'arme est cherchee dans
`_weapons_order[1..10]` (L2796) ; ensuite trois branches — combattant
(`state & 8`), ennemi (`tribe == 1`) ou villageois — chacune tracant deux
barres. Les deux jauges de population suivent (L403F4).

Comme l'original dessine l'ecusson dans `_w_screen` (le fond) et non dans
`_d_screen` (la fenetre 8x8), on le trace apres le terrain : meme resultat.

**HUD de debogage desactive.** L'original n'affiche aucun texte — tout est
dans `qaz.pic` et dans l'ecusson. Le bloc `_draw_hud` ne s'execute plus que si
la variable d'environnement `POPULOUS_HUD` est definie.

### Phase 6 - `_toggle_icon` : l'icone de l'outil arme (L19493)

C'est la piece qui rend l'etat **visible** : sans elle le joueur arme un
pouvoir et rien ne le signale.

L'asm ecrit un **losange de 16x16** en XOR sur l'icone. La table `LAB_4C750`
donne les 16 masques :

```
$0000c000 $0003f000 $000ffc00 $003fff00 $00ffffc0 $03fffff0
$0ffffffc $3fffffff $0ffffffc $03fffff0 $00ffffc0 $003fff00
$000ffc00 $0003f000 $0000c000        (+ 0 pour la 16e ligne : le DS.L 1)
```

En ne gardant que les 16 bits de poids faible de chaque mot (le bit de poids
fort est le pixel de gauche, comme dans un plan Amiga) on obtient exactement le
**losange**, ce que confirme l'execution :

```
largeurs = [2, 4, 6, 8, 10, 12, 14, 16, 14, 12, 10, 8, 6, 4, 2, 0]
```

**Addressing de la grille.** L'asm multiplie par `0x142 = 322` et
`0x13E = 318`. En unites de la ligne (40 octets) et du pixel (8 px par octet de
plan) : `322 = 8 lignes + 16 px` et `318 = 8 lignes - 16 px`. La grille est
donc la grille **isometrique** de l'interface, et l'on retrouve exactement les
coordonnees de la palette : l'offset asm est toujours 16 px a gauche et 8 px
au-dessus du centre calcule par `16*(up-vp+1), 128 + 8*(up+vp)`.

**Etat persistant.** L'asm ecrit en place dans `_back_scr`, qui n'est jamais
efface : l'icone reste inversee d'une image a l'autre, et un second clic annule
l'effet (double XOR). On reproduit cela avec un **ensemble** `icon_toggles`
reapplique a chaque composition — meme comportement, memes consequences :

```
(3,3) -> (1,0) -> (3,3)   :   il ne reste que (1,0) active
```

`_set_tend_icons` (L2455) est cable : il inverse la croix de selection en plus
de l'icone demandee, en fonction de `LAB_52DE8[player]` — les quatre positions
(3,3), (4,3), (5,3) et (4,4) sont exactement les quatre outils de relief
directionnels de la palette.

### Phase 7 - `_text` et `_requester` : la police et les boites de dialogue

**`_text` (L19973)** ecrit une chaine avec la police de `font.dat`. Addressing
exact : ``A0 = ecran + (x >> 3) + y * 0x28``. Donc **x est en unites de 8
pixels** — une troisieme convention, differente de `_draw_icon` (unites de 16
px) et de `_draw_bar` (octets). Chaque glyphe fait 8 lignes, et le glyphe est
ecrase (`(ecran AND masque) OR donnees` sur les 4 plans), donc transparent la
ou le glyphe est vide.

Le retour a la ligne est un saut de **0x140 = 320 octets = 8 lignes** exactement
(« ``ADDA.L #$00000140,A1`` »), ce que la police du jeu confirme a l'ecran.

**`_requester` (L9901)** dessine les boites de dialogue : `D4 = x >> 4`,
`D5 = y >> 4`, `largeur >>= 4`. Le cadre est fait d'icones de 16x16 posees une
par une — 0x0C a gauche, 0x0D jusqu'a n, 0x0E ; 0x0F et 0x10 en bas ; 0x12 et
0x14 sur les cotes ; 0x13 et 0x17 aux coins — puis le titre a `y + 3` et le
message centre dans la largeur.

**Le piege des unites.** `_draw_icon` recoit un `x` en unites de 16 px mais un
`y` **en lignes** (`y * 0x28`). C'est asymetrique, et c'est ce qui faisait que
le premier essai de `_requester` produisait un cadre ecrase en hauteur.

### Phase 8 - Conquest : textes, boites de dialogue, et un bug d'alpha

**`tools/extract_strings.py`** extrait les **48 chaines en dur** du listing
(`DC.B "TEXTE",0`) vers `assets/strings.json`. On y trouve `"SAVE GAME"`,
`"LOAD GAME"`, `"START GAME"`, `"GAME SETUP"`, et surtout **`"TRY NUMBER "`** —
le titre exact de la boite de saisie du numero de niveau de Conquest.

Les textes de Conquest ne sont **pas** dans `gwords` : ce fichier est un
dictionnaire de mots longs (4 octets, tous a 0x4040 au debut). `_word_asc`
(asm L21054) est un simple convertisseur **entier -> decimal**, utilise pour
ecrire le numero du niveau a la suite de `"TRY NUMBER "`. Le reste du texte de
la boite vient des chaines en dur.

**`_requester` (L9901) — signature reelle.** Les 6 pushes avant le JSR donnent :

```
_requester(ecran, x, y, largeur, hauteur, titre, message)
```

avec `D4 = x >> 4`, `largeur >> 4` (colonnes), `D5 = y >> 4` (premiere ligne).
Le cadre est fait d'icones : 0x0C / 0x0D… / 0x0E en haut, 0x12 et 0x13 sur les
cotes, 0x0F / 0x10… en bas ; le titre est ecrit 3 lignes sous le bandeau et le
message 5 lignes plus bas, centre sur `(colonnes * 16 - strlen) / 2`.

### Bug important : `self.frame` sans canal alpha

`self.frame` etait cree par `pygame.Surface((320, 200))` — **sans alpha**. Or
pygame, sur une destination sans `SRCALPHA`, ecrase la destination par la
source **alpha comprise** : les sprites transparents et les glyphes de la
police n'apparaissaient donc pas du tout. C'est ce qui rendait le texte
invisible alors meme que `draw_text` ecrit bien ses pixels (verifie : 14 pixels
pour un `T`).

Correction : `pygame.Surface((320, 200), pygame.SRCALPHA, 32)`. Ce defaut
existait depuis le debut du rendu — il masquait toute la transparence.

### Phase 9 - La saisie du numero de niveau (asm L11942)

La boucle de saisie de Conquest est maintenant cablee au jeu. L'asm (L11926-11971)
fait :

1. `_requester(_d_screen, 0x30, 0x46, 0xE4, 0x40, "TRY NUMBER ")` ;
2. `_left_button = 2` — on bloque la souris pendant la saisie ;
3. boucle `LAB_46D3C` : `_word_asc` ecrit la valeur en decimal, `CMPI.W
   #$7530` la borne a **30000**, et la touche **0x0D** valide
   (`LAB_46E36`) ; toute autre frappe reboucle ;
4. apres validation, la valeur est lue puis `LAB_46F40` (le nom du niveau)
   est ecrit en (0x40, 0x60).

Notre version garde exactement cette machine — tampon, valeur, borne a 30000,
validation au retour chariot — mais au lieu d'une boucle bloquante on l'ouvre
et on la ferme aux touches, comme le joueur ferait. `handle()` donne la
priorite au dialogue tant qu'il est ouvert, donc les chiffres n'actionnent pas
les raccourcis du jeu.

Touche : **L** ou **]** ouvre la boite, **Entree** valide, **Echap** annule,
**Retour arriere** efface.

Verifie par execution : `1` -> `17` -> (retour) `1` -> `142` -> (Entree)
palier 99 charge (graine 55, sol 1, 13 ennemis, mana 10).

### Etat du son et de la musique (analyse faite, non branche)

J'ai lu `_load_sound` (L20712), `_PlaySound` (L20307) et `_PlayMeas` (L20433).
Ce que l'on sait avec certitude :

* **C'est un module de musique Amiga** et non un WAV : pas de magic IFF dans
  `popsam`, `gmusic1` ni `gwords`. Le fichier charge par `_Open` avec le mode
  `$3ED` (L20714), ce qui laisse le format a la charge du handler DOS.
* `_PlayMeas` (L20433) lit **4 sous-pistes par mesure**, aux offsets `+0x00`,
  `+0x40`, `+0x80`, `+0xC0` de `_curmeas` — donc **0x100 octets par mesure**,
  chaque voie tenant 64 encoches. Chaque encoche est un octet dont on soustrait
  `$41` : **0 = silence**, le reste est l'identifiant du son.
* `_PlaySound(n, voie)` selectionne `_ioas[voie]`, verifie `_CheckIO`, compare
  la priorite `_Soundpri`, puis lance via `_AbortIO` / `_StartIO`.
* `_load_sound` lit dans cet ordre : `_measln` (2), `_seqlen` (2), `_sequn`
  (4 x seqlen), `_measure_length` (4), une zone de `0x1000` octets, puis — si
  `_measure_length > 0x1000` — un `Seek(_measure_length - 0x1000)` ; ensuite
  `_no_sounds`, `_drumkit`, `_sams`, `_all_sample_length` et les echantillons.
  `_sequn << 8` donne l'adresse de la premiere mesure (L20844-20848).

**Ce qui bloque** : nos fichiers extraits commencent directement par les
donnees de mesures (`gwords` est un bloc de `00 40` = silence, avec `41` et `42`
aux changements de voie). Il n'y a **aucune trace de l'en-tete** decrit par
`_load_sound`, ce qui signifie que le format n'est pas Teleparagon mais
probablement un format proprietaire gere par `Open($3ED)`. Sans le handler DOS
on ne peut pas savoir ce qu'il attend.

Deux voies possibles, a trancher avec vous :

1. **Rendre le son** (le plus utile au jeu) : synthetiser les bruitages a partir
   des evenements de simulation deja calcules (pas de fichier), avec les
   memes codes d'effet que l'asm (`$42` pour une mort, `$47/$48` pour la
   mesure du tempo, `$4D` pour l'aimant, `$50 | (code & 0x0F)` en L713) ;
2. **Decouvrir le format** : chercher le nom reel du fichier sur le disque
   d'origine, ou retrouver le handler DOS associe a `$3ED`.

### Phase 10 - Le son (`_PlaySound` L20307, `_PlayMeas` L20433, horloge L19620-19673)

**pymod n'aide pas** : le paquet PyPI `pymod` est un **gestionnaire de
paquets** (homonymie), pas un lecteur de modules. Et apres verification
(`tools/check_mod.py`), **aucun de nos trois fichiers** — `popsam`, `gmusic1`,
`gwords` — ne porte de signature ProTracker (`M.K.`, `4CHN`…). Ce ne sont donc
pas des `.mod` : c'est confirme par le decodeur de `_load_sound` lui-meme.
`populous/sound.py` synthetise donc les timbres, mais **toute la logique de jeu
est transcrite de l'asm**.

**33 timbres** generes (ondes glissades, carres, triangles, bruit a graine
fixe), un par code d'effet, chacun avec son enveloppe attaque/decroissance.

#### L'horloge audio : L19620-19673

Ce handler est appele **une fois par image** (la partie sonore de la VBI). Il
fait, dans cet ordre exact :

1. si `_music_off` est **non nul** : `_music_now += 1` ; s'il atteint
   `_music`, on remet `_music` a 10, on joue une mesure, et on reboucle le
   compteur a zero ;
2. si `_effect_off` est non nul :
   * si `_effect != 0` : `_music = 0x28` (**40**) — c'est ce delai qui
     **repousse la prochaine mesure** — puis l'effet joue sur les **voies 2
     ET 3**, `_effect` est mis a zero, et le bloc du tempo est **saute** ;
   * sinon, si `_sound_in == 0` et `_tempo != 0` : le tic. `_tempo_now += 1` ;
     s'il atteint `_tempo`, son `$47` et remise a zero ; sinon, si
     `_tempo - _beat_two == _tempo_now`, son `$48`.

**Bug de polarite trouve.** Les etiquettes de l'asm disent `_music_off` et
`_effect_off`, mais L19621 et L19633 font `TST.W` puis `BEQ` : le bloc est
**saute quand le mot est zero**. Le son joue donc quand le drapeau est **non
nul** — l'inverse de ce que suggere le nom du symbole. On suit le code, pas
l'etiquette : les attributs Python sont `music_on` / `effect_on`. (Mes
icones etaient donc inversees : le son etait coupe quand on l'activait.)

#### Le tempo : derive de la population (L557-603)

`_tempo = 0x32 - (pop_adv / pop_joueur) * 2`, borne a un minimum de **7**, puis
`_beat_two = _tempo / 3`. Si la population du joueur est nulle, `_tempo = 0`
(plus de tic) et `_beat_two = 1` (LAB_3E852). **Plus l'adversaire est peuple,
plus le tempo est court, donc plus les tics sont rapproches** — c'est
exactement ce que fait l'asm.

Verifie par execution :

| pop joueur / pop adv | `_tempo` | `_beat_two` |
|---|---|---|
| 100 / 0   | 50 | 16 |
| 100 / 50  | 50 | 16 |
| 100 / 100 | 48 | 16 |
| 100 / 400 | 42 | 14 |
| 0 / 100   | 0  | 1  |

#### Les deux gardes de `_PlaySound` (L20311-20314)

* `son < _no_sounds` — un code inconnu ne produit **rien** ;
* `voie <= 3` — il n'y a que **4** voies, en indices 0..3.

Verifie : `play(0x42, 3)` joue, `play(0x42, 4)` et `play(0x42, -1)` sont
refuses, `play(0x60, 0)` est refuse (`0x60 == _no_sounds`), `play(0xFF, 0)`
refuse.

#### La mesure (`_PlayMeas`)

4 sous-pistes de 64 notes (`curbeat + 0x00 / +0x40 / +0x80 / +0xC0`), une note
par voie, `0` = silence. Le fichier n'etant pas lisible, les sous-pistes sont
generees (gamme pentatonique mineure), mais leur **structure** est celle de
l'asm.

#### Un deuxieme bug : l'effet etait lu trop tot

`_run_commands` lisait `sim.effect` en **fin** de tour, mais `sim.effect` est
ecrit *pendant* `move_peeps` : le tour suivant l'ecrasait, et aucun son ne
jouait. Correction : la simulation ne fait que **ecrire** le mot `_effect`,
et c'est l'horloge audio — appelee une fois par image depuis `run`, comme la
VBI — qui le **consomme**. C'est la transcription directe de l'asm.

**Mesures** : 894 effets joues sur 3000 tours (les pieux de la tribu adverse) ;
125 mesures, 9 degres distincts. Fenetre reelle + mixer reel : 400 images en
1,00 s (398 img/s, tres au-dessus des 30 img/s de l'original), aucune
exception.

### Phase 11 - La fin de partie et l'ecran de victoire (L4323, L14019, L14460)

#### Attention : `LAB_46F40` n'etait pas la bonne cible

`LAB_46F40` est simplement la chaine `"CONNECTION MADE"` (le dialogue modem).
La vraie routine est **`_won_conquest`, L14460**, appelee depuis `_end_game`.

#### Le test de fin (L4323-4352)

Appele depuis la simulation, chaque tour :

* `good_pop[joueur] == 0` ou `_surender == joueur` -> `_end_game(1)` ;
* sinon `good_pop[adv] == 0` ou `_surender == adv` -> `_end_game(0)`.

Il compare bien **`good_pop`** (la population, somme des vies) et non le nombre
d'habitants.

**Bug de convention trouve.** L'asm ne passe pas un booleen « gagne » : a
L14027 il fait `CMPI.W #$0001,(8,A5)` et, si l'argument vaut 1, il ecrit
`"LOST"`. L'argument 1 designe donc la **defaite du joueur** — ce qui est
coherent : si la population du joueur est nulle, c'est lui qui a disparu. Notre
`_end_game(perdu)` conserve cette convention plutot que d'inverser le
drapeau.

Verifie par execution :

| evenement | `victory` | texte |
|---|---|---|
| joueur mort | `False` | `LOST` |
| adversaire mort | `True` | `YOU WIN` |
| joueur abandonne | `False` | — |
| adversaire abandonne | `True` | — |

#### Le calcul du palier suivant (L14462-14495)

.. code-block:: none

    n = ancien + score / 5000 + 1        # ADDQ.L #1 puis ADD.W
    reste = n % 5                        # DIVS #$0005 / SWAP
    if reste: n += 5 - reste
    if n > 0x9A6:                        # 2470, « WEAVUSPERT »
        if ancien == 0x9A6: n = 0 ; fini = 1     # on reboucle le mode
        else:                n = 0x9A6

`_seed = _level_number` ensuite : le niveau suivant est une **nouvelle carte**.
Verifie sur 17 couples (ancien, score) contre un recalcul independant : tous
concordent. La suite 0 -> 5 -> 10 -> 15 -> 20 -> 25 confirme le palier de 5.

#### L'ecran (L14520-14589, L14358-14363)

Trois lignes ecrites avec `_requester`, aux coordonnees du listing :

* `(8, 0xB2)` — le texte d'en-tete ;
* `(8, 0xBA)` — la ligne complete ;
* `(8, 0xC8)` — `TRY IT AGAIN`.

Les chaines viennent des `DC.B` du listing : `BATTLE NUMBER IS ` (LAB_52224),
`WORLDS LANDSCAPE IS ` (LAB_52228), `HIS RATING IS ` (LAB_5222C), `GENESIS`
(strGENESIS), `LOST` (strLost) et `TRY IT AGAIN` (strTryItAgain).

Comme l'asm, l'ecran **attend une touche** avant d'enchainer : la simulation
est figee, et la validation passe au palier suivant (`_next_conquest`).

#### Verifie par execution

* joueur/adversaire/abandon : les 4 cas donnent le bon `victory` et le bon texte ;
* session Conquest enchainee : palier 3 -> 6 -> 11 -> 16, population du joueur
  inchangee pendant l'ecran (la simulation est bien figee), puis reprise ;
* fenetre reelle : 200 images en 0,33 s (607 img/s), 30 images sur l'ecran de
  fin sans exception.

.. note::
   L'original joue aussi un **discours** (`_read_lord`, `_read_mouth`,
   `_draw_mouth`) et fait tourner un cycle de palette de 16 entrees
   (L14590-14603) pendant l'attente. C'est le seul element non rendu.

### Phase 12 - Les marqueurs `[APPROX]` : 4 sur 9 levés

Il restait neuf routines marquees « approchees ». Quatre sont maintenant
transcrites du listing ; les cinq autres sont identifiees (voir plus bas).

#### 1. `_set_town` — la construction et la demolition des villes (L5866-6062)

La routine **n'etait pas coupee** dans le listing, contrary a ce queAFFICHait
la note §9.1. Les six branches sont donc disponibles, et trois ecarts sont
corriges :

| point | avant (approximation) | asm |
|---|---|---|
| degradation grande ville -> ville | **17** cases (`N_NEIGHBOURS`) | **25** (`CMP.W #$0019`) |
| voisins d'une ville normale | `bk2 = 0x21 + (k % 0x0C)` | `bk2 = 0` — l'asm fait **`CLR.B`** |
| case du centre | `bk2[b] = 0x21` | `bk2[b] = peep[13]` si `blk[b] == $1F+tribu` |

Le « sequenceur » de `bk2` n'existe donc pas : la ville normale met simplement
a zero les 9 premiers voisins. Et le centre recoit l'**octet 13** de la fiche,
c'est-a-dire l'octet haut du mot ecrit a l'offset 12 (la disposition de
`_peeps`, base A4+$9c26, pas 0x16, a ete reconstitue depuis `_place_people`).

*Verifie* : 1500 cas random (position, tribu, frame, `grow`, contenu de carte)
confrontes a une reecriture independante du listing → **identique**, et les
6 branches nommees une par une. Aucun changement de comportement a 4000 tours
(0 batiment de tribu avant comme apres).

#### 2. `_set_magnet_to` (L8271-8291) — mauvais tableau !

L'asm ecrit dans le **struct joueur** (base `_magnet`, A4+$99f6), champ **+2**
(`LAB_52DE6`), et non dans `_stats`. Notre version ecrivait `stats[tribu].p1`
et `.p2` — une autre structure, sans rapport. Le chargement de partie
(L17605-17606) confirme la destination : `_god_magnet = LAB_52DE6[0]`,
`_devil_magnet = LAB_52DF6[0]`.

.. code-block:: none

    if _pause: return                 # TST.W (_pause,A4) / BEQ
    LAB_52DE6[tribu*16] = case        # struct joueur, offset +2
    if tribu == 0: _god_magnet   = case else: _devil_magnet = case

On a ajoute le champ `Player.magnet_to` (+2) et les deux miroirs
`god_magnet` / `devil_magnet`. Le calcul de la case, lui, etait deja correct
(`y*64 + x`, comme `_do_magnet` L6810-6812), ainsi que le cout de 200 mana.

#### 3. `_join_battle` (L6663-6732) — mauvaise semantique

Notre version appelait `set_battle` : la routine declenchait donc un combat la
ou l'asm **fusionne**. Le listing fait :

.. code-block:: none

    if src.tribu != dst.tribu: dst = peeps[dst].w6   # re-indexation
    total = src.vie + dst.vie
    dst.vie = 0x7D00 if total > 0x7D00 else total     # plafond 32000
    if magnet[tribu_src] - 1 == src: magnet[tribu_src] = dst + 1
    if _view_who - 1 == src:         _view_who      = dst + 1
    if dst > src:                    good_pop[tribu_src] -= src.vie
    if src.but:                      dst.but     = src.but
    if src.armes > dst.armes:        dst.armes   = src.armes
    src.vie = 0                                    # `CLR.W (4,A0)`

Le declencheur, lui, etait deja juste : `BTST #3,(A0)` (L4536), et notre
`ST_BATTLE` vaut bien `0x08`.

*Verifie* : fusion 100+50 = 150, plafond 30000+30000 = 32000, transfert de
l'aimant et de `_view_who`, correction de `good_pop`, conservation des armes
les plus fortes, mort de la source.

#### Les 5 marqueurs restants — et pourquoi

| routine | asm | pourquoi ce n'est pas transcriptionnel ici |
|---|---|---|
| `_one_block_flat` | L9148 | C'est la machine de **placement des batiments de l'IA**. Notre IA vit dans `powers.py::ai_choose`, ecrite a la main : la transposer seule produirait du code mort. |
| `do_place_funny` | L8862 | Ne se declenche qu'a **208 peeps** (`CMPI.W #$00d0`), un cas limite. |
| « prochain pas » | — | Marche d'exploration, melange avec notre propre heuristique de deplacement. |
| les 2 autres | — | Idem : appartiennent a la machine `devil_effect` (« demoniaque »), non transcrite. |

La seule transcription d'IA qui soit rentable est **le jeu de decisions
complet** (`devil_effect` + `_one_block_flat`), pas une routine isolee. C'est
le prochain gros chantier, et il est plus gros que tout ce qui precede.

### Phase 13 - La fiche `_stats` : une erreur de ma part, corrigée

> **Correction.** J'avais conclu en Phase 13 que nos champs `.act` / `.p2`
> étaient « transposés » par rapport a l'asm. **C'etait faux**, et la
> verification ci-dessous le montre.

Les ecritures de la barre d'icones dans le listing :

| icone | asm | ecrit |
|---|---|---|
| (0,0) poser un peuple | L1729-1733 | `stats+0 = $0E`, `stats+1 = valeur`, `stats+2 = $07` |
| (1,1) poser un peuple | L1795-1797 | `stats+0 = $0E`, `stats+2 = $08` |
| (1,3) volcan | L1803-1805 | `stats+0 = $0E`, `stats+2 = $06` |
| (2,2) abaisser | L1820-1822 | `stats+0 = $0E`, `stats+2 = $02` |

On en avait conclu que le masque etait en +0 et l'action en +2, et que nos
champs etaient inverses. Or **la routine qui lit reellement le masque est
`_devil_effect`**, et elle lit l'offset **+0x0E** :

.. code-block:: none

    MOVE.W ($E,A2),(-6,A5)      ; L9315 : le MOT a l'offset $0E
    BTST   #0,(-6,A5)           ; bit 0  du masque
    BTST   #7,(-5,A5)           ; bit 15 du masque
    BTST   #5,(-5,A5)           ; bit 13 du masque

Or notre :attr:`~populous.sim.Tribe.tend` **est** le champ a l'offset `0x0E`
(commentaire `power_mask # +0x0E`). `_one_block_flat` lit de meme l'offset
`$0F`, c'est-a-dire le bit 8 de ce meme mot (L9026, L9172).

Donc :

| | asm | notre fiche | verdict |
|---|---|---|---|
| masque `tend` | offset `0x0E` | `.tend` a `0x0E` | **juste** |
| valeur x | offset `+1` | `.p1` a `+1` | **juste** |
| action | offset `+0` (barre) | `.act` a `+0` | **juste** |

Les noms sont semanticement corrects et les lectures de l'IA tombent sur le
bon champ. Le seul ecart est que l'asm ecrit **aussi** `0x0E` a l'offset `+0`
lorsque la barre arme un outil — un second champ de masque que nous ne
modelisons pas. Sans consequence : rien dans le listing ne le relit a la
place du masque d'`devil_effect`.

**Le piege subsistant est ailleurs, et il est reel** : `stats+0x0E` est un
**long**, pas un mot (`MOVEA.L ($E,A2),A0` — L4914, L4921…). `_devil_effect`
n'en examine que le **mot bas**, bit a bit. C'est un champ a double usage,
et c'est ce qui rend la lecture du listing delicate.

### Phase 14 - Le portillon de l'IA (`queued`)

Le point d'entree, dans `_move_peeps` (L3252-3273) :

.. code-block:: none

    for t in (0, 1):
        if stats[t].queued == 0: _set_devil_magnet(t)
        if stats[t].queued == 0: _devil_effect(t)

`LAB_516AC` est l'offset `+8` de la fiche — notre :attr:`Tribe.queued`.
L'IA ne decide donc **que lorsqu'elle n'a aucune action en file** ; pendant
qu'une ville se fonde (`queued` pose par `sim.py` L603/L727), elle cesse de
decider.

Ce portillon **manquait** : `ai_choose` ne testait que `st.act`. Corrigé.
Verifie par execution : sur 3000 tours l'IA est eligible 1182 fois et prend
207 decisions ; avec `queued = 1` elle s'abstient et ne modifie ni `act` ni
`p1`/`p2`. Les 68/68 tiennent toujours.

#### Ce que fait `_devil_effect` (L9300-9601, 301 lignes)

Une cascade de priorites, toutes de meme forme. Le masque est lu une fois
(L9315) puis on teste ses bits de haut en bas ; **le premier qui passe
l'action** et la routine retourne.

Les seuils de mana sont des constantes de `_mana_values` (L24291-24304) plus
un decalage — l'IA est donc bien plus **`conserveuse`** que le joueur :

| branche | bit du masque | seuil | action ecrite |
|---|---|---|---|
| seisme | 0 | `0x13880 + 0x3E7` = **80999** | `+0 = $0E`, `+2 = $03` |
| deluge | 15 | `0x9C40 + 0x7CF` = **41999** | `+0 = $0E`, `+2 = $04` |
| aimant | 13 | `0x1D4C + 0x1F4` = **8000** | `+0 = $0E`, `+2 = $05` |
| effet computer | 14 | `0x2710 + 0x1F4` = **10500** | `+0 = $06`, puis `_do_computer_effect` |
| attaque | 12 | `0x1388 + 0x1F4` = **5500** | `+0 = $04`, + position visee |
| effet computer | 13 | `0x9C4 + 0x1F4` = **3000** | `+0 = $03`, puis `_do_computer_effect` |

A comparer aux couts du joueur (`constants.py`) : relever 10, aimant 200,
seisme 2500, marais 5000. L'IA n'emploie donc ses pouvoirs qu'extremement
tard, une fois sa population faite — c'est bien le comportement voulu.

Deux conditions meritent d'etre notees :

* le **seisme** exige en plus que la tribu soit **plus peuplee** que
  l'adversaire (`good_pop[t] > good_pop[1-t]`, L9341-9343) ;
* l'**aimant** exige que le peep aimant ait plus de `0x0BB8` = 3000 de vie
  (L9381).

`_do_computer_effect` (L9526-9597) choisit la cible : si l'aimant de la
tribu tombe sur un peep **adverse**, on vise sa case ; sinon on vise la case
du peep designe par `stats+0x26`, decalee de 3 en x et en y, sans descendre
sous zero.

#### Pourquoi ce n'est pas encore transpose

`_devil_effect` est ecrit dans notre convention (`.act` pour l'action,
`.tend` pour le masque), mais il **concurrence** notre `ai_choose` deja
fonctionnel et verifie. Le poser tel quel reviendrait a garder deux machines
de decision, dont une incomplete — c'est-a-dire a perdre les 68/68 sans
gagner la fidelite.

Le chantier propre est donc : **remplacer** `ai_choose` par la cascade, et
non l'ajouter. Cela demande de transcrire aussi `_set_devil_magnet`
(L9601) et `_one_block_flat` (L9148, 152 lignes), qui pose un batiment en
testant la moyenne d'altitude sur 4 cases et le reste modulo 4.

### Phase 15 - Bug majeur : la file d'actions ne se vidait jamais

Trouve en ecrivant `tools/stress.py` (nouveau : N graines x M tours, avec
verification d'invariants a chaque tour — vie <= `0x7D00`, `block` dans la
carte, `no_peeps <= 208`, `map_who` dans la table, mana >= plancher).

#### Le symptome

En suivant la trajectoire d'une partie, un chose saute aux yeux :

```
tour | peeps  popJ   popA
  0  |   2      45     45
400  |   2     289    289
1600 |   4    1758   1758
3200 |   4    3758   3758      <- la population grossit, plus personne ne nait
```

`no_peeps` plafonne a **4**. La population augmente sur place, mais plus
aucun habitant ne part fonder une nouvelle ville : la partie est figee.

#### La cause

`grow_peep` (asm L3841-3848) n'autorise une ville a **se scinder** — donc a
produire un nouvel habitant — que si l'action n'est pas deja en file :

.. code-block:: none

    if stats[t].queued != 0: goto suite      # TST.W (LAB_516AC) / BNE
    seuil = 0x131
    stats[t].queued = 1                     # MOVE.W #$0001,(LAB_516AC)

Or chez nous `Tribe.queued` etait **pose a 1 et jamais remis a 0** : le seul
endroit qui l'initialisait etait `__init__`. Des les premieres villes, le
verrou etait pose pour de bon.

Le vide est visible dans le listing : sur les dix-sept references a
`LAB_516AC` (offset `+8`), il n'y a qu'une seule ecriture a 1 (L12766) et une
seule remise a zero, a **L17951** :

.. code-block:: none

    if stats[t].can_build != 1: goto suite        # CMPI.W #$0001
    if game_turn / stats[t].period != 0: goto suite   # DIVU + SWAP + TST
    stats[t].queued = 0                            # CLR.W (LAB_516AC)

`stats+0x10` est bien notre :attr:`Tribe.period`.

#### Le correctif

`do_queued` vide maintenant la file une fois l'action consommee — c'est le sens
meme du champ (« une action est en file ») :

.. code-block:: none

    def do_queued(self, tribe):
        st = self.g.sim.stats[tribe]
        self.dispatch(tribe, st.act, st.p1, st.p2)
        st.act = ACT_NOP          # l'action a ete consommee
        st.queued = 0

#### Effet mesure

| | avant | apres |
|---|---|---|
| habitants au tour 3200 (graine 59) | **4** | **181** |
| population au tour 3200 | 3 758 | 87 981 |
| `no_peeps` final | 4 | 207 |

La chaine « ville se scinde -> l'habitant part -> il fonde une ville »Functionne
desormais. Les 68/68 tiennent, et `tools/stress.py` passe 8/8 sur 2000 tours
sans violer un seul invariant.

#### Un probleme d'equilibrage que cela revele

La croissance est maintenant **beaucoup trop rapide** : 2000 tours (~67 s de
jeu a 30 img/s) donnent 15 000 a 73 000 d'habitants et 44 a 155 peeps. Dans le
jeu original, on serait encore tres tot dans la partie. Trois causes possibles,
a instruire :

* le tableau `population_add` lu dans `land*.dat` — a verifier contre l'asm ;
* la seuil de scission `0x131` (305) : correct d'apres L3844, mais le
  partage `vie / 2` peut etre trop genereux ;
* `p.offspring < 4` : le nombre d'enfants par habitant, a confirmer.

C'est le prochain chantier de **calibrage**, distinct de la transcription.

### Phase 16 - La croissance : transcription exacte, et l'hypothese « rythme » REFUTEE

> **Correction de la Phase 16 v1.** J'y concluaisais que l'ecart venait de la
> base de temps (« un tour par vertical blank »). **C'est faux**, et la
> verification ci-dessous le refute. Le fond reste valable : la
> transcription est exacte. C'est la conclusion qui etait fausse.

Question posee en Phase 15 : la croissance trop rapide vient-elle d'une
erreur de transcription ou de l'equilibrage ?

#### 1. La scission — exacte

L3831-3851, le conditionnement complet :

.. code-block:: none

    if stats[t].can_build == 1:              # CMPI.W #$0001
        if peep->vie > 0x131:               # CMPI.W #$0131,(4,A0) / BLE
            if stats[t].queued == 0:         # TST.W (LAB_516AC) / BNE
                seuil = 0x131                # MOVE.W #$0131,(-12,A5)
                stats[t].queued = 1

puis le partage (L3904-3912) :

.. code-block:: none

    enfant.vie = parent.vie - (seuil >> 1)
    parent.vie = seuil >> 1

Identique a notre `grow_peep`. La population est **conservee** par la
scission : elle ne peut pas expliquer l'ecart.

#### 2. La porte des 8 tours — exacte, et elle gate aussi la population

L3819-3821 :

.. code-block:: none

    D0 = _game_turn ; D0 &= 7
    if D0 != 0: goto LAB_40F58      # BNE.W : saute tout le bloc

Point decisif : le saut d'exclusion arrive a `LAB_40F58`, c'est-a-dire
**apres** le `ADD.W D1,(4,A0)` de L4014 (`vie += population_add[age]`).
L'apport de population est donc lui aussi limite aux tours multiples de 8.
Notre `(game_turn & 7) == 0` qui enveloppe tout `grow_peep` est conforme.

#### 3. Le rythme — l'hypothese est refutee

J'ai cherche le ralentissement de la boucle de tour :

* `_move_peeps` (L681) est appele **sans divisieur**, une fois par passage,
  garde seulement par `_pause` et `_paint_map` (L676-679) ;
* le seul `Delay()` du jeu est dans `_free_inter` (L245), le chemin de
  sortie, et vaut 9 unites ;
* `_waitfor(n)` (L15278) attend bien `n` verticals blanks via `_vbi_timer`
  (incremente par la VBI, L19526) — mais son **unique appelant** est le
  chemin serie/login, avec `n = 0x4B = 75` (L11653). La boucle de jeu
  ne l'appelle pas.

Autrement dit la boucle **tourne librement**, son rythme etant borne par la
vitesse de rendu de la machine. Notre 30 img/s n'est donc pas 10x trop
rapide : c'est un ordre de grandeur plausible pour un Amiga logiciel.

**Conclusion : l'ecart de croissance n'est ni une erreur de transcription,
ni un probleme de base de temps.**

#### Ce qui reste a instruire

Les suspects restants, par ordre de probabilite :

1. **`check_life` et le `score`** — le seuil des villageois non-ville est
   `score`, et non `0x131`. Si notre `score` est trop eleve, les
   villageois se scindent trop tot. Verifier la formule de l'asm.
2. **la transition villageois -> ville** et la formule de l'age
   (`FRAME_AGE + score * 10 / 0x131`), qui indexe `population_add` et
   `mana_add` : un age faux decale toute la croissance.
3. **la population de depart** et le rythme des naissances : l'asm ajuste
   la population initiale selon le mode (`_place_first_people`, lignes
   7652-7686).

Aucun de ces trois n'a ete verifie. C'est le prochain chantier.

### Phase 17 - `check_life` : l'analyse de `bk2` ne devait pas avoir lieu

Le suspect le plus probable de la Phase 16 (`check_life` et le `score`)
l'etait. La routine est desormais transcrite et **verifiee**.

#### Le bug

`_check_life` (L20958-21042) analyse les 17 voisins. Le point de structure
que nous avions faux : **le bloc d'analyse de `bk2` (`LAB_4DDE8`) n'est
atteint que si `valid_move == 0`.**

.. code-block:: none

    pour k dans 17 voisins :
        r = valid_move(case, offset[k])
        si r != 0 :
            si r == 2 : score -= 15        # rocher, LAB_4DDAA
            goto LAB_4DE2A                 # <-- saute l analyse de bk2
        ...

L'eau (`r == 3`) et le hors-carte (`r == 1`)_sortent donc **avant**
`LAB_4DDE8`. Nous analysions `bk2` quand meme, et comme `bk2` vaut `0`
hors carte, la branche `elif k != 0 and 0x20 < d1 <= 0x2C` pouvait
declencher un `return 0` a tort.

Deux consequences, qui expliquent la croissance trop rapide :

1. un villageois **perdait son village** (`score <= 0` le renvoyait a
   l'etat explorateur) ;
2. et surtout, `threshold = score` dans `grow_peep` : un score artificiellement
   bas **baissait le seuil de scission**, donc les villageois se scindaient
   d'autant plus vite.

#### Le correctif

Le `continue` est place immediatement apres le traitement du rocher, et le
test du centre non constructible est rendu explicite :

.. code-block:: none

    if r != 0:
        if r == 2: score -= 0x0F
        continue                    # LAB_4DE2A, sans lire bk2
    nb = block + off
    if blk[nb] == $1F+tribu or blk[nb] == $0F:
        if score == 0: score = 0x32
        score += 0x0F
    elif k == 0:
        return 0                    # LAB_4DDA
    # LAB_4DDE8 : uniquement pour r == 0

#### Verifie

* **2000 cas random** (position, tribu, contenu de carte aleatoire)
  confrontes a une reecriture independante du listing : **identique**.
* Les 68/68 tiennent sur 7 graines, `check_render` OK, `smoke_sim` OK,
  `stress` 6/6.
* La croissance est divisee par deux en milieu de partie (graine 59) :

| tour | population avant | apres |
|---|---|---|
| 400 | 289 | **142** |
| 800 | 866 | **375** |
| 1600 | 6 442 | **2 306** |
| 2400 | 29 962 | **16 056** |

#### Ce qui reste trop rapide

Au tour 3200 on atteint encore 208 habitants — **le plafond `MAX_PEEPS`** — et
50 000 a 56 000 de population. Le correctif a donc bien reduit l'ecart, mais
pas supprime. Restent a instruire :

1. la transition villageois -> ville et le moment ou `FRAME_TOWN` est pose ;
2. la formule de l'age `FRAME_AGE + score * 10 / 0x131`, qui indexe
   `population_add` et `mana_add` ;
3. la population de depart (`_place_first_people`, lignes 7652-7686).

Aucun n'a ete verifie a ce jour.

### Phase 18 - Dernier suspect elimine, et ce que cela revele

La transition villageois -> ville (L3634-3666) :

.. code-block:: none

    if score >= 0x0BEA:                       # CMPI.W #$0bea / BLT LAB_40AA0
        good_towns[tribu] += 1               # ADDQ.W #1,(-40,A5)+tribu*2
        peep->frame = 0x2A                   # grande ville
        goto LAB_40ACE
    else:
        peep->frame = score * 10 / 0x131 + 0x20   # MULS #$000a / DIVS #$0131
        towns[tribu] += 1                    # ADDQ.W #1,(LAB_52DEA)+tribu*16
    age = peep->frame - 0x20                  # (-10,A5)

Exactement ce que nous faisions. Detail releve au passage : les deux
branches n'incrementent pas le **meme** compteur — la grande ville touche
`good_towns`, la ville normale `LAB_52DEA`. Nous n'en incrementons qu'un,
c'est un ecart de **statistique**, sans effet sur la croissance.

#### Bilan : toute la chaine de croissance est verifiee

| element | asm | verdict |
|---|---|---|
| scission | L3904-3912 | exact |
| porte des 8 tours | L3819-3821 | exact |
| `population_add` | L4008-4014 | exact |
| `check_life` | L20958-21042 | **corrige (Phase 17)** |
| transition -> ville | L3634-3666 | exact |
| formule de l'age | L3651-3654 | exact |
| rythme de la boucle | libre | 30 img/s plausible |

Sept elements controles, un seul etait faux. Apres le correctif de la
Phase 17, plus rien dans la chaine de croissance n'est connu comme errone.

#### Ce que cela revele

Du coup, l'ecart restant s'explique probablement **autrement** qu'on le
croyait : par la **comparaison entre tours et secondes reelles**.

Chez nous, un tour = une image a 30 img/s, donc 3200 tours = **107
secondes**. Or l'asm ne fixe **aucun** rythme a la boucle : elle tourne
liberement, bornee par la vitesse de rendu de la machine. Sur un Amiga
7 MHz qui rend en logiciel un ecran 320x256 avec la fenetre en 8 passes,
un rythme de **10 a 15 tours/s** est plausible — contre 30 chez nous.

A 10 tours/s, 3200 tours represente **5 minutes** de jeu : et la, atteindre
les 208 habitants du plafond et 50 000 de population n'a plus rien
d'anormal. Autrement dit une partie de notre port, lancee en conditions
reelles, est probablement **deux a trois fois trop rapide** — mais ce n'est
pas une erreur de transcription, c'est une question de **cadence**, et elle
se reglera sur une cible de tours par seconde choisie explicitement, puis
verifiee par execution.

.. warning::
   Ce raisonnement est une **hypothese** : la frequence reelle de la boucle
   d'origine n'est pas mesurable depuis le listing, puisque le jeu ne la
   fixe nulle part. Elle demande soit une mesure sur l'emulateur, soit un
   choix de conception assume. **Non tranche.**

### Phase 19 - L'interpretation materiel : le 68000 a des mots qui rebouclent

Le port se fait **fidele d'abord**. Cette phase traite la categorie que le
listing impose sans qu'on la voie : l'**interpretation materiel**.

#### Le defaut

Un `int` Python est de taille illimitée. Un registre du 68000 fait **16 ou 32
bits** et **reboucle**. Toute valeur calculee dans un registre reboucle donc a
zero en passant la borne.

C'est la source d'ecart la plus discrete du port : le code Python « fait
sens », donne les memes resultats sur les cas nomines, et **diverge des que
l'overflow est atteint**.

#### `populous/m68k.py`

Un module qui rend la borne explicite, avec la recette du listing a cote de
chaque primitive : `to_word`, `to_long_word`, `s16`, `s32`, `add_word`,
`add_long`, `test_word_eq_zero`, `cmp_word_ge` / `cmp_word_lt` (comparaisons
**signees**), `cmp_byte_ge` / `cmp_byte_le`, `mulu_word`, `divu_word`,
`divs_word`, `asr_word`, `asl_word`.

Deux conversions distinctes qu'il ne faut pas confondre :

* la **troncature** (`to_word`) : un mot lu dans un long ;
* l'**extension de signe** (`to_long_word`) : `MOVEA.L (8,A5),A0` et non
  `MOVEA.W` — un parametre passe en `char` se lit donc **en signe**.

#### Applique a `check_life`

L'accumulateur `D4` est un mot. Quatre rochers le font tomber sous zero ;
le 68000 le ramene a `0xFFC4`. Teste ensuite par `CMP.W #$0023 / BGE`, il
apparait **tres grand** — donc le seuil n'est jamais atteint, et le
villageois ne se scinde pas. En Python sans boucle, le score reste negatif :
le resultat **parait** correct et le verdict est **oppose**.

.. code-block:: none

    score = m68k.add_word(score, -0x0F)      # LAB_4DDAA : ADDI.W #$fff1
    if m68k.test_word_eq_zero(score): ...     # TST.W / BEQ
    if not m68k.cmp_word_ge(score, 0x23):     # CMP.W #$0023 / BGE
        score = 0
    return m68k.to_word(score)

Mesure : `0x32 - 4*0x0F` vaut `-10` en Python, et **`0xFFF6`** sur 68000.

*Verifie* : **3000 cas random** confrontes a une transcription independante
en arithmetique 16 bits → **identiques**. Les 68/68 tiennent, `smoke_sim` OK,
`stress` 5/5.

#### Ce qui reste a passer en 16 bits

Le module est pret ; il reste a l'appliquer aux autres accumulateurs. Par
ordre de risque :

| site | champ | risque |
|---|---|---|
| `grow_peep` L4014 | `vie` — `ADD.W` | reboucle a `0x10000` ; peu atteint en pratique, mais `bataille` et `battle_over` manipulent la vie directement |
| `move_peeps` L3308 | `mana` — `ADD.L` | reboucle a `0x100000000` ; tres lentement atteint |
| `_do_battle` | exchanging des vies | le plafond `0x7D00` est un mot : le depassement doit boucler |
| `Rng` | les tirages | le generateur de l'asm est lui-meme en arithmetique 16 bits |
| `_sculpt`, `check_life` deja fait | les scores de deplacement | idem |

Tant que ces sites ne sont pas convertis, **la portabilite 68000 du port
n'est pas etablie** — c'est le chantier ouvert.

### Phase 20 - Le generateur aleatoire : verifie, et les bornes posees

#### `Rng` — aucune divergence

C'etait le risque le plus grave : si la sequence des tirages s'ecartait,
**toute** la partie s'ecarterait, et aucun test ne l'aurait montre.

`_newrand` (L19129-19135) est deterministe et court :

.. code-block:: none

    MOVE.W _seed,D0      # le mot haut de D0 reste indetermine...
    MULU #$24a1,D0       # ...mais MULU ne lit que le mot BAS -> 32 bits
    ADDI.W #$24df,D0     # mot bas seul
    BCLR #$F,D0          # bit 15
    MOVE.W D0,_seed
    RTS

*Verifie* : **120 000 tirages** (20 000 x 6 graines, dont 0x0000, 0x7FFF,
0xFFFF) confrontes a une reecriture independante → **zero ecart**. Le mot
haut de `D0` est bien preserve, et le bit 15 est bien toujours efface.

Le risque « tout diverge des la premiere graine » est **ecarte**.

#### Les bornes 16 et 32 bits, posees

Trois sites convertis a `m68k` :

| site | asm | type |
|---|---|---|
| mana, 1 par 2 tours | L3308 `ADDQ.W` sur un champ **long** | `add_long` |
| mana, par age | L3876 `ADD.L D1,(A0)` | `add_long` |
| vie, par age | L4014 `ADD.W D1,(4,A0)` | `add_word` |

**Mesure : en jeu normal, aucune borne n'est atteinte.**

| grandeur | maximum atteint | borne |
|---|---|---|
| vie d'un peep | 3 508 | 65 535 |
| mana d'une tribu | 23 527 | 4 294 967 295 |

Autrement dit ces conversions sont **correctes mais sans effet aujourd'hui** :
elles compte sur les parties tres longues, ou si l'equilibrage change. C'est
exactement ce qu'on veut — la fidelite d'abord, l'effet quand il y en a un.

Le reboulement a ete verifie en le forçant : vie `65530 + 10 = 4`, mana
`0xFFFFFFFC + 8 = 4`. Et aucune depasse le plafond de `0x7D00` apres 2500
tours de combat.

*Suite* : 68/68 sur 7 graines, `check_render` OK, `smoke_sim` OK, `stress` 5/5.

### Phase 21 - `_do_battle` : le reboulement et le test de mort

#### Ce que le listing dit vraiment

`do_battle` (L6066-6181) calcule deux jets, puis une soustraction par
combattant. La formule est **verifiee** :

.. code-block:: none

    jet1 = (tirage/3 + 1) * vie_A        # (-6,A5)
    jet2 = (tirage/3 + 1) * vie_B        # (-10,A5)
    degats = armes * (jet / 100) + 10
    vie -= degats                         # SUB.W

L'ordre des operandes de `___divs` etait **non verifie** depuis le debut du
port. Il est tranche : `_divs` (L23385) negue D0 puis D1, donc
`divs(D0, D1) = D0 / D1`. Notre formule `armes * (vie/100) + 10` est donc
**juste**. Et `_mulu` (L22892) fait le produit 32x32 attendu.

#### Deux ecarts 68k corriges

**1. La soustraction reboucle.**

`SUB.W D0,(4,A0)` ecrit un D0 long dans un champ **mot** : seul le bas de
D0 part, et le resultat reboucle a `0x10000`. Une vie qui passe sous zero
vaut `0xFFxx`, pas un entier negatif.

**2. Le test de mort est en signe — et c'est le pire des deux.**

L6167-6171 teste `TST.W (4,A0) / BGT`. Or `TST` ne pose que le bit N : `BGT`
y teste donc le **signe**, pas la nullite. Une vie reboulee a `0xFFF0` a le
bit 15 pose, `BGT` ne passe pas → elle est comptee comme **morte**.

Notre `<= 0` la comptait **vivante**. L'ecart est completement inverse, et
il ne se voit que parce que le reboulement est pose — sans lui, les deux
versions « paraissent » correctes.

.. code-block:: none

    opp.life = m68k.add_word(opp.life, -(atk.weapons * (low // 100) + 10))
    atk_dead = not m68k.cmp_word_gt(atk.life, 0)   # TST.W / BGT

*Verifie* : les six cas de test (0, 1, 100, 0x8000, 0xFFF0, 0xFFFF) ; reboulement
force (`100 - 150 = 0xFFCE`) ; et sur 3 graines apres 2500 tours de combat,
**aucune vie ne survit avec le bit 15 pose**, toutes restent dans `0..0x7FFF`.

#### Decouverte : l'asm est asymetrique, nous ne le sommes pas

En relisant les deux branches, elles ne sont pas miroir :

| branche | condition | cible 1 | cible 2 |
|---|---|---|---|
| L6105-6130 | `jet1 > jet2` | **A** (A0=`(8,A5)`) | **A** encore (A0=`(8,A5)`) |
| L6133-6158 | sinon | **A** | **a** (A0=`(-16,A5)`) |

ou `a = &peeps[A->index]`, c'est-a-dire l'entree canonique du meme peep. Donc
dans la premiere branche, **les deux soustractions visent le meme peep**, avec
`A->weapons` puis `a->weapons` — deux fois sur le meme.

C'est soit un defaut de l'original, soit un artefact du listing. Notre
version applique `min(jet_A, jet_B)` aux deux combattants : c'est une
**symetrie de notre invention**, pas de l'asm.

**Consequence** : `do_battle` porte un marqueur `[APPROX]` de plus. Il ne
suffit pas d'appliquer le `min` de l'asm — il faut choisir laquelle des deux
branches on transcrit, et c'est un arbitrage de portabilite, pas de lecture.
La formule etant verifiee, l'erreur porte sur la **repartition** des degats,
donc sur l'issue des combats serres, pas sur leur existence.

#### Suite

68/68 sur 7 graines, `check_render` OK, `check_assets` OK, `smoke_sim` OK,
`stress` 5/5.

### Phase 22 - `_do_battle` : deux erreurs de lecture, corrigees

Cette phase corrige l'analyse de la phase 21 — qui etait **fausse** — puis le
code. Les deux erreurs se tiennent, et c'est en les enchainant qu'on les a
trouvees.

#### Erreur 1 : le `if/else` n'est pas une dissymetrie

.. code-block:: none

    L6103: CMP.L (-10,A5),D0     # compare jet1 a jet2
    L6104: BLE.S LAB_4275E       # jet1 <= jet2 -> branche 2, qui utilise jet1
                                # jet1 >  jet2 -> branche 1, qui utilise jet2

Les deux branches n'emploient **que le plus petit des deux jets**. Le
`if/else` est un simple **selecteur de minimum**. Notre `min(...)` etait donc
juste, et l'arbitrage « quelle branche ? » etait sans objet — les deux donnent
le meme resultat.

#### Erreur 2 : `a` n'est pas le meme peep

L6071-6073 calcule `a = _peeps + A->index * $16`. J'avais lu l'offset 6 comme
l'index du peep lui-meme, et conclu `a == A`, donc « un seul combattant,_degat
double ».

**L'offset 6 est `w6`, l'index de l'adversaire.** Donc `a = &peeps[A->w6]` est
l'**adversaire**, et `a != A`.

Le test qui tranche : `_battle_over` n'est appele que de L6189 et L6199, tous
deux dans `_do_battle`. Sous `a == A`, les deux sont **inatteignables** — un
peep mort passe par `zero_population`, un peep vivant sort par `RTS`. On
n'aurait donc jamais de mana de combat ni de ruines. Or le jeu original montre
des ruines. `a != A` est donc impose par le listing.

#### Le vrai ecart, et la correction

.. code-block:: none

    L6084-6090: jet1 = (tirage/3 + 1) * a->vie      # L6099-6100 : idem
    L6094-6101: jet2 = (tirage/3 + 1) * a->vie      # sur a, encore

Les **deux** jets sont bastis sur la vie de **`a`**, c'est-a-dire de
l'adversaire — **pas une vie par combattant**. C'etait notre erreur.

Nos degats, eux, etaient deja justes : l'adversaire subit les armes de `A`,
et `A` subit les armes de l'adversaire. Les deux branches echangent ces deux
ecritures sans plus changer le jeu de valeurs.

.. code-block:: none

    jet1 = (self.rng.below(3) + 1) * opp.life
    jet2 = (self.rng.below(3) + 1) * opp.life
    low = jet2 if jet1 > jet2 else jet1

Le nombre de tirages reste de deux : la **sequence du Rng n'est pas decalee**,
seule la valeur du minimum change.

#### Effet mesure

| graine | pop J avant | pop J apres |
|---|---|---|
| 1 | 47 108 | **23 168** |
| 59 | 45 926 | **20 090** |
| 314 | 18 032 | **7 082** |

La population chute de moitie. L'explication est directe : contre un
adversaire a **forte** vie, les deux jets sont forts et le degat aussi ; contre
un adversaire a **faible** vie, les deux jets sont faibles et le coup ne fait
presque rien. Avant, le `min` melangeait une vie forte et une vie faible, donc
le minimum tenait toujours le petit bout — les coups etaient toujours
moderes. Le combat devient **brut par paliers** au lieu d'etre uniforme.

C'est un changement de comportement, pas un ajustement : c'est ce que le
listing impose. L'equilibrage se reglage plus tard, sur un port deja fidel.

*Suite* : 68/68 sur 7 graines, `check_render` OK, `check_assets` OK,
`smoke_sim` OK, `stress` 5/5. Aucune vie ne survit avec le bit 15 pose.

### Phase 23 - `_sculpt` : un garde manquant, et des bornes posees

#### Le vrai ecart : L7307-7312 n'existait pas chez nous

Entre le controle de zone (L7295-7306) et le calcul de la diagonale (L7317),
le listing a un garde que notre port sautait :

.. code-block:: none

    L7307: TST.W   _ok_to_build / BNE  -> poursuivre
    L7309: CMPI.W  #2,_mode     / BNE  -> poursuivre
    L7311: TST.W   _paint_map   / BNE  -> poursuivre
    L7313: LAB_43588: D0 = 0 ; RTS        -> sinon, rendre la main

On ne poursuit que si **l'une** des trois est vraie. Autrement dit : en mode
peinture de carte (``_mode == 2``) sans `_ok_to_build`, la souris ne designe
**aucune** case. Notre port en designait une quand meme.

Les deux variables existaient deja chez nous (``sim.py`` L134 et L154) mais le
garde n'etait pas pose — le genre d'ecart que seule la relecture du listing
 revele, parce que les deux morceaux etaient presents et leur liaison absente.

*Verifie* sur les **cinq** combinaisons, a une position ou `sculpt` aboutit
(mode 1) :

| mode | ok_to_build | paint_map | obtenu | attendu |
|---|---|---|---|---|
| 1 | 0 | 0 | designates | designe |
| 2 | 1 | 0 | designe | designe |
| 2 | 0 | 1 | designe | designe |
| 2 | 0 | 0 | **rien** | **rien** |
| 3 | 0 | 0 | designe | designe |

#### Les bornes 16 bits, posees

`_sculpt` manipule cinq accumulateurs en **mot** : ``base`` (L7321-7324,
`MULS #$0041` + `ADD.W`), ``step`` (L7337-7338, `ASL.W #3` + `ADD.W`), l'indice
dans `_alt` (L7364-7368) et la soustraction d'altitude (L7370-7373).

Le point le pluspiege est L7364-7368 :

.. code-block:: none

    MOVE.W D6,D1 / MULS #$0042,D1 / ADD.W (-30,A5),D1
    EXT.L  D1                          <-- etend le SIGNE
    MOVE.W (_alt,A4,D1.L),D2

Un `base` reboulee avec le bit 15 pose donne un indice **negatif**, et le
68000 lit `_alt` **avant** le tableau. Notre ancien `k % n_alt` etait un
garde-fou de notre invention, entierement different.

**Mesure : aucune borne n'est atteinte.** `base` plafonne a `yoff*65 + xoff +
8*66 = 3168`, tres loin de `65535`. Ces conversions sont donc **correctes sans
effet** — meme constat que Phase 20 : le port est petit devant le 68000. On les
garde parce qu'elles rendent le code exact par construction, pas pour l'effet.

*Verifie* : **4000 positions** de souris confrontes a une reecriture
independante en arithmetique 16 bits → **identique**. 68/68 sur 7 graines,
`check_render` OK, `check_assets` OK, `smoke_sim` OK, `stress` 5/5.

#### Decouverte annexe : `_ok_to_build` est un drapeau collant

`grep` sur le listing : `_ok_to_build` n'est ecrit qu'a deux endroits —

* L613 `CLR.W _ok_to_build` (initialisation), et
* L15981 **`OR.W D6,_ok_to_build`** (jamais un effacement).

ou `D6` vient de `(0,A2)` bits OR a 1 si la tribu du message est `_player` et
que `(0x12,A2) != 0`. Le drapeau est donc **pose une fois et jamais repris** :
des la reception d'un message autorisant a batir, le garde du mode 2 s'ouvre
pour le reste de la session.

Chez nous `ok_to_build` reste a 0 en permanence : le mode 2 ne pourra donc
jamais designer de case tant que le gestionnaire de messages n'est pas
transcrit. C'est le prochain morceau, et il conditionne ce garde.

### Phase 24 - `_ok_to_build` : le drapeau collant, enfin alimente

La Phase 23 laissait un garde corrige mais **immuable** : `ok_to_build` restait
a 0, donc le mode 2 ne designait jamais de case. Voici d'ou il vient.

#### Le producer du drapeau

Le label `_move_sprite` est trompeur — c'est la boucle par peep de
`move_peeps`. En tete de corps (L15968-15981) :

.. code-block:: none

    MOVE.B  (0,A2),D6 / ANDI.W #$00f8,D6      # etat & 0xF8
    MOVE.B  (1,A2),D7 / EXT.W D7              # tribu, en signe
    CMP.W   _player,D7 / BNE LAB_49C2C
    TST.W   ($12,A2)   / BEQ LAB_49C2C        # champ +0x12
    ORI.W   #$0001,D6
LAB_49C2C:
    CMPI.W  #$00d1,(A7)+ / BGE LAB_49C38      # index-1 >= 209 -> on saute
    OR.W    D6,_ok_to_build

Trois lectures, et chacune elimine une piste :

**Le champ `+0x12` ne sert a rien ici.** C'est notre `t12`, et `grep` sur tout
le port montre qu'il **n'est ecrit nulle part** : il reste nul. Le `BEQ` est
donc toujours pris et le `ORI.W #$0001` de L15977 **n'est jamais execute**. Le
bit 0 n'entre donc pas dans le drapeau.

**Le test sur la tribu n filtre rien**, puisque le `ORI.W #1` est mort : D6
reste `etat & 0xF8` que le peep soit au joueur ou non.

**Le `CMPI.W #$00d1` n'ecarte rien** : il porte sur `index - 1`, et nos peeps
s'arretent a 208 (`no_peeps` = 0xD0).

Il ne reste donc qu'une seule regle, posee en tete de la boucle par peep :

.. code-block:: none

    ok_to_build |= peep.state & 0xF8

et elle est **collante** : `CLR.W` une seule fois a l'initialisation (L613),
jamais effacee ensuite. Le seul test est `TST.W / BNE` — il suffit qu'un
seul peep porte son etat hors des huit bits bas.

#### Ce que ca donne, et c'est signifiant

| etat | valeur | `& 0xF8` | contribue |
|---|---|---|---|
| `ST_EXPLORER` | 0x02 | 0x00 | non |
| `ST_BATTLE` | 0x08 | 0x08 | **oui** |
| `ST_DROWNING` | 0x10 | 0x10 | **oui** |

Sur 3 000 tours :

| graine | etat max | drapeau final | s'ouvre au tour |
|---|---|---|---|
| 1 | 0x02 | 0x00 | jamais |
| 59 | 0x22 | **0x20** | **2 162** |
| 314 | 0x02 | 0x00 | jamais |

Le garde du mode 2 s'ouvre donc **quand la tribu entre en combat ou se noie**,
et seulement alors. Ce n'est pas une autorisation de batir au sens d'un
message : c'est un temoin de l'etat des unites. Le port le reproduit
maintenant, et les graines sans combat le garde ferme — ce qui est coherent.

*Invariant verifie* : sur 1 500 tours, **aucune descente** du drapeau. Un
`OR.W` ne peut pas redescendre, et c'est bien ce qu'on observe.

#### Ce que ca ne change pas

Aucune des 7 graines de reference ne teste le mode 2 : `68/68` partout,
`check_render` OK, `check_assets` OK, `smoke_sim` OK, `stress` 5/5. Le gain
est de fidelite, pas de rendement.

### Phase 25 - `_one_block_flat` : le noop de l'IA remplace par le listing

Premier morceau de l'IA. C'etait un `return None` avec le marqueur
`[APPROX]` ; la routine fait 149 lignes de listing et **decide reellement**
quand l'IA touche le terrain.

#### Les cinq portes d'entree

.. code-block:: none

    TST.W  (8,A0)                    / BNE   queued != 0
    CMPI.L #$14,(LAB_52DF0+t*16)     / BLT   mana < 20
    CMPI.W #$32,(LAB_52DEA+t*16)     / BGT   mot haut de pop
    BTST   #0,($F,A0)                / BEQ   bit 8 du masque
    BTST   #2,LAB_518A7              / BEQ   drapeau global

Deux lectures qui ne vont pas de soi :

**`BTST #0,($F,A0)`** lit le bit 0 de l'**octet +0x0F**, donc le bit **8** du
mot `+0x0E` — pas son bit 0. C'est `power_mask & 0x100`. C'est le second cas
du projet ou un offset d'octet au lieu d'un offset de mot change tout.

**`LAB_52DEA` n'est pas un champ** : c'est le **mot haut de `pop`** (long a
+8). Il ne depasse jamais `$32`, donc cette porte est **inerte**. On l'ecrit
quand meme, fidelement — c'est gratuit, et ca garantit le resultat si la
representation change.

#### Le `SWAP` qui change tout

.. code-block:: none

    DIVS #$4,D0 / SWAP D0 / MOVE.W D0,(-6,A5)    ->  (-6,A5) = le RESTE
    DIVS #$4,D0 /         MOVE.W D0,(-8,A5)      ->  (-8,A5) = le QUOTIENT

`DIVS` laisse le quotient en D0.W et le **reste en D1.W**. Apres le `SWAP`, le
mot bas de D0 n'est donc plus le quotient mais le reste. Le parametre qui
choisit l'intention de la routine est `s % 4`, pas `s // 4`. Or `s % 4` ne
prend que les valeurs 0, 1, 2, 3 — et seules **1 et 3** agissent :

| reste | intention | condition |
|---|---|---|
| 3 | poser un arbre, `act = 1` | altitude **egale** au quotient |
| 1 | creuser, `act = 2` | altitude **au-dessus** du quotient, et `LAB_518A7 & 8` nul |
| 0, 2 | rien | — |

La double boucle porte sur les quatre cases voisines (`x`, `x+1` × `y`,
`y+1`), mais le test d'altitude se fait toujours sur `y * $41 + x` : sur la
**case**, pas sur le sommet.

#### Les bornes

La somme des quatre sommets est un `ADD.W` a repetition, et l'offset passe par
`EXT.L` — donc l'indice est **en signe**, et une valeur reboulee avec le bit 15
pose lit `_alt` **avant** le tableau. Aucun modulo n'a ete ajoute : ce serait
notre invention, comme le `k % n_alt` corrige en Phase 23.

*Verifie* : les quatre portes une par une, puis **3000 couples (tribu, case)**
confrontes a une reecriture independante → **identique**, 227 actions emises
sur 3000 appels.

*Suite* : 68/68 sur 7 graines, `check_render` OK, `check_assets` OK,
`smoke_sim` OK, `stress` 5/5.

#### Reste de l'IA

`_devil_effect` (L9300, ~300 l.) et `_set_devil_magnet` (L9601) ne sont pas
transcrits. C'est la que se trouvent les seuils de mana releves tot :

.. code-block:: none

    tremblement 80999   inondation 41999   aimant 8000
    effetVpc 10500      effetPc 3000       attaque 5500

Aucun de ces nombres n'entre dans le port. Tant que `_devil_effect` n'est pas
transcrit, `ai_choose` reste une invention.

### Phase 26 - `_devil_effect` : analyse complete, et une correction

`_devil_effect` va de L9300 a L9522 — **223 lignes**, pas les 300 estimees.
Lue integralement. Cette phase rend l'analyse ; l'implementation est
reportee parce qu'elle ne peut pas etre isolee (voir plus bas).

#### Correction : `LAB_52DEA` n'est pas le mot haut de `pop`

La Phase 23 affirmait que cette porte etait **inerte**. C'etait faux, et la
faute vient de la disposition memoire :

.. code-block:: none

    52DE4  +0    magnet
    52DE6  +2    magnet_to
    52DE8  +4    command
    52DEA  +6    town_count     <-- le champ teste
    52DEC  +8    good_pop
    52DF0  +12   mana

`good_pop` occupe bien +8 — mais `LAB_52DEA` est **+6**, donc `town_count`. La
porte est **vivante** : des que la tribu compte plus de `$32` villes,
`_one_block_flat` sort. Corrige dans le code.

#### Les seuils sont des variables, pas des constantes

Les six seuils sont `LAB_518x x + une constante`, jamais une valeur fixe :

| variable | champ | + delta | valeur initiale |
|---|---|---|---|
| `LAB_51894` | `mana` | `+0x3E7` | 80 000 → **80 999** (tremblement) |
| `LAB_51890` | `mana` | `+0x7CF` | 40 000 → **41 999** (inondation) |
| `LAB_51888` | `mana` | `+0x1F4` | 7 500 → **8 000** (aimant) |
| `LAB_5188C` | `mana` | `+0x1F4` | 10 000 → **10 500** (effet Vpc) |
| `LAB_51884` | `mana` | `+0x1F4` | 2 500 → **3 000** (effet Pc) |
| `LAB_51880` | `mana` | `+0x1F4` | 5 000 → **5 500** (attaque) |

Les valeurs initiales sont exactement des entrees de `_mana_values` — les
**indices 4, 3, 5, 6, 7 et 8**. Les deltas (`$1F4` = 500, `$7CF` = 1999,
`$3E7` = 999) sont separes, et variables : Conquest les modifie. Il faudra
donc des attributs mutables, pas des constantes codees en dur.

#### Les bits testes, et d'ou vient la legerie

Le masque est le mot `+0x0E`. Il est copie dans `(-6,A5)` (octet bas) et
`(-5,A5)` (octet haut), donc les `BTST` visent :

| instruction | bit reel | pouvoir |
|---|---|---|
| `BTST #0,(-6,A5)` | 0 | tremblement de terre |
| `BTST #7,(-5,A5)` | 15 | inondation |
| `BTST #5,(-5,A5)` | 13 | aimant |
| `BTST #6,(-5,A5)` | 14 | effet Vpc |
| `BTST #4,(-5,A5)` | 12 | effet Pc |
| `BTST #3,(-5,A5)` | 11 | attaque |

et deux `AND.W #$0050` sur l'octet bas (bits 4 et 6).

#### Decouverte : l'action `act = 4` est du code mort

Le bloc `LAB_44F90` (L9476-9491) doit poser un arbre (`act = 4`). Il est
**inatteignable**. Voici pourquoi :

.. code-block:: none

    L9452-9455:  _magnet[tribu] - 1  ->  (-2,A5)
    L9459-9462:  _magnet[tribu] - 1  ->  (-4,A5)     <-- la meme valeur

Les deux variables recoivent **exactement la meme chose**. Puis :

.. code-block:: none

    L9463: CMPI.W #$ffff,(-2,A5) / BEQ LAB_44FCA
    L9466: CMPI.W #$ffff,(-4,A5) / BEQ LAB_44F90
    L9467: LAB_53018[(-2,A5)*$16] / L9474: CMP.W avec LAB_53018[(-4,A5)*$16]

`LAB_53018` est `_peeps + 4`, c'est-a-dire la **vie** des peeps. On compare
donc `vie[n]` a `vie[n]` : toujours egal, donc `BLE` est toujours pris et
`LAB_44FCA` est toujours atteint. Le seul chemin vers `LAB_44F90` exigeait
`(-4,A5) == $FFFF` et `(-2,A5) != $FFFF` — impossible.

Autrement dit : **l'IA ne releve jamais le terrain elle-meme**. Le `t12 += 1`
de L9477 est donc lui aussi mort, et le compteur `t12` n'est incremente que
par le chemin `LAB_4500E` (L9520), le vrai effet informatique. `CLR.W ($12,A2)`
de L9417 le remet a zero dans l'autre branche.

#### Pourquoi l'implementation est reportee

`_devil_effect` appelle `_do_computer_effect` (L9526) pour `act = 3` et
`act = 6`. Cette routine est **aussi** necessaire, et elle n'est pas encore
lue. Transcrire la moitie d'un enonce ne rend pas le resultat plus fidele :
`ai_choose` resterait un mélange du listing et d'une approximation, et c'est
exactement ce que la Phase 25 a supprime.

Il faut donc traiter `_devil_effect` + `_do_computer_effect` +
`_set_devil_magnet` (L9601) comme **un seul morceau**, puis brancher
`ai_choose` dessus en supprimant l'heuristique. C'est le prochain chantier.

### Phase 27 - On change de methode : transcrire d abord, comprendre ensuite

Jusqu'ici le processus etait : **comprendre une routine, la transcrire, la
documenter, passer a la suivante.** Cette phase inverse l'ordre, pour une
raison qu'il faut ecrire noir sur blanc.

#### Pourquoi

Les trois erreurs de lecture de ce port etaient toutes du meme genre :

| erreur | genre |
|---|---|
| `min()` au lieu du selecteur de minimum | interpretation |
| `a == A` au lieu de `a` = adversaire | interpretation |
| `LAB_52DEA` = mot haut de `pop` | interpretation |

**Aucune n'est une erreur de transcription.** Toutes viennent d'avoir infere
l'intention au lieu de copier la structure. `CMP`/`BLE`, `MULS #$0016`,
`LAB_52DEA = +6` : tout y etait ecrit, noir sur blanc. Une transcription
**mecanique** — sans interpretation, juste la structure — les aurait eues
justes du premier coup.

Le risque d'une transcription mecanique est qu'elle n'a pas d'oracle. Elle en
a un ici : `autopilot.py` (68 controles), `stress.py`, `smoke_sim.py`. Une
version mecanique se valide par « les tests tiennent », et quand un test
casse, elle dit quelle ligne. Ce qui manquait jusqu'ici, c'était precisement
cette base de comparaison.

#### Le chiffre qu'on n'avait jamais mesure

Les marqueurs `[APPROX]` ne disent rien de la couverture : ils sont ecrits la
ou nous avons regarde, donc la ou nous avons doute. **Une routine jamais lue
n'a aucun marqueur** — non parce qu'elle est correcte, mais parce que personne
ne l'a visitee.

.. code-block:: none

    python tools\coverage.py            # resume
    python tools\coverage.py --top 40   # les plus grosses non couvertes
    python tools\coverage.py --holes    # les trous « lines cut »

.. code-block:: none

    routines _xxx:         : 564
      dont lignes de code  : 21602

    COUVERTURE REELLE      : 173 / 564  (30.7%)
      par alias declare    : 13
      par citation de nom  : 160
      analysees, a coder   : 3
      NON couvertes        : 388

**Un tiers du listing.** Et la liste des plus grosses routines non couvertes
n'est pas une liste de restes :

.. code-block:: none

    _do_action          640 l.   _two_players       621 l.
    _move_magnet_peeps  560 l.   _game_options      540 l.
    _show_world         517 l.   _save_load         490 l.
    _animate            475 l.   _end_game          399 l.
    _won_conquest       316 l.   _place_first_people 205 l.

`_move_magnet_peeps`, `place_first_people`, `_show_world` sont du jeu. Le
port les remplace par quelque chose qui marche, sans que rien ne dise que
ce n'est pas la meme chose.

#### Les trous du listing

Six routines contiennent un « lines cut », et le listing ne les comble pas :

.. code-block:: none

    _move_peeps     L3245   1138 l.   [citee]
    _sculpt         L7271    289 l.   [alias]
    _do_place_funny L8862    148 l.   [alias]
    _end_game      L14019    399 l.   [non couverte]
    _read_back_scr L16359     36 l.   [non couverte]
    _load_ground   L16468    152 l.   [non couverte]

Une transcription mecanique bute sur chacun. Il faut une regle de traitement
par trou — ce qui est du travail d'analyse, pas du travail de copie.

#### L'outil a deja attrape une incoherence

Au premier lancement, il a signale **deux alias casses** :

.. code-block:: none

    !! ALIAS CASSE : 2  (le symbole Python a disparu)
         _devil_effect -> Game.devil_effect
         _set_devil_magnet -> Game.set_devil_magnet

C'etait exact : la Phase 26 a **analyse** ces routines sans les transcrire, et
le port les declarait quand meme couvertes. Une routine analysee qui passe
pour transcrite est precisement le piege que `[APPROX]` ne voit pas. D'ou la
liste `PLANIFIE`, qui distingue les deux et les compte a part.

#### Le nouveau processus

1. **transcrire mecaniquement** une routine, sans l'interpret ;
2. **verifier par execution** (autopilot, stress) ;
3. **reporter l'alias** dans `tools/coverage.py` ;
4. **comprendre** ensuite, et seulement si une reecriture ameliore la
   lisibilite — en gardant la version mecanique pour diff.

La couverture devient une cible qu'on surveille, pas un chiffre qu'on oublie.

### Phase 28 - `_move_magnet_peeps` : structure relevee, et un ecart de type

560 lignes de code, non couvertes (`tools\coverage.py`). Relection des
2 premiers blocs sur 8. La transcription n'est pas faite — mais deux
constats meritaient d etre ecrits avant, parce qu'ils changent la maniere
de la transcrire.

#### Le gradient : un idiome repete, pas une soustraction

Le calcul de la direction vers la cible est ecrit partout sous cette forme :

.. code-block:: none

    TST.W  D1 / BLE.S  -> D0 = 0        (4949-4954)
             sinon      -> D0 = 1
    TST.W  D1 / BGE.S  -> D1 = 0        (4956-4961)
             sinon      -> D1 = 1
    SUB.W  D1,D0                        (4963)

soit exactement ``(D1 > 0) - (D1 < 0)``, c'est-a-dire un **``sign``**. Le
motif revient des dizaines de fois dans la routine — pour l'aimant
(`LAB_52DE6`) comme pour la cible designee. Une transcription litterale
ecrirait quarante fois ces douze lignes ; une transcription qui « comprend »
ecrirait ``sign()``. Les deux sont correctes, mais la seconde ne peut pas
ete verifiee sans le coup d'oeil d'origine. On l'ecrira avec ``sign`` et on
la gardera en regard du listing.

Resultat :

.. code-block:: none

    (-6,A5) = sign((LAB_52DE6[tribu] & $3F) - (A2->block & $3F))
    (-8,A5) = sign((LAB_52DE6[tribu] >> 6) - (A2->block >> 6))

soit `magnet_to - block`, case par case, coordonnee par coordonnee.

#### Ecart de representation : `peeps[0x0E]` est un POINTEUR

L4914 dereference le champ :

.. code-block:: none

    MOVEA.L ($E,A2),A0      ; A2->0x0E, un LONG
    MOVE.W  (8,A0),D0       ; -> la case de la cible
    MOVE.W  (4,A0),D0       ; -> sa vie
    MOVE.B  (1,A0),D0       ; -> sa tribu
    MOVE.B  (A0),D0         ; -> son etat

Chez nous, ``Peep.target`` est un **indice** :

.. code-block:: none

    self.target = -1        # index du peep vise, -1 = aucun (0 dans le jeu)

Les tests booléens coincident — `0` dans l'asm, `-1` chez nous, meme
signification. Mais **nous ne dereferenceons jamais**. Concretement, le
gradient est calcule vers `magnet_to` chez nous, alors que le listing le
calcule vers **la position de la cible designee**, lue dans le peep vise.

C'est donc un ecart de **type**, pas de logique : la meme information ne peut
pas etre lue de la meme facon. Deux options, et il faut trancher :

* garder l'indice et ajouter une resolution `peeps[target]` la ou le listing
  fait `A0 = peeps[0x0E]` — fidele, mais notre `-1` doit se comporter comme le
  pointeur nul `0` de l'asm ;
* ou modelede la cible par son index comme le fait le listing pour `block`,
  ce qui suppose de relire les 9 dereferencements et de verifier qu'ils
  donnaient la meme case.

C'est une decision de portabilite, pas de lecture : les deux sont defendables.

#### Deux mecanismes reveals au passage

**La conversion en aimant** (`LAB_41AF4`, L5009) : quand la cible atteint la
case visee, le peep est reattribue —

.. code-block:: none

    MOVE.B (-13,A5),(1,A2)   ; 1 = tribu, et (-13,A5) vaut 0 ou $FF

`(-13,A5)` est l'octet haut du mot ou L4910 avait range la tribu. Donc la
tribu du peep devient **0 ou 255** — pas 1. Le port n'a rien de comparable.

**`_view_who`** (L5003-5007) : si la vue est sur personne (`_view_who == 0`),
elle est forcee sur la cible. Petit detail d'affichage, mais il est dans le
listing.

#### Ce qu il reste a lire

7 blocs sur 8, et surtout `_get_heading` (L5028, lui aussi non couvert), que
cette routine appelle. La transcription doit donc etre un morceau unique
`_move_magnet_peeps` + `_get_heading`, comme `_devil_effect` +
`_do_computer_effect`. C est aussi la premiere fois qu un ecart de **type de
donnees** et non de logique impose un arbitrage : c est ce qui rend le
travail interessant, et ce que la Phase 23 avait montre sur les doors.

### Phase 29 - `peeps[0x0E]` : l'indice est sur, et voila pourquoi

La Phase 28 posait une condition a l'arbitrage « garder l'indice » : verifier
qui ecrit `0x0E`. La verification est faite, et elle est **favorable**.

#### Quatre ecritures, pas une de plus

.. code-block:: none

    L5480:  MOVE.L A2,($E,A2)     ; auto-reference
    L5527:  MOVE.L A3,($E,A2)
    L19874: MOVE.W D0,($E,A0)     ; sur un MOT, pas un long
    L19885: MOVE.W D0,($E,A0)

Quatre dans tout le listing. Trois consequences :

* **Aucune ne depend de la position.** Un pointeur ne « suit » donc pas un
  deplacement du peep vise — et un indice non plus. Les deux representations
  se comportent identiquement.

* **Les 22 octets d'un peep ne bougent jamais** en memoire. Un pointeur ne
  pendille donc pas davantage qu'un indice ; il devient invalide quand le
  emplacement est reutilise, ce qui arrive dans les deux cas.

* Nous remettons `target` a `-1` dans `zero_population` (`sim.py` L417) et a
  la naissance (L836), donc le recyclage est propre.

L'arbitrage de la Phase 28 est donc **valide**, et pour une raison objective
et non par preference.

#### L'auto-reference est le sentinelle « arrive »

L5480 ecrit ``MOVE.L A2,($E,A2)`` : le peep se designe **lui-meme**. Ce n'est
pas une bogue, c'est le marqueur d'arrivee. En effet L4914-4917 :

.. code-block:: none

    MOVEA.L ($E,A2),A0
    MOVE.W  (8,A0),D0        ; la case de la cible
    CMP.W   (8,A2),D0        ; ... egale a la mienne ?
    BEQ.S   LAB_41A26        ; oui -> calculer un CAP, pas un gradient

Quand la cible est le peep lui-meme, la comparaison est trivialement vraie, et
la routine calcule un cap au lieu de suivre un gradient. Les trois etats du
champ sont donc :

| asm | ici | sens |
|---|---|---|
| `0` (pointeur nul) | `-1` | suit l'aimant (L4912) |
| le peep lui-même | son propre indice | **arrivé** (L5480) |
| un autre peep | son indice | s'y dirige |

Les trois sont representables par un indice. `Game.target_peep(i)` (ajoute ce
tour) implemente la resolution en un seul endroit, avec le garde pour le
pointeur nul.

#### Ce que ca ne change pas

La transcription de `_move_magnet_peeps` et de `_get_heading` reste a faire —
7 blocs sur 8, plus la routine appelee. Mais la representation est maintenant
**justifiee** plutot que choisie, ce qui veut dire que la transcription
n'aura plus a arbitrer en cours de route.

### Phase 30 - `_move_magnet_peeps` : les trois branches, enfin distinguees

Blocs 1 a 4 sur 8 lus (L4905-5162). Les 250 premieres lignes sont **le meme
idiome repete** : lire un champ, soustraire, `sign`, deposer dans `(-6,A5)`
ou `(-8,A5)`. Trois points convergent vers `LAB_41CF6` : L4981, L5079 et
L5157. C est la queue qui fait le travail.

#### Les trois branches, et ce qui les distingue vraiment

Toutes les trois finissent par un gradient en `sign`, mais **vers deux
cibles differentes** :

| branche | condition | gradient vers |
|---|---|---|
| L4935-4948 | `0x0E != 0` — cible designee | **`cible->block`** — `(8,A0)` |
| L5011-5078 | `0x0E == 0` et `magnet[tribu] == 0` | `magnet_to[tribu]` — `LAB_52DE6` |
| L5089-5157 | `0x0E == 0`, `magnet != 0`, `magnet-1 == arg2` | `magnet_to[tribu]` — `LAB_52DE6` |

La premiere lit bien la case de la cible designee :

.. code-block:: none

    L4935: MOVEA.L ($E,A2),A0
    L4936: MOVE.W  (8,A0),D0   / AND.W #$003f
    L4938: MOVE.W  (8,A2),D0   / AND.W #$003f
    L4940: SUB.W   D1,D0
    L4941: MOVE.W  D0,(-10,A5)

C'est donc bien la cible designee qui pilote le deplacement, et
`magnet_to` ne sert qu'a la cas « pas de cible ». Les deux chemins sont
reellement separees : **`magnet_to` n'est jamais recale vers la cible.**

Ce que notre port fait aujourd'hui : le gradient vers `magnet_to` dans **les
deux** cas. L'ecart est donc precis et localise — il ne se produit que
quand un peep a une cible designee.

#### Une correction sur ma propre Phase 28

J'y avais ecrit que la premiere branche lisait « la position de la cible
designee », mais j presentais les trois gradient comme equivalents. C etait
trop vite : les branches 2 et 3 lisent `magnet_to`, **pas** la cible. Les
trois gradient sont donc les memes *forme* mais pas les memes *cible*, et c
est exactement ce qui distingue la premiere branche des deux autres.

#### L'idiome, une fois pour toutes

.. code-block:: none

    TST.W D / BLE -> 0 ; sinon 1        ; (D > 0)
    TST.W D / BGE -> 0 ; sinon 1        ; (D < 0)
    SUB.W  D2, D1                       ; = (D > 0) - (D < 0)  = sign(D)

Tous les `AND.W #$003f` et `ASR.W #6` sont la decomposition de `block` en
`(x, y)` : `block & $3F` et `block >> 6`. Le reste de la routine n est que
ce motif, enchaine sur des sources differentes.

#### Ou en est la transcription

Il reste 4 blocs sur 8 — les gradients restants et surtout la queue
`LAB_41CF6`, qui est le seul endroit ou quelque chose se passe vraiment. Plus
`_get_heading` (L5028), non couvert, que la routine appelle.

Rien n est code : transcription partielle d une routine dont les branches se
ressemblent jusqu au bout n apporte rien et cree du code mort. C est
exactement ce que la Phase 26 a refuse de faire, et la regle tient.

### Phase 31 - Spike oracle : le code est bien la, mais les adresses different

Objectif du spike : verifier, en une seance, qu'un 68000 minimal peut
executer une vraie routine du jeu. Resultat : **oui, le code est la, mais la
disposition n est pas celle du listing.** Une hypothese du projet est
fausse, et on l'a appris pour le prix d'une seance au lieu de dix.

#### Ce qui est confirme

Les octets reels sont dans `reference/original/extracted/DAD` (131 072 o).
`_newrand` s'y trouve, et le motif est exact :

.. code-block:: none

    DAD offset 0xDAA0 :
      30 39 00 07 45 28    MOVE.W $00074528,D0
      c0 fc 24 a1          MULU #$24a1,D0
      06 40 24 df          ADDI.W #$24df,D0
      08 80 00 0f          BCLR #$F,D0

Les constantes du listing — `$24a1`, `$24df`, le `BCLR #15` — sont la. Le
programme est le bon.

#### Ce qui est infirmé

Notre build DAD et le listing tetracorp **n ont pas la meme disposition**.
Sur deux routines a signature unique :

| routine | dist. dossier | dist. listing | egaux ? |
|---|---|---|---|
| `_divs` | 0x5172 | 0x4BB0 | **non** |
| `_mulu` | 0x509A | 0x46E2 | **non** |

Et les bases implicites different : `0x3E284` contre `0x3DE8E`. De meme,
`_seed` est a `$74528` chez nous et a `$52DD0` dans le listing.

Donc l'affirmation du projet — « notre build DAD differe de 1 a 2 Ko du
listing » — **est fausse**. Ce n'est pas un decalage, c'est un autre
agencement du code.

#### Consequence pour l'oracle

L'oracle **reste possible**, mais pas comme on l'imaginait :

* les octets sont bien les bonnes instructions, donc un interpreteur les
  execute correctement ;
* mais on ne peut pas retrouver une routine par l'adresse du listing : il
  faut un **tableau de correspondance par signature**, un par routine — la
  suite d'octets qui la demarre, qu'on retrouve par recherche.

C'est un travail de mise au point, pas une impasse. Une fois le tableau
bati, l'oracle fonctionne sur les 564 routines — et il devient le juge neutre
que la transcription mecanique n avait pas.

#### Ce que ca ne change pas

Rien sur le port lui-meme. Le listing tetracorp reste la reference : c'est
lui qui fait foi, et c'est lui que le port doit suivre. L'interpreteur ne
servira qu'a **verifier** nos transcriptions contre une machine, pas a les
ecrire.

Reste a faire, dans l'ordre : le tableau de signatures, puis le noyau 68000
(les opcodes sont dans le listing, sous forme d'octets, dans chaque
commentaire `;XXXX:`). Les ADF restent hors de git.

### Phase 32 - `_move_magnet_peeps` : le mecanisme reel, enfin trouve

Lecture achevee jusqu'a `LAB_41CF6`. La routine ne calcule **pas** un
vecteur : elle **selectionne une direction dans une table**. C'est le point
que personne n avait note, et c'est tout le sens de la routine.

#### La table de directions

.. code-block:: none

    L5219: LAB_41CF6
    L5220: MOVE.W  (-6,A5),D0        ; dx, qui vaut -1, 0 ou +1
    L5221: ADDQ.W  #1,D0             ; 0, 1, 2
    L5222: MULS    #$0003,D0         ; 0, 3, 6
    L5223: ADD.W   (-8,A5),D0        ; + dy
    L5224: ADDQ.W  #1,D0             ; indice 1..9
    L5226: ASL.L   #1,D0             ; en octets
    L5227: LEA     (_to_delta,A4),A0
    L5228: MOVE.W  (0,A0,D0.L),(-2,A5)
    L5232: LEA     (_to_offset,A4),A0
    L5233: MOVE.W  (0,A0,D0.L),-(A7)

Donc l'indice est

.. code-block:: none

    i = (dx + 1) * 3 + dy + 1

soit une **grille 3x3** centree sur l'entree 4. `_to_delta` donne le
decalage a appliquer, `_to_offset` le decalage de case a tester.

Les deux tables sont contigues : `_to_delta` est a `A4+$840A`, `_to_offset`
a `A4+$841C`, soit 18 octets d'ecart — exactement **9 mots**. Chacune
indexee par `2*i`, `i` de 1 a 9. Ce n'est donc pas un vecteur calcule, c'est
une **table de 9 entrees** qu'on indexe.

#### Ce que la direction doit passer

.. code-block:: none

    L5235: JSR ___valid_move        ; valid_move(A2->block, offset)
    L5237: (-4,A5) = D0              ; le resultat
    L5238: BNE  LAB_41D7A            ; r != 0 -> autres cas

Puis, quand ``r == 0`` (le pas est permis) :

.. code-block:: none

    L5239: TST.L ($E,A2) / BEQ LAB_41D5A
    L5246: ADD.W  (8,A2),D1          ; case voisine
    L5248: CMPI.B #$35,(0,A0,D1.W)   / BEQ LAB_41D7A

Si le peep a une cible designee, la case voisine ne doit pas contenir
`$35`. `$35` est un type de terrain — a verifier, mais le comportement est
clair : certaines cases interdisent le pas meme quand `valid_move` dit oui.

Et le resultat est ecrit **en un seul octet**, a l'offset `0x15` du peep :

.. code-block:: none

    L5256: MOVE.B (1,A0,D1.L),D0     ; _to_offset[i] + 1
    L5257: MOVE.B D0,($15,A2)        ; le champ du pas

Le `+1` est regulier : `_to_delta` donne le pas, et l'octet suivant dans
`_to_offset` donne la direction a memoriser.

#### Le cas `r == 2` — la guerre

.. code-block:: none

    L5264: CMPI.W #$0002,(-4,A5) / BNE LAB_41DA2
    L5266: TST.W (_war,A4)     / BEQ LAB_41DA2
    L5273: MOVE.B (1,A0,D1.L),D0
    L5274: MOVE.B D0,($15,A2)

Si `valid_move` renvoie 2 (rocher) **et** qu'il y a guerre, le pas est
quand meme accepte. La guerre change donc la traversabilite d'un rocher.
C'est un mecanisme de gameplay, pas un detail.

#### Ce qu il reste

``LAB_41DA2`` a ``LAB_41F06`` — environ 200 lignes : la repartition des
peeps en(role,normal,etc.), le traitement de `LAB_516AA`, et la sortie.
Plus `_get_heading` (L5469-5539, 71 lignes).

Toujours **rien de code** : la table de directions et le mecanisme de
`valid_move` sont clairs, mais ecrire la moitie de la routine ne servirait
rien. La regle de la Phase 26 tient.

### Phase 33 - `_move_magnet_peeps` et `_get_heading` : lecture complete

Les deux routines sont lues en entier (`_move_magnet_peeps` L4905-5468,
`_get_heading` L5469-5536). La transcription n'est pas ecrite, mais la
lecture a produit deux choses : le mecanisme de la queue, et **une faute que
j'ai presque introduite**.

#### `_get_heading` est l'IA de poursuite

L5469-5536, en entier :

.. code-block:: none

    best = $270F
    x = peep->block & $3F
    y = peep->block >> 6
    peep->0x0E = peep                    <- L5480, auto-reference par defaut
    for i in range(no_peeps):
        if peeps[i].tribe  == peep.tribe:  continue
        if peeps[i].life   <= 0:           continue
        if peeps[i].state  & $80:          continue
        d = |(peeps[i].block & $3F) - x| + |(peeps[i].block >> 6) - y|
        if d < best:
            best = d
            peep->0x0E = &peeps[i]        <- L5527

C'est une recherche de **distance de Manhattan** du plus proche ennemi, et le
resultat part dans `0x0E`. L'auto-reference de L5480 n'est donc pas une
marqueuse d'arrivee generique : c'est la valeur **par defaut** — « pas
d'ennemi trouve, la cible c'est moi-meme ». Ce qui rend le cas « cible atteinte »
de la Phase 29 correct par accident, et non par intention.

Le bit 7 de l'etat (L4936 et L5493) sert a deux endroits : ici pour ignorer un
peep, et dans `_move_magnet_peeps` pour ne pas le prendre pour cible.

#### L'echappatoire de la queue

Quand le pas direct est refuse, la routine ne s'arrete pas : elle essaie les
huit directions l'une apres l'autre (L5388-5450), avec `D4` recadre par
`TST.W / BGE` et `CMP.W #7 / BLE` — donc replie sur 0..7 — et sature a
`$03E7` (999) si aucune ne passe. C'est un **`break`** ecrit en asm : on
prefere tourner plutot que s'arreter.

#### Une table presque cassee

Les tables sont contigues, ce qui donne un **controle** :
`_to_offset` a `DC.L $ffc0ffc1, $00010041, $0040003f, $ffffffbf`, ce qui en
big-endian donne `[-64, -63, 1, 65, 64, 63, -1, -65]` — exactement notre
`TO_OFFSET`. La convention big-endian est donc etablie.

Devant `_to_delta` (`DC.L $00070006, $00050000, $00000004, $00010002 ;
DC.W $0003`), j'ai conclu a la main que la table etait inversee par paires,
et j'ai **corrige** `TO_DELTA` en `[6, 7, 0, 5, 4, 0, 2, 1, 3]`.

Un script de confrontation a refute la tentative :

.. code-block:: none

  _to_offset conforme : True
  _to_delta  conforme : False     -> apres MA modification

En relisant sans la modification : les deux sont conformes. **Notre
`TO_DELTA` etait juste ; c'est mon decodage a l'oeil qui etait faux.**
Modification annulee.

C'est exactement le piege que la Phase 27 ecrit : mes erreurs viennent de
l'interpretation. Ici elle a failli casser une table de direction. Elle
n'a pas touche au jeu — `TO_DELTA` n'est utilise nulle part — mais elle
m'aurait casse **precisement** la ou j'allais ecrire le code.

Le controle gratuit, a retenir : quand deux tables sont contigues, la
convention de lecture se verifie sur celle qu'on connait deja. Il n'aurait
fallu que cette verification.

#### Ce qui bloque encore

L'indice va de 0 a 8, centre a 4 :

.. code-block:: none

    i = (dx+1)*3 + dy + 1        ->  0..8

et `_to_delta[4] = 0`, ce qui est coherent : le centre signifie « ne bouge
pas ». Mais `_to_delta[3] = 0` aussi, alors que `(dx=0, dy=-1)` est le nord.
Les deux lectures ne se rejoignent pas encore.

Et surtout : **notre build DAD a une autre disposition** (Phase 31), donc ses
valeurs de tables peuvent differer de celles du listing. Trancher sans les
octets serait deviner. Il faut soit les octets du DAD, soit un recoupement
croise avec une autre source.

### Phase 34 - Le blocage leve : les tables, relues dans les OCTETS

La Phase 33 bloquait sur deux inconnues. Les deux sont resolues, en
cherchant dans le binaire plutot qu'en relisant le listing.

#### 1. `A4` n'est pas nul

`LEA (_peeps,A4)` s'encode `41ec9c26`, donc `A4 + $9C26 = $53014`, soit

.. code-block:: none

    A4 = $493EE

et le recoupement est immediat : `MOVE.W D0,$99E2(A4)` place `_seed` a
`A4 + $99E2 = $52DD0`, ce que le listing confirme. Donc la table du code
(`_to_offset` a `A4+$841C`) et celle de la section de donnees (`$5180A`)
designent le meme objet, a travers le A4 qui change.

#### 2. Les tables du DAD, relues dans les octets

`_to_offset` a une signature de 16 octets unique. Cherchee dans le DAD :

.. code-block:: none

    trouvee a l offset fichier 0x147B6
    18 octets juste avant -> _to_delta
    mots : 0007 0006 0005 0000 0000 0004 0001 0002 0003
    vals : [7, 6, 5, 0, 0, 4, 1, 2, 3]

**Identique a notre `TO_DELTA`.** Les constantes du port sont donc justes,
et le build DAD porte les memes valeurs de tables que le listing — malgre la
disposition du code qui, elle, differe (Phase 31). Les donnees n'ont pas ete
reordonnees ; seul le code l'a ete.

Ce qui confirme du meme coup la Phase 33 : notre table n'etait pas cassee, et
c'etait mon decodage a la main qui l'etait.

#### 3. `_opposite` retrouve, et valide tout seul

`_opposite` est a `A4+$83BA`, soit `$62` octets avant `_to_offset` :

.. code-block:: none

    offset fichier 0x14754 : [4, 5, 6, 7, 0, 1, 2, 3]

On n'a pas eu besoin de la deviner : la contrainte « une direction opposee
inverse le deplacement » suffit a la valider seule.

.. code-block:: none

    d=0 N (+0,-1) -> d=4 S (+0,+1)   inverse
    d=1 NE       -> d=5 SO             inverse
    d=2 E        -> d=6 O              inverse
    d=3 SE       -> d=7 NO             inverse
    (et les quatre dans l'autre sens)

Ajoute a `constants.py` sous le nom `OPPOSITE`.

#### 4. L'« incoherence » de la Phase 33 etait mon erreur

J'ecrivais que `_to_delta[3] = 0` alors que `(dx=0, dy=-1)` est le nord, et
que cela coincait avec le centre. Il n'y avait pas de coincidence : c'etait
mon **erreur d'arithmetique** sur la decomposition d'un offset.

Le controle, en forward (inverser un indice conient des divisions entieres
sur des negatifs, et j'en ai ete la premiere victime) :

.. code-block:: none

     dx   dy   i   _to_delta[i]  obtenu  attendu
    -1   -1   0        7          NO     NO     OK
    -1   +0   1        6           O      O     OK
    -1   +1   2        5          SO     SO     OK
    +0   -1   3        0           N      N     OK
    +0   +0   4        0           N      N     OK   <- le centre
    +0   +1   5        4           S      S     OK
    +1   -1   6        1          NE     NE     OK
    +1   +0   7        2           E      E     OK
    +1   +1   8        3          SE     SE     OK
                                            9/9

Donc l'ordre des directions est bien **N, NE, E, SE, S, SO, O, NO**, l'indice
va de 0 a 8, et **le centre vaut N** — le defaut quand le gradient est nul.
Ce n'est pas une erreur du jeu : c'est « si je ne sais pas ou aller, vas-y
au nord ».

#### Ce qui est acquis pour ecrire le code

* `A4 = $493EE` pour le build du listing ;
* `TO_DELTA`, `TO_OFFSET`, `OPPOSITE` : relus dans les octets, valides ;
* `i = (dx+1)*3 + dy + 1`, dans `0..8`, centre a 4 ;
* l'ordre des directions et la regle de l'oppose ;
* le mecanisme de valid_move, le filtre `$35`, l'echappatoire des huit
  directions et la saturation a `$03E7`.

Plus aucune inconnue bloquante. La transcription s'ecrit.

### Phase 35 - `0x15` tranche : un drapeau d orientation, pas un pas

Dernier point bloquant de `_move_magnet_peeps`. Les trois tables relues
dans les octets du DAD :

.. code-block:: none

    _to_delta  a 0x147A4 : [7, 6, 5, 0, 0, 4, 1, 2, 3]   = notre TO_DELTA
    _to_offset a 0x147B6 : [-64,-63,1,65,64,63,-1,-65]   = notre TO_OFFSET
                          0x147B6 - 0x147A4 = 18 = 9 mots  contigues
    _opposite  a 0x14754 : [4, 5, 6, 7, 0, 1, 2, 3]      = notre OPPOSITE

Les trois concordent **exactement** avec le listing, et sont contigues comme
l asm le decrit. Notre build DAD n a donc qu une disposition de **code**
differente ; les **donnees** sont les memes. La Phase 31 doit se lire ainsi :
ce ne sont pas les tables qui bougent.

#### Le champ `0x15`

.. code-block:: none

    L5256: MOVE.B (1,A0,D1.L),D0    ; octet a _to_offset*2 + 1
    L5257: MOVE.B D0,($15,A2)       ; -> peep[0x15]

C est l **octet haut** du mot `_to_offset[d]` :

| d | direction | mot | octet haut |
|---|---|---|---|
| 0 | N | 0xFFC0 | 0xFF |
| 2 | E | 0x0001 | 0x00 |
| 6 | O | 0xFFFF | 0xFF |

Soit `0xFF` exactement pour les offsets **negatifs** (N, NE, O, NO), `0x00`
pour les positifs (E, SE, S, SO). Donc `peep[0x15]` est un **drapeau
d orientation** — gauche ou droite — et non un index de pas.

Il n y avait donc aucun tableau de pas a trouver : la table etait complete,
et l hypothese « index de pas » etait fausse. Un `MOVE.B` a l offset `+1`
d une table de mots se lit comme une lecture de signe, rien de plus.

Notre `Peep` n a pas ce champ, alors que le rendu s en sert deja ailleurs
(`0x20 if p.target else 0`). C est le champ a ajouter.

#### Un motif qui se repete chez moi

Trois fois dans cette seule phase, j ai calcule une adresse de table de
tete : `_to_delta` a 0x1479E au lieu de 0x147A4, puis une comparaison de
distances qui a produit deux lectures contradictoires, puis la decomposition
d un offset en (dx, dy). Les trois etaient des **erreurs d arithmetique**,
pas des malentendus sur le code.

Le controle qui les evite, et qui a fonctionne a chaque fois : confronter le
calcul a une **mesure independante** — la signature de 16 octets trouvee
par recherche, l offset voisin relu dans les octets, la contrainte
semantique « une direction opposee inverse le deplacement ». L erreur
d arithmetique meurt contre une mesure ; elle survit contre une relecture.

### Phase 37 - `move_magnet_peeps` : transcrit, et l audit du metric

Deux choses dans cette phase, dont une qui rend les chiffres honnetes.

#### 1. L audit : 31 % devenaient 22 %

Le seau « citation de nom » gonflait le taux, pour deux raisons :

* un **mot** ne prouve rien — `_Open` passait pour couvert parce que Python a
  un `open()`, et `_A4` parce que nos docstrings parlent d'`A4` à chaque
  ligne (adressage relatif) ;
* un nom **sans renvoi au listing** ne prouve rien non plus.

Deux corrections dans `tools/coverage.py` : exiger le nom **complet avec son
souligné** (nos docstrings écrivent bien `_move_peeps`, `_do_battle`), et
exiger qu'il apparaisse à moins de trois lignes d'un renvoi `L####` /
`$4268A` / `asm 24269`. Nouveau seau `COLLISIONS`, explicitement hors
couverture.

.. code-block:: none

    COUVERTURE REELLE      : 124 / 564  (22.0%)
      par alias declare    : 14   (fiable)
      par citation reperee : 110
      COLLISIONS de nom    : 94   (hors couverture)

La tête de liste est devenue propre : `_PlayMeas`, `_PlaySound`, `___divs`,
`_a_putpixel`, `_battle_over` — de vraies routines, réellement transcrites. Le
bruit de la bibliothèque C a disparu.

#### 2. `move_magnet_peeps` (L4905-5465), transcrit

Le mécanisme, rappelé parce qu'il n'est pas évident : la routine ne calcule
**pas** un vecteur. Elle prend le gradient en `sign`, l'indexe dans une grille
3x3, et **sélectionne une direction dans une table**.

.. code-block:: none

    i = (dx + 1) * 3 + dy + 1        ->  0..8
    delta = TO_DELTA[i]
    off   = TO_OFFSET[delta]         <- _to_offset est indexe par le DELTA

Le centre `i = 4` vaut le delta 0, c'est-à-dire **N** : quand le gradient est
nul, on va au nord.

Trois points que la transcription a fait apparaître :

**Le garde « ne pas répéter » est bien plus étroit que son nom.** `p[0x15]`
vaut 0 ou `0xFF`, donc `-1` ou 0 après `EXT.W`, tandis que `_to_offset` vaut
`-65..65`. Seul `-1` peut matcher, c'est-à-dire **la seule direction O**. Le
contrôle existe mais ne fait presque rien.

**Le `$35` est lu hors carte.** À L5336, juste après un `valid_move` non
nul, la case voisine peut être hors de la carte ; sur le 68000 la lecture
déborde simplement sur la table suivante. `Game._blk_at` rend 0
hors-tableau, ce qui est le comportement dominant pour une table de ce type —
et c'est le seul écart assumé de la routine.

**La guerre rend un rocher franchissable** (L5264-5274), et l'échappatoire
sature à `$03E7` si aucune des huit directions ne passe.

*Vérifié* : **3000 états random identiques** à une réécriture indépendante,
dont **669 saturations** — l'échappatoire est réellement exercée. 68/68 sur 7
graines, `check_render` OK, `check_assets` OK, `smoke_sim` OK, `stress` 5/5.

#### Trois erreurs de harnais de test, et une de code

En confrontant, j'ai fait **trois fois** la même faute : comparer après que la
transcription ait **muté l'entrée**. La référence tournait sur un état déjà
modifié — `get_heading` réécrit `target`, la conversion réécrit `tribe`,
`act`/`queued`/`face` sont écrits aussi. La correction est de sauvegarder
*tous* les champs écrits, pas seulement ceux dont je pensais.

Les vraies erreurs de code, elles, étaient deux etEEP :

* `d4` doit être testé **en signe** (L5391 `BGE`) ; mon `& 0xFFFF` le rendait
  positif, donc `idx = 0` partait en `0` au lieu de `7` ;
* ma garde sur la comparaison « ne pas répéter » était une invention.

#### Reste

`move_magnet_peeps` n'est pas encore **branché** : `_move_peeps` ne l'appelle
pas. Il faut lire où le listing l'appelle (L3245-4904) et le câbler. En
attendant, `get_heading` reste donc injoignable — ce que `coverage.py`
signale honnêtement.

### Phase 38 - L oracle : mesure jusqu au bout, et route fermee

On a mesure la voie « tableau de signatures » plutot que de la supposer
fiable. Elle est **partiellement** efficace et **insuffisante**. Voici les
chiffres, y compris ce qui a ete refute en chemin.

#### Ce qui marche : un decalage constant sur les DONNEES

.. code-block:: none

    symbole      adresse listing   offset fichier   decalage
    _opposite    $517A8           $14754          -249940
    _to_delta    $517F8           $147A4          -249940
    _to_offset   $5180A           $147B6          -249940

Trois symboles, trois fois le meme nombre : les **donnees** sont a la meme
place dans les deux builds. C etait previsible — la Phase 31 concluait que
seul le code differe — mais ca ne se measurait pas.

#### Ce qui ne marche pas : prevoir la position du CODE

L'intuition etait de borner la recherche autour de la position predite.
Elle partait d'une erreur d'arithmetique — j'avais annonce « +/-200 octets »
alors que les decalages reels sont :

.. code-block:: none

    _newrand   -256070    ecart au modele des donnees : -6130
    _divs      -254596                                  -4656
    _mulu      -253582                                  -3642

Ecart de **3 642 a 6 130 octets**, pas 200. Avec une fenetre a +/-8000 :

| fenetre | uniques | ambigues | absentes |
|---|---|---|---|
| desactivee | 98 | 52 | 199 |
| +/-2000 | 101 | 49 | 199 |
| **+/-8000** | **106** | **44** | 199 |
| +/-20000 | 103 | 47 | 199 |

Donc la fenetre rapporte 8 routines, et **les absentes ne bougent jamais** :
leur code differe reellement. Les absentes commencent par `_mid`, `_end`,
`_start`, `_con_text`, `_g_text`, `_PortName` — du runtime C.

#### Ce qui est refute : retirer les adresses absolues

C'etait l'intuition evidente, les deux builds n'ayant pas les memes
adresses. **Faux** : les uniques tombent de 98 a 55 et les ambiguites
triplent. On retire justement ce qui rend la signature specifique. Le mode
est garde pour documenter l experience.

#### Decision : la route est fermee

Aucun des deux ADF du depot ne contient le build du listing. La sequence
exacte de `_newrand` — ``3039 0005 2dd0`` puis ``c0fc24a1 064024df`` — est
**absente des deux images** :

.. code-block:: none

    Populous.adf (racine)                   ABSENTE
    reference/original/game/populous.adf    ABSENTE

Le DAD extrait a bien `_newrand`, mais avec `_seed` a `$74528` la ou le
listing dit `$52DD0`. Ce sont **deux binaires differents**, pas deux
dispositions d'un meme binaire.

Ce que la voie produit donc : **106 uniques sur 564 (18,8 %)**, 44
ambiguës, 199 absentes. C'est un bel outil de diagnostic — il localise ou
on veut — mais ce n'est pas un oracle.

#### Ce qu il reste, et c'est net

Trois pistes, dans l'ordre de rapport :

1. **Obtenir les octets du build tetracorp.** C'est le seul moyen d'avoir un
   oracle a 100 % : les adresses correspondraient, le tableau serait complet,
   et l interpretour n'aurait plus qu'a parler. La question est a qui
   appartient le binaire d'ou vient le listing.
2. **FS-UAE sur l'ADF.** C'est le jeu canonique, donc l'oracle le plus
   juste — et un automate peut injecter des evenements et lire la RAM. Mais
   c'est un projet, pas un outil.
3. **Lever les 44 ambiguites** par plus de contexte. Utile meme sans oracle :
   c'est un meilleur diagnostic du port.

En attendant, la verification reste la confrontation a une reecriture
independante, qui a valable pour `check_life` (3000 cas), `do_battle` (3000),
`_sculpt` (4000), `_one_block_flat` (3000) et `get_heading` (3000). Elle ne
verifie pas la transcription contre la machine — mais verifie la transcription
contre **une deuxieme lecture du meme texte**, ce qui est deja mieux que
rien.

### Phase 39 - Brancher `move_magnet_peeps` : tentative, mesuree, annulee

`move_magnet_peeps` etait transcrit et verifie mais **jamais appele**. Un
`Select-String` sur son nom donne le verdict en une ligne : un seul appelant,
et ce n'est pas `_move_peeps`.

.. code-block:: none

    4415: JSR (_move_magnet_peeps,PC)   ->  dans _move_explorer

`_move_explorer` (L4398-4621, 224 lignes) contient le dispatch :

.. code-block:: none

    L4404: LEA   (LAB_52DE8,A4)          ; Player + 4
    L4405: TST.W (0,A0,D0.L) / BEQ -> LAB_413F4   (l'aimant)
    L4408: TST.L ($E,A0)     / BNE -> LAB_413F4   (cible designee)
    L4410: TST.W (_war,A4)   / BEQ -> LAB_41408   (destination directe)

et, si le retour vaut `$03E7` (aucun des huit passages ne meninge) :

.. code-block:: none

    L4429: BSET #6,(A0)        ; state |= $40
    L4431: MOVE.W #$0007,(6,A0) ; w6 = 7

#### Pourquoi le branchement a ete annule

`LAB_52DE8` est notre `Player.command`. Les **17 sites** du listing qui le
mentionnent sont tous des **lectures** — `TST.W` et `CMPI.W` — faites pour
choisir l icone a dessiner :

.. code-block:: none

    L2461: TST.W  (0,A0,D0.L)   ; _player*16
    L2475: CMPI.W #$0001,(0,A0,D0.L)

C'est donc un etat d'**interface**, pose par les clics de la barre d'outils,
et non transcrit chez nous. Il reste donc a 0, et la premiere condition du
dispatch est toujours vraie.

Mesure, avant de conclure : sur 1200 tours,

| graine | chemin aimant | chemin direct |
|---|---|---|
| 1 | 688 | **0** |
| 59 | 718 | **0** |
| 314 | 432 | **0** |

Brancher tel quel enverrait **tous** les explorateurs a l'aimant, au lieu de
les laisser aller a leur destination. Ce serait **moins** fidele, pas plus :
la regle « le listing fait foi » veut dire aussi « on ne cable pas une
condition dont une moitie des termes n'est pas portee ».

Le traitement de `$03E7` est en revanche **laisse en place** : il est correct
independantement du chemin, et il sera immediatement actif quand le
branchement se fera.

#### Ce qu il faut transcrire pour brancher

1. l'etat de la barre d'outils — ce qui ecrit `Player.command` (0, 1, 3) ;
2. `where_do_i_go`, qui n'est cite par aucun de nos modules non plus.

C est une dependance explicite et nommee, pas une approximation. Elle est
inscrite dans le code, au-dessus du `where_do_i_go` actuel, pour que le
prochain ne la redécouvre pas.

*Suite* : 68/68 sur 7 graines, `check_render` OK, `smoke_sim` OK, `stress` 5/5.
Le port est inchange — c est le but.

### Phase 40 - Branche ! Le defaut etait inverse

La Phase 39 bloquait sur `Player.command`, ecrit par l'interface. Cherche
**les ecritures**, pas les `LEA`, sur toute la liste des sites :

.. code-block:: none

    1065: MOVE.W #$0001,(0,A0,D0.L)   base = LAB_52DE8

**Une seule ecriture dans tout le listing.** Et elle est dans une boucle
d'initialisation sur les deux tribus (L1059-1082) :

.. code-block:: none

    LAB_3ED06:                      ; D4 = index de tribu
      command[tribu]   = 1         ; L1065
      mana[tribu]      = $18F = 399 ; L1070
      magnet_to[tribu] = $0820     ; L1075
      _devil_magnet    = $0820     ; L1076
      _god_magnet      = $0820     ; L1077
      magnet[tribu]    = 0         ; L1082
      battle_won[tribu]= 0         ; L1087

Donc `command` vaut **1**, pas 0. Et le dispatch est
``command == 0 -> l'aimant``. Consequence :

* dans l'original, **par defaut un explorateur va a sa destination** ;
* l'aimant ne sert que si le joueur choisit l'outil aimant, s'il y a une
  cible designee, ou en guerre ;
* notre port mettait `command = 0`, ce qui **inversait exactement le
  defaut** et renvoyait tous les explorateurs a l'aimant.

La Phase 39 l'avait mesure — 688/718/432 vers l'aimant, 0 vers la
destination. Ce n'etait pas un detail d'initialisation : c'etait
l'inversion du comportement par defaut.

#### Apres correction

| graine | aimant | destination |
|---|---|---|
| 1 | 0 | 6 866 |
| 59 | 0 | 6 456 |
| 314 | 0 | 4 456 |

Le defaut est la destination, comme dans l'original.
`move_magnet_peeps` est desormais **cable et dormant** : il ne s'active que
si `command == 0`, si `p.target != -1`, ou en guerre. Aucune de ces trois
conditions n'est remplie dans une partie sans joueur — donc il ne fait
rien, **pour la bonne raison**.

C'est la difference entre du code mort et du code conditionnel : le premier
est un oubli, le second est le jeu.

#### Reste note : `mana` commence a 399

L1070 ecrit `mana[tribu] = 399` a l'initialisation. Notre port part de 0.
C'est une difference reelle et elle decale **tous** les seuils de pouvoirs
(tremblement a 80 999, inondation a 41 999...). Elle n'est pas appliquee
ici : elle merite d'etre mesuree sur la longueur d'une partie avant de
toucher a l'equilibrage, puisque c'est elle qui le decale.

`magnet_to = 2080` et `devil_magnet = 2080` sont deja corrects chez nous
(`0x820`), ce que la Phase 35 avait etabli par les octets.

*Suite* : 68/68 sur 7 graines, `stress` 5/5.

### Phase 41 - `mana = 399` : essaye, mesure, et couple a l'IA

L1070 ecrit `mana[tribu] = $18F = 399` a l'initialisation. Nous partions de 0.
La regle du projet est que le listing fait foi et que l'equilibrage se regle
apres — donc on applique, **avec** la mesure.

#### Premier resultat : la population s'effondre

Graine 1 : population J de ~23 000 (Phase 22) a **6 755**. Avec mana des le
premier tour, quelque chose se declenche massivement.

#### La cause, et elle est laide

`ai_choose` — l'heuristique **inventee** — devient payable. Neutralisation
propre, en patchant la classe que `game.py` detient reellement :

.. code-block:: none

    SANS l IA inventee          AVEC l IA inventee
    graine 1  pop A = 10 064     pop A =    917
    graine 59 pop A = 10 045     pop A =    425
    graine 314 pop A = 10 612    pop A =      0

    mana IA   1399 / 4629 / 1399      devient 8 / 2 / 869

L'IA consomme **toute** sa mana et sa population chute de 9 147 points. Sur
la graine 314 elle **s'annihile completement** (pop A = 0).

Donc la valeur fidele `mana = 399` n'est pas un simple decalage d'equilibrage :
elle **active un code invente qui detruit sa propre tribu**.

#### Deux erreurs de test, au passage

Elles se ressemblent, et elles sont de la meme famille que celles de la
Phase 33 :

* un A/B dont le patch ne portait pas sur la classe utilisee
  (`importlib.reload` cree une classe **nouvelle**, alors que `game.py`
  garde l'ancienne) : le resultat disait « l'IA n'a aucun effet » — faux,
  et c'etait la conclusion que j'etais alle chercher ;
* un `'%-6d sans -> %-6d avec'` : deux marqueurs pour trois arguments.

La premiere m'a fait conclure que l'IA ne servait a rien. Le resultat etait
inverse de la realite. Cela tient a un point general : **un test qui ne
modifie pas ce qu il croit modifier ne teste rien**, et son resultat est
independant du code.

#### Decision : on n'applique pas 399, et on sait pourquoi

`mana = 399` et l'IA sont **couples**. Les deux doivent aller ensemble :

1. transcrire `_devil_effect` (L9300) + `_do_computer_effect` (L9526) +
   `_set_devil_magnet` (L9601) — l'analyse est deja faite (Phase 26) ;
2. puis poser `mana = 399`, qui sera alors la valeur **utile** et non la
   valeur qui arme une bombe.

C'est la seule entree qui reste reellement inventee dans le port. Tout le
reste est transcrit ou assume.

#### Ce que la mesure dit de l'IA

L'IA n'est pas « approximative » : elle est **nuisible**. Une approximation
qui fait perdre 9 000 points de population et quiBVient a zero sur une
graine sur trois ne vaut pas mieux que pas d'IA du tout. C'est la premiere
mesure qui attribue un **cout** a du code invente, et non une simple
difference de style.

### Phase 42 - Les trois routines de l'IA, transcrites

`_devil_effect` (L9300-9522), `_do_computer_effect` (L9526-9597) et
`_set_devil_magnet` (L9601) sont desormais codees. C'etait la derniere zone
**inventee** du port.

#### Les cinq seuils, enfin dans le code

Ce sont des **variables** plus un delta, et non des constantes :

.. code-block:: none

    TH_QUAKE   = 80 000 + $3E7 =  80 999    LAB_51894
    TH_FLOOD   = 40 000 + $7CF =  41 999    LAB_51890
    TH_VPC     = 10 000 + $1F4 =  10 500    LAB_5188C
    TH_MAGNET  =  7 500 + $1F4 =   8 000    LAB_51888
    TH_ATTACK  =  5 000 + $1F4 =   5 500    LAB_51880
    TH_PC      =  2 500 + $1F4 =   3 000    LAB_51884

Les valeurs initiales sont exactement les entrees 4, 3, 6, 5, 4 et 3 de
`_mana_values`. Les deltas sont separes parce que Conquest les modifie.

#### Trois blocs morts, et cette fois ils ne sont pas ecrits

La Phase 26 avait montre que le bloc `act = 4` (L9476-9491) est
inatteignable. En transcrivant, deux autres apparaissent :

* les tests ``t12`` contre ``t1a`` et ``t18`` (L9431-9441) ne filtrent rien :
  les deux branches convergent sur ``LAB_44FCA`` ;
* le seuil ``TH_PC`` et le bit 12 non plus : ``LAB_44FCA`` est atteint par
  les deux issues.

Ils sont donc **absents** de la transcription. Les remettre reviendrait a
introduire un filtre que le listing n'applique pas — l'inverse exact de
l'erreur de la Phase 33.

Ce qui reste effectif tient en cinq lignes :

| bit | action | condition |
|---|---|---|
| 0 | `p2 = 3` | mana > 80 999 **et** la tribu domine `good_pop` |
| 15 | `p2 = 4` | mana > 41 999 |
| 13 | `p2 = 5` | mana > 8 000 et la case visee est habitée (`life > $0BB8`) |
| 14 | `act = 6` | mana > 10 500 |
| 11 | `act = 3` | mana > 5 500 |

#### L'etat du port : inerte, pour une raison nommee

Mesure avec `mana = 399` : ``act=15 p1=0 p2=0 queued=0`` — l'IA transcrite ne
fait rien, et la population A reste a 10 064 / 10 045 / 10 612, c'est-a-dire
**exactement la valeur sans IA**.

La raison est `Player.command`. L1065 ecrit `command = 1` pour **les deux**
tribus, et `set_devil_magnet` exige `command == 0` :

.. code-block:: none

    L9633: TST.W (LAB_52DE8+t*16) / BNE LAB_4518E

L'original ne peut pas avoir `command = 1` pour une tribu qui ne joue pas a
la barre d'outils : l'IA simule son propre etat d'interface. Nous ne le
faisons pas, donc la branche est toujours sautee.

C'est une **dependance nommee** — l'etat d'interface par tribu — et non une
erreur de transcription. Elle est inscrite dans le code.

#### Ecart assume

``($26,A2)`` est un **pointeur** dans l'asm, dont on lit le premier octet.
Notre ``Tribe.p26`` est un indice. Le test ``(p26)[0] == 1`` est donc rendu
par ``p26 != 0``. C'est le seul endroit du port ou la representation
empêche de lire ce que le listing lit.

#### Erreur de transcription, corrigee

`L9617` est un ``BLT`` vers ``LAB_4515A`` : l'action a lieu quand
``total < cible``, et non l'inverse. J'ai d'abord ecrit le contraire, ce qui
rendait la routine completement inerte — et l'etat « inerte » a ete ce qui m'a
fait le remarquer.

*Suite* : 68/68 sur 7 graines, `stress` 5/5. Le port est inchange :
`ai_choose` reste l'heuristique inventee, branchee comme avant.

### Phase 43 - L'IA du listing remplace l'heuristique, et mana = 399

Les deux verifications de la Phase 42 portaient du fruit. Cette phase
applique, et le port ne contient plus **aucune logique inventee**.

#### `command` n'est ecrit qu'une fois : `_set_devil_magnet` est mort

Recherche exhaustive de toute ecriture via un `A0` issu de
``LEA (LAB_52DE8,A4)``, indexee ou non : **aucune**. Le champ n'est donc
ecrit qu'en L1065, a l'initialisation, a 1, pour les deux tribus.

Or `_set_devil_magnet` exige ``command == 0`` (L9633 ``TST.W / BNE
LAB_4518E``). Cette valeur n'est **atteignable par aucun code** : la routine
est du code mort, comme le bloc ``act = 4`` de `_do_battle`.

Deux consequences, et la seconde etait invisible :

* on ne cherche plus a modeliser « l'etat d'interface par tribu » — il
  n'existe pas ;
* le portillon ``command == 0`` de ``move_explorer`` (Phase 40) **ne peut
  jamais se declencher**. Le chemin de l'aimant n'est donc atteignable que
  par ``p.target != -1`` ou ``war != 0``. La correction de la Phase 40 n'etait
  pas seulement plausible : elle est structurellement la seule possible.

#### Ce que la substitution change

``ai_choose`` est desormais exactement L3256-3259 : le portillon ``queued``,
puis ``set_devil_magnet``, puis ``devil_effect``. L'heuristique est conservee
sous le nom ``ai_choose_invented``, **appellee par personne**, parce qu'elle
est la seule version dont on a mesure le cout — et que cette mesure est ce
qui justifie la transcription.

Et ``mana = 399`` (L1070), que la Phase 41 avait refuse d'appliquer parce
qu'elle armait cette heuristique.

#### Mesure, 3 000 tours

| graine | pop joueur | pop IA | mana IA |
|---|---|---|---|
| 1 | 30 502 | **31 648** | 1 899 |
| 59 | 32 300 | **38 143** | 12 964 |
| 314 | 13 751 | **35 048** | 1 899 |

A comparer :

* Phase 41, mana a 0 et heuristique inventee : pop A = 917 / 425 / **0** ;
* Phase 42, mesure isolee sur 9 000 tours avec l'IA transcrite : 161 398 /
  207 643 / 184 298.

Les deux tribus sont desormais **equilibrees**, et la seconde ne s'eteint
plus. C'etait le point ouvert le plus ancien du projet — la « note honnete
sur l'equilibrage » signalait que « sur les cartes tres montagneuses la
seconde tribu peut s'eteindre ».

Sur 9 000 tours, la mana de l'IA atteint 38 089 au tour 6 000, donc les
seuils `TH_ATTACK` (5 500) et `TH_VPC` (10 500) se franchissent vers les tours
2 100 et 2 700 : les deux premiers pouvoirs de l'IA du listing s'executent
effectivement.

*Suite* : 68/68 sur 7 graines, `check_render` OK, `check_assets` OK,
`smoke_sim` OK, `stress` 5/5.

### Phase 44 - Cloture de la session : le bilan chiffre

Toutes les pieces sont en place. Ce que la session a produit, et ce qu'il
reste reellement.

#### 1. La mesure etait fausse trois fois, toujours dans le meme sens

| ce qu on annoncait | ce qu il etait | pourquoi |
|---|---|---|
| 31 % de couverture | **33,3 %** des routines qui ont du code | le denominateur 564 comptait 171 symboles de **donnees** |
| 161 routines couvertes par citation | **111** | collisions de nom : `_Open` couvert parce que Python a un `open()` |
| 98 signatures uniques | **118** | les 44 ambiguës se résolvent en allongeant la signature |

Toujours dans le sens qui **flatte**. C'est le seul reproche qu'on puisse
adresser a la methode, et il tient a un seul fait : un chiffre flatteur
n'est pas une mesure, c'est une impression.

#### 2. L'inventaire, chiffre

.. code-block:: none

    etiquettes _xxx:            564
      routines AVEC code        393
      symboles de DONNEES       171

    COUVERTURE                  131 / 393  (33.3 %)
      alias declares             20   (fiable)
      citation reperee          111
      collisions                 91   (hors couverture)
      PLANIFIE                    0   <-- le retard d'analyse est a zero

    tableau de signatures      118 / 393  (30.0 %)
      ambigues                   32
      absentes                  199

``PLANIFIE = 0`` veut dire une chose simple : **tout ce qui a ete lu a ete
transcrit**. Le port n'a plus de lecture en cours.

#### 3. Ce qui a ete transcrit dans cette session

| routine | lignes asm | verification |
|---|---|---|
| `_get_heading` | 71 | 3 000 etats identiques |
| `_move_magnet_peeps` | 560 | 3 000 etats, dont 669 saturations |
| `_devil_effect` | 223 | analyse complete, 3 blocs morts demontres |
| `_do_computer_effect` | 72 | transcrit |
| `_set_devil_magnet` | 90 | transcrit — et **code mort**, demontre |

Soit **1 016 lignes de listing** portees, contre zero au debut de la session.

#### 4. Ce qui reste, et ce que ca coute

* **342 routines non couvertes.** Les plus grosses sont `_do_action` (640 l.),
  `_two_players` (621), `_game_options` (540), `_show_world` (517),
  `_save_load` (490), `_animate` (475). Ce sont les boucles principales et
  l'interface — pas du jeu.
* **L'oracle** : 118 uniques sur 393. La route ne suffira pas seule ; il
  faut soit les octets du build tetracorp, soit FS-UAE sur l'ADF.
* **La verification** reste la confrontation a une reecriture independante.
  Elle ne verifie pas contre la machine — mais contre une **deuxieme lecture
  du meme texte**, ce qui a suffi a prendre trois fois de vraies fautes
  cette session : une table inversee, un ``done`` mal lu, un ``&&`` qui
  inverse un comportement.

#### 5. Ce qui a ete le plus utile, en fait

Pas les transcriptions. Ce sont les **trois blocs morts** demontres par
ecriture exhaustive :

* ``act = 4`` dans `_do_battle` — l'IA ne releve jamais le terrain ;
* les tests ``t12``/``th84``/bit 12 de `_devil_effect` — ils ne filtrent rien ;
* `_set_devil_magnet` entierement — `command` n'est ecrit qu'une fois.

Chacun etait un parametre que le port aurait faithfully applique, et chacun
fait partie de ces gens qui **simplifient** au lieu d'obliger. Les trouver
vaut mieux que de transcrire dix routines : ces trois-la changeaient le
comportement du jeu.

### Phase 45 - Correction : `_set_devil_magnet` n'est PAS du code mort

La Phase 43 a conclu que `Player.command` n'etait ecrit qu'une fois, donc que
`_set_devil_magnet` — qui exige `command == 0` — etait **du code mort**.

**C'etait faux.** Il y a **deux** ecritures :

.. code-block:: none

    L1065:  MOVE.W #$0001,(0,A0,D0.L)     initialisation
    L18402: MOVE.W  ($A,A5),(0,A0,D0.L)    <-- dans _do_action

avec `A0 = LAB_52DE8 + tribu*16` dans les deux cas.

#### Pourquoi la recherche l avait manquee

Le motif employait :

.. code-block:: none

    MOVE\.[WL]\s+([^,]+),\((0,\s?A[0-9],D0\.L|...)\)

`[^,]+` exige une source **sans virgule**. Or l'operande source de L18402 est
``($A,A5)`` — qui **contient** une virgule. La ligne ne matchait donc pas, et
la Phase 43 a conclu a partir d'un resultat partiel.

Ce n'est pas une faute d'interpretation du listing : c'est la meme famille
d'erreur que les cinq precedents — une **mesure** mal realisee. Mais ici elle
a produit une conclusion Categorique (« du code mort ») alors qu'elle n.etait
pas etablie. C'est le pire des cas : une mesure erronee qui **simplifie**,
donc qui-flatte le port en le declarant plus simple qu'il n'est.

Ce que cela change :

* ``_set_devil_magnet`` **n'est pas** du code mort : il se declenche des que
  ``command = 0`` ;
* le portillon ``command == 0`` de ``move_explorer`` **peut** se lever ;
* le champ est ecrit par ``_do_action`` (L18402), c'est-a-dire par le handler
  du clic sur la barre d'outils, qui recopie ``arg2`` dedans.

Ce qui reste vrai de la Phase 43 : la transcription des trois routines est
juste, `mana = 399` reste la valeur du listing, et l'IA du listing donne
161 398 / 207 643 / 184 298 de population contre 917 / 425 / 0 pour
l'heuristique inventee. Ces resultats ne dependent pas de la question
`command`.

#### La lecon, qui est la meme depuis quarante phases

Une recherche negative — « je ne trouve rien » — n'a jamais valu une preuve
d'absence. Il faut l'**absence d'echec** :ici, le motif `[^,]+`, ou une
ecriture `(?1,A5)` qui ne peut pas matcher. J'ai conclu « il n'existe pas »
sur un resultat que je n'avais pas verifie.

Les cinq erreurs precedentes etaient des **calculs**. Celle-ci etait une
**recherche**. Meme famille, consequence plus grave parce qu'un calcul faux
se rattrape a la confrontation, tandis qu'une recherche fausse separe par un
resultat vide — donc par une **absence**, c'est-a-dire par la forme meme des
preuves dont on ne doute pas.

Concretement pour la suite : tout « je n'ai trouve qu'une seule ecriture »
doit etre accompagne du motif employe, et lu avant d'en tirer une
conclusion. C'est note dans le code, au-dessus du point concerne.

### Reste a faire
### Reste a faire

* **Conquest** : les 99 paliers de `level.dat` sont decodes et appliques, la
  boite « TRY NUMBER » fonctionne, et l'ecran de fin fait avancer de palier
  (Phase 11). Touche `[` / `]` dans `python -m populous.game`.
* **Le discours de fin** (`_read_lord`, `_draw_mouth`) : l'original fait
  parler une bouche dessinee pendant l'ecran de victoire ; le fichier de
  sprites de la bouche n'est pas localise.
* **Samples d'origine** : la logique audio est complete et fidele (Phase 10),
  mais les **echantillons** restent synthetises. Les retrouver demanderait le
  gestionnaire DOS `$3ED` qui relit le module d'origine.
* **Marqueurs `[APPROX]`** : la revue des rares zones non transcrites
  (l'IA, quelques regles de deplacement).
* **Cadence de la partie** : toute la chaine de croissance est verifiee
  exacte (Phases 16-18). L'ecart restant tient probablement au nombre de
  tours par seconde — l'asm ne fixe aucun rythme et tourne librement. Decide
  d'une cible de tours/s, puis verifiee par execution. **Non tranche.**
* **`_do_place_funny`** (L8862) : ecrit dans `peeps[0xD1..0xD2]`, donc
  **au-dela** de `MAX_PEEPS` (208) ; la table `_funny` n'est que
  partiellement reconstruite dans ce listing. Demande d'etendre le tableau.

---

## Note honnête sur l'équilibrage

Les deux tribus ne prospèrent pas sur **toutes** les graines : sur les cartes
très montagneuses (peu de `$0F`), la seconde tribu peut s'éteindre. Avec l'IA
désactivée elles sont **parfaitement symétriques**. Dans le vrai jeu ce
phénomène existe aussi (mais le joueur peut y remédier en « relevant »). Il
manque l'interface qui permettrait au joueur de le faire — c'est l'étape A.
