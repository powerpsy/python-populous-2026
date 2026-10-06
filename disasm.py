"""
Desassembleur 68000 pour executables Amiga (format hunk)
--------------------------------------------------------
Produit une liste commentee pour chaque executable du disque.

Format hunk (big-endian, longs de 4 octets) :
  HUNK_HEADER (0x3F3) : magic, nom (len en longs + chars),
                        table_size, first_hunk, last_hunk,
                        hunk_sizes[table_size]
  HUNK_CODE  (0x3E9) : size (en longs) + code
  HUNK_DATA  (0x3EA) : size + donnees
  HUNK_BSS   (0x3EB) : size (sans donnees)
  HUNK_RELOC32 (0x3EC) : blocs {count, hunk, count offsets} termine par 0
  HUNK_SYMBOL (0x3F0) : symboles locaux
  HUNK_DEBUG (0x3F1) : donnees de debug
  HUNK_END   (0x3F2) : fin de hunk

Chaque hunk est charge a une adresse logique synthetique
(hunk i a 0x00010000 + i*0x00100000). Les relocations 32 bits sont
appliquees afin que les references absolues soient justes dans le
listing : la valeur stockee est l'index du hunk cible, on lui ajoute
la base de charge de ce hunk.
"""
import os
import re
import struct

import capstone

HUNK_CODE = 0x3E9
HUNK_DATA = 0x3EA
HUNK_BSS = 0x3EB
HUNK_RELOC32 = 0x3EC
HUNK_RELOC16 = 0x3ED
HUNK_RELOC8 = 0x3EE
HUNK_EXT = 0x3EF
HUNK_SYMBOL = 0x3F0
HUNK_DEBUG = 0x3F1
HUNK_END = 0x3F2
HUNK_HEADER = 0x3F3

SRC = r"S:\OpenCode\Populous\extracted"
OUT = r"S:\OpenCode\Populous\disasm"

# Offsets LVO (a6 = base de librairie) rencontres le plus souvent.
# Un "jsr -NNN(a6)" = appel de fonction OS.
LVO = {
    -30: "exec:AllocMem", -36: "exec:FreeMem", -48: "exec:AvailMem",
    -54: "exec:AllocSignal", -60: "exec:FreeSignal",
    -78: "exec:AddPort", -84: "exec:RemovePort",
    -114: "exec:ReplyMsg", -120: "exec:WaitPort",
    -144: "exec:CopyMem", -192: "exec:SumLibrary",
    -198: "exec?/graphics:OwnBlitter", -204: "graphics:DisownBlitter",
    -222: "graphics:WaitTOF?/Examine",
    -240: "graphics:DrawPixel?/RemoveDir",
    -246: "exec:OpenLibrary", -252: "exec:CloseLibrary",
    -258: "exec:OpenDevice", -270: "exec:DoIO",
    -306: "exec:AddIntServer", -312: "exec:RemIntServer",
    -372: "graphics:Text?/FindPort", -378: "graphics:RectFill?/FindTask",
    -420: "exec:AllocVec", -426: "exec:FreeVec",
    -468: "exec:Disable", -474: "exec:Enable",
    -552: "exec:OpenLibrary(-552)?", -630: "graphics:WaitTOF",
    -726: "intuition:ClearDMRequest", -150: "dos:Close",
    -156: "dos:Read", -162: "dos:Write", -180: "dos:Seek",
    -198: "dos:Lock", -204: "dos:Unlock", -222: "dos:Examine",
    -252: "dos:PutStr", -30: "dos:AllocMem?/exec:AllocMem",
}


class Hunk:
    def __init__(self, kind):
        self.kind = kind      # 'code' | 'data' | 'bss'
        self.size = 0         # octets
        self.raw = b""
        self.relocs = []      # [(offset, hunk_num)]
        self.symbols = []     # [(offset, nom)]


def parse_hunk(path):
    b = open(path, "rb").read()
    i = 0

    def rl():
        nonlocal i
        v = struct.unpack(">i", b[i:i + 4])[0]
        i += 4
        return v

    def ru():
        nonlocal i
        v = struct.unpack(">I", b[i:i + 4])[0]
        i += 4
        return v

    if ru() != HUNK_HEADER:
        raise ValueError("pas un fichier hunk")
    nlen = rl()
    name = b[i:i + nlen * 4] if nlen > 0 else b""
    i += max(nlen, 0) * 4
    table_size = rl()
    first = rl()
    last = rl()
    sizes = [ru() for _ in range(table_size)]

    hunks = []
    while i < len(b):
        t = ru()
        if t == HUNK_END:
            continue
        if t not in (HUNK_CODE, HUNK_DATA, HUNK_BSS):
            raise ValueError(f"type de hunk inconnu 0x{t:x} a l'offset {i - 4}")
        n = ru()
        kind = {HUNK_CODE: "code", HUNK_DATA: "data", HUNK_BSS: "bss"}[t]
        h = Hunk(kind)
        h.size = n * 4
        if t != HUNK_BSS:
            h.raw = b[i:i + n * 4]
            i += n * 4
        while True:
            save = i
            if i + 4 > len(b):
                break
            t2 = ru()
            if t2 == HUNK_END:
                break
            if t2 == HUNK_RELOC32:
                while True:
                    cnt = rl()
                    if cnt == 0:
                        break
                    hn = rl()
                    for _ in range(cnt):
                        h.relocs.append((rl(), hn))
            elif t2 in (HUNK_RELOC16, HUNK_RELOC8):
                while True:
                    cnt = rl()
                    if cnt == 0:
                        break
                    rl()
                    for _ in range(cnt):
                        rl()
            elif t2 == HUNK_SYMBOL:
                while True:
                    cnt = rl()
                    if cnt == 0:
                        break
                    sname = b[i:i + cnt * 4].split(b"\0")[0]
                    i += cnt * 4
                    h.symbols.append((rl(), sname.decode("latin-1")))
            elif t2 == HUNK_DEBUG:
                i += rl() * 4
            else:
                i = save
                break
        hunks.append(h)

    return {"name": name.decode("latin-1", "replace"), "first": first,
            "last": last, "sizes": sizes, "hunks": hunks}


