"""Mod NG4: convierte los colores rojos de la UI (layout.bin) a gris segun su brillo.

Siempre parte de los archivos originales de ..\\backup (idempotente):
  1. Restaura @patch_image0.dat al tamano/hash original (es append-only, basta truncar).
  2. Lee cada layout vigente (patch tiene prioridad sobre base), recolorea, recomprime (GDeflate).
  3. Agrega los datos al final de @patch_image0.dat (alineado a 16, relleno 0x40).
  4. Reescribe @patch_image0.csv apuntando esos layouts a los datos nuevos.

Uso:  python -I build_mod.py [--dry-run] [--game "E:\\Juegos\\NINJA GAIDEN 4"]
Rollback:  pwsh -File ..\\backup\\restore.ps1 [-Game "E:\\Juegos\\NINJA GAIDEN 4"]
"""
import sys, os, re, json, struct, hashlib, colorsys, collections, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_GAME = r"E:\Juegos\NINJA GAIDEN 4"
GAME = sys.argv[sys.argv.index("--game") + 1] if "--game" in sys.argv else os.environ.get("NG4_GAME_DIR", DEFAULT_GAME)
os.environ["NG4_GAME_DIR"] = GAME           # gdef carga dstorage.dll desde esta carpeta
sys.path.insert(0, HERE)
import gdef, texlib, bc, curves

# Texturas de UI con rojo "horneado" a recolorear (prefijo de GUID -> descripcion).
# Excluidas a proposito: retratos/arte de personajes, items, ninpo, rangos, logos y fondos con personajes.
TEXTURES = {
    "d14ca148": "fondo rojo del titulo (title_0001/0002)",
    "a4722d74": "barra (archive)",
    "7e46c65c": "lineas diagonales (hud_0055, menu_0084/85)",
    "b9b5d39a": "iconos de armas (wpn_menu)",
    "79956c0a": "arte lineal de armas (wpn_get_l)",
    "7af39a52": "botones del titulo (title_01_btn)",
    "ed3c08f5": "piezas HUD (hud_06_prts)",
    "fda86ee3": "seleccion archivo (archive_01_btn_sel)",
    "94f7f463": "diagramas de control (menu_07_cnt)",
    "a5b09677": "botones de menu (menu_04_btn)",
    "4f4dfe35": "animaciones de menu (menu_05_anm)",
    "52411d21": "HUD objetivos/marcadores (hud_01)",
    "a7b1bd32": "fondo HUD (hud_0060)",
    "82258413": "botones del titulo 2 (title_03_btn)",
    "5e888aa0": "fondos/barras comunes (core_02_bg)",
    "2508ec27": "iconos menu_10",
    "595d2f60": "fondos de menu (menu_03_bg)",
    "8451ea51": "lineas de velocidad (menu_1011)",
    "90247c70": "HUD habilidades (hud_03_aby)",
    "1c604ba2": "HUD habilidades (hud_02_aby)",
    "f8ec12b5": "fondos de menu (menu_02_bg)",
    "624d9d89": "lineas (menu_0142)",
    "b066d976": "marco (menu_1010)",
    "9da07fff": "lineas (archive_0050)",
    "6332ddc2": "marco (hud_0060)",
    "ca2de698": "cabeceras (core_01_hdd)",
    "8db202da": "iconos del selector de armas HUD (solo wpn_*, hud_0150/0151)",
}

# Elementos de gameplay que conservan su color original:
#   hud_02_emrg5_* : aviso de ataque (rombo "!": rojo = imbloqueable, amarillo = otro tipo)
#   hud_02_emrg4_* : triangulos de direccion del ataque (mismos colores)
#   hud_02_eye_*   : icono de deteccion enemiga (ojo, "!" rojo de alerta, "?" amarillo)
# - KEEP_LAYOUTS: layouts que no se modifican en absoluto (colores fijos, grupos y animaciones)
# - KEEP_SPRITES: tintes StartColor/EndColor de imagenes con estos sprites (en cualquier layout)
# - TEXTURE_KEEP: en esos atlas, los bloques que cubren estos sprites no se recolorean
KEEP_LAYOUTS = {"hud_0028", "hud_0029", "hud_0031", "hud_0032", "hud_0076"}
KEEP_SPRITES = re.compile(r"^hud_02_(emrg4|emrg5|eye)_")
TEXTURE_KEEP = {"1c604ba2": KEEP_SPRITES}
NAME_RE = re.compile(rb"Name\x00.{4}([ -~]+?)\x00", re.S)

