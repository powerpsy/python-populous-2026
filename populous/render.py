"""Rendu isométrique de la vue de jeu — transcription de l'asm.

Routines référencées (``reference/tetracorp/populous_prg.asm``) :

======================  ======  =================================================
``_drw_blk``/``SUB_49938`` 15737  blitter d'une tuile 32×24 (masque + 4 plans)
``_draw_it``             15794  la fenêtre 8×8 : 3 passes
``SUB_49B90``            15926  blitter d'un sprite 16×16 (masque + 4 plans)
``_move_sprite``         15951  sprite d'un habitant
``_draw_map``            1543   mini-carte (Book of Worlds)
======================  ======  =================================================

Projection (octets dans l'écran, stride 40) :

    octet = _screen_origin + 322*d0 + 318*d1 - 320*alt

avec ``d0 = X - xoff``, ``d1 = Y - yoff`` et ``_screen_origin = 2582``.
En pixels : ``x = 16*(d0-d1) + origin_x``, ``y = 8*(d0+d1) - 8*alt + origin_y``,
soit ``origin = (176, 64)``.

Les faces latérales du relief (passes 2 et 3) n'existent que sur la **dernière
colonne** et la **dernière ligne** de la fenêtre : pour les cases intérieures,
les losanges des cases vers l'avant les recouvrent exactement (démonstration
dans ``docs/map_generation.md`` §9.4).
"""
from __future__ import annotations

import pygame

from .assets import (FONT, ICON_COUNT, _palette_index, load_icon,
                     load_land, load_sprites, palette_rgb)
from .constants import BLK_FLAT, MAP_CELLS
from .terrain import ALT_W, BLK_PROTECT, BLK_SEA, MAX_OFF, Terrain, WATER_ALT_TILE

SCREEN_W, SCREEN_H = 320, 200
ORIGIN_BYTE = 2582          # _screen_origin (0xA16) = 40*64 + 22
ORIGIN_X = (ORIGIN_BYTE % 40) * 8      # 176
ORIGIN_Y = ORIGIN_BYTE // 40           # 64
WINDOW = 8

TILE_W, TILE_H = 32, 24
SPRITE_SIZE = 16

# indices des deux sprites de « falaise » (voir _draw_it passes 2/3)
SPRITE_FACE_RIGHT = 0x3020 // 160      # 77
SPRITE_FACE_LEFT = 0x2F80 // 160       # 76

# marqueurs magnétiques dessinés comme des tuiles
DEVIL_TILE = 0x2E                      # 46
GOD_TILE = 0x2D                        # 45


def cell_px(d0: int, d1: int, alt: int) -> tuple[int, int]:
    """Position pixel de la tuile d'une case ``(d0, d1)`` d'altitude ``alt``.

    C'est l'adresse octet modulo la largeur d'une ligne (40 octets), exactement
    comme le fait ``SUB_49938`` : dans la fenêtre 8×8 le décalage horizontal
    reste toujours dans [0, 40) donc il n'y a jamais de retour à la ligne.
    """
    b = ORIGIN_BYTE + 322 * d0 + 318 * d1 - 320 * alt
    return (b % 40) * 8, b // 40


def cell_abs(x: int, y: int, alt: int) -> tuple[int, int]:
    """Coordonnées pixel **absolues** (non réduites modulo la ligne).

    ``px = 176 + 16*(x-y)``, ``py = 64 + 8*(x+y) - 8*alt``.
    """
    return ORIGIN_X + 16 * (x - y), ORIGIN_Y + 8 * (x + y) - 8 * alt


class Renderer:
    """Charge un jeu de tuiles + de sprites et dessine une fenêtre 8×8."""

    def __init__(self, ground: int = 0):
        self.header, self.tiles = load_land(ground)
        self.sprites = load_sprites("sprites%d.dat" % self.header["sprites_no"])
        # spr_320.dat : 13 sprites 32x32, uniquement pour les « gros » peeps
        # (``who >= 0xD1``, cf. la boucle d'image L632).
        try:
            self.sprites32 = load_sprites("spr_320.dat", 32, 32)
        except FileNotFoundError:                             # pragma: no cover
            self.sprites32 = []
        if len(self.sprites) <= SPRITE_FACE_RIGHT:
            raise ValueError("jeu de sprites trop court (%d)" % len(self.sprites))
        self.ground = ground
        self.toggle = 0          # _toggle : alterne à chaque image (eau)
        self.last_queue: list[tuple[int, int, int, int]] = []

