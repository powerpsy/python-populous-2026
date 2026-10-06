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

---

## Note honnête sur l'équilibrage

Les deux tribus ne prospèrent pas sur **toutes** les graines : sur les cartes
très montagneuses (peu de `$0F`), la seconde tribu peut s'éteindre. Avec l'IA
désactivée elles sont **parfaitement symétriques**. Dans le vrai jeu ce
phénomène existe aussi (mais le joueur peut y remédier en « relevant »). Il
manque l'interface qui permettrait au joueur de le faire — c'est l'étape A.
