"""NG4 UI Recolor: ventana para elegir el color de la interfaz de Ninja Gaiden 4 y aplicarlo.

Ejecutar:  python gui.py      (o el .exe portable generado con PyInstaller)
"""
import os, sys, queue, threading, traceback, colorsys, math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import tkinter as tk
from tkinter import filedialog, messagebox, font as tkfont

import colormap, state, i18n
from i18n import t

APP_NAME = "NG4 UI Recolor"
VERSION = "1.0"

# Colores reales de la UI original (ocurrencias mas comunes), para la vista previa
PALETTE = [("Acento principal", "FF5A6C"), ("Acento intenso", "FF4557"), ("Rojo puro", "FF0000"),
           ("Resaltado del menú", "FF5C6A"), ("Acento medio", "E03240"), ("Rosado claro", "FFAAB1"),
           ("Burdeos", "932D39"), ("Burdeos oscuro", "73282E"), ("Fondo", "302122")]

STATUS_TEXT = {
    "sin_backup": ("Sin copia de seguridad: se creará al aplicar por primera vez.", "#E0B33A"),
    "original": ("Archivos originales.", "#4CC27A"),
    "modificado": ("Mod aplicado.", "#4C9AFF"),
    "actualizado": ("El juego se actualizó desde la copia de seguridad.", "#F05A5A"),
    "desconocido": ("Los archivos no coinciden con la copia de seguridad.", "#F05A5A"),
    "otra_copia": ("", "#F05A5A"),
}

BG, PANEL, FIELD, FIELD_HI = "#131418", "#1D1F25", "#272A31", "#30343C"
FG, MUTED, BTN, BTN_HI, BTN_OFF = "#ECEDF0", "#8D909A", "#2B2E36", "#363A44", "#23252B"
LOG_BG, TRACK_OFF, ACCENT, ERROR = "#17181C", "#3A3D46", "#4C9AFF", "#F05A5A"
FONT, FONT_B = "Segoe UI", "Segoe UI Semibold"

SCALE = 1.0                                       # factor de escala DPI (lo fija App)


def S(v):
    """Pixeles logicos -> pixeles reales segun el DPI."""
    return int(round(v * SCALE))


def resource(name):
    """Ruta a un recurso empaquetado (dentro del .exe) o junto al codigo fuente."""
    return os.path.join(getattr(sys, "_MEIPASS", HERE), name)


# ---------------------------------------------------------------------------- dibujo redondeado
def _rgb(hx):
    hx = hx.lstrip("#")
    return int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c + .5))) for c in rgb)


def _mix(a, b, k):
    """Mezcla dos colores (tuplas RGB): k=1 -> a, k=0 -> b."""
    return tuple(x * k + y * (1 - k) for x, y in zip(a, b))


def _ink(hx):
    """Color de texto legible sobre el fondo hx."""
    r, g, b = _rgb(hx)
    return "#111216" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#F4F5F7"


_CORNERS = {}


def _corner(widget, r, fill, outer, which):
    """Esquina redondeada suavizada (r x r) de color fill sobre outer, cacheada."""
    key = (id(widget._root()), r, fill, outer, which)
    img = _CORNERS.get(key)
    if img is None:
        cx = r if which in ("nw", "sw") else 0
        cy = r if which in ("nw", "ne") else 0
        f, o = _rgb(fill), _rgb(outer)
        rows = []
        for y in range(r):
            row = []
            for x in range(r):
                inside = sum((x + (i + .5) / 4 - cx) ** 2 + (y + (j + .5) / 4 - cy) ** 2 <= r * r
                             for i in range(4) for j in range(4))
                row.append(_hex(_mix(f, o, inside / 16)))
            rows.append("{" + " ".join(row) + "}")
        img = tk.PhotoImage(master=widget, width=r, height=r)
        img.put(" ".join(rows))
        _CORNERS[key] = img
    return img


