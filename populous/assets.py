"""Chargement des extraits graphiques de Populous (Amiga, 1989).

Tous les formats ont ete reverse-es a partir de la desassemblage du jeu
(reference/tetracorp/populous_prg.asm) et valides visuellement :

  ecran         320x200 px, 4 plans, layout "plan-major" (plan p = p*8000)
  tuile landN   114 octets d'entete + 70 tuiles de 480 octets
                24 lignes x [masque.l][p0.l][p1.l][p2.l][p3.l]   (32x24 px)
  sprite 16     160 octets = 16 lignes x [masque.w][p0][p1][p2][p3]  (16x16)
  spr_320       640 octets/enregistrement = 32 lignes x 2 blocs entrelaces
                de 10 octets = 32x32 (taille confirmee par ``MULU #$0280``,
                asm L19397 ; charge a part dans ``_sprite_data_32``, 8320
                octets, L16444)
  bouches       6 x 840 octets = 35 lignes x 4 plans de 6 octets  (48x35)
  .pic          32000 octets = 4 plans x 8000   (+ 32 octets de palette)
  font.dat      40 octets/glyphe = 8 lignes x [masque.b][p0][p1][p2][p3]
                glyphe i = caractere (32+i) ; 110 glyphes (8x8 px)

Les enregistrements d'un meme fichier sont **collés bout a bout**, ce qui permet
de tout decoder en une seule image PIL (voir ``_decode_strip``) : le cout est
alors de l'ordre de 12 appels C par fichier au lieu de ~30 par sprite. Les
resultats sont ensuite mis en cache : creer un ``Renderer`` par image ne
redecode rien.
"""
from __future__ import annotations

import json
import struct
from functools import lru_cache
from pathlib import Path

import pygame
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
GAME = ROOT / "reference" / "original" / "extracted"   # disque de jeu
DATA = ROOT / "extracted"                              # disque de donnees

# Palette du jeu (symbole _palette, populous_prg.asm ligne 24264)
PALETTE = [
    0x0000, 0x0444, 0x0666, 0x0888, 0x0aaa, 0x0ccc, 0x0620, 0x0840,
    0x0a00, 0x0a60, 0x0aa0, 0x04a0, 0x0280, 0x0262, 0x0248, 0x026c,
]

# couleurs nommees utiles a l'interface (index dans PALETTE)
BLACK, GREY, LGREY, XLGREY, WHITE, NEARWHITE = 0, 1, 2, 3, 4, 5
BROWN, LBROWN, RED, ORANGE, YELLOW, GREEN = 6, 7, 8, 9, 10, 11
DGREEN, TEAL, BLUE, LBLUE = 12, 13, 14, 15

# ------------------------------------------------------------------ blitter
# ``ecran = (ecran AND masque) OR donnees`` (asm L15771) :
#   bit de masque 0 -> pixel entierement reecrit (noir si donnees = 0)
#   bit de masque 1 -> arriere-plan conserve (donnees = 0 partout ici)
#
# Les deux lectures ont ete comparees sur l'ecran complet : elles different de
# 128 px sur 64000 (graine 1, fenetre 24,8) parce que qaz.pic est deja noir a
# 97 % sous le losange -> aspect indiscernable. On retient donc la lecture **la
# moins couteuse** : ``donnees = 0 => transparent``, ce qui permet en prime de
# ne plus decoder le masque du tout.
# ``True`` : on decode le masque (comportement exact de la ROM) — uniquement
# utile a ``tools/compare_blit.py``.
OPAQUE_FROM_MASK = False

# Tables de correspondance du pipeline PIL (_decode_blocks). Les images
# converties depuis le mode ``1`` ne contiennent que 0 et 255.
_MUL_LUT = [[0] * 255 + [1 << q] for q in range(4)]   # poids 1 / 2 / 4 / 8
_ALPHA_ON = [0] + [255] * 255                        # donnees != 0 -> opaque
_ALPHA_OFF = [255] + [0] * 255                       # masque a 1 -> transparent
_RGB_LUT_CACHE: dict[tuple, list[int]] = {}


