"""Decompresse le petit stub ``populous.prg`` (descompresseur LZ ecrit a l'envers).

Le fichier est un hunk de 360 octets : ~0xE8 octets de code + un flux compresse
qui se decompresse vers 0x7F000 puis ``jmp $7f000``. On reimplemente ce code en
Python pour recuperer le second stade (il indique comment le vrai jeu est charge).
"""
import struct
import sys

PATH = r"S:\OpenCode\Populous\reference\original\extracted\populous.prg"
OUT = r"S:\OpenCode\Populous\disasm\populous_stage2.bin"

b = open(PATH, "rb").read()
i = 4                                    # magic
nlen = struct.unpack_from(">i", b, i)[0]; i += 4 + abs(nlen) * 4
tab, first, last = struct.unpack_from(">iii", b, i); i += 12 + 4 * tab
assert struct.unpack_from(">I", b, i)[0] == 0x3E9
i += 4
n = struct.unpack_from(">I", b, i)[0]; i += 4
code = b[i:i + n * 4]

d0, d1, d5 = struct.unpack_from(">iii", code, 0xE8)
d0 &= 0xFFFFFFFF
d1 &= 0xFFFFFFFF
d5 &= 0xFFFFFFFF
print("src len %d, dst len %d, xor %08x" % (d0, d1, d5))

a0 = 0xF4 + d0                 # fin du flux compresse (dans `code`)
a2 = d1                        # fin de la zone de sortie
a1 = 0
dst = bytearray(d1)


def rd_long():
    global a0
    a0 -= 4
    return struct.unpack_from(">I", code, a0)[0]


d0reg = rd_long() ^ d5 if False else (rd_long() ^ 0)  # eor.l d0,d5 -> d5 ^= d0
# (l'instruction eor.l d0,d5 met a jour d5, pas d0)
d5 ^= d0reg if False else 0
# on refait proprement :
a0 = 0xF4 + d0
d5v = d5
L = rd_long()
d5v ^= L
d0reg = L

x = 0
steps = 0


def get_bit():
    """Consomme un bit (lsr d0 ; si d0 tombe a 0 : rechargement qui jette le bit)."""
    global d0reg, x, d5v
    carry = d0reg & 1
    d0reg >>= 1
    if d0reg == 0:
        new = rd_long()
        d5v ^= new
        x = 1
        carry = new & 1
        d0reg = (new >> 1) | 0x80000000
    else:
        x = carry
    return carry


def read_bits(n):
    """bsr $100ce : lit n bits, poids fort d'abord, dans d2 (mot bas)."""
    global d0reg, x
    v = 0
    for _ in range(n):
        c = get_bit()
        v = ((v << 1) | c) & 0xFFFF
    return v


while a2 > a1:
    steps += 1
    if steps > 100000:
        raise SystemExit("boucle infinie")
    if get_bit() == 0:
        # --- suite d'octets littéraux ---
        if get_bit() == 1:
            n = read_bits(8)          # recopie courte : distance sur 8 bits, 2 octets
            ln = 2
            for _ in range(ln):
                a2 -= 1
                dst[a2] = dst[(a2 + n) & 0xFFFFFFFF if (a2 + n) >= d1 else a2 + n]
            continue
        cnt = read_bits(3)
        for _ in range(cnt + 1):
            byte = 0
            for _ in range(8):
                byte = ((byte << 1) | get_bit()) & 0xFF
            a2 -= 1
            dst[a2] = byte
    else:
        # --- motif (match) ---
        sel = read_bits(2)
        if sel == 3:
            cnt = read_bits(8) + 8
            for _ in range(cnt + 1):
                byte = 0
                for _ in range(8):
                    byte = ((byte << 1) | get_bit()) & 0xFF
                a2 -= 1
                dst[a2] = byte
            continue
        if sel == 2:
            ln = read_bits(8)
            dist = read_bits(12)
            ln = ln + 1
        else:                            # 0 ou 1
            dist = read_bits(9 + sel)
            ln = sel + 2 + 1
        for _ in range(ln):
            a2 -= 1
            src = a2 + dist
            dst[a2] = dst[src] if 0 <= src < d1 else 0

print("etapes:", steps, "d5 final: %08x (0 = checksum ok)" % (d5v & 0xFFFFFFFF))
print("a0 final: 0x%X (fin 0x%X)" % (a0, 0xF4 + d0))
open(OUT, "wb").write(bytes(dst))
print("ecrit:", OUT, len(dst), "octets")
print(bytes(dst).hex(" "))
