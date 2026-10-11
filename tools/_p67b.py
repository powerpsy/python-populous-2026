# -*- coding: utf-8 -*-
"""Phase 67 (suite) : `_check_cancel` + la vraie signature de `_requester`."""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
ENC = "utf-8"


def load(p):
    with io.open(p, "r", encoding=ENC) as f:
        return f.read().splitlines(True)


def save(p, lines):
    with io.open(p, "w", encoding=ENC, newline="") as f:
        f.write("".join(lines))


g = load("populous/game.py")

i = [k for k, l in enumerate(g)
     if "    def _palette_magnet(self, up: int, vp: int, d0: int) -> None:" in l]
if len(i) != 1:
    raise SystemExit("ancre _palette_magnet : %d occurrences" % len(i))
cible = i[0]

g[cible:cible] = [
    "    def check_cancel(self, ok, cancel) -> int:\n",
    "        \"\"\"``_check_cancel(end_ok, end_cancel)`` (L12106-12159).\n",
    "\n",
    "        Les deux arguments sont des **structures de trois mots** :\n",
    "        ``(x0, y0, x1)``. Rien n'est compare a `x1` autrement que comme\n",
    "        borne droite, et la borne basse est `y0`, la haute `y0 + $10` :\n",
    "        une bande de 16 px (L12124-12129 / L12149-12154).\n",
    "\n",
    "        Retour :\n",
    "\n",
    "        * `0` si ``_left_button != 0`` - pas de clic (L12108-12109) -\n",
    "          ou si aucun cadre n'est touche ;\n",
    "        * `1` si la souris est dans le cadre OK ;\n",
    "        * `2` si elle est dans le cadre CANCEL.\n",
    "\n",
    "        L'ordre des **deux** tests est celui du listing : OK d'abord\n",
    "        (L12110), CANCEL ensuite (L12135), et un cadre nul est saute.\n",
    "        \"\"\"\n",
    "        if self.left_button != 0:                 # L12108-12109\n",
    "            return 0\n",
    "        mx, my = self.mouse\n",
    "        for code, box in ((1, ok), (2, cancel)):  # L12110 / L12135\n",
    "            if box is None:                       # TST.L / BEQ\n",
    "                continue\n",
    "            x0, y0, x1 = box\n",
    "            if mx < x0 or mx > x1:                # L12113-12119\n",
    "                continue\n",
    "            if my < y0 or my > y0 + 0x10:         # L12120-12129\n",
    "                continue\n",
    "            return code                           # L12130 / L12155\n",
    "        return 0                                  # L12157-12158\n",
    "\n",
]

save("populous/game.py", g)
print("ecrit : populous/game.py (%d lignes)" % len(g))

# --------------------------------------------- correction de `_requester` --
r = load("populous/game.py")
j = [k for k, l in enumerate(r)
     if "    def requester(self, x: int, y: int, largeur: int, hauteur: int," in l]
if len(j) != 1:
    raise SystemExit("ancre requester : %d occurrences" % len(j))
j = j[0]
for k in range(j, j + 6):
    print("   ", r[k].rstrip())