def load_bases(parsed):
    bases, addr = [], 0x00010000
    for h in parsed["hunks"]:
        bases.append(addr)
        addr += 0x00100000
    return bases


def apply_relocs(parsed, bases):
    """Retourne des images de hunk reloquees (bytes)."""
    images = []
    for h in parsed["hunks"]:
        img = bytearray(h.raw)
        for off, hn in h.relocs:
            if hn >= len(bases) or off + 4 > len(img):
                continue
            cur = struct.unpack(">I", img[off:off + 4])[0]
            # valeur = index du hunk a ajouter a la reference
            val = (bases[cur] + bases[hn]) & 0xFFFFFFFF if cur < len(bases) else cur
            img[off:off + 4] = struct.pack(">I", val)
        images.append(bytes(img))
    return images


BRANCHES = {
    "bra", "bsr", "bhi", "bls", "bcc", "bcs", "bne", "beq",
    "bvc", "bvs", "bpl", "bmi", "bge", "blt", "bgt", "ble",
    "dbra", "dbf", "dbt", "dbeq", "dbne", "jmp", "jsr",
}


def disassemble(parsed):
    """Desassemble les hunks code avec resynchronisation.

    capstone s'arrete a la premiere instruction invalide ; or un programme
    Amiga contient des donnees (bitmaps, tables) melangees au code. On
    avance donc instruction par instruction : si la decodage echoue, on
    recule de 2 octets et on emet un mot de donnee (dc.w), puis on
    reessaie plus loin. Cela permet de traverser les zones de donnees.
    """
    bases = load_bases(parsed)
    images = apply_relocs(parsed, bases)
    md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_M68K_000)
    out = []
    for idx, h in enumerate(parsed["hunks"]):
        if h.kind != "code":
            continue
        code = images[idx]
        base = bases[idx]
        insns = []
        off = 0
        run_start = None      # debut du bloc d'instructions courant
        while off < len(code):
            got = list(md.disasm(code[off:off + 16], base + off, count=1))
            if got:
                ins = got[0]
                if run_start is None:
                    run_start = off
                insns.append((ins.address, ins.size, ins.mnemonic,
                              ins.op_str, "i"))
                off += ins.size
            else:
                # mot de donnee : on le range dans le flux, on casse le run
                if off + 1 < len(code):
                    val = struct.unpack(">H", code[off:off + 2])[0]
                    insns.append((base + off, 2, "dc.w",
                                  f"0x{val:04x}", "d"))
                    off += 2
                else:
                    break
                run_start = None
        out.append((idx, base, insns))
    return out, bases, images


def annotate(addr, size, mnem, opstr, insns_by_addr, known_labels, strings):
    """Construit le commentaire de fin de ligne."""
    notes = []
    # appel / saut vers une adresse connue
    if mnem in BRANCHES:
        m = re.fullmatch(r"0x([0-9a-f]+)", opstr.strip())
        if m:
            tgt = int(m.group(1), 16)
            if tgt in known_labels:
                notes.append(f"-> {known_labels[tgt]}")
            elif tgt in insns_by_addr:
                notes.append(f"-> loc_{tgt:08x}")
            else:
                notes.append(f"-> hors-code 0x{tgt:x}")
    # appel indirect via LVO : jsr -NNN(a6)
    m = re.fullmatch(r"(-?\d+)\(a6\)", opstr.strip())
    if mnem in ("jsr", "jmp") and m:
        off = int(m.group(1))
        if off in LVO:
            notes.append(LVO[off])
        elif off < 0:
            notes.append(f"LVO {off} inconnu")
    # reference PC-relative : lea XXX(pc),aN  -> chaine cible ?
    if mnem in ("lea", "pea") and "(pc" in opstr:
        m = re.match(r"(-?0x[0-9a-f]+|-?\d+)\(pc", opstr)
        if m:
            disp = int(m.group(1), 0)
            tgt = addr + size + disp
            if tgt in strings:
                notes.append(f"-> chaine {strings[tgt]!r}")
            else:
                notes.append(f"-> 0x{tgt:x}")
    return "; ".join(notes)


