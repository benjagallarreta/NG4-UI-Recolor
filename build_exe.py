import os, sys, subprocess, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)
from gui import APP_NAME, VERSION

EXE = APP_NAME + ".exe"
ICON = os.path.join(SRC, "icon.ico")
VERFILE = os.path.join(ROOT, "build", "version_info.txt")


def make_version_file():
    v = tuple(int(x) for x in VERSION.split(".")) + (0,) * (4 - len(VERSION.split(".")))
    os.makedirs(os.path.dirname(VERFILE), exist_ok=True)
    with open(VERFILE, "w", encoding="utf-8") as f:
        f.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={v}, prodvers={v}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('FileDescription', '{APP_NAME} - cambia el color de la interfaz de Ninja Gaiden 4'),
      StringStruct('ProductName', '{APP_NAME}'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('ProductVersion', '{VERSION}'),
      StringStruct('OriginalFilename', '{EXE}'),
      StringStruct('InternalName', '{APP_NAME}'),
      StringStruct('LegalCopyright', 'Mod no oficial. Ninja Gaiden es marca de Koei Tecmo.')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""")


def main():
    make_version_file()
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
           "--name", APP_NAME, "--icon", ICON, "--version-file", VERFILE,
           "--add-data", f"{ICON};.",                                   # icono de la ventana (gui.resource)
           "--paths", SRC, "--exclude-module", "PIL", "--exclude-module", "numpy", "--noupx",
           "--distpath", os.path.join(ROOT, "dist"), "--workpath", os.path.join(ROOT, "build"),
           "--specpath", os.path.join(ROOT, "build"), os.path.join(SRC, "gui.py")]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    exe = os.path.join(ROOT, "dist", EXE)
    import build_mod
    app = build_mod.DEFAULT_APP_DIR
    os.makedirs(app, exist_ok=True)
    dest = os.path.join(app, EXE)
    try:
        shutil.copy2(exe, dest)
    except PermissionError:
        raise SystemExit(f"No se pudo copiar a {dest}: cerra {EXE} y volve a ejecutar.")
    print(f"\nListo: {dest}  ({os.path.getsize(dest) / 2**20:.1f} MB)")


if __name__ == "__main__":
    main()