# ----------------------------------------------------------- _text (L19973)
    # ``_text(ecran, x, y, chaine)`` ecrit la chaine avec la police du jeu.
    #
    # Addressing : ``x >> 3`` puis ``+ y * 0x28``. Donc **x est exprime en
    # unites de 8 pixels** (1 octet de plan = 8 px), contrairement a
    # ``_draw_icon`` qui recoit des unites de 16 px.
    #
    # Chaque glyphe fait 8 lignes de 8 px. Pour chaque ligne l'asm fait, sur
    # chacun des 4 plans : ``(ecran AND masque) OR donnees``, donc le glyphe
    # est **ecrase** (pas de transparence) â€” c'est ce que fait notre blit avec
    # l'opaque a 1.
    #
    # Le retour a la ligne est un saut de ``0x140 = 320`` octets, soit
    # exactement 8 lignes : on revient au colonne de depart, ligne + 8.
    @staticmethod
    def draw_text(dest: pygame.Surface, x: int, y: int, text: str) -> None:
        """``_text(ecran, x, y, chaine)`` (asm L19973). ``x`` en unitÃ©s de 8 px."""
        px, py = x * 8, y
        if py < 0 or py >= dest.get_height():
            return
        cur_x = px
        line = py
        for ch in text:
            if ch == "\n":
                cur_x = px
                line += 8
                continue
            if ch == "\0":
                break
            code = ord(ch)
            if code < 0x20:               # hors de la police : rien
                continue
            glyph = FONT.glyph(code)
            if cur_x >= 0 and cur_x + 8 <= dest.get_width():
                dest.blit(glyph, (cur_x, line))
            cur_x += 8
            if cur_x >= dest.get_width():
                cur_x = px
                line += 8

    @staticmethod
    def text_width(text: str) -> int:
        """Largeur en pixels d'une chaine (8 px par glyphe)."""
        w = 0
        for ch in text:
            if ch == "\n":
                continue
            w += 8
        return w
    # --------------------------------------------------- primitives d'interface
    # L'ecran Amiga fait 320x200 en 4 bitplans Â« plane-major » : un octet
    # Addressing exact de _draw_icon (L19188-19195) :
    #     D0 = x ; D0 <<= 1  -> x*2 octets  (donc x en unites de 16 px)
    #     D1 = y ; D1 *= 0x28 -> y lignes     (donc y en LIGNES)
    # L icone occupe 16 lignes a partir de y.
    # et la ligne suivante est a +0x28 = +40 octets. Les trois primitives
    # d'interface ecrivent a ces offsets exacts :
    #
    #   _draw_sprite (L19283) : A0 = ecran + x*2 + y*0x28
    #   _draw_icon   (L19184) : A0 = ecran + x*2 + y*0x28
    #   _draw_bar    (L19213) : A0 = ecran + x   + y*0x28
    #
    # Le doublement est present dans _draw_sprite (L19307) et dans
    # _draw_icon (L19192) mais absent de _draw_bar : les deux premiers
    # recoivent un x en unites de 16 pixels, le dernier un offset en
    # octets. Attention, _draw_icon prend y en LIGNES, pas en unites.
    # (x*2 octets = 16 pixels), le dernier un **offset en octets** (x*8 px).
    SCREEN_STRIDE = 40                # 0x28 : octets par ligne
    PLANE_STRIDE = 8000               # 0x1F40 : longueur d'un plan

