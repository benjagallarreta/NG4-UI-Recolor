"""Edicion de curves_N.bin (animaciones de la GUI).

Formato: 0x14 n_pistas, 0x1C offsets (relativos a 0x14). Objeto = u32 tamano, u32 n, (id, off)*n.
Pista: campo 0 nombre ("R", "G", "B", "A"), campo 5 n_claves, seguida de sus claves.
Clave: campo 0 tiempo (f32), campo 1 valor (f32, 0..255).
"""
import struct

BASE = 0x14


def _obj(b, o):
    size, n = struct.unpack_from("<II", b, o)
    return size, {fid: off for fid, off in (struct.unpack_from("<II", b, o + 8 + 8 * i) for i in range(n))}


def parse(b):
    n = struct.unpack_from("<I", b, BASE)[0]
    offs = struct.unpack_from(f"<{n}I", b, BASE + 8)
    tracks = []
    for rel in offs:
        t = BASE + rel
        _, f = _obj(b, t)
        ln = struct.unpack_from("<I", b, t + f[0])[0]
        name = b[t + f[0] + 4:t + f[0] + 4 + ln - 1].decode("latin1")
        nk = struct.unpack_from("<I", b, t + f[5])[0]
        k = t + f[5] + 4
        keys = []
        for _ in range(nk):
            ksz, kf = _obj(b, k)
            t_, v = struct.unpack_from("<f", b, k + kf[0])[0], struct.unpack_from("<f", b, k + kf[1])[0]
            keys.append(dict(t=t_, v=v, voff=k + kf[1]))
            k += ksz
        tracks.append(dict(name=name, keys=keys))
    return tracks


def _eval(keys, t):
    """Devuelve el valor de la pista en el tiempo t (interpolacion lineal)."""
    if not keys:
        return None
    if t <= keys[0]["t"]:
        return keys[0]["v"]
    for a, b in zip(keys, keys[1:]):
        if a["t"] <= t <= b["t"]:
            if b["t"] == a["t"]:
                return b["v"]
            return a["v"] + (b["v"] - a["v"]) * (t - a["t"]) / (b["t"] - a["t"])
    return keys[-1]["v"]


def recolor(buf, mapper, stats):
    """Recolorea en buf las ternas de pistas R, G, B consecutivas."""
    tracks = parse(bytes(buf))
    for i in range(len(tracks) - 2):
        r, g, b = tracks[i:i + 3]
        if (r["name"], g["name"], b["name"]) != ("R", "G", "B"):
            continue
        chans = (r["keys"], g["keys"], b["keys"])
        if not any(chans):
            continue
        if not all(chans):                  # falta un canal: el color real es desconocido
            continue
        stats["ternas"] += 1
        new = []
        for ch, keys in enumerate(chans):
            for k in keys:
                rgb = [_eval(c, k["t"]) for c in chans]
                q = [max(0, min(255, round(x))) for x in rgb]
                m = mapper(*q)
                if m is not None:
                    new.append((k, float(m[ch])))
        for k, v in new:
            struct.pack_into("<f", buf, k["voff"], v)
            stats["claves"] += 1