# Atlas compartidos donde SOLO se recolorean ciertos sprites (el resto queda intacto).
# 8db202da: iconos del selector de armas del HUD (wpn_*); los emblemas de ninpo (nnp_*) no se tocan.
TEXTURE_ONLY = {"8db202da": re.compile(r"^wpn_")}

ASSETS = os.path.join(GAME, "Assets")
BACKUP = os.path.join(os.path.dirname(HERE), "backup")     # NG4_UI_Color\backup
ORIG = os.path.join(BACKUP, "original")
DAT, CSV = "@patch_image0.dat", "@patch_image0.csv"
DRY = "--dry-run" in sys.argv
ALIGN, PAD = 16, b"\x40"

COLOR_RE = re.compile(rb"\x08\xb0\xb7\x8a\xff\x99\xad\xd9(.{4})(.{4})(.{4})(StartColor|EndColor|Color2|Color3|Color)\x00", re.S)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest().upper()


def is_red(r, g, b):
    if max(r, g, b) - min(r, g, b) < 12:          # casi gris: no tocar
        return False
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return s > 0.15 and (h < 0.06 or h > 0.92)   # tono rojo (incluye rosas y burdeos)


def to_gray(r, g, b):
    v = max(r, g, b)                              # brillo = canal maximo: rojo vivo -> blanco
    return v, v, v


