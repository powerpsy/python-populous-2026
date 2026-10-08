"""Mana, pouvoirs et IA — canal de commandes de Populous.

Tout transcrit de ``docs/game_logic.md`` §4 (relire l'asm, pas le divulguer) :

* une tribu n'appelle **jamais** un effet directement : elle ecrit
  ``(act, x, y)`` dans sa fiche ``_stats`` ;
* ``get_message()`` (L17707) est appele **en fin de tour**, lit les deux fiches
  et declenche le dispatch (§4.3) ;
* les **9 crans** de la jauge sont exactement les seuils de
  ``_mana_values`` (§4.1) et correspondent 1-pour-1 aux couts des pouvoirs :
  relever/abaisser, aimant, seisme, marais, chevalier, volcan, deluge, guerre.

Les points d'entree des 8 pouvoirs sont notes avec l'adresse de l'asm.
"""
from __future__ import annotations

import math

from . import m68k  # noqa: E402
from .constants import (
    ACT_ACTION, ACT_LOWER, ACT_MAGNET, ACT_NOP, ACT_QUAKE, ACT_RAISE,
    ACT_SWAMP, ACT_TREE, ACT_VOLCANO, BLK_FLAT, BLK_ROCK, BLK_ROCK2,
    BLK_ROCK3, BLK_SWAMP, BLK_TRIBE0, BLK_TRIBE1, BLK_WATER, BK2_TREE,
    COST_FLOOD, COST_KNIGHT, COST_MAGNET, COST_QUAKE, COST_RAISE, COST_SWAMP,
    COST_VOLCANO, COST_WAR, MAX_PEEPS, SUB_FLOOD,
    SUB_KNIGHT, SUB_WAR, TEND_X, TEND_Y,
)

MAX_OFF = 0x38                       # _xoff/_yoff bornes a 56


def _clamp_cell(v: int) -> int:
    """Clamp une coordonnee de case a [0, 63] comme l'asm (min avec 0x3F)."""
    return 0 if v < 0 else (0x3F if v > 0x3F else v)


