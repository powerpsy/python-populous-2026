"""Compose une planche de controle de tous les graphiques recharges en Python."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402
from populous import assets  # noqa: E402

pygame.init()
pygame.display.set_mode((320, 200))

W, H = 660, 500
surf = pygame.Surface((W, H))
surf.fill((30, 30, 30))
font = assets.Font()
yellow = assets.palette_rgb()[assets.YELLOW]
lblue = assets.palette_rgb()[assets.LBLUE]

y = 4
for n in (0, 4):
    header, tiles = assets.load_land(n)
    font.draw(surf, f"land{n} : {len(tiles)} tuiles 32x24  "
                    f"sprites_no={header['sprites_no']}", (4, y), yellow)
    y += 10
    for i, t in enumerate(tiles):
        surf.blit(t, (4 + (i % 16) * 34, y + (i // 16) * 26))
    y += ((len(tiles) + 15) // 16) * 26 + 6

spr = assets.load_sprites("sprites0.dat")
for i, s in enumerate(spr[:96]):
    surf.blit(s, (4 + (i % 24) * 18, y + (i // 24) * 18))
y += ((96 + 23) // 24) * 18 + 6

for i, s in enumerate(assets.load_sprites("spr_320.dat", 32, 32)):
    surf.blit(s, (4 + i * 36, y))
y += 40

font.draw(surf, "POPULOUS 12345 !?", (4, y), None)
font.draw(surf, "Population: 34  Manna: 876  Level 42", (4, y + 10), yellow)
font.draw(surf, "Settle / Fight / Gather Together", (4, y + 20), lblue)
y += 34

for i, m in enumerate(assets.load_mouths()):
    surf.blit(m, (4 + i * 52, y))
y += 40

out = os.path.join(ROOT, "out_preview")
os.makedirs(out, exist_ok=True)
pygame.image.save(surf, os.path.join(out, "assets_preview.png"))
print("ok", W, H, "hauteur utilisee", y)
