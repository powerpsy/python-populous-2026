"""Socle de jeu : fenetre, boucle d'image, deplacement de la vue.

C'est le premier morceau reellement jouable ; il reutilise tout ce qui existe
(``terrain`` pour la carte, ``render`` pour l'image, ``assets`` pour qaz.pic et
les sprites) et reproduit les regles de deplacement decortiquees dans
``docs/ui_layout.md`` :

* la fenetre isometrique 8x8 est **fixe** a l'ecran (``_screen_origin = 0xA16``),
  c'est ``_xoff/_yoff`` ∈ [0, 0x38] qui choisit la portion de carte visible ;
* un clic sur la mini-carte recentre : ``u = mx//2 + my - 32``,
  ``v = my - mx//2 + 32``, puis ``xoff = clamp(u-3, 0, 0x38)`` ;
* un clic dans le losange fixe le centre sur la case visee.

Usage :  ``python -m populous.game [graine] [sol] [zoom]``

Commandes, identiques a l'original :

* **palette du bas-gauche** : choisir l'action (relever, abaisser, marais,
  seisme, aimant). C'est la seule facon de choisir un pouvoir — le centre de
  chaque case est a l'ecran ``(16*(up-vp+1), 128 + 8*(up+vp))`` ;
* **clic gauche sur la carte** : cibler la case (uniquement en mode de
  sculptage, c'est-a-dire quand ``_mode & 0x0E`` — cf. ``_sculpt``) ;
* **clic gauche sur la mini-carte** (Book of Worlds) : recentrer la vue ;
* **pave du bas** : defiler d'une case ; son centre recentre sur l'habitant
  selectionne ;
* **barre d'icones a droite** : musique, effets sonores, poser un peuple ;
* **maintenir le bouton gauche sur un habitant** : le suivre (``_interogate``).

Touches pratiques restantes :
    fleches / WASD ....... deplacer la vue
    molette ............. +/- 1 au zoom
    + / - ............... idem
    TAB ................. changer de sol (land0..land4)
    N .................... nouvelle graine
    P .................... basculer l'animation d'eau (``_toggle``)
    F1 .................... plein ecran
    Echap / Q ............ quitter
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from populous import config  # noqa: E402
from populous import m68k  # noqa: E402
from populous.assets import load_pic, load_sprites  # noqa: E402
from populous.assets import load_land as load_tiles  # noqa: E402
from populous.config import DEFAULT_GROUND, DEFAULT_SEED  # noqa: E402
from populous.config import TURNS_PER_FRAME, ZOOM  # noqa: E402
from populous import endtext  # noqa: E402
from populous import musique  # noqa: E402  ECART Phase 86 : reference/*.mp3
from populous.conquest import load_levels  # noqa: E402
from populous.conquest_win import (BLOC_H, BLOC_X, BLOC_Y,  # noqa: E402
                                   END_WORDS, PALIER_NOMS, WORDS,
                                   YEUX_X, YEUX_Y, nouveau_niveau, texte_fin)
from populous.constants import (ACT_ACTION, ACT_LOWER, ACT_MAGNET,  # noqa: E402
                                ACT_NOP, ACT_QUAKE, ACT_RAISE, ACT_SWAMP,
                                ACT_TREE, ACT_VOLCANO, BLK_FLAT, DIR_SPRITE,
                                MANA_VALUES, ST_BATTLE, ST_VILLAGER)
from populous.land import load_land  # noqa: E402
from populous.render import (SCREEN_H, SCREEN_W, Renderer,  # noqa: E402
                             clamp_off, map_colours)
from populous.powers import PowerEngine  # noqa: E402
from populous.sound import MusicEngine, SoundEngine  # noqa: E402
from populous.sim import Game as Sim  # noqa: E402
from populous.terrain import MAX_OFF, build_map  # noqa: E402
from populous.rng import Rng  # noqa: E402

KEY_STEP = 4                    # cases par appui (le jeu d'origine fait defiler
                                # d'une case par image, cf. pavé _zoom_map)


def _atoi(texte: str) -> int:
    """`___atoi` (C) : l'entier en tete de ``texte``, 0 s'il n'y en a pas.

    Seul le **mot** retenu a interet : L12265 fait `TST.W D0` et L12270
    `MOVE.W D0,(_start_seed)`. La boucle saute les espaces, prend en compte
    un signe eventuel, puis lit jusqu'au premier caractere non chiffre.
    """
    i, n = 0, len(texte)
    while i < n and texte[i] in " \t\n\r\f\v":
        i += 1
    signe = 1
    if i < n and texte[i] in "+-":
        signe = -1 if texte[i] == "-" else 1
        i += 1
    debut = i
    total = 0
    while i < n and "0" <= texte[i] <= "9":
        total = total * 10 + (ord(texte[i]) - 48)
        i += 1
    if i == debut:
        return 0
    return signe * total


def _touche_nom(ev) -> str | None:
    """La lettre qu'une frappe doit mettre dans ``_asckey``.

    `ev.unicode` porte deja la touche traduite, **shift compris** - c'est
    l'equivalent de la table `keycodes` (L19085) et de son decalage de
    `$60` (L19058-19062). Les trois touches de controle que ``_get_name``
    lit explicitement (`$08`, `$7f`, `$0d` - L10422, L10424, L10435) n'ont
    pas d'unicode partout : elles sont donc nommees.

    Une touche sans lettre (fleches, Fx) rend ``None`` : `_keyboard` ne la
    pousse pas, ce qui revient au `keycodes` plein de zéros de l'original -
    `_asckey` reste nul et L10390 saute vers `_check_cancel`.
    """
    if ev.key == pygame.K_BACKSPACE:
        return "\x08"
    if ev.key == pygame.K_DELETE:
        return "\x7f"
    if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return "\x0d"
    return ev.unicode or None


def _champ(buf: bytearray) -> str:
    """Le contenu d'un tampon `char*` jusqu'a son zero, en latin-1.

    C'est exactement ce que ``___text`` lit (L10353, L10386, L10468) :
    la boucle s'arrete sur l'octet nul, jamais sur la taille du tampon.
    """
    fin = buf.find(0)
    return bytes(buf[:fin if fin >= 0 else len(buf)]).decode("latin-1")


def _remplir(texte, n: int = 16) -> str:
    """La recopie d'un tampon sur ``n`` octets, `$82` au-dela du texte.

    C'est le motif de L10621-10660, L10683-10709 et L10718-10738 : la
    longueur est `strlen` (0 si l'entree est hors contenu), puis les octets
    restants valent `$82` jusqu'a l'octet nul pose a ``n`` (L10658-10660).
    """
    corps = (list(bytes(texte)) if isinstance(texte, (bytes, bytearray))
             else [ord(c) & 0xFF for c in texte])[:n]
    corps += [0x82] * (n - len(corps))
    return bytes(corps).decode("latin-1")


class Game:
    def __init__(self, seed: int = 1, ground: int = 0, zoom: int = 3) -> None:
        self.seed = seed
        # `_start_seed` (L392, L430, L18922) : la copie de `_seed` que la
        # ligne 15 de GAME SETUP restaure **avant** de rappeler
        # `_setup_display`. Le port n'en avait pas (ECART des Phases 71 et
        # 75) ; il est desormais pose partout ou l'est `_seed`.
        self.start_seed = seed
        # `_start_of_game` (L3E2A2, L3E2B4, L3E7B0, L3EC9A, L439C6,
        # L43AD2, L4860A) : 0=normal, 2=choix monde direct, 3=tutoriel/demo.
        self.start_of_game = 0
        self.ground = ground
        self.zoom = max(1, zoom)
        # Vue de depart, `_animate` L507-508 : `CLR.W (_xoff,A4)` puis
        # `CLR.W (_yoff,A4)`, soit **(0, 0)**. `_draw_it` (L15797-15806)
        # ancre ensuite la fenetre en `_map_blk[yoff*64 + xoff]` sans
        # aucune soustraction : (0, 0) est donc le **coin haut-gauche**,
        # pas le centre.
        #
        # **ECART supprime** : le port ouvrait ici sur (24, 8), une valeur
        # sans base dans le listing. Un balayage exhaustif de toutes les
        # ecritures de `_xoff`/`_yoff` (formes MOVE/CLR/ADD/SUB, et pas de
        # forme hexadecimale `$99f0(A4)` — le desassembleur resout le
        # symbole partout) ne trouve que :
        #   * le `CLR` initial, L507-508 ;
        #   * le defilement au clavier, L773-831 (`scroll_w` ... `scroll_e`) ;
        #   * la souris, le pave et la mini-carte, L1697-1698 et L1865-2440.
        # **Rien ne recentre la vue au demarrage**, pas meme
        # `_show_the_shield` (L2769), appele une seule fois depuis le
        # gestionnaire clavier (L761).
        #
        # C'est aussi coherent avec `_place_first_people` : son balayage
        # demarre en (0, 2) (L7688, `#$0080`), c'est-a-dire **juste sous**
        # la vue initiale. La tribu 0 est cherchee la ou l'ecran regarde.
        self.xoff = 0
        self.yoff = 0
        self.frames = 0
        self.running = True
        self.conquest = None          # palier de conquete courant (si charge)
        self.conquest_no = 1
        # --- fin de partie (asm L4323-4352, L14460) ---
        self.game_ended = False      # la simulation est figee
        self.victory = False         # `_end_game(1)` : le joueur a gagne
        self.surrender = -1          # `_surender` : -1 = personne n'abandonne
        self.score = 0               # `_score`, en points de victoire
        self.conquest_next = 0       # prochain palier calcule par l'ecran
        self.conquest_fini = False   # le mode a ete boucle entierement
        self.conquest_dialog = None        # boite « TRY NUMBER » ouverte ?
        # --- l'ecran du Seigneur (`_won_conquest`, L14503-14742) ---
        # Le discours n'a lieu que sur une victoire en conquete avec un
        # `lord.pic` present : hors de la, `victory_speech` reste faux et
        # `draw_end_screen` garde son ancien comportement.
        self.victory_speech = False
        self.victory_fond = None    # `_w_screen`, le portrait 320x200
        self.victory_mouths = []    # les 6 bouches de `_map_steps`
        self.victory_eyes = False   # les yeux (bouche n. 5) ont ete poses
        self.victory_flag = False   # (-122,A5) : le mode est termine
        self.victory_counter = 0    # (-120,A5)
        self.victory_mouth = 0      # (-108,A5) : la bouche 0..4 courante
        self.victory_dir = 1        # (-110,A5) : le sens de l'oscillation
        self.victory_world = 0      # (-114,A5) : `_level_number / 250`
        self.victory_graine = 0     # le mot de `_code(newrand())`, L148D1C
        self.victory_pal = []       # `_tcmap[0..15]`, la palette de lord.pic
        self.victory_texte = ("", "")   # les deux lignes de `_text`
        # `_end_text` + `strGAME_` (L14021-14389) : le tableau des scores,
        # construit **une fois** dans `_end_game` et relu a chaque image.
        self.end_titre = endtext.TEXT_NEW_GAME
        self.end_lignes = list(endtext.END_TEXTE)
        self.victory_vblank = 0     # les 4 `_waittof` de L148EF2-148EFE
        self.victory_music = 1      # (-116,A5) : `_music_off` sauvegarde
        self.victory_effect = 1     # (-118,A5) : `_effect_off` sauvegarde
        self.mouse = (0, 0)
        # Les deux bascules de la barre. L'asm les nomme `_music_off` et
        # `_effect_off`, mais L19621/L19633 font `TST.W` puis `BEQ` : le bloc
        # est **saute quand le mot est zero**. Le son joue donc quand le
        # drapeau est non nul — l'inverse de ce que suggère le nom du
        # symbole. On suit le code, pas l'etiquette.
        self.music_on = 1
        self.effect_on = 1
        # Phase 86 : la musique de fond par fichier (``reference/BGM.mp3``).
        # Ce drapeau n'est arme que par ``run()`` : un outil qui construit
        # un ``Game`` sans boucle d'image (autopilot, stress, check_*) ne
        # doit pas lancer un MP3 pour rien ni laisser un son qui tourne.
        self._piste_armee = False
        self.icon_toggles: set[tuple[int, int, int]] = set()
        # _left_button / _right_button : 0 = clic (1 image), 0x40 = relache,
        # 1 = stable, 2 = bloque (asm L19582-19591, L999, L2425-2448)
        self.left_button = 1
        # Drapeau de redessin de `_game_options` : le listing le tient
        # dans son cadre local (-4,A5). Ici c'est un attribut, pose par
        # `_exec_game_setup` et relu par `game_setup`.
        self._redessiner = False
        # `_message` (L3058) : le tampon de saisie de `_show_world`, qui y
        # recopie "GENESIS" a l'ouverture (L12203) et qui sert aussi de
        # champ de texte aux ecrans de messages (L12234).
        self._message = ""
        # `_conquest` (L84bc) : les dix octets lus dans `level.dat` par
        # `_show_world` (L12360). Le port a aussi `self.conquest`, un
        # `ConquestLevel` reconstruit par `load_conquest` - mais ici le
        # listing ne fait que remplir le tampon, sans interpreter.
        self._conquest = bytearray(10)
        # `(-18,A5)` : le mot saisi ou decode, qui devient `_level_number`.
        self._monde = -1
        # Le tiroir des sauvegardes : `_drawer` (L302c) et le tampon de douze
        # noms `LAB_525C8` (L525c8), plus le defilement et le nom courant.
        self._saves_drawer = "Pop Saves"
        self._saves_liste = []
        self._saves_nom = ""
        self._saves_defil = 0
        self.right_button = 1
        self._raw_left = False          # etat physique du bouton
        self._raw_right = False
        # `_asckey` (L25502) et la file de touches lue par `_keyboard`
        # (L19037-19072) : le port n'a pas le port clavier de l'Amiga,
        # `handle` y verse les KEYDOWN pendant qu'un `get_name` tourne.
        self._touches: list[str] = []
        self._asckey = ""
        self._saisie = False            # un `_get_name` en cours (L10388)

        pygame.init()
        pygame.display.set_caption("Populous (remake) - %d/%d" % (seed, ground))
        self.screen = pygame.display.set_mode((SCREEN_W * self.zoom,
                                               SCREEN_H * self.zoom))
        self.clock = pygame.time.Clock()

        # `_setup_display` L431-433 : `_seed != 0` -> un `_newrand` avance la
        # graine **avant** `_make_alt` (L462). La carte est donc battue depuis
        # la graine **avancee**, pas depuis la graine de depart - celle-ci n'est
        # sauvegardee qu'en `_start_seed` (L430). L496 fait `_seed += 1` une
        # fois `place_first_people` passe. Sans ce tirage, la mer occupe 66 %
        # de la carte au lieu de 41 % (graine 1) et les deux tribus tombe
        # cote a cote sur le bord : aucun habitant visible a l'ouverture.
        #
        # Sequense exacte de tirages de `_setup_display`, dans l'ordre :
        #   L433          1 tirage  (`___newrand` inconditionnel des que
        #                            `_seed != 0` : le `BTST #0,D0` qui suit
        #                            ne pilote que le cycle de `ground_in`)
        #   L458          4 tirages (`_clear_map` L1093 et L1110, une paire
        #                            par joueur - verifie dans `clear()`)
        #   L462          `_make_alt` (3 marches)
        #   L469          `_make_woods_rocks`
        #   L495          `_place_first_people` : **zero** tirage
        #                            (`_place_people` L6982-7651 n'en a pas)
        #   L496          `_seed += 1` : increment entier, pas un tirage
        graine_carte = seed
        if seed != 0:                          # L431-432 : `TST.W / BEQ`
            _av = Rng(seed)
            _av.raw()                          # L433 `JSR ___newrand`
            graine_carte = _av.seed
        self.terrain, rng = build_map(graine_carte, ground)
        self.ren = Renderer(ground)
        self.colours = map_colours(self.ren.header)
        # La simulation partage les tableaux du terrain : `map_who`, `map_bk2`
        # et `map_blk` sont donc vus a l'identique par le rendu.
        # `rng` est rendu par `build_map` a l'etat ou l'a laisse
        # `_make_woods_rocks` : c'est exactement `_seed` au moment de L496,
        # d'ou le `+ 1`. `terrain.seed` porte la meme valeur (`build()`).
        # L'ancien `graine_carte + 1` sautait les 4 tirages de `_clear_map`
        # et les marches de `_make_alt`, emetant la simulation sur une
        # suite de tirages que l'original n'a jamais parcourue.
        self.sim = Sim((rng.seed + 1) & 0xFFFF, load_land(ground),
                       map=self.terrain.game_map())
        # `_one_block_flat` (L9148) lit les altitudes de sommet, qui sont dans
        # le terrain et pas dans `GameMap`.
        self.sim.terrain = self.terrain
        self._sync_level_stats()
        self.powers = PowerEngine(self)
        self.sound = SoundEngine()
        self.music = MusicEngine(self.sound)
        self.effect = 0

        # _start_of_game == 3 : mode tutoriel/demo (L4860A)
        # _start_game copie _tutorial (46 octets) sur _stats, pose _seed=0x69bc,
        # _start_seed=0x69bc, _game_mode=_tutorial_game_mode=1, _pause=1.
        if self.start_of_game == 3:
            self._init_tutorial_mode()

        self._settle_peoples()
        # qaz.pic est le fond permanent de l'ecran (_clr_wsc le recopie a chaque
        # image) ; la mini-carte y est ecrite en place, comme dans l'original.
        self.backdrop = load_pic("qaz.pic")

        # Surface avec canal alpha : sans lui pygame ignore la transparence
        # des sprites et des glyphes (les destinations sans SRCALPHA ecrivent
        # la source telle quelle, alpha compris, donc rien n'apparait).
        self.frame = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA, 32)
        self.hud = pygame.font.Font(None, 16)
        self.people = 0

    # ------------------------------------------------------------------ temps
    def _settle_peoples(self) -> None:
        """Pose les deux tribus sur la carte reellement generee.

        Deux ecritures de fiche, puis :meth:`_place_first_people`, qui est
        la transcription ligne a ligne de L7652-7859 (Phase 78).

        `can_build` : L11256-11259 (fin de la routine qui precede
        `_two_players`, $46492-4649E) ne pose que
        ``can_build[_not_player] = 1`` ; ``can_build[_player]`` garde sa
        valeur `.data`, qui est 0. `can_build[t] == 1` veut dire « l'Amiga
        conduit la tribu t » (menu Game Setup, L12849-12866) : c'est ce qui
        autorise l'auto-releve des noyes (L3497), le sculptage
        `one_block_flat` (L4112) et le seuil avide 0x131 (L3830). Comme le
        port n'a pas encore d'interface de pouvoir, la tribu joueur cesse
        donc de reagir toute seule.

        `colour` garde 11/14 : le `.data` porte 5/1 (L24203 / L24229), mais
        L408 et L12070 reecrivent le champ au demarrage et le port
        travaille avec une autre table de palettes.
        """
        sim = self.sim
        sim.stats[sim.player].can_build = 0
        sim.stats[sim.not_player].can_build = 1
        for t in (0, 1):
            sim.stats[t].colour = 11 if t == 0 else 14
            sim.players[t].magnet = 0          # L3ed4e: _clear_map efface _magnet
        self._place_first_people()
        self._recentrer_depart()

    # ------------------------------------------------- ECART : vue de depart
    def _recentrer_depart(self) -> None:
        """Recentre la vue sur le premier villageois de la tribu jouee.

        **ECART declare et volontaire — le listing ne fait PAS ceci.**

        Ce que le listing fait, et que le port suit a la lettre ailleurs :

        * `_animate` L507-508 efface `_xoff` et `_yoff`, soit (0, 0) ;
        * L623-625 appelle `_draw_it(_xoff, _yoff)` ;
        * `_draw_it` L15797-15806 ancre la fenetre en
          ``_map_blk[yoff*64 + xoff]``, **sans aucune soustraction**, et
          L15873 / L15880 bornent les deux boucles a 8 : la fenetre est
          **8 x 8 cases**, coin haut-gauche en (xoff, yoff) ;
        * un balayage exhaustif de toutes les ecritures de `_xoff` /
          `_yoff` (formes MOVE / CLR / ADD / SUB — il n'existe pas de
          forme hexadecimale `$99f0(A4)`, le desassembleur resout le
          symbole partout) ne trouve que le `CLR` initial (L507-508), le
          defilement au clavier (L773-831) et la souris / le pave / la
          mini-carte (L1697-1698 et L1865-2440). **Rien ne recentre au
          demarrage**, pas meme `_show_the_shield` (L2769), appele une
          seule fois depuis le gestionnaire clavier (L761).

        Autrement dit l'original ouvre vraiment sur le coin haut-gauche.
        Mais `_place_first_people` cherche le premier `0x0F` en partant du
        bloc `#$0080` = **(0, 2)** (L7688, condition `CMPI.B #$0f` en
        L7692) — c'est-a-dire **juste sous** cette vue initiale. Le design
        original suppose que la case plane est pres du bord.

        Or la carte generee n'a que ~3 % de cases planes : `make_alt`
        (L1189) fait trois marches aleatoires (`_make_thing(2,4)`,
        `(4,2)`, `(3,3)`) qui s'arretent a l'altitude 6 (L1226
        `CMP.W #$0006`), et `make_map` (L1420) ne marque `BLK_FLAT` que
        quand les **quatre** sommets d'une case sont egaux et non nuls —
        donc uniquement les plateaux. Mesure : le premier `0x0F` tombe en
        y = 2..5 mais en **x quasi uniforme sur 0..63**, si bien que la
        tribu 0 n'est visible depuis (0, 0) que sur **10 graines sur 64**.

        Le port ne pouvait donc pas rester sur (24, 8) — une valeur sans
        base dans le listing, qui montrait le vide *plus souvent* que
        (0, 0) — ni laisser le joueur chercher ses propres habitants sur
        une vue de 8x8 dans une carte de 64x64 (1,5 % de la surface).

        **Ce que fait ici le port** : apres le placement, la vue est
        amenee sur le premier villageois de la tribu jouee, avec le meme
        serrement de 0 a 0x38 (56) que celui du pave et de la mini-carte
        (L1917 / L1925 : `MOVE.W #$0038,(_xoff,A4)`).

        La suite de tirages n'est **pas** modifiee : cette methode ne
        touche ni a `_seed` ni a la carte, seulement a la fenetre.
        """
        sim = self.sim
        cible = None
        for idx, peep in sim.living():
            if peep.tribe == sim.player:
                cible = peep.block
                break
        if cible is None:                       # nadir : rien a suivre
            return
        self.xoff = max(0, min(0x38, (cible & 0x3F) - 3))
        self.yoff = max(0, min(0x38, (cible >> 6) - 3))

    # ------------------------------------------- _place_first_people (L7652)
    def _nb_peeps(self, tribu: int) -> int:
        """Le mot `(-4,A5)` de `_place_first_people` : villageois a poser.

        L7654-7678 pour la tribu 0, L7756-7780 pour la tribu 1 — le
        squelette est identique, seule la colonne de `level.dat` change
        (`conq_06_yourpop` contre `conq_07_enemypop`) et le test de seuil
        porte sur `stats[0]` contre `stats[1]` (`LAB_516B0` / `LAB_516DE`,
        les deux `+0x0C` de `_stats`).

        * **conquête** (ou **mode tutoriel** `_start_of_game == 3`,
          L7656 / L7758) : la colonne de `level.dat` elle-meme
          (`conq_06_yourpop` / `conq_07_enemypop`) ;
        * **deux joueurs** (`serial_off == 0`) : exactement un ;
        * **sinon** : ``2 * (seuil > 4) + 1``, donc 3 quand la tribu est
          avide (`threshold > 4`), 1 sinon. La tribu Amiga (`.data` = 5)
          demarre donc avec trois villageois, la tribu humaine (`.data` =
          1) avec un.
        """
        sim = self.sim
        if sim.in_conquest != -1 or self.start_of_game == 3:  # L7654-7656 / L7756-7758
            return self._conquest[6 if tribu == 0 else 7]   # L7658 / L7760
        if sim.serial_off == 0:                     # L7664-7666 / L7766-7768
            return 1
        return ((1 if sim.stats[tribu].threshold > 4 else 0) << 1) + 1

    def _peupler(self, tribu: int, n: int, depart: int, pas: int) -> int:
        """Le balayage d'une tribu (L7688-7754 pour la 0, L7790-7856 pour la 1).

        ``pas`` est ``+1`` pour la tribu 0 (elle avance dans `_map_blk`,
        de ``$80`` = (x=0, y=2) vers ``$FFF``) et ``-1`` pour la tribu 1
        (elle recule, de ``$0F80`` = (x=0, y=62) vers ``$80``). Renvoie le
        nombre de villageois **non poses**.

        Premier balayage (L7689-7717 / L7791-7819) : les seules cases
        retenues sont celles dont ``_map_blk == $0F`` (constructibles), et
        chaque case trouvee en consomme un. Le **dernier** villageois est
        pose avec ``magnet = 1`` (L7694-7701), les autres avec 0 — c'est
        ce qui en fait le point d'aimantation de la tribu.

        Second balayage (L7718-7754 / L7820-7856) : seulement si des
        villageois restent (carte sans aucun ``$0F``). Le fait que la case
        soit **vide** ne suffit plus, il faut en plus ``_map_who == 0`` —
        case non occupee.

        **ECART declare, L7823** : la tribu 1 initialise son second
        balayage a ``$1000 = 4096``, **hors** des 4096 cases — un debord
        reel du listing. Le byte lu est `_map_alt[0]` (le tableau suit
        `_map_blk` en memoire, a `$00060F88`) et `_map_who[4096]` est un
        mot d'une autre table. Le port ne garde pas `_map_alt` (4096
        octets ≠ les 4225 sommets de `disp_alt`) : il modele cette case
        comme vide, c'est-a-dire comme si la boucle commencait a `$FFF`.
        """
        sim = self.sim
        blk = self.terrain.blk
        who = self.terrain.who

        i = depart                                # L7688 / L7790
        while True:                               # LAB_43A18 / LAB_43B26
            if 0 <= i < 4096 and blk[i] == BLK_FLAT:   # L7692 / L7794
                n -= 1                            # L7694 / L7796
                sim.place_people(tribu, i,
                                 1 if n <= 0 else 0)     # L7697-7710
                if n == 0:                        # L7712-7713 / L7814-7815
                    return 0
            i += pas                              # L7715 / L7817
            if (pas > 0 and i >= 0x1000) or (pas < 0 and i < 0x80):
                break                             # L7716-7717 / L7818-7819

        if n == 0:                                # L7719-7720 / L7821-7822
            return 0
        i = 0 if pas > 0 else 0x1000              # L7721 / L7823
        while True:                               # LAB_43A70 / LAB_43B82
            if 0 <= i < 4096 and blk[i] != 0 and who[i] == 0:   # L7725-7730
                if pas < 0:                       # L7833-7839 : la tribu 1
                    # teste **avant** de decremente — `magnet` porte alors
                    # l'ancienne valeur de `(-4,A5)`.
                    sim.place_people(tribu, i, 1 if n <= 0 else 0)
                    n -= 1                        # L7850
                    if n == 0:                    # L7851-7852
                        return 0
                else:                             # L7731-7738 : la tribu 0
                    n -= 1
                    sim.place_people(tribu, i, 1 if n <= 0 else 0)
                    if n == 0:                    # L7749-7750
                        return 0
            i += pas                              # L7752 / L7854
            if i == 0 or i == 0x1000:             # bornes L7753 / L7855-7856
                break
        return n

    def _place_first_people(self) -> None:
        """``_place_first_people`` — L7652-7859, appele par `_setup_display` (L495).

        Deux fois le meme squelette, une par tribu :

        1. le **nombre** de villageois, `(-4,A5)` (:meth:`_nb_peeps`) ;
        2. ``+10 points`` par villageois (L7680-7686 / L7782-7788) : seule
           la tribu **jouee** encaisse — c'est le score de fin de partie,
           pas le mana ;
        3. le balayage de `_map_blk` (:meth:`_peupler`), en **ligne
           d'horizon** depuis le centre de la carte : la tribu 0 depuis
           (0, 2), la tribu 1 depuis (0, 62), donc l'une vers le haut et
           l'autre vers le bas.

        **ECART declare** : le port posait avant la Phase 78 les deux
        tribus sur les **deux meilleures cases constructibles** (cela
        garantissait un depart equitable sur des cartes tres
        asymetriques). Le listing, lui, s'arrete a la **premiere** case
        `0x0F` trouvee dans l'ordre lineaire — les deux tribus peuvent
        donc tomber cote a cote sur une carte ou le relief est borne. Le
        code d'origine gagne, conformement a la regle du projet.
        """
        sim = self.sim
        for tribu, depart, pas in ((0, 0x80, 1), (1, 0x0F80, -1)):
            n = self._nb_peeps(tribu)
            if sim.player == tribu:               # L7680-7681 / L7782-7783
                self.score += n * 10              # L7682-7686 / L7784-7788
            self._peupler(tribu, n, depart, pas)

    # ------------------------------------------------------------ Conquest
    #: Les champs de `Sim` que `_setup_display` (L380-498) reconstruit, ou
    #: qui dependent du sol : ils ne sont **pas** repris de la fiche
    #: precedente par :meth:`set_ground` en mode `conserver_etat`. Tout le
    #: reste est intact dans le listing.
    _RECONSTRUIT = frozenset((
        "map", "terrain", "rng", "land", "peeps", "no_peeps", "seed",
        "weapons_order",
    ))

    def _ecritures_palier(self, lv) -> None:
        """`_setup_display` L407-427 : les quatre ecritures, puis `_game_mode`.

        Colonnes 0 et 1 : une seule tribu geree en conquete, d'ou deux
        ecritures par champ::

            L407-408  stats[1].threshold  = _conquest[0]     (lv.threshold)
            L410-411  stats[1].period     = conq_01_speed    (lv.ai_period)
            L414-418  stats[1].power_mask = (conq_02 << 3) | 7
            L419-423  stats[0].power_mask = (conq_03 << 3) | 7
            L425-427  _game_mode          = conq_04_mode     (lv.mode)

        L'asm n'a **aucune** mana de depart par niveau : L1070 pose
        $18F = 399 pour les deux tribus, et `conq_08` n'est lu que L390,
        comme graine. L'ancienne formule `start_mana * 100` venait de la
        colonne 8-9 lue comme deux octets de mana - elle disparait.

        L425-427 est le seul endroit du port qui alimente les cinq options
        de l'ecran *SET GAME OPTIONS* (Phase 71) : les cinq bits de bas
        poid sont les cinq paires de choix exclusifs.
        """
        sim = self.sim
        sim.stats[1].threshold = lv.threshold
        sim.stats[1].period = lv.ai_period
        sim.stats[1].power_mask = (lv.enemypow << 3) | 7
        sim.stats[0].power_mask = (lv.yourpow << 3) | 7
        sim.game_mode = lv.mode

    def _palier(self):
        """Le palier porte par le tampon ``_conquest`` (L12340-12368).

        Dix octets lus dans ``level.dat`` par :meth:`_lire_level_dat`, que
        le listing reutilise tel quels a L395-L427 : `conq_01_speed` ...
        `conq_08_seed` ne sont que des alias d'octets de ce tampon
        (:class:`populous.conquest.ConquestLevel` les lit un par un).
        """
        from populous.conquest import ConquestLevel
        return ConquestLevel(0, bytes(self._conquest))

    def _construire_palier(self, lv, in_conquest: int) -> None:
        """`_setup_display` L388-427 : pose le palier de conquete.

        ``in_conquest`` est `_in_conquest` du listing (L388). Le port passe
        soit `sim.in_conquest` (chemin `_setup_display`), soit
        `lv.number` (chemin :meth:`load_conquest`, qui part d'un numero
        saisi et non d'un monde) - les deux ecritures sont distinctes dans
        le code d'origine comme dans le port.
        """
        # L388-392 : `_seed = _start_seed = (in_conquest & 7) + conq_08`.
        # `conq_08` est un MOT (octets 8-9) - `lv.seed`.
        self.seed = (in_conquest & 7) + lv.seed
        self.start_seed = self.seed
        # L395-399 : le `CMP` de L396 compare `conq_05_terrain` a
        # `_ground_in` mais son drapeau n'est **jamais lu** - une ecriture
        # morte, suivie de `_ground_in = conq_05_terrain` (L399).
        # L400-404 `_load_ground(_ground_in)` puis `_clear_map` ; L458
        # (meme routine), L462-469 (`a == 0`), L495 (`_place_first_people`)
        # et L496 (`_seed += 1`) sont rendus par `set_ground` - dont les
        # quatre ecritures de L407-427 doivent **suivre**, sinon elles
        # tomberaient sur la fiche qui vient d'etre jetee.
        #
        # La branche conquete saute L429-458 entierement : ni le tirage de
        # L433 ni rien d'autre n'avance `_seed` avant `_clear_map`. On pose
        # donc `_seed = self.seed` sur la fiche **avant** l'appel, pour que
        # `set_ground` (qui lit l'etat vivant) parte de la bonne valeur.
        self.sim.rng.seed = self.seed
        self.set_ground(lv.terrain, conserver_etat=True)
        # `_ground_in` (L399). Le `_seed += 1` de L496 est deja rendu par
        # `set_ground` (`rng.seed + 1`) ; l'ecriture qui suivait ici
        # remettait le RNG en arriere sur la graine de depart, sans les
        # tirages de `_clear_map` ni les marches de `_make_alt`.
        self.sim.ground_in = self.ground
        self._ecritures_palier(lv)

    def load_conquest(self, n: int) -> bool:
        """Charge le palier de conquete ``n`` (1..99) et reconstruit la partie.

        ``seed = (in_conquest & 7) + graine`` et ``sol = terrain`` (§5.2 de
        ``docs/game_logic.md``). Les quatre ecritures de `_setup_display`
        (L407-427) y sont posees, par :meth:`_construire_palier` qu'elle
        partage desormais avec :meth:`setup_display`.
        Renvoie ``False`` si ``level.dat`` est absent.
        """
        levels = load_levels()
        if not levels:
            return False
        lv = levels[max(0, min(len(levels) - 1, n - 1))]
        self.conquest = lv
        self.conquest_no = n                 # le palier courant, pour l'ecran
        # Le tampon `_conquest` (L12340-12368) doit suivre : c'est lui que
        # L395-L427 relira si `_setup_display` est rappelle en conquete
        # (`_animate` L552, `_won_conquest` L14432). `load_levels` et
        # `_lire_level_dat` lisent les memes `_CANDIDATES`, donc les memes
        # octets ; l'ecriture partielle de L12365 est retombee sur les dix
        # octets du niveau, pas sur zere. Un echec (fichier disparu entre
        # les deux) laisse le tampon tel quel : `lv` fait foi.
        self._lire_level_dat(max(0, min(len(levels) - 1, n - 1)))
        self._construire_palier(lv, lv.number)
        return True

    def setup_display(self, a: int, ground: int) -> None:
        """``_setup_display(a, ground)`` (L380-498) : (re)construit la carte.

        Cinq appels dans le listing, **tous** avec ``a == 0`` :
        `_animate` L511 ``(0, 1)``, L552 ``(0, -1)``, `_two_players`
        L11815 ``(0, -2)``, `_won_conquest` L14432 ``(0, -1)`` et
        `_do_action` code 8 L18928 ``(0, _new_map - 2)``. Le corps
        ``a != 0`` (L460-461), qui sauterait `_make_alt` /
        `_make_map` / `_make_woods_rocks`, n'est donc jamais atteint.

        **Ce que l'argument `ground` peut faire.** Rien d'autre qu'
        autoriser le changement de sol : la branche partie libre (L429-458)
        ne l'affecte **jamais** a `_ground_in`. Il ne sert qu'aux tests des
        L436 (``== -1``) et L448/L451 (``!= -1`` et ``!= _ground_in``).

        * ``ground == -1`` — le « nouveau monde » des lignes 9 et 14 —
          fait tourner `_ground_in` de +1 (L438-441 : ``BLE``, donc reset a
          0 des qu'il depasse 3) si et seulement si ``_seed != 0`` (L431)
          **et** si le bit0 du prochain `_newrand` vaut 1 (L433-435).
        * ``ground == _ground_in`` — *RESTART THIS MAP* — ne change rien :
          on regenere le meme relief a partir de ``self.seed``, et
          ``_start_seed``/``_seed`` ont ete restaures juste avant
          (L18920-18922).
        * le ``-2`` de `_two_players` recharge le sol courant (L453-456).

        **RNG : ou est `_seed` ?** `_newrand` (L19129-19135) n'est pas une
        methode, c'est un LCG sur la variable absolue `_seed` ($00052DD0) :
        le relief, la simulation et cette routine passent tous par la meme.
        Dans le port c'est :attr:`sim.rng
        <populous.sim.Game.rng>` - `populous.rng.Rng` est la copie ligne a
        ligne de L19129-19135. ``self.seed``, lui, est le mot de graine de
        la carte que `build_map` relit : **les deux existent**, et c'est la
        pour cela que :meth:`set_ground` doit pouvoir rendre ``rng``.

        **ECART declare.** Le port separe ce que l'Amiga n'ecrit pas en
        un seul bloc :

        * `_place_first_people` (L495) devient `_settle_peoples`, appele
          dans `set_ground` ; il efface les peeps existants, que le listing
          **laisse** en place sur la nouvelle carte ;
        * L471-L487 (`Setscreen`, `_draw_map(0,0,63,63)`, deux
          `_copy_screen`) sont le rendu : le port les fait par
          :meth:`compose` a chaque image ;
        * `_seed += 1` (L496) vaut ``vivant + 1`` en partie libre et
          ``(graine du palier + 1)`` en conquete - les deux cas sont
          rendus explicitement ci-dessous.
        """
        sim = self.sim
        if a != 0:                                   # L460-461
            raise NotImplementedError(
                "_setup_display(a = %d) : la branche `a != 0` (L460-461) "
                "veut une carte effacee mais sans relief, et "
                "`Terrain.build` ne produit pas cet etat. Les cinq appels "
                "du listing passent tous a = 0." % a)
        if sim.in_conquest != -1:                    # L382-383
            # Le tampon `_conquest` (L12360) est la source : `_in_conquest`
            # y pointe via `monde / 25` (L12315-12319).
            lv = self._palier()
            self.conquest = lv
            self._construire_palier(lv, sim.in_conquest)   # L388-427
            return                                   # L428 -> LAB_3E6AE

        # ---- LAB_3E652, L429-458 : partie libre -------------------------
        self.start_seed = sim.rng.seed               # L430 `_start_seed = _seed`
        if sim.rng.seed != 0:                        # L431-432
            # L433 : `_newrand` avance `_seed` **meme** si `ground != -1` —
            # le tirage n'est conditionne par rien.
            tirage = sim.rng.raw() & 1               # L434 `BTST #0,D0`
            if tirage and ground == -1:              # L436-437
                self.ground += 1                     # L438
                if self.ground > 3:                  # L439-440 `BLE`
                    self.ground = 0                  # L441
                # L443-446 `_load_ground(_ground_in)` : le sol **apres**
                # incrementation, rendu par `set_ground` plus bas.
        # L448-456 : `_load_ground(_ground_in)` si `ground != _ground_in` et
        # `ground != -1` — c'est toujours le sol **courant**, jamais
        # l'argument. `set_ground` recharge les tables, donc couvert.
        #
        # `set_ground` lit `sim.rng.seed`, qui est ici l'etat post-tirage de
        # L433 : c'est exactement `_seed` au moment de `_clear_map` (L458).
        # L'ecriture `sim.rng.seed = vivant + 1` qui suivait ici autrefois
        # (L496) est **retiree** : `set_ground` rend deja la fiche neuve
        # faconnee avec `rng.seed + 1`, et cette ecriture la-dessus
        # remettait le RNG quatre tirages en arriere (ceux de `_clear_map`).
        self.set_ground(self.ground, conserver_etat=True)   # L458 `_clear_map`
        self.sim.ground_in = self.ground             # `_ground_in` (L438-441)

    # ---------------------------------------- saisie du numero (asm L11942)
    # L asm ecrit la boite Â« TRY NUMBER Â» puis boucle sur le clavier :
    #   * `_word_asc` convertit la valeur en decimal dans un tampon ;
    #   * `CMPI.W #$7530` borne la saisie a 30000 ;
    #   * la touche 0x0D (retour chariot) valide (LAB_46E36) ;
    #   * toute autre touche fait reboucler (LAB_46D3C).
    # Nous gardons exactement cette machine â€” un tampon, une valeur, une
    # borne â€” mais au lieu d'une boucle bloquante on l'ouvre et on la ferme
    # avec les touches, comme le joueur ferait.

    TEXT_TRY_NUMBER = "TRY NUMBER "
    # les chaines de l'ecran de fin, prises dans le listing : la source
    # unique est `populous.endtext` depuis la Phase 83.
    TEXT_LOST = endtext.TEXT_LOST                # strLost       (L14441)
    TEXT_TRY_AGAIN = endtext.TEXT_TRY_IT_AGAIN   # strTryItAgain (L14449)

    def open_conquest_dialog(self) -> None:
        """Ouvre la saisie du numero de niveau (asm L11926-11971).

        Le tampon est initialise au palier courant, comme l'asm qui part de
        la valeur deja incrementee avant d'afficher Â« TRY NUMBER Â».
        """
        self.conquest_dialog = {
            "valeur": self.conquest_no,
            "tampon": str(self.conquest_no),
        }

    def close_conquest_dialog(self, valider: bool) -> bool:
        """Ferme la boite. ``valider`` charge le palier saisi.

        Renvoie vrai si le palier a ete charge. Une valeur hors de 1..99 est
        ramenee dans les bornes, comme le fait l'asm en bornant a 30000 puis
        en lisant l'entree dans ``level.dat``.
        """
        d = self.conquest_dialog
        self.conquest_dialog = None
        if not valider:
            return False
        n = max(1, min(99, d["valeur"]))
        self.conquest_no = n
        return self.load_conquest(n)

    def conquest_key(self, key: int, ch: str | None = None) -> bool:
        """Une frappe dans la boite Â« TRY NUMBER Â» (LAB_46D3C).

        * retour chariot -> validation ;
        * ``Echap``       -> annulation ;
        * ``Retour arriere`` -> efface le dernier chiffre ;
        * chiffre        -> s'ajoute a droite, valeur bornee a 30000.

        Renvoie vrai si la frappe a ete consommee.
        """
        d = self.conquest_dialog
        if d is None:
            return False
        if key == pygame.K_RETURN or key == pygame.K_KP_ENTER:
            self.close_conquest_dialog(True)
            return True
        if key == pygame.K_ESCAPE:
            self.close_conquest_dialog(False)
            return True
        if key == pygame.K_BACKSPACE:
            t = d["tampon"][:-1]
            d["tampon"] = t or ""
            d["valeur"] = int(t) if t else 0
            return True
        if ch and ch.isdigit():
            n = int(d["tampon"] + ch)
            if n > 30000:                  # CMPI.W #$7530, borne de l'asm
                n = 30000
            d["valeur"] = n
            d["tampon"] = str(n)
            return True
        return False

    def draw_conquest_dialog(self) -> None:
        """Dessine la boite de saisie â€” le `LAB_46F40` de l'asm en plus.

        L'asm ecrit le titre Â« TRY NUMBER Â» puis, apres validation, le nom du
        niveau en (0x40, 0x60). Ici les deux sont dans la meme boite, le
        numero saisi etant affiche a droite du titre.
        """
        d = self.conquest_dialog
        if d is None:
            return
        # meme cadre que l'asm : _requester(_d_screen, 0x30, 0x46, 0xE4, 0x40, ...)
        self.requester(0x30, 0x46, 0xE4, 0x40, self.TEXT_TRY_NUMBER,
                       d["tampon"])

    def draw_end_screen(self) -> None:
        """L'ecran de fin : `_end_game` (asm L14356-14389).

        **Une** boite et **sept** lignes — et non quatre boites : le
        listing appelle une seule fois
        ``_requester(_d_screen, $10, $10, $120, $A6, titre, NULL)``
        (L14356-14363) puis boucle sept ``_text`` (L14366-14389) sur les
        sept enregistrements de ``_end_text`` (L24790-24805), avec
        ``x + $10`` et ``y + $10``. Le tableau lui-meme est construit par
        :mod:`populous.endtext`, une fois pour toutes, dans
        :meth:`_end_game`.

        Les deux lignes d'en-tete de ``_won_conquest`` sont, elles, des
        ``_text`` nus en ``(8, $B2)`` et ``(8, $BA)`` (L14526/L14588) —
        elles passent **par-dessus** le tableau, puisque le listing les
        trace **apres** lui. Voir :meth:`draw_victory_screen`.

        **ECART de presentation** : dans l'original, la structure titre
        ``(-60,A5)`` n'est qu'une **zone de clic**, et ce que
        ``_requester`` affiche a sa place est l'etiquette ``OK`` de
        ``_end_ok+6`` (L24354). Le port, qui ne pose pas les boutons
        (ECART Phase 67), ecrit a la meme adresse le **libelle du bouton**,
        c'est-a-dire ``NEW GAME`` ou ``TRY IT AGAIN`` : plus lisible, et
        aucune donnee de jeu n'en depend.
        """
        if not self.game_ended or self.victory_speech:
            return
        self.requester(*endtext.END_BOITE, self.end_titre)
        for i, ligne in enumerate(self.end_lignes):
            self.ren.draw_text(self.frame, (endtext.END_X[i] + 0x10) // 8,
                               endtext.END_Y[i] + 0x10, ligne)
        if self.conquest is not None:
            # LAB_48F84 (L148C54) : `lord.pic` absent, le discours est saute
            # et l'ecran garde ce que `_end_game` avait trace.
            self.ren.draw_text(self.frame, 1, 0xB2, self.victory_texte[0])
            self.ren.draw_text(self.frame, 1, 0xBA, self.victory_texte[1])

    def tick(self) -> None:
        """Un pas de temps : ``_do_funny`` puis ``move_peeps``.

        Le listing enchaîne les deux appels (L680-681) sous **une meme paire
        de tests** : ``TST.W (_pause)`` puis ``TST.W (_paint_map)``, les deux
        nuls ( ;3e942- ;3e94c ). Sinon il va a ``LAB_3E95A``, qui redessine
        les peeps sans les faire bouger. Le port ne gardait pas cette garde :
        en pause ou en mode peinture la simulation continuait. Les appels qui
        suivent dans la boucle d'image (``_get_message`` a ``LAB_3EC88``) ne
        sont pas sous la garde, d'ou ``_run_commands`` **apres**.

        ``move_peeps`` avance lui-meme ``game_turn``/``toggle`` ET appelle
        ``set_frame`` exactement aux endroits de l'asm. Il ne faut surtout pas
        ajouter un second ``set_frame`` ici : la machine d'animation
        (« frames 0..6 puis transition ») ne se produirait jamais.
        Le canal de commandes est joue ensuite, comme dans l'asm (L1011).
        """
        sim = self.sim
        if not sim.pause and not sim.paint_map:        # ;3e942- ;3e94c
            sim.do_funny()                             # ;3e94e
            sim.move_peeps()                           # ;3e952
        self._run_commands()
        self._check_end()

    def image(self) -> None:
        """Une image complete, dans l'ordre de la boucle d'image (L962-1013).

        On sort de la simulation tant que l'ecran de fin est affiche : l'asm
        fait de meme, sa boucle d'ecran s'arrêtant sur l'ecran de fin.
        """
        if self.game_ended:
            self._update_victory_screen()
            self.compose()
            return
        self.tick()
        self._audio()
        self.compose()

    def _return_to_game(self) -> None:
        """`___return_to_game` (L13954, L13960, L18938) : retour d'une boite modale.

        L'asm y met `left_button = 2` (bouton stable/relache) pour eviter le
        rebond au retour dans la boucle principale.
        """
        self.left_button = 2

    # ------------------------------------------------- fin de partie (L4323)
    def _check_end(self) -> None:
        """Le test de fin de partie — asm L4323-4352, appele chaque tour.

        L'asm compare ``good_pop``, c'est-a-dire la **population** (la somme
        des vies), et non le nombre d'habitants :

        * ``good_pop[joueur] == 0`` ou ``_surender == joueur``
          -> ``_end_game(1)`` : le joueur a **perdu** ;
        * sinon ``good_pop[adv] == 0`` ou ``_surender == adv``
          -> ``_end_game(0)`` : le joueur a **gagne**.

        Le parametre n'est donc pas un booleen « gagne » : l'asm teste
        ``CMPI.W #$0001,(8,A5)`` et ecrit `"LOST"` quand il vaut 1
        (L14027-14029). Notre ``_end_game(perdu)`` garde cette convention.
        """
        if self.game_ended:
            return
        p, a = self.sim.player, self.sim.not_player
        pop_j = self.sim.population(p)
        pop_a = self.sim.population(a)
        if pop_j == 0 or self.surrender == p:
            self._end_game(True)          # `_end_game(1)` -> « LOST »
        elif pop_a == 0 or self.surrender == a:
            self._end_game(False)         # `_end_game(0)` -> « WON »

    def _end_game(self, perdu: bool) -> None:
        """``_end_game(gagne)`` : l'ecran de fin (asm L14019, puis L14416).

        L'asm **attend un clic** avant d'enchainer sur `_won_conquest` : la
        simulation s'arrete, l'ecran s'affiche, puis le joueur valide. On
        reproduit cet ordre : `_check_end` fige la partie, `compose` trace
        l'ecran, et `_next_conquest` n'est appele qu'a la validation.

        En conquete, le prochain palier est calcule immediatement pour que le
        texte puisse etre affiche — c'est ce que fait `_won_conquest`, qui
        appelle `strcpy`/`strcat` avant d'attendre.
        """
        if self.game_ended:
            return
        self.game_ended = True
        # l'argument de l'asm est 1 = le joueur a perdu (« LOST », L14029).
        self.victory = not perdu
        # L14021-14340 : la boucle `i = 0..6` construit les sept chaines du
        # tableau des scores **avant** de poser la boite, et le calcul du
        # score (L14204-14271) y est inclus : `_score` est donc deja le
        # bon quand `_won_conquest(score)` est appele a L14416.
        self.end_titre, self.end_lignes, self.score = endtext.construire(
            perdu, self.sim, self.score,
            -1 if self.conquest is None else self.conquest_no)
        if self.conquest is not None:
            # L14412 : `_won_conquest(score)`.
            self.score += self.sim.population(self.sim.player)
            nouveau, self.conquest_fini = nouveau_niveau(
                self.conquest_no - 1, self.score)
            # L14497 : `_seed = _level_number` — le relief est regenere, donc
            # on ramene l'index dans les 99 paliers que contient level.dat.
            self.conquest_next = (nouveau % 99) + 1
            # `(-114,A5) = _level_number / 250` (L148CAE-148CB8) : l'index de
            # monde, qui selectionne les deux mots de `_words` a dire.
            self.victory_world = nouveau // PALIER_NOMS
            # L148D1C : `_code(newrand())` — le nom du monde de la seconde
            # ligne. Un seul tirage, fait ici, pour que l'ecran reste stable.
            self.victory_graine = self.sim.rng.raw() & 0xFFFF
            # Les deux lignes de `_text`, assemblees une seule fois
            # (L14520-14589) et relues telles quelles a chaque image.
            self.victory_texte = texte_fin(
                self.conquest_no - 1, self.conquest_fini,
                self._message, self.victory_graine)

        # `_won_conquest` n'est appele que sur une **victoire en conquete**
        # (L14408-14416 : `TST.W (8,A5)` doit valoir 0 — pas de defaite — et
        # `_in_conquest != -1`). C'est la seule entree du discours.
        if not perdu and self.conquest is not None:
            self._init_victory_screen()

    def _init_victory_screen(self) -> None:
        """``_won_conquest`` : l'ecran du Seigneur (L148C2E-148DC2).

        L'ordre exact du listing :

        1. L148C2E-148C3E : ``_music_off`` et ``_effect_off`` sont sauvegardes
           dans ``(-116)`` / ``(-118)`` puis remis a **zero**, ce qui, chez
           l'asm, *ouvre* les deux bascules (voir ``music_on``) ;
        2. L148C42-148C48 : ``_kill_effect(0, 4)`` — les quatre voies d'effet
           sont coupees ;
        3. L148C4E : ``_read_lord()``. S'il rend zero, l'asm saute a
           ``LAB_48F84`` (L148C54) : **tout le discours saute**, le niveau
           avance est annule (``_level_number = (-106)``) et
           ``_message[0] = 0`` ;
        4. L148C58 : ``_read_mouth()`` — les 5040 octets de ``mouths.pic``
           dans ``_map_steps`` ;
        5. L148C5C-148C68 : ``_free_all_sounds()`` puis
           ``_load_sound("gwords")`` : la banque d'effets est remplacee par
           celle du discours pendant toute la boucle, et restauree en sortie
           (``"gmusic1"``, L148F74-148F7C) ;
        6. L148C6A : ``_seed`` est remis a ``(-106)`` = l'ancien niveau ;
        7. L148C76-148D32 : le texte d'en-tete, ecrit **dans le portrait** ;
        8. L148D5A-148D8A : ``_tcmap[i+16] = _palette[i]`` pour ``i`` dans
           ``0..15``, puis ``_make_copper`` et ``_show_screen`` : le cuivre
           est mis en place **une fois pour toutes**. Il n'y a **aucun**
           cycle de palette pendant la boucle ;
        9. L148DB2-148DC2 : ``_left_button = 2`` et zero des trois compteurs.

        Le port n'a qu'un seul paquet d'effets : l'etape 5 se reduit a laisser
        la musique se taire (``image`` n'appelle pas ``_audio`` pendant le
        discours) et les effets viennent du paquet synthetise — ECART connu,
        depose depuis la Phase 10.
        """
        from populous.assets import load_mouths, load_portrait
        self.victory_speech = False
        self.victory_eyes = False
        portrait = load_portrait()                    # `_read_lord`, L16631
        if portrait is None:                          # LAB_48F84, L14760-14762
            self.conquest_next = 0                    # `_level_number = (-106)`
            self._message = ""                        # `CLR.B (_message)`
            return
        self.victory_speech = True
        fond, pal = portrait
        self.victory_fond = fond                      # `_w_screen`, 320x200
        self.victory_pal = pal                        # `_tcmap[0..15]`
        self.victory_mouths = load_mouths(pal)        # `_read_mouth`, L16668
        # (1) les deux bascules sont sauvegarees puis ouvertes ; (2) les
        # quatre voies sont coupees (`_kill_effect(0, 4)`).
        self.victory_music, self.music_on = self.music_on, 1
        self.victory_effect, self.effect_on = self.effect_on, 1
        self.sound.kill_effect(0, 4)                  # L148C48
        self.maj_musique()                            # ECART Phase 86 : BGM.mp3
        # (9) L148DB2-148DC2
        self.left_button = 2
        self.victory_dir = 1                          # (-110,A5)
        self.victory_mouth = 0                        # (-108,A5)
        self.victory_counter = 0                      # (-120,A5)
        self.victory_flag = self.conquest_fini        # (-122,A5)
        self.victory_vblank = 0

    def _update_victory_screen(self) -> None:
        """La boucle d'attente de ``_won_conquest`` (L148DC6-148F46), une image.

        Une iteration de l'asm = quatre vblanks (les quatre ``_waittof`` de
        L148EF2-148EFE) : le port compte les images et ne fait rien quatre
        fois sur cinq. Le test de clic est en tete de boucle (L148DC6), donc
        aussi une fois par iteration — c'est fiable parce que ``_mouse``
        (L19582-19589) maintient ``_left_button`` a zero tant que le bouton
        est enfonce.

        Le corps, dans l'ordre du listing :

        * **mode termine** (``(-122) != 0``, L148DCE-148E56) : pour
          ``10 <= c <= 14``, un mot de ``_end_words[c-10]`` n'est dit que si
          la voie 2 est libre ; sinon ``c`` est ramene a 0 au dela de 200,
          les **yeux** (bouche n. 5) sont poses une fois pour toutes quand
          ``c == 16``, puis ``c`` avance et la bouche revient a 0 ;
        * **mode courant** (L148E5A-148EE4) : ``c == 10`` dit l'effet 0,
          ``c`` vaut 11 ou 12 dit ``_words[monde*2 + c - 11]`` si le mot est
          positif, et ``c`` est ramene a 0 au dela de 250 ;
        * **commun** (L148EF2-148F42) : la bouche ``(-108)`` est redessinee,
          puis — et seulement si ``_check_effect(2)`` est **nul**, c'est-a-
          dire si la voie sonne encore — elle oscille entre 0 et 4 en
          rebroussant ``(-110)`` aux bornes.
        """
        if not self.game_ended:
            return
        # `_mouse` tourne dans le VBI meme pendant cette boucle (L19579-19591)
        # : c'est lui qui met `_left_button` a 0 au clic. Pendant le discours,
        # la boucle d'image est arretee, donc c'est ici qu'il faut le lire.
        self._read_buttons()
        if not self.victory_speech:
            # LAB_48F84 (L148C54) : pas de `lord.pic`, donc pas de boucle de
            # discours — mais l'attente de clic de `_end_game` reste
            # (L14392-14403), et c'est elle qui enchaîne.
            if self.left_button == 0:
                self.left_button = 2
                self._return_to_game()
                self._next_conquest()
            return
        self.victory_vblank += 1
        if self.victory_vblank < 4:                   # les 4 `_waittof`
            return
        self.victory_vblank = 0
        # LAB_48DC6 : le test de sortie est en tete de boucle.
        if self.left_button == 0:                     # LAB_48F4A, L148F4A
            self.left_button = 2                      # L148F4A
            self.sound.kill_effect(0, 4)              # `_kill_effect(0, 4)`
            self.music_on, self.effect_on = (
                self.victory_music, self.victory_effect)   # L148F8E-148F94
            self.maj_musique()                         # ECART Phase 86
            self.victory_speech = False
            self._return_to_game()
            self._next_conquest()
            return

        c = self.victory_counter
        if self.victory_flag:                         # L148DCE : (-122,A5)
            if 10 <= c <= 14:                         # L148DD6-148DE4
                if self.sound.check_effect(2):        # `_check_effect(2)`
                    self.sound.play(END_WORDS[c - 10], 2)
                    self.victory_counter = c + 1      # L148E12
            else:                                     # LAB_48E18
                if c > 200:                           # L148E18-148E20
                    c = 0
                if c == 16:                           # L148E24-148E44
                    self.victory_eyes = True          # bouche n. 5, (16, 75)
                self.victory_counter = c + 1          # L148E48
                self.victory_mouth = 0                # L148E4C
                self.victory_dir = 1                  # L148E50
        else:                                         # LAB_48E5A
            if 10 <= c <= 12:                         # L148E5A-148E68
                if c == 10:                           # L148E6A-148E7E
                    self.sound.play(0, 2)             # `_PlaySound(0, 2)`
                    self.victory_counter = c + 1
                elif self.sound.check_effect(2):      # L148E84-148E90
                    mot = WORDS[self.victory_world * 2 + c - 11]
                    if mot >= 0:                      # L148EA8-148EAC
                        self.sound.play(mot, 2)
                    self.victory_counter = c + 1      # L148ED2
            else:                                     # LAB_48ED8
                if c > 250:                           # L148ED8-148EE0
                    c = 0
                self.victory_counter = c + 1          # L148EE4
                self.victory_mouth = 0                # L148EE8
                self.victory_dir = 1                  # L148EEC

        # LAB_48EF2 : la bouche est redessinee a chaque iteration, et
        # n'oscille que si `_check_effect(2)` rend **zero**, c'est-a-dire
        # tant que la voie 2 sonne encore (L148F2C-148F42).
        if not self.sound.check_effect(2):
            self.victory_mouth += self.victory_dir
            if self.victory_mouth >= 4 or self.victory_mouth <= 0:
                self.victory_dir = -self.victory_dir

    def draw_victory_screen(self) -> None:
        """Le portrait du Seigneur, sa bouche et ses yeux.

        `_draw_mouth(ecran, x, y, compte, bouche)` (L19894) recopie
        ``compte`` lignes de 48 pixels dans ``_w_screen`` en partant de la
        ligne ``y`` et de la colonne ``x``. Les deux appels du listing sont :

        * les **yeux** (bouche n. 5) en `x = $10, y = $4B` — L14652-14658, une
          seule fois, quand le compteur passe a 16 dans la branche « mode
          termine ». Comme l'asm ecrit dans l'ecran affiche, les yeux
          **restent** ensuite ;
        * la **bouche** en `x = $12, y = $87` — L14721-14727, a **chaque**
          iteration. Les 35 lignes couvrent exactement les 35 lignes de
          l'image precedente, si bien qu'osciller entre les bouches 0..4
          donne l'impression d'une bouche qui parle.

        **`x` est un offset d'octets, pas de pixels.** `_draw_mouth` fait
        `ADDA.L D0,A0` directement (L19900), la ou `_text` fait d'abord
        `LSR.W #3` (L19978). Comme une ligne fait `$28 = 40` octets, soit
        320 pixels, `$10` vaut 128 pixels et `$12` vaut 144 — c'est ce qui
        met la bouche sur la bouche du portrait.

        Les deux lignes d'en-tete sont des `_text` **nus** — contrairement a
        la **seule** boite de `_end_game` — ecrites une fois pour toutes dans
        ``_w_screen`` avant `_show_screen` (L14526, L14559, L14588). Le port
        les redessine a chaque image sur le meme fond, ce qui revient au
        meme puisque rien d'autre ne change. Ici, en revanche, `x` **est**
        en pixels : c'est le listing qui divise.

        Sans ``lord.pic`` (ou hors conquete), on retombe sur le tableau des
        scores seul : c'est le chemin ``LAB_48F84``, ou l'asm n'affiche que
        ce qu'avait dessine ``_end_game``.
        """
        if not self.game_ended:
            return
        if not self.victory_speech:
            self.draw_end_screen()
            return
        self.frame.blit(self.victory_fond, (0, 0))
        # `_draw_mouth` ajoute `x` **en octets** (`ADDA.L D0,A0`, L19900) :
        # `$12` -> 18 x 8 = 144 pixels, `$10` -> 16 x 8 = 128 pixels. `y`,
        # lui, est deja en lignes (`MULU #$0028`).
        self.frame.blit(self.victory_mouths[self.victory_mouth],
                        (BLOC_X * 8, BLOC_Y))
        if self.victory_eyes:
            self.frame.blit(self.victory_mouths[5], (YEUX_X * 8, YEUX_Y))
        # `_text(_w_screen, 8, 0xB2, s)` et `_text(_w_screen, 8, 0xBA, s)` :
        # le listing lit `x` **en pixels** et en derive un offset d'octet par
        # ``LSR.W #3`` (L19978), alors que `draw_text` compte en unites de
        # 8 px — d'ou `8 >> 3`. Les glyphes sont rendus dans ``_tcmap`` :
        # c'est la palette du portrait, pas celle du jeu.
        self.ren.draw_text(self.frame, 8 >> 3, 0xB2, self.victory_texte[0],
                           self.victory_pal)
        self.ren.draw_text(self.frame, 8 >> 3, 0xBA, self.victory_texte[1],
                           self.victory_pal)

    def _next_conquest(self) -> None:
        """Passe au palier suivant — la validation de l'ecran de fin.

        L'asm rappelle `_won_conquest` puis `_show_world`, ce qui regenere la
        carte avec `_seed = _level_number`.
        """
        if self.conquest is not None and self.conquest_next:
            self.conquest_no = self.conquest_next
            self.load_conquest(self.conquest_no)
        self.game_ended = False
        self.victory = False
        self.conquest_next = 0

    # -------------------------------------------------------------- affichage
    def _run_commands(self) -> None:
        """Fin de tour : periode, IA ennemie, puis le canal execute.

        L'asm appelle cette boucle de messages **avant** `_move_peeps`
        (L17929-18230) ; le port l'appelle apres, ce qui decale d'un tour
        `ai_choose` et les extrema (ECART note en Phase 57, non corrige
        ici). L'ordre interne, lui, est celui du listing.
        """
        sim = self.sim
        # L17934-17951 : la boucle de messages vide `queued` pour chaque
        # tribu dont `can_build == 1`, quand `game_turn % period == 0`.
        # C'est le SEUL vidage de `queued` de tout le listing :
        # `_clear_send` (L18234-18254) ne touche qu'a `act/p1/p2`. Une
        # tribu humaine (`can_build == 0`) garde donc `queued == 1` pour
        # toujours, ce qui eteint toute son IA.
        # `DIVU` par zero piégerait le 68000 : le test `period != 0`
        # empeche le crash sans changer le comportement, le `.data`
        # portant 1 et 3 (L24188 / L24226).
        for t in (0, 1):
            st = sim.stats[t]
            if st.can_build == 1 and st.period != 0 and (
                    sim.game_turn % st.period == 0):
                st.queued = 0
        self.powers.ai_choose(sim.not_player)
        for t in (sim.player, sim.not_player):
            self._safe_dispatch(t)
        # `sim.effect` n'est pose que dans deux cas rares ; on le recopie
        # dans le mot global `_effect`, que l'horloge audio consomme a la
        # fin de l'image (comme le fait l'asm, L19635).
        if self.sim.effect:
            self.effect = self.sim.effect

    def _audio(self) -> None:
        """La partie sonore de l'image — asm L19620-19673.

        Appelee **une fois par image**, depuis `run`. C'est ici que
        l'asm consomme `_effect`, joue la mesure et le tic du tempo ; le
        simulation ne fait que **ecrire** le mot `_effect`.
        """
        # le tempo depend des deux populations (L557-603)
        self.music.suivre(self.sim.population(self.sim.player),
                          self.sim.population(self.sim.not_player))
        self.music.image(self)

    def compose(self) -> None:
        """Une image, dans l'ordre exact de la boucle d'image (L604-657).

        1. fond = qaz.pic, avec la mini-carte ecrite **en place** dans
           ``_back_scr`` (elle y reste d'une image a l'autre) ;
        1bis. ``_move_mana`` (L622) — appele entre ``__clr_wsc`` et
           ``__draw_it`` ;
        2. ``_draw_it`` : les 3 passes de la fenetre 8x8 ;
        3. la file ``_sprite[]`` remplie par ``_move_sprite`` ;
        4. le curseur de ``_sculpt`` (sprite 0x54, dessine par la fonte
           elle-meme avant la boucle de sprites — cf. L7440-7449) ;
        5. ``_show_the_shield`` puis les jauges de population (L403F4) ;
        6. la barre de population du joueur.
        """
        if self.game_ended:
            self.draw_victory_screen()
            return
        # L604-609 : `_toggle` bascule **une fois par image**, juste avant
        # `__clr_wsc` (L611). C'est lui qui anime la mer — `_draw_it`
        # (L15817-15822) substitue la tuile 16 a la tuile 0 lorsque
        # `_toggle == 0` — et qui choisit le sprite du blason (L2894) et
        # de l'habitant immobile (L16054). Sans cette bascule la mer reste
        # figee sur la tuile 16 : l'ecart que decrivait le joueur.
        self.ren.toggle ^= 1
        self.frame.blit(self.backdrop, (0, 0))
        self._apply_icon_toggles()          # etat persistant des icones (_back_scr)
        self.ren.draw_minimap(self.frame, self.terrain, colours=self.colours, sim=self.sim, xoff=self.xoff, yoff=self.yoff)
        self.move_mana()                    # L622 : avant __draw_it
        self.ren.draw_window(self.frame, self.terrain, self.xoff, self.yoff)
        self.ren.draw_peeps(self.frame, self.terrain, self.xoff, self.yoff,
                            self.sim)
        # Sur l'Amiga le pointeur est un **sprite materiel** que gere
        # l'OS : le jeu ne le dessine pas, il se contente de le laisser
        # en place. `_sculpt` (L7440-7449) n'ajoute a l'ecran que son
        # propre sprite 0x54, et seulement quand un pouvoir de relief est
        # arme (L966, appele depuis `LAB_3EC20` quand `mode & 0x0E`).
        #
        # Le port n'a pas ce sprite materiel : il substitue la fleche de
        # pygame. Il faut donc **masquer** celle-ci des que le jeu trace
        # son propre curseur, sans quoi l'on voit deux pointeurs.
        pygame.mouse.set_visible(self.sim.cur_screen is None)
        self._draw_cursor()
        if self.sim.game_turn == 0x1000:        # L752-753
            # L755-757 : `_start_seed & 3`, un seul mot pousse ; ($A,A5)
            # n'est pas fourni - decision de phase 56.
            self.sim.do_place_funny(self.seed & 3, 0)
        self.show_the_shield()
        self.draw_pop_gauge()
        self.draw_conquest_dialog()
        self.draw_end_screen()
        self._draw_hud()

    # ------------------------------------------- _clear_all_map (L6926-6963)
    def clear_all_map(self) -> None:
        """``_clear_all_map`` — le code 12 de ``_do_action`` (``LAB_4C124``).

        Trois temps, dans l'ordre du listing :

        1. une boucle de **4225** iterations (`CMP.W #$1081,D4 / BLT`) qui
           vide chaque mot de `_alt` (`D0 = D4<<1`, `CLR.W`), et — seulement
           quand `D4 < $1000`, le `CMP.W #$1000 / BGE` les sautant — chaque
           octet de `_map_who`, `_map_bk2` et `_map_blk`. `_map_alt` n'y
           passe **pas** : c'est `_make_map` plus bas qui le recalcule.
        2. `for (i = 0; i < _no_peeps; i++) _zero_population(&peeps[i], i)`,
           puis `_no_peeps = 0`.
        3. `_make_map(0, 0, $3F, $3F)` puis `_draw_map(0, 0, $3F, $3F)`.

        Les quatre mots empiles avant chaque appel sont `0, 0, $3F, $3F`
        (le dernier empile est celui de l'offset 8), donc `(x0, y0, x1,
        y1)` — bien l'integralite de la carte.

        **_start_of_game == 0** (L1026-1035) : avant le nettoyage,
        `_set_mode_icons(1, 6)` et `_set_tend_icons(3, 4)`.
        """
        # L1026-1035 : _start_of_game == 0 -> pose icones mode/tend
        if self.start_of_game == 0:
            self.set_mode_icons(1, 6)
            self.set_tend_icons(3, 4)

        sim = self.sim
        terr = self.terrain
        alt, who = terr.alt, terr.who
        blk, bk2 = terr.blk, terr.bk2
        for d4 in range(len(alt)):                 # 4225 = CMP.W #$1081
            alt[d4] = 0                            # CLR.W (_alt, D4*2)
            if d4 < len(who):                      # 4096 = CMP.W #$1000
                who[d4] = 0                        # CLR.B (_map_who, D4)
                bk2[d4] = 0                        # CLR.B (_map_bk2, D4)
                blk[d4] = 0                        # CLR.B (_map_blk, D4)
        for d4 in range(sim.no_peeps):             # LAB_43118-43134
            sim.zero_population(d4)
        sim.no_peeps = 0                           # CLR.W (_no_peeps)
        terr.make_map(0, 0, 0x3F, 0x3F)            # ___make_map
        self.ren.draw_minimap(self.frame, self.terrain,
                              colours=self.colours, sim=self.sim,
                              xoff=self.xoff, yoff=self.yoff)   # ___draw_map

# ------------------------------------------- _show_the_shield (asm L2769)
    # Le Â« bouclier Â» : le panneau de l'habitant selectionne dans
    # ``_view_who``. L'asm le dessine dans ``_w_screen`` (le fond), pas dans
    # ``_d_screen`` (la fenetre 8x8 du terrain) â€” d'ou la difference avec le
    # reste de l'interface de jeu. Comme notre fond est deja compose, on
    # dessine par-dessus apres le terrain : meme resultat visuel.
    #
    # Offsets du peep utilises (cf. docs/game_logic.md) :
    #     +0x00 state    +0x01 tribu   +0x03 armes   +0x04 vie
    #     +0x06 w6       +0x08 block   +0x0C frame   +0x0E cible
    def show_the_shield(self) -> None:
        """Dessine le panneau de l'habitant suivi â€” exactement ``_show_the_shield``.

        Structure fidele :

        * L2772 ``_view_who == 0``            -> rien ;
        * L2780 ``life <= 0``                  -> on oublie l'habitant ;
        * L2790 ``_draw_icon(x=0x11, y=4, icone=tribu)``  le blason ;
        * L2796 recherche de l'arme dans ``_weapons_order[1..10]`` ;
        * L2815 ``_draw_icon(x=0x12, y=4, icone=i+1)``    l'icone d'arme ;
        * L2823 ``state & 8`` (combattant)   -> sprite + 2 barres ($0F/$08) ;
        * L2889 ``state == 1`` (villageois)  -> sprite + 2 barres ($0A/$0C) ;
        * L2965 repli                        -> sprite + 2 barres ($0A/$09
          ou $09/$09 selon la magnitude de ``life``).

        Les trois branches dessinent **toutes** un sprite en (272, 22) —
        sauf le villageois, en (268, 22) — puis les deux barres de
        ``_bars``. L'ecusson est suivi par L3092-L3145, les deux jauges
        de population.
        """
        sim = self.sim
        who = sim.view_who
        if not who or who > len(sim.peeps):
            return
        p = sim.peeps[who - 1]
        if p.life <= 0:
            sim.view_who = 0
            return

        r, d = self.ren, self.frame

        # L2790 : le blason de la tribu â€” l'icone 0x11 est le rectangle plein
        # qui sert de fond au panneau.
        r.draw_icon(d, 0x11, 0x04, p.tribe & 1)

        # L2796 : l'arme, cherchee dans _weapons_order (1..10)
        i = 1
        while i <= 10 and sim.weapons_order[i] != p.weapons:
            i += 1
        # L2815-2821 : l'icone d'arme. L'ordre de push est (icone, y, x,
        # ecran) — donc l'ordre d'appel est (ecran, x, y, icone) :
        # `_draw_icon(_w_screen, x=0x12, y=0x04, icone=i+1)`. `x` est en
        # unites de 16 px (render.py L216) : l'arme tombe en (288, 4),
        # a cote du blason en (272, 4). Le code passait `i+1` en **y** et
        # `4` en icone : l'icone tracee etait toujours la 4, decalee
        # verticalement selon l'arme.
        if i < 11:
            r.draw_icon(d, 0x12, 0x04, i + 1)

        # ---- L2823 : combattant (bit 3 de l'etat) ------------------------
        if p.state & 0x08:
            # L2826 : le sprite du combattant, x=$110 (272 px), y=$16 (22)
            self._draw_sprite_at(0x110, 0x16, p.frame)
            # L2832-2847 : les deux pointeurs du duel. Si `tribu == 0`,
            # -10(A5) = A2 (le suivi) et -14(A5) = l'adversaire ; sinon
            # c'est l'inverse. Autrement dit **-10 est toujours le peep
            # de tribu 0 et -14 celui de tribu 1** : la barre de gauche
            # (x=$24, drapeaux $0F) est celle de la tribu 0, celle de
            # droite (x=$25, drapeaux $08) celle de la tribu 1, comme les
            # deux jauges de population.
            adv = (sim.peeps[p.w6]
                   if 0 <= p.w6 < len(sim.peeps) else None)
            if p.tribe == 0:
                a, b = p, adv
            else:
                a, b = adv, p
            # L2849-2869 : rempli = vie*16 / (vie_a + vie_b), deux fois.
            # La somme est calculee en **mot** (`ADD.W` puis `EXT.L`,
            # L2853-2857) et les vies etendues avec signe (`EXT.L`) ; le
            # quotient vient de `_divs` (troncature vers zero).
            va = m68k.to_long_word(a.life) if a else 0
            vb = m68k.to_long_word(b.life) if b else 0
            somme = m68k.to_long_word(va + vb)
            f1 = m68k.divs_long(va << 4, somme)
            f2 = m68k.divs_long(vb << 4, somme)
            # L2871-2885 : hauteur $10 partout, y=$25 ; barre 1 drapeaux
            # $0F, barre 2 drapeaux $08 (et non $0F).
            self._bars(f1, 0x0F, f2, 0x08)
            return

        # ---- L2889 : villageois (`CMPI.B #$01,(A2)`) ----------------------
        # Le test porte sur **byte 0 = `state`**, pas sur `tribe`. Trois
        # lectures de bytes sur A2 le confirment, et les trois cadrent avec
        # nos constantes :
        #     BTST  #3,(A2)      -> ST_BATTLE  = 0x08   (notre `state & 0x08`)
        #     CMPI.B #$01,(A2)   -> ST_VILLAGER= 0x01   <-- ce branchement
        #     MOVE.B (3,A2),D1   -> `weapons`  (compare a _weapons_order)
        # Le code testait `p.tribe == 1` : les villageois de la tribu 0
        # n'avaient donc jamais leur ligne, et tous les peeps de la tribu 1
        # l'avaient, quelle que soit leur etat.
        if p.state == ST_VILLAGER:
            # L2891-2901 : sprite = (tribe << 1) + _toggle + $40, trace en
            # ($10C, $16) = (268, 22). L'ordre de push est (sprite, y, x,
            # ecran), donc l'ordre d'appel est (ecran, x, y, sprite).
            sprite = ((p.tribe << 1) + self.ren.toggle + 0x40) & 0xFFFF
            self._draw_sprite_at(0x10C, 0x16, sprite)
            # L2902-2911 : la vie « reelle » (`_check_life(tribu, block)`),
            # stockee en -6(A5), et un zero remplace par 1 (division !).
            vie = m68k.to_word(sim.check_life(p.tribe, p.block))
            if vie == 0:
                vie = 1
            # L2913-2938 : barre 1, drapeaux $0A, x=$24, y=$25, h=$10.
            # `vie == $0BEA` (3050) est le cas « plein » : rempli $10.
            # Sinon DIVU ($0131 = 305) : rempli = (vie << 4) / 305.
            # Le `SWAP/CLR.W/SWAP` de L2928-2930 est l'idiome 68000
            # d'extension nulle d'un mot apres son `ASL.W #4` : le mot bas
            # vaut (vie*16) & $FFFF, le haut est mis a zero.
            if vie == 0x0BEA:
                f1 = 0x10
            else:
                f1 = ((vie << 4) & 0xFFFF) // 0x131
            # L2940-2955 : barre 2, drapeaux $0C, x=$25 : la meme DIVU par
            # `vie`, sur la vie stockee `(4,A2) << 4`, et bornage en
            # **mot signe** — `CMP.W #$0010 / BLE` puis `TST.W / BGE` sont
            # des tests signes (L2948-2954). Un quotient > 32767 devient
            # donc negatif en mot et retombe a 0, pas a $10.
            q = m68k.to_word((p.life << 4)) // vie
            f2 = m68k.s16(q)
            if f2 > 0x10:
                f2 = 0x10
            if f2 < 0:
                f2 = 0
            self._bars(f1, 0x0A, f2, 0x0C)
            return

        # ---- L2965 : repli -------------------------------------------------
        # Trois sous-cas, tous deux tests sur **l'etat** et non sur le peep.
        if p.state & 0x60:
            # L2969-2981 : si cible (TST.L ($E,A2)) $7D, sinon $65 ; puis
            # + (tribe << 1) + _toggle.
            base = 0x7D if p.target != -1 else 0x65
            sprite = (base + (p.tribe << 1) + self.ren.toggle) & 0xFFFF
        elif p.state & 0x10:
            # L2985-2999 : si cible $6D, sinon $5D ; puis + (tribe << 2)
            # + (_game_turn & 3) — l'animation a 4 images.
            base = 0x6D if p.target != -1 else 0x5D
            sprite = (base + (p.tribe << 2)
                      + (self.sim.game_turn & 3)) & 0xFFFF
        else:
            # L3000-3031 : la direction. On cherche `prev_block` (offset
            # $A) dans `_dir_sprite` ; l'indice retenu est borne a 7, et
            # **4** quand la recherche echoue.
            #
            # La boucle asm va de 0 a 8 (`CMP.W #9 / BGE`) : elle lit
            # l'indice 8, au-dela des 8 entrees du tableau. C'est inutile,
            # et la suite le prouve — `CMP.W #7 / BLE`, sinon D4 = 4 — :
            # un indice 8 ou 9 est remplace par 4 quoi qu'il arrive. On
            # ne cherche donc que dans les 8 entrees reelles, sans perte.
            index = 4
            for k, delta in enumerate(DIR_SPRITE):
                # `CMP.W ($A,A2),D1` (L3013) compare des **motifs de 16
                # bits** : on ramene donc les deux cotes a un mot, et non
                # `prev_block` (stocke en signe, sim.py L1443) a un non-
                # signe — -65 s'ecrit $BFBF et ne vaut jamais 65471.
                if (m68k.to_word(delta) == m68k.to_word(p.prev_block)):
                    index = k
                    break
            # L3020-3031 : D4 = index*2, + _toggle, + $20 si cible,
            # + (tribe << 4).
            sprite = (index * 2 + self.ren.toggle) & 0xFFFF
            if p.target != -1:
                sprite = (sprite + 0x20) & 0xFFFF
            sprite = (sprite + (p.tribe << 4)) & 0xFFFF
        # L3033-3037 : ce sprite est trace en ($110, $16) = (272, 22) —
        # sous le blason. Le port l'oubliait : les trois sous-cas ne
        # dessinaient rien et se contentaient des deux barres.
        self._draw_sprite_at(0x110, 0x16, sprite)
        # L3039-3091 : les deux barres, d'apres la magnitude de `life`.
        life = m68k.to_word(p.life)
        if life > 0x1000:
            # L3042-3064 : DIVS #$0400 — barre 1 quotient (drapeaux $0A),
            # barre 2 reste (drapeaux $09).
            f1 = m68k.divs_long(life, 0x400)
            f2 = m68k.to_word(life - (f1 * 0x400))
            self._bars(f1, 0x0A, f2, 0x09)
        else:
            # L3067-3090 : DIVS #$0100, puis le reste divise par $10 —
            # deux fois drapeaux $09.
            f1 = m68k.divs_long(life, 0x100)
            reste = m68k.to_word(life - (f1 * 0x100))
            f2 = m68k.divs_long(reste, 0x10)
            self._bars(f1, 0x09, f2, 0x09)

    def move_mana(self) -> None:
        """``_move_mana`` (L3164-3241) — le curseur de la jauge de mana.

        Appele **chaque image**, juste avant `__draw_it` (L622 : entre
        `__clr_wsc` et la fenetre 8x8). `render.py` n'en contient aucune
        trace : la jauge n'existait pas dans le port.

        .. code-block:: none

            D4 = 0
            LAB_404DA : D2 = mana ; D1 = _mana_values[D4]      ; longs
                        BGT -> D4 += 1  (tant que mana > v[D4])
            CMP.W #9,D4 / BGT -> sprite fixe
            sinon :
                D0 = mana - v[D4-1]                            ; SUB.L
                D0 = D0 << 3  (* 8)                            ; ASL.L #3
                D1 = v[D4] - v[D4-1]                           ; SUB.L
                D0 = _divs(D0, D1)                             ; L40544
                D5 = D0                                        ; MOVE.W D0,D5
                y = (D4-1)*8  + D5 + 8                         ; mot, ASL.W #3
                x = (D4-1)*16 + D5*2 + $A0                     ; mot, ASL.W #4
                _draw_sprite(_w_screen, x, y, $45)

        **Les deux lectures hors table**, les deux relevees dans le listing
        plutot que devinees :

        * ``D4 == 0`` (jamais atteint : `mana` est plancher a -250 par
          `sim.py:594` et demarre a 399, donc il faudrait `mana == -250`)
          fait ``SUBQ.W #1`` -> indice -1, soit **4 octets avant** la table :
          adresse $51870, qui tombe dans `_big_city` (`DC.W $0029` a $51872).
          Les 4 octets valent donc ``$00290029``.
        * ``D4 == 11`` (`mana > 2 000 063`) lirait `_prot_num2 = $E0ED80A7`,
          qui est **negatif** : `mana > v[11]` serait vrai, D4 vaudrait 12,
          puis 13... la boucle partirait en fuite sur la memoire. On
          l'arrete a la fin de la table. C'est **observ equivalent**, pas un
          raccourci : D4 ne fait qu'augmenter et la sortie est ``D4 > 9``,
          donc des que D4 atteint 11 le resultat est le meme, branche
          « sprite fixe » dans les deux cas.
        """
        sim = self.sim
        mana = sim.players[sim.player].mana

        d4 = 0
        while d4 < len(MANA_VALUES) and mana > MANA_VALUES[d4]:
            d4 += 1
        if d4 > 9:                                   # L404FA-404FE
            self._draw_sprite_at(0x137, 0x57, 0x45)  # L4057A-4058E
            return

        # `SUBQ.W #1` puis `EXT.L` : l'indice est signe, donc -1 pour D4=0.
        prev = 0x00290029 if d4 == 0 else MANA_VALUES[d4 - 1]
        cur = MANA_VALUES[d4]

        # `ASL.L #3` : ecrasement sur 32 bits (le debordement ne pose que le
        # flag V, ignore ici). `s32` masque sur 32 bits puis rend le signe.
        # Attention, `m68k.to_long_word` NE LE FAIT PAS : c'est un `EXT.L`
        # (mot signe etendu), et l'employer ici tronque tout a 16 bits.
        numer = m68k.s32((mana - prev) << 3)
        denom = m68k.s32(cur - prev)
        d5 = m68k.to_word(m68k.divs_long(numer, denom))   # MOVE.W D0,D5

        y = ((d4 - 1) * 8 + d5 + 8) & 0xFFFF              # L4054E-40556
        x = ((d4 - 1) * 16 + (d5 << 1) + 0xA0) & 0xFFFF   # L4055A-40566
        self._draw_sprite_at(x, y, 0x45)

    def _draw_sprite_at(self, x: int, y: int, sprite: int) -> None:
        """``_draw_sprite(ecran, x, y, sprite)`` — **x et y sont en pixels**.

        L'asm (L19283) lit ses arguments ainsi : ``(8,A5)`` = ecran,
        ``($C,A5)`` = x, ``($E,A5)`` = y, ``($10,A5)`` = sprite, et l'ordre
        de push des appelants confirme ``(ecran, x, y, sprite)``.

        Ce que fait ``_draw_sprite`` de x (L19306-19311) :

        .. code-block:: none

            MOVE.W #$000f,D3 / CMP.W #$00b8,D1 / BLE   ; y > 184 -> clip bas
            MOVE.L #$00000026,D7 / CMP.W #$0130,D0      ; x > 304 -> 40 o/ligne
            MOVE.W D0,D6 / MULU #$0028,D1               ; D1 = y * 40 (ligne)
            LSR.W #4,D6 / LSL.W #1,D6 / ADDA.L D6,A0    ; offset = (x/16)*2 o

        Les bornes $B8 = 184 et $C8 = 200 donnent la **hauteur 200**, et
        $0028 = 40 octets par ligne donnent la **largeur 320** : c'est bien
        un ecran 320x200, et x est un **coordonnee pixel** (40 o x 8 px/o
        = 320).

        Cette fonction faisait autrefois ``x * 16``, ce qui mettait le sprite
        a ``272 * 16 = 4352`` hors d'un frame de 320 px : pygame le
        decoupait silencieusement et **aucun sprite n'apparaissait**.
        Le test qui l'a revelé : frame (320,200), sprite 0x110 (16,16),
        destination (4352, 22) -> ``4352 >= 320``.
        """
        sp = self.ren.sprites
        if not sp:
            return
        self.frame.blit(sp[sprite % len(sp)], (x, y))

    def _bars(self, rempli1: int, drapeaux1: int,
              rempli2: int, drapeaux2: int) -> None:
        """Les deux barres de l'ecusson : ``_draw_bar`` deux fois.

        Tous les sites du listing — combat (L2871-2885), villageois
        (L2915-2921 et L2956-2962), repli (L3042-3090) — emploient la
        **meme geometrie** ; seuls le remplissage et les drapeaux
        changent :

        .. code-block:: none

            barre 1 : _draw_bar(ecran, x=$24, y=$25, h=$10, rempli1, dr1)
            barre 2 : _draw_bar(ecran, x=$25, y=$25, h=$10, rempli2, dr2)

        ``x`` est un offset en **octets** (render.py L245) : $24 donne le
        pixel 288, $25 le pixel 296 — soit 8 pixels de large chacune, a
        cote du sprite trace en (272, 22).

        L'ancien ``_bars_for`` avait justement ces deux ``x`` et ces deux
        ``y``. Ce qu'il se trompait sur les trois autres comptes : la
        **hauteur** (0x0F puis 0x08, au lieu de $10 partout), le
        **remplissage** (``valeur >> 8`` et ``valeur >> 9``, au lieu des
        divisions propres a chaque branche) et les **drapeaux** (toujours
        $0F, alors que le listing emploie $0F, $08, $0A, $0C et $09 selon
        la branche). D'ou le partage des arguments ci-dessus : le port ne
        pouvait pas les deviner, il les reçoit.
        """
        r = self.ren
        r.draw_bar(self.frame, 0x24, 0x25, 0x10, rempli1, drapeaux1)
        r.draw_bar(self.frame, 0x25, 0x25, 0x10, rempli2, drapeaux2)

# ---------------------------------------------------- _requester (asm L9901)
    # Les boites de dialogue (intro de niveau, messages du Conseil, etc.).
    #
    # ``_requester(ecran, x, y, largeur, struct_titre, struct_message)`` :
    #   D4 = x >> 4, D5 = y >> 4, largeur >>= 4
    # Le cadre est fait d'icones de 16x16 posees une par une :
    #   0x0C en haut a gauche      0x0D en haut (repete)
    #   0x0E coin haut droit       0x12 bord gauche (repete)
    #   0x14 bord haut (repete)    0x13 coin haut
    #   0x0F coin bas gauche       0x10 bas (repete)
    #   0x15 angle                 0x16 bord bas (repete)
    #   0x17 coin bas droit
    # Puis le texte : d'abord le titre a ``y + 3``, puis le message.
    def requester(self, x: int, y: int, largeur: int, hauteur: int,
                  titre: str, message: str = "") -> None:
        """Boite de dialogue — transcription de ``_requester`` (asm L9901).

        Les **sept** pushes avant le JSR donnent
        ``_requester(ecran, x, y, largeur, hauteur, end_ok, end_cancel)``.
        Les deux derniers arguments ne sont pas des chaines mais des
        **structures de trois mots** ``(x0, y0, x1)`` que la routine
        remplit elle-meme (L10081-10085 pour CANCEL) et dont le texte est
        a ``+6`` (L10046-10052 : ``ADDQ.L #6,A0`` puis ``___strlen``) -
        d'ou ``DC.B "OK",0`` a ``_end_ok+6`` (L24354) et
        ``DC.B "CANCEL",0`` a ``_end_cancel+6`` (L24361). Les appels du
        listing passent donc ``PEA (_end_cancel,A4)`` puis
        ``PEA (_end_ok,A4)`` (L13634-13635 pour ``_options``).

        Ce port n'a garde que les deux chaines : le cadre et le texte
        sont fideles, mais les **boutons OK/CANCEL ne sont pas poses**
        et leurs cadres sont calcules par l'appelant (voir
        ``Game.check_cancel``). ECART assume, Phase 67.

        Releve dans le tas d'appels :
        ``_requester(d_screen, $10, $10, $120, $A6, ...)`` pour
        ``_options`` (L13636-13640) et ``(d_screen, $30, $46, $E4, $40,
        ...)`` pour la saisie du niveau (L11927).

        **Unites** (L9904-9910) : ``D4 = x >> 4`` et
        ``colonnes = largeur >> 4`` sont seuls divises — ``_draw_icon``
        prend ``x`` en colonnes de 16 px (``LSL.W #1``, L19192) mais ``y``
        en **lignes** (``MULU #$0028``, L19191), et ``_requester`` passe
        ``D5`` **tel quel** : la boite commence a la ligne ``y``, pas a la
        ligne ``y >> 4``. Correction de Phase 82 ; la consequence se voit
        a l'oeil : ``_do_message`` trace sa boite en ``y = $3C = 60`` et
        son texte en ``y = $48 = 72`` — le texte tombe **dans** la boite
        (lignes 72 a 87, la boite faisant 60 a 107) seulement si ``D5``
        n'est pas divise.

        Le cadre est fait d'icones de 16x16 posees une par une :

        * bandeau haut (L9918-9948) : 0x0C, puis 0x0D jusqu'a la colonne
          ``D1 - 1``, puis 0x0E ;
        * cotes (L9949-9990) : ``D6`` part de ``D5 + 0x10`` et avance de
          ``0x10`` tant que ``D6 < D5 + hauteur - 0x10`` ; a chaque tour on
          pose 0x12 a gauche, 0x14 sur les colonnes centrales et 0x13 a
          droite ;
        * bandeau bas (L9991-9996) : 0x0F, puis 0x10 sur le reste de la
          ligne — sauf la derniere colonne, prise par l'angle 0x11 du
          bouton (L10247-10254). Ce port ne pose pas les boutons
          (ECART Phase 67) et laisse donc l'angle bas-droit absent.

        Le titre et le message sont, eux, des ajouts du port : le listing
        ne sait tracer que les etiquettes ``OK`` / ``CANCEL`` (L10045-10057
        et L10140-10152), et c'est l'**appelant** qui trace ses propres
        lignes apres le retour de ``_requester`` (L11935-11940 pour
        *TRY NUMBER*).

        Comme `_draw_icon` ecrase les 4 plans, l'interieur de la boite est
        **noir** — c'est bien ce que fait l'original.
        """
        r, d = self.ren, self.frame
        d4 = x >> 4                      # colonne de depart (L9907)
        d5 = y                           # premiere ligne, EN LIGNES (L9905)
        n = max(2, largeur >> 4)         # nombre de colonnes (L9908-9910)

        px = lambda col: d4 + col        # noqa: E731  colonne

        # ---- bandeau haut (L9918-9948) ----------------------------------
        r.draw_icon(d, px(0), d5, 0x0C)
        for i in range(1, n - 1):
            r.draw_icon(d, px(i), d5, 0x0D)
        r.draw_icon(d, px(n - 1), d5, 0x0E)

        # ---- cotes (L9949-9990) : D6 de D5+0x10, par pas de 0x10 --------
        bas = d5 + 0x10
        while bas < d5 + hauteur - 0x10:  # L9986-9990
            r.draw_icon(d, px(0), bas, 0x12)
            for j in range(1, n - 1):
                r.draw_icon(d, px(j), bas, 0x14)
            r.draw_icon(d, px(n - 1), bas, 0x13)
            bas += 0x10

        # ---- bandeau bas (L9991-9996) ----------------------------------
        r.draw_icon(d, px(0), bas, 0x0F)
        for i in range(1, n - 1):
            r.draw_icon(d, px(i), bas, 0x10)

        # ---- titre (port) : a l'abscisse `end_ok.x0`, calque sur l'ecran
        # de saisie du niveau. L'asm ne trace pas de titre dans
        # `_requester` : c'est l'appelant qui le fait, et pour la boite
        # « TRY NUMBER » (L11926-11940) il ecrit
        # `_text(d_screen, $40, $58, "TRY NUMBER")`. Or `end_ok.x0 =
        # (D4 + 1) << 4` (L10006) vaut bien `$40` pour `x = $30`, et
        # `D5 + $10 + $2 = 0x46 + 18 = $58` pour `y = $46` : les deux
        # coordonnees du port sont celles du listing, et non une
        # approximation.
        if titre:
            r.draw_text(d, (d4 + 1) * 2, d5 + 16 + 2, titre)

        # ---- message (port) : la ligne suivante, meme abscisse ---------
        if message:
            r.draw_text(d, (d4 + 1) * 2, d5 + 16 + 10, message)


    # --------------------------------------------- jauges de population (L403F4)
    # Appelées en fin de `_show_the_shield` (L3092 et L3119). Les deux
    # jauges sont lues à des adresses **absolues**, pas indexées par
    # `_player` : `good_pop = $52DEC` et `bad_pop = $52DFC` (stride 16
    # depuis la base joueur `$52DE4`, champ pop en +8). La colonne de
    # gauche est donc toujours la tribu 0 et celle de droite la tribu 1,
    # même quand l'humain joue la tribu 1 — comme les deux barres du
    # duel en combat (L2871-2885).
    def draw_pop_gauge(self) -> None:
        """Les deux jauges de population (asm L3092-3145).

        .. code-block:: none

            D0 = pop ; D1 = $1F   ; _mulu   -> pop * 31
            D1 = $C350            ; _divs   -> / 50000
            ADDQ.L #1,D0                      ; + 1
            _draw_bar(ecran, x, y=$1F, h=$20, rempli, drapeaux)

        La jauge adverse (L3119-3145) est identique en `x=$27`,
        `drapeaux=$08`. Les deux branches `pop == 0` (L3110 et L3137)
        tracent une jauge **vide** plutôt que de sauter l'appel : c'est
        ce qui efface la barre quand une tribu est éliminée.
        """
        sim = self.sim
        r = self.ren
        for pl, x, drapeaux in ((sim.players[0], 0x20, 0x0F),
                                (sim.players[1], 0x27, 0x08)):
            pop = pl.pop
            if pop:
                # `_mulu` puis `_divs` (L3098-3100) : produit non signé,
                # quotient signe tronque vers zero. `pop * 31` est toujours
                # positif ici, donc `//` Python coïncide.
                rempli = pop * 0x1F // 0xC350 + 1      # L3098-3101
            else:
                rempli = 0                            # L3112 / L3139 CLR.W
            # L3103-3105 : y=$1F (31), h=$20 (32), x en octets.
            r.draw_bar(self.frame, x, 0x1F, 0x20, rempli, drapeaux)
    def _draw_cursor(self) -> None:
        """Le curseur de la carte : le sprite 0x54 (``_sculpt`` L7440-7449).

        L'asm ne le dessine que si son ordonnee est sous ``0xC0`` : au-dela le
        curseur sort par le bas de l'ecran et n'est pas trace.
        """
        cur = self.sim.cur_screen
        if cur is None or cur[1] >= 0xC0:
            return
        sprite = self.ren.sprites[self.CURSOR_SPRITE]
        self.frame.blit(sprite, (cur[0] & ~1, cur[1] & ~1))

    def _draw_hud(self) -> None:
        """Le HUD de debogage — **désactivé par défaut**.

        L'original n'affiche aucun texte : toutes les informations sont dans
        le décor `qaz.pic` (jauge de mana, jauges de population, blason) et
        dans l'écusson de `_show_the_shield`. Ce bloc était un instrument de
        mise au point ; on ne le trace plus que si ``POPULOUS_HUD`` est défini
        dans l'environnement, pour ne jamais masquer l'interface fidèle.
        """
        import os
        if not os.environ.get("POPULOUS_HUD"):
            return
        pl = self.sim.players[self.sim.player]
        st = self.sim.stats[self.sim.player]
        txt = ("t=%d pop=%d hab=%d mana=%d  act=%d tend=%02X  vue=%d,%d"
               % (self.sim.game_turn, pl.pop, self.people, pl.mana,
                  st.act, st.tend, self.xoff, self.yoff))
        self.frame.blit(self.hud.render(txt, True, (255, 255, 0)), (2, 190))
        if self.sim.cur_screen is not None:
            txt2 = "curseur %d,%d" % (self.sim.cur_x, self.sim.cur_y)
            self.frame.blit(self.hud.render(txt2, True, (0, 255, 255)),
                            (2, 192))

    # ------------------------------------------------- projection isometrique
    def _mouse(self, mx: int, my: int) -> tuple[int, int]:
        """Coordonnees souris dans l'ecran logique 320x200.

        La fenetre pygame est agrandie d'un facteur ``zoom`` : sans cette
        conversion, tous les tests de zone (``0 <= u < 0x40``…) echouent.
        L'original lit directement les deltas 8 bits de ``JOY0DAT`` qu'il
        accumule dans ``_big_mousex/_big_mousey`` (plage 0..0x27F) avant de
        diviser par 2 — le resultat est le meme, seule la precision change.
        """
        z = self.zoom or 1
        return mx // z, my // z

    @staticmethod
    def _uv(mx: int, my: int) -> tuple[int, int]:
        """``u`` et ``v`` de l'asm, calculees une seule fois en tete de
        ``_zoom_map`` (L1660-1670) et de nouveau a l'identique dans
        ``_sculpt`` (L7282-7294) :

            u = (mousex >> 1) + mousey - 0x20      # colonne X de la projection
            v = mousey - (mousex >> 1) + 0x20      # ligne  Y de la projection

        L'inversion est triviale et sert aux reperes de l'ecran :

            mousex = u - v + 0x40      mousey = (u + v) >> 1
        """
        h = mx >> 1
        return h + my - 0x20, my - h + 0x20

    # ------------------------------------------- boutons : _mouse (L19579)
    # ``_left_button`` / ``_right_button`` ne sont pas des booleens. La lecture
    # hardware (asm L19582-19591) y ecrit la **valeur brute du bit** :
    #
    #     0x40  bouton relache        (EXT_BFE0FF & 0x40 pour la gauche,
    #     0     bouton enfonce         POTGOR & 0x400 pour la droite)
    #     1     etat stable            (ecrit par la boucle d'image, L999)
    #     2     bloque : il faut relacher avant de pouvoir re-cliquer
    #
    # La ligne ``if _left_button == 2`` est l'anti-rebond : un second front
    # montant est ignore tant que le bouton n'a pas ete relache. La ligne
    # ``MOVE.W _mmousex,_mousex`` n'est executee qu'a un changement valide :
    # la position de la souris n'est donc lue que sur un vrai mouvement.
    BTN_UP = 0x40

    def _read_buttons(self) -> None:
        """Transcription de la partie boutons de ``_mouse`` (L19579-19605).

        L'enchainement exact est :

            if _left_button == 0            -> rien (front deja vu)
            elif _left_button != 2          -> _left_button = bit brut
            elif bit brut == 0              -> rien (bloque, encore enfonce)
            else                            -> _left_button = bit brut

        Consequence : apres un clic, ``_zoom_map`` met l'etat a 2 (L2444) et il
        **reste a 2 tant que le bouton est enfonce** ; il ne retombe a 0 qu'au
        relachement. Donc ``_left_button == 0`` ne vaut exactement qu'une image
        par clic — c'est cela qui fait qu'un clic declenche une seule action.
        """
        for raw, attr in ((self._raw_left, "left_button"),
                          (self._raw_right, "right_button")):
            d0 = 0 if raw else self.BTN_UP
            cur = getattr(self, attr)
            if cur == 0 or (cur == 2 and not d0):
                continue
            setattr(self, attr, d0)

    # ------------------------------------------------- _sculpt (asm L7271)
    # Le role de ``_sculpt`` n'est PAS d'appliquer un pouvoir : c'est la
    # traduction de la position de la souris en **case de la carte**, plus le
    # dessin du curseur et l'ecriture de la cible (``LAB_516A5/6``).
    # L'original ne la appelle que si ``_mode & 0x0E != 0`` (L963-967).
    CURSOR_SPRITE = 0x54

    def sculpt(self) -> bool:
        """Renvoie vrai si une case a ete designee cette image.

        Transcription complete :

        * zone (L7295-7306) : pas de guerre, ``0x3E <= u <= 0x10A``,
          ``-0x40 <= v <= 0x88`` et ``mousex >= 0x40`` ;
        * ligne/colonnes (L7317-7352) : ``d4 = (mousex - 0x38) >> 4`` puis le
         zigzag qui recadre la fenetre 8x8 sur la seule diagonale visee ;
        * balayage (L7357-7392) : pour chaque case de la diagonale, le bord
          superieur est a ``step - alt*8`` ; on retient la premiere case dont
          le bord est sous ``mousey + 4`` (les sprites etant 16 px de haut,
          ``+4`` vise le tiers central, comme dans l'original) ;
        * ``(-36,A5) = -1`` au depart : aucune case trouvee -> on renvoie 0.
        """
        sim = self.sim
        sim.cur_screen = None
        if sim.war or sim.pause:
            return False
        mx, my = self.mouse
        u, v = self._uv(mx, my)
        if not (0x3E <= u <= 0x10A) or not (-0x40 <= v <= 0x88) or mx < 0x40:
            return False

        # L7307-7312, garde qu'on n'avait pas. On ne poursuit que si
        # l'UNE des trois conditions est vraie ; sinon on rend la main.
        #
        #     TST.W _ok_to_build / BNE  -> poursuivre
        #     CMPI.W #2,_mode / BNE     -> poursuivre
        #     TST.W _paint_map  / BNE   -> poursuivre
        #     sinon                     -> rendre 0
        #
        # Autrement dit : en mode peinture de carte (mode 2) sans
        # `_ok_to_build`, la souris ne designe **aucune** case. Notre port
        # en designait une quand meme.
        if not (sim.ok_to_build or sim.mode != 2 or sim.paint_map):
            return False

        d4 = (mx - 0x38) >> 4              # diagonale visee dans la fenetre
        terrain = self.terrain
        # L7321-7324 : `MULS #$0041` puis `ADD.W` -- les deux en 16 bits,
        # donc `base` reboucle a 0x10000.
        base = m68k.to_word(self.yoff * 0x41 + self.xoff)
        nb = 9
        step = 0x48
        if d4 > 8:                         # coin droit du losange
            nb = 0x11 - d4
            base = m68k.to_word(base + (d4 - 8))                  # L7334
            step = m68k.to_word(step + m68k.asl_word(d4 - 8, 3))  # L7337-7338
        elif d4 < 8:                       # coin gauche du losange
            nb = d4 + 1
            base = m68k.to_word(base + m68k.to_word((8 - d4) * 0x41))
            step = m68k.to_word(step + m68k.asl_word(8 - d4, 3))

        col = -1
        cur_step = step
        for i in range(nb):
            # L7364-7368 : `MULS #$0042` puis `ADD.W (-30,A5)`, les deux en
            # 16 bits, puis `EXT.L` qui **etend le signe**. Un `base`
            # reboulee avec le bit 15 pose donne un indice NEGATIF, et le
            # 68000 lit alors _alt **avant** le tableau. Notre ancien
            # `k % n_alt` etait un garde-fou de notre invention.
            idx = m68k.to_long_word(m68k.to_word(i * 0x42 + base))
            # L7370-7373 : `ASL.W #3` puis `SUB.W` -- reboucles 16 bits.
            top = m68k.to_word(cur_step - m68k.asl_word(terrain._cell(idx), 3))
            cur_step = m68k.to_word(cur_step + 0x10)              # L7375
            # CMP.W D1,D2 / BGT : D2-D1 = (mousey+4) - top, donc BGT saute
            # quand le sommet de la case est *au-dessus* du curseur. La boucle
            # **ne s'arrete pas** (LAB_43662 ne fait qu'incrementer D6) : on
            # descend la diagonale en notant chaque case, et c'est la derniere
            # dont le bord haut n'a pas encore depasse le curseur qui gagne.
            if not m68k.cmp_word_gt(top, my + 4):                # L7383-7384
                col = i
                sim.cur_screen = (d4 * 0x10 + 0x3D, m68k.to_word(top - 3))
        if col < 0:
            return False

        base = m68k.to_word(base + col * 0x42)
        sim.cur_y = base // 0x41           # _cur_y
        sim.cur_x = base - sim.cur_y * 0x41    # _cur_x
        self._on_cell()
        return True

    def _on_cell(self) -> None:
        """Ce que ``_sculpt`` fait une fois la case designee (L7440-7560).

        Le curseur est **un vrai sprite** (0x54) et non le pointeur systeme :
        il est trace a ``(d4*16 + 0x3D, top - 3)``, et seulement si
        ``top - 3 < 0xC0`` (au-dela il sort par le bas de l'ecran).

        Puis le clic. ``_left_button == 0`` ne dure **qu'une image** (l'epilogue
        de ``_zoom_map`` le met aussitot a 2 et il faut le relacher), c'est
        donc exactement l'image du clic.

        Le clic n'ecrit pas que la case : il ecrit ``act`` ET ``p1``/``p2``,
        les trois octets ``_stats+0/+1/+2`` que ``_get_message`` lira
        (L17953).  C'est ce qui explique pourquoi la palette (3,3) ne peut
        armer relever : elle pose ``act = 14, p2 = 1`` (le **sens** du
        relief), c'est le clic qui choisit l'action et la case.

        Trois points repris a la ligne :

        1. ``(-1,A5)``/``(-3,A5)`` sont les octets **bas** des mots
           ``cur_x``/``cur_y`` ecrits au L7409/L7415 (un mot en big-endian
           occupe -2 puis -1).  Le port prenait ``cur_x`` entier en disant
           que le listing lisait un demi-mot toujours nul : c'etait une
           melecture, l'ecart est supprime.
        2. ``bitfield_51645`` est l'octet bas de ``_mode`` (voir
           ``set_mode_icons``) : ``BTST #3`` vaut donc ``mode & 08``
           (marais arme par ``(2,2)``, L2040) et ``BTST #2`` vaut
           ``mode & 04`` (aimant arme par ``(6,2)``, L2127).  Ces deux
           bits ne sont poses que par la palette et sont effaces ici
           (L7479, L7516) : les deux branches sont donc **inaccessible**
           en l'etat, on les transcrit quand meme.
        3. La branche par defaut (L7527-7540) pose ``act = 1`` sans test :
           elle ecrase l'action eventuellement armee, donc apres un clic
           sur la carte ``act`` ne peut plus valoir 14.
        """
        sim = self.sim
        st = sim.stats[sim.player]
        x, y = sim.cur_x, sim.cur_y

        if self.left_button == 0:                  # L7452
            if sim.mode & 0x08:                    # L7454 : marais arme
                self.set_mode_icons(6, (sim.mode & 0x03) - 1)  # L7459-7461
                st.act = ACT_SWAMP                 # L7466
                st.p1 = (x - 1) & 0xFF             # L7467-7472
                st.p2 = (y - 1) & 0xFF             # L7473-7478
                sim.mode &= ~0x08                  # L7479
                sim.pointer = sim.mode - 1         # L7480-7482
                if sim.pointer == 1 and sim.player == 1:
                    sim.pointer = 4                # L7483-7487
            elif sim.mode & 0x04:                  # L7491 : aimant arme
                self.set_mode_icons(6, (sim.mode & 0x03) - 1)  # L7496-7498
                st.act = ACT_MAGNET                # L7503
                st.p1 = (x - 1) & 0xFF             # L7504-7509
                st.p2 = (y - 1) & 0xFF             # L7510-7515
                sim.mode &= ~0x04                  # L7516
                sim.pointer = sim.mode - 1         # L7517-7519
                if sim.pointer == 1 and sim.player == 1:
                    sim.pointer = 4                # L7520-7524
            else:                                  # L7527
                st.act = ACT_RAISE                 # L7531
                st.p1 = x & 0xFF                   # L7535 `(-1,A5)`
                st.p2 = y & 0xFF                   # L7539 `(-3,A5)`
            sim.tgt[sim.player] = (st.p1, st.p2)
            sim.tgt_dirty = True
            return

        # ---- clic droit : LAB_43860 ---------------------------------------
        if (self.right_button == 0 and sim.mode == 2
                and not (sim.flags & 0x08)):
            self.right_button = 2                  # L7549
            st.act = ACT_LOWER                     # L7553
            st.p1 = x & 0xFF                       # L7557
            st.p2 = y & 0xFF                       # L7561
            sim.tgt[sim.player] = (st.p1, st.p2)
            sim.tgt_dirty = True

    # --------------------------------------- _zoom_map (asm L1658, fin L1931)
    # ``u``/``v`` sont calculees UNE SEULE FOIS en tete (L1660-1670). Le
    # dispatch est ensuite strictement ordonne, chaque zone se terminant par
    # un branchement a l'epilogue commun ``LAB_3FCB6`` :
    #
    #   1. mini-carte  (L1671-1699) : u,v dans [0,0x40) -> xoff=u-3, yoff=v-3
    #   2. barre      (L1706-1824) : u > 0x112
    #   3. pave       (L1825-1927) : v >= 0x92 et up dans [3,5], vp dans [0,2]
    #   4. palette    (LAB_3F666)  : v >= 0x92, index = up dans [0,9)
    #   5. sinon rien (LAB_3F52E avec v < 0x92, ou LAB_3FC90)
    def zoom_map(self, d0: int) -> None:
        """``_zoom_map(d0)`` â€” l'asm passe ``d0 = 1`` quand le bouton gauche
        **vient** d'etre appuye (donc 0 la plupart du temps). La fonction est
        appelee a chaque image par la boucle (L985-990)."""
        mx, my = self.mouse
        u, v = self._uv(mx, my)
        st = self.sim.stats[self.sim.player]

        # ---- 1. la mini-carte (Book of Worlds) â€” L1671-1699
        if 0 <= u < 0x40 and 0 <= v < 0x40:
            self.xoff = clamp_off(u - 3)
            self.yoff = clamp_off(v - 3)
        elif u > 0x112:
            # ---- 2. la barre d'icones - L1706-1824 ----------------------
            # `DIVS` (L1711 / L1716) tronque **vers zero** : en sortie par
            # le haut la case vaut 0 et non -1, d'ou une branche (0, 0) qui
            # peut partir sur un clic qui n'est pas vraiment dans la barre.
            col = m68k.divs_word(u - 0x110, 0x10)
            row = m68k.divs_word(v - 0x20, 0x10)
            if col == 0:                            # L1718
                if row == 0:                        # L1722-1734 poser
                    self.toggle_icon(col, row, 0x17E4)
                    st.act = ACT_ACTION             # L1729
                    st.p2 = 7                       # L1731 -> _do_action 7
                    # L1733 lit `(9,A5)` : `LINK A5,#-14` laisse le mot
                    # pousse par l'appelant (L988) en A5+8..9 et l'adresse
                    # de retour en A5+4..7 - donc (9,A5) en est l'octet
                    # **bas**, soit d0 tel quel (0 ou 1).
                    st.p1 = d0 & 0xFF
                elif row == 3:                      # L1736-1758 musique
                    self.toggle_icon(col, row, 0x17E4)
                    self.music_on ^= 1              # `_music_off` L1744-1750
                    if self.music_on:               # L1751-1756
                        self.kill_effect(0, 4)
                    self.maj_musique()              # ECART Phase 86 : BGM.mp3
                elif row == 4:                      # L1760-1780 effets
                    self.toggle_icon(col, row, 0x17E4)
                    self.effect_on ^= 1
                    if self.effect_on:
                        self.kill_effect(0, 4)
            elif col == 1:                          # L1784
                if row == 1:                        # L1786-1798
                    self.toggle_icon(col, row, 0x17E4)
                    st.p2 = 8                       # L1795
                    st.act = ACT_ACTION             # L1797
                elif row == 3:                      # L1800-1805
                    # **aucune** icone : le volcan arme ici se declenche
                    # de lui-même a la fin de l'image (L1800-1805).
                    st.act = ACT_ACTION             # L1803
                    st.p2 = 6                       # L1805
            elif col == 2:                          # L1809
                if row == 2:                        # L1811-1822
                    self.toggle_icon(col, row, 0x17E4)
                    st.p2 = 2                       # L1820
                    st.act = ACT_ACTION             # L1822
        elif v >= 0x92:
            # ---- 3. le pave de defilement â€” L1825-1927
            vp = m68k.divs_word(v - 0x90, 0x10)
            up = m68k.divs_word(u - 0x60, 0x10)
            if 3 <= up <= 5 and 0 <= vp <= 2:
                self.toggle_icon(up, vp, 0x12C0)
                if up == 4 and vp == 1:           # centre : _view_who
                    b = self._peep_block(self.sim.view_who)
                    if b is not None:
                        self.xoff = clamp_off((b & 63) - 3)
                        self.yoff = clamp_off((b >> 6) - 3)
                else:                             # fleches : +/- 1 case
                    self.xoff = clamp_off(self.xoff + (1 if up == 5 else 0)
                                          - (1 if up == 3 else 0))
                    self.yoff = clamp_off(self.yoff + (1 if vp == 2 else 0)
                                          - (1 if vp == 0 else 0))
                return self._zoom_map_end()
            # ---- 4. la palette d'outils (LAB_3F666) : 9 entrees
            self.palette(up, vp, d0)
        # ---- epilogue LAB_3FCB6 : bornage + anti-rebond
        self._zoom_map_end()

    def _zoom_map_end(self) -> None:
        """``LAB_3FCB6`` (L2425-2450) : bornage de la vue puis, si un bouton
        vient d'etre appuye, blocage untilte qu'il soit relache. C'est ce qui
        fait que ``_left_button == 0`` ne vaut **qu'une image** â€” donc que
        ``_sculpt`` et la palette ne declenchent qu'une fois par clic."""
        self.xoff = clamp_off(self.xoff)
        self.yoff = clamp_off(self.yoff)
        if self.left_button == 0:
            self.left_button = 2
        if self.right_button == 0:
            self.right_button = 2

    def kill_effect(self, a: int, b: int) -> None:
        """``_kill_effect(a, b)`` (L1742/L1777) : coupe le son en cours."""
        self.effect = 0
        self.sound.kill_effect(a, b)

    # --------------------------------- palette d'outils (LAB_3F670 .. LAB_3FB26)
    # Table de dispatch a 9 entrees indexee par ``up = (u - 0x60) >> 4``, le
    # second parametre etant ``vp = (v - 0x90) >> 4``. A l'ecran cela occupe le
    # parallelogramme x dans [0,160), y dans [120,200) : la colonne d'icones du
    # bas-gauche, celle des outils de terrain et de pouvoirs.
    # Coordonnees a l'ecran du centre de chaque case (voir ``_uv``) :
    #     mx = 16*(up - vp + 1)      my = 128 + 8*(up + vp)
    def palette(self, up: int, vp: int, d0: int = 0) -> None:
        """Une entree de la palette a ete cliquee - ``LAB_3F666`` (L1928-2133).

        La table de saut ``LAB_3FC92`` (L2408-2417) est indexee par la
        **colonne** ``up`` ; chaque branche teste ensuite ``vp``. Tout se
        passe dans la fiche que ``_zoom_map`` vient d'ouvrir : ``st.act`` =
        ``_stats+0``, ``st.p1`` = ``_stats+1``, ``st.p2`` = ``_stats+2`` -
        les trois octets que ``_get_message`` relit en fin d'image
        (L17953-17971).

        Deux familles, et c'est la premiere grande lecon du listing :

        * ``act = $0E`` (14) -> ``_get_message`` appelle
          ``_do_action(tribu, p1, p2)`` (L18185-18190) et c'est **``p2``**
          qui indexe la table ``LAB_4C16A`` (L18378) : 1 = outil de relief,
          3 = guerre, 4 = deluge, 5 = chevalier, 7 = options, 8 = setup ;
        * ``act = 3`` ou ``act = 6`` -> la table ``LAB_4B81A``
          (L18202-18217) appelle directement ``_do_quake`` /
          ``_do_volcano`` sur ``(p1, p2)``.

        =========  ====  ==============  ====  ==========================
        (up, vp)   act   p1              p2    effet (ligne du listing)
        =========  ====  ==============  ====  ==========================
        (0, 0)     14    (9,A5) = 0      4     deluge            L1942
        (1, 0)     14    inchange        3     guerre  (!paint)  L1959
        (1, 1)     6     ``_xoff``       ``_yoff``  volcan       L1972
        (2, 0)     3     ``_xoff``       ``_yoff``  seisme       L1989
        (2, 1)     14    inchange        5     chevalier         L2005
        (2, 2)     -     -               -     sculptage (garde) L2038
        (3, 3)     14    0               1     relief, dir 0     L2049
        (4, 3)     14    1               1     relief, dir 1     L2060
        (4, 4)     14    3               1     relief, dir 3     L2070
        (5, 3)     14    2               1     relief, dir 2     L2081
        (6, 0..2)  -     -               -     selecteur de mode L2094
        =========  ====  ==============  ====  ==========================

        Un octet que la branche n'ecrit **pas** garde la valeur de la
        commande precedente : c'est le listing qui le veut (``LAB_3F6A0``
        saute a l'epilogue sans jamais toucher a ``p1``, L1946).

        ``(p1, p2)`` des branches volcan/seisme sont le **bas** octet des
        mots ``_xoff``/``_yoff`` : ``LAB_52DDF`` = ``_xoff+1``,
        ``LAB_52DE1`` = ``_yoff+1`` (L25313-25318, jamais ecrits sous ce
        nom - ils ne sont modifies que par les ``MOVE.W (..., _xoff)``).
        Le listing ne les lit qu'aux L1974/1976 et L1991/1993.
        """
        sim = self.sim
        st = sim.stats[sim.player]

        if up == 0:                                 # LAB_3F670
            if vp == 0:                             # L1933
                self.toggle_icon(up, vp, 0x12C0)    # L1935
                st.act = ACT_ACTION                 # L1942
                st.p2 = 4                           # L1944 -> _do_flood
        elif up == 1:                               # LAB_3F6A4
            if vp == 0 and not sim.paint_map:       # L1948 / L1950
                self.toggle_icon(up, vp, 0x12C0)    # L1952
                st.act = ACT_ACTION                 # L1959
                st.p2 = 3                           # L1961 -> _do_war
            elif vp == 1:                           # LAB_3F6DA, L1963
                self.toggle_icon(up, vp, 0x12C0)    # L1965
                st.act = ACT_VOLCANO                # L1972
                st.p1 = self.xoff & 0xFF            # L1974 (LAB_52DDF)
                st.p2 = self.yoff & 0xFF            # L1976 (LAB_52DE1)
        elif up == 2:                               # LAB_3F71A
            if vp == 0:                             # L1980
                self.toggle_icon(up, vp, 0x12C0)    # L1982
                st.act = ACT_QUAKE                  # L1989
                st.p1 = self.xoff & 0xFF            # L1991
                st.p2 = self.yoff & 0xFF            # L1993
            elif vp == 1:                           # L1996
                self.toggle_icon(up, vp, 0x12C0)    # L1998
                st.act = ACT_ACTION                 # L2005
                st.p2 = 5                           # L2007 -> _do_knight
            elif vp == 2:                           # L2010
                self.toggle_icon(up, vp, 0x12C0)    # L2012
                # L2018-2032 : le sculptage n'est ouvert que si la tribu a
                # le mana ET le bit du masque de pouvoirs, ou si
                # `_paint_map` est deja pose.
                if self._may_paint():
                    self.set_mode_icons(up, vp)     # L2036
                    sim.mode = (sim.mode & 0x03) | 0x08   # L2038-2041
                    sim.pointer = 5                 # L2042
        elif up == 3:                               # LAB_3F804
            if vp == 3:                             # L2046
                st.act = ACT_ACTION                 # L2049
                st.p2 = 1                           # L2051
                st.p1 = 0                           # L2053 (CLR.B)
        elif up == 4:                               # LAB_3F82A
            if vp == 3:                             # L2057
                st.act = ACT_ACTION                 # L2060
                st.p2 = 1                           # L2062
                st.p1 = 1                           # L2064
            elif vp == 4:                           # L2067
                st.act = ACT_ACTION                 # L2070
                st.p2 = 1                           # L2072
                st.p1 = 3                           # L2074
        elif up == 5:                               # LAB_3F878
            if vp == 3:                             # L2078
                st.act = ACT_ACTION                 # L2081
                st.p2 = 1                           # L2083
                st.p1 = 2                           # L2085
        elif up == 6:                               # LAB_3F8A0
            if vp in (0, 1):                        # L2089-2092
                self.set_mode_icons(up, vp)         # L2094-2096
                sim.mode = vp + 1                   # L2098-2100
                if vp == 1:                         # L2101
                    # L2103-2112 : `MULS #3` sur le joueur (1 si joueur 1,
                    # 0 sinon), puis `ADDQ #1` -> 4 chez le joueur 1, 1
                    # partout ailleurs.
                    sim.pointer = 4 if sim.player == 1 else 1
                else:                               # L2115
                    sim.pointer = vp
            elif vp == 2:                           # L2119
                self.set_mode_icons(up, vp)         # L2121-2123
                sim.mode = (sim.mode & 0x03) | 0x04  # L2125-2128
                sim.pointer = sim.player + 2        # L2129-2131
        elif up == 7:                               # LAB_3F924
            if vp == 0:                             # L2135
                self._palette_magnet(up, vp, d0)    # L2137-2226
            elif vp == 1:                           # L2228
                self._palette_fight(up, vp)         # L2228-2296
        elif up == 8:                               # LAB_3FB26
            if vp == 0:                             # L2298
                self._palette_people(up, vp, d0)    # L2300-2405
    def _pompe(self) -> None:
        """Les evenements pendant une boucle modale.

        Ni `poll_mouse` ni `image` : le listing gele le jeu pendant
        `_options` et ne lit que la souris. On pompe quand meme les
        evenements clavier, sans quoi la fenetre ne repond plus.

        **La souris est bien lue** : sur l'Amiga elle ne depend pas de la
        boucle, `_mouse` etant pose comme serveur d'interruption par
        `_setup_interrupt` (L187-207, `___AddIntServer(..., 5)` - l'
        interruption VERTB). C'est donc `_read_buttons` ici, et c'est ce
        qui rend `_check_cancel` actif **dans** `_get_name`.
        """
        for ev in pygame.event.get():
            self.handle(ev)
        self._read_buttons()
        self.afficher()

    def afficher(self) -> None:
        """Valide l'image : ``frame`` -> ``screen``, puis *flip*.

        Sur l'original il n'y a rien a faire - `_text` ecrit dans le plan
        bitmap que le copper balaye deja, l'effet est immediat, et c'est
        la meme interruption VERTB qui fait tourner `_mouse`. Le port doit
        le faire a la main : sans cela une boucle modale reste figee sur
        la derniere image du jeu et le champ de `_get_name` est invisible.
        """
        self.screen.blit(pygame.transform.scale(self.frame,
                                                 self.screen.get_size()),
                         (0, 0))
        pygame.display.flip()

    def _keyboard(self) -> int:
        """``_keyboard()`` (L19037-19072) : 0 sans touche, sinon `_asckey`.

        L'original lit le registre `CIAA_SDR` (L19042), traduit le code
        brut par la table `keycodes` (L19085) avec le decalage de `$60`
        quand `_shift` est enfonce (L19058-19062), pose le resultat dans
        `_asckey` (L19062) et rend **une touche par appel** : `D0` est
        l'octet `_asckey` etautranduit en long (L19063-19064), donc 0 quand
        rien n'arrivait.

        ECART declare : le port clavier de l'Amiga est du materiel, comme
        les routines de liaison serie. Seul le contrat est transcrit - file
        d'attente, un element par appel, `_asckey` sur **un octet**
        (`& 0xFF`, meme truncation que le `MOVE.B` de L19062) - et la
        table `keycodes` est remplacee par `ev.unicode`, deja traduite.
        """
        if not self._touches:
            self._asckey = ""
            return 0
        self._asckey = chr(ord(self._touches.pop(0)) & 0xFF)
        return ord(self._asckey)

    def _cadres_boutons(self, x: int, y: int, largeur: int,
                        hauteur: int, texte_ok: str = "OK",
                        texte_cancel: str = "CANCEL"):
        """Les deux cadres poses par ``_requester`` (L9991-10246).

        ``_requester`` remplit lui-meme les structures ``_end_ok`` et
        ``_end_cancel`` sur la ligne du bas de la boite. L'arithmetique,
        relevee telle quelle :

        * ``D4 = x >> 4`` (L9904, L9907) mais ``D5 = y`` **sans
          decalage** (L9905) : seuls ``x`` et ``largeur`` sont divises,
          car ``_draw_icon`` prend ``y`` en lignes (L19191). Correction
          de Phase 82 — voir :meth:`requester` ;
        * ``D6`` part de ``D5 + $10`` et avance de ``$10`` tant que
          ``D6 < D5 + hauteur - $10`` (L9949-9990) : c'est la ligne des
          boutons ;
        * ``end_ok.y0 = D6`` (L9999) et ``end_ok.x0 = (D4 + 1) << 4``
          (L10006, ``D7`` valant 1) ;
        * ``end_cancel.y0 = end_ok.y0`` (L10009) ;
        * ``end_cancel.x0 = (D4 + D7) << 4`` ou ``D7`` s'est arrete a
          ``(largeur >> 4) - strlen("CANCEL")/2 - 3`` (L10079) ;
        * les deux ``x1`` : ``x0 + (strlen(texte) + 4) * 8``
          (L10241-10246 pour OK, L10134-10139 pour CANCEL).

        **Quirk du listing assume** : ``x0``/``y0`` sont en pixels, mais
        ``x1`` est additionne en unites de 8 px (`ASL.W #3`).
        `_check_cancel` compare les trois a `_mousex` sans convertir -
        le port fait pareil.
        """
        d4 = x >> 4                     # L9907
        d5 = y                          # L9905 : pas de decalage
        d6 = d5 + 0x10                  # L9949
        while d6 < d5 + hauteur - 0x10:  # L9953-9960
            d6 += 0x10
        ok_x0 = (d4 + 1) << 4           # L10006
        n_ok = len(texte_ok)            # `___strlen` de `end_ok+6` (L10239)
        ok = (ok_x0, d6, ok_x0 + (n_ok + 4) * 8)      # L9999, L10241-10246
        colonnes = largeur >> 4          # L9908-9910
        n_cancel = len(texte_cancel)    # `___strlen` de `end_cancel+6` (L10073)
        d7 = 4                          # apres l'angle + un remplissage
        # `D1 = colonnes - strlen(cancel)/2 - 3` puis `CMP D1,D7 ; BLT`
        # (L10076-10080) : la borne depend du **texte** du bouton CANCEL.
        while d7 < colonnes - (n_cancel // 2) - 3:
            d7 += 1
        cx0 = (d4 + d7) << 4            # L10081-10085
        cancel = (cx0, d6, cx0 + (n_cancel + 4) * 8)  # L10134-10139
        return ok, cancel

    def _trace_options(self, player: int) -> None:
        """Le trace des 14 lignes (L13661-13784)."""
        from populous.options import (OPTIONS_TEXTE, OPTIONS_W, OPTIONS_X,
                                       OPTIONS_Y)
        r, d = self.ren, self.frame
        self.requester(0x10, 0x10, 0x120, 0xA6, "", "")
        nom = "GOOD" if player == 0 else "EVIL"     # L13669-13688
        for i in range(14):                        # L13783
            txt = OPTIONS_TEXTE[i]
            if i == 0:
                txt = "OPTIONS FOR " + nom
            x = OPTIONS_X[i] + 0x10                # L13728
            y = OPTIONS_Y[i] + 0x10                # L13728
            if 1 <= i < 10:                        # L13690-13710
                masque = 1 << (i - 1)              # L13740 `ASL`
                txt = ("\x81" if (self.sim.stats[player].power_mask
                                    & masque) else "\x80") + txt[1:]
            if i == 11:                            # L13733-13755
                x = OPTIONS_X[11] + 0x28 \
                    + self.sim.stats[player].threshold * 8
            if i == 13:                            # L13756-13779
                x = OPTIONS_X[13] + 0x30 \
                    + self.sim.stats[player].period * 8
            # `_text` prend x en unites de 8 px (L19977-19980)
            r.draw_text(d, x >> 3, y, txt)

    def options(self, player: int) -> None:
        """``_options(player)`` (L13617-13942) - boite de dialogue modale.

        C'est le handler du **code 7** de `_do_action`, arme par
        l'entree `(0,0)` de la barre d'icones. Boucle en cinq temps :

        1. sauvegarde des champs que la boite peut changer
           (`threshold`, `power_mask`, `period` - le listing copie les
           46 octets de `_stats`, L13619-13632) ;
        2. inversion des deux curseurs : `threshold = 10 - threshold`,
           idem `period` (L13643-13660) - ils sont stockes en
           **complement** ;
        3. trace (`_requester` puis les quatorze lignes) ;
        4. attente de ``_left_button == 0``, survol de la premiere
           ligne dont la boite est touchee ;
        5. application, puis `_check_cancel` : `0` recommence au trace,
           `2` (CANCEL) restaure la sauvegarde, `1` (OK) re-inverse les
           deux curseurs.

        Ne s'applique que si `_in_conquest == -1` (L13834) ; hors de la
        conquete le clic ne change donc rien.
        """
        from populous.options import OPTIONS_TEXTE, OPTIONS_W, OPTIONS_X, \
            OPTIONS_Y
        from populous import m68k
        st = self.sim.stats[player]
        # (1) sauvegarde (L13619-13632) - les trois champs touches
        garde = (st.threshold, st.power_mask, st.period)
        # (2) inversion (L13643-13660)
        st.threshold = 10 - st.threshold
        st.period = 10 - st.period
        ok, cancel = self._cadres_boutons(*self._boite_options())

        while True:
            self.left_button = 2                    # L13662
            self._trace_options(player)             # L13661-13784
            # (4) attente du clic (L13785-13789)
            while self.left_button != 0:
                self._pompe()
                if not self.running:
                    return
            mx, my = self.mouse
            i = 14                                  # L13832 : aucune ligne
            for k in range(1, 14):                  # L13790-13832
                if mx < OPTIONS_X[k] + 0x10 or mx > OPTIONS_X[k] + OPTIONS_W[k] + 0x10:
                    continue
                if my < OPTIONS_Y[k] + 0x10 or my > OPTIONS_Y[k] + 0x18:
                    continue
                i = k
                break
            # (5) application (L13833-13893)
            if self.sim.in_conquest == -1 and i != 14:
                if i < 10:                          # L13836-13848
                    st.power_mask ^= 1 << (i - 1)
                elif i == 11:                       # L13850-13871
                    v = m68k.divs_word(mx - (OPTIONS_X[11] + 0x28), 8)
                    if 0 <= v <= 9:
                        st.threshold = v
                elif i == 13:                       # L13873-13893
                    v = m68k.divs_word(mx - (OPTIONS_X[13] + 0x30), 8)
                    if 0 <= v <= 9:
                        st.period = v
            r = self.check_cancel(ok, cancel)       # L13894-13900
            if r == 0:                              # L13938
                continue
            if r == 2:                              # CANCEL : restaure
                st.threshold, st.power_mask, st.period = garde
            else:                                   # OK : re-inversione
                st.threshold = 10 - st.threshold
                st.period = 10 - st.period
            break
        self.left_button = 2                        # L13954 `_return_to_game`
        self.compose()

    def _boite_options(self):
        """`(x, y, largeur, hauteur)` de la boite d'`_options` (L13660)."""
        return (0x10, 0x10, 0x120, 0xA6)

    def _boite_game_setup(self):
        """`(x, y, largeur, hauteur)` de la boite de `GAME SETUP` (L12891)."""
        return (0x10, 0x10, 0x120, 0xB0)

    def _trace_game_setup(self) -> None:
        """Le trace des dix-sept lignes de `GAME SETUP` (L12886-12924).

        `_requester` n'est retrace que lorsqu'un handler leve le drapeau de
        redessin (`-4,A5`, L12887-12898) ; le cadre disparait donc quand on
        passe par `_set_options`, et revient au trace suivant.
        """
        from populous.game_setup import (GAME_SETUP_NB, GAME_SETUP_TEXTE,
                                         GAME_SETUP_X, GAME_SETUP_Y)
        r, d = self.ren, self.frame
        for i in range(GAME_SETUP_NB):                     # L12902-12924
            txt = GAME_SETUP_TEXTE[i]
            if i:                                           # le titre n'a pas
                txt = self.sim.setup_ticks[i] + txt[1:]      # de coche
            x = GAME_SETUP_X[i] + 0x10                      # L12910-12912
            y = GAME_SETUP_Y[i] + 0x10                      # L12910-12912
            # `_text` prend x en unites de 8 px (L12964-12966)
            r.draw_text(d, x >> 3, y, txt)

    def game_setup(self) -> None:
        """``_game_options`` (L12801-13358) - la boite *GAME SETUP*.

        Handler du **code 8** de `_do_action`, arme par l'entree `(1,1)` de
        la barre d'icones. Comme `_options`, c'est une boucle modale :

        1. sauvegarde de l'etat - `serial_off`, `paint_map`, `player`,
           `_stats[player].act` et `in_conquest` (L12803-12811) ;
        2. `_bring_up_two = 0` (L12812) ;
        3. recalcul des dix coches d'apres cet etat (L12813-12884) : elles
           vivent **dans** le tableau `strGameSetup`, l'octet 0 de chaque
           chaine ;
        4. trace, attente du clic, survol de la premiere ligne touchee
           (L12866-12982) ;
        5. saut dans le handler de la ligne (table de L13292-13308) ;
        6. `_check_cancel` : `0` retrace, `2` restaure la sauvegarde et
           sort, `1` sort (L13316-13358).

        **Tous les handlers sont transcrits depuis la Phase 75.** Ce
        paragraphe annoncait autrefois six levages (`_two_players`,
        `_show_world`, `_set_options`, `_save_load`, et l'absence de
        `_ground_in`) : les cinq premiers sont tombes au fil des Phases 68
        a 75, et la **Phase 77** a transcrit `_setup_display` (L380-498) -
        la ligne 15 pose donc simplement `_new_map = _ground_in + 2`
        (L13282-13284), consomme par `_do_action` code 8 (L18917-18931).
        Seule la liaison serie (`_write_serial` / `_read_serial`) reste hors
        portee : elle demande un second Amiga, et l'implementation
        `NotImplementedError` nomme toujours la routine manquante.
        """
        sim = self.sim
        st = sim.stats
        ticks = sim.setup_ticks

        # (1) sauvegarde - L12803-12811
        garde = (sim.serial_off, sim.paint_map, sim.player,
                 st[sim.player].act, sim.in_conquest)
        sim.bring_up_two = 0                              # L12812

        # (2) les dix coches, recalculees d'apres l'etat - L12813-12884.
        # L'entree cochee porte $81, l'autre $80.
        for i, actif in ((1, sim.serial_off != 0),
                         (2, sim.serial_off == 0),
                         (3, sim.paint_map == 0),
                         (4, sim.paint_map != 0),
                         (5, sim.player == 0),
                         (6, sim.player != 0),
                         (7, st[sim.player].act == 0),
                         (8, st[sim.player].act != 0),
                         (9, sim.in_conquest == -1),
                         (10, sim.in_conquest != -1)):
            ticks[i] = "\x81" if actif else "\x80"

        redessiner = True                          # -4,A5 = 1, L12803
        ok, cancel = self._cadres_boutons(*self._boite_game_setup())

        while True:
            self._redessiner = False
            if redessiner:                          # LAB_47822-47850
                self.requester(*self._boite_game_setup(), "", "")
                redessiner = False
            self.left_button = 2                    # L12925
            self._trace_game_setup()                # L12901-12924
            while self.left_button != 0:            # L12927-12929
                self._pompe()
                if not self.running:
                    return
            i = self._survol_game_setup()           # L12866-12982
            if self._exec_game_setup(i):             # L12980 + table L13292
                break                               # sortie directe (LAB_47E4E)
            redessiner = self._redessiner           # (-4,A5), L13257
            r = self.check_cancel(ok, cancel)        # LAB_47DCA, L13317-13319
            if r == 0:                               # L13322 : on retrace
                continue
            if r == 2:                               # L13323 : CANCEL
                (sim.serial_off, sim.paint_map, sim.player,
                 st[sim.player].act, sim.in_conquest) = garde
            break
        self.left_button = 2                        # L13960 `_return_to_game`
        self.compose()

    def _survol_game_setup(self) -> int:
        """L'index de la premiere ligne touchee, ou 17 (L12866-12982)."""
        from populous.game_setup import (GAME_SETUP_CONQUEST_MAX, GAME_SETUP_NB,
                                         GAME_SETUP_W, GAME_SETUP_X,
                                         GAME_SETUP_Y)
        sim = self.sim
        mx, my = self.mouse
        for i in range(GAME_SETUP_NB):
            x0 = GAME_SETUP_X[i] + 0x10              # L12886-12888
            if mx < x0:                              # L12889-12890
                continue
            if mx > x0 + GAME_SETUP_W[i] + 0x10:     # L12892-12893
                continue
            y0 = GAME_SETUP_Y[i] + 0x10              # L12894-12896
            if my < y0:                              # L12897-12898
                continue
            if my <= y0 + 8:                         # L12900-12901
                # L12974-12978 : en conquete les premieres lignes sont
                # neutralisees - l'index saute hors du tableau et le
                # dispatch de `LAB_47DB8` retombe sur le no-op.
                if i < GAME_SETUP_CONQUEST_MAX and sim.in_conquest != -1:
                    return 0x13
                return i
        return GAME_SETUP_NB                        # aucune ligne (L12969-12972)

    def _exec_game_setup(self, i: int) -> bool:
        """Le handler de la ligne `i`. Rend vrai si la boite se ferme.

        Ordre et branches releves sur la table de sauts de L13292-13308 ;
        chaque handler y aboutit soit a `LAB_47DCA` (on rend faux, la suite
        est `_check_cancel`), soit a `LAB_47E4E` (`_return_to_game`, on rend
        vrai).
        """
        sim = self.sim
        st = sim.stats
        ticks = sim.setup_ticks
        coche = "\x81"                              # ligne active
        vide = "\x80"                                # l'autre

        if i == 0:                                   # LAB_47D94 : le titre
            return False
        if i >= 17:                                  # LAB_47DB8 : hors tableau
            return False

        if i == 1:                                   # LAB_47968 ONE PLAYER
            ticks[1], ticks[2] = coche, vide          # L12987-12992
            if sim.serial_off == 0:                  # L12993
                # L12998 puis L13002 : le meme mot ecrit deux fois, il reste
                # donc `act = 1`. On garde les deux ecritures, pas l'effet.
                st[sim.player].act = 0                # L12998
                st[sim.player].act = 1                # L13002
                ticks[7], ticks[8] = coche, vide      # L13003-13004
                sim.serial_off = 1                   # L13005
            return False
        if i == 2:                                   # LAB_479CC TWO PLAYERS
            if sim.serial_off != 0:
                sim.bring_up_two = 1                 # L13028, puis sortie
                return True                          # LAB_47A0E-47A14
            ticks[2], ticks[1] = coche, vide          # L13014-13019
            self.two_players()                      # L13021
            return True
        if i == 3:                                   # LAB_47A1C PLAY GAME
            ticks[3], ticks[4] = coche, vide          # L13038-13043
            sim.paint_map = 0                        # L13044
            return False
        if i == 4:                                   # LAB_47A4A PAINT MAP
            ticks[4], ticks[3] = coche, vide          # L13050-13055
            sim.paint_map = 1                        # L13056
            return False
        if i == 5:                                   # LAB_47A7A GOOD
            ticks[5], ticks[6] = coche, vide          # L13062-13067
            self.set_tend_icons(-1, -1)              # L13068-13071
            self.set_mode_icons(-1, -1)              # L13072-13075
            # L13076-13084 : on echange les `act` des deux fiches. Le
            # listing ecrit `LAB_516D8` et `LAB_516AA` en dur, soit
            # `stats[1]` et `stats[0]`, et non `not_player`.
            tmp = st[sim.not_player].act             # L13076-13079
            st[1].act = st[sim.player].act           # L13080-13083
            st[0].act = tmp                          # L13084
            sim.player = 0                           # L13085
            self._pointeur_set_options(1, 4)         # L13086-13095
            sim.not_player = 1                       # L13097-13102
            self.set_tend_icons(-1, -1)              # L13104-13107
            self.set_mode_icons(-1, -1)              # L13108-13111
            return False
        if i == 6:                                   # LAB_47B3E EVIL
            ticks[6], ticks[5] = coche, vide          # L13117-13122
            self.set_tend_icons(-1, -1)              # L13123-13126
            self.set_mode_icons(-1, -1)              # L13127-13130
            tmp = st[sim.not_player].act             # L13131-13134
            st[1].act = st[sim.player].act           # L13135-13138
            st[0].act = tmp                          # L13139
            sim.player = 1                           # L13140
            self._pointeur_set_options(4, 4)         # L13141-13150
            sim.not_player = 0                       # L13152-13157
            self.set_tend_icons(-1, -1)              # L13159-13162
            self.set_mode_icons(-1, -1)              # L13163-13166
            return False
        if i == 7:                                   # LAB_47C04 HUMAN VS AMIGA
            ticks[7], ticks[8] = coche, vide          # L13172-13177
            st[sim.player].act = 0                   # L13178-13181
            if sim.serial_off != 0:                  # L13182
                st[1 - sim.player].act = 1           # L13184-13193
            return False
        if i == 8:                                   # LAB_47C5E AMIGA VS AMIGA
            ticks[8], ticks[7] = coche, vide          # L13200-13205
            st[sim.player].act = 1                   # L13206-13209
            if sim.serial_off != 0:                  # L13210
                st[1 - sim.player].act = 1           # L13212-13221
            return False
        if i == 9:                                   # LAB_47CBA CONQUEST
            if sim.serial_off == 0:                  # L13225 : inerte
                return False
            ticks[9], ticks[10] = coche, vide         # L13230-13235
            # L13237-13240 : `JSR _show_world ; MOVE.W D0,(_in_conquest)
            # ; MOVE.W #1,(_new_map) ; BRA.W LAB_47E4E`. Le monde rendu est
            # range tel quel - y compris -1, la graine saisie - puis la
            # boite se referme sur `LAB_47E4E` (`_return_to_game`).
            ret = self.show_world()                   # L13237
            sim.in_conquest = ret                     # L13238
            sim.new_map = 1                           # L13239
            return True                               # -> LAB_47E4E
        if i == 10:                                  # LAB_47D00 CUSTOM GAME
            ticks[10], ticks[9] = coche, vide         # L13247-13252
            sim.in_conquest = -1                     # L13253
            return False
        if i == 11:                                  # LAB_47D30 GAME OPTIONS
            self.set_options()                       # L13256
            self._redessiner = True                  # L13257 : (-4,A5) = 1
            return False                             # -> LAB_47DCA
        if i in (12, 13):                            # LAB_47D3E / LAB_47D56
            # L13267-13270 : `TST.W (_serial_off) ; BEQ.S LAB_47D70`. La
            # ligne 13 (*LOAD A GAME*) n'ouvre l'ecran que si la liaison
            # serie est **coupee** - donc en un seul joueur. La ligne 12
            # (*SAVE A GAME*, L13259-13266) n'a pas cette garde.
            if i == 13 and sim.serial_off == 0:       # L13268-13269
                return False
            # L13261 (`_save_load(1)`) et L13071 (`_save_load(0)`) : le
            # meme ecran, la seule difference est le titre. Un retour non
            # nul fait sortir de la boite par `_return_to_game` (L13264,
            # L13275) - donc, de l'exterieur, la boite se referme.
            self.save_load(i == 12)                  # L13061 / L13261
            return True
        if i == 14:                                  # LAB_47D72 NEXT MAP
            sim.new_map = 1                          # L13279, puis LAB_47E4E
            return True
        if i == 15:                                  # LAB_47D7C RESTART
            # L13282-13284 : `_new_map = _ground_in + 2`, puis `BRA.W
            # LAB_47E4E` (`_return_to_game`). Le `+2` est la marque «
            # regenere tel quel » : `_do_action` code 8 en fera
            # `_setup_display(0, _new_map - 2)` = `_setup_display(0,
            # _ground_in)`, en passant par L18920-18922 qui restaure
            # `_seed = _start_seed` puisque `_new_map != 1`.
            # `self.ground` **est** `_ground_in` du listing : c'est ce que
            # `set_ground` (L4C12A `_ground_in = $A(A5)`) et
            # `_setup_display` (L399, L438-441) tiennent a jour.
            sim.new_map = self.ground + 2            # L13282-13284
            return True                              # -> LAB_47E4E
        # i == 16                                    # LAB_47D8A SURRENDER
        self.surrender = sim.player                  # L13287, puis LAB_47E4E
        return True

    def _pointeur_set_options(self, si_mode2, si_mode4):
        """`_pointer` apres un changement de tribu (L13086-13095 / L13141).

        `CMPI.W #$0002,(_mode)` : le mode 2 force le pointeur du joueur.
        Sinon `BTST #2,bitfield_51645` - le **bas octet** de `_mode`
        (Phase 63) - et le pointeur vaut alors `player + 2`.
        """
        if self.sim.mode == 2:                       # L13086-13088
            self.sim.pointer = si_mode2
            return
        if self.sim.mode & 4:                        # BTST #2, bas octet
            self.sim.pointer = self.sim.player + 2   # L13091-13095

    def _boite_set_options(self):
        """`(x, y, largeur, hauteur)` de la boite *SET GAME OPTIONS* (L13367)."""
        from populous.set_options import SET_OPTIONS_BOXE
        return SET_OPTIONS_BOXE

    def _draw_set_option(self, i: int, txt: str) -> None:
        """Une ligne de *SET GAME OPTIONS* a l'index `i` (L13403-13416).

        `_text(d_screen, _set_text[i]+$20, LAB_523B0[i]+$18, txt)` ; `_text`
        prend x en unites de 8 px, y en lignes de pixels.
        """
        from populous.set_options import SET_OPTIONS_X, SET_OPTIONS_Y
        x = SET_OPTIONS_X[i] + 0x20                  # L13412-13414
        y = SET_OPTIONS_Y[i] + 0x18                  # L13404-13406
        self.ren.draw_text(self.frame, x >> 3, y, txt)

    def _trace_set_options(self) -> None:
        """Le trace du titre, des cinq paires et de la rustine de debug."""
        from populous.set_options import (SET_OPTIONS_BLANC, SET_OPTIONS_PASTICHE,
                                           SET_OPTIONS_TEXTE, SET_OPTIONS_X,
                                           SET_OPTIONS_Y)
        sim = self.sim
        ticks = sim.set_option_ticks
        self._draw_set_option(0, SET_OPTIONS_TEXTE[0])        # L13374-13382
        for j in range(5):                                   # L13386-13446
            col = 2 if (sim.game_mode >> j) & 1 else 1        # L13386-13396
            i = 2 * j + col
            self._draw_set_option(i, SET_OPTIONS_BLANC)        # L13398
            self._draw_set_option(i, ticks[i] + SET_OPTIONS_TEXTE[i][1:])
        # L13447-13482 : rustine de debug, « new code added here » dans le
        # listing. Elle ecrit « LANDSCAPE NO » puis le numero de terrain a
        # `buf + 13` - juste apres l'espace final, en recouvrant le zero -
        # et l'affiche sous la derniere paire, avec un y de `+ $22` et non
        # `+ $18`.
        #
        # Le listing y met `_start_seed` (L13451-13458) : c'est le mot que
        # `_setup_display` pose en tete de branche (L430, L392) et que la
        # ligne 15 restaure (L18922). Le port le suit desormais - le mot
        # unique `self.seed` a ete double en Phase 77.
        prefixe, decalage = SET_OPTIONS_PASTICHE
        buf = prefixe + str(self.start_seed)
        i = 2 * 4 + col                                       # L13459-13463
        x = SET_OPTIONS_X[i] + 0x20                           # L13473-13475
        y = SET_OPTIONS_Y[i] + 0x22                           # L13465-13467
        self.ren.draw_text(self.frame, x >> 3, y, buf)

    def _survol_set_options(self):
        """L'index de la ligne touchee, ou `None` (L13490-13587)."""
        from populous.set_options import (SET_OPTIONS_SURVOL, SET_OPTIONS_W,
                                           SET_OPTIONS_X, SET_OPTIONS_Y)
        sim = self.sim
        mx, my = self.mouse
        if sim.in_conquest != -1:                        # L13500-13501
            return None
        for i in SET_OPTIONS_SURVOL:
            # L13494-13496 : `x0 = _set_text[i] + $20`
            x0 = SET_OPTIONS_X[i] + 0x20
            if mx < x0:                                  # L13497-13499
                continue
            # L13507-13510 : `D2 = _set_text[i] + LAB_523B2[i] + $20`, soit
            # exactement `x0 + w`. Contrairement a `_options` et `GAME
            # SETUP`, le decalage de $20 n'apparait **qu'une** fois, a
            # gauche : la zone fait 8 px de large, pas 40.
            if mx > x0 + SET_OPTIONS_W[i]:               # L13511-13513
                continue
            y0 = SET_OPTIONS_Y[i] + 0x18                 # L13516-13518
            if my < y0:                                  # L13519-13521
                continue
            if my <= y0 + 8:                             # L13524-13529
                return i
        return None

    def set_options(self) -> None:
        """``_set_options`` (L13362-13605) - l'ecran *SET GAME OPTIONS*.

        Appele par la ligne 11 (*GAME OPTIONS*) du dialogue `GAME SETUP`
        (L13256). Cinq paires de choix exclusifs, un bit de `_game_mode`
        chacune ; la boite est plus petite que celle de *GAME SETUP*
        (`$100` x `$70`, L13367-13370) parce que les deux colonnes sont
        a x = 16, cote a cote sur la meme ligne.

        Boucle : sauvegarde de `_game_mode` (L13364), trace, attente du clic
        (L13484-13488), survol, bascule du bit, `_check_cancel` (L13489-13603).
        Un `0` retrace, un `2` restaure `_game_mode`, un `1` sort.

        **Point d'asm** : les deux colonnes d'une paire ont le meme x et le
        meme y, et la zone cliquable ne couvre que les huit pixels de la
        coche. Cliquer la colonne 1 bascule le bit de la paire, et la coche
        part alors sur la colonne 2 (L13537-13545) - c'est le bit qui decide,
        pas la colonne cliquee.
        """
        from populous.set_options import (SET_OPTIONS_BLANC,
                                           SET_OPTIONS_TEXTE)
        sim = self.sim
        garde = sim.game_mode                            # L13364
        ok, cancel = self._cadres_boutons(*self._boite_set_options())

        while True:
            self.requester(*self._boite_set_options(), "", "")  # L13365-13373
            # Le prologue reclasse les dix coches d'apres `_game_mode`
            # (L13386-13396) : c'est lui, et non le contenu du ROM, qui fait
            # foi a l'affichage.
            ticks = [s[:1] for s in SET_OPTIONS_TEXTE]
            for j in range(5):
                ticks[2 * j + 2] = ("\x81" if (sim.game_mode >> j) & 1
                                    else "\x80")
            sim.set_option_ticks = ticks
            self._trace_set_options()
            self.left_button = 2                          # L13484
            while self.left_button != 0:                  # L13485-13488
                self._pompe()
                if not self.running:
                    return
            i = self._survol_set_options()               # L13490-13587
            if i is not None:
                # L13530-13546 : le bit est celui de la paire, et la coche
                # part sur `i` ou `i + 1` selon sa nouvelle valeur.
                bit = 1 << (i >> 1)                       # L13531-13534
                sim.game_mode ^= bit                      # L13536
                k = i + 1 if (sim.game_mode & bit) else i  # L13537-13545
                ticks[k] = "\x81" if (sim.game_mode & bit) else "\x80"
                self._draw_set_option(k, SET_OPTIONS_BLANC)   # L13547-13561
                self._draw_set_option(k, ticks[k] + SET_OPTIONS_TEXTE[k][1:])
            r = self.check_cancel(ok, cancel)             # L13489-13491
            if r == 0:                                    # L13594
                continue
            if r == 2:                                    # L13595-13597
                sim.game_mode = garde
            break
        self.left_button = 2                              # L13603
        self.compose()

    def save_game(self, chemin: str) -> int:
        """``_save_game(nom)`` (L17123-17373). **Rend 0 en cas de succes.**

        L'inversion est celle du listing : `(-12,A5)` vaut 1 au depart
        (L17126) et n'est mis a zero qu'apres le dernier `Write` reussi
        (L17365). L'appelant teste donc `TST.W D0 ; BEQ` pour la reussite
        (L46093).

        Le nom recoit le suffixe `.GAM` comme dans le listing
        (L17130-17153) : une seule fois, et cherche a partir de l'octet 4.

        **ECART declare** : `Open(name, $3EE)` ouvrait le fichier en
        lecture/ecriture, donc un fichier existant etait ecrase. Le port
        ecrit en mode binaire truncant, ce qui a le meme effet.
        """
        from populous.savegame import nom_de_fichier
        from populous.saveio import pack_moteur
        nom = nom_de_fichier(chemin)
        donnees = pack_moteur(self, nom)
        try:
            with open(nom, "wb") as f:            # `Open(name, $3EE)`
                f.write(donnees)
        except OSError:
            return 1                             # LAB_4AE0A
        return 0                                 # L17365

    def load_game(self, chemin: str) -> bool:
        """``_load_game(nom)`` (L17412-17691). Rend vrai si l'entete est bonne.

        Apres les 25 lectures, la routine :

        * appelle `load_ground(0, _ground_in)` sans regarder le retour
          (L17586-17589) ;
        * recalcule `not_player` depuis `player` (L17590-17595) ;
        * redessine (`set_tend_icons`, `set_mode_icons`, `Setscreen`,
          `draw_map`) ;
        * **recalcule `_no_peeps`** : elle remonte depuis la fiche 207 tant
          que `life == 0` (L17623-17638) - le nombre d'unites n'est donc pas
          relu du fichier ;
        * met a zero `act`, `p1` et `p2` des deux fiches (L17639-17649) ;
        * appelle `get_heading` sur toute unite qui a une cible (L17650-17670) ;
        * repose `_pointer` quand `_mode == 2` : `player == 1 ? 4 : 1`
          (L17671-17682).
        """
        from populous.savegame import nom_de_fichier
        from populous.saveio import unpack_moteur
        nom = nom_de_fichier(chemin)
        try:
            with open(nom, "rb") as f:            # `Open(name, $3ED)`
                donnees = f.read()
        except OSError:
            return False                         # LAB_4B226
        if not unpack_moteur(self, donnees):     # L17453, LAB_4B21C
            return False
        self.load_ground(self.sim.ground_in, 0)  # L17586-17589 (`CLR.W`)
        self.set_tend_icons(-1, -1)              # L17597-17603
        self.set_mode_icons(-1, -1)
        sim = self.sim
        i = 0xCF                                  # L17623 : 207
        while i >= 0 and sim.peeps[i].life == 0:
            i -= 1
        sim.no_peeps = i + 1                     # L17636-17638
        for t in (0, 1):                         # L17639-17649
            sim.stats[t].act = 0
            sim.stats[t].p1 = 0
            sim.stats[t].p2 = 0
        for k in range(sim.no_peeps):            # L17650-17670
            p = sim.peeps[k]
            if p.target != 0:
                sim.get_heading(k)
        if sim.mode == 2:                        # L17671-17682
            sim.pointer = 4 if sim.player == 1 else 1
        return True

    def _boite_save_load(self):
        """`(x, y, largeur, hauteur)` de la boite de sauvegarde (L10523)."""
        return (0x48, 0x10, 0xB0, 0xB0)

    def _trace_save_load(self, sauvegarder: bool) -> None:
        """Le trace de l'ecran des douze emplacements (L10520-10750).

        `_text` prend **x et y en pixels** et le port les convertit en
        unites de 8 px : `_text($58, $18, "SAVE GAME")` (L10530) est donc
        `(11, 24)`, pas l'inverse.

        Le masque `(-144,A5)` ne sert qu'aux rafraichissements - bit 0 :
        relister le tiroir (L10573-10598), bit 1 : redessiner les douze
        lignes (L10602-10674), bits 2 et 3 : les deux champs (L10676,
        L10711). Le port redessine tout a chaque tour, qui est le cas
        ouvert du masque `$000F` pose en tete (L10496) ; seuls le re-listage
        et le repositionnement du defilement restent conditionnes, et sont
        faits par `save_load` lui-meme.
        """
        r, d = self.ren, self.frame
        from populous.world import WORLD_TRAIT        # `LAB_525C8` (L24927)
        self.requester(*self._boite_save_load(), "", "")
        r.draw_text(d, 0x58 >> 3, 0x18,              # L10530-10535 `(-10,A5)`
                    "SAVE GAME" if sauvegarder else "LOAD GAME")
        r.draw_text(d, 0xD8 >> 3, 0x22, "\x88")      # L10536-10541 `LAB_46192`
        r.draw_text(d, 0xD8 >> 3, 0x7A, "\x89")      # L10542-10547 `LAB_46194`
        r.draw_text(d, 0x58 >> 3, 0x84, "DIRECTORY")  # L10548-10553
        r.draw_text(d, 0x58 >> 3, 0x97, "FILE NAME")  # L10554-10559
        # `LAB_525C8` (L24927) = seize octets `$82` : le fond du champ du
        # tiroir (L10560-10565) et de celui du nom (L10566-10571).
        r.draw_text(d, 0x58 >> 3, 0x8D, WORLD_TRAIT)
        r.draw_text(d, 0x58 >> 3, 0xA0, WORLD_TRAIT)
        for k in range(12):                          # L10604-10674 : les
            j = self._saves_defil + k                # douze lignes, depuis
            nom = b""                                # l'offset `(-134)`
            if 0 <= j < len(self._saves_liste):
                nom = self._saves_liste[j].rstrip(b"\x00")
            r.draw_text(d, 0x58 >> 3, 0x22 + k * 8, _remplir(nom))
        # L10676-10709 puis L10711-10750 : les deux champs, recopies sur
        # seize octets completes de `$82` au-dela du texte.
        r.draw_text(d, 0x58 >> 3, 0x8D, _remplir(self._saves_drawer))
        r.draw_text(d, 0x58 >> 3, 0xA0, WORLD_TRAIT)  # L10739-10744
        r.draw_text(d, 0x58 >> 3, 0xA0, _remplir(self._saves_nom))

    def _survol_save_load(self):
        """L'index de l'emplacement clique, ou `None` (L10759-10784).

        La zone est `$58 <= x <= $D8` et `$22 <= y <= $82` (L10759-10766) ;
        la ligne se lit `(y - $22) >> 3`, ajoute a l'offset de defilement
        `self._saves_defil` (L10767-10771). Une ligne au-dela du contenu
        n'est pas selectionnable (L10772-10774).
        """
        mx, my = self.mouse
        if mx < 0x58 or mx > 0xD8:                     # L10759-10762
            return None
        if my < 0x22 or my > 0x82:                     # L10763-10766
            return None
        i = ((my - 0x22) >> 3) + self._saves_defil     # L10767-10771
        if i >= len(self._saves_liste):                # L10772-10774
            return None
        self._saves_nom = self._saves_liste[i].rstrip(b"\x00").decode("latin-1")
        return i

    def _defiler_save_load(self, delta: int) -> None:
        """Les deux fleches a droite (L10819-10842)."""
        n = len(self._saves_liste)
        if delta < 0:                                  # fleche du haut
            if self._saves_defil:                      # L10827-10828
                self._saves_defil -= 1
            return
        if self._saves_defil + 5 < n:                  # L10837-10840
            self._saves_defil += 1

    def save_load(self, sauvegarder: bool) -> int:
        """``_save_load(sauvegarder)`` (L10493-10972).

        **Rend 1 si l'ecran a ete valide, 0 sinon.** Appele par les lignes 12
        (*SAVE A GAME*) et 13 (*LOAD A GAME*) du dialogue *GAME SETUP*.

        La boucle :

        * `_requester(d_screen, $48, $10, $B0, $B0, (-130), _end_cancel)`
          (L10523-10529) ;
        * le tiroir est liste par `_get_a_dir` puis `_sort` quand le masque
          `(-144)` porte le bit 0 (L10573-10598) - c'est le cas a
          l'ouverture (`$000F`, L10496) et apres une edition du tiroir
          (`$0003`, L10800), donc **une fois au depart puis a chaque changement
          de repertoire**, et non une seule fois ;
        * chaque clic dans la zone `$58..$D8` x `$22..$82` met `_filename` a
          l'entree correspondante (L10759-10784) ; les deux fleches, dans
          `$D8..$E0`, font defiler (L10818-10842) ;
        * les deux zones d'edition `$8D..$95` et `$A0..$A8` (L10786-10815)
          ouvrent `_get_name` sur `_drawer` puis `_filename`, avec
          `x = $58`, `y = $8D` / `$A0` et `maxlen = $10` ;
        * chaque branche **saute** a `LAB_45F7C` (L10801, L10816), donc a
          `_check_cancel` : les fleches ne sont plus consultees ensuite ;
        * `_check_cancel` : `0` reboucle au trace (L10970-10971), `2` sort
          sans rien faire, `1` assemble le chemin (L10832-10886) puis
          appelle `_save_game` ou `_load_game` (L10888-10894).

        Apres une sauvegarde reussie, la routine met `_saved = 1` (L10930)
        puis **verifie que `level.dat` est present** : elle boucle sur
        `Open("level.dat", $3ED)` tant que le fichier manque, en affichant
        `strInsertDisk` (L10931-10950).
        """
        from populous.saveslots import chemin_complet, get_a_dir, sort
        self._saves_defil = 0
        self._saves_nom = ""
        self._saves_liste = get_a_dir(self._saves_drawer)
        sort(self._saves_liste)                     # L10597
        ok, cancel = self._cadres_boutons(*self._boite_save_load())

        while True:
            self._trace_save_load(sauvegarder)
            self.left_button = 2                     # L10753
            while self.left_button != 0:             # L10754-10757
                self._pompe()
                if not self.running:
                    return 0
            # LAB_45EAC (L10758) : **une seule** zone est testee, et
            # chaque branche saute a `LAB_45F7C` puis `_check_cancel`
            # (L10801, L10816) - les fleches ne sont plus consultees.
            mx, my = self.mouse
            if 0x58 <= mx <= 0xD8:                   # L10759-10762
                if 0x22 <= my <= 0x82:               # L10763-10766
                    self._survol_save_load()         # L10767-10784
                elif 0x8D <= my <= 0x95:             # L10787-10790
                    # L10791-10801 : `_get_name(_drawer, $58, $8D, $10, ...)`
                    # puis `(-144) = 3`, dont le bit 0 reliste le tiroir.
                    self._saves_drawer = self.get_name(
                        self._saves_drawer, 0x58, 0x8D, 0x10, ok, cancel)
                    self._saves_liste = get_a_dir(self._saves_drawer)
                    sort(self._saves_liste)           # L10589-10598
                    self._saves_defil = 0             # L10600 `(-134)`
                elif 0xA0 <= my <= 0xA8:             # L10802-10815
                    self._saves_nom = self.get_name(
                        self._saves_nom, 0x58, 0xA0, 0x10, ok, cancel)
            elif 0xD8 <= mx <= 0xE0:                 # LAB_45F7E, L10819-10822
                if 0x22 <= my <= 0x2A:               # L10823-10826
                    self._defiler_save_load(-1)      # L10827-10830
                elif 0x7A <= my <= 0x82:             # L10833-10836
                    self._defiler_save_load(1)       # L10837-10842
            r = self.check_cancel(ok, cancel)        # L10843-10848
            if r == 0:                                # L10849
                continue
            if r == 2:                                # L10850
                return 0
            if not self._saves_nom:                   # L10853-10854
                return 0
            chemin = chemin_complet(self._saves_drawer, self._saves_nom)
            if sauvegarder:
                if self.save_game(chemin) == 0:      # L10888-10894
                    self._saved = True                # L10930
                    self._verifier_level_dat()        # L10931-10950
                return 1
            self.load_game(chemin)                    # L10952-10954
            return 1

    def get_name(self, texte: str, x: int, y: int, maxlen: int,
                 end_ok, end_cancel) -> str:
        """``_get_name(ecran, texte, x, y, maxlen, end_ok, end_cancel)``
        (L10307-10489) : l'editeur de nom au clavier.

        Sept arguments, dans l'ordre des pushes des six appels du listing
        (L10798, L10814, L11177, L11628, L11675, L12249) : `ecran` est
        `_d_screen`, `texte` est le tampon que l'original modifie **en
        place** - le port le rend, l'appelant l'affecte.

        **Remplissage** (L10313-10347) : le champ est complete jusqu'a
        `maxlen`. Tout octet `$20` **ou inferieur**, et tout octet situe
        **apres** le terminateur (le drapeau `(-44)` de L10321), devient
        `$82` - le trait de soulignement - puis le terminateur est pose a
        ``texte[maxlen]`` et non a ``strlen`` (L10342-10344). Le champ
        affiche fait donc **toujours `maxlen` glyphes**, jamais un de plus
        ni un de moins. `scratch`, le tampon local de 40 octets, recoit
        `$82` partout et n'est dessine qu'une fois au depart (L10349).

        **Clignotement** (L10356-10380) : un compteur parcourt
        ``maxlen + 20`` (`DIVS` puis `SWAP` pour le reste, L10361-10364)
        ; a chaque tour ou le reste est nul, ``texte[-46]`` alterne
        `$82` et `$83` (L10366-10380). Le curseur est donc **pose par
        dessus** le caractere de la position - c'est cela, et rien d'autre,
        qui fait marcher la retour arriere.

        **Saisie** : `_asckey` compris entre `$20` et `$7A` avec
        ``curseur < maxlen - 1`` (L10392-10400) ecrit le caractere, en
        **majuscules** quand il est dans `$61..$7A` (L10410-10414, qui
        modifie aussi le global `_asckey`) ; `$08` / `$7f` reculent d'un
        rang en posant `$82` a l'ancienne position (L10422-10432) ;
        `$0d` valide (L10435-10437). Tout le reste est ignore.

        **Sortie** : `_check_cancel` a chaque tour (L10439-10443). `2`
        efface ``texte[0]`` et rend la main (L10445-10451), `1` valide,
        `0` remet `_left_button = 2` s'il valait 0 (L10454-10459) et
        reboucle. **La souris est vivante pendant toute cette boucle** :
        `_mouse` tourne sur l'interruption VERTB (`_setup_interrupt`,
        L187-207, `___AddIntServer(..., 5)`), d'ou le `_pompe` de chaque
        tour - sans lui les boutons ne repondraient pas.

        La validation (L10460-10489) pose `$82` sur le curseur, redessine,
        puis **ramene le tampon en arriere** tant que l'octet lu est
        `> $80` : les traits de fin sont effaces sans autre redraw, le
        champ garde donc a l'ecran le nom suivi de ses soulignements.
        """
        r, d = self.ren, self.frame
        # (-46,A5) : la position du curseur, `strlen` au depart (L10310)
        curseur = len(texte)
        # Le tampon d'appelant, sur `maxlen + 1` octets : l'original n'ecrit
        # jamais `texte[maxlen]` avant L10344, qui y pose le zero - d'ou
        # l'octet de terminaison fourni par la taille ci-dessous.
        buf = bytearray(max(len(texte), maxlen) + 1)
        donnees = bytes(ord(c) & 0xFF for c in texte)
        buf[:len(donnees)] = donnees
        # (-40,A5) : 40 octets de local (le LINK fait -46, soit 2+2+2+40)
        scratch = bytearray(max(40, maxlen + 1))
        # ---- L10313-10347 : le remplissage ------------------------------
        apres_fin = 0                           # (-44,A5), pose en L10321
        i = 0                                   # (-42,A5)
        while i != maxlen:                      # L10338-10341
            if buf[i] == 0:
                apres_fin = 1                   # L10319-10321
            if buf[i] <= 0x20 or apres_fin:     # BLS / TST+BEQ, L10325-10328
                buf[i] = 0x82                   # L10329-10332
            scratch[i] = 0x82                   # L10333-10336
            i += 1
        buf[maxlen] = 0                         # L10342-10344
        scratch[maxlen] = 0                     # L10345-10347

        self.left_button = 2                    # L10348
        r.draw_text(d, x >> 3, y, _champ(scratch))       # L10349-10354
        compteur = 0                            # L10355 CLR.W (-44)
        self._saisie = True
        try:
            while True:                         # ---- LAB_4597A (L10356) ----
                t = compteur                    # L10357
                compteur += 1                   # L10358
                if t % (maxlen + 20) == 0:      # L10359-10364
                    # L10366-10380 : `$83` si le curseur etait deja `$82`
                    buf[curseur] = 0x83 if buf[curseur] == 0x82 else 0x82
                r.draw_text(d, x >> 3, y, _champ(buf))   # L10382-10387
                self._pompe()                   # la VERTB de L187-207
                if not self.running:
                    return ""
                if self._keyboard() != 0:       # L10388-10390
                    code = ord(self._asckey)
                    if 0x20 <= code <= 0x7A and curseur < maxlen - 1:
                        buf[curseur] = 0x82             # L10401-10403
                        r.draw_text(d, x >> 3, y, _champ(buf))   # L10404
                        if 0x61 <= code <= 0x7A:        # L10410-10414
                            code -= 0x20
                            self._asckey = chr(code)
                        buf[curseur] = code             # L10419
                        curseur += 1                    # L10417
                    elif code in (0x08, 0x7F):          # L10422-10425
                        if curseur != 0:                # L10427-10428
                            ancien = curseur            # L10429-10432
                            curseur -= 1
                            buf[ancien] = 0x82
                    elif code == 0x0D:                  # L10435-10437
                        break                           # -> LAB_45ABA
                # ---- LAB_45A82 (L10438) --------------------------------
                rr = self.check_cancel(end_ok, end_cancel)
                if rr == 0:                       # L10444
                    if self.left_button == 0:     # L10455-10456
                        self.left_button = 2      # L10457
                    continue                      # L10459 BRA LAB_4597A
                if rr == 2:                       # L10445-10446
                    return ""                     # L10447-10451 CLR.B (A0)
                break                             # L10452-10453 -> LAB_45ABA
            # ---- LAB_45ABA (L10460) : la validation ---------------------
            buf[curseur] = 0x82                   # L10461-10463
            r.draw_text(d, x >> 3, y, _champ(buf))       # L10464-10469
            i = maxlen - 1                        # L10470-10472
            while True:                           # LAB_45AFC puis LAB_45AEC
                octet = buf[i] if 0 <= i < len(buf) else 0   # L10480-10484
                if octet <= 0x80:                 # BLS -> LAB_45B16
                    break
                if i < 0:                         # TST.W / BGE
                    break
                buf[i] = 0                        # L10475-10477
                i -= 1                            # L10478
            return _champ(buf)
        finally:
            self._saisie = False

    def _verifier_level_dat(self) -> None:
        """L10931-10950 : `level.dat` doit etre lisible, sinon on le demande.

        La boucle du listing est ``LAB_46110`` a ``LAB_4613E``::

            h = Open("level.dat", $3ED)
            if h > 0: Close(h)
            else:     _do_message(strInsertDisk, 0)
            if h <= 0: goto LAB_46110

        Le point d'entree est en tete, donc on **reteste** apres le
        dialogue : le fichier peut etre apparu. Le port n'a pas de disque
        a insérer et les candidats sont fixes au demarrage — le dialogue
        tourne donc tant que la fenetre reste ouverte, exactement comme
        l'original en l'absence de disque. ``do_message`` rend 0 si la
        fenetre est fermee, et c'est la seule sortie.
        """
        from populous.message import INSERT_DISK
        while not self._level_dat_present():       # LAB_46110, L10931-10938
            if self.do_message(INSERT_DISK) == 0:  # L10943-10946, annuler=0
                return                             # ECART : fenetre fermee

    def _level_dat_present(self) -> bool:
        """``Open("level.dat", $3ED) > 0`` (L10931-10938), sans l'ouvrir.

        Le port cherche les memes ``_CANDIDATES`` que
        :meth:`_lire_level_dat`, donc les memes endroits que l'original
        cherche son fichier.
        """
        import os
        from populous.conquest import _CANDIDATES
        return any(os.path.exists(str(p)) for p in _CANDIDATES)

    def _trace_show_world(self, i: int, lignes, colonnes) -> None:
        """Un tour de la boucle de tracé de `_show_world` (L12380-12743).

        Deux choses se passent, dans cet ordre : le handler de la ligne,
        puis `LAB_47620` qui trace le libelle. Les handlers `line_1` a
        `line_7` ne font que remplir le tampon (`_put_in_string`) - c'est
        fait en amont par :func:`populous.world.resumer` - et les lignes
        9 a 14 tracent **elles-memes** leurs valeurs, a part du libelle :
        deux ``___text`` chacune.

        Les colonnes de ces deux appels sont relevees telles quelles :

        * `y` = ``WORLD_Y[i] + $18`` (L12629, L12650) ;
        * `x` = ``WORLD_X[i] + WORLD_W[i] + $10`` pour la premiere valeur
          (L12594-12596) et ``+ $48`` de plus pour la deuxieme (L12620-12622).

        ``WORLD_W[i]`` vaut 120 pour ces lignes, soit `15 * 8` : la
        colonne YOU du libelle ``"               YOU    HIM"`` ecrit a la
        ligne 8, qui pose le reperage des deux colonnes.
        """
        from populous.world import WORLD_W, WORLD_X, WORLD_Y
        r, d = self.ren, self.frame
        if i >= 9:                                # `line_9` puis `line_0`
            y = WORLD_Y[i] + 0x18
            x_vous = (WORLD_X[i] + WORLD_W[i] + 0x10) >> 3
            x_lui = (WORLD_X[i] + WORLD_W[i] + 0x10 + 0x48) >> 3
            r.draw_text(d, x_vous, y, colonnes[i][0])
            r.draw_text(d, x_lui, y, colonnes[i][1])
        # LAB_47620 (L12720-12740) : le libelle lui-meme
        r.draw_text(d, (WORLD_X[i] + 0x10) >> 3, WORLD_Y[i] + 0x18, lignes[i])

    def _lire_level_dat(self, index: int) -> bool:
        """`Open` / `Seek` / `Read` / `Close` sur ``level.dat`` (L12340-12367).

        ``Seek(h, index * 10, 1)`` part de l'ouverture, donc la position 0.
        L'Amiga rend -1 quand la recherche echoue ; au moins une lecture a
        lieu sinon. Un fichier plus court que l'entree rend **zero octet** :
        le tampon `_conquest` garde alors son contenu precedent - c'est ce
        que fait l'ecriture partielle ci-dessous, fidèle au ``Read``.
        """
        import os
        from populous.conquest import _CANDIDATES
        chemin = next((p for p in _CANDIDATES if os.path.exists(p)), None)
        if chemin is None:                        # `Open` rend <= 0 (L12345)
            return False
        with open(str(chemin), "rb") as f:
            f.seek(index * 10)                    # L12347-12355
            donnees = f.read(0xA)                 # L12358-12363
        self._conquest[:len(donnees)] = donnees
        return True

    def show_world(self) -> int:
        """``_show_world()`` (asm L12190-12773). Rend le monde choisi.

        L'ecran *WORLD TO CONQUER*, ouvert par la ligne 9 (CONQUEST) de
        *GAME SETUP*. Trois boucles emboitees, dans l'ordre du listing :

        **`LAB_47064`** (L12207) pose la boîte et son titre.
        **`LAB_470AC`** (L12227) dessine le trait, le champ de saisie, et
        lit la saisie :

        * si le texte est **entierement numerique**, c'est une graine :
          `_start_seed = _seed = n`, et la routine rend -1 sans jamais
          toucher a ``level.dat`` (L12262-12273) ;
        * sinon le nom passe par :func:`populous.decode.decode` ;
          `GENESIS` force l'indice 0 (L12277-12296) ;
        * tant que l'indice est negatif, on reste dans la boucle, apres
          avoir affiche ``NO SUCH WORLD`` (L12297-12312).

        `saisi` vaut 0 a la premiere visite (L12192 l'efface), puis 1
        des qu'un monde a ete valide (L12314). Le point d'entree qui le
        relit est `LAB_47064`, ou reviennent deux chemins : L12376, apres
        L12370 qui **efface** `saisi` (disque absent), et **L12758**,
        l'abandon *NEW GAME*, qui lui **le laisse a 1**. C'est donc par
        NEW GAME que la saisie passe par `_get_name` (L12249) : apres un
        premier monde accepte, jamais avant - et la deuxieme visite est
        la premiere a pouvoir editer le champ.
        ``tools/check_show_world_modal.py`` relit ces quatre lignes, puis
        fait entrer un nom au clavier par ce chemin.

        `(-20) = (-18) / 25` (L12315-12319) donne l'entree de
        ``level.dat``. En echec l'affichage demande le disque et la boite
        s'ouvre de nouveau (L12345-12376) - ce qui tourne en boucle tant
        que le fichier manque, exactement comme l'original.

        **`LAB_47236`** (L12377) trace les quinze lignes, attend le
        relachement du bouton (L12745-12747), puis :
        `_check_cancel` rend 0 (retracer), 2 (effacer `_message` et
        rouvrir) ou 1 (OK). OK arme une partie neuve a un joueur et rend
        le monde (L12762-12773), que la ligne 9 range dans
        `_in_conquest` (L13238).

        **Rendu numerique** (L12267-12273) : `_start_seed = _seed = n`,
        deux ecritures distinctes (L12270 puis L12271) - le port les suit
        depuis la Phase 77, ou `self.start_seed` a ete cree a cote de
        `self.seed`.
        """
        from populous.decode import decode
        from populous.message import INSERT_DISK
        # `strGENESIS1` (L12782) et `strGENESIS2` (L12786) sont les memes
        # sept octets, ecrits deux fois dans le listing : une seule constante
        # dans le port.
        from populous.world import (WORLD_BOXE, WORLD_GENESIS,
                                    WORLD_GRAINE,
                                    WORLD_NB, WORLD_OK_TEXTE,
                                    WORLD_CANCEL_TEXTE, WORLD_PAS_DE_MONDE,
                                    WORLD_TRAIT, WORLD_TEXTE, WORLD_X,
                                    WORLD_Y,
                                    reinit, resumer, valeurs_colonnes)
        r, d = self.ren, self.frame
        sim = self.sim
        saisi = 0                           # (-22,A5), L12192
        monde = -1                          # (-18,A5)
        brut = self._conquest
        if not self._message:               # L12201-12206
            self._message = WORLD_GENESIS
        reinit()                            # `strWorldToConquer` au complet
        ok, cancel = self._cadres_boutons(*WORLD_BOXE,
                                          WORLD_OK_TEXTE, WORLD_CANCEL_TEXTE)

        while True:                         # ---- LAB_47064 (L12207) ----
            self.requester(*WORLD_BOXE, "", "")
            # L12217-12226 : `___text(_c_text + $10, LAB_51EEC + $18,
            # strWorldToConquer)` - les deux index non signes valent l'entree
            # 0 : titre, puisque la boucle commence a i = 1.
            r.draw_text(d, (WORLD_X[0] + 0x10) >> 3,
                        WORLD_Y[0] + 0x18, WORLD_TEXTE[0])

            while True:                     # ---- LAB_470AC (L12227) ----
                r.draw_text(d, 0x20 >> 3, 0x2C, WORLD_TRAIT)   # L12228-12233
                r.draw_text(d, 0x20 >> 3, 0x2C, self._message)  # L12234-12239
                if saisi:                   # L12240-12250
                    # `PEA (-118)`, `PEA (-72)`, `$10`, `$2C`, `$20`,
                    # `_message`, `_d_screen` : les memes `ok`/`cancel`
                    # que `_check_cancel` de L12749.
                    self._message = self.get_name(
                        self._message, 0x20, 0x2C, 0x10, ok, cancel)
                n = _atoi(self._message) & 0xFFFF     # L12262-12265
                if n != 0:                  # L12266
                    # L12270-12271 : `MOVE.W D0,(_start_seed)` **puis**
                    # `MOVE.W D0,(_seed)` - deux ecritures, deux variables.
                    self.start_seed = n
                    self.seed = n
                    self._message = ""       # L12272
                    return WORLD_GRAINE      # L12273 `MOVEQ #-1,D0`
                if self._message:            # L12278-12279
                    monde = (0 if self._message == WORLD_GENESIS
                             else decode(self._message, self))   # L12281-12295
                    if monde < 0:            # L12297-12312
                        r.draw_text(d, (WORLD_X[0] + 0x10) >> 3,
                                    WORLD_Y[0] + 0x18, WORLD_PAS_DE_MONDE)
                if monde >= 0:
                    break                    # L12313 : valide
            saisi = 1                        # L12314

            index = monde // 25              # L12315-12319 `DIVS #$0019`
            if not self._lire_level_dat(index):     # L12340-12368
                saisi = 0                    # L12370
                # `diskerr_47222` (L12371-12376) : `_do_message(strInsertDisk,
                # 0)` puis `BRA.W LAB_47064`. Sans CANCEL, la boucle ne
                # sort que quand le fichier est la — et `do_message` rend 0
                # si la fenetre est fermee, ce qui n'existe pas sur Amiga.
                if self.do_message(INSERT_DISK) == 0:
                    return WORLD_GRAINE
                continue                     # L12376 -> LAB_47064

            # `abandon` porte le `BRA.W LAB_47064` de L12758 : un retour en
            # tete de la boucle de dehors, **pas** une sortie de la routine.
            abandon = False
            while True:                      # ---- LAB_47236 (L12377) ----
                self.left_button = 2         # L12378
                lignes = resumer(brut, monde)          # `line_1` a `line_7`
                colonnes = valeurs_colonnes(brut)     # `line_9`/`line_0`
                for i in range(1, WORLD_NB):  # L12741-12743 `CMPI.W #$000f`
                    self._trace_show_world(i, lignes, colonnes)
                while self.left_button != 0:  # L12745-12747
                    self._pompe()
                    if not self.running:
                        return WORLD_GRAINE
                rr = self.check_cancel(ok, cancel)    # L12749-12753
                if rr == 2:                  # L12755-12758 : NEW GAME
                    self._message = ""
                    abandon = True           # BRA.W LAB_47064
                    break
                if rr != 1:                  # L12760-12761 : on retrace
                    continue
                break                        # OK
            if abandon:                      # -> LAB_47064, `saisi` = 1
                continue

            # L12762-12771 : la sequence meme du demarrage monojoueur.
            # Les deux fiches sont adressees **en dur** - `LAB_516D8` et
            # `LAB_516AA`, donc stats[1] et stats[0], et non `not_player`.
            st = sim.stats
            sim.player = 0
            sim.not_player = 1
            st[1].can_build = 1              # L12764
            st[0].act = 0                    # L12765
            st[0].queued = 1                 # L12766
            st[1].queued = 0                 # L12767
            sim.serial_off = 1               # L12768
            sim.paint_map = 0                # L12769
            sim.war = 0                      # L12770
            self._monde = monde              # L12771 `_level_number`
            return monde                     # L12772-12773

    def _trace_two_players(self, etat: int) -> None:
        """Un panneau de `_two_players` (L11284-11413)."""
        from populous.two_players import (SERIAL_BOXE, SERIAL_NB, SERIAL_TEXTE,
                                          SERIAL_X, SERIAL_Y)
        r, d = self.ren, self.frame
        self.requester(*SERIAL_BOXE, "", "")
        if 0 <= etat < SERIAL_NB:
            # L11306-11317 : `_text(x + $20, y + $2E, texte)`, `_blank`
            # d'abord (L11298).
            r.draw_text(d, (SERIAL_X[etat] + 0x20) >> 3,
                        SERIAL_Y[etat] + 0x2E, SERIAL_TEXTE[etat])

    def two_players(self) -> int:
        """``_two_players()`` (L11265-11892). Rend 1, comme la machine.

        Une machine a etats, dont le mot `(-40,A5)` est l'etat :

        * **`$3E7 = 999`** au depart (L11267) - « je ne suis pas pret » ;
        * **`2`** : *STARTUP SERIAL*, titre indexe par `(-42) + $0C`
          (L11298-11320) ;
        * **`3`** : *SEND LOGIN*, indexe par `(-44) + $0E` (L11323-11346) ;
        * **`4`** : *SERIAL ERROR!* (L11349-11361) ;
        * **`5`** et **`6`** : les options modem (L11363-11413).

        La boucle tourne tant que `(-40,A5) != 0` (L11285-11286) et sort par
        `_check_cancel` (L11876-11878) : `0` retrace, `2` sort, et `1`
        avec `(8,A5) != 0` - c'est-a-dire **depuis le code 8**, puisque
        l'argument est nul quand on vient du dialogue (L11884-11885).

        **Transcrit** : la machine a etats, les seize panneaux, le titre
        indexe par le joueur, et l'effet sur `_player` (L11744-11752).

        **Non transcrit** : `_clear_serial` (L11277), `_write_serial`
        (L11643, L11658), `_set_baud_rate` (L11703) et `_try_serial`
        (L11763). Ces quatre routines commandent le **port serie de l'Amiga** ;
        il n'y a pas de second Amiga a relier, donc elles leve
        `NotImplementedError` en nommant la routine. La boite s'ouvre et
        affiche ses panneaux, mais tenter de se connecter leve : mieux vaut
        une erreur nommee qu'un ecart muet.
        """
        from populous.two_players import SERIAL_BOXE, SERIAL_ETAT_INITIAL
        sim = self.sim
        etat = SERIAL_ETAT_INITIAL                 # L11267
        ok, cancel = self._cadres_boutons(*SERIAL_BOXE)

        while etat != 0:                           # L11285-11286
            self._trace_two_players(etat)
            self.left_button = 2
            while self.left_button != 0:
                self._pompe()
                if not self.running:
                    return 0
            r = self.check_cancel(ok, cancel)      # L11876-11878
            if r == 0:                              # L11888 : on retrace
                continue
            if r == 1:
                raise NotImplementedError(         # L11884-11885
                    "`_two_players` : la connexion passe par `_try_serial` "
                    "(L11903), `_write_serial` (L20141) et `_set_baud_rate` "
                    "(L16841) - le port serie de l'Amiga, dont il n'y a pas "
                    "d'equivalent sur un poste seul")
            break                                   # CANCEL : L11886-11892
        self.left_button = 2                       # `_return_to_game`
        self.compose()
        return 1                                   # L11891 puis LAB_46BDC

    def do_message(self, texte: str, annuler: int = 0) -> int:
        """``_do_message(texte, annuler)`` (L11098-11139).

        Une boite de dialogue sur ``_d_screen``, un texte, et la main
        rendue au clic. **Ce n'est pas une erreur : c'est le dialogue
        « montrez-moi le disque »** que le listing ouvre quand il ne
        trouve pas un fichier. Voir :mod:`populous.message`.

        La sequence, relevee telle quelle :

        * ``annuler != 0`` pose ``_end_cancel`` dans la structure locale,
          sinon elle la met a **zero** (L11100-11106) ;
        * `_requester(_d_screen, $28, $3C, $100, $30, _end_ok, (-4))`
          (L11108-11116) ;
        * `_text(_d_screen, $38, $48, texte)` (L11117-11122) — en pixels,
          `_text` divise par 8 ;
        * ``_left_button = 2``, puis spin jusqu'a ce que le VBI le mette a
          0 (L11123-11128) ;
        * `_check_cancel(_end_ok, (-4))` (L11129-11135) : **0 reboucle sur
          la boite**, 1 rend la main.
          Le ``BEQ`` de L11135 teste ``Z`` pose par ``MOVE.W D0,(-6,A5)``
          — ``MOVE`` modifie le CCR et ``ADDQ`` vers ``A7`` non -, donc
          bien le retour de ``_check_cancel`` ;
        * ``_left_button = 2`` une derniere fois (L11136), puis rend D0.

        Renvoie donc 1 sur OK, 2 sur CANCEL, et 0 si la fenetre a ete
        fermee : c'est le seul ecart, et il n'existe pas sur Amiga.

        ``annuler = 0`` ne laisse que le bouton OK : la boucle est
        **infinie** tant que la fenetre reste ouverte. C'est voulue — le
        listing boucle jusqu'a ce que le disque soit insere — mais le port
        n'a pas de disque a insérer, d'ou le recours 0.
        """
        from populous.message import (MESSAGE_BOXE, MESSAGE_CANCEL,
                                      MESSAGE_OK, MESSAGE_X, MESSAGE_Y)
        while True:                                    # LAB_462E6, L11123
            self.requester(*MESSAGE_BOXE, "", "")      # L11108-11116
            self.ren.draw_text(self.frame, MESSAGE_X >> 3, MESSAGE_Y,
                               texte)                  # L11117-11122
            self.left_button = 2                       # L11124
            while self.left_button != 0:               # L11126-11128
                self._pompe()
                if not self.running:
                    return 0
            ok, cancel = self._cadres_boutons(*MESSAGE_BOXE,
                                              MESSAGE_OK, MESSAGE_CANCEL)
            r = self.check_cancel(ok, cancel if annuler else None)  # L11129
            if r == 0:                                 # L11135 : on retrace
                continue
            self.left_button = 2                       # L11136
            return r

    def check_cancel(self, ok, cancel) -> int:
        """``_check_cancel(end_ok, end_cancel)`` (L12106-12159).

        Les deux arguments sont des **structures de trois mots** :
        ``(x0, y0, x1)``. Rien n'est compare a `x1` autrement que comme
        borne droite, et la borne basse est `y0`, la haute `y0 + $10` :
        une bande de 16 px (L12124-12129 / L12149-12154).

        Retour :

        * `0` si ``_left_button != 0`` - pas de clic (L12108-12109) -
          ou si aucun cadre n'est touche ;
        * `1` si la souris est dans le cadre OK ;
        * `2` si elle est dans le cadre CANCEL.

        L'ordre des **deux** tests est celui du listing : OK d'abord
        (L12110), CANCEL ensuite (L12135), et un cadre nul est saute.
        """
        if self.left_button != 0:                 # L12108-12109
            return 0
        mx, my = self.mouse
        for code, box in ((1, ok), (2, cancel)):  # L12110 / L12135
            if box is None:                       # TST.L / BEQ
                continue
            x0, y0, x1 = box
            if mx < x0 or mx > x1:                # L12113-12119
                continue
            if my < y0 or my > y0 + 0x10:         # L12120-12129
                continue
            return code                           # L12130 / L12155
        return 0                                  # L12157-12158

    def _palette_magnet(self, up: int, vp: int, d0: int) -> None:
        """``LAB_3F924`` (L2134-2226) - colonne 7, ligne 0.

        Suivre l'aimant. L'icone est inversee des qu'on la clique ; le
        recentrage n'a lieu que sur l'image du clic gauche (`TST.W
        (8,A5)` = le mot pousse par l'appelant, L988). Ensuite :

        * ``_magnet[player] != 0`` -> centre sur la **case** du peep
          aimante (``LAB_5301C`` = ``_peeps + 8``) et
          ``_set_temp_view(magnet)`` ;
        * ``_magnet[player] == 0`` -> centre sur la case visee par
          l'aimant (``LAB_52DE6`` = ``_magnet_to``), sans
          ``_set_temp_view``.

        Les deux branches font ``- 3`` : la fenetre de 8 cases garde
        3 cases de marge avant le centre.
        """
        self.toggle_icon(up, vp, 0x12C0)             # L2137-2142
        if not d0:                                 # L2143
            return                                 # LAB_3F98E
        sim = self.sim
        pl = sim.players[sim.player]
        if pl.magnet:                              # L2149
            idx = pl.magnet - 1
            if not (0 <= idx < len(sim.peeps)):    # ECART : l'asm indexe
                return                             # les 208 fiches sans
            b = sim.peeps[idx].block                # LAB_5301C + i*22
        else:                                      # LAB_3FA0A
            b = pl.magnet_to                       # LAB_52DE6
        self.xoff = (b & 0x3F) - 3                  # L2214-2223
        self.yoff = (b >> 6) - 3
        if pl.magnet:                              # L2205
            self.set_temp_view(pl.magnet)

    def _palette_fight(self, up: int, vp: int) -> None:
        """``LAB_3FA40`` (L2227-2296) - colonne 7, ligne 1.

        Prochaine bataille. Balayage circulaire a partir de
        ``_view_fight + 1``, borne par un tour complet (l'octet
        `(-8,A5)` du L2260) : on s'arrete des qu'on retombe sur la case
        de depart. Le peep retenu a le **bit 3 de `state`** pose
        (``ST_BATTLE``) et une vie non nulle.
        """
        self.toggle_icon(up, vp, 0x12C0)             # L2230-2235
        sim = self.sim
        n = sim.no_peeps
        if n == 0:                                 # L2236
            return
        if sim.view_fight >= n:                     # L2238-2241
            sim.view_fight = 0
        i = sim.view_fight + 1                      # L2243-2245
        tour = 0                                    # (-8,A5) L2246
        while True:                                 # LAB_3FA86
            if i >= n:                              # L2248-2251
                i = 0
            if sim.view_fight + 1 == i and tour:    # L2253-2258
                return
            tour = 1                                # L2260
            p = sim.peeps[i]
            if not (p.state & ST_BATTLE) or p.life == 0:
                i += 1                              # LAB_3FB1A
                continue
            self.xoff = (p.block & 0x3F) - 3         # L2274-2284
            self.yoff = (p.block >> 6) - 3
            sim.view_fight = i                      # L2285
            self.set_temp_view(i + 1)                # L2286-2290
            return

    def _palette_people(self, up: int, vp: int, d0: int) -> None:
        """``LAB_3FB26`` (L2297-2405) - colonne 8, ligne 0.

        Prochain habitant. Meme balayage circulaire que `(7,1)` mais
        sur ``_view_people``, et le filtre depend du **bouton** :

        * clic **gauche** (`d0 != 0`) -> "le long" de ``LAB_53022``
          (``_peeps + 14``) est non nul, c'est-a-dire que le peep a
          une **cible** ;
        * clic **droit** (`d0 == 0`) -> `state == $01` (villageois).

        Il faut de plus que le peep soit de la tribu du joueur
        (``LAB_53015`` = ``_peeps + 1``) et vivant. Le ``TST.W
        (8,A5)`` du L2306 ne branche pas : c'est un residu, il ne
        teste rien ici - les deux boutons declenchent la recherche, ils
        ne changent que le filtre.
        """
        self.toggle_icon(up, vp, 0x12C0)             # L2300-2305
        sim = self.sim
        n = sim.no_peeps
        if n == 0:                                 # L2307
            return
        if sim.view_people >= n:                     # L2309-2312
            sim.view_people = 0
        i = sim.view_people + 1                      # L2314-2316
        tour = 0                                    # L2317
        while True:                                 # LAB_3FB6E
            if sim.view_people + 1 == i:             # L2319-2321
                if tour:                             # L2323-2324
                    return
            if i == n:                              # L2326-2329
                i = 0
            tour = 1                                # L2331
            p = sim.peeps[i]
            if p.tribe != sim.player:               # L2334-2338
                i += 1
                continue
            if p.life <= 0:                         # L2341-2343
                i += 1
                continue
            if d0:                                  # L2345 -> LAB_3FC26
                if p.target == -1:                  # L2378-2379 `TST.L`
                    i += 1                          # LAB_3FC86
                    continue
            elif p.state != ST_VILLAGER:            # L2348-2350
                i += 1
                continue
            self.xoff = (p.block & 0x3F) - 3         # L2383-2393
            self.yoff = (p.block >> 6) - 3
            sim.view_people = i                      # L2365 / L2394
            self.set_temp_view(i + 1)                # L2366-2370 / L2395
            return

    def set_temp_view(self, who: int) -> None:
        """``_set_temp_view(who)`` (L404ac).

        Trois instructions : si ``_view_timer`` est nul, reculer
        ``_view_who`` dans ``_old_view_who`` ; remettre le compteur a
        10 images ; ecrire ``_view_who = who``.  C'est la "vue
        temporaire" : au bout des 10 images on revient a l'ancien
        suivi.
        """
        sim = self.sim
        if sim._temp_timer == 0:                   # L404ac-404ba
            sim.old_view_who = sim.view_who
        sim._temp_timer = 10                       # L404bc
        sim.view_who = who                         # L404c2
        sim._temp_view = who          # redite du port (lecteur
                                    # historique de `_temp_view`)

    def _may_paint(self) -> bool:
        """Garde du bouton ``(2, 2)`` de la palette - L2018-2032.

        ``D1`` est le mot long ``LAB_52DF0[_player]``, c'est-a-dire la
        **reserve de mana** du joueur (`Player.mana`, stride 16, L2021) ;
        il faut ``D1 > LAB_51884`` (``$1388`` = 5000, L24296) **et** le bit
        4 pose sur ``_stats[_player] + 0x0F``, c'est-a-dire le bit ``0x0010``
        du masque de pouvoirs (``BTST #4`` L2028). Sinon, et dans tous les
        cas, ``_paint_map`` suffit (L2030-2032).
        """
        sim = self.sim
        st = sim.stats[sim.player]
        if sim.players[sim.player].mana > 0x1388 and (st.power_mask & 0x0010):
            return True
        return bool(sim.paint_map)

    def set_mode_icons(self, x: int, y: int) -> None:
        """``_set_mode_icons(x, y)`` (L2526-2567).

        Trois inversions mutuellement exclusives sur l'octet bas de
        ``_mode``, puis **toujours** l'icone ``(x, y)`` demandee si
        ``x >= 0`` (L2557-2564) - c'est par la que le selecteur ``(6, vp)``
        retourne la case qu'on vient de cliquer.

        ================  ==================  =====================
        test              icone               ligne
        ================  ==================  =====================
        ``mode & 04``     ``(6, 2)``          L2528-2534
        ``mode & 08``     ``(2, 2)``          L2538-2544
        sinon             ``(6, _mode - 1)``  L2547-2554
        ================  ==================  =====================

        ``bitfield_51645`` n'est pas un champ a part : c'est l'octet
        **bas** du mot ``_mode`` (0x51644 = ``_mode``, 0x51645 =
        ``bitfield_51645`` ; ``MOVE.W #$0002,(_mode,A4)`` au L1148
        redonne exactement les deux octets initiaux ``DS.B 1`` = 0 puis
        ``DC.B $02``).  D'ou ``BTST #2`` = ``mode & 04``, et ``BSET #3``
        (L2040) = ``mode = (mode & 3) | 8`` - deja fait par ``(2,2)``.
        """
        mode = self.sim.mode
        if mode & 0x04:
            self.toggle_icon(6, 2, 0x12C0)
        elif mode & 0x08:
            self.toggle_icon(2, 2, 0x12C0)
        else:
            self.toggle_icon(6, mode - 1, 0x12C0)
        if x >= 0:                                # L2557
            self.toggle_icon(x, y, 0x12C0)        # L2559-2563

    def set_tend_icons(self, x: int, y: int) -> None:
        """``_set_tend_icons(x, y)`` (asm L2455).

        Inverse l'icone de la **croix de selection** du pouvoir, en plus de
        celle demandee par l'appelant. La croix est a 4 positions
        correspondant aux 4 outils de relief (cf. les entrees (3,3), (4,3),
        (5,3) et (4,4) de la palette) :

        * ``LAB_52DE8[player] == 0`` -> (3, 3)
        * ``== 1``                    -> (4, 3)
        * ``== 2``                    -> (5, 3)
        * ``== 3``                    -> (4, 4)

        ou 0 signifie « aucune » : seule l'icone demandee est alors inversee.
        Les positions sont en coordonnees de la grille isometrique
        (``col * 322 + row * 318 + masque``), comme dans ``_toggle_icon``.
        """
        # L2457-2461 : la croix vient de `LAB_52DE8[_player]`, qui est
        # `players[player].command` (ecrit par `do_action` code 1, L18402,
        # et initialise a 1 au L1065). `sim._tend` n'existe pas dans le
        # listing.
        tend = self.sim.players[self.sim.player].command
        croix = {0: (3, 3), 1: (4, 3), 2: (5, 3), 3: (4, 4)}.get(tend)
        if croix is not None:
            self.toggle_icon(croix[0], croix[1], 0x12C0)
        self.toggle_icon(x, y, 0x12C0)

    def _peep_block(self, who: int) -> int | None:
        if 0 < who <= len(self.sim.peeps):
            return self.sim.peeps[who - 1].block
        return None

    def toggle_icon(self, col: int, row: int, mask: int) -> None:
        """``_toggle_icon(ecran, col, row, masque)`` (asm L19493).

        L'asm ecrit le losange inverse **en place** dans ``_back_scr``, qui
        n'est jamais efface : l'icone reste donc inversee d'une image a l'autre.
        Nous reproduisons cet etat persistant avec un ensemble : le losange est
        re-applique a chaque composition, et un second appel sur la meme icone
        l'annule (c'est exactement ce que fait le double XOR de l'original).
        """
        key = (col, row, mask)
        if key in self.icon_toggles:
            self.icon_toggles.discard(key)
        else:
            self.icon_toggles.add(key)

    def _apply_icon_toggles(self) -> None:
        """Re-applique les inversions d'icones (voir ``toggle_icon``)."""
        for col, row, mask in sorted(self.icon_toggles):
            self.ren.toggle_icon(self.frame, col, row, mask)

    # ------------------------------------------------------------------ reperes
    def on_minimap(self, mx: int, my: int) -> bool:
        """Le point vise-t-il la mini-carte ? (meme test que ``zoom_map``)"""
        u, v = self._uv(mx, my)
        return 0 <= u < 0x40 and 0 <= v < 0x40

    def recentre(self, cx: int, cy: int) -> None:
        """Recentrage de la mini-carte : ``clamp(v-3, 0, 0x38)`` (asm L1679)."""
        self.xoff = clamp_off(cx - 3)
        self.yoff = clamp_off(cy - 3)

    def zoom_to_cell(self, cx: int, cy: int) -> None:
        """Comme ``recentre`` mais en mettant la case au centre de la fenetre
        (la fenetre fait 8 cases de large, donc centre = -4)."""
        self.xoff = clamp_off(cx - 4)
        self.yoff = clamp_off(cy - 4)

    # ------------------------------------------------------------------ boucle
    def handle(self, ev: pygame.event.Event) -> None:
        if ev.type == pygame.QUIT:
            self.running = False
        elif ev.type == pygame.KEYDOWN:
            # L'ecran de fin attend un clic pour enchainer (asm L14392 :
            # `LAB_48B24` boucle sur `_left_button` jusqu'au front, et la
            # boucle du discours le teste en tete, L148DC6). Le clavier ne
            # fait pas partie de l'original : on s'en sert de raccourci, mais
            # on ne fait que **poser le clic**, pour que le chemin de sortie
            # (restauration des deux bascules, `_kill_effect`, L148F4A-148F94)
            # reste celui du listing.
            if self.game_ended:
                if ev.key in (pygame.K_RETURN, pygame.K_SPACE,
                              pygame.K_ESCAPE):
                    self.left_button = 0
                return
            # Un `_get_name` en cours prend le clavier tout entier : c'est
            # `_keyboard` (L10388) qui le lit dans sa boucle, et `_key`
            # n'existe pas a cet endroit du listing.
            if self._saisie:
                touche = _touche_nom(ev)
                if touche:
                    self._touches.append(touche)
                return
            # La boite « TRY NUMBER » capte tout le clavier tant qu'elle est
            # ouverte (LAB_46D3C boucle jusqu'a validation ou annulation).
            if self.conquest_dialog is not None:
                if self.conquest_key(ev.key, ev.unicode):
                    return
            self._key(ev.key)
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            self.mouse = self._mouse(*ev.pos)
            if ev.button == 1:
                self._raw_left = True
            elif ev.button == 3:
                self._raw_right = True
        elif ev.type == pygame.MOUSEBUTTONUP:
            if ev.button == 1:
                self._raw_left = False
            elif ev.button == 3:
                self._raw_right = False
        elif ev.type == pygame.MOUSEMOTION:
            self.mouse = self._mouse(*ev.pos)
        elif ev.type == pygame.MOUSEWHEEL:
            self.set_zoom(self.zoom - ev.y)

    # ------------------------------- une image de la boucle (asm L963-1010)
    def poll_mouse(self) -> None:
        """La partie Â« souris » de la boucle d'image, dans l'ordre exact.

        ``LAB_3EC20``  mode de sculpture ou survol d'un habitant ;
        ``LAB_3EC40``  ``_zoom_map`` sauf si les deux boutons sont enfonces ;
        ``LAB_3EC60``  passage des boutons a l'etat stable (1), sauf 2 qui
                       reste bloque jusqu'au relachement ;
        ``LAB_3EC88``  ``_get_message``.
        """
        sim = self.sim
        self._read_buttons()
        if sim.mode & 0x0E:
            self.sculpt()
        elif self.left_button == 0 or self.right_button == 0:
            self.interogate()
        if not (self.left_button and self.right_button):
            self.zoom_map(1 if self.left_button == 0 else 0)
        self.left_button = 2 if self.left_button == 2 else 1
        self.right_button = 2 if self.right_button == 2 else 1
        self._do_actions()

    def _do_actions(self) -> None:
        """``_get_message`` (L17707, appelee chaque image au L1010).

        La boucle de messages relit ``act``/``p1``/``p2`` dans la fiche
        (L17953-17971) et appelle ``_do_action(tribe, p1, p2)`` : la case
        visee n'est pas un argument a part, c'est ``p1``/``p2``.  Le lien
        est fait ici meme image pour garder la reactivite du port.

        Deux ecarts assumes :

        1. le declenchement reste subordonne a ``tgt_dirty`` (un clic a
           rempli la fiche) ; l'asm declenche a **chaque** image et la
           palette attend donc la fin du tour, executee par ``do_queued``.
        2. ``sim.tgt`` n'est plus qu'une redite de ``p1``/``p2`` (meme
           octets, ``LAB_516A5/6``) : il reste la pour le debogage.
        """
        sim = self.sim
        st = sim.stats[sim.player]
        if sim.tgt_dirty and st.act:
            self._safe_dispatch(sim.player)

    def _safe_dispatch(self, tribe: int) -> None:
        """Execute la fiche ``stats[tribe]`` en survivant a un code non transcrit.

        ``_get_message`` (L17707, appele **a chaque image** au L1011)
        dispatche la fiche sans filet. Dans l'original, les entrees
        ``(0,0)``, ``(1,1)`` et ``(2,2)`` de la barre d'icones ouvrent donc
        leur boite de dialogue sur l'image du clic (Phase 63) ; le port n'a
        pas les ~1300 lignes de ``_options`` (L13617) et ``_game_options``
        (L12801), et un clic sur ces icones arme un code qui leve.

        Deux consequences corrigees ici :

        1. ``_do_actions`` ne declenche que sur ``tgt_dirty`` - une
           commande de palette reste donc en fiche jusqu'au tour suivant ;
        2. ``_run_commands`` la dispatchait a ce moment-la, au milieu de
           ``tick``, et le ``NotImplementedError`` tuait la partie.

        On signale l'erreur sur la sortie d'erreur et on vide la fiche
        comme ``_clear_send`` (L18234-18254) : le jeu reste jouable et le
        code manquant reste **visible**. Ce n'est pas un no-op.
        """
        st = self.sim.stats[tribe]
        try:
            self.powers.do_queued(tribe)
        except NotImplementedError as exc:
            print("[non transcrit] %s" % exc, file=sys.stderr)
            st.act = ACT_NOP
            st.p1 = 0
            st.p2 = 0

    # ------------------------------------------------- _interogate (asm L2719)
    def interogate(self) -> None:
        """Survol d'un habitant (asm L2719).

        La routine parcourt la file ``_sprite[]`` deja produite par
        ``_move_sprite`` et teste une boite de **12 x 8** autour de chaque
        sprite. Au premier succes :

        * ``_right_button == 0`` -> selection : ``_view_who = who`` ;
        * sinon                    -> ``_set_temp_view(who)``, c'est-a-dire un
          affichage temporaire de 10 images (``_view_timer``).
        """
        sim = self.sim
        mx, my = self.mouse
        for x, y, _sprite, who in self.ren.last_queue:
            if x <= mx <= x + 12 and y <= my <= y + 8:
                if sim.mode != 1:          # L2743 : rien hors du mode 1
                    return
                if self.right_button != 0:         # bouton droit relache
                    sim.view_who = who             # selection
                    sim._temp_timer = 0            # _view_timer = 0
                else:                             # bouton droit enfonce
                    self.set_temp_view(who)       # `_set_temp_view`
                return

    def _key(self, key: int) -> None:
        if key in (pygame.K_ESCAPE, pygame.K_q):
            self.running = False
        elif key in (pygame.K_LEFT, pygame.K_a):
            self.xoff = clamp_off(self.xoff - KEY_STEP)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.xoff = clamp_off(self.xoff + KEY_STEP)
        elif key in (pygame.K_UP, pygame.K_w):
            self.yoff = clamp_off(self.yoff - KEY_STEP)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.yoff = clamp_off(self.yoff + KEY_STEP)
        elif key == pygame.K_PAGEUP or key in (pygame.K_EQUALS,
                                               pygame.K_KP_PLUS):
            self.set_zoom(self.zoom + 1)
        elif key in (pygame.K_PAGEDOWN, pygame.K_MINUS, pygame.K_KP_MINUS):
            self.set_zoom(self.zoom - 1)
        elif key == pygame.K_TAB:
            self.set_ground((self.ground + 1) % 5)
        elif key == pygame.K_n:
            self.set_seed(self.seed + 1)
        elif key == pygame.K_p:
            self.ren.step_toggle()
        elif key in (pygame.K_l, pygame.K_RIGHTBRACKET):
            self.open_conquest_dialog()
        elif key == pygame.K_LEFTBRACKET:
            self.conquest_no = (getattr(self, "conquest_no", 1) - 2) % 99 + 1
            if self.load_conquest(self.conquest_no):
                self.frames = 0
        elif key == pygame.K_F1:
            self._fullscreen()

    def set_zoom(self, z: int) -> None:
        z = max(1, min(6, z))
        if z == self.zoom:
            return
        self.zoom = z
        self.screen = pygame.display.set_mode((SCREEN_W * z, SCREEN_H * z))

    def _fullscreen(self) -> None:
        self.screen = pygame.display.set_mode((SCREEN_W * self.zoom,
                                               SCREEN_H * self.zoom),
                                              pygame.FULLSCREEN)

    # ---------------------------------------------------- _load_ground (L16468)
    def load_ground(self, n: int, msg: int = 0) -> bool:
        """``_load_ground(n, msg)`` (L16468-4A444) — le code 13 de ``_do_action``.

        Ce n'est **pas** la creation du relief : la routine ne touche ni
        ``_alt`` ni ``_map_blk``. Elle recharge l'habillage d'un terrain :

        1. ``_Open("LANDn")`` + 9 x ``_Read`` + ``_Close`` (L4A25A-4A32E) :
           ``walk_death``, ``population_add``, ``mana_add``, ``weapons_add``,
           ``battle_add1``, ``battle_add2``, ``map_colour`` (16 octets),
           ``sprites_no`` (2 octets) et ``_blk_data`` (0x8340 = 70 tuiles).
           ``land.load_land`` et ``assets.load_land`` lisent les memes octets
           aux memes offsets (tableau dans :mod:`populous.land`).
        2. ``if sprites_no != _sprites_in: _read_sprites(sprites_no)``
           (L4A330-4A342) : le jeu 0 ou 4 n'est recharge que s'il change.
        3. ``_map_colour[i+16] = _map_colour[i]`` (L4A348-4A36C), exprime ici
           par la reconstruction de ``self.colours`` via :func:`map_colours`.
        4. ``_weapons_order[0..10] = _weapons_add[0..10]`` puis tri croissant
           (L4A372-4A41E).

        Renvoie 1, comme le ``MOVEQ #1,D0`` du listing.

        **Le chemin d'erreur** (``LAB_4A426``, L16611-16622) est transcrit
        depuis la Phase 82. Quand ``Open("LANDn")`` rend nul :


            r = _do_message(strInsertDisk, msg)
            if r == 2:                 # CANCEL
                return 0               # LAB_4A442
            goto LAB_4A25A             # on retente l'Open

        ``(-4,A5)`` vaut 0 dans ce chemin, donc ``TST.L (-4,A5) ; BEQ
        LAB_4A25A`` (L16618-16619) retente **toujours**. `msg` est le
        second argument du listing (`($A,A5)`) : 0 chez les trois appels a
        0 de la boucle de jeu (L400, L17586), 1 chez celui de L18985. Seul
        ``msg = 1`` donne un CANCEL ; avec ``msg = 0`` la boucle est
        infinie tant que la fenetre reste ouverte — c'est voulu, le
        disque doit arriver.
        """
        from populous.message import INSERT_DISK
        while True:                                   # LAB_4A25A, L4A25A
            try:
                tables = load_land(n)                 # LandTables : l'en-tete
                header, tiles = load_tiles(n)         # + les 0x8340 de tuiles
            except (FileNotFoundError, ValueError):
                r = self.do_message(INSERT_DISK, msg)  # L16612-16615
                if r == 2:                             # L16616-16617
                    return False                       # LAB_4A442
                if r == 0:                             # ECART : fenetre fermee
                    return False
                continue                               # L16618-16619
            break

        ren = self.ren
        sprites_in = ren.header["sprites_no"]     # _sprites_in (L4A334)
        ren.header, ren.tiles = header, tiles
        if header["sprites_no"] != sprites_in:    # BEQ LAB_4A344
            ren.sprites = load_sprites("sprites%d.dat" % header["sprites_no"])
        ren.ground = n

        self.ground = n                           # _ground_in (L4C12A)
        self.sim.land = tables
        self.sim.weapons_order = (
            sorted(tables.weapons_add[0:11]) + [0xFFFF])
        self.colours = map_colours(ren.header)
        return True

    def _init_tutorial_mode(self) -> None:
        """Initialise le mode tutoriel/demo (`_start_of_game == 3`).

        `_start_game` (L4860A-48660) :
        - Copie `_tutorial` (46 octets = 2 x 23 = deux fiches `_stats`) sur `_stats`
        - Copie `LAB_5172E` (46 octets) sur `strABC` (zone texte)
        - `_pause = 1` (L48636)
        - `_seed = _start_seed = 0x69bc` (L48654, L4865A)
        - `_game_mode = _tutorial_game_mode = 1` (L48660)
        - Bascule icone (1,3) masque 0x17e4 (L4863C-4864C)

        Le port recree les fiches `Tribe` avec les valeurs du tutoriel.
        """
        sim = self.sim
        # _tutorial (L24233-24248) -> deux fiches Tribe (23 octets chacune)
        # Valeurs decodees depuis le listing :
        # Tribu 0 : act=0x61, p1=0x62, p2=0x63, can_build=0, queued=1,
        #           threshold=1, period=10, power_mask=0x003F, tend=0,
        #           castles=0, towns=0, colour=5, ...
        # Tribu 1 : act=0x61, p1=0x62, p2=0x63, can_build=0, queued=1,
        #           threshold=5, period=10, power_mask=0x000A, tend=0,
        #           castles=0, towns=0, colour=1, ...
        t0, t1 = sim.stats[0], sim.stats[1]
        # Champs communs initiaux (act/p1/p2 = 'abc')
        for t in (t0, t1):
            t.act = 0x61
            t.p1 = 0x62
            t.p2 = 0x63
            t.can_build = 0
            t.queued = 1
            t.tend = 0
            t.castles = 0
            t.towns = 0
            t.t12 = t.t1a = t.t18 = t.t1c = t.t1e = 0
            t.strongest = -1
            t.p26 = -1
            t.p2a = -1
        # Tribu 0 (humaine dans le tutoriel)
        t0.threshold = 1
        t0.period = 10
        t0.power_mask = 0x003F
        t0.colour = 5
        # Tribu 1 (Amiga dans le tutoriel)
        t1.threshold = 5
        t1.period = 10
        t1.power_mask = 0x000A
        t1.colour = 1

        # `_start_game`, L13998-13999 (`$48654`, `$4865a`) :
        # `_seed = _start_seed = $69bc`. La routine **retourne** ensuite
        # (L14001-14011) sans rien generer : la carte n'est batie que plus
        # tard, par `_setup_display`, qui passe par L433.
        #
        # **ECART supprime** : le port avancait ici le RNG de `+ 1` (un
        # increment entier) puis battait la carte depuis `self.seed` brut.
        # Il manquait donc le tirage reel de L433 - meme ecart que celui
        # corrige dans `__init__` - et il remettait le RNG sur une valeur
        # que `_seed` n'a jamais eue.
        self.seed = 0x69BC
        self.start_seed = 0x69BC
        sim.rng.seed = self.seed               # L13998 `_seed = $69bc`
        if self.seed != 0:                     # L431-432 `TST.W / BEQ`
            sim.rng.raw()                      # L433 `JSR ___newrand`

        # _game_mode = 1 (L14000, `$48660` : `_tutorial_game_mode`)
        sim.game_mode = 1

        # _pause = 1 (L48636)
        sim.pause = 1

        # Re-regenerer la carte depuis l'etat vivant du RNG, puis rendre
        # `_seed += 1` (L496) : increment entier sur l'etat que laisse
        # `_make_woods_rocks` (L469). `_place_first_people` (L495) n'a
        # consomme aucun tirage.
        self.terrain, _rng_tut = build_map(sim.rng.seed, self.ground)
        sim.rng.seed = (_rng_tut.seed + 1) & 0xFFFF   # L496 `_seed += 1`
        self.ren = Renderer(self.ground)
        self.colours = map_colours(self.ren.header)
        sim.terrain = self.terrain
        sim.land = load_land(self.ground)
        sim.map = self.terrain.game_map()
        self._sync_level_stats()

    def _sync_level_stats(self) -> None:
        """``_clear_map`` L1088-1121 : `t1a` / `t18` recopies dans `_stats`.

        `Terrain.clear` **consomme** les deux tirages par joueur - il faut
        le faire pour que la suite de la sequence du RNG reste identique -
        mais `Terrain` ne porte pas `_stats`. Les voici donc dans la fiche,
        ou `_devil_effect` les lit (L9431-9441 : la porte du bloc
        `act = 4` est `t1a <= t12 <= t18`).
        """
        for k in (0, 1):
            self.sim.stats[k].t1a = self.terrain.t1a[k]
            self.sim.stats[k].t18 = self.terrain.t18[k]

    def set_ground(self, g: int, conserver_etat: bool = False) -> None:
        """Regenere le relief ``g`` - et, dans le port, re-instantie ``Sim``.

        **ECART de port** : l'Amiga n'a pas besoin de recréer quoi que ce
        soit - `_load_ground` (L16468) re-chargera les tables de sol,
        `_clear_map` (L1088) effacera les cases, `_make_alt` / `_make_map`
        / `_make_woods_rocks` (L462-469) regenereront le relief. Le port,
        lui, doit construire `Terrain` + `Renderer` + `Sim` ensemble, car
        `Sim` porte `land` (les tables du sol) et `map` (les cases). Il
        jette donc la fiche de simulation **entiere** a chaque changement
        de carte.

        `conserver_etat=True` remet a plat, sur la fiche neuve, tout ce que
        `_setup_display` (L380-498) n'a **jamais** touche : le listing ne
        regenere que la carte, il laisse `_in_conquest`, `_player`,
        `_serial_off`, `_stats`, `_game_mode`, `_new_map`, `_bring_up_two`,
        `_mana` et les coches de *GAME SETUP* intacts. Sans cette reprise,
        la ligne 9 de *GAME SETUP* perdrait L12762-12771 ecrits une
        seconde plus tot, et chaque nouvelle carte remettrait la partie
        a zero.

        Les champs reconstruits (:data:`_RECONSTRUIT`) sont ceux que la
        routine d'origine ecrit elle-meme ou qui dependent du sol.
        """
        ancien = self.sim
        self.ground = g
        # Le relief est battu depuis l'**etat vivant** de `_seed`
        # (`self.sim.rng.seed`), pas depuis `self.seed` : en partie libre,
        # `_setup_display` a deja passe le tirage de L433 quand il appelle
        # ici, et `self.seed` reste la graine de depart. Construire depuis
        # `self.seed` sautait ce tirage - meme ecart que celui corrige dans
        # `__init__`, et il faisait au passage deriver toute la suite de
        # tirages de la simulation.
        self.terrain, rng = build_map(self.sim.rng.seed, g)
        self.ren = Renderer(g)
        self.colours = map_colours(self.ren.header)
        # `_seed += 1` (L496) : increment entier applique a l'etat que laisse
        # `_make_woods_rocks`. `_place_first_people` (L495) n'a consomme
        # aucun tirage (`_place_people` L6982-7651 n'en a pas), d'ou le `+ 1`.
        self.sim = Sim((rng.seed + 1) & 0xFFFF, load_land(g),
                       map=self.terrain.game_map())
        self.sim.terrain = self.terrain
        if conserver_etat:
            for nom, valeur in vars(ancien).items():
                if nom not in self._RECONSTRUIT:
                    setattr(self.sim, nom, valeur)
        self._sync_level_stats()
        self._settle_peoples()

    def set_seed(self, s: int) -> None:
        self.seed = s
        self.start_seed = s
        self.set_ground(self.ground)

    def maj_musique(self) -> None:
        """La piste de fond suit ``music_on`` -- ECART Phase 86.

        N'agit que si ``run()`` a arme la session : sinon un outil en ligne
        de commande qui construit un ``Game`` declencherait le chargement de
        ``BGM.mp3``. Fichier manquant ou carte son absente : ``demarrer``
        renvoie ``False``, ``musique.actif()`` reste faux, et les mesures
        synthétisees de ``populous.sound`` reprennent la main -- le port
        degrade donc sans jamais casser.
        """
        if not self._piste_armee:
            return
        if self.music_on:
            musique.demarrer(musique.MUSIQUE_JEU)
        else:
            musique.arreter()

    def run(self) -> None:
        """La boucle d'image.

        .. note::
           Le rythme vient de :data:`populous.config.TURNS_PER_SECOND` et
           :data:`populous.config.TURNS_PER_FRAME`. La boucle d'origine
           reboucle sur `LAB_3E7E8` sans attendre, mais son basculement
           d'ecran finit sur ``_show_screen`` (L19782-19790), qui tourne en
           boucle sur ``INTREQR & $0020`` - le vblank. Un tour par image,
           donc un plafond de 50 tours/s en PAL. Ici ``clock.tick`` prend
           en charge ce plafond : ``0.0`` veut dire sans plafond.

           Le diviseur s'accumule en virgule flottante plutot qu'avec un
           compteur entier, afin que `TURNS_PER_FRAME` accepte n'importe
           quelle valeur (1.0, 3.0, 7.5...) sans derivation cumulative.
        """
        # Phase 84 : l'intro d'attirance (populous.intro), voir
        # config.SHOW_INTRO. L'original demarre dessus et sort par SUB_16E ;
        # ici ``demarrer`` renvoie le choix de l'ecran titre, 0 quand le
        # demo a ete quitte, et -1 si la fenetre a ete fermee.
        if config.SHOW_INTRO:
            from . import intro
            if intro.demarrer(self.frame, self.clock,
                              fenetre=self.screen,
                              im_par_seconde=50.0) < 0:
                self.running = False

        # Phase 86 : ``intro.demarrer`` a monte puis remonte ``Main Theme`` ;
        # on arme ici la piste de la partie. Cet armement est aussi la porte
        # des outils en ligne de commande : voir ``maj_musique``.
        self._piste_armee = True
        self.maj_musique()

        # _start_of_game == 2 : choix de monde direct (L3E7B0-3E7E3)
        # L'original : clear _start_of_game, ___clr_wsc, ___swap_screens,
        # boucle ___show_world jusqu'a retour != -1, puis ___return_to_game,
        # puis _setup_display(0, -1).
        if self.start_of_game == 2:
            self.start_of_game = 0
            self.frame.blit(self.backdrop, (0, 0))  # ___clr_wsc equivalent
            # ___swap_screens : la boucle modale gerera son propre affichage
            while True:
                monde = self.show_world()  # remplit self._conquest, retourne monde
                if monde != -1:
                    self.sim.in_conquest = monde
                    break
            self._return_to_game()
            self.setup_display(0, -1)

        # L3E7E4 : _start_of_game efface dans tous les cas
        self.start_of_game = 0

        par_image = max(0.0, TURNS_PER_FRAME)
        tps = max(0.0, config.TURNS_PER_SECOND)
        # images par seconde ; 0.0 = sans plafond
        img_s = tps / par_image if (tps > 0.0 and par_image > 0.0) else 0.0
        credit = 0.0
        while self.running:
            for ev in pygame.event.get():
                self.handle(ev)
            self.poll_mouse()          # debounce + _zoom_map + _interogate
            if par_image >= 1.0:
                for _ in range(int(par_image)):
                    self.image()
            else:
                credit += par_image
                if credit >= 1.0:
                    credit -= 1.0
                    self.image()
            self.people = sum(1 for v in self.sim.map.who if v)
            self.afficher()
            self.frames += 1
            self.clock.tick(img_s)
        # Phase 86 : la piste rend la main avant que ``pygame.quit()`` ne
        # ferme le mixer -- meme chemin que ``SUB_2DD8`` ;1260.
        musique.arreter()
        self._piste_armee = False
        pygame.quit()


def main(argv: list[str]) -> None:
    """Point d'entree.

    .. code-block:: none

        python -m populous.game [graine] [sol] [zoom] [tours_par_image] [tours/s] [start_of_game]

    Les deux derniers arguments sont les leviers de cadence. Par defaut :
    ``tours_par_image = 1.0`` (un tour par image, la regle du listing,
    L681) et ``tours/s = 30.0``. ``0.0`` en tours/s enleve tout plafond,
    ``50.0`` rejoue le plafond VBlank de la boucle d'origine. Voyez
    :data:`populous.config.TURNS_PER_SECOND` pour la preuve au listing.

    ``start_of_game`` (entier 0/2/3, defaut 0) : 0 = normal, 2 = choix de
    monde direct (L3E7B0), 3 = tutoriel/demo (L4860A).
    ``--intro`` (n'importe ou dans la ligne) joue l'intro de la Phase 84
    avant la partie ; voir :data:`populous.config.SHOW_INTRO`.
    """
    if "--intro" in argv:
        config.SHOW_INTRO = True
        argv = [a for a in argv if a != "--intro"]

    seed = int(argv[0]) if len(argv) > 0 else DEFAULT_SEED
    ground = int(argv[1]) if len(argv) > 1 else DEFAULT_GROUND
    zoom = int(argv[2]) if len(argv) > 2 else ZOOM
    if len(argv) > 3:
        config.TURNS_PER_FRAME = float(argv[3])
    if len(argv) > 4:
        config.TURNS_PER_SECOND = float(argv[4])
    start_of_game = int(argv[5]) if len(argv) > 5 else 0
    g = Game(seed, ground, zoom)
    g.start_of_game = start_of_game
    g.run()


if __name__ == "__main__":
    main(sys.argv[1:])
