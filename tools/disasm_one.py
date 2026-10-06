"""Desassemble un executable Amiga et ecrit le listing (voir disasm.py).

Usage : python tools/disasm_one.py <fichier> [sortie.asm]
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from disasm import parse_hunk, disassemble, find_strings  # noqa: E402


def build(path):
    parsed = parse_hunk(path)
    dis, bases, images = disassemble(parsed)
    strings = find_strings(images, bases, parsed)
    return parsed, dis, bases, images, strings


def listing(path, out=None):
    parsed, dis, bases, images, strings = build(path)
    insns_by_addr, all_insns = {}, []
    for idx, base, insns in dis:
        for a in insns:
            if a[4] == "i":
                insns_by_addr[a[0]] = a
            all_insns.append(a)
    known_labels = {}
    for idx, h in enumerate(parsed["hunks"]):
        for off, sname in h.symbols:
            known_labels[bases[idx] + off] = sname
    for a, size, mnem, opstr, kind in all_insns:
        if kind == "i" and mnem in ("bsr", "bra", "jsr", "jmp"):
            import re
            m = re.fullmatch(r"0x([0-9a-f]+)", opstr.strip())
            if m:
                known_labels.setdefault(int(m.group(1), 16), f"sub_{int(m.group(1),16):08x}")

    from disasm import annotate
    lines = []
    lines.append(f"; fichier : {path}  ({os.path.getsize(path)} octets)")
    for idx, h in enumerate(parsed["hunks"]):
        lines.append(f"; hunk {idx}: {h.kind} {h.size} octets")
    lines.append("")
    if strings:
        lines.append("; --- chaines ---")
        for a in sorted(strings):
            lines.append(f";  {a:08x} : {strings[a]!r}")
        lines.append("")
    for idx, base, insns in dis:
        lines.append(f"; ===== HUNK {idx} =====")
        for a, size, mnem, opstr, kind in insns:
            if a in known_labels:
                lines.append(f"\n{known_labels[a]}:")
            prefix = "  " if kind == "i" else "  * "
            note = annotate(a, size, mnem, opstr, insns_by_addr, known_labels,
                            strings) if kind == "i" else ""
            lines.append(f"{prefix}{a:08x}  {mnem:<8s} {opstr}"
                         + (("  ; " + note) if note else ""))
    text = "\n".join(lines) + "\n"
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        print("ecrit:", out, len(text), "octets")
    return text


if __name__ == "__main__":
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + ".asm"
    listing(src, dst)
