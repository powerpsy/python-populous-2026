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

from populous.assets import load_pic  # noqa: E402
from populous.conquest import load_levels  # noqa: E402
from populous.conquest_win import nouveau_niveau, texte_fin  # noqa: E402
from populous.constants import (ACT_LOWER, ACT_RAISE, ACT_TREE,  # noqa: E402
                                BLK_FLAT)
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
        for t in (0, 1):
            sim.stats[t].can_build = 1
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
        ``docs/game_logic.md``). ``start_mana`` donne la mana de depart.
        Renvoie ``False`` si ``level.dat`` est absent.
        """
        levels = load_levels()
        if not levels:
            return False
        lv = levels[max(0, min(len(levels) - 1, n - 1))]
        self.conquest = lv
        self.conquest_no = n                 # le palier courant, pour l'ecran
        self.seed = (lv.number & 7) + lv.seed
        self.set_ground(lv.terrain)
        for pl in self.sim.players:
            pl.mana = lv.start_mana * 100
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
        """Fin de tour : l'IA ennemie choisit, puis le canal execute.

        Le joueur n'a pas encore d'interface de pouvoir, donc les deux fiches
        sont traitees de la meme facon — comme un joueur humain qui ne
        commanderait rien.
        """
        self.powers.ai_choose(self.sim.not_player)
        for t in (self.sim.player, self.sim.not_player):
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
        self.ren.draw_window(self.frame, self.terrain, self.xoff, self.yoff)
        self.ren.draw_peeps(self.frame, self.terrain, self.xoff, self.yoff,
                            self.sim)
        self._draw_cursor()
        self.show_the_shield()
        self.draw_pop_gauge()
        self.draw_conquest_dialog()
        self.draw_end_screen()
        self._draw_hud()

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

        # ---- L2888 : ennemi ----------------------------------------------
        if p.tribe == 1:
            # L2891 : x = (tribu << 1) + _toggle + 0x40 (animation de l'eau)
            x = ((p.tribe << 1) + self.ren.toggle + 0x40) & 0xFFFF
            self._draw_sprite_at(0x10C + x, 0x16, 0)
            # L2906 : la vie Â« reelle Â» (_check_life) et non la valeur stockee
            vie = sim.check_life(p.tribe, p.block)
            if vie <= 0:
                vie = 1
            self._bars_for(vie)
            return

        # ---- L2965 : villageois -------------------------------------------
        self._bars_for(p.life)

    def _draw_sprite_at(self, x: int, y: int, sprite: int) -> None:
        """``_draw_sprite(ecran, x, y, sprite)`` avec x en unites de 16 px."""
        sp = self.ren.sprites
        if not sp:
            return
        self.frame.blit(sp[sprite % len(sp)], ((x * 16) & ~1, y & ~1))

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

        d4 = (mx - 0x38) >> 4              # diagonale visee dans la fenetre
        alt = self.terrain.alt
        n_alt = len(alt)
        base = self.yoff * 0x41 + self.xoff
        nb = 9
        step = 0x48
        if d4 > 8:                         # coin droit du losange
            nb = 0x11 - d4
            base += d4 - 8
            step += (d4 - 8) * 8
        elif d4 < 8:                       # coin gauche du losange
            nb = d4 + 1
            base += (8 - d4) * 0x41
            step += (8 - d4) * 8

        col = -1
        cur_step = step
        for i in range(nb):
            k = base + i * 0x42
            top = cur_step - alt[k % n_alt if k < n_alt else n_alt - 1] * 8
            cur_step += 0x10
            # CMP.W D1,D2 / BGT : D2-D1 = (mousey+4) - top, donc BGT saute
            # quand le sommet de la case est *au-dessus* du curseur. La boucle
            # **ne s'arrete pas** (LAB_43662 ne fait qu'incrementer D6) : on
            # descend la diagonale en notant chaque case, et c'est la derniere
            # dont le bord haut n'a pas encore depasse le curseur qui gagne.
            if top <= my + 4:
                col = i
                sim.cur_screen = (d4 * 0x10 + 0x3D, top - 3)
        if col < 0:
            return False

        base += col * 0x42
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

        La cible est ecrite dans ``LAB_516A5/6[player]``, c'est-a-dire
        ``(x, y)`` de la carte. Deux ecarts assumes par rapport au listing
        tetracorp, tous deux documentes :

        1. Le listing ecrit ``MOVE.B (-1,A5),(0,A0,D0.L)`` pour la cible X, ce
           qui lit le **demi-mot haut** de ``cur_x`` — toujours nul, puisque
           ``cur_x < 64``. La cible serait donc systematiquement la colonne 0 ;
           on prend ``cur_x`` entier, comme pour Y.
        2. ``bitfield_51645`` n'est pas un champ independant : l'offset
           ``A4+0x8257`` est immediatement apres ``_mode`` (0x8256), c'est
           donc le **demi-mot haut** de ``_mode`` (bits 11 et 10). Ces deux bits
           ne sont poses nulle part dans le listing, et la branche par defaut
           ``LAB_43828`` ecrase ``stats.act`` avec 1 — ce qui supprimerait
           toute action choisie a la palette. On ne l'ecrase donc que si l'un
           de ces deux bits est reellement pose, ce qui reproduit le
           comportement du jeu : la palette choisit l'action, le clic sur la
           carte choisit la cible.
        """
        sim = self.sim
        st = sim.stats[sim.player]
        x, y = sim.cur_x, sim.cur_y

        if self.left_button == 0:
            if sim.mode & 0x0800:                  # bit 11 : relever arme
                sim.mode &= ~0x0800
                st.act, st.tend = 4, 0x0E
            elif sim.mode & 0x0400:                # bit 10 : abaisser arme
                sim.mode &= ~0x0400
                st.act, st.tend = 5, 0x0E
            sim.tgt[sim.player] = (x, y)
            sim.tgt_dirty = True
            return

        # ---- clic droit : LAB_43860 ---------------------------------------
        if (self.right_button == 0 and sim.mode == 2
                and not (sim.flags & 0x08)):
            self.right_button = 2
            st.act = 2                             # action du bouton droit
            sim.tgt[sim.player] = (x, y)
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
            # ---- 2. la barre d'icones â€” L1706-1824
            col = (u - 0x110) // 0x10
            row = (v - 0x20) // 0x10
            if (col, row) == (0, 0):              # poser un peuple
                self.toggle_icon(col, row, 0x17E4)
                st.act, st.p1, st.tend = 7, d0, 0x0E
            elif (col, row) == (0, 3):            # musique
                # L1744-1756 : on bascule, puis si le mot est non nul on
                # coupe tout le son.
                self.toggle_icon(col, row, 0x17E4)
                self.music_on ^= 1
                if self.music_on:
                    self.kill_effect(0, 4)
            elif (col, row) == (0, 4):            # effets sonores
                # L1768-1780, meme mecanique.
                self.toggle_icon(col, row, 0x17E4)
                self.effect_on ^= 1
                if self.effect_on:
                    self.kill_effect(0, 4)
            elif (col, row) == (1, 1):            # poser un peuple (2e variante)
                self.toggle_icon(col, row, 0x17E4)
                st.act, st.tend = 8, 0x0E
            elif (col, row) == (1, 3):            # volcan
                st.tend, st.act = 0x0E, 6
            elif (col, row) == (2, 2):            # abaisser
                self.toggle_icon(col, row, 0x17E4)
                st.act, st.tend = 2, 0x0E
        elif v >= 0x92:
            # ---- 3. le pave de defilement â€” L1825-1927
            vp = (v - 0x90) // 0x10
            up = (u - 0x60) // 0x10
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
            # ---- 4. la palette d'outils (LAB_3F666) â€” table de 9 entrees
            self.palette((u - 0x60) // 0x10, vp)
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
        """Une entree de la palette a ete cliquee.

        Chaque ecriture est celle de l'asm : ``stats+0`` est le **masque de
        pouvoirs autorises** (``tend``), ``stats+2`` le **code d'action**. Ces
        codes coincident exactement avec nos constantes ``ACT_*`` :

        Les codes ecrits dans ``stats+2`` coincident **exactement** avec nos
        constantes ``ACT_*`` (asm L1989 ``$03`` = ``ACT_QUAKE``, L2007 ``$05``
        = ``ACT_MAGNET``, etc.) :

        ==========  ==========  =========================  ========
        entree       stats+2     action (constante ACT_*)   cout
        ==========  ==========  =========================  ========
        (0, 0)       4           ACT_SWAMP   marais          5 000
        (1, 0)       3           ACT_QUAKE   seisme          2 500
        (1, 1)       -           tend = 0x06 seule          -
        (2, 0)       -           mode : ``_mode |= 8``       -
        (2, 1)       5           ACT_MAGNET  aimant            200
        (2, 2)       -           mode : ``_mode |= 8``       -
        (3, 3)       1           ACT_RAISE   relever            10
        (4, 3)       1           ACT_RAISE   relever, dir 1     10
        (4, 4)       1           ACT_RAISE   relever, dir 3     10
        (5, 3)       1           ACT_RAISE   relever, dir 2     10
        (6, 0)       -           ``_mode = 1``              -
        (6, 1)       -           ``_mode = 2``              -
        (6, 2)       -           ``_mode = (mode & 3) | 4`` -
        (7, 0)       -           liste d'habitants du village
        (8, 0)       -           liste d'habitants (2e tribu)
        ==========  ==========  =========================  ========

        Les quatre icones ``(3,3) (4,3) (4,4) (5,3)`` ecrivent toutes
        ``ACT_RAISE`` avec une **direction** differente dans ``stats+1``
        (0, 1, 3, 2) : ce sont les quatre outils de relief directionnels.

        Les modes 2 et 3 (et 4) font tourner ``_sculpt`` : c'est la que la
        souris designe une case. Le mode 1 est le mode normal, ou alone
        ``_interogate`` s'occupe du survol des habitants.
        """
        sim = self.sim
        st = sim.stats[sim.player]

        if up == 0 and vp == 0:                  # LAB_3F670
            self.toggle_icon(0, 0, 0x12C0)
            st.act, st.tend = 4, 0x0E
        elif up == 1 and vp == 0:                # LAB_3F6A4
            if not sim.paint_map:
                self.toggle_icon(1, 0, 0x12C0)
                st.act, st.tend = 3, 0x0E
        elif up == 1 and vp == 1:                # LAB_3F6DA
            st.tend, st.p1, st.p2 = 0x06, 0, 0
        elif up == 2 and vp == 0:                # LAB_3F71A
            st.tend, st.p1, st.p2 = 0x03, 0, 0
            sim.mode |= 0x08
            sim.pointer = 5
        elif up == 2 and vp == 1:                # LAB_3F758
            self.toggle_icon(2, 1, 0x12C0)
            st.act, st.tend = 5, 0x0E
        elif up == 2 and vp == 2:                # LAB_3F78C
            self.set_mode_icons(0, 6)
            sim.mode |= 0x08
            sim.pointer = 5
        elif up == 3 and vp == 3:                # LAB_3F804
            st.tend, st.p1, st.act = 0x0E, 0, 1
            sim._tend[sim.player] = 1
            self.set_tend_icons(3, 3)
        elif up == 4 and vp == 3:                # LAB_3F82A
            st.tend, st.p1, st.act = 0x0E, 1, 1
            sim._tend[sim.player] = 2
            self.set_tend_icons(4, 3)
        elif up == 4 and vp == 4:                # LAB_3F850
            st.tend, st.p1, st.act = 0x0E, 3, 1
            sim._tend[sim.player] = 3
            self.set_tend_icons(4, 4)
        elif up == 5 and vp == 3:                # LAB_3F878
            st.tend, st.p1, st.act = 0x0E, 2, 1
            sim._tend[sim.player] = 0
            self.set_tend_icons(5, 3)
        elif up == 6 and vp in (0, 1):          # LAB_3F8A0 (vp 0 et 1)
            # ``_mode = vp + 1`` tel quel (L2098-2100) : les deux cases
            # donnent exactement les modes 1 et 2. Puis ``_pointer = vp``
            # (L2115), sauf pour vp == 1 ou la regle speciale L2101-2112
            # s'applique (MULS #3 puis +1, donc 4 chez le joueur 1, 1 sinon).
            self.set_mode_icons(vp, 6)
            sim.mode = vp + 1
            sim.pointer = (4 if sim.player == 1 else 1) if vp == 1 else vp
        elif up == 6 and vp == 2:               # LAB_3F8F0 : 4e mode
            self.set_mode_icons(2, 6)
            sim.mode = (sim.mode & 0x03) | 0x04
            sim.pointer = sim.player + 2
        elif up in (7, 8) and vp == 0:            # LAB_3F924 / LAB_3FB26
            self.toggle_icon(up, vp, 0x12C0)

    def set_mode_icons(self, x: int, y: int) -> None:
        """``_set_mode_icons(x, y)`` (L2526-2551) : bascule l'icone ``(6,
        _mode - 1)`` ou, si un des drapeaux de mode est pose, ``(2, 6)`` /
        ``(2, 2)``."""
        if self.sim.flags & 0x04:
            self.toggle_icon(2, 6, 0x12C0)
        elif self.sim.flags & 0x08:
            self.toggle_icon(2, 2, 0x12C0)
        else:
            self.toggle_icon(6, (self.sim.mode & 0x03) - 1, 0x12C0)

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
        tend = self.sim._tend[  self.sim.player]
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
        """Execute l'action armee par la palette sur la case visee au clic.

        L'original ecrit l'action dans ``_stats+2`` et la cible dans
        ``LAB_516A5/6``, puis la boucle de messages (appellee en fin d'image,
        L1010) fait le lien. Ici le lien est fait des la meme image, ce qui rend
        le jeu reactif sans changer la logique.
        """
        sim = self.sim
        st = sim.stats[sim.player]
        if sim.tgt_dirty and st.act:
            x, y = sim.tgt[sim.player]
            self.powers.dispatch(sim.player, st.act, x, y)
            sim.tgt_dirty = False

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

    def set_ground(self, g: int) -> None:
        self.ground = g
        self.terrain, _ = build_map(self.seed, g)
        self.ren = Renderer(g)
        self.colours = map_colours(self.ren.header)
        self.sim = Sim(self.seed + 1, load_land(g),
                       map=self.terrain.game_map())
        self._settle_peoples()

    def set_seed(self, s: int) -> None:
        self.seed = s
        self.set_ground(self.ground)

    def run(self) -> None:
        while self.running:
            for ev in pygame.event.get():
                self.handle(ev)
            self.poll_mouse()          # debounce + _zoom_map + _interogate
            self.image()               # _move_peeps + audio + composition
            self.people = sum(1 for v in self.sim.map.who if v)
            self.screen.blit(pygame.transform.scale(self.frame,
                                                    self.screen.get_size()),
                             (0, 0))
            pygame.display.flip()
            self.frames += 1
            self.clock.tick(30)        # 30 images/s : cadence de l'original
        pygame.quit()


def main(argv: list[str]) -> None:
    seed = int(argv[0]) if len(argv) > 0 else 1
    ground = int(argv[1]) if len(argv) > 1 else 0
    zoom = int(argv[2]) if len(argv) > 2 else 3
    Game(seed, ground, zoom).run()


if __name__ == "__main__":
    main(sys.argv[1:])