# ------------------------------------------------- _toggle_icon (L19493)
    # L'icone Â« active Â» est obtenue en XORant sur elle un losange de 16x16.
    # L'asm ecrit 4 octets par ligne (un par plan) et passe a la ligne
    # suivante avec +0x28 ; la table LAB_4C750 contient les 16 masques :
    #
    #   $0000c000 $0003f000 $000ffc00 $003fff00 $00ffffc0 $03fffff0
    #   $0ffffffc $3fffffff $0ffffffc $03fffff0 $00ffffc0 $003fff00
    #   $000ffc00 $0003f000 $0000c000   (+ 0 pour la 16e ligne, le DS.L 1)
    #
    # Ces valeurs sont symetriques autour de la ligne 7 et forment exactement le
    # losange : on n'en garde que les 16 bits de poids faible, qui sont le
    # losange vu en largeur (1 bit = 1 pixel, le bit de poids fort etant le
    # pixel de gauche comme dans un plan Amiga).
    _TOGGLE_ROWS = (0xC000, 0xF000, 0xFC00, 0xFF00, 0xFFC0, 0xFFF0,
                    0xFFFC, 0xFFFF, 0xFFFC, 0xFFF0, 0xFFC0, 0xFF00,
                    0xFC00, 0xF000, 0xC000, 0x0000)
    # Pas de la grille d'icones : l'asm multiplie par 0x142 = 322 et 0x13E =
    # 318. En decodedunits de la ligne (40 octets) et du pixel (8 octets par
    # octet de plan), 322 = 8 lignes + 16 px et 318 = 8 lignes - 16 px : la
    # grille est donc la grille **isometrique** de l'interface.
    TOGGLE_DX, TOGGLE_DY = 16, 8

    @classmethod
    def toggle_icon(cls, dest: pygame.Surface, col: int, row: int,
                    mask: int) -> int:
        """``_toggle_icon(ecran, x, y, masque)`` (asm L19493).

        Retourne le nombre de pixels modifies. Sur chaque pixel du losange on
        fait un **XOR de l'indice de palette avec 1**, ce qui est l'equivalent
        du ``EOR.L`` de l'asm : l'icone bascule entre son etat normal et son
        etat inverse. C'est ce qui rend visible l'outil arme.
        """
        # position de l'icone, en (ligne, octet de depart sur la ligne)
        off = col * 322 + row * 318 + mask
        y0, xb = divmod(off, 40)
        x0 = xb * 8
        pal = palette_rgb()
        rev = _palette_index()
        w, h = dest.get_width(), dest.get_height()
        n = 0
        for dy, bits in enumerate(cls._TOGGLE_ROWS):
            y = y0 + dy
            if not (0 <= y < h):
                continue
            for dx in range(16):
                if not (bits >> (15 - dx)) & 1:
                    continue
                x = x0 + dx
                if not (0 <= x < w):
                    continue
                idx = rev.get(dest.get_at((x, y))[:3], 0)
                dest.set_at((x, y), pal[idx ^ 1])
                n += 1
        return n
    @staticmethod
    def draw_icon(dest: pygame.Surface, x: int, y: int, icon: int) -> None:
        """``_draw_icon(ecran, x, y, icone)`` (asm L19184).

        Addressing exact (L19188-19195) :

            D0 = x ; D0 <<= 1        -> x*2 octets
            D1 = y ; D1 *= 0x28      -> y lignes
            A0 = ecran + x*2 + y*40

        donc **x est en unites de 16 pixels** et **y est en lignes** : l'icone
        occupe 16 lignes a partir de ``y``. C'est la piege — `_draw_bar`, elle,
        recoit un x en octets (elle ne fait pas le doublement).

        L'icone vient de ``_icon_data + icone * 128`` — c'est le ``LSL.W #7``
        de L19196. Elle n'a **pas** de mot de masque : l'original ecrase les
        4 plans, donc les pixels d'indice 0 sont peints et non transparents
        (d'ou ``opaque=True``).
        """
        if not (0 <= icon < ICON_COUNT):
            return
        px, py = x * 16, y
        if px >= dest.get_width() or py >= dest.get_height():
            return
        dest.blit(load_icon(icon, opaque=True), (px, py))
    @staticmethod
    def draw_bar(dest: pygame.Surface, x: int, y: int, height: int,
                 filled: int, flags: int) -> None:
        """``_draw_bar(ecran, x, y, hauteur, rempli, drapeaux)`` (asm L19213).

        * ``x`` est un **offset en octets** : le groupe de 8 pixels commence
          au pixel ``x*8`` ;
        * la barre se remplit **vers le haut** : le pointeur part de la ligne
          ``y`` et chaque iteration recule de 40 octets (``SUBA.L #$28,A0``,
          L19277), donc les ``filled`` premieres lignes tracees sont celles du
          bas ;
        * ``filled`` lignes sont peintes avec ``flags``, le reste avec
          ``flags = 2`` (L19242) ;
        * pour chaque plan p, ``BTST #p,D3`` choisit entre ``ORI.B #$3c`` et
          ``ANDI.B #$c3`` sur l'octet du plan (L19249-19276) : cela allume ou
          eteint les **bits 2 a 5** de l'indice de couleur de la palette.

        Les bornes sont celles de l'asm : ``filled`` est borne a
        ``[0, height]`` (L19226-19232).
        """
        if height <= 0:
            return
        filled = max(0, min(height, filled))
        rest = height - filled
        pal = palette_rgb()
        rev = _palette_index()
        x0 = x * 8
        w, h = dest.get_width(), dest.get_height()
        # un segment = (nombre de lignes, drapeaux) ; le curseur ``row``
        # descend de 1 a chaque ligne, comme le SUBA de l'asm
        row = y
        for count, fl in ((filled, flags), (rest, 2)):
            for _ in range(count):
                if 0 <= row < h:
                    for col in range(8):
                        px = x0 + col
                        if not (0 <= px < w):
                            continue
                        idx = rev.get(dest.get_at((px, row))[:3], 0)
                        for bit in range(4):
                            if (fl >> bit) & 1:
                                idx |= 0x3C
                            else:
                                idx &= 0xC3
                        # un octet de plan ne porte que 4 bits : l'asm
                        # travaille sur le mot, dont seuls les 4 bits bas
                        # sont utilises. On borne donc a 0..15.
                        dest.set_at((px, row), pal[idx & 0x0F])
                row -= 1

    # ------------------------------------------------------------------ tuiles
    def blit_tile(self, dest: pygame.Surface, tile: int, d0: int, d1: int,
                  alt: int) -> None:
        """``SUB_49938(D0=d0, D1=d1, D2=alt*8, D3=tile)``."""
        if not (0 <= tile < len(self.tiles)):
            return
        x, y = cell_px(d0, d1, alt)
        dest.blit(self.tiles[tile], (x, y))

    # ------------------------------------------------------------------ vue
    @staticmethod
    def cell_px(d0: int, d1: int, alt: int) -> tuple[int, int]:
        """Raccourci : position pixel d'une case de la fenetre."""
        return cell_px(d0, d1, alt)

    def blit_face(self, dest: pygame.Surface, sprite: int, x: int, y: int,
                  levels: int, dx: int) -> None:
        """``SUB_49B90`` × ``levels`` — la colonne de falaise d'une case.

        ``x, y`` = ancrage de la tuile au **niveau 0** ; la première copie est
        posée 8 px plus bas, puis on remonte de 8 px à chaque niveau.
        ``dx`` = décalage horizontal de la face (0 = gauche, 16 = droite).
        """
        if levels <= 0 or not (0 <= sprite < len(self.sprites)):
            return
        img = self.sprites[sprite]
        px = x + dx
        py = y + 8
        for k in range(levels):
            dest.blit(img, (px, py - 8 * k))

    # ------------------------------------------------------------------ vue
    def draw_window(self, dest: pygame.Surface, terr: Terrain,
                    xoff: int = 0, yoff: int = 0,
                    devil: int = 0, god: int = 0,
                    sprite_for=None) -> None:
        """``_draw_it(xoff, yoff)`` — les 3 passes."""
        blk, disp_alt, bk2, who = (terr.blk, terr.disp_alt, terr.bk2, terr.who)

        # ---- passe 1 : les 64 losanges de haut -----------------------------
        for d1 in range(WINDOW):
            y = yoff + d1
            row = y << 6
            for d0 in range(WINDOW):
                x = xoff + d0
                idx = row + x
                tile = blk[idx]
                if tile == BLK_SEA and self.toggle == 0:
                    tile = WATER_ALT_TILE          # animation de l'eau
                a = disp_alt[idx]
                self.blit_tile(dest, tile, d0, d1, a)
                deco = bk2[idx]
                if deco:
                    self.blit_tile(dest, deco, d0, d1, a + 1)
                w = who[idx]
                if w and sprite_for is not None:
                    img = sprite_for(w, idx)
                    if img is not None:
                        x0, y0 = cell_px(d0, d1, a)
                        dest.blit(img, (x0, y0))
                if devil and idx == devil:
                    self.blit_tile(dest, DEVIL_TILE, d0, d1, a)
                if god and idx == god:
                    self.blit_tile(dest, GOD_TILE, d0, d1, a)

        # ---- passe 2 : face avant droite (dernière colonne) ----------------
        xcol = xoff + WINDOW - 1
        for d1 in range(WINDOW):
            idx = (yoff + d1) << 6 | xcol
            a = disp_alt[idx]
            if a:
                x, y0 = cell_px(WINDOW - 1, d1, 0)   # ancrage niveau 0
                self.blit_face(dest, SPRITE_FACE_RIGHT, x, y0, a, dx=16)

        # ---- passe 3 : face avant gauche (dernière ligne) -----------------
        yrow = yoff + WINDOW - 1
        for d0 in range(WINDOW, 0, -1):
            idx = yrow << 6 | (xoff + d0 - 1)
            a = disp_alt[idx]
            if a:
                x, y0 = cell_px(d0 - 1, WINDOW - 1, 0)
                self.blit_face(dest, SPRITE_FACE_LEFT, x, y0, a, dx=0)

    # ------------------------------------------------------------- habitants
    # ``_move_sprite`` (L15951) ne dessine rien : il empile des quadruplets
    # (x, y, sprite, who) dans ``_sprite[]`` (8 octets, 8 bits de large en x),
    # et la boucle d'image (L627-657) les relit ensuite *dans l'ordre*.
    #
    #     D5 = 8*(d0+d1) - alt*8      -> ligne
    #     D4 = 16*(d0-d1)             -> colonne
    #     soit, une fois les +0xC0 / +0x40 des branches :
    #         x = 16*(d0-d1) + 192     (cell_px + 16)
    #         y = 8*(d0+d1) - 8*alt + 64   (= cell_px + 0)
    def build_sprite_queue(self, terr: Terrain, xoff: int, yoff: int,
                           sim) -> list[tuple[int, int, int, int]]:
        """Reproduit la file ``_sprite[]`` remplie par ``_move_sprite``.

        Le résultat est aussi conservé dans ``self.last_queue`` : c'est cette
        liste que parcourt ``_interogate`` (asm L2719) pour le survol des
        habitants (boîtes de 12 × 8 autour de chaque sprite).
        """
        q: list[tuple[int, int, int, int]] = []
        who_map = sim.map.who
        disp_alt = terr.disp_alt
        peeps = sim.peeps
        toggle = sim.toggle
        for d1 in range(WINDOW):
            row = (yoff + d1) << 6
            for d0 in range(WINDOW):
                idx = row + xoff + d0
                w = who_map[idx]
                if not w:
                    continue
                p = peeps[w - 1]
                st = p.state
                x = ORIGIN_X + 16 * (d0 - d1) + 16
                yy = ORIGIN_Y + 8 * (d0 + d1) - 8 * disp_alt[idx]
                if st == 2 or (st & 0x10):
                    # Lab_49D3E (L16063) : ce n'est PAS « ne pas dessiner ».
                    # C'est le chemin d'interpolation d'un peep qui marche ou
                    # qui traverse une falaise :
                    #     si frame >= 8  -> traceur de debug, RIEN n'est dessine
                    #     sinon           -> la ligne est decalee par
                    #                       (bk2[ancienne] - bk2[actuelle]) * frame
                    #                       (+4 si la case n'est pas du plat)
                    # C'est ce decalage qui fait « monter/descendre » le peep
                    # le long d'une pente ou d'un batiment.
                    if p.frame >= 8:
                        continue
                    old = idx - p.prev_block if p.prev_block else idx
                    old = max(0, min(MAP_CELLS - 1, old))
                    bk2 = sim.map.bk2
                    shift = (bk2[old] - bk2[idx]) * p.frame
                    if shift > 32767 or shift < -32768:
                        shift = 0
                    yy += shift
                    if sim.map.blk[idx] != BLK_FLAT:
                        yy += 4
                    sprite = p.frame + (0x20 if p.target else 0)
                    if p.tribe:
                        sprite += 4
                    q.append((x, yy, sprite, w))
                    continue
                self._pending = True
                if st == 1:                                   # Lab_49D16
                    sprite = 0x40 + toggle + (2 if p.tribe else 0)
                elif st & 0x60:                               # Lab_49CCC
                    sprite = p.frame + (0x18 if p.target else 0)
                    if p.tribe:
                        sprite += 2
                elif st & 0x08:                               # Lab_49CF8
                    sprite = p.frame
                elif st & 0x80:                               # Lab_49CA4
                    x -= 8
                    sprite = (sim.game_turn & 3) + 0x69
                else:                                         # marche
                    sprite = p.frame + (0x20 if p.target else 0)
                    if p.tribe:
                        sprite += 4
                q.append((x, yy, sprite, w))
                if w == sim.view_who:                         # curseur
                    q.append((x + 8, yy, 0x44, w))
                pl = sim.players[p.tribe]
                if pl.magnet and pl.magnet == w:              # marqueur de but
                    q.append((x + 8, yy, p.tribe + 0x4A, w))
        self.last_queue = q
        return q

    def draw_peeps(self, dest: pygame.Surface, terr: Terrain,
                   xoff: int, yoff: int, sim) -> int:
        """Relit la file et blitte, comme la boucle L627-657.

        ``who >= 0xD1`` : sprite 32x32 de ``spr_320.dat``, dessine 8 px plus haut
        et 16 px plus haut que son ancre (``___draw_s_32``). Sinon sprite 16x16.
        """
        sprites = self.sprites
        big = self.sprites32
        n = 0
        for x, y, sprite, who in self.build_sprite_queue(terr, xoff, yoff, sim):
            if who >= 0xD1:
                k = sprite - 0xD1
                if 0 <= k < len(big):
                    dest.blit(big[k], (x - 8, y - 16))
            elif 0 <= sprite < len(sprites):
                dest.blit(sprites[sprite], (x, y))
            n += 1
        return n

    # ------------------------------------------------------------- mini-carte
    def draw_minimap(self, dest: pygame.Surface, terr: Terrain,
                     colours: list[int] | None = None,
                     rgb: dict[int, tuple[int, int, int]] | None = None) -> None:
        """``_draw_map(0, 0, 0x3F, 0x3F)`` : ``x = X-Y+64``, ``y = (X+Y)>>1``."""
        if colours is None:
            colours = map_colours(self.header)
        base = rgb or _map_rgb()
        for y in range(64):
            for x in range(64):
                c = colours[terr.blk[(y << 6) + x]]
                if c == 0x19:
                    c = colours[0x1F]
                dest.set_at((x - y + 64, (x + y) >> 1), base.get(c, (0, 0, 0)))

    def step_toggle(self) -> int:
        """``_toggle`` bascule à chaque image (boucle d'animation L604)."""
        self.toggle ^= 1
        return self.toggle


