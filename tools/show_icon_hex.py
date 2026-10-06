"""Affiche une icone sous forme de grille d'indices hexadecimaux (0..F)."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(ROOT, "assets", "icons")

for arg in sys.argv[1:]:
    i = int(arg)
    with open(os.path.join(ICONS, "icon_%02d.json" % i)) as f:
        g = json.load(f)
    print("=== icone %d ===" % i)
    print("    " + "".join("%X" % (x % 16) for x in range(16)))
    for y, row in enumerate(g):
        print("%3d %s" % (y, "".join("%X" % v for v in row)))