def find_strings(images, bases, parsed):
    """Cherche les chaines ASCII imprimables (bornes par des octets
    non-imprimables, longueur >= 4) dans les hunks code/data."""
    found = {}
    for idx, h in enumerate(parsed["hunks"]):
        if h.kind == "bss":
            continue
        blob = images[idx]
        for m in re.finditer(rb"(?:^|[^\x20-\x7e])([\x20-\x7e]{4,})(?:$|[^\x20-\x7e])",
                             blob):
            s = m.group(1).decode("latin-1")
            found[bases[idx] + m.start(1)] = s
    return found


def main():
    os.makedirs(OUT, exist_ok=True)
    targets = ["INTR", os.path.join("l", "Port-Handler"),
               os.path.join("l", "Disk-Validator"),
               os.path.join("l", "Ram-Handler"), "type"]
    for rel in targets:
        path = os.path.join(SRC, rel)
        if not os.path.exists(path):
            print("absent:", rel)
            continue
        try:
            parsed = parse_hunk(path)
        except Exception as exc:
            print(f"{rel}: ERREUR parse: {exc}")
            continue
        dis, bases, images = disassemble(parsed)
        strings = find_strings(images, bases, parsed)

        insns_by_addr = {}
        all_insns = []
        for idx, base, insns in dis:
            for a in insns:
                if a[4] == "i":
                    insns_by_addr[a[0]] = a
                all_insns.append(a)

        # etiquettes : entrees de sous-routine (bsr cible) + symboles hunk
        known_labels = {}
        for idx, h in enumerate(parsed["hunks"]):
            for off, sname in h.symbols:
                known_labels[bases[idx] + off] = sname
        for a, size, mnem, opstr, kind in all_insns:
            if kind == "i" and mnem == "bsr":
                m = re.fullmatch(r"0x([0-9a-f]+)", opstr.strip())
                if m:
                    tgt = int(m.group(1), 16)
                    known_labels.setdefault(tgt, f"sub_{tgt:08x}")

        out_path = os.path.join(OUT, os.path.basename(rel) + ".asm")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"; Fichier      : {rel}\n")
            f.write(f"; Taille       : {os.path.getsize(path)} octets\n")
            f.write(f"; Nom interne  : {parsed['name']!r}\n")
            f.write(f"; Hunks        : {len(parsed['hunks'])} "
                    f"(first={parsed['first']}, last={parsed['last']})\n")
            for idx, h in enumerate(parsed["hunks"]):
                f.write(f";   hunk {idx}: {h.kind:4s} {h.size:6d} octets"
                        f"  relocs={len(h.relocs)}\n")
            f.write(";\n; Desassembly 68000 (capstone), adresses logiques\n")
            f.write("; 0x00010000 + i*0x00100000 par hunk.\n")
            f.write("=" * 78 + "\n\n")

            # table des chaines
            if strings:
                f.write("; --- chaines detectees --------------------------\n")
                for a in sorted(strings):
                    f.write(f";  {a:08x} : {strings[a]!r}\n")
                f.write("\n")

            for idx, base, insns in dis:
                h = parsed["hunks"][idx]
                f.write(f"; ========== HUNK {idx} (code, {h.size} octets) "
                        f"==========\n\n")
                for a, size, mnem, opstr, kind in insns:
                    if a in known_labels:
                        f.write(f"\n{known_labels[a]}:\n")
                    prefix = "  " if kind == "i" else "  * "
                    f.write(f"{prefix}{a:08x}  {mnem:<8s} {opstr}")
                    if kind == "i":
                        note = annotate(a, size, mnem, opstr, insns_by_addr,
                                        known_labels, strings)
                        if a in strings and mnem in ("lea", "pea"):
                            note = (note + " " if note else "") + \
                                   f"chaine={strings[a]!r}"
                    else:
                        note = "donnee (bitmap/table)" if a in strings else ""
                        if a in strings:
                            note += f" {strings[a]!r}"
                    if note:
                        pad = max(1, 52 - (len(mnem) + len(opstr) + 4))
                        f.write(" " * pad + "; " + note)
                    f.write("\n")

                # hunks data : hexdump commente
            for idx, h in enumerate(parsed["hunks"]):
                if h.kind != "data":
                    continue
                f.write(f"\n; ========== HUNK {idx} (data, {h.size} octets) "
                        f"==========\n")
                blob = images[idx]
                for o in range(0, len(blob), 16):
                    chunk = blob[o:o + 16]
                    hx = " ".join(f"{c:02x}" for c in chunk)
                    txt = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
                    f.write(f"  {bases[idx] + o:08x}  {hx:<47s} {txt}\n")
        total = sum(len(x[2]) for x in dis)
        print(f"{rel:22s} -> {out_path}  ({total} instructions, "
              f"{len(strings)} chaines)")


if __name__ == "__main__":
    main()
