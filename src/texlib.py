"""Lectura de texturas NG4 desde los .dat (DDS inline, animadas o con mips en streaming)."""
import re, struct
import gdef

DXGI = {71: "BC1", 72: "BC1", 74: "BC2", 75: "BC2", 77: "BC3", 78: "BC3", 80: "BC4", 83: "BC5",
        98: "BC7", 99: "BC7", 28: "RGBA8", 29: "RGBA8", 87: "BGRA8", 91: "BGRA8", 61: "R8"}


def read_entry_blob(e, arc_path):
    """Lee y descomprime el bloque principal de una entrada."""
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
    """Carga una textura (DDS completo, formato, tamano y mips)."""
    raw = read_entry_blob(e, arc_path)
    files = {f[0]: f for f in e["files"]}
    # inline: Image0.img, o Image.img sin mips (animaciones: arreglo DX10 de cuadros)
    name = "Image0.img" if "Image0.img" in files else "Image.img"
    whole = not any(n.startswith("mip") for n in files) and name in files
    if whole:
        _, _, hoff, size, _ = files[name]
        whole = raw[hoff:hoff + 4] == b"DDS "
    if whole:
        dds = raw[hoff:hoff + size]
        kind = "inline"
    else:
        _, _, hoff, size, _ = files["Image.img"]
        img = raw[hoff:hoff + size]
        ddshdr = img[img.find(b"DDS "):]
        mipnames = sorted((n for n in files if n.startswith("mip")), key=lambda n: int(n[3:-4]))
        data = b"".join(read_stream(arc_path, files[n][1], files[n][3], files[n][4]) for n in mipnames)
        dds = ddshdr + data
        kind = "streamed"
    h, w = struct.unpack("<II", dds[12:20])
    nmips = max(1, struct.unpack("<I", dds[28:32])[0])
    dx10 = dds[84:88] == b"DX10"
    fmt = DXGI.get(struct.unpack("<I", dds[128:132])[0], "?") if dx10 else dds[84:88].decode("latin1")
    return dict(kind=kind, dds=dds, fmt=fmt, w=w, h=h, mips=nmips, raw=raw, hdr_len=148 if dx10 else 128)


def sprite_rects(meta):
    """Devuelve los rectangulos UV de cada sprite de un atlas."""
    rects = {}
    for m in re.finditer(rb"(.{4})([ -~]{3,64}\.tif)\x00", meta, re.S):
        if struct.unpack("<I", m.group(1))[0] != len(m.group(2)) + 1:
            continue
        rects[m.group(2).decode()] = struct.unpack_from("<4f", meta, m.end() + 4)
    return rects


BLOCK = {"BC1": 8, "BC4": 8, "BC2": 16, "BC3": 16, "BC5": 16, "BC7": 16}


def mip_spans(fmt, w, h, mips):
    """Devuelve el offset y el tamano en bloques de cada nivel de mip."""
    bs, off, out = BLOCK[fmt], 0, []
    for i in range(mips):
        bw, bh = max(1, (max(1, w >> i) + 3) // 4), max(1, (max(1, h >> i) + 3) // 4)
        out.append((off, bw, bh))
        off += bw * bh * bs
    return out


def sprite_blocks(fmt, w, h, mips, rects):
    """Devuelve los rangos de bytes de los bloques que cubren los sprites, en todos los mips."""
    bs, out = BLOCK[fmt], []
    for i, (off, bw, bh) in enumerate(mip_spans(fmt, w, h, mips)):
        mw, mh = max(1, w >> i), max(1, h >> i)
        for u0, v0, u1, v1 in rects:
            x0, x1 = max(0, int(u0 * mw) // 4), min(bw - 1, int(u1 * mw) // 4)
            y0, y1 = max(0, int(v0 * mh) // 4), min(bh - 1, int(v1 * mh) // 4)
            for by in range(y0, y1 + 1):
                out.append((off + (by * bw + x0) * bs, (x1 - x0 + 1) * bs))
    return out
