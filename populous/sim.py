"""Cœur de simulation de Populous — reconstitution des routines de ``_move_peeps``.

Références : ``docs/game_logic.md`` (lecture intégrale du désassemblage) et
``reference/tetracorp/populous_prg.asm``. Les passages marqués **[APPROX]** ne
sont plus « là où le désassemblage est coupé » — la Phase 12 a montré que le
listing est complet — mais ceux qui n'ont pas encore été transcrits ligne à
ligne : ce sont surtout des règles écrites de notre main — l'IA (dans
``powers.py``) et la marche d'exploration — qui n'ont pas de transcription
ASM équivalente.

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
    ACT_NONE, BIG_CITY, BLK_FLAT, BLK_ROCK, BLK_ROCK2, BLK_ROCK3, BLK_SWAMP,
    BLK_TRIBE0, BLK_WATER,
    FRAME_AGE, FRAME_TOWN, MANA_VALUES, MAP_CELLS, MAX_PEEPS,
    N_BIG_NEIGHBOURS, N_NEIGHBOURS, OFFSET_VECTOR, ST_DROWNING,
    offset_to_dx,
    ST_EXPLORER, ST_VILLAGER, ST_ANIM, ST_BATTLE,
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
        "make_level_res",
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

    def __init__(self) -> None:
        self.act = ACT_NONE     # +0x00 code d'action en attente
        self.p1 = 0             # +0x01 x
        self.p2 = 0             # +0x02 y / sous-commande
        self.can_build = 0      # +0x06 == 1 => emet des actions
        self.queued = 0         # +0x08 action deja en file
        self.threshold = 0      # +0x0C seuil (CMP #4)
        self.power_mask = 0     # +0x0E masque de pouvoirs (`tend` dans l'asm)
        self.tend = 0           # alias explicite du champ +0x0E
        self.period = 0         # +0x10 période des décisions IA
        self.t12 = 0            # +0x12
        self.castles = 0        # +0x14 châteaux
        self.towns = 0          # +0x16 villes
        self.t18 = self.t1a = self.t1c = self.t1e = 0
        self.colour = 0         # +0x20 couleur de la mini-carte
        self.strongest = -1     # +0x22 index du peep ennemi le plus fort
        self.p26 = -1           # +0x26 (0 = pointeur nul dans le jeu)
        self.p2a = 0            # +0x2A


class Player:
    """Fiche par joueur, 16 octets (``_magnet``, asm $52DE4)."""

    __slots__ = ("magnet", "magnet_to", "command", "town_count", "pop", "mana")

    def __init__(self) -> None:
        self.magnet = 0         # +0  index + 1 du peep aimanté (0 = aucun)
        self.magnet_to = 0x820  # +2  case visée par l'aimant (LAB_52DE6)
        self.command = 0        # +4  commande en attente
        self.town_count = 0     # +6  compteur « town » (remis à 0 par tour)
        self.pop = 0            # +8  somme des vies
        self.mana = 0           # +12 réserve de mana


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

        self.peeps: list[Peep] = [Peep() for _ in range(MAX_PEEPS)]
        self.no_peeps = 0
        self.stats = [Tribe(), Tribe()]
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
        self.flags = 0            # LAB_518A7 : bit0 tue dans l'eau, bit2 gèle l'IA
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
        self.ui_bits = 0          # bitfield_51645 : bit2 = "abaisser" arme,
                                   #                     bit3 = "relever" arme
        self.ok_to_build = 0      # _ok_to_build (L7307)
        self.cur_x = 0            # _cur_x : case sous la souris (_sculpt)
        self.cur_y = 0            # _cur_y
        self.cur_screen = None    # (x, y) du curseur dessine (sprite 0x54)
        self.tgt = [(0, 0), (0, 0)]    # LAB_516A5/6[player] : case visee
        self.tgt_dirty = False         # une cible vient d etre posee
        self.view_people = 0      # _view_people : village ouvert
        self._temp_view = 0       # _set_temp_view : survol temporaire
        self._temp_timer = 0      # _view_timer : 10 images de reaffichage
        # _weapons_order (asm L25460) : 11 mots, remplis a l'execution. L'asm
        # cherche (asm L2800-2811) l'indice i tel que weapons_order[i] ==
        # peep.weapons, i de 1 a 10 : c'est l'ordre d'affichage des armes dans
        # l'ecusson. On construit la table depuis ``weapons_add`` du terrain,
        # qui donne l'arme de chaque age (asm L3877-3882).
        self.weapons_order = [0] + list(self.land.weapons_add[1:11]) + [0xFFFF]
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
        all_of_city = 0
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
            if v == own or v == BLK_FLAT:
                if m68k.test_word_eq_zero(score):
                    score = 0x32            # 50 a la premiere case favorable
                score = m68k.add_word(score, 0x0F)    # +15 par case
            elif k == 0:
                return 0                     # LAB_4DDA : centre non constructible

            d1 = map_bk2[nb]
            if k < 9 and centre_bk2 == 0x2A and 0x29 <= d1 <= 0x2C:
                all_of_city += 1
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
        """Crée un peep (asm $43164). Renvoie son index, ou ``None``."""
        if self.no_peeps >= MAX_PEEPS:
            return None
        if magnet:
            idx = self.players[tribe].magnet
            if idx != 0:
                j = idx - 1                             # l'ancien aimanté est tué
                self.zero_population(j)
            else:
                j = None
        else:
            j = None
        if j is None:
            j = self.no_peeps
            self.no_peeps += 1

        p = self.peeps[j]
        p.tribe = tribe
        p.w6 = 0
        p.life = 0x2D                                    # 45
        p.block = block
        p.prev_block = 0
        p.state = ST_EXPLORER                           # 0x02
        p.offspring = 0
        p.weapons = 0
        p.target = -1
        p.frame = 0
        p.spawn_block = block
        p.make_level_res = 0
        self.map.who[block] = j + 1
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
            st.p2a = 0
            st.p26 = -1
            st.strongest = -1

        # (c) compacter les peeps morts en fin de tableau
        while self.no_peeps > 0 and self.peeps[self.no_peeps - 1].life <= 0:
            self.no_peeps -= 1

        # (e) guerre globale : tous les aimants valent 0x0820
        if self.war:
            for pl in self.players:
                pl.magnet = 0x0820

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
                else:
                    p.frame = FRAME_AGE + score * 10 // 0x131
                    self.players[p.tribe].town_count += 1
                if self.map.who[p.block] == 0:
                    self.map.who[p.block] = i + 1

                # tous les 8 tours : mana, armes, croissance, scission
                if (self.game_turn & 7) == 0:
                    self.grow_peep(i, p, score)
                if p.life <= 0:
                    self.zero_population(i)
                    continue

                if p.frame != old_frame:
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
                if not self.funny_done:                # table pleine : moment « drôle »
                    self.funny_done = 1
                    self.do_place_funny(1)

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

    def do_place_funny(self, code: int) -> None:
        """**[APPROX]** `_do_place_funny` — événement quand les 208 emplacements sont pris."""
        self.effect = 0x50 + (code & 0x0F)

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
        delta = self.where_do_i_go(i, p)

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
        """**[APPROX]** renvoie le décalage du prochain pas (0 = il s'installe).

        ``_where_do_i_go`` (asm $416A0) évalue les 8 directions avec
        ``_map_steps``, les cases libres et le champ de vision. Tant que la case
        courante offre de la place (``_check_life`` non nul) il choisit 0 et
        devient villageois ; sinon il part vers l'espace libre le plus proche.
        """
        if (self.map.blk[p.block] == BLK_FLAT
                and p.target < 0
                and self.check_life(p.tribe, p.block) > 0):
            return 0                      # il peut fonder ici : delta nul

        # Sinon il cherche. Les 8 voisins directs sont testes, puis, si aucun
        # n'est meilleur que la case courante, on fait un **court regard plus
        # loin** (rayon 2 et 3) pour trouver de la plaine constructible : sans
        # cela un explorateur peut tourner dans un coin sans jamais voir la
        # moindre `$0F`, alors que la logique `_where_do_i_go` (asm 416A0)
        # exige justement `$0F` pour s'installer.
        best = 0
        best_score = self._explore_score(p, 0, 0)
        offs = OFFSET_VECTOR[1:9]
        for off in offs:
            nb = p.block + off
            if not (0 <= nb < MAP_CELLS):
                continue
            v = self.map.valid_move(p.block, off)
            if v != 0:
                continue                  # hors carte, eau, rocher
            if self.map.blk[nb] in (BLK_ROCK, BLK_ROCK2, BLK_ROCK3, BLK_WATER):
                continue
            # un voisin deja fort sillonne decourage le detour
            score = self._explore_score(p, off, 0)
            if score > best_score:
                best_score, best = score, off
        if best != 0:
            return best
        # aucun voisin immediat prometteur : on part vers la plaine la plus
        # proche trouvee en rayon 2-3, en se dirigeant vers elle par le 1er pas
        # du chemin (les deux diagonales disponibles).
        target = self._find_flat_ahead(p)
        if target is not None:
            dx = (target & 63) - (p.block & 63)
            dy = (target >> 6) - (p.block >> 6)
            for off in offs:
                ox, oy = offset_to_dx(off), off // 64
                if ox == 0 and oy == 0:
                    continue
                if (dx == 0 or ox * dx > 0) and (dy == 0 or oy * dy > 0):
                    nb = p.block + off
                    if (0 <= nb < MAP_CELLS
                            and self.map.valid_move(p.block, off) == 0
                            and self.map.blk[nb] not in (BLK_ROCK, BLK_ROCK2,
                                                         BLK_ROCK3, BLK_WATER)):
                        return off
        return 0

    def _explore_score(self, p: Peep, off: int, depth: int) -> int:
        """Note une case voisine pour l'explorateur (plus haut = mieux)."""
        nb = p.block + off
        score = -self.map.step(nb) * 4      # evite les zones deja sillonnees
        if self.map.blk[nb] == BLK_FLAT:
            score += 2000
            if self.check_life(p.tribe, nb) > 0:
                score += 8000              # il peut y fonder une ville
        if depth:
            score -= depth * 64
        return score

    def _find_flat_ahead(self, p: Peep, radius: int = 3) -> int | None:
        """Cherche une case ``$0F`` constructible dans un rayon, et renvoie son
        index (ou ``None``). Guide l'explorateur vers de la vraie plaine."""
        best = None
        best_d = radius + 1
        bx, by = p.block & 63, p.block >> 6
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx == 0 and dy == 0:
                    continue
                xx, yy = bx + dx, by + dy
                if not (0 <= xx < 64 and 0 <= yy < 64):
                    continue
                nb = (yy << 6) | xx
                if self.map.blk[nb] != BLK_FLAT:
                    continue
                if self.check_life(p.tribe, nb) <= 0:
                    continue
                d = abs(dx) + abs(dy)
                if d < best_d:
                    best_d, best = d, nb
        return best

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

        * ``BTST #0,($F,A0)`` lit le bit 0 de l'**octet +0x0F**, c'est-a-dire
          le bit **8** du mot ``+0x0E`` — pas son bit 0. C'est le masque de
          pouvoirs ``power_mask & 0x100``.

        * ``LAB_52DEA`` n'est pas un champ : c'est le **mot haut de ``pop``**
          (long a +8). Il ne depasse donc jamais ``$32``, et cette porte est
          **inerte**. On l'ecrit quand meme, fidelement.

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
        if m68k.cmp_word_lt(m68k.to_word(pl.mana), 0x14):
            return                                    # L9159-9164
        if m68k.cmp_word_gt((pl.pop >> 16) & 0xFFFF, 0x32):
            return                                    # L9165-9170 (inerte)
        if not (st.power_mask & 0x100):               # L9172-9173
            return
        if not (self.flags & 0x04):                   # L9174-9175
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
