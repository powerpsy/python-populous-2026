"""Affiche des icones extraites en ASCII pour validation (sans vision d'image)."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(ROOT, "assets", "icons")

SHADES = " .:-=+*#%@"

ids = [int(a) for a in sys.argv[1:]] or list(range(6))
grids = []
for i in ids:
    with open(os.path.join(ICONS, "icon_%02d.json" % i)) as f:
        grids.append(json.load(f))

for row in range(0, len(grids), 6):
    chunk = grids[row:row + 6]
    print("--- icônes %s ---" % ids[row:row + 6])
    for y in range(16):
        line = []
        for g in chunk:
            line.append("".join(SHADES[min(9, g[y][x])] for x in range(16)))
            line.append(" ")
        print(" ".join(line))
    print()
