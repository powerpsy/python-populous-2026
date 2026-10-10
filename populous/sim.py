"""Cœur de simulation de Populous — reconstitution des routines de ``_move_peeps``.

Références : ``docs/game_logic.md`` (lecture intégrale du désassemblage) et
``reference/tetracorp/populous_prg.asm``. Les passages marqués **[APPROX]** ne
sont plus « là où le désassemblage est coupé » — la Phase 12 a montré que le
listing est complet — mais ceux qui n'ont pas encore été transcrits ligne à
ligne. Il n'en reste **aucun** dans ``populous/`` : la derniere branche
ouverte, ``LAB_45196`` de ``_set_devil_magnet``, a ete transcrite ligne a
ligne en Phase 57, apres ``_do_place_funny`` (Phase 56) et la marche
d'exploration. Les marqueurs **[APPROX]** servent donc maintenant de
compteur : ils sont a zero.

Corrections apportées au document par relecture directe du code :

* ``_peeps+0x0A`` (``prev_block``) n'est **pas** la case précédente mais le
  **déplacement** effectué (``p.block += delta ; p.prev_block = delta``,
  asm 4168E‑41696). ``_zero_population`` utilise donc
  ``map_who[p.block - p.prev_block]`` = l'ancienne case (asm 42258‑4227E).
* ``_do_battle`` fait subir les dégâts **aux deux combattants**, sur la base de
  ``min(roll_atk, roll_opp)`` : chaque camp perd
  ``autre.weapons * (min_roll // 100) + 10`` (asm 42704‑42758). La formule du
  document (`loser.weapons * max(...)`) est erronée.
* ``_zero_population`` : si ``state == 0x08``, l'adversaire (``p.w6``) perd le
  bit 3 (asm 4220C‑42220) — preuve que **+0x06 vaut l'index de l'adversaire
  pendant une bataille**, et le tour d'installation le reste à l'extérieur
  (surcharge de champs, cf. §A.3).
"""
from __future__ import annotations

from . import m68k
from .constants import (
    A_FLAT,
    BIG_CITY, BLK_FLAT, BLK_ROCK, BLK_ROCK2, BLK_ROCK3, BLK_RUINS,
    BLK_SWAMP, BLK_TRIBE0, BLK_WATER,
    FRAME_AGE, FRAME_TOWN, FUNNY, MANA_VALUES, MAP_CELLS, MAX_PEEPS,
    PEEP_SLOTS, BK2_CITY, N_BIG_NEIGHBOURS, N_NEIGHBOURS, OFFSET_VECTOR,
    ST_DROWNING,
    ST_EXPLORER, ST_VILLAGER, ST_ANIM, ST_BATTLE,
    OPPOSITE, TO_DELTA, TO_OFFSET,
)
from .land import LandTables, load_land
from .map import GameMap
from .rng import Rng


# ------------------------------------------------------------------ structures
class Peep:
    """Fiche d'unité, 22 octets (``_peeps``, asm $53014)."""

    __slots__ = (
        "state", "tribe", "offspring", "weapons", "life", "w6",
        "block", "prev_block", "frame", "target", "spawn_block",
        "make_level_res", "face",
    )

    def __init__(self) -> None:
        self.state = 0
        self.tribe = 0
        self.offspring = 0
        self.weapons = 0
        self.life = 0
        self.w6 = 0            # tour d'installation OU index adversaire (bataille)
        self.block = 0
        self.prev_block = 0     # delta du dernier déplacement
        self.frame = 0
        self.target = -1        # index du peep visé, -1 = aucun (0 dans le jeu)
        self.spawn_block = 0
        self.make_level_res = 0
        # +0x15 : un OCTET. Le listing y ecrit l'octet **haut** du mot
        # `_to_offset[delta]`, donc 0xFF pour un deplacement vers l'ouest et
        # 0x00 vers l'est (L5256-5257). Relu plus loin par `EXT.W`, donc la
        # valeur vue en signe est -1 ou 0 -- et la comparaison avec
        # `_to_offset[D4]` de L5415 n'est donc satisfaite que pour la
        # direction O. Ce n'est pas un index de pas.
        self.face = 0

    def __repr__(self) -> str:                      # pragma: no cover
        return ("Peep(t=%d trib=%d vie=%d bloc=%d état=%02X frm=%02X)"
                % (id(self) % 1000, self.tribe, self.life, self.block,
                   self.state, self.frame))


class Tribe:
    """Fiche par tribu, 46 octets (``_stats``, asm $516A4)."""

    __slots__ = (
        "act", "p1", "p2", "can_build", "queued", "threshold", "power_mask",
        "period", "t12", "castles", "towns", "t18", "t1a", "t1c", "t1e",
        "colour", "strongest", "p26", "p2a", "tend",
    )

    def __init__(self, t: int = 0) -> None:
        # `.data` de `_stats` (L24171-24230) : les deux fiches sont
        # initialisees une fois pour toutes au chargement du binaire, avant
        # toute partie. Les trois premiers octets valent $61/$62/$63 —
        # « abc », dc.b de L24172 pour la fiche 0 et `strABC` de L24212
        # pour la fiche 1. Ce sont des codes `act/p1/p2` sans effet : le
        # dispatch saute a LAB_4B818 des que `act >= $0F` (L18219-18220),
        # donc 97 ne fait rien.
        self.act = 0x61         # +0x00  LAB_516A4 / strABC[0]
        self.p1 = 0x62          # +0x01  LAB_516A5 / strABC[1]
        self.p2 = 0x63          # +0x02  LAB_516A6 / strABC[2]
        # `can_build[t] == 1` veut dire « l'Amiga conduit la tribu t » :
        # menu Game Setup, `strHumanVsAmiga` est selectionne quand
        # `can_build[_player] == 0` (L12849-12866). Le `.data` vaut donc
        # 0 (bon) / 1 (mal), et L11256-11259 ne pose que `+1` sur le
        # `_not_player` du setup monojoueur.
        self.can_build = 1 if t else 0   # +0x06  LAB_516AA / LAB_516D8
        # `queued == 1` arrete tout ce qui depend de l'IA pour la tribu :
        # `_set_devil_magnet`/`_devil_effect` (L3255-3268), le bloc
        # `_make_level` (L3770), `one_block_flat` (L4112) et le seuil
        # avide 0x131 (L3841). Le SEUL vidage du listing exige
        # `can_build == 1` (L17934-17951) : la tribu humaine garde donc
        # `queued == 1` pour toujours.
        self.queued = 1         # +0x08  LAB_516AC / LAB_516DA ($00010000)
        self.threshold = 1 if t == 0 else 5   # +0x0C  LAB_516B0 / LAB_516DE
        self.power_mask = 0xFFFF              # +0x0E  LAB_516B2 / LAB_516E0
        self.tend = 0           # alias explicite du champ +0x0E
        self.period = 1 if t == 0 else 3         # +0x10 période des décisions IA
        self.t12 = 0            # +0x12
        self.castles = 0        # +0x14 châteaux
        self.towns = 0          # +0x16 villes
        self.t18 = self.t1a = self.t1c = self.t1e = 0
        self.colour = 5 if t == 0 else 1         # +0x20 couleur de la mini-carte
        self.strongest = -1     # +0x22 index du peep ennemi le plus fort
        self.p26 = -1           # +0x26 (0 = pointeur nul dans le jeu)
        self.p2a = -1           # +0x2A index du peep le plus jeune
                              # (pointeur nul dans l'asm)


class Player:
    """Fiche par joueur, 16 octets (``_magnet``, asm $52DE4)."""

    __slots__ = ("magnet", "magnet_to", "command", "town_count", "pop", "mana")

    def __init__(self) -> None:
        self.magnet = 0         # +0  index + 1 du peep aimanté (0 = aucun)
        self.magnet_to = 0x820  # +2  case visée par l'aimant (LAB_52DE6)
        self.command = 1        # +4  outil courant (LAB_52DE8, init L1065)
        self.town_count = 0     # +6  compteur « town » (remis à 0 par tour)
        self.pop = 0            # +8  somme des vies
        # L1070 ecrit `mana = $18F = 399` a l'initialisation. La Phase 41 avait
        # montre qu'appliquer 399 **avant** d'avoir transcrit l'IA armait
        # l'heuristique inventee, qui detruisait sa propre tribu (population
        # A de 10 064 a 917, et 0 sur la graine 314).
        #
        # L'IA est desormais transcrite (Phase 42), et la mesure change de
        # sens : sur 9 000 tours, population A de 161 398 / 207 643 /
        # 184 298 avec l'IA du listing, contre 917 / 425 / 0 avec
        # l'heuristique. Les deux valeurs fideles vont donc ensemble.
        self.mana = 399         # +12 réserve de mana (L1070 : $18F)


