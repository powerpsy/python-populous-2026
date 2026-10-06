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
