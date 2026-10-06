"""Liste triee des symboles de la desassemblage (utile comme index)."""
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else r"S:\OpenCode\Populous\reference\tetracorp\populous_prg.cnf"
syms = []
for line in open(path, encoding="latin-1"):
    m = re.match(r"SYMBOL (\S+) \$([0-9A-Fa-f]+)", line)
    if m:
        syms.append((int(m.group(2), 16), m.group(1)))
syms.sort()
print("total", len(syms))
for a, n in syms:
    print("%06X %s" % (a, n))
