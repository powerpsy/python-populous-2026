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
                                ACT_QUAKE, ACT_RAISE, ACT_SWAMP,
                                ACT_TREE, ACT_VOLCANO, BLK_FLAT,
                                MANA_VALUES, ST_VILLAGER)
from populous.land import load_land  # noqa: E402
from populous.render import (SCREEN_H, SCREEN_W, Renderer,  # noqa: E402
                             clamp_off, map_colours)
from populous.powers import PowerEngine  # noqa: E402
from populous.sound import MusicEngine, SoundEngine  # noqa: E402
from populous.sim import Game as Sim  # noqa: E402
from populous.terrain import MAX_OFF, build_map  # noqa: E402

KEY_STEP = 4                    # cases par appui (le jeu d'origine fait defiler
                                # d'une case par image, cf. pavé _zoom_map)


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
        # L425-427 (`_game_mode = conq_04_mode`) reste a transcrire.
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
            self.powers.do_queued(t)
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

        Les 6 pushes avant le JSR donnent :

            _requester(ecran, x, y, largeur, hauteur, titre, message)

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
        haut = max(2, hauteur)           # hauteur, en lignes de 16 px

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
            self.palette(up, vp)
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
    def palette(self, up: int, vp: int) -> None:
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
        elif up in (7, 8) and vp == 0:              # LAB_3F924 / LAB_3FB26
            # Colonnes 7 et 8 : Phase 64 (L2134-2405).
            self.toggle_icon(up, vp, 0x12C0)

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
            self.powers.dispatch(sim.player, st.act, st.p1, st.p2)

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
                    sim._temp_view = who           # _set_temp_view(who)
                    sim._temp_timer = 10           # 10 images d'affichage
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
