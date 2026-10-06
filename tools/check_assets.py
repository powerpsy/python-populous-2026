"""Verifie que le pipeline PIL de ``assets._decode_blocks`` est identique a la
transcription naive (boucle Python), pixel par pixel, sur **tous** les fichiers.

    python tools\\check_assets.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from populous import assets  # noqa: E402
from PIL import Image  # noqa: E402


def slow_blocks(raw: bytes, w: int, h: int, pb: int,
                pal) -> Image.Image:
    """Reference : boucle Python explicite (variante donnees nulles)."""
    bw = pb * 8
    nblk = max(1, w // bw)
    bstride = pb * 5
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y in range(h):
        base = y * bstride * nblk          # blocs entrelaces sur la ligne
        for c in range(nblk):
            o = base + c * bstride
            planes = [int.from_bytes(raw[o + pb + q * pb: o + 2 * pb + q * pb],
                                     "big") for q in range(4)]
            for x in range(bw):
                bp = bw - 1 - x
                if not any(p >> bp & 1 for p in planes):
                    continue
                idx = 0
                for q in range(4):
                    if planes[q] >> bp & 1:
                        idx |= 1 << q
                px[c * bw + x, y] = (*pal[idx], 255)
    return img


def check(raw: bytes, w: int, h: int, pb: int, pal) -> int:
    """Un enregistrement compare au pipeline et a la reference naive."""
    fast = assets._decode_strip(raw, w, h, 1, pb, pal, False)[0]
    ref = assets._surface(slow_blocks(raw, w, h, pb, pal))
    a = pygame.image.tostring(fast, "RGBA")
    b = pygame.image.tostring(ref, "RGBA")
    return sum(1 for i in range(w * h)
               if a[i * 4:i * 4 + 4] != b[i * 4:i * 4 + 4])


def main() -> None:
    pygame.init()
    pygame.display.set_mode((320, 200))
    pal = assets.palette_rgb()
    total_bad = 0

    for n in range(5):
        p = assets.GAME / ("land%d" % n)
        if not p.exists():
            continue
        body = p.read_bytes()[114:]
        ntiles = len(body) // 480
        fast = assets._decode_strip(body, 32, 24, ntiles, 4, pal, False)
        bad = 0
        for i in range(ntiles):
            ref = assets._surface(slow_blocks(body[i * 480:(i + 1) * 480],
                                              32, 24, 4, pal))
            a = pygame.image.tostring(fast[i], "RGBA")
            b = pygame.image.tostring(ref, "RGBA")
            bad += sum(1 for k in range(32 * 24)
                       if a[k * 4:k * 4 + 4] != b[k * 4:k * 4 + 4])
        print("land%d : %d tuiles, %d pixel(s) different(s)" % (n, ntiles, bad))
        total_bad += bad

    for name, w, h, pb in (("sprites0.dat", 16, 16, 2),
                           ("sprites4.dat", 16, 16, 2),
                           ("spr_320.dat", 32, 32, 2)):
        src = None
        for folder in (assets.GAME, assets.DATA):
            if (folder / name).exists():
                src = folder / name
                break
        if src is None:
            print("%s : absent" % name)
            continue
        b = src.read_bytes()
        rec = (w // 16) * 10 * h
        cnt = len(b) // rec
        fast = assets._decode_strip(b, w, h, cnt, pb, pal, False)
        bad = 0
        for k in range(cnt):
            bad += check(b[k * rec:(k + 1) * rec], w, h, pb, pal)
        print("%s : %d sprites, %d pixel(s) different(s)" % (name, cnt, bad))
        total_bad += bad

    loads = (("load_land(0)", lambda: assets.load_land(0)),
             ("load_sprites(sprites0.dat)",
              lambda: assets.load_sprites("sprites0.dat")),
             ("load_sprites(sprites4.dat)",
              lambda: assets.load_sprites("sprites4.dat")))

    print()
    print("chronometre :")
    for label, fn in loads:
        assets._load_land_cached.cache_clear()
        assets._load_sprites_cached.cache_clear()
        t = time.perf_counter()
        fn()
        cold = (time.perf_counter() - t) * 1000
        t = time.perf_counter()
        for _ in range(200):
            fn()
        warm = (time.perf_counter() - t) * 1000 / 200
        print("  %-28s %6.2f ms a froid   %6.4f ms en cache"
              % (label, cold, warm))

    print()
    print("=> %s" % ("OK" if total_bad == 0 else "ECART (%d)" % total_bad))


if __name__ == "__main__":
    main()