# ------------------------------------------------------------------ couleurs
_ROM_MAP_COLOUR_16_30 = bytes.fromhex("0e0c0b0b0c0c0b0b0d0d0c0c0d0d0c")
"""Octets ROM de ``_map_colour`` pour les blocs 16..30 (L24252-24254).

``_load_ground`` ne réécrit que les 16 premiers octets : les blocs 16..30
(« rives ») gardent donc la couleur par défaut, quel que soit le sol choisi.
"""


def map_colours(header: dict | None = None) -> list[int]:
    """Table complète ``_map_colour`` indexée par ``map_blk`` (0..231)."""
    head = list(header["map_colour"]) if header else list(
        bytes.fromhex("0e0c0b0b0c0c0b0b0d0d0c0c0d0d0c0c"))
    # blocs 16..30 (ROM) ; 31 = LAB_5177D = 0x0C ; 32.. = 0x19 -> replacé par 0x0C
    return head + list(_ROM_MAP_COLOUR_16_30) + [0x0C] + [0x19] * 200


def _map_rgb() -> dict[int, tuple[int, int, int]]:
    from .assets import palette_rgb
    return dict(enumerate(palette_rgb()))


def clamp_off(v: int) -> int:
    """``_xoff``/``_yoff`` bornés à 0..0x38 (``MAX_OFF``)."""
    return 0 if v < 0 else MAX_OFF if v > MAX_OFF else v
