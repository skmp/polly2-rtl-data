#!/usr/bin/env python3
"""PVR core dumps (.pvrdmp), the one-file form of a dump: what nulldc3 writes with its dump key and with a script's
"dump" (nulldc3 libswirl/hw/pvr/pvr_coredump.h).

    "pvrcoredump"     the 11 bytes of this cookie, ASCII
    gzip member       video memory in 32 bit area order: 8 MB (Dreamcast) or 16 MB (NAOMI); the size is what it
                      inflates to
    gzip member       the PVR register file, 8 KB (0x005F8000-0x005F9FFF)

The members are, byte for byte, the vram_<scene>.bin and pvr_regs_<scene>.bin of the older dumps beside them.

    python3 pvrdmp.py info <file.pvrdmp>...
    python3 pvrdmp.py unpack <file.pvrdmp>... [--to <folder>]   -> vram_<scene>.bin, pvr_regs_<scene>.bin
    python3 pvrdmp.py pack <scene> [--from <folder>] [--to <folder>]   vram_<scene>.bin + pvr_regs_<scene>.bin -> <scene>.pvrdmp

<scene> is the file's name without .pvrdmp. The folders default to the one the file is in (unpack) and to dumps/
beside this script (pack). refsw3-offline renders one directly: refsw3-offline --dump <file.pvrdmp> [png], or
-c "pvrdmp <file>; ...".
"""
import gzip
import os
import struct
import sys
import zlib

COOKIE = b"pvrcoredump"
VRAM_SIZES = (8 << 20, 16 << 20)
REGS_SIZE = 0x2000


def read(path):
    """(vram bytes, register bytes) of a .pvrdmp"""
    data = open(path, "rb").read()
    if data[:len(COOKIE)] != COOKIE:
        raise ValueError(f"{path}: not a PVR core dump (no {COOKIE!r} at its start)")
    d = zlib.decompressobj(zlib.MAX_WBITS | 16)
    vram = d.decompress(data[len(COOKIE):])
    if not d.eof:
        raise ValueError(f"{path}: the video memory member is cut short")
    d2 = zlib.decompressobj(zlib.MAX_WBITS | 16)
    regs = d2.decompress(d.unused_data)
    if not d2.eof:
        raise ValueError(f"{path}: the register member is cut short")
    if len(vram) not in VRAM_SIZES:
        raise ValueError(f"{path}: video memory of {len(vram)} bytes (8 or 16 MB expected)")
    if len(regs) != REGS_SIZE:
        raise ValueError(f"{path}: a register file of {len(regs)} bytes ({REGS_SIZE} expected)")
    return vram, regs


def write(path, vram, regs):
    if len(vram) not in VRAM_SIZES or len(regs) != REGS_SIZE:
        raise ValueError(f"{path}: video memory {len(vram)} bytes, registers {len(regs)} bytes")
    with open(path, "wb") as f:
        f.write(COOKIE)
        f.write(gzip.compress(vram, mtime=0))
        f.write(gzip.compress(regs, mtime=0))


def scene_of(path):
    return os.path.basename(path)[:-len(".pvrdmp")] if path.endswith(".pvrdmp") else os.path.basename(path)


def main(argv):
    if len(argv) < 2 or argv[0] not in ("info", "unpack", "pack"):
        print(__doc__)
        return 1
    op, args, to, frm = argv[0], [], None, None
    k = 1
    while k < len(argv):
        if argv[k] == "--to":
            to = argv[k + 1]; k += 2
        elif argv[k] == "--from":
            frm = argv[k + 1]; k += 2
        else:
            args.append(argv[k]); k += 1
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dumps")
    for a in args:
        if op == "info":
            vram, regs = read(a)
            r = lambda o: struct.unpack_from("<I", regs, o)[0]
            print(f"{a}: {len(vram) >> 20} MB video memory; REGION_BASE {r(0x2c):06x} PARAM_BASE {r(0x20):06x} "
                  f"FB_W_SOF1 {r(0x60):08x} FB_W_CTRL {r(0x48):08x}")
        elif op == "unpack":
            vram, regs = read(a)
            out = to or os.path.dirname(os.path.abspath(a))
            s = scene_of(a)
            open(os.path.join(out, f"vram_{s}.bin"), "wb").write(vram)
            open(os.path.join(out, f"pvr_regs_{s}.bin"), "wb").write(regs)
            print(f"{a} -> {out}/vram_{s}.bin, pvr_regs_{s}.bin")
        else:
            src = frm or here
            vram = open(os.path.join(src, f"vram_{a}.bin"), "rb").read()
            regs = open(os.path.join(src, f"pvr_regs_{a}.bin"), "rb").read()
            if len(regs) == 0x8000:          # older emulator builds wrote 32 KB; the first 8 KB are the registers
                regs = regs[:REGS_SIZE]
            out = os.path.join(to or here, f"{a}.pvrdmp")
            write(out, vram, regs)
            print(f"{a} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