def _rgb_lut(pal: list[tuple[int, int, int]]) -> list[int]:
    """Table 768 entrees pour ``Image.point(lut, mode="RGB")``.

    Pillow lit cette table **par bandes** (les 256 valeurs de R, puis celles de
    G, puis celles de B) et non entrelacees.
    """
    key = tuple(pal)
    lut = _RGB_LUT_CACHE.get(key)
    if lut is None:
        lut = [pal[v & 15][band]
               for band in range(3) for v in range(256)]
        _RGB_LUT_CACHE[key] = lut
    return lut


def rgb4(word: int) -> tuple[int, int, int]:
    """Mot de couleur Amiga $0RGB (4 bits/canal) -> RGB 8 bits."""
    return ((word >> 8 & 15) * 17, (word >> 4 & 15) * 17, (word & 15) * 17)


def palette_rgb(words=PALETTE) -> list[tuple[int, int, int]]:
    return [rgb4(w) for w in words]


def _surface(img: Image.Image) -> pygame.Surface:
    """PIL -> pygame.Surface, sans passer par un fichier."""
    return pygame.image.frombytes(img.tobytes(), img.size, img.mode).convert_alpha()


# ------------------------------------------------------------------ tuiles
@lru_cache(maxsize=None)
def _load_land_cached(n: int, mask_opaque: bool):
    for folder in (GAME, DATA):
        p = folder / f"land{n}"
        if p.exists():
            break
    else:
        raise FileNotFoundError(f"land{n} introuvable")
    b = p.read_bytes()
    header = {
        "walk_death": struct.unpack_from(">H", b, 0)[0],
        "population_add": list(struct.unpack_from(">11H", b, 2)),
        "mana_add": list(struct.unpack_from(">11H", b, 24)),
        "weapons_add": list(struct.unpack_from(">11H", b, 46)),
        "battle_add1": list(struct.unpack_from(">11H", b, 68)),
        "battle_add2": list(struct.unpack_from(">3H", b, 90)),
        "map_colour": list(b[96:112]),
        "sprites_no": struct.unpack_from(">H", b, 112)[0],
    }
    body = b[114:]
    return header, tuple(_decode_strip(body, 32, 24, len(body) // 480, 4,
                                      palette_rgb(), mask_opaque))


def load_land(n: int) -> tuple[dict, list[pygame.Surface]]:
    """``land{n}`` : en-tête de 114 octets + 70 tuiles de terrain 32x24.

    Résultat **mis en cache** : créer plusieurs ``Renderer`` ne reclasse rien.
    """
    header, tiles = _load_land_cached(n, OPAQUE_FROM_MASK)
    return header, list(tiles)


