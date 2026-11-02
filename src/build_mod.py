"""Motor del mod: recolorea layouts, animaciones, textos y texturas de la UI.

Parte siempre de la copia original: trunca @patch_image0.dat, agrega al final los assets
recoloreados y reescribe @patch_image0.csv para que apunten a ellos.
"""
import sys, os, re, json, struct, hashlib, collections, shutil, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gdef, texlib, bc, curves, colormap
from i18n import t

# Datos del programa al ejecutar desde el codigo: NG4_UI_Recolor_App junto al repo (o NG4_APP_DIR)
REPO_DIR = os.path.dirname(HERE)
DEFAULT_APP_DIR = os.environ.get("NG4_APP_DIR") or os.path.join(os.path.dirname(REPO_DIR), "NG4_UI_Recolor_App")
DEFAULT_BACKUP = os.path.join(DEFAULT_APP_DIR, "backup")

# Texturas de UI con rojo horneado (prefijo de GUID -> descripcion)
TEXTURES = {
    "d14ca148": "fondo rojo del título (title_0001/0002)",
    "a4722d74": "barra (archive)",
    "7e46c65c": "líneas diagonales (hud_0055, menu_0084/85)",
    "b9b5d39a": "iconos de armas (wpn_menu)",
    "79956c0a": "arte lineal de armas (wpn_get_l)",
    "7af39a52": "botones del título (title_01_btn)",
    "ed3c08f5": "piezas HUD (hud_06_prts)",
    "fda86ee3": "selección archivo (archive_01_btn_sel)",
    "94f7f463": "diagramas de control (menu_07_cnt)",
    "a5b09677": "botones de menú (menu_04_btn)",
    "4f4dfe35": "animaciones de menú (menu_05_anm)",
    "52411d21": "HUD objetivos/marcadores (hud_01)",
    "a7b1bd32": "fondo HUD (hud_0060)",
    "82258413": "botones del título 2 (title_03_btn)",
    "5e888aa0": "fondos/barras comunes (core_02_bg)",
    "2508ec27": "iconos menu_10",
    "595d2f60": "fondos de menú (menu_03_bg)",
    "8451ea51": "líneas de velocidad (menu_1011)",
    "90247c70": "HUD habilidades (hud_03_aby)",
    "1c604ba2": "HUD habilidades (hud_02_aby)",
    "f8ec12b5": "fondos de menú (menu_02_bg)",
    "624d9d89": "líneas (menu_0142)",
    "b066d976": "marco (menu_1010)",
    "9da07fff": "líneas (archive_0050)",
    "6332ddc2": "marco (hud_0060)",
    "ca2de698": "cabeceras (core_01_hdd)",
    "8db202da": "iconos del selector de armas / emblemas de ninpo (hud_0150/0151/0156)",
    "53d31b0c": "botón 'pulsar' y piezas del logo de la pantalla de título (title_04_*)",
    "0eb60f0b": "logo de Ninja Gaiden 4 (GAIDEN y el 4)",
    "e16d1b93": "símbolos que caen en el fondo de los menús (partícula, MainTexture)",
}

# Simbolos que caen en el fondo de los menus (opcion recolor_particles)
PARTICLE_TEXTURES = {"e16d1b93"}

# Alertas de gameplay (opcion keep_alerts): aviso de ataque (emrg4/emrg5) e icono de deteccion (eye)
ALERT_LAYOUTS = {"hud_0028", "hud_0029", "hud_0031", "hud_0032", "hud_0076"}
ALERT_SPRITES = re.compile(r"^hud_02_(emrg4|emrg5|eye)_")
ALERT_ATLAS = "1c604ba2"

# Intro y aparicion del titulo (opcion keep_intro); el boton "pulsar" (title_04_psh_*) siempre se recolorea
INTRO_LAYOUTS = {"title_0033"}
INTRO_SPRITES = re.compile(r"^title_04_(?!psh_)")
INTRO_CURVE_LAYOUTS = {"title_0001", "title_0002", "hud_9001", "hud_a080"}
INTRO_TEXTURES = {"d14ca148"}

# Logo "GAIDEN 4" (opcion recolor_logo): textura completa y piezas animadas en TITLE_ATLAS
LOGO_TEXTURE = "0eb60f0b"
LOGO_SPRITES = re.compile(r"^title_04_(lg_eff_\d+|lg_\d+|ng_\d+)\.tif$")