def round_rect(cv, x0, y0, x1, y1, r, fill, outer, tags=()):
    """Rectangulo redondeado con bordes suavizados (outer = color de fondo detras)."""
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    r = int(max(0, min(r, (x1 - x0) // 2, (y1 - y0) // 2)))
    if r == 0:
        cv.create_rectangle(x0, y0, x1, y1, fill=fill, width=0, tags=tags)
        return
    cv.create_rectangle(x0 + r, y0, x1 - r, y1, fill=fill, width=0, tags=tags)
    cv.create_rectangle(x0, y0 + r, x1, y1 - r, fill=fill, width=0, tags=tags)
    for which, x, y in (("nw", x0, y0), ("ne", x1 - r, y0), ("sw", x0, y1 - r), ("se", x1 - r, y1 - r)):
        cv.create_image(x, y, anchor="nw", image=_corner(cv, r, fill, outer, which), tags=tags)


# ---------------------------------------------------------------------------- widgets
class Card(tk.Canvas):
    """Panel redondeado; el contenido va en .body. stretch=True estira el contenido al alto del panel."""

    def __init__(self, master, fill=PANEL, outer=BG, radius=14, padx=16, pady=14, stretch=False):
        super().__init__(master, bg=outer, highlightthickness=0, bd=0, width=1, height=1)
        self.fill, self.outer, self.radius = fill, outer, S(radius)
        self.padx, self.pady, self.stretch = S(padx), S(pady), stretch
        self.body = tk.Frame(self, bg=fill)
        self._win = self.create_window(self.padx, self.pady, anchor="nw", window=self.body)
        self.body.bind("<Configure>", self._fit, add="+")
        self.bind("<Configure>", self._redraw, add="+")

    def _fit(self, ev=None):
        self.configure(width=self.body.winfo_reqwidth() + 2 * self.padx,
                       height=self.body.winfo_reqheight() + 2 * self.pady)

    def _redraw(self, ev=None):
        w, h = self.winfo_width(), self.winfo_height()
        self.delete("bg")
        round_rect(self, 0, 0, w, h, self.radius, self.fill, self.outer, "bg")
        self.tag_lower("bg")
        size = dict(width=max(1, w - 2 * self.padx))
        if self.stretch:
            size["height"] = max(1, h - 2 * self.pady)
        self.itemconfigure(self._win, **size)

    def set_fill(self, fill):
        self.fill = fill
        self.body.configure(bg=fill)
        self._redraw()


class Field(Card):
    """Campo de texto redondeado que se ilumina con el foco."""

    def __init__(self, master, textvariable, outer=PANEL, width=None, font=(FONT, 10)):
        super().__init__(master, fill=FIELD, outer=outer, radius=9, padx=10, pady=6)
        self.entry = tk.Entry(self.body, textvariable=textvariable, bg=FIELD, fg=FG, insertbackground=FG,
                              relief="flat", bd=0, highlightthickness=0, font=font, width=width or 20,
                              selectbackground="#3D5A80", selectforeground=FG)
        self.entry.pack(fill="x")
        self.entry.bind("<FocusIn>", lambda e: self._focus(True), add="+")
        self.entry.bind("<FocusOut>", lambda e: self._focus(False), add="+")
        self.bind("<Button-1>", lambda e: self.entry.focus_set())

    def _focus(self, on):
        c = FIELD_HI if on else FIELD
        self.entry.configure(bg=c)
        self.set_fill(c)


class RoundButton(tk.Canvas):
    """Boton tipo pildora. kind='accent' usa el color de acento (el color elegido)."""

    def __init__(self, master, text, command, kind="normal", outer=BG, font=(FONT_B, 10)):
        super().__init__(master, bg=outer, highlightthickness=0, bd=0, cursor="hand2")
        self.font = tkfont.Font(master, font=font)
        self.command, self.kind, self.outer = command, kind, outer
        self.enabled, self.hover, self.accent = True, False, ACCENT
        self.text = text
        w = self.font.measure(text) + S(40)
        h = self.font.metrics("linespace") + S(16)
        self.configure(width=w, height=h)
        self.w, self.h = w, h
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", self._click)
        self._redraw()

    def _set_hover(self, on):
        self.hover = on
        self._redraw()

    def _click(self, ev):
        if self.enabled and 0 <= ev.x < self.w and 0 <= ev.y < self.h:
            self.command()

    def _redraw(self):
        if not self.enabled:
            fill, ink = BTN_OFF, "#62656E"
        elif self.kind == "accent":
            base = _rgb(self.accent)
            fill = _hex(_mix((255, 255, 255), base, 0.18) if self.hover else base)
            ink = _ink(fill)
        else:
            fill, ink = (BTN_HI if self.hover else BTN), FG
        self.delete("all")
        round_rect(self, 0, 0, self.w, self.h, self.h // 2, fill, self.outer)
        self.create_text(self.w / 2, self.h / 2, text=self.text, fill=ink, font=self.font)

    def set_state(self, enabled):
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._redraw()

    def set_accent(self, color):
        self.accent = color
        self._redraw()


class Toggle(tk.Frame):
    """Interruptor con texto, ligado a un BooleanVar."""

    def __init__(self, master, text, variable, bg=PANEL):
        super().__init__(master, bg=bg)
        self.var, self.bg, self.accent = variable, bg, ACCENT
        self.w, self.h = S(40), S(22)
        self.sw = tk.Canvas(self, width=self.w, height=self.h, bg=bg, highlightthickness=0, cursor="hand2")
        self.sw.pack(side="left", anchor="n", pady=(S(1), 0))
        self.lbl = tk.Label(self, text=text, bg=bg, fg=FG, justify="left", anchor="w", font=(FONT, 10),
                            cursor="hand2")
        self.lbl.pack(side="left", anchor="n", padx=(S(10), 0))
        for w in (self.sw, self.lbl):
            w.bind("<Button-1>", lambda e: self.var.set(not self.var.get()))
        self._trace = variable.trace_add("write", lambda *a: self._redraw())
        self.bind("<Destroy>", self._untrace, add="+")
        self._redraw()

    def _untrace(self, ev):
        if ev.widget is self:
            try:
                self.var.trace_remove("write", self._trace)
            except tk.TclError:
                pass

    def _redraw(self):
        on = bool(self.var.get())
        track = self.accent if on else TRACK_OFF
        m = S(3)
        d = self.h - 2 * m
        x = self.w - m - d if on else m
        self.sw.delete("all")
        round_rect(self.sw, 0, 0, self.w, self.h, self.h // 2, track, self.bg)
        round_rect(self.sw, x, m, x + d, m + d, d // 2, "#FFFFFF" if on else "#C4C6CD", track)

    def set_accent(self, color):
        self.accent = color
        self._redraw()


class Swatch(tk.Canvas):
    """Muestra de color redondeada, con texto opcional."""

    def __init__(self, master, width, height, outer=PANEL, radius=6, font=("Consolas", 8)):
        super().__init__(master, width=S(width), height=S(height), bg=outer, highlightthickness=0, bd=0)
        self.w, self.h, self.outer, self.radius, self.font = S(width), S(height), outer, S(radius), font

    def set(self, color, text="", ink=None):
        self.delete("all")
        round_rect(self, 0, 0, self.w, self.h, self.radius, color, self.outer)
        if text:
            self.create_text(self.w / 2, self.h / 2, text=text, fill=ink or _ink(color), font=self.font)


class Progress(tk.Canvas):
    """Barra de progreso redondeada."""

    def __init__(self, master, outer=BG):
        super().__init__(master, width=1, height=S(8), bg=outer, highlightthickness=0, bd=0)
        self.outer, self.frac, self.accent = outer, 0.0, ACCENT
        self.bind("<Configure>", lambda e: self._redraw())

    def _redraw(self):
        w, h = self.winfo_width(), self.winfo_height()
        self.delete("all")
        round_rect(self, 0, 0, w, h, h // 2, FIELD, self.outer)
        fw = int(w * self.frac)
        if fw >= h:
            round_rect(self, 0, 0, fw, h, h // 2, self.accent, FIELD)

    def set(self, frac):
        self.frac = max(0.0, min(1.0, frac))
        self._redraw()

    def set_accent(self, color):
        self.accent = color
        self._redraw()


class ColorWheel(tk.Frame):
    """Rueda de tono/saturacion + barra de brillo. Llama on_change(rgb) al interactuar."""

    def __init__(self, master, size, on_change, bg=PANEL):
        super().__init__(master, bg=bg)
        self.size, self.on_change, self.bg = size, on_change, bg
        self.h, self.s, self.v = 0.0, 0.0, 1.0
        self.wheel = tk.Canvas(self, width=size, height=size, bg=bg, highlightthickness=0, cursor="crosshair")
        self.wheel.pack()
        self.bar_h = max(12, size // 13)
        self.knob = self.bar_h // 2 + S(3)
        self.bar = tk.Canvas(self, width=size + 2 * self.knob, height=2 * self.knob + 2, bg=bg,
                             highlightthickness=0, cursor="sb_h_double_arrow")
        self.bar.pack(pady=(S(10), 0))
        self._wheel_img = self._render_wheel()
        self.wheel.create_image(0, 0, anchor="nw", image=self._wheel_img)
        r = max(5, size // 26)
        self._mk = self.wheel.create_oval(0, 0, 2 * r, 2 * r, outline="#111216", width=S(4))
        self._mk2 = self.wheel.create_oval(0, 0, 2 * r, 2 * r, outline="#FFFFFF", width=S(2))
        self._mr = r
        self._bar_cov = self._capsule(size, self.bar_h)
        self._bar_img = tk.PhotoImage(width=size, height=self.bar_h)
        self.bar.create_image(self.knob, self.knob + 1 - self.bar_h // 2, anchor="nw", image=self._bar_img)
        self._bmk = self.bar.create_oval(0, 0, 0, 0, outline="#FFFFFF", width=S(2))
        for ev in ("<Button-1>", "<B1-Motion>"):
            self.wheel.bind(ev, self._on_wheel)
            self.bar.bind(ev, self._on_bar)
        self._redraw()

    def _render_wheel(self):
        n, c = self.size, (self.size - 1) / 2
        rad = c - 1
        bg = _rgb(self.bg)
        img = tk.PhotoImage(width=n, height=n)
        rows = []
        for y in range(n):
            row = []
            dy = y - c
            for x in range(n):
                dx = x - c
                d = math.hypot(dx, dy)
                cov = min(1.0, rad - d + 0.5)            # borde suavizado
                if cov <= 0:
                    row.append(self.bg)
                    continue
                h = (math.atan2(-dy, dx) / (2 * math.pi)) % 1.0
                rgb = tuple(v * 255 for v in colorsys.hsv_to_rgb(h, min(1.0, d / rad), 1.0))
                row.append(_hex(_mix(rgb, bg, cov) if cov < 1 else rgb))
            rows.append("{" + " ".join(row) + "}")
        img.put(" ".join(rows))
        return img

    @staticmethod
    def _capsule(w, h):
        """Cobertura (0..1) de una capsula w x h, suavizada en los extremos."""
        r = h / 2
        cov = []
        for y in range(h):
            row = []
            for x in range(w):
                if r <= x <= w - r - 1:
                    row.append(1.0)
                    continue
                cx = r if x < r else w - r
                n = sum((x + (i + .5) / 4 - cx) ** 2 + (y + (j + .5) / 4 - r) ** 2 <= r * r
                        for i in range(4) for j in range(4))
                row.append(n / 16)
            cov.append(row)
        return cov

    def _redraw(self):
        c = (self.size - 1) / 2
        rad = c - 1
        x = c + math.cos(self.h * 2 * math.pi) * self.s * rad
        y = c - math.sin(self.h * 2 * math.pi) * self.s * rad
        r = self._mr
        for item in (self._mk, self._mk2):
            self.wheel.coords(item, x - r, y - r, x + r, y + r)
        n = self.size
        cols = [tuple(v * 255 for v in colorsys.hsv_to_rgb(self.h, self.s, i / (n - 1))) for i in range(n)]
        hexes = [_hex(cl) for cl in cols]
        bg = _rgb(self.bg)
        rows = []
        for cov in self._bar_cov:
            rows.append("{" + " ".join(hexes[i] if k >= 1 else (self.bg if k <= 0 else _hex(_mix(cols[i], bg, k)))
                                       for i, k in enumerate(cov)) + "}")
        self._bar_img.put(" ".join(rows), to=(0, 0))
        bx, by, kr = self.knob + self.v * (n - 1), self.knob + 1, self.knob - S(1)
        self.bar.coords(self._bmk, bx - kr, by - kr, bx + kr, by + kr)
        self.bar.itemconfigure(self._bmk, fill=hexes[int(self.v * (n - 1))])

    def _emit(self):
        r, g, b = colorsys.hsv_to_rgb(self.h, self.s, self.v)
        self.on_change(tuple(int(x * 255 + .5) for x in (r, g, b)))

    def _on_wheel(self, ev):
        c = (self.size - 1) / 2
        dx, dy = ev.x - c, ev.y - c
        self.h = (math.atan2(-dy, dx) / (2 * math.pi)) % 1.0
        self.s = min(1.0, math.hypot(dx, dy) / (c - 1))
        self._redraw(); self._emit()

    def _on_bar(self, ev):
        self.v = min(1.0, max(0.0, (ev.x - self.knob) / (self.size - 1)))
        self._redraw(); self._emit()

    def set_rgb(self, rgb):
        """Mueve los marcadores al color dado (sin emitir). Con grises conserva el tono previo."""
        h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in rgb))
        if s > 0.001 and v > 0.001:
            self.h = h
        if v > 0.001:
            self.s = s
        self.v = v
        self._redraw()


def _enable_dpi():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def _dark_titlebar(win):
    """Barra de titulo oscura (Windows 10 1809+) y del color del fondo (Windows 11)."""
    try:
        import ctypes
        hwnd = int(win.wm_frame(), 16)
        dwm = ctypes.windll.dwmapi
        on = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(on), 4)          # DWMWA_USE_IMMERSIVE_DARK_MODE
        r, g, b = _rgb(BG)
        cap = ctypes.c_int(r | (g << 8) | (b << 16))
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(cap), 4)         # DWMWA_CAPTION_COLOR
    except Exception:
        pass


def accent_for(rgb):
    """Color de acento de la ventana a partir del color elegido (con brillo minimo para que se vea)."""
    if rgb is None:
        return ACCENT
    h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in rgb))
    return _hex(tuple(x * 255 for x in colorsys.hsv_to_rgb(h, s, max(v, 0.6))))


class App(tk.Tk):
    def __init__(self):
        global SCALE
        super().__init__()
        SCALE = self.winfo_fpixels("1i") / 96.0
        i18n.set_lang(state.read_state().get("lang") or "en")          # ingles por defecto
        self.title(f"{APP_NAME} {VERSION} - Ninja Gaiden 4")
        try:
            self.iconbitmap(default=resource("icon.ico"))
        except tk.TclError:
            pass
        self.configure(bg=BG)
        self.q = queue.Queue()
        self.busy = False
        self._last_status = None
        self.color = tk.StringVar(value="FFFFFF")
        self.game = tk.StringVar()
        # opciones de la ventana; engine_options() las traduce al motor
        self.alerts = tk.BooleanVar(value=False)         # recolorear tambien las alertas de gameplay
        self.intro = tk.BooleanVar(value=True)           # recolorear intro, cinematicas de inicio y logo
        self.particles = tk.BooleanVar(value=True)       # recolorear particulas de la UI
        self.icons = tk.BooleanVar(value=True)           # recolorear iconos de armas y de ninpo
        self._build()
        self.color.trace_add("write", lambda *a: self._update_preview())
        self._update_preview()
        self._fit_window()
        _dark_titlebar(self)
        st = state.read_state()
        g = state.find_game_dir(extra=[st.get("game_dir")] if st.get("game_dir") else [])
        if g:
            self.game.set(g)
            self.refresh_status()
        else:
            self._set_status(t("No se encontró el juego. Elegí la carpeta con 'Buscar...'."), ERROR)
        self._poll_id = self.after(100, self._poll)

    def destroy(self):
        try:
            self.after_cancel(self._poll_id)
        except (AttributeError, tk.TclError):
            pass
        super().destroy()

    # ------------------------------------------------------------------ UI
    def _fit_window(self):
        """Ajusta la ventana a su contenido (los paneles se acomodan en varias pasadas)."""
        self.minsize(1, 1)
        self.geometry("")
        cards, todo = [], [self]
        while todo:
            w = todo.pop()
            todo.extend(w.winfo_children())
            if isinstance(w, Card):
                cards.append(w)
        for _ in range(3):                 # de adentro hacia afuera: un panel puede contener otro (campos)
            self.update_idletasks()
            for c in reversed(cards):
                c._fit()
        self.update()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        h = min(h, self.winfo_screenheight() - S(90))      # pantallas chicas: se recorta el registro (va al final)
        self.minsize(w, min(h, S(560)))
        self.geometry(f"{w}x{h}")

    def _card(self, parent, title=None, **kw):
        c = Card(parent, **kw)
        if title:
            tk.Label(c.body, text=title, bg=c.fill, fg=FG, font=(FONT_B, 11)).pack(anchor="w", pady=(0, S(10)))
        return c

    @staticmethod
    def _label(parent, text, muted=False, size=10, bold=False, **kw):
        return tk.Label(parent, text=text, bg=parent["bg"], fg=MUTED if muted else FG,
                        font=(FONT_B if bold else FONT, size), **kw)

    def _build(self):
        root = self.root_frame = tk.Frame(self, bg=BG, padx=S(18), pady=S(16))
        root.pack(fill="both", expand=True)

        # --- barra superior: nombre de la herramienta + idioma
        top = tk.Frame(root, bg=BG); top.pack(fill="x", pady=(0, S(14)))
        self.logo = Swatch(top, 14, 14, outer=BG, radius=7)
        self.logo.pack(side="left", pady=(S(4), 0))
        self._label(top, APP_NAME, size=17, bold=True).pack(side="left", padx=(S(10), 0))
        self._label(top, "Ninja Gaiden 4", muted=True, size=10).pack(side="left", padx=(S(10), 0), pady=(S(7), 0))
        self.lang_btn = RoundButton(top, "English" if i18n.get_lang() == "es" else "Español", self.toggle_lang,
                                    font=(FONT, 9))
        self.lang_btn.pack(side="right")

        # --- juego
        p = self._card(root, t("Juego"))
        p.pack(fill="x")
        row = tk.Frame(p.body, bg=PANEL); row.pack(fill="x")
        Field(row, self.game).pack(side="left", fill="x", expand=True)
        RoundButton(row, t("Buscar..."), self.browse, outer=PANEL).pack(side="left", padx=(S(10), 0))
        st = tk.Frame(p.body, bg=PANEL); st.pack(fill="x", pady=(S(10), 0))
        self.status_dot = Swatch(st, 8, 8, radius=4)
        self.status_dot.pack(side="left", padx=(S(2), S(8)))
        self.status_lbl = tk.Label(st, text="", bg=PANEL, fg=FG, anchor="w", justify="left", font=(FONT, 9))
        self.status_lbl.pack(side="left", fill="x")

        mid = tk.Frame(root, bg=BG); mid.pack(fill="x", pady=S(14))
        mid.columnconfigure(0, weight=1); mid.columnconfigure(1, weight=1)

        # --- color
        c = self._card(mid, t("Color de la interfaz"))
        c.grid(row=0, column=0, sticky="nsew", padx=(0, S(7)))
        row = tk.Frame(c.body, bg=PANEL); row.pack(fill="x")
        self._label(row, "#", muted=True, size=11).pack(side="left", padx=(0, S(4)))
        Field(row, self.color, width=8, font=("Consolas", 11)).pack(side="left")
        self.swatch = Swatch(row, 46, 30, radius=9)
        self.swatch.pack(side="left", padx=(S(10), 0))
        body = tk.Frame(c.body, bg=PANEL); body.pack(fill="x", pady=(S(14), 0))
        self.wheel = ColorWheel(body, S(176), self._from_wheel)
        self.wheel.pack(side="left", anchor="n")
        self._label(body, t("Rueda: tono y saturación\nBarra: brillo"), muted=True, size=9,
                    justify="left").pack(side="left", anchor="s", padx=(S(14), 0), pady=(0, S(4)))

        # --- vista previa
        v = self._card(mid, t("Vista previa (colores de la UI)"))
        v.grid(row=0, column=1, sticky="nsew", padx=(S(7), 0))
        grid = tk.Frame(v.body, bg=PANEL); grid.pack(fill="x")
        grid.columnconfigure(0, weight=1)
        self._label(grid, t("Original"), muted=True, size=9).grid(row=0, column=1, pady=(0, S(4)))
        self._label(grid, t("Con el mod"), muted=True, size=9).grid(row=0, column=3, pady=(0, S(4)))
        self.preview = []
        for i, (name, hx) in enumerate(PALETTE, 1):
            self._label(grid, t(name), size=10).grid(row=i, column=0, sticky="w", pady=S(2))
            sw = Swatch(grid, 78, 24)
            sw.grid(row=i, column=1)
            sw.set("#" + hx)
            self._label(grid, "→", muted=True).grid(row=i, column=2, padx=S(8))
            after = Swatch(grid, 78, 24)
            after.grid(row=i, column=3)
            self.preview.append((hx, after))

        # --- opciones
        o = self._card(root, t("Opciones"))
        o.pack(fill="x")
        og = tk.Frame(o.body, bg=PANEL); og.pack(fill="x")
        og.columnconfigure(0, weight=1); og.columnconfigure(1, weight=1)
        opts = [(t("Recolorear la intro, las cinemáticas de inicio y el logo\nde Ninja Gaiden 4 (GAIDEN y el 4)"),
                 self.intro),
                (t("Recolorear las partículas de la UI (caracteres y símbolos que caen, destellos)"), self.particles),
                (t("Recolorear los iconos del selector de armas y de ninpo"), self.icons),
                (t("Recolorear también las alertas de gameplay\n(ataque imbloqueable, detección enemiga)"), self.alerts)]
        self.toggles = []
        for i, (text, var) in enumerate(opts):
            tg = Toggle(og, text, var)
            tg.grid(row=i // 2, column=i % 2, sticky="nw", pady=S(5), padx=(0, S(16)))
            self.toggles.append(tg)

        # --- acciones
        a = tk.Frame(root, bg=BG); a.pack(fill="x", pady=(S(16), 0))
        self.apply_btn = RoundButton(a, t("Aplicar color"), self.apply, kind="accent", font=(FONT_B, 11))
        self.apply_btn.pack(side="left")
        self.restore_btn = RoundButton(a, t("Restaurar originales"), self.restore, font=(FONT_B, 11))
        self.restore_btn.pack(side="left", padx=S(10))
        self.prog = Progress(a)
        self.prog.pack(side="left", fill="x", expand=True, padx=(S(8), 0))
        self.prog_lbl = self._label(root, "", muted=True, size=9)
        self.prog_lbl.pack(anchor="w", pady=(S(6), S(6)))

        lg = Card(root, fill=LOG_BG, radius=12, padx=12, pady=10, stretch=True)
        lg.pack(fill="both", expand=True)
        self.log_txt = tk.Text(lg.body, height=5, bg=LOG_BG, fg="#A9ACB5", bd=0, wrap="word",
                               font=("Consolas", 9), insertbackground=FG, highlightthickness=0,
                               selectbackground="#3D5A80")
        self.log_txt.pack(fill="both", expand=True)
        self.log_txt.configure(state="disabled")

    # ------------------------------------------------------------------ helpers
    def target(self):
        try:
            return colormap.parse_hex(self.color.get())
        except ValueError:
            return None

    def _from_wheel(self, rgb):
        self._wheel_driven = True
        try:
            self.color.set(colormap.to_hex(rgb)[1:])
        finally:
            self._wheel_driven = False

    def _update_preview(self):
        tg = self.target()
        if tg:
            self.swatch.set(colormap.to_hex(tg))
        else:
            self.swatch.set(FIELD, "?", MUTED)
        if tg and not getattr(self, "_wheel_driven", False):
            self.wheel.set_rgb(tg)                 # cambio desde HEX o desde el estado guardado
        for hx, sw in self.preview:
            if tg is None:
                sw.set(FIELD, "?", MUTED); continue
            new = colormap.map_color(*colormap.parse_hex(hx), tg) or colormap.parse_hex(hx)
            h = colormap.to_hex(new)
            sw.set(h, h)
        acc = accent_for(tg)
        self.logo.set(acc)
        self.apply_btn.set_accent(acc)
        self.prog.set_accent(acc)
        for tgl in self.toggles:
            tgl.set_accent(acc)

    def _set_status(self, text, color):
        self.status_lbl.configure(text=text)
        self.status_dot.set(color)

    def log(self, msg):
        self.q.put(("log", msg))

    def _append(self, msg):
        self.log_txt.configure(state="normal")
        self.log_txt.insert("end", msg + "\n")
        self.log_txt.see("end")
        self.log_txt.configure(state="disabled")

    def _set_busy(self, busy):
        self.busy = busy
        for b in (self.apply_btn, self.restore_btn, self.lang_btn):
            b.set_state(not busy)
        self.configure(cursor="watch" if busy else "")

    def _poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    self._append(val)
                elif kind == "progress":
                    frac, text = val
                    self.prog.set(frac)
                    if text:
                        self.prog_lbl.configure(text=text)
                elif kind == "status":
                    self._show_status(val)
                elif kind == "done":
                    ok, msg = val
                    self._set_busy(False)
                    if msg:
                        (messagebox.showinfo if ok else messagebox.showerror)(APP_NAME, msg)
        except queue.Empty:
            pass
        self._poll_id = self.after(80, self._poll)

    def _run(self, fn, done_msg, start_text=""):
        if self.busy:
            return
        self._set_busy(True)
        self.prog.set(0)
        self.prog_lbl.configure(text=start_text)
        self._set_status(start_text, MUTED)

        def worker():
            try:
                fn()
                self.q.put(("status", state.status(self.game.get())))
                self.q.put(("done", (True, done_msg)))
            except state.StateError as ex:
                self.log(f"ERROR: {ex}")
                self.q.put(("done", (False, str(ex))))
            except Exception as ex:
                self.log(traceback.format_exc())
                self.q.put(("done", (False, t("Error inesperado: {error}\nRevisá el registro.", error=ex))))
            finally:
                self.q.put(("progress", (1.0, "")))
        threading.Thread(target=worker, daemon=True).start()

    def _progress(self, frac, text):
        self.q.put(("progress", (frac, text)))

    # ------------------------------------------------------------------ estado
    def refresh_status(self):
        g = self.game.get()
        if not state.is_game_dir(g):
            self._set_status(t("La carpeta elegida no es una instalación de Ninja Gaiden 4."), ERROR)
            return
        self._set_status(t("Comprobando archivos..."), MUTED)

        def worker():
            try:
                self.q.put(("status", state.status(g)))
            except Exception as ex:
                self.q.put(("status", dict(code="desconocido", detail=str(ex), applied=None)))
        threading.Thread(target=worker, daemon=True).start()

    def _show_status(self, st):
        self._last_status = st
        text, color = STATUS_TEXT.get(st["code"], (st["detail"], MUTED))
        text = t(text)
        if st["code"] in ("actualizado", "desconocido", "otra_copia"):
            text = st["detail"]
        ap = st.get("applied")
        if ap:
            text = t("Mod aplicado: color {color}  (aplicado el {date})", color=ap["color"],
                     date=ap["date"].replace("T", " "))
            if not getattr(self, "_keep_controls", False):     # al cambiar de idioma no se pisa la seleccion
                self.color.set(ap["color"].lstrip("#"))
                self.alerts.set(not ap.get("keep_alerts", True))
                self.intro.set(not ap.get("keep_intro", False) or ap.get("recolor_logo", False))
                self.particles.set(ap.get("recolor_particles", True))
                self.icons.set(ap.get("recolor_weapons", True) or ap.get("recolor_ninpo", False))
        self._keep_controls = False
        self._set_status(text, color)

    # ------------------------------------------------------------------ acciones
    def toggle_lang(self):
        """Cambia entre espanol e ingles: guarda la preferencia y reconstruye la ventana."""
        if self.busy:
            return
        i18n.set_lang("en" if i18n.get_lang() == "es" else "es")
        try:
            state.write_state(lang=i18n.get_lang())
        except OSError:
            pass
        log = self.log_txt.get("1.0", "end-1c")
        self.root_frame.destroy()
        self._build()
        if log:
            self._append(log)
        self._update_preview()
        self._fit_window()
        if state.is_game_dir(self.game.get()):
            self._keep_controls = True
            self.refresh_status()             # el detalle del estado se genera en el idioma nuevo
        else:
            self._set_status(t("No se encontró el juego. Elegí la carpeta con 'Buscar...'."), ERROR)

    def browse(self):
        d = filedialog.askdirectory(title=t("Carpeta de Ninja Gaiden 4"), initialdir=self.game.get() or None)
        if d:
            self.game.set(os.path.normpath(d))
            self.refresh_status()

    def engine_options(self):
        """Traduce los 4 interruptores de la ventana a los parametros del motor."""
        intro, icons = self.intro.get(), self.icons.get()
        return dict(keep_alerts=not self.alerts.get(),                 # alertas: opcional, desactivado
                    keep_intro=not intro, recolor_logo=intro,          # intro + cinematicas + logo
                    recolor_particles=self.particles.get(),
                    recolor_weapons=icons, recolor_ninpo=icons)        # iconos de armas + ninpo

    def apply(self):
        tg = self.target()
        if tg is None:
            messagebox.showerror(APP_NAME, t("Color inválido. Usá el formato RRGGBB, por ejemplo 3A7BFF."))
            return
        g = self.game.get()
        if not state.is_game_dir(g):
            messagebox.showerror(APP_NAME, t("Elegí la carpeta del juego primero."))
            return
        if state.read_manifest(state.resolve_backup_dir(g)) is None and not messagebox.askokcancel(
                APP_NAME, t("Es la primera vez: se va a crear una copia de seguridad de los archivos originales (~600 MB) en:\n"
                            "{path}\n\nAsegurate de que el juego no tenga otros mods en esos archivos. ¿Continuar?",
                            path=state.backup_dir())):
            return
        opts = self.engine_options()
        self._append(t("--- Aplicando {color} ---", color=colormap.to_hex(tg)))
        self._run(lambda: state.apply_mod(g, tg, log=self.log, progress=self._progress, **opts),
                  t("Color {color} aplicado. Ya podés abrir el juego.", color=colormap.to_hex(tg)),
                  t("Aplicando el color..."))

    def restore(self):
        g = self.game.get()
        if not messagebox.askokcancel(APP_NAME, t("¿Restaurar los archivos originales del juego?")):
            return
        self._append(t("--- Restaurando originales ---"))
        self._run(lambda: state.restore(g, log=self.log, progress=self._progress),
                  t("Archivos originales restaurados."), t("Restaurando los archivos originales..."))


def selftest(argv):
    """Modo sin ventana para probar el .exe: --selftest SALIDA.json [--apply RRGGBB] [--restore]."""
    import json
    out = argv[argv.index("--selftest") + 1]
    res = dict(frozen=bool(getattr(sys, "frozen", False)), app_dir=state.app_dir(), log=[])
    try:
        g = state.find_game_dir()
        res["game"] = g
        if "--restore" in argv:
            state.restore(g, log=res["log"].append)
        if "--apply" in argv:
            hx = argv[argv.index("--apply") + 1]
            res["summary"] = state.apply_mod(g, colormap.parse_hex(hx), log=res["log"].append)
        res["status"] = state.status(g)
        res["ok"] = True
    except Exception as ex:
        res["ok"] = False
        res["error"] = f"{type(ex).__name__}: {ex}"
        res["trace"] = traceback.format_exc()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)


def main():
    if "--selftest" in sys.argv:
        selftest(sys.argv)
        return
    _enable_dpi()
    app = App()
    if "--screenshot" in sys.argv:              # prueba: captura la ventana y cierra
        out = sys.argv[sys.argv.index("--screenshot") + 1]
        color = sys.argv[sys.argv.index("--color") + 1] if "--color" in sys.argv else None

        def snap():
            if color:
                app.color.set(color)
            app.update()
            from PIL import ImageGrab
            x, y = app.winfo_rootx(), app.winfo_rooty()
            ImageGrab.grab((x, y, x + app.winfo_width(), y + app.winfo_height())).save(out)
            app.destroy()
        app.after(2500, snap)
    app.mainloop()


if __name__ == "__main__":
    main()
