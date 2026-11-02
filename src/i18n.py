"""Traducciones: la clave es el texto en espanol; t() lo devuelve en el idioma activo."""
LANGS = ("es", "en")
_lang = "es"


def set_lang(lang):
    global _lang
    _lang = lang if lang in LANGS else "es"


def get_lang():
    return _lang


def t(text, **kw):
    s = EN.get(text, text) if _lang == "en" else text
    return s.format(**kw) if kw else s


EN = {
    # ventana
    "Juego": "Game",
    "Buscar...": "Browse...",
    "Color de la interfaz": "Interface color",
    "Rueda: tono y saturación\nBarra: brillo": "Wheel: hue and saturation\nBar: brightness",
    "Opciones": "Options",
    "Recolorear también las alertas de gameplay\n(ataque imbloqueable, detección enemiga)":
        "Also recolor the gameplay alerts\n(unblockable attack, enemy detection)",
    "Recolorear los iconos del selector de armas y de ninpo": "Recolor the weapon selector and ninpo icons",
    "Recolorear la intro, las cinemáticas de inicio y el logo\nde Ninja Gaiden 4 (GAIDEN y el 4)":
        "Recolor the intro, the startup cinematics and the\nNinja Gaiden 4 logo (GAIDEN and the 4)",
    "Vista previa (colores de la UI)": "Preview (UI colors)",
    "Original": "Original",
    "Con el mod": "With the mod",
    "Aplicar color": "Apply color",
    "Restaurar originales": "Restore originals",
    "Acento principal": "Main accent", "Acento intenso": "Strong accent", "Rojo puro": "Pure red",
    "Resaltado del menú": "Menu highlight", "Acento medio": "Medium accent", "Rosado claro": "Light pink",
    "Burdeos": "Burgundy", "Burdeos oscuro": "Dark burgundy", "Fondo": "Background",
    # estado
    "Sin copia de seguridad: se creará al aplicar por primera vez.":
        "No backup yet: it will be created the first time you apply.",
    "Archivos originales.": "Original files.",
    "Mod aplicado.": "Mod applied.",
    "El juego se actualizó desde la copia de seguridad.": "The game was updated since the backup was made.",
    "Los archivos no coinciden con la copia de seguridad.": "The files do not match the backup.",
    "No se encontró el juego. Elegí la carpeta con 'Buscar...'.":
        "Game not found. Choose its folder with 'Browse...'.",
    "La carpeta elegida no es una instalación de Ninja Gaiden 4.":
        "The selected folder is not a Ninja Gaiden 4 installation.",
    "Comprobando archivos...": "Checking files...",
    "Mod aplicado: color {color}  (aplicado el {date})": "Mod applied: color {color}  (applied on {date})",
    # dialogos
    "Carpeta de Ninja Gaiden 4": "Ninja Gaiden 4 folder",
    "Color inválido. Usá el formato RRGGBB, por ejemplo 3A7BFF.":
        "Invalid color. Use the RRGGBB format, for example 3A7BFF.",
    "Elegí la carpeta del juego primero.": "Choose the game folder first.",
    "Es la primera vez: se va a crear una copia de seguridad de los archivos originales (~600 MB) en:\n"
    "{path}\n\nAsegurate de que el juego no tenga otros mods en esos archivos. ¿Continuar?":
        "First run: a backup of the original files (~600 MB) will be created in:\n{path}\n\n"
        "Make sure the game has no other mods in those files. Continue?",
    "--- Aplicando {color} ---": "--- Applying {color} ---",
    "Color {color} aplicado. Ya podés abrir el juego.": "Color {color} applied. You can start the game now.",
    "Aplicando el color...": "Applying the color...",
    "¿Restaurar los archivos originales del juego?": "Restore the original game files?",
    "--- Restaurando originales ---": "--- Restoring originals ---",
    "Archivos originales restaurados.": "Original files restored.",
    "Restaurando los archivos originales...": "Restoring the original files...",
    "Error inesperado: {error}\nRevisá el registro.": "Unexpected error: {error}\nCheck the log.",
    # state.py
    "El mod se aplicó con otra copia de la herramienta y su copia de seguridad ya no está en:\n{path}":
        "The mod was applied with another copy of this tool and its backup is no longer at:\n{path}",
    "Todavía no hay copia de seguridad.": "There is no backup yet.",
    "El juego cambió de versión ({old} -> {new}).": "The game version changed ({old} -> {new}).",
    "El .dat es más chico que el original.": "The .dat file is smaller than the original.",
    "El .dat no coincide con la copia de seguridad.": "The .dat file does not match the backup.",
    "Mod aplicado (configuración desconocida).": "Mod applied (unknown settings).",
    "El índice no coincide con el .dat.": "The index does not match the .dat file.",
    "No es una carpeta válida de Ninja Gaiden 4:\n{path}": "Not a valid Ninja Gaiden 4 folder:\n{path}",
    "Cerrá el juego antes de continuar.": "Close the game before continuing.",
    "No hay espacio suficiente: se necesitan {mb} MB.": "Not enough disk space: {mb} MB required.",
    "Ya existe una copia de seguridad.": "A backup already exists.",
    "Los archivos del juego tienen el mod aplicado: no se pueden respaldar como originales.\n"
    "Usá 'Verificar integridad' en Steam para recuperar los originales.":
        "The game files have the mod applied: they cannot be backed up as originals.\n"
        "Use 'Verify integrity of game files' in Steam to get the originals back.",
    "Creando copia de seguridad (asegurate de que los archivos del juego sean los originales)...":
        "Creating backup (make sure the game files are the original ones)...",
    "La copia de {name} no se verificó correctamente.": "The copy of {name} could not be verified.",
    "Copia de seguridad creada y verificada.": "Backup created and verified.",
    "No hay copia de seguridad para restaurar.": "There is no backup to restore.",
    "La copia de seguridad es de otra versión del juego. Usá 'Verificar integridad' en Steam para "
    "recuperar los archivos originales y luego crea una copia nueva.":
        "The backup belongs to another game version. Use 'Verify integrity of game files' in Steam to "
        "get the original files back, then create a new backup.",
    "La copia de seguridad de {name} está dañada.": "The backup of {name} is damaged.",
    "Falló la restauración de {name}.": "Restoring {name} failed.",
    "  Restaurado: {name}": "  Restored: {name}",
    "Usando la copia de seguridad existente en: {path}": "Using the existing backup at: {path}",
    "Usá 'Verificar integridad' en Steam para recuperar los originales y volvé a aplicar.":
        "Use 'Verify integrity of game files' in Steam to get the originals back and apply again.",
    "Creando copia de seguridad...": "Creating backup...",
    "Restaurá los archivos con 'Verificar integridad' en Steam, borrá la carpeta backup y volvé a aplicar.":
        "Restore the files with 'Verify integrity of game files' in Steam, delete the backup folder "
        "and apply again.",
    "Usá 'Restaurar originales' o 'Verificar integridad' en Steam.":
        "Use 'Restore originals' or 'Verify integrity of game files' in Steam.",
    # build_mod.py
    "No se encontró el juego en: {path}": "Game not found at: {path}",
    "No se encontró la copia de seguridad en: {path}": "Backup not found at: {path}",
    "Color objetivo: {color}  | alertas originales: {alerts}  | intro original: {intro}  | logo: {logo}  "
    "| partículas: {particles}  | armas: {weapons}  | ninpo: {ninpo}":
        "Target color: {color}  | original alerts: {alerts}  | original intro: {intro}  | logo: {logo}  "
        "| particles: {particles}  | weapons: {weapons}  | ninpo: {ninpo}",
    "Recolorear las partículas de la UI (caracteres y símbolos que caen, destellos)":
        "Recolor the UI particles (falling characters and symbols, glows)",
    "Conservados (alertas e intro): {n}": "Kept (alerts and intro): {n}",
    "ADVERTENCIA: no se encontró el dato de texto {pre} ({desc}); se omite.":
        "WARNING: text data {pre} ({desc}) not found; skipped.",
    "Datos de texto modificados: {n} colores en {assets} assets (etiquetas de color y estilos)":
        "Text data changed: {n} colors in {assets} assets (color tags and styles)",
    "etiquetas de color del texto (tutoriales, créditos)": "text color tags (tutorials, credits)",
    "estilo de texto con acento rojo": "text style with red accent",
    "Restaurando el archivo original...": "Restoring the original file...",
    "El .dat no coincide con el original: copiando desde la copia de seguridad...":
        "The .dat file does not match the original: copying it from the backup...",
    "ADVERTENCIA: {n} layouts están en @patch_image1 y se omiten.":
        "WARNING: {n} layouts are in @patch_image1 and are skipped.",
    "Layouts {i}/{n}": "Layouts {i}/{n}",
    "Falló la verificación de compresión en {path}": "Compression check failed for {path}",
    "Layouts modificados: {changed}/{total}  colores fijos: {colors}  animaciones: {anim}":
        "Layouts changed: {changed}/{total}  static colors: {colors}  animations: {anim}",
    "{keys} claves en {tracks} grupos RGB": "{keys} keys in {tracks} RGB groups",
    "Textura {i}/{n}: {desc}": "Texture {i}/{n}: {desc}",
    "ADVERTENCIA: no se encontró la textura {pre} ({desc}); se omite.":
        "WARNING: texture {pre} ({desc}) not found; skipped.",
    "ADVERTENCIA: la textura {pre} está en @patch_image1; se omite.":
        "WARNING: texture {pre} is in @patch_image1; skipped.",
    "ADVERTENCIA: formato {fmt} no soportado en {pre}; se omite.":
        "WARNING: unsupported format {fmt} in {pre}; skipped.",
    "ADVERTENCIA: formato de índice inesperado en {pre}; se omite.":
        "WARNING: unexpected index format in {pre}; skipped.",
    "ADVERTENCIA: estructura de mips inesperada en {pre}; se omite.":
        "WARNING: unexpected mip layout in {pre}; skipped.",
    "Falló la verificación de compresión en la textura {pre}": "Compression check failed for texture {pre}",
    "ADVERTENCIA: selección de sprites no soportada en texturas streamed ({pre}); se omite.":
        "WARNING: sprite selection is not supported for streamed textures ({pre}); skipped.",
    "  textura {pre} {fmt} {w}x{h} {kind} bloques={blocks}  {desc}{extra}":
        "  texture {pre} {fmt} {w}x{h} {kind} blocks={blocks}  {desc}{extra}",
    "  [sprites protegidos: {n}]": "  [protected sprites: {n}]",
    "  [sprites recoloreados: {n}]": "  [recolored sprites: {n}]",
    "Bytes agregados al .dat: {n}  (nuevas entradas csv: {new}, redirigidas: {moved})":
        "Bytes appended to the .dat: {n}  (new csv entries: {new}, redirected: {moved})",
    "Simulación: no se escribió nada.": "Dry run: nothing was written.",
    "Simulación terminada": "Dry run finished",
    "Escribiendo archivos...": "Writing files...",
    "Verificando...": "Verifying...",
    "Textura vacía tras escribir: {path}": "Empty texture after writing: {path}",
    "OK: {layouts} layouts y {textures} texturas verificados desde {dat}.":
        "OK: {layouts} layouts and {textures} textures verified from {dat}.",
    "Listo": "Done",
    # descripciones de texturas (build_mod.TEXTURES)
    "fondo rojo del título (title_0001/0002)": "red title background (title_0001/0002)",
    "barra (archive)": "bar (archive)",
    "líneas diagonales (hud_0055, menu_0084/85)": "diagonal lines (hud_0055, menu_0084/85)",
    "iconos de armas (wpn_menu)": "weapon icons (wpn_menu)",
    "arte lineal de armas (wpn_get_l)": "weapon line art (wpn_get_l)",
    "botones del título (title_01_btn)": "title buttons (title_01_btn)",
    "piezas HUD (hud_06_prts)": "HUD parts (hud_06_prts)",
    "selección archivo (archive_01_btn_sel)": "archive selection (archive_01_btn_sel)",
    "diagramas de control (menu_07_cnt)": "controller diagrams (menu_07_cnt)",
    "botones de menú (menu_04_btn)": "menu buttons (menu_04_btn)",
    "animaciones de menú (menu_05_anm)": "menu animations (menu_05_anm)",
    "HUD objetivos/marcadores (hud_01)": "HUD objectives/markers (hud_01)",
    "fondo HUD (hud_0060)": "HUD background (hud_0060)",
    "botones del título 2 (title_03_btn)": "title buttons 2 (title_03_btn)",
    "fondos/barras comunes (core_02_bg)": "common backgrounds/bars (core_02_bg)",
    "iconos menu_10": "menu_10 icons",
    "fondos de menú (menu_03_bg)": "menu backgrounds (menu_03_bg)",
    "líneas de velocidad (menu_1011)": "speed lines (menu_1011)",
    "HUD habilidades (hud_03_aby)": "HUD abilities (hud_03_aby)",
    "HUD habilidades (hud_02_aby)": "HUD abilities (hud_02_aby)",
    "fondos de menú (menu_02_bg)": "menu backgrounds (menu_02_bg)",
    "líneas (menu_0142)": "lines (menu_0142)",
    "marco (menu_1010)": "frame (menu_1010)",
    "líneas (archive_0050)": "lines (archive_0050)",
    "marco (hud_0060)": "frame (hud_0060)",
    "cabeceras (core_01_hdd)": "headers (core_01_hdd)",
    "iconos del selector de armas / emblemas de ninpo (hud_0150/0151/0156)":
        "weapon selector icons / ninpo emblems (hud_0150/0151/0156)",
    "botón 'pulsar' y piezas del logo de la pantalla de título (title_04_*)":
        "title screen 'press' button and logo pieces (title_04_*)",
    "logo de Ninja Gaiden 4 (GAIDEN y el 4)": "Ninja Gaiden 4 logo (GAIDEN and the 4)",
    "símbolos que caen en el fondo de los menús (partícula, MainTexture)":
        "falling symbols in the menu backgrounds (particle, MainTexture)",
}