# Atlas donde solo se recolorean ciertos sprites: armas (wpn_*) y ninpo (nnp_*); en el titulo, "pulsar"
SHARED_ATLAS = "8db202da"
TITLE_ATLAS = "53d31b0c"
TITLE_BUTTON_SPRITES = re.compile(r"^title_04_psh_")

# Colores de texto en Data.bin: etiquetas <COLOR:..> (tutoriales, creditos) y estilos de texto
TEXT_DATA = {
    "64cac02d": ("tags", "etiquetas de color del texto (tutoriales, créditos)"),
    "e46e6bbb": ("style", "estilo de texto con acento rojo"),
    "22de56ab": ("style", "estilo de texto con acento rojo"),
}
TAG_RE = re.compile(rb"<COLOR:\w+>\x00", re.S)
STYLE_OBJ_RE = re.compile(rb"i\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00H\x00\x00\x00", re.S)


def recolor_text_tags(buf, start, end, mapper):
    """Recolorea el color de cada etiqueta <COLOR:xx> de la tabla de etiquetas."""
    n = 0
    for m in TAG_RE.finditer(buf, start, end):
        i = m.end()
        new = mapper(*buf[i:i + 3])
        if new is not None:
            buf[i:i + 3] = bytes(new); n += 1
    return n


def recolor_text_styles(buf, start, end, mapper):
    """Recolorea el color (campo 5) de cada estilo de texto."""
    n = 0
    for m in STYLE_OBJ_RE.finditer(buf, start, end):
        s = m.start()
        nf = struct.unpack_from("<I", buf, s + 4)[0]
        fields = dict(struct.unpack_from("<II", buf, s + 8 + 8 * k) for k in range(nf))
        i = s + fields[5]
        new = mapper(*buf[i:i + 3])
        if new is not None:
            buf[i:i + 3] = bytes(new); n += 1
    return n


NEVER = re.compile(r"(?!)")
NAME_RE = re.compile(rb"Name\x00.{4}([ -~]+?)\x00", re.S)
ATLAS_RE = re.compile(rb"AtlasName\x00.{4}([ -~]*?)\x00", re.S)
COLOR_RE = re.compile(rb"\x08\xb0\xb7\x8a\xff\x99\xad\xd9(.{4})(.{4})(.{4})"
                      rb"(StartColor|EndColor|EdgeColor|ColorStart|ColorEnd|Color2|Color3|Color)\x00", re.S)
IMAGE_PROPS = (b"StartColor", b"EndColor", b"EdgeColor")      # tintes de imagen (respetan KEEP_SPRITES)
PARTICLE_PROPS = (b"ColorStart", b"ColorEnd")                 # emisores de particulas (opcion recolor_particles)
DAT, CSV = "@patch_image0.dat", "@patch_image0.csv"
ALIGN, PAD = 16, b"\x40"


class ModError(Exception):
    """Error con mensaje apto para el usuario."""


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest().upper()


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


def image_atlas(buf, start, pos):
    """Devuelve el atlas de la imagen a la que pertenece la propiedad en `pos`."""
    t = buf.rfind(b"TextureFile\x00", start, pos)
    if t < 0:
        return None
    m = ATLAS_RE.search(buf, t, pos)
    return m.group(1).decode() if m else None


def recolor(buf, start, end, mapper, stats, keep_sprites=NEVER, keep_stats=None, particles=True):
    """Recolorea los colores fijos de un layout.bin dentro de buf[start:end]."""
    n = 0
    for m in COLOR_RE.finditer(buf, start, end):
        voff, size, nlen = struct.unpack("<III", m.group(1) + m.group(2) + m.group(3))
        if nlen != len(m.group(4)) + 1 or size - voff != 4:
            continue
        if m.group(4) in PARTICLE_PROPS and not particles:
            continue
        i = m.end()
        r, g, b, a = buf[i:i + 4]
        new = mapper(r, g, b)
        if new is None:
            continue
        if m.group(4) in IMAGE_PROPS:
            atlas = image_atlas(buf, start, m.start())
            if atlas and keep_sprites.match(atlas):
                if keep_stats is not None:
                    keep_stats[atlas] += 1
                continue
        buf[i:i + 3] = bytes(new)
        stats[(r, g, b) + tuple(new)] += 1
        n += 1
    return n


