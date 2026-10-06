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

from .constants import (
    ACT_ACTION, ACT_LOWER, ACT_MAGNET, ACT_NOP, ACT_QUAKE, ACT_RAISE,
    ACT_SWAMP, ACT_TREE, ACT_VOLCANO, BLK_FLAT, BLK_ROCK, BLK_ROCK2,
    BLK_ROCK3, BLK_SWAMP, BLK_TRIBE0, BLK_TRIBE1, BLK_WATER, BK2_TREE,
    COST_FLOOD, COST_KNIGHT, COST_MAGNET, COST_QUAKE, COST_RAISE, COST_SWAMP,
    COST_VOLCANO, COST_WAR, MAP_CELLS, SUB_CLEAR, SUB_FLOOD, SUB_KNIGHT,
    SUB_WAR,
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
            self._sub_action(tribe, x, y)
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

    def _sub_action(self, tribe: int, p1: int, p2: int) -> None:
        """Sous-commandes de ``_do_action`` (§4.4)."""
        sim = self.g.sim
        if p2 == SUB_WAR:
            self.do_war(tribe)
        elif p2 == SUB_FLOOD:
            self.do_flood(tribe)
        elif p2 == SUB_KNIGHT:
            self.do_knight(tribe, 0, 0)
        elif p2 == 9:                         # demi-mana joueur 0
            pl = sim.players[0]
            pl.mana = (pl.mana // 2) if p1 else min(pl.mana * 2 + 500, 100000)
        elif p2 == 10:                        # demi-mana joueur 1
            pl = sim.players[1]
            pl.mana = (pl.mana // 2) if p1 else min(pl.mana * 2 + 500, 100000)
        elif p2 == SUB_CLEAR:
            for i in range(MAP_CELLS):
                sim.map.blk[i] = BLK_WATER
                sim.map.bk2[i] = 0
                sim.map.who[i] = 0
        # 11 (rotate) et 13 (ground) traites ailleurs ; 12/14/15 no-op ou cheat

    # ------------------------------------------------------------------- IA
    def ai_choose(self, tribe: int) -> None:
        """L'IA ennemie choisit une action (§5.3). Approximation fable mais
        coherente : elle ameliore son terrain quand elle a de la mana, sinon
        elle pose des arbres pour proteger, puis des pierres.

        On ne touche qu'a la fiche de l'IA (``tribe``), jamais celle du joueur.

        **Le portillon.** L'asm teste ``LAB_516AC`` — c'est-a-dire
        ``stats+8``, notre :attr:`~populous.sim.Tribe.queued` — **avant**
        toute decision (L3256) :

        .. code-block:: none

            for t in (0, 1):
                if stats[t].queued == 0: _set_devil_magnet(t)
                if stats[t].queued == 0: _devil_effect(t)

        Autrement dit l'IA ne reflechit **que lorsqu'elle n'a aucune action
        en file** : pendant qu'une ville se fonde (``queued`` pose par
        `sim.py` L603/L727), elle ne decide plus. Ce portillon manquait.
        """
        sim = self.g.sim
        st = sim.stats[tribe]
        if st.queued:
            return                       # asm L3256 : TST.W (8,A0) / BNE
        if st.act not in (0, ACT_NOP):
            return                            # une action est deja en attente
        mana = self.mana(tribe)
        if mana < COST_RAISE:
            return
        # choisit un point aleatoire autour d'un village de la tribu
        target = None
        for _i, p in sim.living():
            if p.tribe == tribe and p.state == 1:      # villageois = ville
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