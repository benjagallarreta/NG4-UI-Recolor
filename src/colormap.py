"""Deteccion de rojo y mapeo al color elegido: hsv = (tono_obj, s * s_obj, v * v_obj)."""
import colorsys

WHITE = (255, 255, 255)


def is_red(r, g, b):
    if max(r, g, b) - min(r, g, b) < 12:          # casi gris
        return False
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return s > 0.15 and (h < 0.06 or h > 0.92)   # tono rojo (incluye rosas y burdeos)


def parse_hex(s):
    s = s.strip().lstrip("#")
    if len(s) != 6:
        raise ValueError(f"color invalido: {s!r} (se espera RRGGBB)")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def to_hex(rgb):
    return "#%02X%02X%02X" % tuple(rgb)


def map_color(r, g, b, target=WHITE):
    """Devuelve el color de reemplazo de (r, g, b) si es rojo, o None."""
    if not is_red(r, g, b):
        return None
    _, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    th, ts, tv = colorsys.rgb_to_hsv(*(c / 255 for c in target))
    out = colorsys.hsv_to_rgb(th, s * ts, v * tv)
    return tuple(max(0, min(255, round(c * 255))) for c in out)


def mapper(target=WHITE):
    """Devuelve map_color con el color objetivo fijado."""
    return lambda r, g, b: map_color(r, g, b, target)
