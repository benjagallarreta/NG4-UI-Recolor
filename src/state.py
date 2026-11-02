"""Carpeta del juego, copia de seguridad, estado y aplicacion/restauracion segura.

Todo se guarda en app_dir() (junto al .exe): backup\\ y mod_state.json.
"""
import os, sys, re, json, glob, shutil, hashlib, datetime, subprocess

import build_mod
from i18n import t

FILES = (build_mod.DAT, build_mod.CSV)
GAME_EXE_RE = re.compile(r"^NINJAGAIDEN4.*\.exe$", re.I)
CHUNK = 1 << 24


class StateError(build_mod.ModError):
    """Error de estado o de la copia de seguridad."""


# ubicaciones
def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return build_mod.DEFAULT_APP_DIR


def backup_dir():
    return os.path.join(app_dir(), "backup")


def state_path():
    return os.path.join(app_dir(), "mod_state.json")


def is_game_dir(path):
    return bool(path) and all(os.path.isfile(os.path.join(path, *p)) for p in (
        ("Assets", build_mod.CSV), ("Assets", build_mod.DAT), ("dstorage.dll",),
        ("DirectStorage", "dstoragecore.dll"), ("version.txt",)))


def _steam_libraries():
    roots = []
    try:
        import winreg
        for hive, key, val in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                               (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    roots.append(os.path.normpath(winreg.QueryValueEx(k, val)[0]))
            except OSError:
                pass
    except ImportError:
        pass
    libs = []
    for root in roots:
        libs.append(root)
        vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
        try:
            text = open(vdf, encoding="utf-8", errors="replace").read()
            libs += [os.path.normpath(p.replace("\\\\", "\\")) for p in re.findall(r'"path"\s+"([^"]+)"', text)]
        except OSError:
            pass
    return list({os.path.normcase(p): p for p in reversed(libs)}.values())[::-1]   # sin duplicados (mayusculas)


def find_game_dir(extra=()):
    """Busca la carpeta del juego y devuelve su ruta, o None."""
    cands = list(extra) + [read_state().get("game_dir")]     # la ultima carpeta usada
    here = app_dir()
    cands += [here, os.path.dirname(here)]                    # .exe dentro o al lado del juego
    for lib in _steam_libraries():
        for d in glob.glob(os.path.join(lib, "steamapps", "common", "*")):
            if os.path.isdir(d) and any(GAME_EXE_RE.match(f) for f in os.listdir(d)):
                cands.append(d)
    for c in cands:
        if is_game_dir(c):
            return os.path.abspath(c)
    return None


# utilidades
def game_version(game_dir):
    """Devuelve la version del juego segun version.txt."""
    try:
        text = open(os.path.join(game_dir, "version.txt"), encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    ids = re.findall(r"(changelist|changeset) id:\s*(\d+)", text)
    return " ".join(f"{k}={v}" for k, v in ids) if ids else text.strip()


def is_game_running():
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                             creationflags=flags, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return any(GAME_EXE_RE.match(line.split('","')[0].strip('"')) for line in out.splitlines() if line)


def _hash_file(path, limit=None, progress=None, base=0.0, span=1.0):
    h, done = hashlib.sha256(), 0
    total = os.path.getsize(path) if limit is None else limit
    with open(path, "rb") as f:
        while done < total:
            b = f.read(min(CHUNK, total - done))
            if not b:
                break
            h.update(b); done += len(b)
            if progress:
                progress(base + span * done / max(1, total), None)
    return h.hexdigest().upper(), done


def _copy_hashed(src, dst, progress=None, base=0.0, span=1.0):
    """Copia src a dst calculando el SHA256 al vuelo; devuelve (hash, tamano)."""
    h, done, total = hashlib.sha256(), 0, os.path.getsize(src)
    tmp = dst + ".tmp"
    with open(src, "rb") as fi, open(tmp, "wb") as fo:
        while True:
            b = fi.read(CHUNK)
            if not b:
                break
            fo.write(b); h.update(b); done += len(b)
            if progress:
                progress(base + span * done / max(1, total), None)
    os.replace(tmp, dst)
    return h.hexdigest().upper(), done


# manifiesto y estado
def read_manifest(bdir=None):
    """Lee el manifiesto de la copia de seguridad, o devuelve None si no existe."""
    path = os.path.join(bdir or backup_dir(), "manifest.json")
    if not os.path.isfile(path):
        return None
    data = json.load(open(path, encoding="utf-8-sig"))
    data["by_name"] = {f["Name"]: f for f in data["files"]}
    return data


def write_manifest(m, bdir=None):
    m = {k: v for k, v in m.items() if k != "by_name"}
    m["format"] = 2
    path = os.path.join(bdir or backup_dir(), "manifest.json")
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2, ensure_ascii=False)
    os.replace(path + ".tmp", path)


def read_state():
    try:
        return json.load(open(state_path(), encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_state(**kw):
    s = read_state(); s.update(kw)
    with open(state_path() + ".tmp", "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)
    os.replace(state_path() + ".tmp", state_path())


# Marca en el juego: el mod esta aplicado y su copia de seguridad esta en backup_dir.
# Se ignora si los archivos ya no coinciden (p. ej. Steam los restauro).
MARKER = "NG4_UI_Recolor.json"


def read_marker(game_dir):
    assets = os.path.join(game_dir, "Assets")
    try:
        mk = json.load(open(os.path.join(game_dir, MARKER), encoding="utf-8"))
        if os.path.getsize(os.path.join(assets, build_mod.DAT)) != mk.get("dat_size"):
            return None
        if _hash_file(os.path.join(assets, build_mod.CSV))[0] != mk.get("csv_sha256"):
            return None
    except (OSError, ValueError):
        return None
    return mk


def write_marker(game_dir, **kw):
    path = os.path.join(game_dir, MARKER)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(dict(tool="NG4 UI Recolor", **kw), f, indent=2, ensure_ascii=False)
    os.replace(path + ".tmp", path)


def remove_marker(game_dir):
    try:
        os.remove(os.path.join(game_dir, MARKER))
    except OSError:
        pass


def resolve_backup_dir(game_dir):
    """Devuelve la copia de seguridad de esta herramienta o, si no hay, la que indica la marca del juego."""
    local = backup_dir()
    if read_manifest(local):
        return local
    mk = read_marker(game_dir) if game_dir and is_game_dir(game_dir) else None
    if mk and mk.get("backup_dir") and read_manifest(mk["backup_dir"]):
        return mk["backup_dir"]
    return local


def status(game_dir, bdir=None):
    """Compara el juego con la copia de seguridad y devuelve su estado (code, detail, applied)."""
    m = read_manifest(bdir or resolve_backup_dir(game_dir))
    st = read_state()
    mk = read_marker(game_dir)
    if m is None:
        if mk:
            return dict(code="otra_copia", applied=mk.get("applied"),
                        detail=t("El mod se aplicó con otra copia de la herramienta y su copia de seguridad ya no "
                                 "está en:\n{path}", path=mk.get("backup_dir")))
        return dict(code="sin_backup", detail=t("Todavía no hay copia de seguridad."), applied=None)
    ver = game_version(game_dir)
    if m.get("game_version") and ver != m["game_version"]:
        return dict(code="actualizado", applied=None,
                    detail=t("El juego cambió de versión ({old} -> {new}).", old=m["game_version"], new=ver))
    dat = m["by_name"][build_mod.DAT]; csv = m["by_name"][build_mod.CSV]
    assets = os.path.join(game_dir, "Assets")
    dsize = os.path.getsize(os.path.join(assets, build_mod.DAT))
    if dsize < dat["Size"]:
        return dict(code="desconocido", applied=None, detail=t("El .dat es más chico que el original."))
    dh, _ = _hash_file(os.path.join(assets, build_mod.DAT), limit=dat["Size"])
    if dh != dat["SHA256"]:
        return dict(code="desconocido", applied=None, detail=t("El .dat no coincide con la copia de seguridad."))
    ch, _ = _hash_file(os.path.join(assets, build_mod.CSV))
    if dsize == dat["Size"] and ch == csv["SHA256"]:
        return dict(code="original", applied=None, detail=t("Archivos originales."))
    if dsize > dat["Size"] and ch != csv["SHA256"]:
        applied = mk.get("applied") if mk else None
        if not applied and st.get("dat_size") == dsize and st.get("csv_sha256") == ch:
            applied = st.get("applied")
        return dict(code="modificado", applied=applied,
                    detail=t("Mod aplicado.") if applied else t("Mod aplicado (configuración desconocida)."))
    return dict(code="desconocido", applied=None, detail=t("El índice no coincide con el .dat."))


# operaciones
def _guard(game_dir, need_space=0, bdir=None):
    if not is_game_dir(game_dir):
        raise StateError(t("No es una carpeta válida de Ninja Gaiden 4:\n{path}", path=game_dir))
    if is_game_running():
        raise StateError(t("Cerrá el juego antes de continuar."))
    if need_space:
        free = shutil.disk_usage(os.path.dirname(bdir or backup_dir()) or ".").free
        if free < need_space * 1.05:
            raise StateError(t("No hay espacio suficiente: se necesitan {mb} MB.", mb=f"{need_space / 2**20:,.0f}"))


def create_backup(game_dir, log=print, progress=None, bdir=None):
    """Copia los archivos originales del juego a la carpeta de copia de seguridad."""
    bdir = bdir or backup_dir()
    if read_manifest(bdir):
        raise StateError(t("Ya existe una copia de seguridad."))
    if read_marker(game_dir):
        raise StateError(t("Los archivos del juego tienen el mod aplicado: no se pueden respaldar como originales.\n"
                           "Usá 'Verificar integridad' en Steam para recuperar los originales."))
    assets = os.path.join(game_dir, "Assets")
    need = sum(os.path.getsize(os.path.join(assets, f)) for f in FILES)
    os.makedirs(os.path.join(bdir, "original"), exist_ok=True)
    _guard(game_dir, need, bdir)
    log(t("Creando copia de seguridad (asegurate de que los archivos del juego sean los originales)..."))
    files, sizes = [], [os.path.getsize(os.path.join(assets, f)) for f in FILES]
    base = 0.0
    for f, size in zip(FILES, sizes):
        span = size / need
        h, n = _copy_hashed(os.path.join(assets, f), os.path.join(bdir, "original", f), progress, base, span)
        base += span
        h2, _ = _hash_file(os.path.join(bdir, "original", f))
        if h2 != h:
            raise StateError(t("La copia de {name} no se verificó correctamente.", name=f))
        files.append({"Name": f, "Size": n, "SHA256": h})
        log(f"  {f}: {n:,} bytes  SHA256 {h[:16]}...")
    write_manifest({"game_version": game_version(game_dir), "game_dir": os.path.abspath(game_dir),
                    "created": datetime.datetime.now().isoformat(timespec="seconds"), "files": files}, bdir)
    log(t("Copia de seguridad creada y verificada."))


def restore(game_dir, log=print, progress=None, bdir=None):
    """Restaura los archivos originales desde la copia de seguridad, verificando hashes."""
    bdir = bdir or resolve_backup_dir(game_dir)
    m = read_manifest(bdir)
    if not m:
        raise StateError(t("No hay copia de seguridad para restaurar."))
    _guard(game_dir)
    ver = game_version(game_dir)
    if m.get("game_version") and ver != m["game_version"]:
        raise StateError(t("La copia de seguridad es de otra versión del juego. Usá 'Verificar integridad' en Steam para "
                           "recuperar los archivos originales y luego crea una copia nueva."))
    total = sum(f["Size"] for f in m["files"])
    base = 0.0
    for f in m["files"]:
        src = os.path.join(bdir, "original", f["Name"])
        span = f["Size"] / total
        h, _ = _hash_file(src, progress=progress, base=base, span=span / 2)
        if h != f["SHA256"]:
            raise StateError(t("La copia de seguridad de {name} está dañada.", name=f["Name"]))
        h2, _ = _copy_hashed(src, os.path.join(game_dir, "Assets", f["Name"]), progress, base + span / 2, span / 2)
        base += span
        if h2 != f["SHA256"]:
            raise StateError(t("Falló la restauración de {name}.", name=f["Name"]))
        log(t("  Restaurado: {name}", name=f["Name"]))
    write_state(applied=None, dat_size=None, csv_sha256=None)
    remove_marker(game_dir)
    log(t("Archivos originales restaurados."))


def apply_mod(game_dir, target, keep_alerts=True, recolor_weapons=True, recolor_ninpo=True, keep_intro=False, recolor_logo=True,
              recolor_particles=True, log=print, progress=None, bdir=None):
    """Aplica el mod con las opciones dadas, creando la copia de seguridad si hace falta."""
    bdir = bdir or resolve_backup_dir(game_dir)
    progress = progress or (lambda f, txt: None)
    _guard(game_dir)
    st = status(game_dir, bdir)
    if bdir != backup_dir():
        log(t("Usando la copia de seguridad existente en: {path}", path=bdir))
    if st["code"] == "otra_copia":
        raise StateError(st["detail"] + "\n" + t("Usá 'Verificar integridad' en Steam para recuperar los originales "
                                                 "y volvé a aplicar."))
    if st["code"] == "sin_backup":
        create_backup(game_dir, log, lambda f, txt: progress(0.3 * f, txt or t("Creando copia de seguridad...")), bdir)
    elif st["code"] == "actualizado":
        raise StateError(st["detail"] + "\n" + t("Restaurá los archivos con 'Verificar integridad' en Steam, borrá la "
                                                 "carpeta backup y volvé a aplicar."))
    elif st["code"] == "desconocido":
        raise StateError(st["detail"] + "\n" + t("Usá 'Restaurar originales' o 'Verificar integridad' en Steam."))
    start = 0.3 if st["code"] == "sin_backup" else 0.0
    summary = build_mod.apply(game_dir, tuple(target), keep_alerts=keep_alerts, recolor_weapons=recolor_weapons,
                              recolor_ninpo=recolor_ninpo, keep_intro=keep_intro, recolor_logo=recolor_logo,
                              recolor_particles=recolor_particles, backup_dir=bdir, log=log,
                              progress=lambda f, txt: progress(start + (1 - start) * f, txt))
    assets = os.path.join(game_dir, "Assets")
    ch, _ = _hash_file(os.path.join(assets, build_mod.CSV))
    applied = dict(color=summary["target"], keep_alerts=keep_alerts, recolor_weapons=recolor_weapons,
                   recolor_ninpo=recolor_ninpo, keep_intro=keep_intro, recolor_logo=recolor_logo,
                   recolor_particles=recolor_particles,
                   date=datetime.datetime.now().isoformat(timespec="seconds"))
    dsize = os.path.getsize(os.path.join(assets, build_mod.DAT))
    write_state(applied=applied, game_dir=os.path.abspath(game_dir), dat_size=dsize, csv_sha256=ch)
    write_marker(game_dir, applied=applied, backup_dir=os.path.abspath(bdir), dat_size=dsize, csv_sha256=ch)
    return summary
