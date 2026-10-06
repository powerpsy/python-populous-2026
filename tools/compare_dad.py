"""Compare la desassemblage tetracorp avec notre copie du jeu (DAD).

Pour chaque etiquette de fonction, on prend les premiers octets d'instructions
puis on les cherche dans le fichier DAD pour deduire la base de chargement.
"""
import binascii
import re
import sys

ASM = r"S:\OpenCode\Populous\reference\tetracorp\populous_prg.asm"
DAD = r"S:\OpenCode\Populous\reference\original\extracted\DAD"

dad = open(DAD, "rb").read()

# 1) recolte (etiquette, adresse, octets) dans la desassemblage
entries = []
lines = open(ASM, encoding="latin-1").read().split("\n")
for i, line in enumerate(lines):
    m = re.match(r"^(_?[A-Za-z_][\w]*):\s*$", line)
    if not m:
        continue
    # ligne suivante contenant ";aaaa: hh hh hh"
    for j in range(i + 1, min(i + 4, len(lines))):
        m2 = re.search(r";([0-9a-f]{4,6}):\s+((?:[0-9a-f]{2}\s*)+)", lines[j])
        if m2:
            addr = int(m2.group(1), 16)
            raw = binascii.unhexlify(re.sub(r"\s", "", m2.group(2))[:16])
            entries.append((m.group(1), addr, raw))
            break

print("fonctions reperees:", len(entries))

hits = {}
for name, addr, raw in entries:
    # on evite les sequences trop generiques (LINK #0 / MOVEM...)
    pat = raw[:8] if len(raw) >= 8 else raw
    found = []
    start = 0
    while True:
        k = dad.find(pat, start)
        if k < 0:
            break
        found.append(k)
        start = k + 1
        if len(found) > 4:
            break
    if len(found) == 1:
        hits.setdefault(addr - found[0], []).append(name)

if not hits:
    print("aucune correspondance unique")
    sys.exit(0)

print("bases deduites (base -> nombre de fonctions) :")
for base, names in sorted(hits.items(), key=lambda kv: -len(kv[1])):
    print("  0x%06X  %3d  %s" % (base, len(names), ", ".join(names[:8])))

total = sum(len(v) for v in hits.values())
best = max(hits.items(), key=lambda kv: len(kv[1]))
print("total uniques:", total, "| meilleure base 0x%06X avec %d" % (best[0], len(best[1])))

# 2) ou commence la derive ?
base = best[0]
print("\nfonctions dont l'adresse sous cette base ne correspond pas :")
bad = 0
for name, addr, raw in entries:
    pat = raw[:8] if len(raw) >= 8 else raw
    off = addr - base
    if off < 0 or off >= len(dad) or dad[off:off + len(pat)] != pat:
        bad += 1
        if bad <= 40:
            print("  %-24s asm=0x%06X off=0x%X" % (name, addr, off))
print("total non alignes:", bad, "/", len(entries))