def parse_csv(path, arc):
    header, rows = None, {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if line.startswith("header"):
                header = line; continue
            p = line.split(",")
            if len(p) < 8:
                continue
            files = []
            s = p[7].split("/")
            for i in range(0, len(s) - 4, 5):
                if s[i]:
                    files.append((s[i], *map(int, s[i + 1:i + 5])))
            rows[p[0]] = dict(arc=arc, line=p, path=p[0], off=int(p[1]), total=int(p[2]),
                              raw=int(p[3]), comp=int(p[4]), files=files)
    return header, rows


def read_raw(e, arc_path):
    return texlib.read_entry_blob(e, arc_path)


ATLAS_RE = re.compile(rb"AtlasName\x00.{4}([ -~]*?)\x00", re.S)


def image_atlas(buf, start, pos):
    """AtlasName de la imagen a la que pertenece la propiedad en `pos` (la del ultimo TextureFile previo)."""
    t = buf.rfind(b"TextureFile\x00", start, pos)
    if t < 0:
        return None
    m = ATLAS_RE.search(buf, t, pos)
    return m.group(1).decode() if m else None


def recolor(buf, start, end, stats, keep_stats=None):
    n = 0
    for m in COLOR_RE.finditer(buf, start, end):
        voff, size, nlen = struct.unpack("<III", m.group(1) + m.group(2) + m.group(3))
        if nlen != len(m.group(4)) + 1 or size - voff != 4:
            continue
        i = m.end()
        r, g, b, a = buf[i:i + 4]
        if is_red(r, g, b) and m.group(4) in (b"StartColor", b"EndColor"):
            atlas = image_atlas(buf, start, m.start())
            if atlas and KEEP_SPRITES.match(atlas):
                if keep_stats is not None:
                    keep_stats[atlas] += 1
                continue
        if is_red(r, g, b):
            nr, ng, nb = to_gray(r, g, b)
            buf[i:i + 3] = bytes((nr, ng, nb))
            stats[(r, g, b, nr)] += 1
            n += 1
    return n


def main():
    manifest = {m["Name"]: m for m in json.load(open(os.path.join(BACKUP, "manifest.json"), encoding="utf-8-sig"))}
    dat_path, csv_path = os.path.join(ASSETS, DAT), os.path.join(ASSETS, CSV)
    orig_size = manifest[DAT]["Size"]

    # 1. dat al estado original (sin tocar si es dry-run)
    if not DRY:
        cur = os.path.getsize(dat_path)
        if cur < orig_size:
            raise SystemExit("El .dat es mas chico que el original: usa restore.ps1")
        if cur > orig_size:
            with open(dat_path, "r+b") as f:
                f.truncate(orig_size)
        if sha256(dat_path) != manifest[DAT]["SHA256"]:
            print("dat no coincide con el original, copiando desde backup...")
            shutil.copyfile(os.path.join(ORIG, DAT), dat_path)

    # indice: base de Assets (no se modifican) + patch0 desde el backup original
    entries = {}
    for name in sorted(os.listdir(ASSETS)):
        if name.endswith(".csv") and name.startswith("@image"):
            entries.update(parse_csv(os.path.join(ASSETS, name), name[:-4] + ".dat")[1])
    p1 = parse_csv(os.path.join(ASSETS, "@patch_image1.csv"), "@patch_image1.dat")[1]
    header, p0 = parse_csv(os.path.join(ORIG, CSV), DAT)
    entries.update(p0)

    layouts = [e for e in entries.values() if any(f[0] == "layout.bin" for f in e["files"])]
    clash = [e["path"] for e in layouts if e["path"] in p1]
    if clash:
        raise SystemExit(f"Hay layouts en @patch_image1 (prioridad desconocida): {clash[:5]}")

    stats = collections.Counter(); cstats = collections.Counter(); kstats = collections.Counter()
    new_rows, appended, changed_layouts = {}, bytearray(), 0
    for e in sorted(layouts, key=lambda e: e["path"]):
        arc_path = os.path.join(ORIG if e["arc"] == DAT else ASSETS, e["arc"])
        buf = bytearray(read_raw(e, arc_path))
        lf = next(f for f in e["files"] if f[0] == "layout.bin")
        lname = NAME_RE.search(buf, lf[2], lf[2] + lf[3])
        if lname and lname.group(1).decode() in KEEP_LAYOUTS:
            kstats["layout:" + lname.group(1).decode()] += 1
            continue
        n = 0
        for name, soff, hoff, size, csize in e["files"]:
            if name == "layout.bin":
                n += recolor(buf, hoff, hoff + size, stats, kstats)
            elif name.startswith("curves_"):
                sub = bytearray(buf[hoff:hoff + size])
                before = cstats["claves"]
                try:
                    curves.recolor(sub, bc.is_red, cstats)
                except Exception:
                    cstats["errores_parseo"] += 1
                    continue
                if cstats["claves"] != before:
                    buf[hoff:hoff + size] = sub
                    n += cstats["claves"] - before
        if not n:
            continue
        changed_layouts += 1
        comp = gdef.compress(bytes(buf), 0)
        assert gdef.decompress(comp, len(buf)) == bytes(buf)
        off = orig_size + len(appended)
        appended += comp
        appended += PAD * (-len(appended) % ALIGN)
        line = list(e["line"])
        line[1], line[4] = str(off), str(len(comp))
        new_rows[e["path"]] = line

    print(f"layouts modificados: {changed_layouts}/{len(layouts)}  colores fijos cambiados: {sum(stats.values())}  curvas: {dict(cstats)}")
    print(f"conservados (alertas gameplay): {sum(kstats.values())} -> {dict(kstats)}")

    # ---- texturas
    def put(data):
        nonlocal appended
        off = orig_size + len(appended)
        appended += data
        appended += PAD * (-len(appended) % ALIGN)
        return off

    by_guid = {e["path"].split("/")[-2][:8]: e for e in entries.values()}
    for pre, desc in TEXTURES.items():
        e = by_guid[pre]
        if e["path"] in p1:
            raise SystemExit(f"Textura en @patch_image1 (prioridad desconocida): {e['path']}")
        arc_path = os.path.join(ORIG if e["arc"] == DAT else ASSETS, e["arc"])
        t = texlib.load(e, arc_path)
        st = collections.Counter()
        fn = bc.RECOLOR[t["fmt"]]
        line = list(e["line"])
        files = [list(f) for f in e["files"]]
        assert "".join(f"{n}/{a}/{b}/{c}/{d}/" for n, a, b, c, d in files) == line[7], e["path"]
        if t["kind"] == "inline":
            raw = bytearray(t["raw"])
            f = next(f for f in files if f[0] == "Image0.img")
            region = bytearray(raw[f[2] + t["hdr_len"]:f[2] + f[3]])
            sel_re = TEXTURE_KEEP.get(pre) or TEXTURE_ONLY.get(pre)
            spans_sel = []
            if sel_re:
                meta_f = next(f for f in files if f[0] == "Metadata.bin")
                rects = texlib.sprite_rects(raw[meta_f[2]:meta_f[2] + meta_f[3]])
                sel = [r for k, r in rects.items() if sel_re.match(k)]
                spans = texlib.mip_spans(t["fmt"], t["w"], t["h"], t["mips"])
                last = spans[-1]
                assert last[0] + last[1] * last[2] * texlib.BLOCK[t["fmt"]] == len(region), "layout de mips inesperado"
                spans_sel = texlib.protected_blocks(t["fmt"], t["w"], t["h"], t["mips"], sel, margin=0)
                st["sprites_sel"] = len(sel)
            original = bytes(region)
            fn(region, st)
            if pre in TEXTURE_KEEP:            # restaurar los sprites protegidos
                for o, l in spans_sel:
                    region[o:o + l] = original[o:o + l]
            elif pre in TEXTURE_ONLY:          # restaurar todo excepto los sprites seleccionados
                recolored = bytes(region)
                region[:] = original
                for o, l in spans_sel:
                    region[o:o + l] = recolored[o:o + l]
            raw[f[2] + t["hdr_len"]:f[2] + f[3]] = region
            comp = gdef.compress(bytes(raw), 0)
            assert gdef.decompress(comp, len(raw)) == bytes(raw)
            line[1], line[4] = str(put(comp)), str(len(comp))
        else:
            # cabecera intacta (copiada tal cual) + cada mip recoloreado por separado
            with open(arc_path, "rb") as fh:
                fh.seek(e["off"]); hdr = fh.read(e["comp"] or e["raw"])
            line[1] = str(put(hdr))
            for f in files:
                if not f[0].startswith("mip"):
                    continue
                data = bytearray(texlib.read_stream(arc_path, f[1], f[3], f[4]))
                assert pre not in TEXTURE_KEEP and pre not in TEXTURE_ONLY, "seleccion de sprites solo implementada para texturas inline"
                fn(data, st)
                if f[4]:
                    blob = gdef.compress(bytes(data), 0)
                    assert gdef.decompress(blob, len(data)) == bytes(data)
                else:
                    blob = bytes(data)
                f[1], f[4] = put(blob), (len(blob) if f[4] else 0)
            line[7] = "".join(f"{n}/{a}/{b}/{c}/{d}/" for n, a, b, c, d in files)
        new_rows[e["path"]] = line
        print(f"  textura {pre} {t['fmt']:4} {t['w']}x{t['h']} {t['kind']:8} bloques={st['blocks']:7}  {desc}" + (f"  [sprites {'protegidos' if pre in TEXTURE_KEEP else 'recoloreados'}: {st['sprites_sel']}]" if st['sprites_sel'] else ""))
    print(f"bytes agregados al .dat: {len(appended):,}  (nuevas entradas csv: {sum(p not in p0 for p in new_rows)}, redirigidas: {sum(p in p0 for p in new_rows)})")
    with open(os.path.join(HERE, "cambios_colores.tsv"), "w", encoding="utf-8") as f:
        f.write("original\tgris\tocurrencias\n")
        for (r, g, b, v), c in stats.most_common():
            f.write(f"#{r:02X}{g:02X}{b:02X}\t#{v:02X}{v:02X}{v:02X}\t{c}\n")
    if DRY:
        print("dry-run: no se escribio nada."); return

    # 3. append al dat
    with open(dat_path, "ab") as f:
        f.write(appended)
    # 4. csv (ordenado, CRLF, misma cabecera)
    rows = {p: e["line"] for p, e in p0.items()}
    rows.update(new_rows)
    tmp = csv_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(header + "\r\n")
        for p in sorted(rows):
            f.write(",".join(rows[p]) + "\r\n")
    os.replace(tmp, csv_path)

    # verificacion: releer cada layout modificado desde los archivos finales
    _, final = parse_csv(csv_path, DAT)
    tex_paths = {by_guid[pre]["path"] for pre in TEXTURES}
    for p in new_rows:
        e = final[p]
        if p in tex_paths:
            t = texlib.load(e, dat_path)          # lee cabecera + todos los mips desde el .dat final
            assert len(t["dds"]) - t["hdr_len"] > 0
        else:
            read_raw(e, dat_path)
    print(f"OK: {len(new_rows) - len(tex_paths)} layouts y {len(tex_paths)} texturas verificados desde {DAT}.")


if __name__ == "__main__":
    main()
