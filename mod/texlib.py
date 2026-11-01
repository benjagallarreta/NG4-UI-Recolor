"""Lectura de texturas NG4 desde los .dat y decodificacion a RGBA (Pillow) para inspeccion."""
import os, io, struct
import gdef

DXGI = {71: "BC1", 72: "BC1", 74: "BC2", 75: "BC2", 77: "BC3", 78: "BC3", 80: "BC4", 83: "BC5",
        98: "BC7", 99: "BC7", 28: "RGBA8", 29: "RGBA8", 87: "BGRA8", 91: "BGRA8", 61: "R8"}
LEGACY = {"BC1": b"DXT1", "BC2": b"DXT3", "BC3": b"DXT5"}


def read_entry_blob(e, arc_path):
    """Bloque cabecera de la entrada (descomprimido)."""
    with open(arc_path, "rb") as f:
        f.seek(e["off"])
        if e["comp"] == 0:
            return f.read(e["raw"])
        blob = f.read(e["comp"])
    return gdef.decompress(blob, e["raw"]) if e["comp"] != e["raw"] else blob


def read_stream(arc_path, off, size, csize):
    with open(arc_path, "rb") as f:
        f.seek(off)
        if csize == 0:
            return f.read(size)
        return gdef.decompress(f.read(csize), size)


def load(e, arc_path):
    """Devuelve dict con: kind ('inline'|'streamed'), dds (bytes DDS completo), fmt, w, h, mips, ..."""
    raw = read_entry_blob(e, arc_path)
    files = {f[0]: f for f in e["files"]}
    if "Image0.img" in files and not any(n.startswith("mip") for n in files):
        _, _, hoff, size, _ = files["Image0.img"]
        dds = raw[hoff:hoff + size]
        kind, prefix, mipnames = "inline", None, []
    else:
        _, _, hoff, size, _ = files["Image.img"]
        img = raw[hoff:hoff + size]
        p = img.find(b"DDS ")
        prefix, ddshdr = img[:p], img[p:]
        mipnames = sorted((n for n in files if n.startswith("mip")), key=lambda n: int(n[3:-4]))
        data = b"".join(read_stream(arc_path, files[n][1], files[n][3], files[n][4]) for n in mipnames)
        dds = ddshdr + data
        kind = "streamed"
    h, w = struct.unpack("<II", dds[12:20])
    nmips = max(1, struct.unpack("<I", dds[28:32])[0])
    dx10 = dds[84:88] == b"DX10"
    fmt = DXGI.get(struct.unpack("<I", dds[128:132])[0], "?") if dx10 else dds[84:88].decode("latin1")
    return dict(kind=kind, dds=dds, fmt=fmt, w=w, h=h, mips=nmips, dx10=dx10, raw=raw,
                prefix=prefix, mipnames=mipnames, hdr_len=148 if dx10 else 128)


def decode(t, mip0_only=True):
    """RGBA PIL.Image del mip0."""
    from PIL import Image
    dds = bytearray(t["dds"])
    if t["dx10"] and t["fmt"] in LEGACY:
        # Pillow no decodifica BC1-3 con cabecera DX10: reescribir como FourCC legacy
        dds[84:88] = LEGACY[t["fmt"]]
        dds = dds[:128] + dds[148:]
    if mip0_only:
        struct.pack_into("<I", dds, 28, 1)
    return Image.open(io.BytesIO(bytes(dds))).convert("RGBA")


def sprite_rects(meta):
    """{nombre.tif: (u0, v0, u1, v1)} desde Metadata.bin de un atlas."""
    import re
    rects = {}
    for m in re.finditer(rb"(.{4})([ -~]{3,64}\.tif)\x00", meta, re.S):
        if struct.unpack("<I", m.group(1))[0] != len(m.group(2)) + 1:
            continue
        rects[m.group(2).decode()] = struct.unpack_from("<4f", meta, m.end() + 4)
    return rects


BLOCK = {"BC1": 8, "BC4": 8, "BC2": 16, "BC3": 16, "BC5": 16, "BC7": 16}


def mip_spans(fmt, w, h, mips):
    """[(offset, bw, bh)] de cada nivel de mip dentro de los datos BC (sin cabecera)."""
    bs, off, out = BLOCK[fmt], 0, []
    for i in range(mips):
        bw, bh = max(1, (max(1, w >> i) + 3) // 4), max(1, (max(1, h >> i) + 3) // 4)
        out.append((off, bw, bh))
        off += bw * bh * bs
    return out


def protected_blocks(fmt, w, h, mips, rects, margin=1):
    """[(offset_byte, longitud)] de los bloques que cubren los rects UV, en todos los mips."""
    bs, out = BLOCK[fmt], []
    for i, (off, bw, bh) in enumerate(mip_spans(fmt, w, h, mips)):
        mw, mh = max(1, w >> i), max(1, h >> i)
        for u0, v0, u1, v1 in rects:
            x0 = max(0, int(u0 * mw) // 4 - margin); x1 = min(bw - 1, int(u1 * mw) // 4 + margin)
            y0 = max(0, int(v0 * mh) // 4 - margin); y1 = min(bh - 1, int(v1 * mh) // 4 + margin)
            for by in range(y0, y1 + 1):
                out.append((off + (by * bw + x0) * bs, (x1 - x0 + 1) * bs))
    return out
