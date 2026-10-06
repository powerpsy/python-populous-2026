"""Inspecte un ADF : OFS ou FFS, rootblock, en-tetes de fichiers."""
import struct
import sys

BS = 512


def s32(b, o):
    return struct.unpack(">i", b[o:o + 4])[0]


def u32(b, o):
    return struct.unpack(">I", b[o:o + 4])[0]


def main(path):
    data = open(path, "rb").read()
    nb = len(data) // BS
    print(f"{path}: {len(data)} octets, {nb} blocs")
    print("bootblock[0:8]:", data[:8].hex(" "), data[:8])

    # rootblock : on scanne les types
    types = {}
    for n in range(nb):
        b = data[n * BS:(n + 1) * BS]
        t = s32(b, 0)
        types[t] = types.get(t, 0) + 1
        if t == 1:  # root
            hs = s32(b, 12)
            print(f"  rootblock={n} hash_size={hs} checksum_ok="
                  f"{sum(struct.unpack('>128i', b)) % 2**32 == 0}")

    print("histogramme des types primaires :", sorted(types.items()))

    # en-tetes de fichiers (type 2, secondaire -3)
    print("\nen-tetes type 2 avec sec=-3 :")
    for n in range(nb):
        b = data[n * BS:(n + 1) * BS]
        if s32(b, 0) != 2:
            continue
        sec = s32(b, 508)
        if sec != -3:
            continue
        namelen = b[432]
        name = b[433:433 + namelen].decode("latin-1", "replace")
        high = s32(b, 8)
        first = s32(b, 16)
        size = u32(b, 324)
        table = [s32(b, 24 + 4 * i) for i in range(72)]
        nz = [(71 - i, v) for i, v in enumerate(table) if v]
        # contenu du 1er bloc de donnees (OFS = type 8, FFS = brut)
        blk_type = None
        if first > 0:
            blk_type = s32(data[first * BS:(first + 1) * BS], 0)
        print(f"  #{n:4d} {name:24s} size={size:8d} high_seq={high:3d} "
              f"first={first}(type {blk_type}) ntable={len(nz)} "
              f"slots={nz[:3]}...{nz[-1:] if nz else ''}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else
         r"S:\OpenCode\Populous\reference\original\game\populous.adf")
