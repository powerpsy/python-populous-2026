"""Génération de la carte de Populous — transcription exacte de l'asm.

Références (``reference/tetracorp/populous_prg.asm``) :

===========================  ======  ==================================
routine                       ligne   rôle
===========================  ======  ==================================
``_clear_map``                1023   remise à zéro de toutes les tables
``_make_alt``                 1189   3 marches aléatoires → relief brut
``_make_thing``               1208   une marche (bâtît une colline)
``_raise_point``              1274   +1 d'altitude + lissage des 8 voisins
``_make_map``                 1420   moyenne 2×2 → ``map_blk`` / ``map_alt``
``_mod_map``                  1594   idem, après coup du joueur
``_lower_point``              2571   miroir de ``_raise_point``
``_make_woods_rocks``         8535   7 amas de rochers + 15 d'arbres
``_load_ground``             16468   en-tête ``LANDn`` (114 o) + 70 tuiles
``_draw_map``                1543   mini-carte (Book of Worlds)
``_draw_it``                 15794   vue isométrique de la fenêtre 8×8
===========================  ======  ==================================

Toutes les tables de cases font 64×64 et sont indexées ``y*64+x`` ; la grille
d'altitude ``_alt`` fait **65×65** (stride ``0x41``) car ce sont les *sommets*
du terrain.

Documentation détaillée : ``docs/map_generation.md``.
"""
from __future__ import annotations

from collections import Counter

from .rng import Rng

# ------------------------------------------------------------------ constantes
MAP_W = 64                      # cases par côté
ALT_W = 65                      # sommets par côté (indices 0..64)
N_CELLS = MAP_W * MAP_W         # 4096
N_VERTS = ALT_W * ALT_W         # 4225
WINDOW = 8                      # fenêtre visible = 8 x 8 cases
MAX_OFF = MAP_W - WINDOW        # _xoff/_yoff bornés à 0x38 = 56

ALT_MAX = 8                     # _raise_point refuse au-delà
ALT_STOP = 6                    # _make_thing s'arrête quand une case vaut 6

BLK_SEA = 0                     # eau plate
BLK_FLAT = 15                   # plaine plate (constructible)
BLK_SHORE = 16                  # variante « rive » (16..30)
BLK_PROTECT = 47                # 0x2F : case protégée / rocher
ROCK_TILES = (47, 48, 49)       # tuiles avant-plan
TREE_TILES = (50, 51, 52)       # tuiles de la couche map_bk2
WATER_ALT_TILE = 16             # état n°2 de l'animation de l'eau


