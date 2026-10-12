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
from populous.conquest import load_levels  # noqa: E402
from populous.conquest_win import nouveau_niveau, texte_fin  # noqa: E402
from populous.constants import (ACT_ACTION, ACT_LOWER, ACT_MAGNET,  # noqa: E402
                                ACT_NOP, ACT_QUAKE, ACT_RAISE, ACT_SWAMP,
                                ACT_TREE, ACT_VOLCANO, BLK_FLAT,
                                MANA_VALUES, ST_BATTLE, ST_VILLAGER)
from populous.land import load_land  # noqa: E402
from populous.render import (SCREEN_H, SCREEN_W, Renderer,  # noqa: E402
                             clamp_off, map_colours)
from populous.powers import PowerEngine  # noqa: E402
from populous.sound import MusicEngine, SoundEngine  # noqa: E402
from populous.sim import Game as Sim  # noqa: E402
from populous.terrain import MAX_OFF, build_map  # noqa: E402

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


class Game:
    def __init__(self, seed: int = 1, ground: int = 0, zoom: int = 3) -> None:
        self.seed = seed
        self.ground = ground
        self.zoom = max(1, zoom)
        self.xoff = 24
        self.yoff = 8
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
        self.mouse = (0, 0)
        # Les deux bascules de la barre. L'asm les nomme `_music_off` et
        # `_effect_off`, mais L19621/L19633 font `TST.W` puis `BEQ` : le bloc
        # est **saute quand le mot est zero**. Le son joue donc quand le
        # drapeau est non nul — l'inverse de ce que suggère le nom du
        # symbole. On suit le code, pas l'etiquette.
        self.music_on = 1
        self.effect_on = 1
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

        pygame.init()
        pygame.display.set_caption("Populous (remake) - %d/%d" % (seed, ground))
        self.screen = pygame.display.set_mode((SCREEN_W * self.zoom,
                                               SCREEN_H * self.zoom))
        self.clock = pygame.time.Clock()

        self.terrain, rng = build_map(seed, ground)
        self.ren = Renderer(ground)
        self.colours = map_colours(self.ren.header)
        # La simulation partage les tableaux du terrain : `map_who`, `map_bk2`
        # et `map_blk` sont donc vus a l'identique par le rendu.
        self.sim = Sim(seed + 1, load_land(ground),
                       map=self.terrain.game_map())
        # `_one_block_flat` (L9148) lit les altitudes de sommet, qui sont dans
        # le terrain et pas dans `GameMap`.
        self.sim.terrain = self.terrain
        self._sync_level_stats()
        self.powers = PowerEngine(self)
        self.sound = SoundEngine()
        self.music = MusicEngine(self.sound)
        self.effect = 0
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

        L'original appelle ``_place_people(0, magnet, 0)`` puis
        ``_place_people(1, 0, 0)`` ; le magnet est choisi par
        ``_set_magnet_to`` sur une case constructible.

        Comme les cartes generees sont tres asymetriques (la graine 1 a 73
        cases plates en haut contre 10 en bas), on ne fige pas un coin : on
        score **toutes** les cases constructibles et on prend les **deux
        meilleures**, ce qui garantit un depart equitable.
        """
        sim = self.sim
        blk = self.terrain.blk
        # L11256-11259 : le setup monojoueur ne pose que
        # `can_build[_not_player] = 1` ; `can_build[_player]` garde sa
        # valeur `.data`, qui est 0. `can_build[t] == 1` veut dire
        # « l'Amiga conduit la tribu t » (menu Game Setup, L12849-12866) :
        # c'est ce qui autorise l'auto-releve des noyes (L3497), le
        # sculptage `one_block_flat` (L4112) et le seuil avide 0x131
        # (L3830). Comme le port n'a pas encore d'interface de pouvoir,
        # la tribu joueur cesse donc de reagir toute seule.
        sim.stats[sim.player].can_build = 0
        sim.stats[sim.not_player].can_build = 1
        # `colour` garde 11/14 : le `.data` porte 5/1 (L24203 / L24229),
        # mais L408 et L12070 reecrivent le champ au demarrage et le port
        # travaille avec une autre table de palettes.
        for t in (0, 1):
            sim.stats[t].colour = 11 if t == 0 else 14

        scored = []
        for y in range(64):
            row = y << 6
            for x in range(64):
                i = row + x
                if blk[i] != BLK_FLAT:            # 0x0F = case constructible
                    continue
                n_flat = 0
                for dy in range(-3, 4):
                    yy = y + dy
                    if not 0 <= yy < 64:
                        continue
                    for dx in range(-3, 4):
                        xx = x + dx
                        if 0 <= xx < 64 and blk[(yy << 6) + xx] == BLK_FLAT:
                            n_flat += 1
                scored.append((n_flat, i))
        scored.sort(reverse=True)
        chosen = []
        for score, i in scored:
            x, y = i & 63, i >> 6
            # on exige une distance minimale entre les deuxTribes
            if all(abs(x - (j & 63)) + abs(y - (j >> 6)) >= 16 for j in chosen):
                chosen.append(i)
            if len(chosen) == 2:
                break
        for t, i in enumerate(chosen):
            sim.place_people(t, i, 0)

    # ------------------------------------------------------------ Conquest
    def load_conquest(self, n: int) -> bool:
        """Charge le palier de conquete ``n`` (1..99) et reconstruit la partie.

        ``seed = (in_conquest & 7) + graine`` et ``sol = terrain`` (§5.2 de
        ``docs/game_logic.md``). Les quatre ecritures de `_setup_display`
        (L407-423) y sont posees.
        Renvoie ``False`` si ``level.dat`` est absent.
        """
        levels = load_levels()
        if not levels:
            return False
        lv = levels[max(0, min(len(levels) - 1, n - 1))]
        self.conquest = lv
        self.conquest_no = n                 # le palier courant, pour l'ecran
        # L388-391 : `seed = (in_conquest & 7) + conq_08_seed`. `conq_08`
        # est un MOT (octets 8-9) - `lv.seed`, et non plus `data[3]`.
        self.seed = (lv.number & 7) + lv.seed
        # L395-402 : `conq_05_terrain` puis `_load_ground`. Attention a
        # l'ordre : `set_ground` regenere le relief **et** reinstantie
        # `self.sim`, donc les quatre ecritures de L407-423 doivent suivre,
        # sinon elles tomberaient sur la fiche qui vient d'etre jetee.
        self.set_ground(lv.terrain)
        sim = self.sim
        # _setup_display, L407-423 : les ecritures conditionnees au mode
        # conquest (`_in_conquest != -1`). Colonnes 0 et 1 : tribu 1 seule.
        #   L407-408  stats[1].threshold  = _conquest[0]
        #   L410-411  stats[1].period     = conq_01_speed
        #   L414-418  stats[1].power_mask = (conq_02_enemypow << 3) | 7
        #   L419-423  stats[0].power_mask = (conq_03_yourpow  << 3) | 7
        sim.stats[1].threshold = lv.threshold
        sim.stats[1].period = lv.ai_period
        sim.stats[1].power_mask = (lv.enemypow << 3) | 7
        sim.stats[0].power_mask = (lv.yourpow << 3) | 7
        # L'asm n'a **aucune** mana de depart par niveau : L1070 pose
        # $18F = 399 pour les deux tribus, et `conq_08` n'est lu que L390,
        # comme graine. L'ancienne formule `start_mana * 100` venait de la
        # colonne 8-9 lue comme deux octets de mana - elle disparait.
        # L425-427 : `_game_mode = conq_04_mode`. C'est le seul endroit du
        # port qui alimente les cinq options de l'ecran *SET GAME OPTIONS*
        # (Phase 71) - les cinq bits de bas poid sont les cinq paires de
        # choix exclusifs. Le port posait 0.
        sim.game_mode = lv.mode
        return True

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
    # les chaines de l'ecran de fin, prises dans le listing
    TEXT_LOST = "LOST"                 # strLost    (L14441)
    TEXT_TRY_AGAIN = "TRY IT AGAIN"    # strTryItAgain (L14449)
    TEXT_BATTLE = "BATTLE NUMBER IS "  # LAB_52224 (L14538)

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
        """L'ecran de fin — `_end_game` (asm L14019) puis `_won_conquest`.

        L'asm ecrit trois lignes avec `_requester` (L14358-14363) puis la
        ligne d'en-tete en `(8, 0xB2)` et `(8, 0xBA)` (L14523/L14546). Les
        coordonnees sont celles du listing : colonne en unites de 8 pixels et
        ligne en lignes de 8 pixels, donc `0xB2` = ligne 22 et `0xBA` = 23.
        """
        if not self.game_ended:
            return
        if self.conquest is not None:
            # L14522-14583 : le texte d'en-tete, puis la ligne complete.
            self.requester(0x08, 0xB2, 0xFF, 0x40,
                           texte_fin(self.conquest_no - 1, self.seed,
                                     self.conquest_fini), "")
            self.requester(0x10, 0xBA, 0xFF, 0x40,
                           "%s%d" % (self.TEXT_BATTLE, self.conquest_no), "")
        else:
            # hors conquete, l'asm affiche le tableau des scores
            self.requester(0x10, 0xA6, 0xFF, 0x40,
                           "YOU WIN" if self.victory else self.TEXT_LOST, "")
        # « TRY IT AGAIN » invite a continuer (strTryItAgain, L14452).
        self.requester(0x10, 0xC8, 0xFF, 0x40, self.TEXT_TRY_AGAIN, "")

    def tick(self) -> None:
        """Un pas de temps : un seul appel a ``move_peeps``.

        ``move_peeps`` avance lui-meme ``game_turn``/``toggle`` ET appelle
        ``set_frame`` exactement aux endroits de l'asm. Il ne faut surtout pas
        ajouter un second ``set_frame`` ici : la machine d'animation
        (« frames 0..6 puis transition ») ne se produirait jamais.
        Le canal de commandes est joue ensuite, comme dans l'asm (L1011).
        """
        self.sim.move_peeps()
        self._run_commands()
        self._check_end()

    def image(self) -> None:
        """Une image complete, dans l'ordre de la boucle d'image (L962-1013).

        On sort de la simulation tant que l'ecran de fin est affiche : l'asm
        fait de meme, sa boucle d'ecran s'arrêtant sur l'ecran de fin.
        """
        if self.game_ended:
            self.compose()
            return
        self.tick()
        self._audio()
        self.compose()

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
        if self.conquest is not None:
            # L14412 : `_won_conquest(score)`.
            self.score += self.sim.population(self.sim.player)
            nouveau, self.conquest_fini = nouveau_niveau(
                self.conquest_no - 1, self.score)
            # L14497 : `_seed = _level_number` — le relief est regenere, donc
            # on ramene l'index dans les 99 paliers que contient level.dat.
            self.conquest_next = (nouveau % 99) + 1

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
        self.frame.blit(self.backdrop, (0, 0))
        self._apply_icon_toggles()          # etat persistant des icones (_back_scr)
        self.ren.draw_minimap(self.frame, self.terrain, colours=self.colours)
        self.move_mana()                    # L622 : avant __draw_it
        self.ren.draw_window(self.frame, self.terrain, self.xoff, self.yoff)
        self.ren.draw_peeps(self.frame, self.terrain, self.xoff, self.yoff,
                            self.sim)
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
        """
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
                              colours=self.colours)   # ___draw_map

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
        * L2790 ``_draw_icon(0x11, 0x04, tribu)``    le blason ;
        * L2796 recherche de l'arme dans ``_weapons_order[1..10]`` ;
        * L2813 ``_draw_icon(0x12, i+1, 4)``   l'icone d'arme (icone 4 = 0x04) ;
        * L2823 ``state & 8`` (combattant)      -> sprite + 2 barres ;
        * L2888 ``tribune == 1`` (ennemi)      -> sprite 0x16 + 2 barres ;
        * L2965 villageois                    -> 2 barres (vie / arme).
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
        if i < 11:
            r.draw_icon(d, 0x12, i + 1, 0x04)

        # ---- L2823 : combattant (bit 3 de l'etat) ------------------------
        if p.state & 0x08:
            # L2826 : le sprite de l'arme, a x=0x110 (272 px), y=0x16 (22)
            self._draw_sprite_at(0x110, 0x16, p.frame)
            # L2859 : deux barres, largeurs issues de deux __divs par la vie
            self._bars_for(p.life)
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
            # L2891 : sprite = (tribe << 1) + _toggle + $40 (animation eau)
            sprite = ((p.tribe << 1) + self.ren.toggle + 0x40) & 0xFFFF
            # L2888-2894 : l'ordre de push est sprite, y, x, ecran, donc
            # `_draw_sprite(_w_screen, $10C, $16, sprite)` -- **sprite est le
            # quatrieme argument**, pas une composante de x. Le code faisait
            # `0x10C + x` avec sprite 0 : x valait 334 (hors des 320 px) et
            # on dessinait le mauvais sprite.
            self._draw_sprite_at(0x10C, 0x16, sprite)
            # L2906 : la vie Â« reelle Â» (_check_life) et non la valeur stockee
            vie = sim.check_life(p.tribe, p.block)
            if vie <= 0:
                vie = 1
            self._bars_for(vie)
            return

        # ---- L2965 : villageois -------------------------------------------
        self._bars_for(p.life)

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

    def _bars_for(self, valeur: int) -> None:
        """Les deux barres de l'ecusson (L2871 et L2879, puis L3042/L3053).

        L'asm calcule deux fois une division par ``life`` pour obtenir des
        largeurs de barre, puis trace deux ``_draw_bar`` de 15 lignes. La
        seconde valeur du couple est, elle, une division par 16 donnee par
        ``weapons`` (L3084 ``DIVS #$0010``).
        """
        r = self.ren
        # L2871 : 15 lignes a x=0x24 (pixel 288), flags 0x0F (les 4 plans)
        r.draw_bar(self.frame, 0x24, 0x25, 0x0F, max(0, min(0x0F, valeur >> 8)),
                   0x0F)
        # L2879 : 8 lignes a x=0x25 (pixel 296) â€” meme principe, barre fine
        r.draw_bar(self.frame, 0x25, 0x25, 0x08, max(0, min(0x08, valeur >> 9)),
                   0x0F)

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

        avec ``D4 = x >> 4``, ``D1 = largeur >> 4`` (nombre de colonnes) et
        ``D5 = y >> 4`` (premiere ligne).

        Le cadre est fait d'icones de 16x16 posees une par une :

        * bandeau haut (L9918-9948) : 0x0C, puis 0x0D jusqu'a la colonne
          ``D1 - 1``, puis 0x0E ;
        * cotes (L9949-9990) : ``D6`` part de ``D5 + 0x10`` et avance de
          ``0x10`` tant que ``D6 < D5 + hauteur - 0x10`` ; a chaque tour on
          pose 0x12 a gauche, 0x14 sur les colonnes centrales et 0x13 a
          droite ;
        * bandeau bas (L9991-9996) : 0x0F puis 0x10 ;
        * titre (L10045-10057) : `_text` trois lignes plus bas ;
        * message (L10059-10126) : `_text` cinq lignes plus bas, centre sur
          ``(colonnes * 16 - strlen) / 2``.

        Comme `_draw_icon` ecrase les 4 plans, l'interieur de la boite est
        **noir** — c'est bien ce que fait l'original.
        """
        r, d = self.ren, self.frame
        d4 = x >> 4                      # colonne de depart, en unites de 16 px
        d5 = y >> 4                      # premiere ligne, en LIGNES
        n = max(2, largeur >> 4)         # nombre de colonnes
        # L9949-9960 : `D6` va de `D5+$10` a `D5+hauteur-$10` par pas de
        # `$10`, soit `hauteur/16 - 1` rangees. Le port prenait `hauteur`
        # brut, soit 16x trop de rangees.
        haut = max(2, hauteur >> 4)     # hauteur, en LIGNES (L9953)

        px = lambda col: d4 + col        # noqa: E731  colonne

        # ---- bandeau haut (L9918-9948) ----------------------------------
        r.draw_icon(d, px(0), d5, 0x0C)
        for i in range(1, n - 1):
            r.draw_icon(d, px(i), d5, 0x0D)
        r.draw_icon(d, px(n - 1), d5, 0x0E)

        # ---- cotes (L9949-9990) : D6 de D5+0x10, par pas de 0x10 --------
        for j in range(1, haut - 1):
            yj = d5 + j * 16
            r.draw_icon(d, px(0), yj, 0x12)
            r.draw_icon(d, px(n - 1), yj, 0x13)

        # ---- bandeau bas (L9991-9996) ----------------------------------
        bas = d5 + (haut - 1) * 16
        r.draw_icon(d, px(0), bas, 0x0F)
        for i in range(1, n - 1):
            r.draw_icon(d, px(i), bas, 0x10)

        # ---- titre (L10045-10057) : sous le bandeau, en px ---------------
        if titre:
            r.draw_text(d, px(0) * 2 + 1, d5 + 16 + 3, titre)

        # ---- message (L10059-10126) : centre dans la largeur -----------
        if message:
            cx = (px(0) * 16 + (n * 16 - r.text_width(message)) // 2) // 8
            r.draw_text(d, cx, d5 + 16 + 5, message)


    # --------------------------------------------- jauges de population (L403F4)
    # Apres le bouclier, l'asm trace les jauges : ``good_pop`` (le peuple du
    # joueur) et ``bad_pop``, chacune divisee par 0x1F (L403FE) puis tracee
    # en 0x1F lignes a partir de x=0x20.
    def draw_pop_gauge(self) -> None:
        """Les deux jauges de population (asm L403F4-40446)."""
        sim = self.sim
        r = self.ren
        # L40403 : good_pop / 31 -> _draw_bar(x=0x20, y=0x20, h=0x1F)
        r.draw_bar(self.frame, 0x20, 0x20, 0x1F,
                   min(0x1F, sim.good.pop * 0x1F // 1000), 0x0F)
        # LAB_40430 : bad_pop, meme position (la colonne x=0x20)
        r.draw_bar(self.frame, 0x20, 0x1F, 0x1F,
                   min(0x1F, sim.bad.pop * 0x1F // 1000), 0x0F)
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
        """
        for ev in pygame.event.get():
            self.handle(ev)
        self._read_buttons()

    def _cadres_boutons(self, x: int, y: int, largeur: int,
                        hauteur: int, texte_ok: str = "OK",
                        texte_cancel: str = "CANCEL"):
        """Les deux cadres poses par ``_requester`` (L9991-10246).

        ``_requester`` remplit lui-meme les structures ``_end_ok`` et
        ``_end_cancel`` sur la ligne du bas de la boite. L'arithmetique,
        relevee telle quelle :

        * ``D4 = x >> 4``, ``D5 = y >> 4`` (L9904-9905) ;
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
        d5 = y >> 4                     # L9905
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

        **Six handlers restent non transcrits** parce qu'ils appellent une
        routine qui ne l'est pas - ils levent `NotImplementedError` en
        nommant la routine : ligne 2 (`_two_players`, L11265) sur sa branche
        active, ligne 9 (`_show_world`, L12190), ligne 11 (`_set_options`,
        L13362), lignes 12 et 13 (`_save_load`, L10493), ligne 15
        (`_ground_in` + `___setup_display`, L18924). Le port ne peut pas
        faire semblant : mieux vaut une erreur nommee qu'un ecart muet.
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
            raise NotImplementedError(               # L13282-13284
                "GAME SETUP : la ligne 15 (RESTART THIS MAP) veut "
                "`_new_map = _ground_in + 2` ; le port ne suit pas "
                "`_ground_in` (L396-399, L438-441)")
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
        # ECART declare : le listing y met `_start_seed`, le port n'a qu'un
        # seul mot de graine, `self.seed`. Les deux sont egaux juste apres
        # `load_conquest` (L430 `_start_seed = _seed`) et ne divergent qu'au
        # milieu d'une partie, quand `_seed` est regenere (L18922 fait
        # l'inverse). Le port lit donc `self.seed`.
        prefixe, decalage = SET_OPTIONS_PASTICHE
        buf = prefixe + str(self.seed)
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
        self.load_ground(self.sim.ground_in)     # L17586-17589
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
        """Le trace de l'ecran des douze emplacements (L10520-10750)."""
        r, d = self.ren, self.frame
        self.requester(*self._boite_save_load(), "", "")
        # les trois titres de colonnes, tous a y = $58 (L10530-10570)
        for x, txt in ((0x18, "SAVE GAME" if sauvegarder else "LOAD GAME"),
                       (0x7A, "DIRECTORY"), (0xD8, "FILE NAME")):
            r.draw_text(d, x >> 3, 0x58, txt)
        # les douze emplacements : `LAB_525C8[k]` a `$22 + k*8` (L10577-10585)
        for k in range(12):
            if k < len(self._saves_liste):
                nom = self._saves_liste[k].rstrip(b"\x00").decode("latin-1")
            else:
                nom = ""
            r.draw_text(d, (0x22 + k * 8) >> 3, 0x58, nom)
        # le tiroir puis le nom de fichier, a `$A0` (L10739-10749)
        r.draw_text(d, 0xA0 >> 3, 0x58, self._saves_drawer)
        r.draw_text(d, 0xA0 >> 3, 0x58, self._saves_nom)

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
        * le tiroir est liste par `_get_a_dir` puis `_sort` **une seule fois**,
          a la construction (L10589-10598) - les douze emplacements ne sont
          donc pas recharges pendant la navigation ;
        * chaque clic dans la zone `$58..$D8` x `$22..$82` met `_filename` a
          l'entree correspondante (L10759-10784) ; les deux fleches a
          `$D8..$E0` font defiler (L10819-10842) ;
        * `_check_cancel` : `0` retrace, `2` sort sans rien faire, `1`
          assemble le chemin (L10832-10886) puis appelle `_save_game` ou
          `_load_game` (L10888-10894).

        Apres une sauvegarde reussie, la routine met `_saved = 1` (L10930)
        puis **verifie que `level.dat` est present** : elle boucle sur
        `Open("level.dat", $3ED)` tant que le fichier manque, en affichant
        `strInsertDisk` (L10931-10950).

        **Non transcrit** : `_get_name` (L10307, 183 lignes), l'editeur de
        nom de fichier au clavier - les deux zones d'edition (tiroir a `$8D`,
        nom a `$A0`, L10787-10815) leve donc `NotImplementedError`.
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
            # L10787-10815 : les deux zones d'edition
            mx, my = self.mouse
            if 0x58 <= mx <= 0xD8 and 0x8D <= my <= 0x95:
                raise NotImplementedError(
                    "SAVE/LOAD : l'edition du tiroir appelle `_get_name` "
                    "(L10307), non transcrite")
            if 0x58 <= mx <= 0xD8 and 0xA0 <= my <= 0xA8:
                raise NotImplementedError(
                    "SAVE/LOAD : l'edition du nom de fichier appelle "
                    "`_get_name` (L10307), non transcrite")
            i = self._survol_save_load()             # L10759-10784
            if i is None:
                self._defiler_save_load(
                    1 if (mx >= 0xD8 and 0x7A <= my <= 0x82) else
                    (-1 if (mx >= 0xD8 and 0x22 <= my <= 0x2A) else 0))
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

    def _verifier_level_dat(self) -> None:
        """L10931-10950 : `level.dat` doit etre lisible, sinon on le demande.

        La routine boucle sur `Open("level.dat", $3ED)` tant que le fichier
        manque : elle ne rend la main qu'apres l'avoir referme. Le port
        n'insere pas de disque - il n'y en a pas - mais l'echec reste
        signale.
        """
        import os
        if not os.path.exists("level.dat"):
            print("[SAVE/LOAD] level.dat est absent du repertoire courant")

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
        NEW GAME que la saisie passe par `_get_name` (L12249), **non
        transcrite** : le port leve `NotImplementedError` a cet endroit -
        apres un premier monde accepte, jamais avant.
        ``tools/check_show_world_modal.py`` relit ces quatre lignes pour
        le montrer, puis provoque la levee.

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

        **ECART declare** : `_start_seed` n'existe pas dans le port, qui
        n'a qu'un seul mot de graine (`self.seed`, meme ecart qu'aux
        lignes 1836-1840).
        """
        from populous.decode import decode
        # `strGENESIS1` (L12782) et `strGENESIS2` (L12786) sont les memes
        # sept octets, ecrits deux fois dans le listing : une seule constante
        # dans le port.
        from populous.world import (WORLD_BOXE, WORLD_GENESIS,
                                    WORLD_GRAINE, WORLD_LEVEL_DAT,
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
                    raise NotImplementedError(
                        "_show_world : la deuxieme saisie passe par "
                        "`_get_name` (L10307), non transcrite")
                n = _atoi(self._message) & 0xFFFF     # L12262-12265
                if n != 0:                  # L12266
                    self.seed = n            # L12270-12271 `_start_seed=_seed`
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
                print("[SHOW-WORLD] %s est introuvable : le jeu demande "
                      "d'insérer le disque original (L12371-12374), et "
                      "boucle tant qu'il n'y est pas." % WORLD_LEVEL_DAT)
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
            # L'ecran de fin attend une touche pour enchainer (asm L14392 :
            # `LAB_48B24` boucle sur `_left_button` jusqu'au clic).
            if self.game_ended:
                if ev.key in (pygame.K_RETURN, pygame.K_SPACE,
                              pygame.K_ESCAPE):
                    self._next_conquest()
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
    def load_ground(self, n: int) -> bool:
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

        Renvoie 1, comme le ``MOVEQ #1,D0`` du listing. Le chemin d'erreur
        LAB_4A426 appelle ``_do_message``, sous-systeme non transcrit : cette
        methode **leve** plutot que de renvoyer silencieusement 0.
        """
        try:
            tables = load_land(n)                 # LandTables : l'en-tete
            header, tiles = load_tiles(n)         # + les 0x8340 octets de tuiles
        except (FileNotFoundError, ValueError):
            raise NotImplementedError(
                "_load_ground : chemin d'erreur LAB_4A426 (_do_message) "
                "non transcrit") from None

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

    def set_ground(self, g: int) -> None:
        self.ground = g
        self.terrain, _ = build_map(self.seed, g)
        self.ren = Renderer(g)
        self.colours = map_colours(self.ren.header)
        self.sim = Sim(self.seed + 1, load_land(g),
                       map=self.terrain.game_map())
        self.sim.terrain = self.terrain
        self._sync_level_stats()
        self._settle_peoples()

    def set_seed(self, s: int) -> None:
        self.seed = s
        self.set_ground(self.ground)

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
            self.screen.blit(pygame.transform.scale(self.frame,
                                                    self.screen.get_size()),
                             (0, 0))
            pygame.display.flip()
            self.frames += 1
            self.clock.tick(img_s)
        pygame.quit()


def main(argv: list[str]) -> None:
    """Point d'entree.

    .. code-block:: none

        python -m populous.game [graine] [sol] [zoom] [tours_par_image] [tours/s]

    Les deux derniers arguments sont les leviers de cadence. Par defaut :
    ``tours_par_image = 1.0`` (un tour par image, la regle du listing,
    L681) et ``tours/s = 30.0``. ``0.0`` en tours/s enleve tout plafond,
    ``50.0`` rejoue le plafond VBlank de la boucle d'origine. Voyez
    :data:`populous.config.TURNS_PER_SECOND` pour la preuve au listing.
    """
    seed = int(argv[0]) if len(argv) > 0 else DEFAULT_SEED
    ground = int(argv[1]) if len(argv) > 1 else DEFAULT_GROUND
    zoom = int(argv[2]) if len(argv) > 2 else ZOOM
    if len(argv) > 3:
        config.TURNS_PER_FRAME = float(argv[3])
    if len(argv) > 4:
        config.TURNS_PER_SECOND = float(argv[4])
    Game(seed, ground, zoom).run()


if __name__ == "__main__":
    main(sys.argv[1:])
