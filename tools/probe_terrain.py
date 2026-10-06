"""Reconstitution exacte de la generation de terrain (_make_alt) + rendu ASCII.

Transcription ligne a ligne de reference/tetracorp/populous_prg.asm :
  _clear_map  (L1023) : alt[4225] = 0, map_* = 0
  _make_alt   (L1189) : make_thing(2,4), make_thing(4,2), make_thing(3,3)
  _make_thing (L1208) : marche aleatoire levant le relief
  _raise_point(L1274) : increment + lissage recursif des 8 voisins
  _make_map   (L1420) : alt 2x2 -> map_blk / map_alt
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.setrecursionlimit(20000)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from populous.rng import Rng

# ------------------------------------------------------------------ _alt ----
ALT_W = 65                      # MULS #$41 -> stride 65 (0..64 inclus)
# _alt (4225 mots) est suivi de _map_blk/_map_alt/_map_bk2/_map_steps/_map_who,
# tous encore a zero quand _make_alt tourne : on padde de zeros comme le 68000.
alt = [0] * (ALT_W * ALT_W + 132)
build_count = 0
xmin = xmax = ymin = ymax = 0


def raise_point(x: int, y: int) -> int:
    """_raise_point (asm L1274-1416). Retourne la nouvelle altitude de (x,y).

    Les 8 voisins sont parcourus dans l'ordre E, SE, S, SW, W, NW, N, NE,
    A3 (pointeur de cellule) et D4/D5 (coordonnees) restant synchro'ses.
    """
    global build_count, xmin, xmax, ymin, ymax
    px, py = x, y                          # (8,A5) / ($A,A5) : params d'entree
    if x > 0x40 or x < 0 or y > 0x40 or y < 0:
        return 0
    i = y * ALT_W + x
    if alt[i] >= 8:                       # CMPI #8,(A2) / BGE -> retourne (A2)
        return alt[i]
    build_count += 1
    alt[i] += 1
    d4, d5 = x + 1, y
    a3 = i + 1                            # A3 = A2 + 2 octets (cellule x+1,y)

    def step(delta: int, dd4: int | None, dd5: int | None) -> None:
        """Compare alt[i]-alt[A3] et recursse sur (D4,D5) si > 1."""
        nonlocal a3, d4, d5
        if delta:
            a3 += delta
        if dd4 is not None:
            d4 = dd4
        if dd5 is not None:
            d5 = dd5
        if alt[i] - _cell(a3) > 1:
            raise_point(d4, d5)

    step(0, None, None)                   # E   (x+1, y)
    step(ALT_W, None, y + 1)              # SE  (x+1, y+1)
    step(-1, x, None)                     # S   (x,   y+1)
    step(-1, x - 1, None)                 # SW  (x-1, y+1)
    step(-ALT_W, None, y)                 # W   (x-1, y)
    step(-ALT_W, None, y - 1)             # NW  (x-1, y-1)
    step(1, x, None)                      # N   (x,   y-1)
    step(1, x + 1, None)                  # NE  (x+1, y-1)

    # mise a jour de la boite englobante (parametres d'entree)
    if px < xmin:
        xmin = px
    if px > xmax:
        xmax = px
    if py < ymin:
        ymin = py
    if py > ymax:
        ymax = py
    return alt[i]


def _cell(idx: int) -> int:
    """Lecture hors-table : sur le 68000 cela tombe sur _map_blk (encore nul)."""
    return alt[idx] if 0 <= idx < len(alt) else 0


def make_thing(a: int, b: int, rng: Rng, stats: dict | None = None) -> int:
    """_make_thing (asm L1208-1270)."""
    global x0, y0
    x = rng.below(0x40)
    y = rng.below(0x40)
    iters = 0
    while True:
        iters += 1
        r = raise_point(x, y)
        if r == 6:
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
        if iters > 4_000_000:             # garde-fou (absent du jeu)
            break
    if stats is not None:
        stats["iters"] = stats.get("iters", 0) + iters
    return iters


def make_alt(rng: Rng) -> None:
    """_make_alt (asm L1189-1204)."""
    make_thing(2, 4, rng)
    make_thing(4, 2, rng)
    make_thing(3, 3, rng)


# ------------------------------------------------------------- _make_map ----
def make_map(x0: int, y0: int, x1: int, y1: int,
             map_blk: bytearray, map_alt: bytearray, map_bk2: bytearray,
             map_steps: list[int]) -> None:
    """_make_map (asm L1420-1539) : 2x2 -> pente + altitude."""
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            idx = (y << 6) + x
            i = y * ALT_W + x
            avg = (alt[i + 1] + alt[i + ALT_W] + alt[i + ALT_W + 1] + alt[i]) >> 2
            d6 = 0
            if alt[i] > avg:
                d6 |= 1
            if alt[i + 1] > avg:
                d6 |= 2
            if alt[i + ALT_W + 1] > avg:
                d6 |= 4
            if alt[i + ALT_W] > avg:
                d6 |= 8
            if map_blk[idx] == 0x2F and (d6 != 0 or avg != 0):
                d6 = map_blk[idx]                       # on preserve la case
            else:
                map_blk[idx] = d6
            if avg != 0 and d6 == 0:
                avg -= 1
                d6 = 0x0F
            if avg == 0 and d6 != 0x0F and d6 != 0:
                d6 += 0x10
            map_alt[idx] = avg & 0xFF
            if map_blk[idx] != 0x2F:
                map_blk[idx] = d6 & 0xFF
            elif True:
                d6 = map_blk[idx]
            if d6 == 0:
                map_bk2[idx] = 0
            map_steps[idx] = 0


# ----------------------------------------------------------------- affichage --
SHADE = " .:-=+*#%@"


def show(map_blk: bytearray, map_alt: bytearray) -> None:
    print("   " + "".join(str(x % 10) for x in range(64)))
    for y in range(64):
        row = []
        for x in range(64):
            i = (y << 6) + x
            b, a = map_blk[i], map_alt[i]
            if b == 0:
                row.append("~")
            elif b == 15:
                row.append((".:-=+*#%@"[min(a, 9)] if a else "."))
            elif 16 <= b <= 30:
                row.append(",")
            elif b in (47, 48, 49):
                row.append("R")
            else:
                row.append(str(b % 10))
        print(f"{y:2d} " + "".join(row))


def main() -> None:
    global x0, y0
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    rng = Rng(seed)
    stats: dict = {}
    x0 = y0 = 0
    make_alt(rng)
    land = sum(1 for v in alt if v > 0)
    print(f"seed={seed}  alt>0 : {land}/{len(alt)}  max={max(alt)}  "
          f"build_count={build_count}  box=({xmin},{ymin})-({xmax},{ymax})")
    print("histogramme alt :", {k: alt.count(k) for k in range(0, 9) if alt.count(k)})

    map_blk = bytearray(4096)
    map_alt = bytearray(4096)
    map_bk2 = bytearray(4096)
    map_steps = [0] * 4096
    make_map(0, 0, 0x3F, 0x3F, map_blk, map_alt, map_bk2, map_steps)
    from collections import Counter
    print("map_blk :", dict(sorted(Counter(map_blk).items())))
    print("map_alt :", dict(sorted(Counter(map_alt).items())))
    print("cases constructibles (blk==15) :", sum(1 for b in map_blk if b == 15))
    print("cases eau (blk==0) :", sum(1 for b in map_blk if b == 0))
    show(map_blk, map_alt)


x0 = y0 = 0

if __name__ == "__main__":
    main()
