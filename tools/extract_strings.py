"""Extrait toutes les chaines en dur du listing tetracorp.

Chaque ``DC.B "TEXTE",0`` devient une entree indexee par son adresse, ce qui
permet ensuite de retrouver le texte d'un appel a ``_text`` ou ``_requester``
en relisant l'asm.

Usage::

    python tools/extract_strings.py            -> ecrit assets/strings.json
    python tools/extract_strings.py --grep X   -> affiche les chaines contenant X
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASM = ROOT / "reference" / "tetracorp" / "populous_prg.asm"
OUT = ROOT / "assets" / "strings.json"

# DC.B "texte",0   et   DC.B $xx,$xx,... (que l'on ignore)
RE_STR = re.compile(r'^(LAB_\w+|_end_cancel|_game_name\w*):\s*$')
RE_DC = re.compile(r'^\s*DC\.B\s+"([^"]*)",\s*0\s*$')


def parse() -> dict[str, str]:
    lines = ASM.read_text(encoding="latin-1").split("\n")
    out: dict[str, str] = {}
    label = None
    for line in lines:
        m = RE_STR.match(line)
        if m:
            label = m.group(1)
            continue
        if label is None:
            continue
        m = RE_DC.match(line)
        if m:
            out[label] = m.group(1)
            label = None
    return out


def main() -> int:
    chaines = parse()
    if "--grep" in sys.argv:
        mot = sys.argv[sys.argv.index("--grep") + 1].upper()
        for k, v in sorted(chaines.items()):
            if mot in v.upper():
                print("%-14s %r" % (k, v))
        return 0
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(chaines, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print("%d chaines extraites -> %s" % (len(chaines), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())