# ------------------------------------------------------------------- la partie
class Game:
    """État complet d'une partie."""

    def __init__(self, seed: int = 0, land: LandTables | None = None,
                 player: int = 0, map: GameMap | None = None) -> None:
        self.map = map if map is not None else GameMap()
        # Les altitudes de SOMMET (`_alt`, 65x65) vivent dans le terrain, pas
        # dans `GameMap` qui ne porte que les 4096 cases. `_one_block_flat`
        # (L9148) en a besoin, donc on garde la reference.
        self.terrain = None
        self.rng = Rng(seed)
        self.land = land if land is not None else load_land(0)

        # `_peeps` compte **212** fiches : 5424C - 53014 = 4664 = 212 * 22,
        # et `_no_peeps` suit immediatement (L25365-25392). MAX_PEEPS (208)
        # reste la borne de simulation : `find_free_slot` et les boucles de
        # `_move_peeps` n'atteignent jamais les fiches 208..211, ecrites par
        # `_do_place_funny` (slots 0xD1/0xD2) et lues via `map_who`.
        self.peeps: list[Peep] = [Peep() for _ in range(PEEP_SLOTS)]
        self.no_peeps = 0
        # `Tribe(0)` / `Tribe(1)` portent desormais tout le `.data` de
        # `_stats` (L24171-24230) : act/p1/p2 = $61/$62/$63, `can_build`
        # 0/1, `queued` 1/1, `threshold` 1/5, `power_mask` $FFFF/$FFFF,
        # `period` 1/3, `colour` 5/1. Sans `power_mask = $FFFF` toute la
        # cascade d'`ai_choose` (L9365-9396) reste morte hors Conquest.
        self.stats = [Tribe(0), Tribe(1)]
        self.players = [Player(), Player()]

        self.game_turn = 0
        self.toggle = 0          # inversement à chaque image
        self.war = 0             # guerre globale
        self.pause = 0
        self.paint_map = 0
        self.player = player
        self.not_player = 1 - player
        self.seed = seed
        self.cheat = 0
        self.serial_off = 0
        self.flags = 0x10        # LAB_518A7 (L24311-24312, DC.B $10) :
                                   # bit0 tue dans l'eau, bit2 gele l'IA
        # Globaux remis a zero par `_check_life` (L20965 / L20970) puis lus
        # par `_move_peeps` juste apres l'appel : L3785 / L4042 pour
        # `a_flat_block`, L4047 pour `all_of_city`.
        self.a_flat_block = 0
        self.all_of_city = 0
        self.battle_won = [0, 0]
        # miroirs de `players[t].magnet_to` (asm A4+$ae78 / A4+$ae76)
        self.god_magnet = 0x820
        self.devil_magnet = 0x820
        self.view_who = 0
        self.funny_done = 0
        self.effect = 0          # code du dernier effet sonore à jouer

        # --- etats d'interface transcrits de l'asm -------------------------
        self.mode = 1             # _mode : 1..3 = mode d'outil courant
        self.pointer = 0          # _pointer : curseur d'icone associe
        # `bitfield_51645` (0x51645) n'est pas un champ independant :
        # c'est l'octet **bas** du mot `_mode` (0x51644), comme le prouve
        # `MOVE.W #$0002,(_mode,A4)` (L1148) qui redonne exactement les
        # deux octets initiaux. `mode & 04` = aimant arme, `mode & 08` =
        # marais arme ; un `ui_bits` a part restait toujours nulle.
        self.ok_to_build = 0      # _ok_to_build (L7307)
        self.cur_x = 0            # _cur_x : case sous la souris (_sculpt)
        self.cur_y = 0            # _cur_y
        self.cur_screen = None    # (x, y) du curseur dessine (sprite 0x54)
        self.tgt = [(0, 0), (0, 0)]    # LAB_516A5/6[player] : case visee
        self.tgt_dirty = False         # une cible vient d etre posee
        self.view_people = 0      # _view_people (L25458) : habitant suivi
        self.view_fight = 0       # _view_fight (L25456) : prochaine bataille
        self._temp_view = 0       # `_view_who` du survol temporaire
        self._temp_timer = 0      # _view_timer : 10 images de reaffichage
        self.old_view_who = 0     # _old_view_who (L25400) : sauvegarde
        # _weapons_order (asm L25460) : 11 mots, remplis a l'execution. L'asm
        # cherche (asm L2800-2811) l'indice i tel que weapons_order[i] ==
        # peep.weapons, i de 1 a 10 : c'est l'ordre d'affichage des armes dans
        # l'ecusson. On construit la table depuis ``weapons_add`` du terrain,
        # qui donne l'arme de chaque age (asm L3877-3882).
        # L4A372-4A41E : `for i in 0..10: _weapons_order[i] = _weapons_add[i]`
        # puis un tri croissant (boucle particuliere : pour chaque i on
        # compare a tous les j et on echange des que order[i] < order[j]).
        # Les sols 0..4 livrent deja leurs weapons_add tries, donc `sorted()`
        # ne change rien sur les donnees reelles — c'est la transcription, pas
        # une correction. Le rang 0 n'est jamais lu (la recherche de L2804
        # part de 1) ; le 0xFFFF borne l'indice 10.
        self.weapons_order = sorted(self.land.weapons_add[0:11]) + [0xFFFF]
        # LAB_52DE8[_player] : quel outil de relief est arme (0 = aucun).
        # C'est ce que ``_set_tend_icons`` (L2455) utilise pour inverser la
        # bonne icone de la croix de selection.
        self._tend = [0, 0]

        # callback optionnel : mini-carte (asm _a_putpixel)
        self.minimap_pixel = None

    # --------------------------------------------------------------- accès
    @property
    def good(self) -> Player:
        return self.players[self.player]

    @property
    def bad(self) -> Player:
        return self.players[self.not_player]

    @property
    def good_stats(self) -> Tribe:
        return self.stats[self.player]

    @property
    def bad_stats(self) -> Tribe:
        return self.stats[self.not_player]

    def living(self):
        for i in range(self.no_peeps):
            if self.peeps[i].life > 0:
                yield i, self.peeps[i]

    # --------------------------------------------------- _zero_population
    def zero_population(self, i: int) -> None:
        """Tue le peep ``i`` (asm $421F4, lignes 5645‑5720)."""
        p = self.peeps[i]
        tribe = p.tribe
        p.life = 0

        if p.state == ST_BATTLE:                       # 0x08 : l'adversaire s'en sort
            opp = self.peeps[p.w6]
            opp.state &= 0xF7                          # ANDI #$F7 => clear bit 3

        if p.state & ST_VILLAGER:                      # il rase son village
            self.set_town(p, 1)

        if self.map.who[p.block] - 1 == i:
            self.map.who[p.block] = 0
        old = p.block - p.prev_block                   # ancienne case
        if 0 <= old < len(self.map.who) and self.map.who[old] - 1 == i:
            self.map.who[old] = 0

        pl = self.players[tribe]
        if pl.magnet - 1 == i:
            pl.magnet = 0
            self.set_magnet_to(tribe, p.block)

        if self.view_who - 1 == i:
            self.view_who = 0

    # ------------------------------------------------------- _check_life
    def check_life(self, tribe: int, block: int) -> int:
        """Score d'exploitabilité autour de ``block`` — `_check_life` (L20958-21042).

        Transcription integrale. Un point de structure etait faux avant cette
        version, et il pesait sur toute la croissance :

        **L'analyse de ``bk2`` (LAB_4DDE8) n'est atteinte que si
        ``valid_move == 0``.** Pour une case hors carte (``r == 1``) ou de
        l'eau (``r == 3``), l'asm saute directement a ``LAB_4DE2A``
        (L21018-21022 pour l'eau) sans jamais regarder ``bk2``. Nous
        analysions quand meme ``bk2``, ce qui faisait rendre ``0`` trop
        souvent : un villageois perdait son village, et le seuil de scission
        (``threshold = score``) baissait, donc il se scindait davantage.

        .. code-block:: none

            pour k dans 17 voisins :
                r = valid_move(case, offset[k])
                si r != 0 :
                    si r == 2 : score -= 15        # rocher
                    continuer                      # <- L21018-21022
                nb = case + offset[k]
                si blk[nb] == $1F+tribu ou blk[nb] == $0F :
                    si score == 0 : score = 50
                    score += 15
                elif k == 0 :
                    return 0                                    # LAB_4DDA
                # LAB_4DDE8 : analyse de bk2, uniquement pour r == 0
                d1 = bk2[nb]
                si k < 9 et bk2[case] == $2A et $29 <= d1 <= $2C :
                    all_of_city += 1
                elif k != 0 et $20 < d1 <= $2C :
                    return 0                        # enclavé par un bâtiment
            score = max(score, 0x23) ; 0x131 -> 0x0BEA
        """
        own = tribe + 0x1F
        map_blk, map_bk2 = self.map.blk, self.map.bk2
        score = 0
        # `_all_of_city` (L20965, CLR.W a l'entree) et `_a_flat_block`
        # (L20970, CLR.W a l'entree) sont des **globaux** : un retour
        # premature garde l'accumulation partielle. On ne peut donc pas
        # les passer en variables locales rendues par la fonction.
        self.all_of_city = 0
        self.a_flat_block = 0
        centre_bk2 = map_bk2[block]

        for k in range(N_NEIGHBOURS):
            off = OFFSET_VECTOR[k]
            r = self.map.valid_move(block, off)

            if r != 0:
                if r == 2:
                    # LAB_4DDAA : `ADDI.W #$fff1,D4`. D4 est un **mot**, il
                    # reboucle donc a zero s'il passe sous zero. Un score
                    # negatif, lu ensuite par `CMP.W #$0023 / BGE`, apparait
                    # alors tres grand : le villageois ne se scinde pas. En
                    # Python sans boucle, le resultat parait plausible et le
                    # verdict est oppose.
                    score = m68k.add_word(score, -0x0F)
                # r == 1 (hors carte) et r == 3 (eau) : on saute l analyse
                continue                     # LAB_4DE2A, sans lire bk2

            nb = block + off
            v = map_blk[nb]
            favorable = v == own                  # L20985-20986, BEQ LAB_4DDCC
            if not favorable and v == BLK_FLAT:
                favorable = True                  # L20987-20989
                # L20989 `MOVE.W #$0001,_a_flat_block` : une case **libre
                # et a plat** est adjacente au village. Ce global est lu
                # ensuite par `_make_level` (L3785) et par la remise en
                # place du village (L4042).
                self.a_flat_block = 1
            if not favorable and k == 0:
                return 0                     # LAB_4DDA : centre non constructible
            if favorable:
                if m68k.test_word_eq_zero(score):
                    score = 0x32            # 50 a la premiere case favorable
                score = m68k.add_word(score, 0x0F)    # +15 par case

            d1 = map_bk2[nb]
            if k < 9 and centre_bk2 == 0x2A and 0x29 <= d1 <= 0x2C:
                self.all_of_city += 1             # L21014 ADDI.W #1,_all_of_city
            elif k != 0 and 0x20 < d1 <= 0x2C:
                return 0                     # LAB_4DE1E : enclave par un batiment

        if not m68k.cmp_word_ge(score, 0x23):     # CMP.W #$0023 / BGE
            score = 0
        if m68k.to_word(score) == 0x131:         # CMP.W #$0131 / BNE
            score = 0x0BEA                   # 305 -> 3050 : grande ville
        return m68k.to_word(score)

    # --------------------------------------------------------- _set_town
    def set_town(self, p: Peep, grow: int) -> None:
        """Construit (``grow=0``) ou rase (``grow=1``) le village — asm L5866-6062.

        Transcription integrale de `_set_town` ($4243C). Le test d'entree est
        ``TST.W ($C,A5) / BEQ.L LAB_42528`` : **grow == 0 tombe dans la
        construction**, grow != 0 dans la demolition.

        Deux boucles par branche, toujours les memes Neighbor() :

        * **demolition** — 25 cases si `bk2[b] == $2A` (grande ville), sinon
          17 ; les 9 premieres.voisins sont mis a zero dans ``bk2``, et
          ``blk`` retombe a ``$0F`` la ou il vautait `$1F + tribu`` ;
        * **construction** — 25 cases si ``frame == $2A`` (les 9 premiers
          voisins recoivent `_big_city[k]`), 17 sinon. Les 9 premiers voisins
          sont **mis a zero** dans ``bk2`` — l'asm fait `CLR.B`, il n'ecrit
          aucun sprite — et ``blk`` passe a `$1F + tribu`` la ou il vautait
          ``$0F``. Enfin le centre recoit ``bk2[b] = peep[13]`` si
          ``blk[b] == $1F + tribu``.
        """
        b = p.block
        own = p.tribe + 0x1F
        blk, bk2 = self.map.blk, self.map.bk2
        vm = self.map.valid_move

        if grow:                                           # LAB_4246E
            if bk2[b] == 0x2A:                            # 25 cases
                for k in range(N_BIG_NEIGHBOURS):
                    off = OFFSET_VECTOR[k]
                    if vm(b, off) == 1:
                        continue
                    nb = b + off
                    bk2[nb] = 0
                    if blk[nb] == own:
                        blk[nb] = BLK_FLAT
            else:                                          # 17 cases
                for k in range(N_NEIGHBOURS):
                    off = OFFSET_VECTOR[k]
                    if vm(b, off) == 1:
                        continue
                    nb = b + off
                    if k < 9:
                        bk2[nb] = 0
                    if blk[nb] == own:
                        blk[nb] = BLK_FLAT
                bk2[b] = 0                                # LAB_42518-42520
            return

        if p.frame == FRAME_TOWN:                         # LAB_42528
            for k in range(N_BIG_NEIGHBOURS):             # grande ville
                off = OFFSET_VECTOR[k]
                if vm(b, off) == 1:
                    continue
                nb = b + off
                if k < 9:
                    bk2[nb] = BIG_CITY[k]
                if blk[nb] == BLK_FLAT:
                    blk[nb] = own
        else:
            if bk2[b] == 0x2A:                            # LAB_425A6 : 25 cases
                for k in range(N_BIG_NEIGHBOURS):
                    off = OFFSET_VECTOR[k]
                    if vm(b, off) == 1:
                        continue
                    nb = b + off
                    bk2[nb] = 0
                    if blk[nb] == own:
                        blk[nb] = BLK_FLAT
            for k in range(N_NEIGHBOURS):                 # LAB_42600 : 17
                off = OFFSET_VECTOR[k]
                if vm(b, off) == 1:
                    continue
                nb = b + off
                if k < 9:
                    bk2[nb] = 0                          # `CLR.B`
                if blk[nb] == BLK_FLAT:
                    blk[nb] = own
            if blk[b] == own:                              # LAB_42650-4267C
                bk2[b] = p.frame >> 8                     # `MOVE.B ($D,A0)`

    # ------------------------------------------------------ _place_people
    def place_people(self, tribe: int, block: int, magnet: int) -> int | None:
        """``_place_people`` (L6982-7087, asm $43164) : cree un peep.

        Renvoie **son index**, ou ``None`` quand la table est pleine.
        *Ecart de contrat* : l'asm rend le ``D0`` de l'``_set_frame`` de fin
        (L7086) - un booleen 0/1 - et non l'index ; le port garde l'index,
        dont se servent ``_settle_peoples`` et ``tools/check_makelevel.py``.

        Les ecritures suivent l'ordre du listing :

        =========  ========================================================
        L6984-88   garde ``_no_peeps < 0xD0`` (``MAX_PEEPS`` = 208)
        L6990-13   si ``magnet`` et ``_magnet[tribu] != 0`` : l'ancien
                   aimante est tue (``_zero_population``) et son slot reutilise
        L7019-22   ``w6 = 0``
        L7023-26   ``life = $002D`` (45)
        L7027-33   ``block``
        L7034-41   ``_map_who[block] = j + 1``
        L7042-45   ``tribe``
        L7046-49   ``state = 2`` - ``ST_EXPLORER``
        L7050-53   ``frame = $00FF``
        L7054-57   ``offspring = 1``
        L7058-61   ``prev_block = 0``
        L7062-65   ``weapons = 1``
        L7066-69   ``target`` : ``CLR.L`` ecrit **0**, le port ecrit **-1**
                   (indice de peep vs pointeur) - ecart de convention deja
                   declare
        L7070-78   si ``magnet`` : ``_magnet[tribu] = j + 1``
        L7080-86   ``_set_frame(peep)``
        =========  ========================================================

        ``spawn_block`` et ``make_level_res`` ne sont **pas** ecrits par
        ``_place_people`` dans le listing ; le port les reinitialise quand
        meme (un slot recycle garderait des valeurs obsoletes). Ecart
        declare, compte a part par ``tools/check_place.py``.
        """
        if self.no_peeps >= MAX_PEEPS:                   # L6984-6988
            return None
        if magnet:                                       # L6990 `TST.W ($E,A5)`
            idx = self.players[tribe].magnet             # L6998-7003
            if idx != 0:
                j = idx - 1                              # l'ancien aimante est tue
                self.zero_population(j)                  # L7011
            else:
                j = None                                 # LAB_431BE
        else:
            j = None
        if j is None:
            j = self.no_peeps                            # LAB_431BE
            self.no_peeps += 1

        p = self.peeps[j]
        p.w6 = 0                                         # L7019-7022
        p.life = 0x2D                                    # L7023-7026
        p.block = block                                  # L7027-7033
        self.map.who[block] = j + 1                      # L7034-7041
        p.tribe = tribe                                  # L7042-7045
        p.state = ST_EXPLORER                            # L7046-7049
        p.frame = 0x00FF                                 # L7050-7053
        p.offspring = 1                                  # L7054-7057
        p.prev_block = 0                                 # L7058-7061
        p.weapons = 1                                    # L7062-7065
        p.target = -1                                    # L7066-7069 ($0 en asm)
        p.spawn_block = block                            # hors listing (declare)
        p.make_level_res = 0                             # hors listing (declare)
        if magnet:                                       # L7070-7078
            self.players[tribe].magnet = j + 1
        self.set_frame(p)                                # L7080-7086
        return j

    # ------------------------------------------------------ _set_magnet_to
    def set_magnet_to(self, tribe: int, block: int) -> None:
        """`_set_magnet_to(tribu, case)` — asm L8271-8291.

        Transcription integrale :

        .. code-block:: none

            if _pause: return                     # TST.W (_pause,A4) / BEQ
            LAB_52DE6[tribu*16] = case            # struct joueur, offset +2
            if tribu == 0: _god_magnet    = case  # A4+$ae78
            else:         _devil_magnet  = case  # A4+$ae76

        L'asm ecrit donc dans le **struct joueur** (base ``_magnet``,
        A4+$99f6), champ +2 — et non dans ``_stats``. Les deux globales
        ``_god_magnet`` / ``_devil_magnet`` n'en sont que des miroirs, ce que
        confirme le chargement de partie (L17605-17606).
        """
        if self.pause:
            return
        self.players[tribe].magnet_to = block
        if tribe == 0:
            self.god_magnet = block
        else:
            self.devil_magnet = block

    # --------------------------------------------------------- _set_frame
    def set_frame(self, p: Peep) -> int:
        """Anime un peep (asm $422D2, décodée intégralement).

        Renvoie **1** quand l'animation est terminée (le peep a « fini » son
        déplacement ou son action), **0** sinon. La valeur de retour pilote
        toute la boucle de ``_move_peeps``.
        """
        if p.life == 0:
            return 0

        s = p.state
        if s == ST_EXPLORER:                       # exactement $02
            old = p.frame
            p.frame = (old + 1) & 0xFFFF
            if old >= 7:                           # un pas toutes les 8 images
                p.frame = 0
                return 1
            return 0

        if s & ST_DROWNING:                        # noyade : 0x5D..0x60
            p.frame += 1
            if 0x5D <= p.frame <= 0x60:
                return 0
            p.frame = 0x5D
            return 1

        if s & ST_BATTLE:                          # bataille : plage autour de D4
            opp = self.peeps[p.w6]
            if p.target >= 0 and opp.target >= 0:
                d4 = 0x8A
            elif p.target >= 0:
                d4 = 0x82 if p.tribe == 0 else 0x86
            elif opp.target >= 0:
                d4 = 0x82 if opp.tribe == 0 else 0x86
            else:
                d4 = 0x46
            p.frame += 1
            if d4 <= p.frame < d4 + 3:
                return 0
            p.frame = d4
            return 1

        if s == ST_VILLAGER:                       # exactement $01
            score = self.check_life(p.tribe, p.block)
            if score >= 0x0BEA:
                p.frame = FRAME_TOWN
            else:
                p.frame = 0x20 + score * 10 // 0x131
            return 0

        if s & ST_ANIM:                            # animation générale 0x55..0x57
            p.frame += 1
            if 0x55 <= p.frame <= 0x57:
                return 0
            p.frame = 0x55
            return 1

        if s & 0x60:                               # « occupé » 0x65..0x66
            p.frame += 1
            if 0x65 <= p.frame <= 0x66:
                return 0
            p.frame = 0x65
            return 1

        return 0                                   # LAB_42436

    # --------------------------------------------------------- _do_battle
    def do_battle(self, atk_idx: int) -> None:
        """Un coup d'échange entre ``atk`` et son adversaire (asm $4268A).

        Corrigé par lecture directe : les **deux** combattants encaissent,
        sur la base de ``min(roll_atk, roll_opp)``.
        """
        atk = self.peeps[atk_idx]
        opp_idx = atk.w6
        opp = self.peeps[opp_idx]

        # L6084-6091 puis L6094-6101 : les DEUX jets sont bastis sur `a`,
        # c'est-a-dire `&peeps[A->w6]` — **l'adversaire** — et sur sa vie
        # a chaque fois. Pas une vie par combattant.
        jet1 = (self.rng.below(3) + 1) * opp.life
        jet2 = (self.rng.below(3) + 1) * opp.life

        # L6102-6104 : `CMP.L jet2,D1 / BLE LAB_4275E`. Les deux branches
        # n'emploient **que le plus petit** des deux jets : le if/else est
        # un simple selecteur de minimum, pas une dissymetrie.
        low = jet2 if jet1 > jet2 else jet1

        # L6108-6130 puis L6146-6158 : le degat est
        #     armes * (vie / 100) + 10
        # et il est **soustrait par `SUB.W`** : seul le mot bas de D0 est
        # ecrit dans un champ mot. La vie reboucle donc a 0x10000.
        opp.life = m68k.add_word(opp.life,
                                 -(atk.weapons * (low // 100) + 10))
        atk.life = m68k.add_word(atk.life,
                                 -(opp.weapons * (low // 100) + 10))

        self.set_frame(atk)
        self.set_frame(opp)

        # L6167-6171 : le test de mort est `TST.W (4,A0) / BGT`. `TST.W`
        # teste le bit 15 : une vie reboulee sous zero vaut `0xFFxx`, et
        # `BGT` ne passe **pas** -> elle est comptee comme morte. Un `<= 0`
        # en Python la verrait vivante : c'est l'ecart que le reboulement
        # revele.
        atk_dead = not m68k.cmp_word_gt(atk.life, 0)
        opp_dead = not m68k.cmp_word_gt(opp.life, 0)
        if atk_dead:
            self.zero_population(atk_idx)
        if opp_dead:
            self.zero_population(opp_idx)
        if atk_dead and not opp_dead:
            self.battle_over(opp_idx, atk_idx)
        elif opp_dead and not atk_dead:
            self.battle_over(atk_idx, opp_idx)

    # ------------------------------------------------------- _battle_over
    def battle_over(self, winner: int, loser: int) -> None:
        """Fin de bataille : mana, ruines, destruction du village (asm $4283A)."""
        w, l = self.peeps[winner], self.peeps[loser]
        self.battle_won[w.tribe] += 1

        age = l.frame - FRAME_AGE
        table = self.land.battle_add1
        gain = table[age] if 0 <= age < len(table) else 100
        pl = self.players[w.tribe]
        pl.mana = max(pl.mana + gain, MANA_VALUES[0])

        n = N_BIG_NEIGHBOURS if l.frame == FRAME_TOWN else N_NEIGHBOURS
        blk, bk2 = self.map.blk, self.map.bk2
        for k in range(n):
            off = OFFSET_VECTOR[k]
            if self.map.valid_move(l.block, off) == 1:
                continue
            nb = l.block + off
            blk[nb] = 0x42                              # ruines
            bk2[nb] = (bk2[nb] + 0x15) & 0xFF

    # ----------------------------------------------------- _join_forces
    def join_forces(self, src_idx: int, dst_idx: int) -> None:
        """Fusionne deux peeps de même tribu (asm ligne 5540)."""
        s, d = self.peeps[src_idx], self.peeps[dst_idx]
        d.life = min(d.life + s.life, 0x7D00)
        self.players[d.tribe].magnet = self.players[s.tribe].magnet
        d.weapons = max(d.weapons, s.weapons)
        s.life = 0
        if self.map.who[s.block] == src_idx + 1:
            self.map.who[s.block] = 0

    # ------------------------------------------------------------ _set_battle
    def set_battle(self, a_idx: int, b_idx: int) -> None:
        """Lie les deux combattants (asm $42CBA, lignes 6590‑6592)."""
        a, b = self.peeps[a_idx], self.peeps[b_idx]
        a.state |= ST_BATTLE
        b.state |= ST_BATTLE
        a.w6 = b_idx
        b.w6 = a_idx

    # ------------------------------------------------------------- gestion
    def count_peeps(self, tribe: int) -> int:
        return sum(1 for _, p in self.living() if p.tribe == tribe)

    def population(self, tribe: int) -> int:
        """``good_pop`` = somme des vies (asm 3472‑3474)."""
        return sum(p.life for _, p in self.living() if p.tribe == tribe)

    # -------------------------------------------------------- _move_peeps
    def target_peep(self, i: int) -> Peep | None:
        """``A0 = peeps[0x0E]`` : le peep vise par le peep ``i``.

        Dans l'asm, ``peeps[0x0E]`` est un **pointeur** ; chez nous c'est un
        indice. La correspondance est exacte, et l'arbitrage de la Phase 28
        (garder l'indice) tient grace a trois faits :

        * il n'y a que **quatre** ecritures de ``0x0E`` dans tout le listing
          (L5480, L5527, L19874, L19885) ;
        * aucune ne depend de la position : un pointeur ne « suit » donc pas
          un deplacement, et un indice non plus ;
        * les 22 octets d'un peep ne bougent jamais sur la memoire, donc un
          pointeur ne pendille pas davantage qu'un indice — et nous
          remettons ``target`` a -1 dans ``zero_population`` et a la naissance.

        Les trois etats du champ, tous representables :

        ==================  =========  ===================================
        asm                  ici         sens
        ==================  =========  ===================================
        ``0`` (pointeur nul) ``-1``      suit l'aimant (L4912)
        ``le peep lui-meme`` son indice   **arrive** (L5480)
        un autre peep        son indice   s'y dirige
        ==================  =========  ===================================

        L'auto-reference est le sentinelle « arrive » : L5480 ecrit
        ``MOVE.L A2,($E,A2)``, puis L4916 compare ``cible->block`` a
        ``peep->block``. Les deux sont le meme, donc le test passe et la
        routine calcule un cap plutot que de suivre un gradient.
        """
        t = self.peeps[i].target
        return self.peeps[t] if 0 <= t < MAX_PEEPS else None

    def get_heading(self, i: int) -> None:
        """``_get_heading`` (L5469-5536) : la cible devient l'ennemi le plus proche.

        Transcription integrale. Recherche de **distance de Manhattan** sur
        tous les peeps, avec trois exclusions :

        .. code-block:: none

            L5486: MOVE.B (1,A2),D0 / CMP.B (1,A3),D0 / BEQ -> meme tribu
            L5489: TST.W (4,A3)        / BLE -> vie nulle
            L5493: BTST #7,(A3)        / BNE -> etat bit 7

        Et surtout **l auto-reference par defaut** :

        .. code-block:: none

            L5480: MOVE.L A2,($E,A2)     ; la cible c'est moi-meme
            L5527: MOVE.L A3,($E,A2)     ; puis l'ennemi le plus proche

        Ce n'est donc pas une marqueuse « arrive » : c'est la valeur de
        depart, et elle subsiste quand aucun ennemi n est eligible. Le champ
        ``target`` de la Phase 29 se revele avoir deux lectures superposees,
        et l asm les melange — ce qui est coherent avec le code mort du bloc
        ``act = 4`` trouve en Phase 26.

        La borne ``$270F`` (9999) est l'initiale de ``best`` ; comme la
        distance maximale d une carte 64x56 vaut au plus 118, elle n'est
        jamais atteinte — c'est un simple grand infini.
        """
        p = self.peeps[i]
        best = 0x270F
        x = p.block & 0x3F
        y = p.block >> 6
        p.target = i                                 # L5480
        for j in range(self.no_peeps):
            q = self.peeps[j]
            if q.tribe == p.tribe:
                continue                             # L5486-5488
            if q.life <= 0:
                continue                             # L5489-5490
            if q.state & 0x80:
                continue                             # L5493-5494
            d = abs((q.block & 0x3F) - x) + abs((q.block >> 6) - y)
            if d < best:                             # L5523 CMP.W / BGE
                best = d
                p.target = j                         # L5527

    def _blk_at(self, block: int) -> int:
        """``_map_blk[block]`` comme le 68000 le lit, hors-tableau compris.

        Le listing indexe ``_map_blk`` avec un mot 16 bits et **sans
        garantie** : a L5336, juste apres un ``valid_move`` non nul, la case
        voisine peut etre hors de la carte. Sur le materiel, la lecture
        deborde simplement sur la table suivante — ``_map_bk2`` dans notre
        disposition, qui commence par des zeros.

        On rend donc 0 hors-tableau, ce qui est le comportement dominant du
        materiel pour une table de ce type, et on le note plutot que de
        faire planter le port.
        """
        blk = self.map.blk
        return blk[block] if 0 <= block < len(blk) else 0

    def move_magnet_peeps(self, i: int, arg2: int) -> int:
        """``_move_magnet_peeps`` (L4905-5465) : un pas de magnetisme.

        **Transcription integrale.** Le mecanisme n'est pas un vecteur : la
        routine calcule un gradient en ``sign``, l'indexe dans une grille
        3x3, et **selectionne une direction dans une table**.

        .. code-block:: none

            L5220: MOVE.W (-6,A5),D0      dx = sign(cible_x - moi_x)
            L5221: ADDQ.W #1,D0
            L5222: MULS   #$0003,D0
            L5223: ADD.W  (-8,A5),D0     + dy = sign(cible_y - moi_y)
            L5224: ADDQ.W #1,D0         i = (dx+1)*3 + dy + 1  -> 0..8
            L5227: LEA    (_to_delta,A4) / MOVE.W -> le DELTA
            L5232: LEA    (_to_offset,A4) / _to_offset est indexe par le delta

        Les trois tables sont relues dans les **octets** du DAD et
        concordent avec le listing : ``TO_DELTA`` (9 mots), ``TO_OFFSET``
        (8, dans l'ordre N NE E SE S SO O NO) et ``OPPOSITE``. Le centre
        ``i = 4`` vaut le delta 0, c'est-a-dire **N** : quand le gradient
        est nul, on va au nord.

        Renvoie l'offset du pas effectue, ``$03E7`` (999) si aucune des huit
        directions ne passe, et 0 dans les cas de sortie directe.
        """
        p = self.peeps[i]
        tribe = p.tribe
        pl = self.players[tribe]
        st = self.stats[tribe]

        # ---- L4912 : y a-t-il une cible designee ? -------------------------
        if p.target != -1:                                  # TST.L ($E,A2)
            j = p.target
            tgt = self.peeps[j] if 0 <= j < MAX_PEEPS else None
            if tgt is not None and tgt.block != p.block:     # L4916 CMP / BEQ
                # L4919-4929 : trois conditions pour NE PAS rechercher
                if not (tgt.life > 0
                        and tgt.tribe != tribe
                        and not (tgt.state & 0x80)):
                    self.get_heading(i)                      # LAB_41A26
            else:
                self.get_heading(i)                          # LAB_41A26
            if tgt is None:
                return 0
            vers = tgt.block                                  # L4936 (8,A0)

        # ---- LAB_41A9E : pas de cible, on suit l'aimant -----------------
        else:
            if pl.magnet != 0:                                # L4987 / BNE
                # LAB_41B9C : le magnet designe-t-il un peep ?
                j = pl.magnet - 1
                if j != arg2:                                 # L5087 / BNE
                    # LAB_41C5E : vers la case du peep vise par le magnet
                    if not (0 <= j < MAX_PEEPS):
                        return 0
                    vers = self.peeps[j].block                # LAB_5301C
                else:
                    vers = pl.magnet_to                       # LAB_52DE6
            else:
                # LAB_41AF4 : vers la case visee par l'aimant du joueur
                if pl.magnet_to == p.block:                   # L4994 / BNE
                    # le peep vient d arriver : il est converti
                    pl.magnet = arg2 + 1                      # L5000-5002
                    if getattr(self, "view_who", 0) == 0:     # L5003-5007
                        self.view_who = arg2 + 1
                    p.tribe = 0xFF if (tribe & 0x80) else 0  # L5009
                vers = pl.magnet_to                           # L5011

        # ---- L4935-4980 / L5011-5218 : le gradient en sign ---------------
        dx = (1 if (vers & 0x3F) - (p.block & 0x3F) > 0 else 0) - \
             (1 if (vers & 0x3F) - (p.block & 0x3F) < 0 else 0)
        dy = (1 if (vers >> 6) - (p.block >> 6) > 0 else 0) - \
             (1 if (vers >> 6) - (p.block >> 6) < 0 else 0)

        # ---- LAB_41CF6 : la grille 3x3, puis la table --------------------
        idx = (dx + 1) * 3 + dy + 1                           # L5219-5224
        delta = TO_DELTA[idx]                                 # L5228
        off = TO_OFFSET[delta]                                # L5233
        r = self.map.valid_move(p.block, off)                 # L5235

        if r == 0:
            # L5239-5249 : avec une cible, la case voisine ne doit pas etre
            # du type $35 -- certaines cases interdisent le pas meme quand
            # valid_move dit oui.
            if p.target != -1 and \
                    self._blk_at(p.block + off) == 0x35:
                r = 0x35                                      # force LAB_41D7A
            else:
                p.face = 0xFF if (off & 0xFFFF) & 0x8000 else 0x00   # L5256
                return off

        # ---- LAB_41D7A -----------------------------------------------------
        if r == 2 and self.war:                              # L5264-5266
            p.face = 0xFF if (off & 0xFFFF) & 0x8000 else 0x00        # L5274
            return off

        # LAB_41DA2 : la ia demande a creuser, si elle y est autorisee
        if st.can_build == 1 or self.war:                     # L5283-5286
            if not (self.flags & 0x04 and self.war):         # L5288-5291
                if r == 3:                                   # L5293
                    st.act = 1                                # L5300
                    st.p1 = p.block & 0x3F                    # L5301-5310
                    st.p2 = p.block >> 6                      # L5311-5320
                    st.queued = 1                             # L5326
                elif self._blk_at(p.block + off) == 0x35 \
                        and not (self.flags & 0x08) \
                        and not self.war:                    # L5336-5341
                    st.act = 1
                    cible = (p.block + off) & 0xFFFF
                    st.p1 = cible & 0x3F                      # L5354-5362
                    st.p2 = cible >> 6                        # L5369-5377
                    st.queued = 1                             # L5383

        # ---- LAB_41F06 : echappatoire, on essaie les huit directions ------
        d4 = m68k.s16(idx - 1)                                # L5385-5386, en signe
        trouve = 0
        while trouve < 8:                                    # L5449-5450
            if d4 < 0:
                d4 = 7                                       # L5391-5392
            elif d4 > 7:
                d4 = 0                                       # L5394-5396
            o = TO_OFFSET[d4]
            if self.map.valid_move(p.block, o) == 0:          # L5404-5407
                # L5408-5416 : on ne repete pas. `p.face` relu par `EXT.W`
                # vaut 0 ou -1, et `_to_offset` vaut -65..65 : seul -1, la
                # direction O, peut matcher. Le controle est bien plus
                # etroit que son nom ne le dit.
                if m68k.s16(p.face) == (o & 0xFFFF):
                    trouve += 1
                    d4 += 1
                    continue
                if p.target != -1 and \
                        self._blk_at(p.block + o) == 0x35:
                    trouve += 1
                    d4 += 1
                    continue
                # LAB_41F7A
                p.face = 0xFF if (TO_OFFSET[OPPOSITE[d4]] & 0xFFFF) & 0x8000 \
                    else 0x00                                # L5437
                return TO_OFFSET[d4]                         # L5443
            trouve += 1                                      # L5446-5447
            d4 += 1

        # LAB_41FE2 : aucune direction ne passe
        p.face = 0xFF if (TO_OFFSET[OPPOSITE[d4 & 7]] & 0xFFFF) & 0x8000 else 0
        return 0x03E7                                        # L5462

    def move_peeps(self) -> None:
        """Un tour de simulation (asm $4059A)."""
        self.game_turn += 1
        self.toggle ^= 1

        # (b) réinitialisations par tribu
        for t in (0, 1):
            pl, st = self.players[t], self.stats[t]
            pl.town_count = 0
            pl.pop = 0
            if self.toggle:
                # L3308 : `ADDQ.W #1,(LAB_52DF0)+tribu*16` -- le champ est un
                # LONG, l'addition reboucle donc a 0x100000000.
                pl.mana = m68k.add_long(pl.mana, 1)
            # L3313/3317/3321 : `CLR.L` des trois pointeurs de `_stats`.
            # Ils ne sont lus qu'a la fin du tour, par `_devil_effect` et
            # `_set_devil_magnet` ; nul = aucun peep repere, donc -1 chez
            # nous (indice base 0), comme `p26` depuis la Phase 37.
            st.p2a = -1
            st.p26 = -1
            st.strongest = -1

        # (-24,A5) / (-28,A5) / (-36,A5) : les trois registres par tribu du
        # cadre de `_move_peeps`, remis a zero ici (L3335 / L3330 / L3341).
        # `0x4E1F` = 19999 est la valeur initiale du registre "plus jeune".
        vie_max = [0, 0]
        age_max = [0, 0]
        age_min = [0x4E1F, 0x4E1F]
        # (-32,A5), L3276-3289 : la « pression de construction », calculee
        # en tete de tour a partir des snapshots du **tour precedent** :
        #     (-32)[t] = good_castles[t] * 3 + good_towns[t]
        # `good_castles` = `_stats+0x14` = `st.castles`, `good_towns` =
        # `_stats+0x16` = `st.towns` ; les deux ne sont ecrits qu'en fin
        # de tour (L4362 / L4370). Lu une seule fois, par `_make_level`
        # a L3806 (`CMPI.W #$0003 / BGE`).
        pressure = [self.stats[t].castles * 3 + self.stats[t].towns
                    for t in (0, 1)]
        # `(-40,A5)` (L3325-3326, `CLR.W`) : compteur de « grandes
        # villes » par tribu, incremente a L3643-3644 quand `score >=
        # $0BEA`. Il n'est lu nulle part dans le tour : c'est lui qui
        # alimente `st.castles` en fin de tour (L4366-4370).
        big_town = [0, 0]

        # (c) compacter les peeps morts en fin de tableau
        while self.no_peeps > 0 and self.peeps[self.no_peeps - 1].life <= 0:
            self.no_peeps -= 1

        # (e) guerre globale (L3426-3432) : c'est `magnet_to` qui vaut
        # 0x0820 (le centre de la carte) - `LAB_52DE6` / `LAB_52DF6` et
        # les deux miroirs `_god_magnet` / `_devil_magnet`. `magnet`
        # (l'indice du peep vise) n'est pas touche.
        if self.war:
            for pl in self.players:
                pl.magnet_to = 0x0820

        # (f) boucle principale
        for i in range(self.no_peeps):
            p = self.peeps[i]

            # L15968-15981, en tete de la boucle par peep :
            #
            #     MOVE.B (0,A2),D6 / ANDI.W #$00f8,D6
            #     ...
            #     CMPI.W #$00d1,(A7)+ / BGE LAB_49C38
            #     OR.W  D6,_ok_to_build
            #
            # Le drapeau est **cumulatif** : mis a zero une seule fois, a
            # l'initialisation (L613 `CLR.W`), et jamais efface ensuite.
            # Le seul test qui nous interesse est `TST.W / BNE` : il suffit
            # qu'un seul peep porte son etat hors des huit bits bas.
            #
            # `CMPI.W #$00d1,(A7)+` ecarte les index >= 210 ; nos peeps
            # s'arretent a 208 (`no_peeps` = 0xD0), donc rien n'est ecarte.
            self.ok_to_build |= p.state & 0xF8
            # `TST.W ($12,A2) / BEQ LAB_49C2C` : le champ `t12` n'est ecrit
            # nulle part dans le listing, il reste nul, et le `ORI.W #$0001`
            # de L15977 n'est donc jamais execute. Le bit 0 n'entre pas ici.

            if p.life <= 0:
                continue

            # somme des vies
            self.players[p.tribe].pop += p.life

            tile = self.map.blk[p.block]

            # (g)/(h) — le seul cas d'usure de ``2 * walk_death`` est la noyade
            if p.state & ST_DROWNING:
                if self.flags & 0x01:                 # LAB_518A7 bit0 : tue dans l'eau
                    self.zero_population(i)
                    continue
                st = self.stats[p.tribe]
                if (st.can_build == 1 and not (self.flags & 0x04)) or self.war:
                    st.act = 1                        # l'IA émet un relèvement
                    st.p1 = p.block & 0x3F
                    st.p2 = p.block >> 6
                    st.queued = 1
                p.life -= 2 * self.land.walk_death
                if p.life <= 0:
                    self.zero_population(i)
                    continue
                if tile != 0:
                    p.state &= ~ST_DROWNING & 0xFF    # il est ressorti de l'eau
                    self.set_frame(p)
                else:
                    continue                          # il se noie encore ce tour
            elif tile == 0:
                # LAB_40994 : sur l'eau alors qu'il n'est pas encore noyé
                if p.state & ST_VILLAGER:
                    self.set_town(p, 1)
                p.state = 0x12                        # noyade | explorateur
                if p.frame >= 8:
                    p.frame = 0

            if p.state & ST_ANIM:
                if self.set_frame(p) != 0:
                    p.state &= ~ST_ANIM & 0xFF
                    self.set_frame(p)
                continue

            # villageois
            if p.state == ST_VILLAGER:
                score = self.check_life(p.tribe, p.block)
                if score <= 0 or p.target >= 0 or self.war:
                    p.state = (p.state & ~ST_VILLAGER) | ST_EXPLORER
                    p.frame = 0
                    p.prev_block = 0
                    self.set_town(p, 1)
                    continue

                old_frame = p.frame
                if score >= 0x0BEA:
                    p.frame = FRAME_TOWN                    # 42 grande ville
                    big_town[p.tribe] += 1                  # L3642-3644
                else:
                    p.frame = FRAME_AGE + score * 10 // 0x131
                    self.players[p.tribe].town_count += 1
                if self.map.who[p.block] == 0:
                    self.map.who[p.block] = i + 1

                # L3679-3763 : les trois registres de la tribu. Trois
                # extrema, chacun range dans la fiche de l'**autre** tribu
                # (`D0 = 1 - peep.tribe`, L3694-3701) : ce que lit
                # `_set_devil_magnet` est donc l'ennemi le plus fort, le
                # plus vieux et le plus jeune.
                k = p.tribe
                age = (self.game_turn - p.w6) & 0xFFFF    # L3711-3712, MOT
                if vie_max[k] < score:                     # L3685 BGE (signe)
                    vie_max[k] = score
                    self.stats[1 - k].strongest = i        # L3703
                if not age_max[k] > age:                   # L3714 BHI (non signe)
                    age_max[k] = age
                    self.stats[1 - k].p26 = i              # L3735
                if not age_min[k] <= age:                  # L3746 BLS (non signe)
                    age_min[k] = age
                    self.stats[1 - k].p2a = i              # L3763

                # L3766-3817 : `_make_level`, la porte d'entree du
                # villageois. Trois garde-fous, dans l'ordre du listing :
                #
                #   L3766-3772  `stats[tribe].queued != 0`  -> tout sauter
                #   L3774-3777  `_map_alt[block] == 0` ? non -> LAB_40C84
                #   L3778-3786  aucun des trois motifs -> tout sauter
                #
                # `old_frame` est `(-46,A5)` : le **cadre d'avant** la mise
                # a jour de L3646-3655 (L3636). Il est copie avant, pas
                # apres — l'assembleur le range au meme endroit mais la
                # valeur lue a L3783 est celle d'avant.
                st = self.stats[p.tribe]
                if st.queued == 0:
                    if self.map.alt[p.block] == 0:          # TST.B _map_alt
                        if (p.make_level_res == 0
                                or p.frame != old_frame
                                or self.a_flat_block != 0):  # L3779/L3783/L3785
                            # L3794-3797 : le seul des trois appels dont le
                            # rendu soit range dans `peep+0x14`.
                            p.make_level_res = self.make_level(p.block,
                                                               p.tribe)
                    elif (pressure[p.tribe] < 3               # L3806, (-32,A5)
                          and self.game_turn > 0xFA):         # L3808-3809
                        # LAB_40C84 : resultat **jete**, +0x14 pas touche.
                        self.make_level(p.block, p.tribe)

                # tous les 8 tours : mana, armes, croissance, scission
                if (self.game_turn & 7) == 0:
                    self.grow_peep(i, p, score)
                if p.life <= 0:
                    self.zero_population(i)
                    continue

                # L4016-4036 : la pastille du village sur la mini-carte.
                # **Polarite inverse** des deux autres pastilles : ici
                # `TST.W _toggle / BNE -> sauter` (L4016-4017), donc le
                # village ne se dessine que quand `_toggle == 0`, tandis
                # que L4186 et L4221 font `BEQ`. L'alternance evite que
                # les deux sorts de pastilles s'effacent a mi-parcours.
                # La couleur vient de `stats[tribe].colour` (mot +0x20,
                # `LAB_516C4`), pas des 15/8 des units.
                if not self.toggle and (p.tribe == self.player
                                        or self.serial_off):
                    self.putpixel(p.block, self.stats[p.tribe].colour)

                # L4037-4053 : le village est **repose** (arg = 0) si
                # l'une des trois conditions tient ; sinon LAB_40FCE.
                if (p.frame != old_frame                     # L4040-4041
                        or self.a_flat_block != 0            # L4042-4043
                        or (p.frame == FRAME_TOWN             # L4045-4046
                            and self.all_of_city < 9)):       # L4047-4048
                    self.set_town(p, 0)
                continue

            # explorateur — branche exacte de ``_move_peeps`` (asm L4058‑4212)
            if p.state == ST_EXPLORER:
                if p.life <= 0:
                    continue
                if self.set_frame(p) != 0:
                    if self.map.blk[p.block] == BLK_SWAMP:
                        self.zero_population(i)
                        self.effect = 0x42
                        self.map.blk[p.block] = BLK_FLAT    # si !bit1(LAB_518A7)
                        continue
                    st = self.stats[1 - p.tribe]
                    if st.p26 < 0:
                        st.p26 = i                          # cible ennemie repérée
                    if self.stats[p.tribe].queued == 0:
                        self.one_block_flat(p.tribe, p.block)
                    self.move_explorer(i, p)
                    if p.spawn_block != 0 and (p.block - p.prev_block) != p.spawn_block:
                        p.spawn_block = 0
                    p.life -= self.land.walk_death
                if p.life <= 0:
                    self.zero_population(i)
                    continue
                other = self.map.who[p.block] - 1
                if other != i and 0 <= other < MAX_PEEPS:
                    o = self.peeps[other]
                    if o.spawn_block == 0 and not (o.state & ST_DROWNING):
                        o.state |= 0x20                     # « occupé »
                        o.spawn_block = 101
                        o.w6 = 0
                if self.toggle and (p.tribe == self.player or self.serial_off):
                    self.putpixel(p.block, 15 if p.tribe == 0 else 8)
                continue

            # peep « occupé » (bit 5 = 0x20 ou bit 6 = 0x40) — asm L411C0‑4267
            if p.state & 0x60:
                self.set_frame(p)
                if self.toggle and (p.tribe == self.player or self.serial_off):
                    self.putpixel(p.block, 15 if p.tribe == 0 else 8)
                p.life -= self.land.walk_death
                if p.life <= 0:
                    self.zero_population(i)
                    continue
                old = p.w6
                p.w6 += 1
                if old > 14:
                    p.state &= 0x9F
                    self.set_frame(p)
                    if p.state == ST_EXPLORER:
                        self.move_explorer(i, p)
                        if p.life <= 0:
                            self.zero_population(i)
                continue

            # bataille en cours (asm L4269+)
            if p.state & ST_BATTLE:
                self.do_battle(i)

        # L4353-4373 : les deux snapshots de fin de tour. `good_towns`
        # reçoit le compteur de villes simples et `good_castles` celui
        # des grandes villes ; ce sont les champs `+0x16` et `+0x14` de
        # `_stats`, relus au tour suivant (L3276-3289) pour fabriquer la
        # pression `3*castles + towns` lue par `_make_level`. Sans cette
        # copie, `st.towns + st.castles` — la condition de la decision
        # de ville de `_devil_effect` (L9611-9617) — reste nulle pour
        # toujours.
        for t in (0, 1):
            self.stats[t].towns = self.players[t].town_count   # L4361-4362
            self.stats[t].castles = big_town[t]                # L4366-4370

    # -------------------------------------------------- cycle des 8 tours
    def grow_peep(self, i: int, p: Peep, score: int) -> None:
        """Mana, armes, croissance et scission (asm lignes 3819‑4014)."""
        age = p.frame - FRAME_AGE
        if not (0 <= age <= 10):
            age = max(0, min(10, age))
        st = self.stats[p.tribe]
        pl = self.players[p.tribe]

        threshold = score
        if (p.frame == FRAME_TOWN and st.can_build == 1
                and p.life > 0x131 and st.queued == 0):
            threshold = 0x131
            st.queued = 1
        if self.cheat != 0 and p.tribe == self.cheat - 1:
            threshold = 0x32

        # L3876 : `ADD.L D1,(A0)` -- champ LONG
        pl.mana = m68k.add_long(pl.mana, self.land.mana_add[age])
        p.weapons = self.land.weapons_add[age]

        if p.life > threshold:
            j = self.find_free_slot()
            if j is not None:
                child = self.peeps[j]
                half = threshold // 2
                child.life = p.life - half
                p.life = half
                if self.players[p.tribe].magnet - 1 == i:
                    self.players[p.tribe].magnet = j + 1
                if self.view_who - 1 == i:
                    self.view_who = j + 1
                child.offspring = p.offspring
                child.block = p.block
                child.state = ST_EXPLORER
                child.tribe = p.tribe
                child.prev_block = 0
                child.frame = 0
                child.weapons = p.weapons
                child.target = -1
                child.spawn_block = p.block
                child.make_level_res = 0
                child.w6 = 0
                self.map.who[child.block] = j + 1
                if p.offspring < 4:
                    p.offspring += 1
            else:
                if not self.funny_done:           # L3998-4006 : table pleine
                    self.funny_done = 1
                    # L4003 ne pousse qu'UN mot : ($A,A5) n'est pas fourni
                    self.do_place_funny(1, 0)

        # L4014 : `ADD.W D1,(4,A0)` -- champ MOT, reboucle a 0x10000.
        # C'est ce qui borne la vie a 16 bits sur le materiel.
        p.life = m68k.add_word(p.life, self.land.population_add[age])

    def find_free_slot(self) -> int | None:
        """Premier emplacement libre (``life <= 0``) ; met ``no_peeps`` à jour."""
        j = 0
        while j < MAX_PEEPS and self.peeps[j].life > 0:
            j += 1
        if j >= MAX_PEEPS:
            return None
        if j >= self.no_peeps:
            self.no_peeps = j + 1          # asm L3895‑3900
        return j

    def do_place_funny(self, code: int, arg2: int) -> None:
        """``_do_place_funny`` (L8862-9013) - le "peep drole" de la table.

        Deux appels par partie :

        * `_move_peeps` (L3998-4006), quand les 0xD0 emplacements sont tous
          pris au moment ou un peep veut se scinder - une seule fois,
          `funny_done` bannissant l'appel ensuite ;
        * `_main` (L752-759), sur l'image ou ``game_turn == $1000``.

        **Deux parametres, un seul argument.** ``(8,A5)`` = ``arg1`` et
        ``($A,A5)`` = ``arg2`` : le cadre ``LINK A5,#-18`` reserve bien 18
        octets de locaux (-18..-1), donc les deux mots positifs sont des
        arguments. Or les deux appels ne poussent qu'**un seul mot** (L757
        et L4003, nettoyes par ``ADDQ.W #2,A7``) : ``arg2`` lit un mot de
        pile de l'appelant, de valeur indeterminee, qui choisit la branche
        d'attribution de ``block`` (L8901-8970). Le port le rend
        **explicite** et le passe a 0 (decision de phase 56) : le peep
        tombe sur la derniere rangee.

        ``(-6,A5)`` et ``(-10,A5)`` (L8870-8885) recopient l'adresse des
        stats des deux joueurs - **jamais lus** ensuite (code mort).

        La boucle part de l index ``0xD1`` et **retourne des la premiere
        fiche vide remplie** (L9002) : un seul peep par appel. Borne haute
        ``0xD3`` (L9010) - les fiches 209 et 210 des 212.
        """
        if code > 2:                                   # L8864-8868
            return
        idx = 0xD1                                     # L8886
        while idx < 0xD3:                              # LAB_449BC L9009-9011
            p = self.peeps[idx]                        # (-18,A5)
            if p.life:                                 # L8895-8896
                idx += 1                               # LAB_449B0 L9006-9008
                continue
            p.life = 1                                 # L8898
            p.state = ST_EXPLORER                      # L8900 ($02)
            if arg2 == 0:                              # L8901
                # 4032 + ((newrand % 125) >> 1)  L8903-8912
                reste = self.rng.below(125)            # EXT.L/DIVS/SWAP
                p.block = m68k.to_word(0x0FC0 + m68k.asr_word(reste, 1))
            elif arg2 == 1:                            # L8915
                if self.rng.raw() & 1:                 # L8917-8919 BTST #0
                    # ((newrand % 43) + 20) << 6 + 63   L8920-8930
                    w = m68k.to_word(self.rng.below(43) + 0x0014)
                    p.block = m68k.to_word(m68k.asl_word(w, 6) + 0x003F)
                else:                                  # LAB_448C6 L8932
                    # ((newrand % 43) + 20) << 6 + 4032 L8933-8943
                    w = m68k.to_word(self.rng.below(43) + 0x0014)
                    p.block = m68k.to_word(m68k.asl_word(w, 6) + 0x0FC0)
            elif arg2 == 2:                            # L8947
                if self.rng.raw() & 1:                 # L8949-8951
                    # (newrand % 43) << 6               L8952-8960
                    p.block = m68k.asl_word(self.rng.below(43), 6)
                else:                                  # LAB_44918 L8962
                    p.block = self.rng.below(43)       # L8963-8970
            # arg2 ni 0, ni 1, ni 2 -> LAB_44930 : block non reassigne.
            # LAB_44930 (L8971) : map_who[p.block] = idx + 1
            # ECART : l'ecriture d'origine (L8977) n'a **aucune borne**.
            # La branche arg2==1/bit0==0 produit un block jusqu'a 8000 et
            # sortirait des 4096 cases ; elle est inatteignable (arg2 vaut
            # 0) mais on empeche l'ecriture de sortir du tableau.
            if 0 <= p.block < MAP_CELLS:
                self.map.who[p.block] = idx + 1        # L8972-8977
            prev, weapons, offspring = FUNNY[code]     # L8978-8992
            p.prev_block = m68k.s16(prev)              # L8982 MOVE.W
            p.offspring = offspring                    # L8987 octet +2
            p.weapons = weapons                        # L8992 octet +3
            p.face = 1                                 # L8994
            p.w6 = weapons                             # L8996-8999
            p.make_level_res = code & 0xFF             # L9001 (9,A5)
            return                                     # L9002 -> LAB_449C6

    # ---------------------------------------------------------- explorateur
    def move_explorer(self, i: int, p: Peep) -> None:
        """``_move_explorer(peep, i)`` (asm $413CA) — contrat d'emploi intégral.

        * un peep adverse/allié sur la case d'arrivée ⇒ ``_join_battle`` /
          ``_join_forces`` / ``_set_battle`` ;
        * sinon, si un déplacement est choisi ⇒ ``map_steps`` +1, ``map_who``
          marqué sur la case de départ, ``block += delta``,
          ``prev_block = delta`` ;
        * sinon (delta nul et pas de cible) ⇒ **il fonde le village** :
          ``state = 1``, ``w6 = game_turn``, ``set_frame``, ``set_town(0)``.
        """
        # L4401-4411 : le listing choisit entre l'aimant et la destination
        # directe, et **ne le fait pas** chez nous. En effet :
        #
        #     L4404: LEA    (LAB_52DE8,A4)   ; Player + 4
        #     L4405: TST.W  (0,A0,D0.L) / BEQ -> LAB_413F4  (l'aimant)
        #     L4408: TST.L  ($E,A0)    / BNE -> LAB_413F4  (cible designee)
        #     L4410: TST.W  (_war,A4)  / BEQ -> LAB_41408  (destination)
        #
        # `LAB_52DE8` est notre `Player.command`. Or les 17 sites du listing
        # qui le mentionnent sont tous des **lectures** (`TST.W`, `CMPI.W`),
        # faites pour choisir l icone a dessiner : c est un etat
        # d'**interface**, pose par les clics de la barre d'outils, et donc
        # non transcrit chez nous.
        #
        # Consequence : `command` reste a 0, et la premiere condition est
        # toujours vraie. Brancher tel quel enverrait **tous** les
        # explorateurs a l'aimant, au lieu de les laisser aller a leur
        # destination — ce qui serait moins fidele, pas plus.
        #
        # Il faut donc transcrire l'interface avant de brancher. C'est une
        # dependance explicite, pas une approximation.
        # L4401-4411 : le listing choisit entre l'aimant et la destination
        # directe :
        #
        #     L4404: LEA   (LAB_52DE8,A4)   ; Player + 4 = `command`
        #     L4405: TST.W (0,A0,D0.L) / BEQ -> LAB_413F4  (l'aimant)
        #     L4408: TST.L ($E,A0)    / BNE -> LAB_413F4  (cible designee)
        #     L4410: TST.W (_war,A4)  / BEQ -> LAB_41408  (destination)
        #
        # Trois conditions suffisent pour prendre l'aimant. Le point
        # decisif est l'initialisation : L1065 ecrit `command = 1` a la
        # creation d'une partie. Donc **par defaut on va a la destination**,
        # et l'aimant ne sert que si le joueur choisit l'outil aimant
        # (`command = 0`), s'il y a une cible designee, ou en guerre.
        #
        # Notre port mettait `command = 0`, ce qui inversait exactement le
        # defaut et envoie tous les explorateurs a l'aimant.
        pl = self.players[p.tribe]
        if pl.command == 0 or p.target != -1 or self.war:
            delta = self.move_magnet_peeps(i, i)
        else:
            delta = self.where_do_i_go(i, p)

        # L4426-4431 : le retour $03E7 (aucun des huit passages ne meninge)
        # est traite des que `move_magnet_peeps` sera branche.
        if delta == 0x03E7:
            p.state |= 0x40
            p.w6 = 7
            return

        # Un peep ne doit jamais s'arreter sur un rocher ni sur l'eau : la cible
        # de `where_do_i_go` est un sommet du terrain, pas une case, donc le
        # decalage peut tomber sur un rocher ($2F..$31) ou sur la mer.
        dest = p.block + delta
        if (0 <= dest < MAP_CELLS
                and self.map.blk[dest] in (BLK_ROCK, BLK_ROCK2, BLK_ROCK3,
                                           BLK_WATER)):
            delta = 0
            dest = p.block
            occ = -1
        else:
            occ = self.map.who[dest] - 1 if 0 <= dest < MAP_CELLS else -1
        if occ != -1 and occ != i and occ < MAX_PEEPS:
            other = self.peeps[occ]
            if other.life > 0 and not (other.state & 0x80):
                if other.state & ST_BATTLE:
                    self.join_battle(i, occ)
                    return
                if other.tribe == p.tribe:
                    self.join_forces(i, occ)
                    if p.life <= 0:
                        return
                else:
                    self.set_battle(i, occ)
                    return

        if p.life <= 0:
            return

        if delta != 0 or p.target >= 0:
            # --- déplacement : on libere la case qu'on quitte, on marque
            # celle qu'on rejoint (exactement le couple prev_block / who
            # de l'asm : sans ce nettoyage le peep laisse une trainee de
            # marqueurs qui pointent sur lui apres sa mort).
            self.map.set_step(p.block, (self.map.step(p.block) + 1) & 0xFFFF)
            if self.map.who[p.block] == i + 1:
                self.map.who[p.block] = 0
            p.block += delta
            p.prev_block = delta
            if self.map.who[p.block] == 0:
                self.map.who[p.block] = i + 1
        else:
            # --- il reste en place et fonde le village
            if self.map.who[p.block] == 0:
                self.map.who[p.block] = i + 1
            p.state = ST_VILLAGER
            p.w6 = self.game_turn
            self.set_frame(p)
            self.set_town(p, 0)


    # --------------------------------------------------------- _where_do_i_go
    def where_do_i_go(self, i: int, p: Peep) -> int:
        """``_where_do_i_go`` (L4622-4901) - decalage du prochain pas.

        **Transcription complete, ligne a ligne.** Neuf directions
        (L4637-4853) et, pour chacune, ``offspring`` cellules de regard : la
        boucle interieure tourne tant que ``offspring != d`` (L4844-4848), un
        peep neuf n examine donc que sa propre case et ses huit voisines
        (``_place_people`` ecrit ``1`` en +0x02, L7057).

        Cinq criteres remplissent cinq cases (score + decalage), ``5`` valant
        "jamais retenu" (valeur initiale, L4627-4635) :

        ======  ===========  =================================================
        slot    frame        critere
        ======  ===========  =================================================
        0       -22 / -32    ``_map_blk == $0F`` ; dehors ``check_life != 0``
                             (L4695) ou aucune ville a distance 2 (L4734)
        1       -20 / -30    occupant en bataille (``BTST #3``, L4765)
        2       -18 / -28    occupant d une autre tribu (L4780)
        3       -16 / -26    occupant explorateur (``BTST #1``, L4793)
        4       -14 / -24    ``_map_steps`` le plus court (L4818-4840)
        ======  ===========  =================================================

        Retour ``999`` ($03E7, L4900) : aucun critere n a retenu autre chose.
        L appelant (L4426-4431) met alors ``state |= 0x40`` et ``w6 = 7``, ce
        que ``move_peeps`` traduit par une pause de huit tours.
        """
        off_vec = OFFSET_VECTOR
        map_blk = self.map.blk
        map_bk2 = self.map.bk2
        map_who = self.map.who
        map_steps = self.map.steps
        valid_move = self.map.valid_move

        scores = [5, 5, 5, 5, 5]                 # (-22,A5) + 2*D5  L4627-4635
        results = [0, 0, 0, 0, 0]                # (-32,A5) + 2*D5
        best_steps = 0x270F                      # L4625 (-12,A5)
        d5 = -1                                  # L4636
        k = 0                                    # L4637

        while k != 9:                            # LAB_41944 (L4851)
            # --- LAB_416D2 : direction suivante --------------------------
            if d5 != 0 or k != 1:
                d5 += 1                          # LAB_416EC (L4649)
            else:
                d5 = (self.rng.raw() & 7) + 1    # L4644-4647, tirage unique
            if d5 == 9:
                d5 = 0                           # wrap 9 -> 0 (L4652-4654)
            block = p.block                      # L4657 (-10,A5)
            d = 0                                # L4658 (D4)

            while True:                          # LAB_41930 (L4843)
                if d == p.offspring:             # L4844-4848
                    break                        # -> LAB_41940
                off = off_vec[d5]
                if valid_move(block, off) != 0:
                    break                        # L4667-4671 -> LAB_41940
                block += off                     # L4677

                settled = False
                if map_blk[block] == BLK_FLAT and d < scores[0]:  # L4680-83
                    if d5 == 0:
                        # case courante : peut-on fonder ici ? (L4686-4697)
                        if self.check_life(p.tribe, block) != 0:
                            scores[0] = d
                            results[0] = 0       # CLR.W (-32,A5)
                            settled = True
                    else:
                        # aucun voisin a distance 2 n a de ville $21..$2C :
                        # on s installe sur la case atteinte (L4700-4740)
                        d6 = 9
                        ville = False
                        while True:              # LAB_41782 (L4702)
                            o6 = off_vec[d6]
                            if valid_move(block, o6) == 0:
                                v = map_bk2[block + o6]
                                if BK2_CITY[0] <= v <= BK2_CITY[1]:
                                    ville = True
                                    break        # LAB_417D6 (L4731)
                            d6 += 1              # LAB_417CE (L4727)
                            if d6 >= 17:
                                break
                        if not ville:            # D6 == 17 (L4732-4739)
                            scores[0] = d
                            results[0] = off
                            settled = True

                if not settled:
                    # --- LAB_417F4 : qui occupe la case ? ----------------
                    if d5 != 0:                  # L4742-4743
                        taken = False
                        w = map_who[block]
                        if w != 0 and w - 1 != i:        # L4746-4754
                            o = self.peeps[w - 1]        # (-6,A5) L4755-63
                            if (o.state & ST_BATTLE) and d < scores[1]:
                                scores[1] = d            # L4765-4774
                                results[1] = off
                                taken = True
                            if (not taken and o.tribe != p.tribe
                                    and d < scores[2]):
                                scores[2] = d            # L4779-4789
                                results[2] = off
                                taken = True
                            if (not taken and o.state & ST_EXPLORER
                                    and d < scores[3]):
                                scores[3] = d            # L4792-4802
                                results[3] = off
                                taken = True
                        if not taken:
                            # --- LAB_418BE : le chemin le plus court ------
                            if off != p.prev_block:      # L4810-4812
                                s = map_steps[block]     # L4813-4817
                                if s < best_steps or (
                                        s == best_steps and d < scores[4]):
                                    best_steps = s        # L4834
                                    scores[4] = d         # L4835
                                    results[4] = off      # L4840

                d += 1                          # LAB_4192E (L4841)
            k += 1                              # LAB_41940 (L4849)

        # --- selection finale (LAB_4195E-419C6) --------------------------
        cmd = self.players[p.tribe].command     # LAB_52DE8 = joueur + 4
        if cmd == 3 and scores[2] != 5:         # L4854-4862
            return results[2]
        if cmd == 2 and scores[3] != 5:         # L4868-4877
            return results[3]
        for slot in range(5):                   # LAB_419A0 (L4880)
            if scores[slot] != 5:
                return results[slot]
        return 0x03E7                           # L4900


    # ------------------------------------------------------- _make_level
    def make_level(self, block: int, tribe: int) -> int:
        """``_make_level`` (L9017-9144) : l'IA-emet une action de terrain.

        La routine arpente les **81 sommets** d'une fenetre 9x9 autour de
        ``block`` (table ``_a_flat``) et pose, pour la premiere case qui
        merite une correction, ``st.act``/``st.p1``/``st.p2`` puis
        ``st.queued = 1``. Elle rend 0 quand une action a ete posee, 1
        quand les 81 cases n'ont rien donne.

        .. code-block:: none

            si power_mask bit0 == 0 ou flags bit2 != 0 : return (L9026-9029)
            x = block & $3F ; y = block >> 6 ; centre = _alt[y*65+x]
            pour chaque (dx, dy) dans _a_flat (81 paires, L9049) :
                xx = x+dx ; yy = y+dy
                si xx ou yy hors [0, $40] : suivant          (L9062-9069)
                idx = yy*64 + xx  (mot)                       (L9070-9073)
                si map_blk[idx] == $2F et flags bit3 == 0 :
                    map_blk[idx] += 1      # rocher -> rocher2
                    act=2 ; p1=xx ; p2=yy ; queued=1 ; return 0
                delta = centre - _alt[yy*65+xx]  (mot)        (L9093-9102)
                si delta > 0 : act=1 ; queued=1 ; return 0    (L9103-9114)
                si delta < 0 :                                    -> lab_44b38
                si delta == 0 et (blk == $42 ou blk == $35) :       -> lab_44b38
                sinon : suivant                                   (L9118-9125)
                lab_44b38 : si flags bit3 : suivant (L9127-9128)
                    act=2 ; p1=xx ; p2=yy ; queued=1 ; return 0
            return 1                                             (L9143-9144)

        **L'ordre de ``_a_flat`` compte.** Les lignes de ``dx`` n'y vont
        pas de -4 a +4 : l'ordre du listing est ``-4, -3, +4, +3, -2,
        +2, -1, +1, 0`` et les colonnes de ``dy`` vont de -4 a +4. La
        routine revient sur la **premiere** paire qui satisfait un test :
        l'ordre decide donc laquelle des 81 cases ouvre le terrain.

        ``delta > 0`` signifie que le sommet du centre est **plus haut**
        que le voisin : on leve le voisin (``act = 1``). ``delta < 0`` :
        on le creuse (``act = 2``). A altitude egale, un ruine (``$42``)
        ou un marais (``$35``) merite aussi un ``act = 2``.
        """
        st = self.stats[tribe]

        # L9026-9029 : deux tests, un seul chemin d'entree.
        # `BTST #0,($F,A0)` lit l'octet a `st+0x0F` : sur un 68000
        # gros-boutiste c'est l'octet **bas** du mot `power_mask` (+0x0E),
        # donc `power_mask & 1`. `BTST #2,(LAB_518A7)` est le bit 2 de
        # `flags` — le « gelez l'IA ». L'un ou l'autre bloque -> RTS.
        if (st.power_mask & 0x0001) == 0 or (self.flags & 0x04):
            # D0 vaut alors `&stats[tribe]` (L9023) : le dispatch rend
            # 0xA4 / 0xD2 — octets bas de 0x516A4 / 0x516D2 au
            # chargement tetracorp — et jamais 0. Le seul lecteur est
            # `TST.B (peep+0x14)` (L3779) : seule la nullite compte,
            # 0xA4 et 0xD2 se comportent donc comme 1. ECART marque :
            # le port n'a pas d'adresse, on garde les octets du listing
            # plutot que de rendre 0, ce qui declencherait un rappel a
            # chaque tour.
            return 0xA4 if tribe == 0 else 0xD2

        x = block & 0x3F                                  # L9035-9037
        y = m68k.asr_word(block, 6)                       # L9038-9040
        terrain = self.terrain
        centre = m68k.to_word(terrain.vertex(x, y))       # L9041-9047

        # `_map_blk` ($56376, 4096 octets) est suivi dans le listing par
        # `_map_alt` ($57376). Les bornes de L9062-9069 laissent passer
        # xx == 64 ou yy == 64 : l'indice va alors jusqu'a 4160 et le
        # 68000 lit, ou ecrit, `_map_alt[idx-4096]`. Aucun test ne
        # compare l'indice a 4096.
        blk = self.map.blk
        alt_disp = self.map.alt                           # `_map_alt`

        def lu(idx: int) -> int:
            return blk[idx] if idx < MAP_CELLS else alt_disp[idx - MAP_CELLS]

        for dx, dy in A_FLAT:                             # L9049, D6 de 0 a $A2
            xx = x + dx
            yy = y + dy
            if xx < 0 or xx > 0x40 or yy < 0 or yy > 0x40:
                continue                                 # L9062-9069
            idx = m68k.to_word((yy << 6) + xx)            # L9070-9073
            v = lu(idx)                                   # L9074-9076

            if v == BLK_ROCK and not (self.flags & 0x08):  # L9076-9079
                # L9080-9082 `ADDQ.B #1` : le rocher monte d'un cran
                # (BLK_ROCK -> BLK_ROCK2) **avant** l'action, en
                # memoire, puis act=2 sur la meme case.
                if idx < MAP_CELLS:
                    blk[idx] = (blk[idx] + 1) & 0xFF
                else:
                    alt_disp[idx - MAP_CELLS] = \
                        (alt_disp[idx - MAP_CELLS] + 1) & 0xFF
                st.act = 2                                # L9084
                st.p1 = xx                                # L9086, MOVE.B D4
                st.p2 = yy                                # L9088, MOVE.B D5
                st.queued = 1                             # L9090
                return 0

            delta = m68k.s16(centre - m68k.to_word(
                terrain.vertex(xx, yy)))                  # L9093-9102
            if delta > 0:                                 # L9103-9104 BLE
                st.act = 1
                st.p1 = xx
                st.p2 = yy
                st.queued = 1
                return 0

            if delta < 0:                                 # L9116-9117 BLT
                pass
            elif v == BLK_RUINS or v == BLK_SWAMP:        # L9118-9125
                pass
            else:
                continue                                 # L9125 -> LAB_44B68

            if self.flags & 0x08:                         # L9127-9128
                continue                                 # -> LAB_44B68
            st.act = 2
            st.p1 = xx
            st.p2 = yy
            st.queued = 1
            return 0

        return 1                                          # L9143-9144

    def one_block_flat(self, tribe: int, block: int) -> None:
        """``_one_block_flat`` (L9148-9296) : l'IA-emet une action de terrain.

        **Transcription complete**, plus portee que le noop qui la
        remplacait. Les cinq portes d'entree, dans l'ordre du listing :

        .. code-block:: none

            TST.W  (8,A0)          / BNE          st.queued != 0  -> sortir
            CMPI.L #$14,(LAB_52DF0+t*16) / BLT   mana < 20        -> sortir
            CMPI.W #$32,(LAB_52DEA+t*16) / BGT   mot haut de pop  -> sortir
            BTST   #0,($F,A0)      / BEQ          -> sortir
            BTST   #2,LAB_518A7    / BEQ          -> sortir

        Deux lectures qui ne vont pas de soi :

        * ``BTST #0,($F,A0)`` lit le bit 0 de l'octet ``+0x0F``. Ce
          ``+0x0F`` est le **deuxieme** octet du mot ``+0x0E`` : le 68000
          est gros-boutiste, donc ``+0x0E`` = bits 15-8 et ``+0x0F`` = bits
          7-0. Le test porte donc sur ``power_mask & 0x0001``. *(Le
          commentaire initial affirmait « bit 8 », soit ``0x100`` : c'etait
          l'hypothese d'un ordre petit-boutiste. Elle est contredite par
          L9510-9511, qui lit le meme mot en entier par ``AND.W #$0050`` et
          qui, lui, etait juste : les deux ne peuvent pas coexister.)*

        * ``LAB_52DEA`` est le champ **+6** du joueur, c'est-a-dire
          ``town_count`` : le listing sort donc des que la tribu compte plus
          de ``$32`` villes. *(Une premiere lecture y voyait le mot haut de
          `pop` ; c'est faux — `good_pop` occupe +8 et `mana` +12.)*

        Ensuite la somme des quatre sommets de la case — en ``ADD.W``, donc
        rebouclante — puis la division. Et la legerie du listing :

        .. code-block:: none

            DIVS #$4,D0 / SWAP D0 / MOVE.W D0,(-6,A5)   -> (-6,A5) = RESTE
            DIVS #$4,D0 /         MOVE.W D0,(-8,A5)     -> (-8,A5) = QUOTIENT

        Apres le ``SWAP``, le mot bas de D0 n'est plus le quotient mais le
        **reste**. Donc ``(-6,A5)`` est ``s % 4`` et ``(-8,A5)`` est ``s // 4``.
        Le reste ne sert qu'a choisir entre deux intentions :

        =============  =========================================================
        reste          action
        =============  =========================================================
        3              poser un arbre : ``act = 1`` si l'altitude vaut le
                       quotient
        1              creuser : ``act = 2`` si l'altitude est **au-dessus**
                       du quotient et que ``LAB_518A7 & 8`` est nul
        0, 2           rien
        =============  =========================================================

        La double boucle porte sur les quatre cases voisines, mais le test
        d'altitude se fait toujours sur ``y * $41 + x`` — sur la case, pas
        sur le sommet.
        """
        st = self.stats[tribe]
        if st.queued:
            return                                    # L9157-9158
        pl = self.players[tribe]
        # L9163-9164 : `CMPI.L #$00000014,(LAB_52DF0+t*16) / BLT` —
        # comparaison **LONG** signee sur le champ `mana` (champ +12 du
        # joueur, LONG). `to_word` + `cmp_word_lt` tronquait le mot bas et
        # le relisait en signe : des que `mana & $FFFF >= 32768` — ou
        # vaut un petit multiple de 65536 — la routine sortait a tort et
        # l'explorateur cessait de sculpter le terrain.
        if m68k.s32(pl.mana) < 0x14:
            return                                    # L9159-9164
        if m68k.cmp_word_gt(pl.town_count, 0x32):     # L9165-9170, champ +6
            return
        if not (st.power_mask & 0x0001):               # L9172-9173, BTST #0
            return
        # L9174-9175 : `BTST #2,(LAB_518A7) / BEQ LAB_44BE2` - LAB_44BE2
        # est le corps : il ne s'execute que si le bit 2 est **nul**.
        if self.flags & 0x04:
            return

        alt = self.terrain.alt if self.terrain is not None else []
        n_alt = len(alt)

        def sommet(i: int) -> int:
            """Lecture de ``_alt`` ; hors-tableau, comme sur le 68000."""
            return alt[i] if 0 <= i < n_alt else 0

        x0 = block & 0x3F                              # L9181-9183
        y0 = (block >> 6) & 0x3F                      # L9184-9186, ASR.W #6

        # L9187-9218 : somme des quatre sommets, chaque `ADD.W` rebouclant.
        # L'offset passe par `EXT.L`, donc l'indice est en signe : une valeur
        # reboulee avec le bit 15 pose lit `_alt` **avant** le tableau. Aucun
        # modulo n'est ajouter ici -- ce serait notre invention.
        base = m68k.to_long_word(m68k.to_word(y0 * 0x41 + x0))
        s = sommet(base)
        s = m68k.add_word(s, sommet(base + 1))
        s = m68k.add_word(s, sommet(base + 0x42))
        s = m68k.add_word(s, sommet(base + 0x41))
        if s == 1:
            return                                    # L9219-9221
        q = m68k.divs_word(s, 4)                      # L9228-9231
        r = m68k.to_word(s - q * 4)                   # L9223-9227, apres SWAP

        for x in range(x0, x0 + 2):                   # D4, L9291-9295
            for y in range(y0, y0 + 2):               # D5, L9285-9289
                a = sommet(m68k.to_long_word(m68k.to_word(y * 0x41 + x)))
                if r == 3:                            # L9238-9257
                    if a == q:
                        st.act = 1
                        st.p1 = x
                        st.p2 = y
                        st.queued = 1
                        return
                elif r == 1:                          # L9260-9282
                    if m68k.cmp_word_gt(a, q) and not (self.flags & 0x08):
                        st.act = 2
                        st.p1 = x
                        st.p2 = y
                        st.queued = 1
                        return

    def putpixel(self, block: int, colour: int) -> None:
        """``_a_putpixel(block, colour)`` — pastille de la mini-carte."""
        cb = self.minimap_pixel
        if cb is not None:
            cb(block, colour)

    def join_battle(self, mover: int, occupant: int) -> None:
        """``_join_battle(src, dst)`` — asm L6663-6732, transcription integrale.

        L'asm appelle cette routine quand l'occupant a **le bit 3** de son etat
        pose (L4536 : `BTST #3,(A0)`), c'est-a-dire quand il est deja en
        combat. Contraryment a ce que son nom suggere, la routine ne declenche
        **aucun** combat : elle **fusionne** les deux fiches.

        .. code-block:: none

            if src.tribe != dst.tribe: dst = peeps[dst].w6   # re-indexation
            total = src.life + dst.life
            dst.life = 0x7D00 if total > 0x7D00 else total  # `CMP.L #$7D00`
            if magnet[src.tribe] - 1 == src: magnet[src.tribe] = dst + 1
            if _view_who - 1 == src:         _view_who      = dst + 1
            if dst > src:                    good_pop[src.tribe] -= src.life
            if src.target:                   dst.target     = src.target
            if src.weapons > dst.weapons:    dst.weapons    = src.weapons
            src.life = 0                                    # `CLR.W (4,A0)`

        Le champ `weapons` est l'octet +3 de la fiche, et `target` le long +14
        — voir :class:`Peep`.
        """
        ps = self.peeps[mover]
        if ps.tribe != self.peeps[occupant].tribe:
            # `MOVE.W (6,A0),($A,A5)` : l'index fourni peut etre perime
            occupant = self.peeps[occupant].w6
        pd = self.peeps[occupant]

        total = ps.life + pd.life
        pd.life = 0x7D00 if total > 0x7D00 else total       # CMPI.L #$7D00

        if self.players[ps.tribe].magnet - 1 == mover:
            self.players[ps.tribe].magnet = occupant + 1
        if self.view_who - 1 == mover:
            self.view_who = occupant + 1
        if occupant > mover:
            self.players[ps.tribe].pop -= ps.life

        if ps.target:                                       # TST.L ($E,A0)
            pd.target = ps.target
        if ps.weapons > pd.weapons:                         # CMP.B (3,A1) / BLS
            pd.weapons = ps.weapons
        ps.life = 0