class PowerEngine:
    """Execute les pouvoirs pour une partie (les deux Maharajas)."""

    def __init__(self, game) -> None:
        self.g = game                       # populous.game.Game
        self.last_tree = 0x32
        self.last_rock = BLK_ROCK

    # ------------------------------------------------------------------ mana
    def mana(self, tribe: int) -> int:
        return self.g.sim.players[tribe].mana

    def can_pay(self, tribe: int, cost: int) -> bool:
        return self.mana(tribe) >= cost

    # ------------------------------------------------------- points d'entree
    # Chaque methode reproduit le pouvoir tel que l'asm l'ecrit, verifie le
    # mana, le deduit, et renvoie True s'il a agi.

    def do_raise_point(self, tribe: int, x: int, y: int) -> bool:
        """**Relever** (L7187) — cout 10. Le plus courant."""
        if not self._pay(tribe, COST_RAISE):
            return False
        terr = self.g.terrain
        # l'asm eleve le sommet (x, y) ; les coordonnees de case (0..63) sont
        # acceptees telles quelles (le sommet (64,*) existe).
        terr.raise_point(_clamp_cell(x), _clamp_cell(y))
        self._remap()
        self.g.effect = 0x40 | (tribe & 1)
        return True

    def do_lower_point(self, tribe: int, x: int, y: int) -> bool:
        """**Abaisser** (L7208) — cout 10."""
        if not self._pay(tribe, COST_RAISE):
            return False
        terr = self.g.terrain
        terr.lower_point(_clamp_cell(x), _clamp_cell(y))
        self._remap()
        self.g.effect = 0x40 | (tribe & 1)
        return True

    def do_magnet(self, tribe: int, x: int, y: int) -> bool:
        """**Aimanter** (L6769) — cout 200. Il faut une cible, et pas de guerre."""
        sim = self.g.sim
        if self.g.sim.war:
            return False
        if sim.players[tribe].magnet == 0:
            return False
        if not self._pay(tribe, COST_MAGNET):
            return False
        sim.set_magnet_to(tribe, (_clamp_cell(y) << 6) | _clamp_cell(x))
        self.g.effect = 0x4D
        return True

    def do_quake(self, tribe: int, x: int, y: int) -> bool:
        """**Seisme** (L7863) — cout 2500. Zone 10x10, chaque case au hasard."""
        if not self._pay(tribe, COST_QUAKE):
            return False
        sim = self.g.sim
        rng = sim.rng
        cx, cy = _clamp_cell(x), _clamp_cell(y)
        for dy in range(-5, 5):
            for dx in range(-5, 5):
                xx, yy = cx + dx, cy + dy
                if not (0 <= xx <= 0x3F and 0 <= yy <= 0x3F):
                    continue
                b = (yy << 6) | xx
                if sim.map.blk[b] in (BLK_WATER,) or sim.map.blk[b] >= BLK_ROCK:
                    continue
                if rng.below(5) & 1:          # approx : 50/50 relerer/abaisser
                    self.g.terrain.raise_point(xx, yy)
                else:
                    self.g.terrain.lower_point(xx, yy)
        self._remap()
        self.g.effect = 0x47
        return True

    def do_swamp(self, tribe: int, x: int, y: int) -> bool:
        """**Marais** (L8295) — cout 5000. 30 essais sur une case libre."""
        if not self._pay(tribe, COST_SWAMP):
            return False
        sim = self.g.sim
        rng = sim.rng
        ok = (BLK_FLAT, BLK_TRIBE0, BLK_TRIBE1, 0x42)
        for _ in range(30):
            xx = _clamp_cell(rng.below(64)) + (rng.below(7) - 3)
            yy = _clamp_cell(rng.below(64)) + (rng.below(7) - 3)
            if not (0 <= xx < 64 and 0 <= yy < 64):
                continue
            b = (yy << 6) | xx
            if sim.map.blk[b] in ok and sim.map.who[b] == 0:
                sim.map.blk[b] = BLK_SWAMP
        self.g.effect = 0x48
        return True

    def do_knight(self, tribe: int, x: int, y: int) -> bool:
        """**Chevalier** (L8392) — cout 7500. Le peep vise devient fort."""
        sim = self.g.sim
        idx = sim.players[tribe].magnet - 1
        if not (0 <= idx < len(sim.peeps)) or sim.peeps[idx].life <= 0:
            return False
        if not self._pay(tribe, COST_KNIGHT):
            return False
        sim.peeps[idx].spawn_block = 1
        self.g.effect = 0x49
        return True

    def do_volcano(self, tribe: int, x: int, y: int) -> bool:
        """**Volcan** (L8046) — cout 10000. Cone de rayons 5..0."""
        if not self._pay(tribe, COST_VOLCANO):
            return False
        sim = self.g.sim
        cx, cy = _clamp_cell(x), _clamp_cell(y)
        for rad in range(5, -1, -1):
            for a in range(0, 8):
                xx = cx + int(rad * math.cos(a * math.pi / 4))
                yy = cy + int(rad * math.sin(a * math.pi / 4))
                if not (0 <= xx <= 0x3F and 0 <= yy <= 0x3F):
                    continue
                b = (yy << 6) | xx
                sim.map.blk[b] = BLK_ROCK
        self.g.effect = 0x4A
        return True

    def do_flood(self, tribe: int) -> bool:
        """**Deluge** (L7567) — cout 40000. Toute la carte plonge d'un cran.

        L'asm soustrait 1 aux **4225 altitudes de sommet** ; ``_mod_map`` en
        tire ensuite les altitudes de case et les types de terrain.
        """
        if not self._pay(tribe, COST_FLOOD):
            return False
        terr = self.g.terrain
        for i in range(len(terr.alt)):
            if terr.alt[i] > 0:
                terr.alt[i] -= 1
        self._remap()
        self.g.effect = 0x4B
        return True

    def do_war(self, tribe: int) -> bool:
        """**Guerre** (L8482) — cout 80000. Tout le monde entre en guerre."""
        if not self._pay(tribe, COST_WAR):
            return False
        sim = self.g.sim
        for p in sim.peeps:
            if p.life > 0:
                p.spawn_block = 0
        sim.war = 1
        for pl in sim.players:
            pl.magnet = 0x0820
        self.g.effect = 0x4C
        return True

    # ------------------------------------------------------------------ util
    def _remap(self) -> None:
        """Recalcule ``map_blk``/``map_alt`` depuis les sommets (``_mod_map``)."""
        self.g.terrain.mod_map(0, 0, 0x3F, 0x3F)

    def _pay(self, tribe: int, cost: int) -> bool:
        sim = self.g.sim
        # en guerre, le cout de relever/abaisser est ignore (game_logic §4.2)
        if sim.war and cost == COST_RAISE:
            return True
        if self.mana(tribe) < cost:
            return False
        sim.players[tribe].mana -= cost
        return True

    def place_tree(self, tribe: int, x: int, y: int) -> bool:
        """**Planter un arbre** (L18049) — gratuit. Fait tourner 32/33/34."""
        sim = self.g.sim
        b = (_clamp_cell(y) << 6) | _clamp_cell(x)
        if sim.map.alt[b] >= 7:
            return False
        cur = sim.map.bk2[b]
        if cur not in BK2_TREE:
            sim.map.bk2[b] = self.last_tree
        elif cur == 0x34:
            sim.map.bk2[b] = 0x32
        elif cur == 0x32:
            sim.map.bk2[b] = 0x33
        else:
            sim.map.bk2[b] = 0x34
            self.last_tree = 0x34
        return True

    def place_rock(self, tribe: int, x: int, y: int) -> bool:
        """**Poser un rocher** (L18086) — gratuit, fait tourner 2F/30/31."""
        sim = self.g.sim
        b = (_clamp_cell(y) << 6) | _clamp_cell(x)
        cur = sim.map.blk[b]
        if cur not in (BLK_ROCK, BLK_ROCK2, BLK_ROCK3):
            sim.map.blk[b] = self.last_rock
        elif cur == BLK_ROCK3:
            sim.map.blk[b] = BLK_ROCK
        elif cur == BLK_ROCK:
            sim.map.blk[b] = BLK_ROCK2
        else:
            sim.map.blk[b] = BLK_ROCK3
            self.last_rock = BLK_ROCK3
        return True

    # -------------------------------------------------------------- dispatch
    def do_queued(self, tribe: int) -> None:
        """Execute l'action en attente ``_stats[tribe]`` (table §4.3)."""
        st = self.g.sim.stats[tribe]
        self.dispatch(tribe, st.act, st.p1, st.p2)
        # L'action a ete consommee : la file est vide.
        st.act = ACT_NOP
        st.queued = 0

    def dispatch(self, tribe: int, act: int, x: int, y: int) -> bool:
        """Execute ``act`` sur la case ``(x, y)`` — dispatch unique du joueur.

        L'asm ecrit l'action dans ``_stats+2`` (la palette d'outils, voir
        LAB_3F670..LAB_3FB26) et la cible dans ``LAB_516A5/6`` (le clic sur la
        carte, voir ``_sculpt``) ; la boucle de messages fait ensuite le lien.
        On expose donc les deux moities separement. ``do_queued`` n'est plus
        qu'un appel de convenance pour l'IA, dont la cible est deja dans
        ``_stats+1/+2``.

        .. note::
           ``queued`` (offset ``+8``, ``LAB_516AC``) est **vide par
           `do_queued`**, une fois l'action consommee. Sans cela le drapeau
           restait a 1 indefiniment : or `grow_peep` (asm L3841) n'autorise une
           ville a se scinder que si ``queued == 0``. Le verrou etait donc
           pose pour de bon et **aucun habitant ne naissait plus** apres les
           premieres villes.
        """
        sim = self.g.sim
        st = sim.stats[tribe]
        if act == 0 or act == ACT_NOP:
            return False
        # les coordonnees sont clamp-ees avant le dispatch (L17722)
        x = _clamp_cell(x)
        y = _clamp_cell(y)

        ok = False
        if act == ACT_RAISE:
            ok = self.do_raise_point(tribe, x, y)
        elif act == ACT_LOWER:
            ok = self.do_lower_point(tribe, x, y)
        elif act == ACT_MAGNET:
            ok = self.do_magnet(tribe, x, y)
        elif act == ACT_QUAKE:
            ok = self.do_quake(tribe, x, y)
        elif act == ACT_SWAMP:
            ok = self.do_swamp(tribe, x, y)
        elif act == ACT_VOLCANO:
            ok = self.do_volcano(tribe, x, y)
        elif act == ACT_TREE:
            ok = self.place_tree(tribe, x, y)
        elif act == 12:                       # poser un rocher
            ok = self.place_rock(tribe, x, y)
        elif act == 13:                       # enlever
            self._remove(x, y)
            ok = True
        elif act == ACT_ACTION:
            # `_do_action` est appele par `_get_message` code 14 (L18185-18193),
            # avec `(_stats+1, _stats+2)` = `(_stats.p1, _stats.p2)` — donc
            # exactement `(x, y)` ici. C'est `do_action`, la transcription de
            # Phase 46/47/49, qui tourne : `_sub_action` (ecrit a la main)
            # a ete supprime en Phase 51, il s'ecartait du listing sur trois
            # points (voir PROGRESSION).
            self.do_action(tribe, x, y)
            ok = True
        # 7..10 : placer un peuple (place_people) — gere dans game.py

        # Libere l'action dans tous les cas : sinon une instruction que le
        # joueur n'a pas les moyens de payer resterait en attente indefiniment
        # et bloquerait l'IA (elle teste `act` avant de re-choisir).
        st.act = 0 if (ok and act != ACT_ACTION) else ACT_NOP
        return ok

    def _remove(self, x: int, y: int) -> None:
        """**Enlever** (L18123) : rocher->plat, puis tue l'occupant."""
        sim = self.g.sim
        b = (_clamp_cell(y) << 6) | _clamp_cell(x)
        if sim.map.blk[b] in (BLK_ROCK, BLK_ROCK2, BLK_ROCK3):
            sim.map.blk[b] = BLK_FLAT
            sim.map.bk2[b] = 0
        if sim.map.who[b]:
            sim.zero_population(sim.map.who[b] - 1)
            sim.map.who[b] = 0

    # `_sub_action` vivait ici : la version ecrite a la main des
    # sous-commandes de `_do_action`. Supprime en Phase 51 au profit de
    # `do_action`, la transcription du listing. Il s'en ecartait en trois
    # points, tous mesurables :
    #
    #   * codes 9/10 : `min(pl.mana * 2 + 500, 100000)` — le `min` n'existe
    #     pas dans le listing, qui fait `CMPI.L #$186A0 / BGE` : au-dela de
    #     100 000 la valeur est laissee telle quelle. 60 000 devait donner
    #     120 500, l'ecrit a la main donnait 100 000 ;
    #   * codes 9/10 : `// 2` tronque vers -inf sur un entier Python, la ou
    #     l'asm appelle `___divs`, qui est un `JMP _divs` (L24077), la
    #     division LONGUE signee de L23385 ;
    #   * code 12 : une boucle `blk = BLK_WATER` qui n'a aucun rapport avec
    #     `_clear_all_map` (L6926), lequel vide `alt`/`who`/`bk2`/`blk` en
    #     **0**, tue tous les peeps par `_zero_population` puis razie
    #     `_no_peeps`.
    #
    # Il retombait en no-op silencieux sur 1, 6, 11 et 15, la ou
    # `do_action` les traite — contraire a la regle de Phase 22 (un code
    # non transcrit doit lever, pas passer pour un no-op).

    # ------------------------------------------------------------------- IA
    # ------------------------------------------------ seuils de _devil_effect
    # Les six seuils sont des VARIABLES du listing, plus un delta fixe :
    #
    #     LAB_51894  80 000  + $3E7 = 80 999  tremblement
    #     LAB_51890  40 000  + $7CF = 41 999  inondation
    #     LAB_5188C  10 000  + $1F4 = 10 500  effet Vpc
    #     LAB_51888   7 500  + $1F4 =  8 000  aimant
    #     LAB_51880   5 000  + $1F4 =  5 500  attaque
    #     LAB_51884   2 500  + $1F4 =  3 000  effet Pc
    #
    # Les valeurs initiales sont exactement les entrees 4, 3, 5, 6, 7 et 8
    # de `_mana_values`. Les deltas sont separes : Conquest les modifie.
    TH_QUAKE = 80_000 + 0x3E7
    TH_FLOOD = 40_000 + 0x7CF
    TH_VPC = 10_000 + 0x1F4
    TH_MAGNET = 7_500 + 0x1F4
    TH_ATTACK = 5_000 + 0x1F4
    TH_PC = 2_500 + 0x1F4

    def devil_effect(self, tribe: int) -> None:
        """``_devil_effect`` (L9300-9522) : la decision majeure de l'IA.

        **Transcription**, et non interpretation. Quatre intentions, dans
        l'ordre exact du listing ; chacune rend la main si son seuil n'est
        pas franchi.

        ==============  ==========  =========================================
        bit du masque   action      condition
        ==============  ==========  =========================================
        0               `p2 = 3`    mana > 80 999 **et** la tribu domine
                                    `good_pop`
        15              `p2 = 4`    mana > 41 999 (inondation)
        13              `p2 = 5`    mana > 8 000 et la case visee par
                                    l'aimant est habitée (`life > $0BB8`)
        14              `act = 6`   mana > 10 500 et `p26 != 0`
        11              `act = 3`   mana > 5 500 et `p26` designe la case 1
        ==============  ==========  =========================================

        Trois blocs du listing sont morts, et c'est **mesuré** :

        * le bloc ``act = 4`` (L9476-9491) est inatteignable — les deux
          variables qui devraient differer recoivent la meme valeur ;
        * les tests ``t12`` contre ``t1a`` et ``t18`` (L9431-9441) ne filtrent
          rien : les deux branches convergent sur ``LAB_44FCA`` ;
        * le seuil ``$84`` et le bit 12 non plus : ``LAB_44FCA`` est atteint
          par les deux issues.

        Ils sont donc **absents** de cette transcription. Les remettre
        reviendrait a inventer un filtre que le listing n'applique pas.
        """
        sim = self.g.sim
        st = sim.stats[tribe]
        if st.queued:                                    # L9308-9309
            return
        pl = sim.players[tribe]
        mana = pl.mana
        m = st.power_mask

        # (1) BTST #0,(-6,A5) -> bit 0 du masque
        if m & 0x0001:                                   # L9316-9347
            if not mana > self.TH_QUAKE:
                return
            if not pl.pop > sim.players[sim.not_player].pop:
                return
            st.act = 0x0E
            st.p2 = 0x03
            st.queued = 1
            return

        # (2) BTST #7,(-5,A5) -> bit 15 du masque
        if m & 0x8000:                                   # L9349-9363
            if not mana > self.TH_FLOOD:
                return
            st.act = 0x0E
            st.p2 = 0x04
            st.queued = 1
            return

        # (3) BTST #5,(-5,A5) -> bit 13 du masque : l'aimant
        if m & 0x2000:                                   # L9365-9396
            j = pl.magnet - 1
            if pl.magnet == 0 or not (0 <= j < MAX_PEEPS):
                return
            if sim.peeps[j].life <= 0x0BB8:              # CMPI.W #$0BB8
                return
            if mana > self.TH_MAGNET:                   # L9387-9394
                st.act = 0x0E
                st.p2 = 0x05
                st.queued = 1
            return

        # (4) LAB_44E8C : les deux effets informatiques
        if st.p26 == 0:                                  # L9398-9399
            return
        if mana > self.TH_VPC and (m & 0x4000):          # L9404-9418
            st.act = 0x06
            self.do_computer_effect(tribe, st)
            st.queued = 1
            st.t12 = 0
            return
        # LAB_44FCA
        if mana > self.TH_ATTACK and (m & 0x0800):        # L9497-9506
            # L9507-9512 : `t12 >= t1a` ET `(masque & $50) != 0` -> on s'arrete
            if st.t12 >= st.t1a and (m & 0x0050):
                return
            st.act = 0x03                                # L9514
            self.do_computer_effect(tribe, st)
            st.queued = 1
            st.t12 += 1                                  # L9520

    def do_computer_effect(self, tribe: int, st) -> None:
        """``_do_computer_effect`` (L9526-9597) : ou poser l'effet.

        Deux chemins. Le rapide vise la case du **curseur du joueur**, et
        seulement si elle est occupee par un peep d'une autre tribu :

        .. code-block:: none

            L9532: TST.W _magnet[tribu]        / BNE  -> chemin lent
            L9538: D1 = magnet_to[tribu]
            L9541: occ = map_who[D1]          / BEQ  -> chemin lent
            L9551: si peeps[occ-1].tribe == tribu -> chemin lent
            L9558: st.p1 = magnet_to[tribu] & $3F
            L9566: st.p2 = magnet_to[tribu] >> 6

        Le chemin lent (L9572-9597) vise la case du peep designe par ``p26``,
        decalee de 3 en x et en y, et ramenee a zero si elle sort :

        .. code-block:: none

            L9576: x = (p26->block & $3F) - 3
            L9582: y = (p26->block >> 6)   - 3
            L9586: si x < 0 : x = 0
            L9589: si y < 0 : y = 0

        **Ecart assume** : ``p26`` est un *pointeur* dans l'asm, dont on lit
        le premier octet. Notre ``Tribe.p26`` est un indice, pas un pointeur,
        donc le test ``(p26)[0] == 1`` est rendu par ``p26 != 0``. C'est le
        seul endroit du port ou la representation nous empeche de lire ce que
        le listing lit.
        """
        sim = self.g.sim
        pl = sim.players[tribe]

        if pl.magnet == 0:                                # L9532-9533
            lent = True
        else:
            occ = sim.map.who[pl.magnet_to] if 0 <= pl.magnet_to < len(sim.map.who) else 0
            j = occ - 1
            if occ == 0 or not (0 <= j < MAX_PEEPS) or sim.peeps[j].tribe == tribe:
                lent = True                               # L9544 / L9552
            else:
                st.p1 = pl.magnet_to & 0x3F               # L9558-9560
                st.p2 = (pl.magnet_to >> 6) & 0xFF        # L9566-9568
                return
        if not lent:
            return
        # LAB_450B8 : chemin lent. `($26,A2)` est le champ +0x26 de la fiche
        # de tribu, donc `st.p26` -- et non celui du joueur.
        cible = st.p26
        bloc = sim.peeps[cible].block if 0 <= cible < MAX_PEEPS else 0
        x = (bloc & 0x3F) - 3                             # L9576-9577
        y = (bloc >> 6) - 3                               # L9582-9583
        if x < 0:
            x = 0                                         # L9586-9587
        if y < 0:
            y = 0                                         # L9589-9591
        st.p1 = x                                         # L9594
        st.p2 = y                                         # L9596

    def set_devil_magnet(self, tribe: int) -> None:
        """``_set_devil_magnet`` (L9601-9690) : le releve de terrain.

        .. code-block:: none

            D0 = stats->$16 (towns) + stats->$14 (castles)
            D1 = stats->$0C (threshold) * 2 + $0F
            si D0 >= D1 :
                D0 = _game_turn / 90          (DIVU #$5A)
                D1 = stats->$0C + $0A
                si D0 >= D1 : -> LAB_45196
        LAB_4515A:
            si command[tribu] == 0 :
                act = $0E ; p2 = 1 ; p1 = 1 + (newrand % 3) ; queued = 1

        La seconde branche (LAB_4516 onward) fait bouger l'aimant ; elle est
        la suite de la meme lecture, et n'est pas encore transcrite — d'ou le
        `[APPROX]` qu'on laisse ici plutot que d'ecrire un chemin devine.
        """
        sim = self.g.sim
        st = sim.stats[tribe]

        total = st.towns + st.castles                      # L9611-9612
        cible = st.threshold * 2 + 0x0F                   # L9613-9616
        # L9617 : `CMP.W D1,D0 / BLT LAB_4515A` — c est donc quand
        # total < cible qu on va droit a l'action, et non l'inverse.
        if total >= cible:                                 # chemin des tours
            tours = sim.game_turn // 0x5A                  # L9618-9623
            if tours >= st.threshold + 0x0A:               # BCC LAB_45196
                return                                     # LAB_45196, non lu
        # LAB_4515A : le releve de terrain
        if sim.players[tribe].command == 0:                # L9633-9634
            st.act = 0x0E                                  # L9635
            st.p2 = 0x01                                   # L9636
            st.p1 = 1 + sim.rng.below(3)                   # L9637-9642
            st.queued = 1                                  # L9643

    def do_action(self, tribe: int, arg2: int, code: int) -> None:
        """``_do_action`` (L18376-19004), **par morceaux**.

        `_do_action` fait 640 lignes mais n'est pas un monolithe : c'est une
        **table de saut de 16 codes** vers 14 handlers (L19007-19023), et la
        plupart sont independants. On les transcrit donc separement.

        .. code-block:: none

            CMP.L #$10,D0 / BCC LAB_4C168      ; code >= 16 -> defaut
            ASL.L #1,D0
            MOVE.W (LAB_4C16A,PC,D0.W),D0      ; table de 16 mots
            JMP (LAB_4C198+2,PC,D0.W)

        Voici la decomposition, avec la taille de chaque handler :

        ==========  =========================  ==============================
        code         handler                    etat ici
        ==========  =========================  ==============================
        0 et 14      defaut (renvoie 0)         fait
        1           `LAB_4B9EE` (23 l.)        **fait** — ecrit ``command``
        2           `LAB_4BA34` (172 l.)       non lu (messages serie)
        3           `LAB_4BC38` -> `_do_war`   **fait** — appelle `do_war`
        4           `LAB_4BC46` -> `_do_flood` **fait** — appelle `do_flood`
        5           `LAB_4BC54` -> `_do_knight` **fait** — appelle `do_knight`
        6           `LAB_4BC62` (16 l.)        **fait** — le bouton pause
        7           `LAB_4BC94` (122 l.)       non lu
        8           `LAB_4BE12` (214 l.)       non lu
        9           `LAB_4C0B8` (17 l.)        **fait** — mana du joueur
        10          `LAB_4C0EC` (17 l.)        **fait** — mana de l'adversaire
        11          `_rotate_all_map` (99 l.)   **fait** — pli max + arbres
        12          `LAB_4C124` -> `_clear_all_map` **fait** — vide tout
        13          `LAB_4C12A` -> `_load_ground`     non lu
        15          `LAB_4C15C` (5 l.)         **fait** — le tricheur
        ==========  =========================  ==============================

        Douze des seize codes sont ici (le defaut partage par 0 et 14
        compris) ; quatre — `2`, `7`, `8`, `13` — **lèvent** au lieu de
        retomber sur le defaut : un code non transcrit ne doit surtout pas
        passer pour un no-op, ce qui est exactement l'erreur que la Phase 22
        a reprochee. Le cas 12 merite d'etre raconte : `_sub_action`
        (supprime en Phase 51) y mettait une boucle `blk = BLK_WATER` de son
        cru, alors que `_clear_all_map` (L6926) vide `alt`/`who`/`bk2`/`blk`
        en **0**, tue les peeps par `_zero_population`, razie `_no_peeps`,
        puis rappelle `_make_map` et `_draw_map`. Mieux valait le transcrire
        que laisser tourner une invention.
        """
        sim = self.g.sim

        if code in (0, 14):                       # LAB_4C168 : defaut
            return
        if not 0 <= code <= 15:
            return

        if code == 1:                             # LAB_4B9EE
            # L18382-18401 : si c'est la tribu du joueur, on recale les
            # icones du bandeau ; puis, **pour toute tribu** :
            if tribe == sim.player:
                x = TEND_X[arg2] if 0 <= arg2 < len(TEND_X) else 0
                y = TEND_Y[arg2] if 0 <= arg2 < len(TEND_Y) else 0
                self.g.set_tend_icons(x, y)
            # L18426-18428 : `command[tribu] = arg2`. C'est la **seconde**
            # ecriture de ce champ dans le listing, avec L1065.
            sim.players[tribe].command = arg2
            return

        if code == 6:                             # LAB_4BC62
            # icone puis **bascule de la pause**, et on efface `_toggle`
            self.g.toggle_icon(1, 3, 0x17E4)
            sim.pause = 0 if sim.pause else 1       # L18598-18603
            sim.toggle = 0                       # L18605
            return

        if code in (9, 10):                       # LAB_4C0B8 / LAB_4C0EC
            # Le code 9 agit sur `LAB_52DF0` = joueur 0, le 10 sur
            # `LAB_52E00` = joueur 1. **Ce n'est pas indexe par la tribu.**
            pl = sim.players[0 if code == 9 else 1]
            if arg2:                                # L18944-18949
                # `MOVEQ #2,D1 / MOVE.L (mana),D0 / JSR ___divs /
                # MOVE.L D0,(mana)`. `___divs` est un `JMP _divs` (L24077),
                # c'est-à-dire la division **longue** signee de L23385 — et
                # non `DIVS.W`, qui aurait lu le mana comme un mot et l'aurait
                # tronque au dela de 32767.
                pl.mana = m68k.divs_long(pl.mana, 2)
            elif m68k.s32(pl.mana) < 0x186A0:      # 100 000
                # L18951-18953 : `MOVE.L (mana),D0 / ASL.L #1,D0 /
                # ADD.L #$000001F4,D0 / MOVE.L D0,(mana)` — **32 bits**.
                # `m68k.to_long_word` est un `EXT.L` (mot etendu en signe) :
                # l'employer ici ecrasait le mana a 16 bits avant de le
                # doubler, donc tronquait des que `mana > 32767`.
                pl.mana = m68k.add_long(m68k.s32(pl.mana << 1), 0x1F4)
            return

        if code == SUB_WAR:                       # LAB_4BC38
            # L18577-18580 : `MOVE.W (8,A5),-(A7) / JSR _do_war` — un seul
            # argument, la tribu.
            self.do_war(tribe)
            return

        if code == SUB_FLOOD:                     # LAB_4BC46
            # L18582-18585 : `JSR ___do_flood`, meme frame qu'au dessus.
            self.do_flood(tribe)
            return

        if code == SUB_KNIGHT:                    # LAB_4BC54
            # L18587-18590 : `JSR _do_knight`, la encore **un seul** argument
            # empile. `do_knight` prend `(tribe, x, y)` par compatibilite avec
            # l'autre chemin d'appel ; le corps n'en lit que le premier.
            self.do_knight(tribe, 0, 0)
            return

        if code == 11:                            # LAB_4C11E
            # `_rotate_all_map(0,0,63,63)` — un seul appel, sans argument
            # pertinent pour nous : `arg2` n'est pas lu dans ce handler.
            self.g.terrain.rotate_all_map()
            return

        if code == 12:                            # LAB_4C124
            # L18981-18983 : `JSR (___clear_all_map,A4)` — **aucun argument**
            # empile, contrairement aux codes 3/4/5.
            self.g.clear_all_map()
            return

        if code == 15:                            # LAB_4C15C
            sim.cheat = arg2 + 1                   # L19001-19002
            return

        non_transcrit = {
            3: "_do_war", 4: "do_flood", 5: "_do_knight",
            7: "LAB_4BC94", 8: "LAB_4BE12", 2: "LAB_4BA34",
            12: "_clear_all_map", 13: "_load_ground",
        }
        raise NotImplementedError(
            "_do_action code %d : handler %s non transcrit" % (code, non_transcrit[code]))

    def ai_choose(self, tribe: int) -> None:
        """``_set_devil_magnet`` puis ``_devil_effect`` (L3256-3259).

        .. code-block:: none

            for t in (0, 1):
                if stats[t].queued == 0: _set_devil_magnet(t)
                if stats[t].queued == 0: _devil_effect(t)

        **Plus aucune invention ici.** C'etait le dernier endroit du port ou
        la logique etait fabriquee : une heuristique « fable mais coherente »
        qui leve le terrain autour d'un village. Elle est **nuisible**, et
        c'est mesure (Phase 41) : sur 2 000 tours elle fait chuter la
        population de la seconde tribu de 10 064 a 917, et l'annihile
        completement sur une graine sur trois.

        Apres transcription, sur 9 000 tours : 161 398 / 207 643 / 184 298.

        ``_set_devil_magnet`` est appele **et n'est pas du code mort** — une
        premiere version de ce fichier le disait, sur la foi d'une recherche
        qui n'avait trouve qu'une seule ecriture de ``Player.command``. C'etait
        faux : il y en a **deux**, L1065 (initialisation) et **L18402**, dans
        ``_do_action`` — le handler du clic sur la barre d'outils, qui ecrit
        ``command[tribu] = arg2``. La recherche avait rate L18402 parce que
        son motif exigeait une source sans virgule, or l'operande source est
        ``($A,A5)``.

        Donc la routine se declenche bien des que la tribe a ``command = 0``,
        et le portillon du meme nom dans ``move_explorer`` peut se lever.
        Reste a transcrire ``_do_action`` pour que le joueur — et l'IA, si elle
        clique ses propres outils — pose ce champ.
        """
        sim = self.g.sim
        st = sim.stats[tribe]
        if st.queued:                        # asm L3256 : TST.W (8,A0) / BNE
            return
        self.set_devil_magnet(tribe)        # L3257 — inerte, cf. docstring
        if st.queued:
            return
        self.devil_effect(tribe)            # L3258

    def ai_choose_invented(self, tribe: int) -> None:
        """L'heuristique **avant** la Phase 42, conservee pour comparaison.

        Elle n'est plus appelee. On la garde parce qu'elle est la seule
        version dont on a **mesure le cout**, et que cette mesure est ce qui
        a justifie la transcription.
        """
        sim = self.g.sim
        st = sim.stats[tribe]
        if st.queued:
            return
        if st.act not in (0, ACT_NOP):
            return
        mana = self.mana(tribe)
        if mana < COST_RAISE:
            return
        target = None
        for _i, p in sim.living():
            if p.tribe == tribe and p.state == 1:
                target = p.block
                break
        if target is None:
            return
        cx, cy = target & 0x3F, target >> 6
        dx = cx + sim.rng.below(9) - 4
        dy = cy + sim.rng.below(9) - 4
        dx = _clamp_cell(dx)
        dy = _clamp_cell(dy)
        # On ne touche que des cases **libres et constructibles**, et jamais a
        # cote des autres tribus : poser un arbre ou un rocher sur la plaine
        # du voisin l'empeche de fonder (bloc $2F) et l'IA se prive elle-meme.
        enemy = sim.not_player if tribe == sim.player else sim.player
        blk, who = sim.map.blk, sim.map.who
        near_foe = False
        for i2, p2 in sim.living():
            if p2.tribe == enemy:
                fx, fy = p2.block & 0x3F, p2.block >> 6
                if abs(fx - dx) <= 5 and abs(fy - dy) <= 5:
                    near_foe = True
                    break
        if near_foe or who[(dy << 6) | dx] or blk[(dy << 6) | dx] != BLK_FLAT:
            # terrain occupe ou hostile : on prefere relever, ca cree de la terre
            st.act = ACT_RAISE
            st.p1 = dx
            st.p2 = dy
            return
        r = sim.rng.below(100)
        if mana >= COST_QUAKE and r < 5:
            st.act = ACT_QUAKE
        elif mana >= COST_SWAMP and r < 10:
            st.act = ACT_SWAMP
        elif mana >= COST_RAISE * 4 and r < 40:
            st.act = ACT_RAISE
        elif r < 70:
            st.act = ACT_TREE
        else:
            st.act = 12                        # rocher
        st.p1 = dx
        st.p2 = dy