def _decode_strip(raw: bytes, w: int, h: int, n: int, pb: int,
                  pal: list[tuple[int, int, int]],
                  mask_opaque: bool = False) -> list[pygame.Surface]:
    """``n`` sprites/tuiles concaténés -> ``n`` surfaces, **en ~12 appels PIL**.

    Les enregistrements sont collés les uns après les autres, ce qui n'est pas un
    hasard : ``land0`` fait 70 tuiles x 24 lignes de 20 octets, donc
    ``len(body)`` octets se lisent d'un coup comme **une seule** image
    ``(20, 24*70)``. Meme chose pour les sprites 16x16 (16 lignes de 10) et
    32x32 (32 lignes de 20 = ``MULU #$0280``, asm L19397).

    ``pb`` = octets par plan et par ligne (4 pour une tuile, 2 pour un sprite).
    Le decodage lui-meme est 100 % PIL, donc en C : chaque plan devient une
    image mode ``1``, est etalee en ``L`` (0/255), multipliee par 1/2/4/8, puis
    les quatre plans sont additionnes — l'addition ne peut pas provoquer de
    retenue puisque chaque plan ne porte qu'un seul bit. Resultat : l'indice
    de couleur 0..15, converti en RGB par une table de correspondance.
    """
    bw = pb * 8
    nblk = max(1, w // bw)
    bstride = pb * 5
    stride = bstride * nblk
    height = h * n
    big = Image.frombytes("L", (stride, height), raw[:stride * height])

    acc = None
    for q in range(4):
        if nblk == 1:                                  # tuile / sprite 16x16
            o = pb + q * pb
            pl = Image.frombytes("1", (bw, height),
                                 big.crop((o, 0, o + pb, height)).tobytes())
            pl = pl.convert("L").point(_MUL_LUT[q])
        else:                                          # sprite 32x32
            im = Image.new("L", (w, height), 0)
            for b in range(nblk):
                o = b * bstride + pb + q * pb
                pl = Image.frombytes("1", (bw, height),
                                     big.crop((o, 0, o + pb, height)).tobytes())
                im.paste(pl.convert("L").point(_MUL_LUT[q]), (b * bw, 0))
            pl = im
        acc = pl if acc is None else ImageChops.add(acc, pl)

    if mask_opaque:
        al = Image.new("L", (w, height), 255)
        for b in range(nblk):
            o = b * bstride
            m = Image.frombytes("1", (bw, height),
                                big.crop((o, 0, o + pb, height)).tobytes())
            al.paste(m.convert("L").point(_ALPHA_OFF), (b * bw, 0))
        alpha = al
    else:
        alpha = acc.point(_ALPHA_ON)

    rgb = acc.point(_rgb_lut(pal), "RGB")
    rgb.putalpha(alpha)
    out = []
    for k in range(n):
        y0 = k * h
        out.append(pygame.image.frombytes(
            rgb.crop((0, y0, w, y0 + h)).tobytes(), (w, h), "RGBA").convert_alpha())
    return out


def _decode_blocks(raw: bytes, w: int, h: int, pb: int,
                   pal: list[tuple[int, int, int]],
                   mask_opaque: bool = False) -> pygame.Surface:
    """Une seule tuile/sprite (voir ``_decode_strip``)."""
    return _decode_strip(raw, w, h, 1, pb, pal, mask_opaque)[0]


def _masked_tile(d: bytes, w: int, h: int, mask_bytes: int,
                 pal: list[tuple[int, int, int]]) -> pygame.Surface:
    """Lignes [masque][4 plans] big-endian -> surface RGBA (24 x 32 px).

    ``mask_bytes`` est compté **en mots** : 2 mots = 4 octets pour une tuile de
    terrain, soit 4 + 4x4 = 20 octets/ligne x 24 lignes = 480 octets.
    """
    return _decode_strip(d, w, h, 1, mask_bytes * 2, pal, OPAQUE_FROM_MASK)[0]


# ----------------------------------------------------------------- sprites
@lru_cache(maxsize=None)
def _load_sprites_cached(name: str, w: int, h: int, mask_opaque: bool):
    for folder in (GAME, DATA):
        p = folder / name
        if p.exists():
            break
    else:
        raise FileNotFoundError(name)
    b = p.read_bytes()
    rec = (w // 16) * 10 * h         # un bloc de 16 px = masque.w + 4 mots
    return tuple(_decode_strip(b, w, h, len(b) // rec, 2,
                               palette_rgb(), mask_opaque))


def load_sprites(name: str, w: int = 16, h: int = 16) -> list[pygame.Surface]:
    """``sprites0.dat``/``sprites4.dat`` (16x16) ou ``spr_320.dat`` (32x32).

    Résultat **mis en cache** (voir ``load_land``).
    """
    return list(_load_sprites_cached(name, w, h, OPAQUE_FROM_MASK))


# ------------------------------------------------------------------- bouches
def load_mouths() -> list[pygame.Surface]:
    """6 images de 48x35 px (animations du portrait du Seigneur)."""
    p = (GAME / "mouths.pic")
    if not p.exists():
        p = DATA / "mouths.pic"
    b = p.read_bytes()
    pal = palette_rgb()
    out = []
    for k in range(len(b) // 840):
        d = b[k * 840:(k + 1) * 840]
        img = Image.new("RGBA", (48, 35), (0, 0, 0, 0))
        px = img.load()
        for y in range(35):
            base = y * 24
            for x in range(48):
                bi, bit = x // 8, 7 - x % 8
                idx = 0
                for q in range(4):
                    if d[base + q * 6 + bi] >> bit & 1:
                        idx |= 1 << q
                if idx:
                    px[x, y] = (*pal[idx], 255)
        out.append(_surface(img))
    return out


# -------------------------------------------------------------------- .pic
def load_pic(name: str, planes: int = 4) -> pygame.Surface:
    """Image plein ecran 320x200 (plans dedies) avec sa palette si presente."""
    for folder in (GAME, DATA):
        p = folder / name
        if p.exists():
            break
    else:
        raise FileNotFoundError(name)
    b = p.read_bytes()
    total = 320 * 200 // 8 * planes            # 32000 (4 plans) / 40000 (5)
    ncol = 1 << planes
    if len(b) >= total + ncol * 2:
        pal_words = list(struct.unpack_from(f">{ncol}H", b, total))
    elif planes >= 5:                          # load.pic : 32 mots de palette
        pal_words = list(struct.unpack_from(">32H", b, 40000))
    else:
        pal_words = PALETTE
    img = Image.new("P", (320, 200))
    px = img.load()
    rb, ps = 40, 8000
    for y in range(200):
        for x in range(320):
            bi, bit = x // 8, 7 - x % 8
            idx = 0
            for q in range(planes):
                off = q * ps + y * rb + bi
                if off < total and (b[off] >> bit) & 1:
                    idx |= 1 << q
            px[x, y] = idx
    flat = []
    for w in pal_words:
        flat += list(rgb4(w))
    flat += flat[:3] * (768 - len(flat))
    img.putpalette(flat[:768])
    return _surface(img.convert("RGBA"))


def load_portrait() -> pygame.Surface:
    """lord.pic : portrait 320x200 + 16 mots de palette."""
    return load_pic("lord.pic", planes=4)


# ------------------------------------------------------------------- icones
# ``_icon_data`` (asm L21656, adresse $4E4C6) : 30 icones de 16x16, 4 plans,
# 128 octets chacune (16 lignes x [p0][p1][p2][p3]). L'offset d'une icone est
# ``icone * 128`` — c'est exactement le ``LSL.W #7,D4`` de ``_draw_icon``
# (asm L19196). Elles sont extraites par ``tools/extract_icon_data.py``, qui
# ecrit aussi la grille d'indices de palette de chacune dans
# ``assets/icons/icon_NN.json``.

ICON_COUNT = 30
ICON_W = ICON_H = 16
_ICON_DIR = ROOT / "assets" / "icons"


@lru_cache(maxsize=1)
def icon_grids() -> tuple[tuple[tuple[int, ...], ...], ...]:
    """Les 30 grilles d'indices de palette, lues depuis les JSON extraits."""
    out = []
    for i in range(ICON_COUNT):
        p = _ICON_DIR / ("icon_%02d.json" % i)
        with open(p, encoding="utf-8") as f:
            out.append(tuple(tuple(row) for row in json.load(f)))
    return tuple(out)


@lru_cache(maxsize=ICON_COUNT)
def load_icon(index: int, opaque: bool = False) -> pygame.Surface:
    """Une icone 16x16 de l'interface, en couleurs de la palette du jeu.

    ``_draw_icon`` (asm L19184) ecrase les 4 plans **sans mot de masque** :
    avec ``opaque=True`` on rend donc aussi les pixels d'indice 0, comme
    l'original. Avec ``opaque=False`` (defaut) ils sont transparents, ce qui
    est pratique pour superposer une icone sur un decor.
    """
    grid = icon_grids()[index]
    img = Image.new("RGBA", (ICON_W, ICON_H), (0, 0, 0, 0))
    px = img.load()
    pal = palette_rgb()
    for y in range(ICON_H):
        row = grid[y]
        for x in range(ICON_W):
            v = row[x]
            if v or opaque:
                px[x, y] = pal[v] + (255,)
    return _surface(img)


@lru_cache(maxsize=1)
def _palette_index() -> dict[tuple[int, int, int], int]:
    """Table inverse ``couleur RGB -> indice de palette``.

    Indispensable pour ``_draw_bar`` : l'asm travaille sur les octets de plan,
    c'est-a-dire sur les **indices** 0..15, alors que notre surface est en
    RVB. Sans cette table on ne peut pas relire l'indice courant d'un pixel
    pour lui appliquer le ``ORI #$3c`` / ``ANDI #$c3`` de l'original.
    """
    pal = palette_rgb()
    return {tuple(c): i for i, c in enumerate(pal)}


# -------------------------------------------------------------------- font
class Font:
    """Police 8x8 du jeu (font.dat / _font_data), glyphe = 40 octets."""

    def __init__(self):
        p = GAME / "font.dat"
        if not p.exists():
            p = DATA / "font.dat"
        self.raw = p.read_bytes()
        self._cache: dict[int, pygame.Surface] = {}
        self._masks: dict[int, pygame.Surface] = {}
        self.glyphs = len(self.raw) // 40

    def mask(self, code: int) -> pygame.Surface:
        """Glyphe blanc sur fond transparent (pour le recolorer)."""
        if code in self._masks:
            return self._masks[code]
        i = (code - 32) * 40
        d = self.raw[i:i + 40]
        img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        px = img.load()
        for y in range(8):
            base = y * 5
            for x in range(8):
                v = 0
                for q in range(4):
                    if d[base + 1 + q] >> (7 - x) & 1:
                        v |= 1 << q
                if v:
                    px[x, y] = (255, 255, 255, 255)
        s = _surface(img)
        self._masks[code] = s
        return s

    def glyph(self, code: int, color: tuple[int, int, int] | None = None
              ) -> pygame.Surface:
        """Glyphe colore (par defaut : couleurs d'origine du jeu)."""
        key = code if color is None else (code, color)
        if key in self._cache:
            return self._cache[key]
        if color is None:
            i = (code - 32) * 40
            d = self.raw[i:i + 40]
            img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
            px = img.load()
            pal = palette_rgb()
            for y in range(8):
                base = y * 5
                for x in range(8):
                    idx = 0
                    for q in range(4):
                        if d[base + 1 + q] >> (7 - x) & 1:
                            idx |= 1 << q
                    if idx:
                        px[x, y] = (*pal[idx], 255)
            s = _surface(img)
        else:
            s = self.mask(code).copy()
            s.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MAX)
        self._cache[key] = s
        return s

    def draw(self, dest: pygame.Surface, text: str, pos, color=None,
             spacing: int = 0) -> pygame.Rect:
        """Ecrit ``text`` (\\n pour le retour a la ligne) sur ``dest``."""
        x0, y = pos
        x, w, h = x0, 0, 8
        for ch in text:
            if ch == "\n":
                x, y = x0, y + 8
                h += 8
                continue
            if ch != " ":
                dest.blit(self.glyph(ord(ch), color), (x, y))
            x += 8 + spacing
            w = max(w, x - x0)
        return pygame.Rect(x0, y, w, h)


def text_width(text: str, spacing: int = 0) -> int:
    longest = max((len(s) for s in text.split("\n")), default=0)
    return longest * (8 + spacing)


# Instance partagee de la police : `_text` (asm L19973) ecrit
# les glyphes directement dans l'ecran 4 bitplans.
FONT = Font()