class Terrain:
    """Relief + tables de cases, dans l'état où le jeu les laisse."""

    __slots__ = ("alt", "blk", "disp_alt", "bk2", "steps", "who",
                 "build_count", "xmin", "xmax", "ymin", "ymax",
                 "seed", "ground", "t1a", "t18")

    def __init__(self, seed: int = 0, ground: int = 0):
        self.seed = seed & 0xFFFF
        self.ground = ground
        self.t1a = [0, 0]                  # `_clear_map` L1099, par joueur
        self.t18 = [0, 0]                  # `_clear_map` L1121, par joueur
        self.alt = [0] * N_VERTS
        self.blk = bytearray(N_CELLS)
        self.disp_alt = bytearray(N_CELLS)
        self.bk2 = bytearray(N_CELLS)
        self.steps = [0] * N_CELLS
        self.who = bytearray(N_CELLS)
        self.build_count = 0
        self.xmin = self.xmax = self.ymin = self.ymax = 0

    # ---------------------------------------------------------- accès mémoire
    def game_map(self):
        """Vue ``GameMap`` partageant **les mêmes tableaux** (pas de copie).

        C'est le lien entre le rendu (``terrain.blk``…) et la simulation
        (``Sim.map``) : les deux voient les mutations de l'autre.
        ``disp_alt`` joue le rôle de ``map_alt`` (4225 sommets ≠ 4096 cases).
        """
        from .map import GameMap
        return GameMap(blk=self.blk, bk2=self.bk2, who=self.who,
                       alt=self.disp_alt, steps=self.steps)

    def _cell(self, idx: int) -> int:
        """Lecture de ``_alt`` ; hors-table, le 68000 lit ``_map_blk`` (nul)."""
        a = self.alt
        return a[idx] if 0 <= idx < len(a) else 0

    def index(self, x: int, y: int) -> int:
        return (y << 6) + x

    def vertex(self, x: int, y: int) -> int:
        """Altitude du sommet ``(x, y)`` (borne à [0, 64])."""
        if 0 <= x <= 64 and 0 <= y <= 64:
            return self.alt[y * ALT_W + x]
        return 0

    # ------------------------------------------------------------- _clear_map
    def clear(self, rng: Rng | None = None) -> None:
        """``_clear_map`` (L1023), à partir du remplacement des tables."""
        self.alt = [0] * N_VERTS
        self.blk = bytearray(N_CELLS)
        self.disp_alt = bytearray(N_CELLS)
        self.bk2 = bytearray(N_CELLS)
        self.steps = [0] * N_CELLS
        self.who = bytearray(N_CELLS)
        self.build_count = 0
        self.xmin = self.xmax = self.ymin = self.ymax = 0
        # `_clear_map` L1088-1121 : par joueur, `t1a` (+0x1A) = `below(3)`
        # (L1097 `DIVS #3 / SWAP`) puis `t18` (+0x18) = `t1a + below(5) + 1`
        # (L1116-1121), et `t12` (+0x12) remis a zero (L1124-1125).
        # `Terrain` ne porte pas `_stats` : les tirages restent ici et
        # `game.py` les recopie dans `sim.stats[k]`. Sans eux `t1a = t18 = 0`
        # et `_devil_effect` (L9431-9441) verrait une porte toujours ouverte
        # sur le bloc `act = 4`.
        self.t1a = [0, 0]
        self.t18 = [0, 0]
        if rng is not None:
            for k in range(2):
                a = rng.below(3)               # t1a, L1097-1099
                self.t1a[k] = a
                self.t18[k] = a + rng.below(5) + 1   # t18, L1116-1121

    # ---------------------------------------------------------- _raise_point
    def raise_point(self, x: int, y: int) -> int:
        """``_raise_point`` (L1274). Renvoie la **nouvelle** altitude.

        Les 8 voisins sont parcourus dans l'ordre E, SE, S, SW, W, NW, N, NE ;
        ``A3`` (pointeur de sommet) et ``D4/D5`` (coordonnées) restent
        synchronisés, y compris aux bords (débordement de rangée identique au
        68000 : ``i+64`` vaut ``(64, y)`` quand ``x == 0``).
        """
        px, py = x, y                       # (8,A5) / ($A,A5)
        if x > 0x40 or x < 0 or y > 0x40 or y < 0:
            return 0
        i = y * ALT_W + x
        alt = self.alt
        if alt[i] >= 8:                     # CMPI #8,(A2) → retourne (A2)
            return alt[i]
        self.build_count += 1
        alt[i] += 1
        me = alt[i]

        d4, d5 = x + 1, y
        a3 = i + 1                          # A3 = A2 + 2 octets

        for delta, nd4, nd5 in ((0, None, None),          # E   (x+1, y)
                                (ALT_W, None, y + 1),     # SE  (x+1, y+1)
                                (-1, x, None),            # S   (x,   y+1)
                                (-1, x - 1, None),        # SW  (x-1, y+1)
                                (-ALT_W, None, y),        # W   (x-1, y)
                                (-ALT_W, None, y - 1),    # NW  (x-1, y-1)
                                (1, x, None),             # N   (x,   y-1)
                                (1, x + 1, None)):        # NE  (x+1, y-1)
            a3 += delta
            if nd4 is not None:
                d4 = nd4
            if nd5 is not None:
                d5 = nd5
            if me - self._cell(a3) > 1:
                self.raise_point(d4, d5)
                me = alt[i]                # (A2) relu après récursion

        # _xmin/_xmax/_ymin/_ymax : bornes des paramètres d'ENTRÉE
        if px < self.xmin:
            self.xmin = px
        if px > self.xmax:
            self.xmax = px
        if py < self.ymin:
            self.ymin = py
        if py > self.ymax:
            self.ymax = py
        return alt[i]

    # ---------------------------------------------------------- _lower_point
    def lower_point(self, x: int, y: int) -> int:
        """``_lower_point`` (L2571) — miroir exact de ``raise_point``."""
        px, py = x, y
        if x > 0x40 or x < 0 or y > 0x40 or y < 0:
            return 0
        i = y * ALT_W + x
        alt = self.alt
        if alt[i] == 0:                     # TST.W (A2) / BEQ → rien à faire
            return alt[i]
        self.build_count += 1
        alt[i] -= 1
        me = alt[i]

        d4, d5 = x + 1, y
        a3 = i + 1
        for delta, nd4, nd5 in ((0, None, None),
                                (ALT_W, None, y + 1),
                                (-1, x, None),
                                (-1, x - 1, None),
                                (-ALT_W, None, y),
                                (-ALT_W, None, y - 1),
                                (1, x, None),
                                (1, x + 1, None)):
            a3 += delta
            if nd4 is not None:
                d4 = nd4
            if nd5 is not None:
                d5 = nd5
            if self._cell(a3) - me > 1:
                self.lower_point(d4, d5)
                me = alt[i]

        if px < self.xmin:
            self.xmin = px
        if px > self.xmax:
            self.xmax = px
        if py < self.ymin:
            self.ymin = py
        if py > self.ymax:
            self.ymax = py
        return alt[i]

    # ------------------------------------------------------------ _make_thing
    def make_thing(self, a: int, b: int, rng: Rng, guard: int = 4_000_000) -> int:
        """``_make_thing(a, b)`` (L1208) : marche aléatoire qui dresse un relief.

        ``a`` = amplitude du pas en X, ``b`` en Y (déplacements uniformes dans
        ``[-a, +a]`` / ``[-b, +b]``, coordonnées bornées à [0, 64]).
        """
        x = rng.below(0x40)
        y = rng.below(0x40)
        iters = 0
        while True:
            iters += 1
            if self.raise_point(x, y) == ALT_STOP:
                break
            x += rng.below(2 * a + 1) - a
            y += rng.below(2 * b + 1) - b
            if x < 0:
                x = 0
            elif x > 0x40:
                x = 0x40
            if y < 0:
                y = 0
            elif y > 0x40:
                y = 0x40
            if iters >= guard:              # garde-fou (absent du jeu)
                break
        return iters

    # -------------------------------------------------------------- _make_alt
    def make_alt(self, rng: Rng) -> None:
        """``_make_alt`` (L1189) : trois marches successives."""
        self.make_thing(2, 4, rng)
        self.make_thing(4, 2, rng)
        self.make_thing(3, 3, rng)

    # -------------------------------------------------------------- _make_map
    def make_map(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """``_make_map(x0, y0, x1, y1)`` (L1420) — moyenne 2×2 → pente/altitude."""
        alt = self.alt
        blk, disp_alt, bk2, steps = (self.blk, self.disp_alt, self.bk2, self.steps)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                idx = (y << 6) + x
                i = y * ALT_W + x
                # moyenne des 4 sommets de la case
                avg = (alt[i + 1] + alt[i + ALT_W] + alt[i + ALT_W + 1] + alt[i]) >> 2
                mask = 0
                if alt[i] > avg:                    # haut-gauche
                    mask |= 1
                if alt[i + 1] > avg:                # haut-droit
                    mask |= 2
                if alt[i + ALT_W + 1] > avg:        # bas-droit
                    mask |= 4
                if alt[i + ALT_W] > avg:            # bas-gauche
                    mask |= 8

                if blk[idx] == BLK_PROTECT and (mask != 0 or avg != 0):
                    mask = BLK_PROTECT              # case conservée telle quelle
                else:
                    blk[idx] = mask

                if avg != 0 and mask == 0:          # 4 sommets égaux et > 0
                    avg -= 1
                    mask = BLK_FLAT
                if avg == 0 and mask != BLK_FLAT and mask != 0:
                    mask += BLK_SHORE               # rive (16..30)

                disp_alt[idx] = avg & 0xFF
                if blk[idx] != BLK_PROTECT:
                    blk[idx] = mask & 0xFF
                else:
                    mask = BLK_PROTECT
                if mask == 0:
                    bk2[idx] = 0
                steps[idx] = 0

    def mod_map(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """``_mod_map`` (L1594) : identique, mais sans toucher à ``bk2``."""
        alt = self.alt
        blk, disp_alt, steps = self.blk, self.disp_alt, self.steps
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                idx = (y << 6) + x
                i = y * ALT_W + x
                avg = (alt[i + 1] + alt[i + ALT_W] + alt[i + ALT_W + 1] + alt[i]) >> 2
                mask = 0
                if alt[i] > avg:
                    mask |= 1
                if alt[i + 1] > avg:
                    mask |= 2
                if alt[i + ALT_W + 1] > avg:
                    mask |= 4
                if alt[i + ALT_W] > avg:
                    mask |= 8
                if blk[idx] == BLK_PROTECT and (mask != 0 or avg != 0):
                    mask = BLK_PROTECT
                else:
                    blk[idx] = mask
                if avg != 0 and mask == 0:
                    avg -= 1
                    mask = BLK_FLAT
                if avg == 0 and mask != BLK_FLAT and mask != 0:
                    mask += BLK_SHORE
                disp_alt[idx] = avg & 0xFF
                blk[idx] = mask if blk[idx] != BLK_PROTECT else BLK_PROTECT
                steps[idx] = 0

    # ------------------------------------------------------- _rotate_all_map
    def rotate_all_map(self) -> None:
        """``_rotate_all_map`` (L6824-6921) — **transcrit tel quel**.

        Trois blocs, dans cet ordre :

        1. **``_alt``** (L6830-6868) : les paires ``(i, 0x1080-i)`` sont les
           partenaires d'une rotation 180° de la grille 65×65 de sommets
           (``0x1080 = 4224``, et ``k' = 4224 - k`` pour ``(x,y) -> (64-x,64-y)``).
           La boucle va de ``i = 0`` à ``i < 0x1080 >> 1``, soit ``2112``
           itérations : elle couvre **tous** les indices sauf le centre 2112.
        2. **``_map_bk2``** (L6874-6904) : les tuiles d'arbre (``$32..$37``)
           sont propagées vers leur partenaire ``(i, 0xFFF-i)``.
        3. ``_make_map(0,0,$3F,$3F)`` — les blocs sont **recalculés** depuis
           ``_alt``, donc la forme du terrain vient entièrement de l'étape 1.

        **L'écart assumé.** L'étape 1 n'est **pas un échange** : il n'existe
        aucune variable temporaire nulle part dans le bloc, et l'ordre des deux
        écritures fait que chaque paire finit avec les **deux** cases égales au
        **maximum** des deux valeurs d'origine :

        .. code-block:: none

            42ff0  MOVE.W (0,A0,D0.L),D2       ; D2  = alt[i]
            42ff4  CMP.W  (0,A1,D1.L),D2       ; D2  = alt[i] - alt[j]
            42ff8  BGE.S  43016                ; si alt[i] >= alt[j], on saute
            43010  MOVE.W (A0,D0),(A1,D1)       ; alt[i] = alt[j]   (fall-through)
            43016  MOVE.W (A0,D0),(A1,D1)       ; alt[j] = alt[i]   (inconditionnel)

        Un ``swap`` aurait besoin d'un registre ou d'une pile pour garder la
        valeur **d'origine** de ``alt[i]`` ; il n'y en a aucun. On transcrit
        donc le pli max, et l'on ne « corrige » pas vers un échange : ce serait
        de la reconstruction, pas de la transcription.

        **Le second écart** : la boucle ``_map_bk2`` teste
        ``i < 0xFFF >> 1``, soit ``i < 2047`` — elle rate donc la paire centrale
        ``(2047, 2048)``. La boucle ``_alt``, elle, est juste (``2112`` pairs
        pour 4225 sommets). L'off-by-one est donc réel et côté ``bk2`` seul.

        Le ``_draw_map(0,0,$3F,$3F)`` final (L6918) n'est pas rappelé ici :
        dans notre port la mini-carte est repeinte **chaque image** depuis
        ``terr.blk`` (``Game.compose``, L453), donc l'effet est identique.
        """
        alt = self.alt
        d5 = 0x1080
        d4 = 0
        while d4 < (d5 >> 1):
            i = d4
            j = d5 - d4
            if alt[i] < alt[j]:            # L6846-6850, BGE → signe
                alt[i] = alt[j]            # L6846-6850
            alt[j] = alt[i]                # L6856-6861, inconditionnel
            d4 += 1

        bk2 = self.bk2
        d5 = 0x0FFF
        d4 = 0
        while d4 < (d5 >> 1):              # i < 2047 : rate (2047, 2048)
            j = d5 - d4
            v = bk2[d4]
            if 0x32 <= v <= 0x37:          # L6876-6884, BCS/BHI = non signé
                bk2[j] = v                 # L6884-6888
            elif 0x32 <= bk2[j] <= 0x37:   # L6890-6898
                bk2[d4] = bk2[j]           # L6904
            d4 += 1

        self.make_map(0, 0, 0x3F, 0x3F)    # L6906-6915

    # ------------------------------------------------------ _make_woods_rocks
    def make_woods_rocks(self, rng: Rng) -> None:
        """``_make_woods_rocks`` (L8535) : 7 amas de rochers + 15 d'arbres."""
        blk, bk2 = self.blk, self.bk2
        for k in range(0x16):                       # 22 amas
            thresh = 0x32 - (3 if k < 7 else 0)     # 47 ou 50
            x0 = rng.below(0x3B)                    # 0..58
            y0 = rng.below(0x3B)
            for _ in range(0x1E):                   # 30 essais
                x = x0 + rng.below(9)
                y = y0 + rng.below(9)
                if not (0 <= x < 64 and 0 <= y < 64):
                    continue
                idx = (y << 6) + x
                b = blk[idx]
                if b == BLK_SEA or b == BLK_PROTECT:
                    continue
                v = thresh + rng.below(3)           # 47,48,49 ou 50,51,52
                if thresh == BLK_PROTECT:
                    blk[idx] = v                    # rochers (avant-plan)
                else:
                    bk2[idx] = v                    # arbres (couche décor)

    # ------------------------------------------------------------ _setup_display
    def build(self, rng: Rng, trees: bool = True) -> None:
        """Chaîne complète effectuée par ``_setup_display`` quand ``a == 0``.

        À noter : ``clear_map()`` consomme **4 tirages** avant ``make_alt()``,
        et ``_seed`` est incrémenté à la fin de ``_setup_display``.
        """
        self.clear(rng)
        self.make_alt(rng)
        self.make_map(0, 0, 0x3F, 0x3F)
        if trees:
            self.make_woods_rocks(rng)
        self.seed = (rng.seed + 1) & 0xFFFF        # _seed += 1

    # ------------------------------------------------------------------ divers
    def flat_cells(self) -> list[int]:
        """Indices des cases planes constructibles (``map_blk == 15``)."""
        return [i for i, b in enumerate(self.blk) if b == BLK_FLAT]

    def is_water(self, idx: int) -> bool:
        return self.blk[idx] == BLK_SEA

    def stats(self) -> dict:
        land = sum(1 for v in self.alt if v > 0)
        return {
            "verts": len(self.alt),
            "land_verts": land,
            "max_alt": max(self.alt),
            "build_count": self.build_count,
            "box": (self.xmin, self.ymin, self.xmax, self.ymax),
            "alt_hist": dict(sorted(Counter(self.alt[:N_VERTS]).items())),
            "blk_hist": dict(sorted(Counter(self.blk).items())),
            "flat": sum(1 for b in self.blk if b == BLK_FLAT),
            "sea": sum(1 for b in self.blk if b == BLK_SEA),
        }


def build_map(seed: int, ground: int = 0, trees: bool = True) -> tuple[Terrain, Rng]:
    """Génère une carte complète à partir d'une graine (comme le jeu)."""
    rng = Rng(seed)
    t = Terrain(seed, ground)
    t.build(rng, trees=trees)
    return t, rng