def apply(game_dir, target=colormap.WHITE, keep_alerts=True, recolor_weapons=True,
          recolor_ninpo=True, keep_intro=False, recolor_logo=True, recolor_particles=True,
          dry_run=False, backup_dir=DEFAULT_BACKUP, log=print, progress=None):
    """Aplica el mod y devuelve un resumen. Lanza ModError ante problemas recuperables."""
    progress = progress or (lambda frac, text: None)
    target = tuple(target)
    assets = os.path.join(game_dir, "Assets")
    orig = os.path.join(backup_dir, "original")
    dat_path, csv_path = os.path.join(assets, DAT), os.path.join(assets, CSV)
    man_path = os.path.join(backup_dir, "manifest.json")
    if not os.path.isfile(csv_path):
        raise ModError(t("No se encontró el juego en: {path}", path=game_dir))
    if not os.path.isfile(man_path) or not os.path.isfile(os.path.join(orig, DAT)):
        raise ModError(t("No se encontró la copia de seguridad en: {path}", path=backup_dir))

    gdef.init(game_dir)
    bc.set_target(target)
    mapper = colormap.mapper(target)
    keep_layouts = (ALERT_LAYOUTS if keep_alerts else set()) | (INTRO_LAYOUTS if keep_intro else set())
    # intro original, salvo las piezas del logo si se recolorea el logo
    intro_rx = INTRO_SPRITES.pattern + (f"(?!{LOGO_SPRITES.pattern[len('^title_04_'):]})" if recolor_logo else "")
    sprite_rx = [p for p, on in ((ALERT_SPRITES.pattern, keep_alerts), (intro_rx, keep_intro)) if on]
    keep_sprites = re.compile("|".join(f"(?:{p})" for p in sprite_rx)) if sprite_rx else NEVER
    keep_curves = INTRO_CURVE_LAYOUTS if keep_intro else set()
    texture_keep = {ALERT_ATLAS: ALERT_SPRITES} if keep_alerts else {}
    shared = [p for p, on in (("wpn_", recolor_weapons), ("nnp_", recolor_ninpo)) if on]
    texture_only = {SHARED_ATLAS: re.compile("^(" + "|".join(shared) + ")")} if shared else {}
    title_rx = [TITLE_BUTTON_SPRITES.pattern] + ([LOGO_SPRITES.pattern] if recolor_logo else [])
    texture_only[TITLE_ATLAS] = re.compile("|".join(f"(?:{p})" for p in title_rx))
    textures = {k: v for k, v in TEXTURES.items()
                if (k != SHARED_ATLAS or shared) and not (keep_intro and k in INTRO_TEXTURES)
                and (k != LOGO_TEXTURE or recolor_logo) and (k not in PARTICLE_TEXTURES or recolor_particles)}
    log(t("Color objetivo: {color}  | alertas originales: {alerts}  | intro original: {intro}  | logo: {logo}  "
          "| partículas: {particles}  | armas: {weapons}  | ninpo: {ninpo}",
          color=colormap.to_hex(target), alerts=keep_alerts, intro=keep_intro, logo=recolor_logo,
          particles=recolor_particles, weapons=recolor_weapons, ninpo=recolor_ninpo))

    manifest = {m["Name"]: m for m in json.load(open(man_path, encoding="utf-8-sig"))["files"]}
    orig_size = manifest[DAT]["Size"]

    # 1. dat al estado original
    if not dry_run:
        progress(0.0, t("Restaurando el archivo original..."))
        cur = os.path.getsize(dat_path)
        if cur > orig_size:
            with open(dat_path, "r+b") as f:
                f.truncate(orig_size)
        if cur < orig_size or sha256(dat_path) != manifest[DAT]["SHA256"]:
            log(t("El .dat no coincide con el original: copiando desde la copia de seguridad..."))
            shutil.copyfile(os.path.join(orig, DAT), dat_path)

    # indice: base de Assets + patch0 original de la copia
    entries = {}
    for name in sorted(os.listdir(assets)):
        if name.endswith(".csv") and name.startswith("@image"):
            entries.update(parse_csv(os.path.join(assets, name), name[:-4] + ".dat")[1])
    p1_path = os.path.join(assets, "@patch_image1.csv")
    p1 = parse_csv(p1_path, "@patch_image1.dat")[1] if os.path.isfile(p1_path) else {}
    header, p0 = parse_csv(os.path.join(orig, CSV), DAT)
    entries.update(p0)

    def arc_of(e):
        return os.path.join(orig if e["arc"] == DAT else assets, e["arc"])

    layouts = [e for e in entries.values() if any(f[0] == "layout.bin" for f in e["files"])]
    clash = [e for e in layouts if e["path"] in p1]
    if clash:
        log(t("ADVERTENCIA: {n} layouts están en @patch_image1 y se omiten.", n=len(clash)))
        layouts = [e for e in layouts if e["path"] not in p1]

    stats, cstats, kstats = collections.Counter(), collections.Counter(), collections.Counter()
    new_rows, appended, changed_layouts = {}, bytearray(), 0

    def put(data):
        nonlocal appended
        off = orig_size + len(appended)
        appended += data
        appended += PAD * (-len(appended) % ALIGN)
        return off

    # 2. layouts (colores fijos + animaciones)
    for li, e in enumerate(sorted(layouts, key=lambda e: e["path"])):
        if li % 10 == 0:
            progress(0.05 + 0.45 * li / len(layouts), t("Layouts {i}/{n}", i=li, n=len(layouts)))
        buf = bytearray(texlib.read_entry_blob(e, arc_of(e)))
        lf = next(f for f in e["files"] if f[0] == "layout.bin")
        lname = NAME_RE.search(buf, lf[2], lf[2] + lf[3])
        lname = lname.group(1).decode() if lname else ""
        if lname in keep_layouts:
            kstats["layout:" + lname] += 1
            continue
        n = 0
        for name, soff, hoff, size, csize in e["files"]:
            if name == "layout.bin":
                # particulas de la intro (plumas, ruido del logo) siguen la opcion de la intro
                parts = recolor_particles and not (keep_intro and lname in INTRO_CURVE_LAYOUTS)
                n += recolor(buf, hoff, hoff + size, mapper, stats, keep_sprites, kstats, parts)
            elif name.startswith("curves_") and lname not in keep_curves:
                sub = bytearray(buf[hoff:hoff + size])
                before = cstats["claves"]
                try:
                    curves.recolor(sub, mapper, cstats)
                except Exception:                  # curva con otro formato: se deja intacta
                    continue
                if cstats["claves"] != before:
                    buf[hoff:hoff + size] = sub
                    n += cstats["claves"] - before
        if not n:
            continue
        changed_layouts += 1
        comp = gdef.compress(bytes(buf), 0)
        if gdef.decompress(comp, len(buf)) != bytes(buf):
            raise ModError(t("Falló la verificación de compresión en {path}", path=e["path"]))
        line = list(e["line"])
        line[1], line[4] = str(put(comp)), str(len(comp))
        new_rows[e["path"]] = line

    log(t("Layouts modificados: {changed}/{total}  colores fijos: {colors}  animaciones: {anim}",
          changed=changed_layouts, total=len(layouts), colors=sum(stats.values()),
          anim=t("{keys} claves en {tracks} grupos RGB", keys=cstats["claves"], tracks=cstats["ternas"])))
    log(t("Conservados (alertas e intro): {n}", n=sum(kstats.values())))

    by_guid = {e["path"].split("/")[-2][:8]: e for e in entries.values()}

    # 2b. datos de texto
    data_done = collections.Counter()
    for pre, (kind, desc) in TEXT_DATA.items():
        e = by_guid.get(pre)
        if e is None or e["path"] in p1:
            log(t("ADVERTENCIA: no se encontró el dato de texto {pre} ({desc}); se omite.", pre=pre, desc=t(desc)))
            continue
        buf = bytearray(texlib.read_entry_blob(e, arc_of(e)))
        f = next(x for x in e["files"] if x[0] == "Data.bin")
        n = (recolor_text_tags if kind == "tags" else recolor_text_styles)(buf, f[2], f[2] + f[3], mapper)
        if not n:
            continue
        comp = gdef.compress(bytes(buf), 0)
        if gdef.decompress(comp, len(buf)) != bytes(buf):
            raise ModError(t("Falló la verificación de compresión en {path}", path=e["path"]))
        line = list(e["line"])
        line[1], line[4] = str(put(comp)), str(len(comp))
        new_rows[e["path"]] = line
        data_done[pre] = n
    log(t("Datos de texto modificados: {n} colores en {assets} assets (etiquetas de color y estilos)",
          n=sum(data_done.values()), assets=len(data_done)))

    # 3. texturas
    tex_done = []
    for ti, (pre, desc) in enumerate(textures.items()):
        progress(0.5 + 0.45 * ti / len(textures), t("Textura {i}/{n}: {desc}", i=ti + 1, n=len(textures), desc=t(desc)))
        e = by_guid.get(pre)
        if e is None:
            log(t("ADVERTENCIA: no se encontró la textura {pre} ({desc}); se omite.", pre=pre, desc=t(desc)))
            continue
        if e["path"] in p1:
            log(t("ADVERTENCIA: la textura {pre} está en @patch_image1; se omite.", pre=pre))
            continue
        arc_path = arc_of(e)
        tx = texlib.load(e, arc_path)
        if tx["fmt"] not in bc.RECOLOR:
            log(t("ADVERTENCIA: formato {fmt} no soportado en {pre}; se omite.", fmt=tx["fmt"], pre=pre))
            continue
        st = collections.Counter()
        fn = bc.RECOLOR[tx["fmt"]]
        line = list(e["line"])
        files = [list(f) for f in e["files"]]
        if "".join(f"{n}/{a}/{b}/{c}/{d}/" for n, a, b, c, d in files) != line[7]:
            log(t("ADVERTENCIA: formato de índice inesperado en {pre}; se omite.", pre=pre))
            continue
        sel_re = texture_keep.get(pre) or texture_only.get(pre)
        if tx["kind"] == "inline":
            raw = bytearray(tx["raw"])
            f = next(f for f in files if f[0] in ("Image0.img", "Image.img"))
            region = bytearray(raw[f[2] + tx["hdr_len"]:f[2] + f[3]])
            spans_sel = []
            if sel_re:
                meta_f = next(f for f in files if f[0] == "Metadata.bin")
                rects = texlib.sprite_rects(raw[meta_f[2]:meta_f[2] + meta_f[3]])
                sel = [r for k, r in rects.items() if sel_re.match(k)]
                spans = texlib.mip_spans(tx["fmt"], tx["w"], tx["h"], tx["mips"])
                last = spans[-1]
                if last[0] + last[1] * last[2] * texlib.BLOCK[tx["fmt"]] != len(region):
                    log(t("ADVERTENCIA: estructura de mips inesperada en {pre}; se omite.", pre=pre))
                    continue
                spans_sel = texlib.sprite_blocks(tx["fmt"], tx["w"], tx["h"], tx["mips"], sel)
                st["sprites_sel"] = len(sel)
            original = bytes(region)
            fn(region, st)
            if pre in texture_keep:            # los sprites protegidos conservan el original
                for o, l in spans_sel:
                    region[o:o + l] = original[o:o + l]
            elif pre in texture_only:          # solo cambian los sprites seleccionados
                recolored = bytes(region)
                region[:] = original
                for o, l in spans_sel:
                    region[o:o + l] = recolored[o:o + l]
            raw[f[2] + tx["hdr_len"]:f[2] + f[3]] = region
            comp = gdef.compress(bytes(raw), 0)
            if gdef.decompress(comp, len(raw)) != bytes(raw):
                raise ModError(t("Falló la verificación de compresión en la textura {pre}", pre=pre))
            line[1], line[4] = str(put(comp)), str(len(comp))
        else:
            if sel_re:
                log(t("ADVERTENCIA: selección de sprites no soportada en texturas streamed ({pre}); se omite.", pre=pre))
                continue
            # cabecera intacta (copiada tal cual) + cada mip recoloreado por separado
            with open(arc_path, "rb") as fh:
                fh.seek(e["off"]); hdr = fh.read(e["comp"] or e["raw"])
            line[1] = str(put(hdr))
            for f in files:
                if not f[0].startswith("mip"):
                    continue
                data = bytearray(texlib.read_stream(arc_path, f[1], f[3], f[4]))
                fn(data, st)
                if f[4]:
                    blob = gdef.compress(bytes(data), 0)
                    if gdef.decompress(blob, len(data)) != bytes(data):
                        raise ModError(t("Falló la verificación de compresión en la textura {pre}", pre=pre))
                else:
                    blob = bytes(data)
                f[1], f[4] = put(blob), (len(blob) if f[4] else 0)
            line[7] = "".join(f"{n}/{a}/{b}/{c}/{d}/" for n, a, b, c, d in files)
        new_rows[e["path"]] = line
        tex_done.append(e["path"])
        extra = ""
        if st["sprites_sel"]:
            extra = t("  [sprites protegidos: {n}]" if pre in texture_keep else "  [sprites recoloreados: {n}]",
                      n=st["sprites_sel"])
        log(t("  textura {pre} {fmt} {w}x{h} {kind} bloques={blocks}  {desc}{extra}", pre=pre, fmt=f"{tx['fmt']:4}",
              w=tx["w"], h=tx["h"], kind=f"{tx['kind']:8}", blocks=f"{st['blocks']:7}", desc=t(desc), extra=extra))

    summary = dict(layouts=changed_layouts, textures=len(tex_done), colors=sum(stats.values()),
                   curve_keys=cstats["claves"], appended=len(appended), target=colormap.to_hex(target))
    log(t("Bytes agregados al .dat: {n}  (nuevas entradas csv: {new}, redirigidas: {moved})", n=f"{len(appended):,}",
          new=sum(p not in p0 for p in new_rows), moved=sum(p in p0 for p in new_rows)))
    if dry_run:
        log(t("Simulación: no se escribió nada."))
        progress(1.0, t("Simulación terminada"))
        return summary

    # 4. append al dat
    progress(0.95, t("Escribiendo archivos..."))
    with open(dat_path, "ab") as f:
        f.write(appended)
    # 5. csv (ordenado, CRLF)
    rows = {p: e["line"] for p, e in p0.items()}
    rows.update(new_rows)
    tmp = csv_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(header + "\r\n")
        for p in sorted(rows):
            f.write(",".join(rows[p]) + "\r\n")
    os.replace(tmp, csv_path)

    # verificacion: cada asset se relee desde los archivos finales
    progress(0.97, t("Verificando..."))
    _, final = parse_csv(csv_path, DAT)
    tex_set = set(tex_done)
    for p in new_rows:
        e = final[p]
        if p in tex_set:
            tx = texlib.load(e, dat_path)          # lee cabecera + todos los mips desde el .dat final
            if len(tx["dds"]) <= tx["hdr_len"]:
                raise ModError(t("Textura vacía tras escribir: {path}", path=p))
        else:
            texlib.read_entry_blob(e, dat_path)
    log(t("OK: {layouts} layouts y {textures} texturas verificados desde {dat}.", layouts=len(new_rows) - len(tex_set), textures=len(tex_set), dat=DAT))
    progress(1.0, t("Listo"))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="Cambia el color rojo de la UI de Ninja Gaiden 4.")
    ap.add_argument("--color", default="FFFFFF", help="color objetivo RRGGBB (por defecto FFFFFF)")
    ap.add_argument("--game", help="carpeta del juego (por defecto se busca en las bibliotecas de Steam)")
    ap.add_argument("--backup", default=DEFAULT_BACKUP)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--recolor-alerts", "--no-keep-alerts", dest="recolor_alerts", action="store_true",
                    help="recolorear tambien las alertas de gameplay")
    ap.add_argument("--no-intro", action="store_true", help="intro, cinematicas de inicio y logo con color original")
    ap.add_argument("--no-particles", action="store_true", help="no recolorear las particulas de la UI")
    ap.add_argument("--no-icons", action="store_true", help="no recolorear iconos de armas y de ninpo")
    a = ap.parse_args(argv)
    if not a.game:
        import state
        a.game = state.find_game_dir()
        if not a.game:
            print("ERROR: no se encontro el juego; usa --game", file=sys.stderr)
            return 1
    try:
        apply(a.game, colormap.parse_hex(a.color), keep_alerts=not a.recolor_alerts,
              keep_intro=a.no_intro, recolor_logo=not a.no_intro, recolor_particles=not a.no_particles,
              recolor_weapons=not a.no_icons, recolor_ninpo=not a.no_icons, dry_run=a.dry_run,
              backup_dir=a.backup)
    except (ModError, ValueError) as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
