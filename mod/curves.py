"""Parser/editor de curves_N.bin (animaciones de la GUI pt::gui).

Estructura observada:
  0x14: u32 n_pistas, 0x18: u32 tamano, 0x1C: offsets[n] (relativos a 0x14)
  pista (objeto): u32 tamano, u32 n_campos(6), (u32 id, u32 off)*6 -> campos (off relativo a la pista):
      0: nombre (u32 len + str, p.ej. "R","G","B","A")   1: u32 color de editor
      2: u32   3: u8   4: u8   5: u32 n_claves
      seguido de n_claves objetos clave
  clave (objeto, 0x59 bytes): u32 tamano, u32 7, (id, off)*7 ->
      0: f32 tiempo  1: f32 valor (0..255 en colores)  2..5: f32 tangentes  6: u8 interpolacion
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
        size, f = _obj(b, t)
        ln = struct.unpack_from("<I", b, t + f[0])[0]
        name = b[t + f[0] + 4:t + f[0] + 4 + ln - 1].decode("latin1")
        nk = struct.unpack_from("<I", b, t + f[5])[0]
        k = t + f[5] + 4
        keys = []
        for _ in range(nk):
            ksz, kf = _obj(b, k)
            fo = {i: k + kf[i] for i in range(6)}
            vals = [struct.unpack_from("<f", b, fo[i])[0] for i in range(6)]
            keys.append(dict(off=k, fo=fo, t=vals[0], v=vals[1], tan=vals[2:], interp=b[k + kf[6]]))
            k += ksz
        tracks.append(dict(name=name, off=t, size=size, keys=keys))
    return tracks


def _eval(keys, t):
    """Valor de una pista en el tiempo t (lineal entre claves; constante fuera de rango)."""
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


def recolor(buf, is_red, stats):
    """Recolorea en el bytearray todas las ternas de pistas R,G,B consecutivas."""
    tracks = parse(bytes(buf))
    for i in range(len(tracks) - 2):
        r, g, b = tracks[i:i + 3]
        if (r["name"], g["name"], b["name"]) != ("R", "G", "B"):
            continue
        chans = (r["keys"], g["keys"], b["keys"])
        if not any(chans):
            continue
        if not all(chans):                  # falta un canal: el color real es desconocido
            stats["ternas_incompletas"] += 1
            continue
        stats["ternas"] += 1
        new = []
        for ch, keys in enumerate(chans):
            for k in keys:
                rgb = [_eval(c, k["t"]) for c in chans]
                q = [max(0, min(255, round(x))) for x in rgb]
                if is_red(*q):
                    new.append((k, float(max(q))))
        for k, v in new:
            struct.pack_into("<f", buf, k["fo"][1], v)
            stats["claves"] += 1
            if any(k["tan"]):
                stats["claves_con_tangente"] += 1
