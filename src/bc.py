"""Recoloreo de texturas BC1/BC3/BC7 editando solo los endpoints rojos (sin recomprimir)."""
import struct
from functools import lru_cache
from colormap import map_color

_TARGET = None
_MAP565 = None


# BC1 / BC3 (RGB565)
def _565(c):
    r, g, b = c >> 11, (c >> 5) & 63, c & 31
    return (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)


def _enc565(r, g, b):
    return (round(r * 31 / 255) << 11) | (round(g * 63 / 255) << 5) | round(b * 31 / 255)


def set_target(target):
    """Fija el color objetivo y precalcula la tabla RGB565 -> RGB565."""
    global _TARGET, _MAP565
    target = tuple(target)
    if target == _TARGET:
        return
    table = []
    for c in range(65536):
        n = map_color(*_565(c), target)
        table.append(_enc565(*n) if n else c)
    _TARGET, _MAP565 = target, table


def _swap_idx(idx, three_color):
    out = 0
    for i in range(16):
        k = (idx >> (2 * i)) & 3
        if three_color:
            k = {0: 1, 1: 0}.get(k, k)          # 2 = punto medio (simetrico), 3 = transparente
        else:
            k ^= 1                               # 0<->1, 2<->3
        out |= k << (2 * i)
    return out


def _color_block(buf, o, bc1, stats):
    c0, c1, idx = struct.unpack_from("<HHI", buf, o)
    n0, n1 = _MAP565[c0], _MAP565[c1]
    if n0 == c0 and n1 == c1:
        return
    if bc1:
        four = c0 > c1
        if four and n0 < n1:
            n0, n1, idx = n1, n0, _swap_idx(idx, False)
        elif four and n0 == n1:                  # mismo color: todos los pixeles = n0
            if n0 == 0:
                n0 = 1
            n1, idx = n0 - 1, 0
        elif not four and n0 > n1:
            n0, n1, idx = n1, n0, _swap_idx(idx, True)
    struct.pack_into("<HHI", buf, o, n0, n1, idx)
    stats["blocks"] += 1


def recolor_bc1(buf, stats):
    for o in range(0, len(buf) - 7, 8):
        _color_block(buf, o, True, stats)


def recolor_bc3(buf, stats):
    for o in range(8, len(buf) - 7, 16):
        _color_block(buf, o, False, stats)


# BC7
# (subsets, partition bits, rotation bits, idx-select bits, color bits, alpha bits, endpoint pbits, shared pbits)
_BC7 = [(3, 4, 0, 0, 4, 0, 1, 0), (2, 6, 0, 0, 6, 0, 0, 1), (3, 6, 0, 0, 5, 0, 0, 0), (2, 6, 0, 0, 7, 0, 1, 0),
        (1, 0, 2, 1, 5, 6, 0, 0), (1, 0, 2, 0, 7, 8, 0, 0), (1, 0, 0, 0, 7, 7, 1, 0), (2, 6, 0, 0, 5, 5, 1, 0)]


def _deq(q, bits, p):
    if p is not None:
        q, bits = (q << 1) | p, bits + 1
    q <<= 8 - bits
    return q | (q >> bits)


@lru_cache(maxsize=None)
def _q(v, bits, p):
    """Devuelve el valor cuantizado mas cercano a v."""
    return min(range(1 << bits), key=lambda q: abs(_deq(q, bits, p) - v))


def _bc7_block(blk, stats):
    x = int.from_bytes(blk, "little")
    mode = 0
    while mode < 8 and not (x >> mode) & 1:
        mode += 1
    if mode == 8:
        return None
    ns, pb, rb, isb, cb, ab, epb, spb = _BC7[mode]
    pos = mode + 1 + pb
    rot = (x >> pos) & ((1 << rb) - 1) if rb else 0
    pos += rb + isb
    ne = 2 * ns
    fields = {}                                   # (canal, endpoint) -> (bitpos, bits)
    for ch, bits in ((0, cb), (1, cb), (2, cb), (3, ab)):
        if not bits:
            continue
        for e in range(ne):
            fields[(ch, e)] = (pos, bits); pos += bits
    pbit = [None] * ne
    if epb:
        for e in range(ne):
            pbit[e] = (x >> pos) & 1; pos += 1
    elif spb:
        for s in range(ns):
            p = (x >> pos) & 1; pos += 1
            pbit[2 * s] = pbit[2 * s + 1] = p
    get = lambda f: (x >> f[0]) & ((1 << f[1]) - 1)
    # canal fisico -> slot almacenado (rotacion de modos 4/5)
    slot = {0: 0, 1: 1, 2: 2}
    if rot:
        slot[rot - 1] = 3
    changed = False
    for e in range(ne):
        rgb = []
        for ch in range(3):
            f = fields[(slot[ch], e)]
            rgb.append(_deq(get(f), f[1], pbit[e] if slot[ch] < 3 or epb else None))
        new = map_color(*rgb, _TARGET)
        if new is None:
            continue
        for ch in range(3):
            f = fields[(slot[ch], e)]
            p = pbit[e] if slot[ch] < 3 or epb else None
            q = _q(new[ch], f[1], p)
            x = (x & ~(((1 << f[1]) - 1) << f[0])) | (q << f[0])
        changed = True
    if changed:
        stats["blocks"] += 1
        return x.to_bytes(16, "little")
    return None


def recolor_bc7(buf, stats):
    for o in range(0, len(buf) - 15, 16):
        nb = _bc7_block(bytes(buf[o:o + 16]), stats)
        if nb is not None:
            buf[o:o + 16] = nb


RECOLOR = {"BC1": recolor_bc1, "BC3": recolor_bc3, "BC7": recolor_bc7}
