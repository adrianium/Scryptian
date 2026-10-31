# main.py — Scryptian Core
# Skill scanner | Hotkey | UI bar

import os
import sys
import re
import importlib.util
import threading
import tkinter as tk
from PIL import Image, ImageTk
import pyperclip
import keyboard
import time
import datetime
import math
import bridge
import telemetry
import tray
import store
import updater
from ui import StorePanel, CurrencyPanel
import autostart
import queue
import selection_watcher
import pins as pins_module
import main_pins
import skill_editor
import skill_settings
import core
import source_detect
import wallet
from config import SLIPPER_SCALE


def _skill_price(skill, file_path=""):
    """Compute a skill's price in micro-slippers (1 slipper = SLIPPER_SCALE)."""
    fixed = int(skill.get("price", 0) or 0)
    unit = (skill.get("unit") or "").strip()
    ppu = int(skill.get("price_per_unit", 0) or 0)
    if not unit or ppu <= 0:
        return fixed
    module = skill.get("module")
    measure = getattr(module, "measure", None) if module else None
    qty = None
    if callable(measure) and file_path:
        try:
            qty = measure(file_path)
        except Exception:
            qty = None
    if qty is None:
        return fixed
    try:
        qty = float(qty)
    except (TypeError, ValueError):
        return fixed
    return max(1, int(math.ceil(qty * ppu)))


def _format_slippers(micro):
    """Format micro-slippers as a human-readable slipper amount (full precision)."""
    try:
        micro = int(micro)
    except (TypeError, ValueError):
        return "0"
    if micro % SLIPPER_SCALE == 0:
        return str(micro // SLIPPER_SCALE)
    return f"{micro / SLIPPER_SCALE:.3f}".rstrip("0").rstrip(".")


def _format_price(micro):
    """Format a price with at most 2 decimals for compact display."""
    try:
        micro = int(micro)
    except (TypeError, ValueError):
        return "0"
    if micro % SLIPPER_SCALE == 0:
        return str(micro // SLIPPER_SCALE)
    return f"{micro / SLIPPER_SCALE:.2f}".rstrip("0").rstrip(".")


def _format_measure(value, unit):
    """Format a measure() result for display, based on the skill's unit."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return ""
    unit = (unit or "").strip().lower()
    if unit == "second":
        secs = value
        if secs < 60:
            return f"{int(round(secs))} sec"
        mins = secs / 60.0
        if mins < 60:
            return f"{mins:.1f} min"
        return f"{mins / 60.0:.1f} hr"
    if unit == "page":
        pages = int(round(value))
        return f"{pages} page" if pages == 1 else f"{pages} pages"
    if unit == "character":
        chars = int(round(value))
        return f"{chars} chars"
    return ""


def _measure_file(skills, file_path):
    """Return (value, unit) from the first skill whose input_type matches file_path."""
    ext = os.path.splitext(file_path)[1].lower()
    for s in skills:
        if ext not in (s.get("input_type") or []):
            continue
        m = s.get("module")
        fn = getattr(m, "measure", None) if m else None
        if not callable(fn):
            continue
        try:
            value = fn(file_path)
        except Exception:
            value = None
        if value is not None:
            return value, (s.get("unit") or "").strip()
    return None, ""


def _file_supported(skill, file_path):
    """Return True if file_path's extension matches the skill's input_type."""
    types = skill.get("input_type") or []
    if "link" in types:
        return False
    if not types:
        return True
    ext = os.path.splitext(file_path or "")[1].lower()
    return ext in types


def _io_label(skill):
    """Return a short 'input → output' label for a skill (e.g. 'PDF → JPG')."""
    itypes = skill.get("input_type") or []
    _out = skill.get("output_type")
    if isinstance(_out, (list, tuple)):
        otype = (_out[0] if _out else "")
    else:
        otype = _out or ""
    otype = otype.lstrip(".").strip().upper()

    _audio_exts = (".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma", ".aiff", ".aif")
    _audio_out = {"MP3", "WAV", "M4A", "AAC", "FLAC", "OGG", "OPUS", "WMA", "AIFF"}
    # Audio converters also accept video files, but the label is the audio action.
    if otype in _audio_out and any(e in itypes for e in _audio_exts):
        inp = "Audio"
    elif otype in {"EPUB", "FB2", "AZW3", "MOBI", "AZW"} and any(
        e in itypes for e in (
            ".epub", ".fb2", ".mobi", ".azw", ".azw3",
            ".doc", ".docx", ".odt", ".rtf", ".txt", ".pdf", ".html", ".htm",
        )
    ):
        inp = "Book"
    elif otype in {"PDF", "DOCX", "DOC", "TXT", "RTF", "ODT", "HTML", "HTM", "PPTX", "XLSX", "CSV"} and any(
        e in itypes for e in (
            ".doc", ".docx", ".odt", ".rtf", ".txt", ".pdf", ".html", ".htm",
            ".ppt", ".pptx", ".odp", ".xls", ".xlsx", ".ods", ".csv",
        )
    ):
        inp = "Document"
    elif "link" in itypes:
        inp = "Link"
    elif not itypes:
        inp = "Link"
    elif ".pdf" in itypes:
        inp = "PDF"
    elif any(e in itypes for e in (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".flv", ".ts")):
        inp = "Video"
    elif any(e in itypes for e in (".jpg", ".jpeg", ".png", ".webp", ".bmp")):
        inp = "Image"
    elif ".txt" in itypes:
        inp = "Text"
    elif any(e in itypes for e in (".wav", ".mp3", ".m4a", ".aac")):
        inp = "Audio"
    else:
        inp = "/".join(sorted({e.lstrip(".").upper() for e in itypes}))[:12]

    return f"{inp} → {otype}" if otype else inp


def _truncate(text, maxlen):
    """Truncate text with an ellipsis to keep rows from overlapping."""
    text = (text or "").strip()
    if len(text) <= maxlen:
        return text
    return text[: max(1, maxlen - 1)].rstrip() + "…"


def _ease_out_cubic(t):
    """Ease-out cubic: fast start, soft end. t in [0,1]."""
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _reserve_skill(skill, price=None):
    """Reserve the skill's price before running. Returns False (and notifies) if not."""
    if price is None:
        price = _skill_price(skill)
    if price <= 0:
        return True
    if wallet.reserve(price):
        return True
    bal = wallet.cached_balance() or 0
    bridge.notify("Not enough slippers", f"Need {_format_slippers(price)}, you have {_format_slippers(bal)}.")
    return False


def _settle_skill(skill, price=None):
    """Pay author (70%) + platform (30%) from the reserved amount on success."""
    if price is None:
        price = _skill_price(skill)
    author_id = skill.get("author_id", "") or ""
    if price <= 0 or not author_id:
        return
    skill_id = skill.get("id") or skill.get("filename", "").replace(".py", "")
    wallet.settle(price, author_id, skill_id)


def _refund_skill(skill, price=None):
    """Return the reserved amount to the user on failure."""
    if price is None:
        price = _skill_price(skill)
    if price <= 0:
        return
    wallet.refund(price)

import ctypes


# ── DPI (crisp rendering on Windows) ──
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ── Settings ──
from config import HOTKEY, BASE_DIR, APP_VERSION
from core.registry import _version_ge
import bootstrap
SKILLS_DIR = os.path.join(BASE_DIR, "skills")


# Source app/site detection lives in source_detect.py (ctypes-only, no deps).


def _track_skill(skill_id: str) -> None:
    """Record count and last_used for a skill after successful run."""
    state = bridge.get_state(skill_id)
    bridge.set_state(skill_id, {
        "count": state.get("count", 0) + 1,
        "last_used": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })


def _build_skill_event(skill, input_text, elapsed, **extra):
    """Build a detailed skill_run telemetry payload."""
    inp = core.get_input()
    input_type = inp["type"] if inp else "text"
    raw = (input_text or "").strip().strip('"')
    if raw and os.path.isfile(raw):
        _, found = os.path.splitext(raw)
        if found:
            input_type = found.lower().lstrip(".")
    out = skill.get("output_type")
    if isinstance(out, (list, tuple)):
        out = out[0] if out else ""
    output_type = str(out or "").strip().lower().lstrip(".")
    sec = round(elapsed, 2)
    if sec < 1:
        bucket = "<1s"
    elif sec < 5:
        bucket = "1-5s"
    elif sec < 30:
        bucket = "5-30s"
    else:
        bucket = "30s+"
    skill_id = skill.get("id") or skill.get("filename", "").replace(".py", "")
    state = bridge.get_state(skill_id)
    is_first = state.get("count", 0) == 0
    return {
        "skill_id": skill_id,
        "skill_title": skill.get("title", ""),
        "skill_version": skill.get("version", ""),
        "skill_author": skill.get("author", ""),
        "mode": skill.get("mode", "cloud"),
        "input_type": input_type,
        "output_type": output_type,
        "text_len": len(input_text or ""),
        "word_count": len((input_text or "").split()),
        "elapsed_sec": sec,
        "duration_bucket": bucket,
        "is_first_run": is_first,
        **extra,
    }


def _clip_seq():
    """Current Windows clipboard sequence number (0 on failure)."""
    try:
        return ctypes.windll.user32.GetClipboardSequenceNumber()
    except Exception:
        return 0


def _register_manrope():
    """Register bundled Manrope fonts with Windows (private to this process)."""
    try:
        font_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "assets", "font")
        if not os.path.isdir(font_dir):
            return
        add_font = ctypes.windll.gdi32.AddFontResourceExW
        add_font.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
        add_font.restype = ctypes.c_int
        FR_PRIVATE = 0x10
        for name in os.listdir(font_dir):
            if name.lower().endswith(".ttf"):
                add_font(os.path.join(font_dir, name), FR_PRIVATE, 0)
    except Exception:
        pass


def _round_window_corners(window):
    """Give a Toplevel the native Windows 11 rounded corners via DWM."""
    try:
        hwnd = ctypes.windll.user32.GetAncestor(window.winfo_id(), 2)  # GA_ROOT
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref),
        )
    except Exception:
        pass


def _rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    """Draw a rounded rectangle on a canvas (smooth polygon)."""
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


# ── UI ──
class ScryptianBar:
    def __init__(self, root, skills, toolbar=None):
        self.root = root
        self.skills = skills
        self.toolbar = toolbar
        self.filtered = list(skills)
        self.selected_index = 0
        self.window = None
        self.visible = False
        self.has_result = False
        self.last_result = ""
        self.processing = False
        self.pending_result = None
        self.store_frame = None
        self.in_store = False
        self.store_panel = StorePanel(self)
        self.in_currency = False
        self.currency_panel = CurrencyPanel(self)
        self._source_hwnd = None
        self._clip_seq_at_hide = None

    def toggle(self):
        """Show/hide the bar (called from any thread)."""
        if not self.visible:
            hwnd = source_detect.get_source_window()
            if hwnd:
                self._source_hwnd = hwnd
        telemetry.send("hotkey_pressed")
        self.root.after(0, self._do_toggle)

    def _do_toggle(self):
        """Toggle visibility (runs on tkinter main thread)."""
        if self.visible:
            self._hide()
        else:
            self._show()

    def _redraw_balance_pill(self):
        if not hasattr(self, "balance_pill") or not self.balance_pill.winfo_exists():
            return
        c = self.balance_pill
        try:
            req_w = self.balance_content.winfo_reqwidth()
            req_h = self.balance_content.winfo_reqheight()
        except Exception:
            return
        w = max(req_w + 2, 28)
        h = max(req_h + 2, 24)
        c.config(width=w, height=h)
        c.delete("pill")
        bg = getattr(self, "_balance_bg", "#2B2B2B")
        _rounded_rect(c, 1, 1, w - 1, h - 1, (h - 2) // 2,
                      fill=bg, outline=bg, tags="pill")
        c.tag_lower("pill")
        c.coords(self._balance_win, 1, 1)

    def _update_balance(self):
        if not hasattr(self, "balance_label"):
            return
        try:
            bal = wallet.cached_balance()
            if bal is None:
                self.balance_label.config(text="0")
            else:
                self.balance_label.config(text=_format_slippers(bal))
        except Exception:
            pass
        self.root.after(0, self._redraw_balance_pill)

    def _refresh_balance(self):
        wallet.ensure_wallet()
        self.root.after(0, self._update_balance)

    def _show(self):
        if self.window and self.visible:
            return

        if self.toolbar:
            self.toolbar._dismiss()

        # Hot-reload skills on every open
        self.skills = core.scan_skills()
        self.filtered = list(self.skills)

        self.window = tk.Toplevel(self.root)
        self.window.title("Scryptian")
        self.window.overrideredirect(True)
        self.window.attributes("-toolwindow", True)
        self.window.configure(bg="#3C3C3C")

        # ── Size and center position ──
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        bar_width = max(640, int(screen_w * 0.45))
        bar_height = 52
        x = (screen_w - bar_width) // 2
        y = int(screen_h * 0.3)
        self._bar_width = bar_width
        self._bar_x0 = x
        self._bar_y0 = y

        self.window.geometry(f"{bar_width}x{bar_height}+{x}+{y + 10}")
        self.window.attributes("-alpha", 0.0)
        self.window.update_idletasks()
        _round_window_corners(self.window)

        # ── Border ──
        self.border = tk.Frame(self.window, bg="#3C3C3C", padx=1, pady=1)
        self.border.pack(fill="both", expand=True)

        # ── Container ──
        self.container = tk.Frame(self.border, bg="#202020")
        self.container.pack(fill="both", expand=True)

        # ── Header: file context (left) + balance (right) ──
        self.balance_frame = tk.Frame(self.container, bg="#202020")
        self.balance_frame.pack(fill="x", padx=14, pady=(8, 0))

        # Left: file name + size/duration (truncated, never overlaps right)
        self.file_left = tk.Frame(self.balance_frame, bg="#202020")
        self.file_left.pack(side="left", fill="x", expand=True)

        self.file_info_name_top = tk.Label(
            self.file_left, text="", font=("Segoe UI Variable", 12),
            bg="#202020", fg="#FFFFFF", anchor="w",
        )
        self.file_info_name_top.pack(side="left")

        self.file_info_dur_top = tk.Label(
            self.file_left, text="", font=("Segoe UI Variable", 12),
            bg="#202020", fg="#9A9A9A", anchor="w",
        )
        self.file_info_dur_top.pack(side="left", padx=(8, 0))

        # Right: balance pill + hotkey keycap
        self.balance_right = tk.Frame(self.balance_frame, bg="#202020")
        self.balance_right.pack(side="right")

        # Balance pill (rounded chip)
        self.balance_pill = tk.Canvas(self.balance_right, height=28, bg="#202020",
                                      highlightthickness=0, bd=0)
        self.balance_pill.pack(side="left", padx=(0, 8))
        self.balance_content = tk.Frame(self.balance_pill, bg="#2B2B2B", padx=10, pady=3)
        self._balance_win = self.balance_pill.create_window(0, 0, anchor="nw", window=self.balance_content)

        self.balance_icon = tk.Label(
            self.balance_content, text="", font=("Segoe UI Variable", 12),
            bg="#2B2B2B", fg="#60CDFF", width=2, anchor="center",
        )
        self.balance_icon.pack(side="left", padx=(0, 2))
        self.balance_photo = None
        try:
            if getattr(sys, "frozen", False):
                assets_dir = os.path.join(sys._MEIPASS, "docs", "assets")
            else:
                assets_dir = os.path.join(BASE_DIR, "docs", "assets")
            icon_path = os.path.join(assets_dir, "slippers.png")
            source = Image.open(icon_path).convert("RGBA")
            alpha = source.getchannel("A").resize((20, 20), Image.Resampling.LANCZOS)
            icon = Image.new("RGBA", (20, 20), "#60CDFF")
            icon.putalpha(alpha)
            self.balance_photo = ImageTk.PhotoImage(icon)
            self.balance_icon.config(image=self.balance_photo, text="", width=20)
        except Exception:
            pass

        self.balance_label = tk.Label(
            self.balance_content, text="", font=("Segoe UI Variable", 12, "bold"),
            bg="#2B2B2B", fg="#60CDFF", anchor="e",
        )
        self.balance_label.pack(side="left")

        self.balance_hotkey = tk.Label(
            self.balance_right, text="Ctrl+0", font=("Segoe UI Variable", 12),
            bg="#202020", fg="#9A9A9A", anchor="e", padx=6, pady=2,
        )
        self.balance_hotkey.pack(side="left", padx=(0, 2))

        self._balance_bg = "#2B2B2B"

        def _balance_hover(entering):
            self._balance_bg = "#0078D4" if entering else "#2B2B2B"
            self.balance_content.config(bg=self._balance_bg)
            self.balance_icon.config(bg=self._balance_bg)
            self.balance_label.config(bg=self._balance_bg,
                                      fg="#FFFFFF" if entering else "#60CDFF")
            self._redraw_balance_pill()

        # Make the balance pill clickable to open the balance page.
        for _w in (self.balance_pill, self.balance_content, self.balance_icon,
                   self.balance_label, self.balance_hotkey):
            _w.config(cursor="hand2")
            _w.bind("<Button-1>", lambda e: self._open_currency())
            _w.bind("<Enter>", lambda e: _balance_hover(True))
            _w.bind("<Leave>", lambda e: _balance_hover(False))

        self._update_balance()
        threading.Thread(target=self._refresh_balance, daemon=True).start()

        # ── Input field (search, rounded) ──
        self.entry_border = tk.Canvas(self.container, height=40, bg="#202020",
                                      highlightthickness=0, bd=0)
        self.entry_border.pack(fill="x", padx=14, pady=(8, 8))
        self._entry_outline = "#3C3C3C"

        self.entry_shell = tk.Frame(self.entry_border, bg="#2B2B2B", padx=5)
        self._entry_win = self.entry_border.create_window(4, 4, anchor="nw", window=self.entry_shell)
        self.entry_border.bind("<Configure>", self._redraw_entry_round)

        # Search icon (left)
        self.search_icon_lbl = tk.Label(self.entry_shell, text="", bg="#2B2B2B", fg="#9A9A9A")
        self.search_icon_lbl.pack(side="left", padx=(2, 6), pady=4)
        self.search_photo = None
        try:
            if getattr(sys, "frozen", False):
                assets_dir = os.path.join(sys._MEIPASS, "docs", "assets")
            else:
                assets_dir = os.path.join(BASE_DIR, "docs", "assets")
            icon_path = os.path.join(assets_dir, "search.png")
            source = Image.open(icon_path).convert("RGBA")
            alpha = source.getchannel("A").resize((16, 16), Image.Resampling.LANCZOS)
            icon = Image.new("RGBA", (16, 16), "#9A9A9A")
            icon.putalpha(alpha)
            self.search_photo = ImageTk.PhotoImage(icon)
            self.search_icon_lbl.config(image=self.search_photo)
        except Exception:
            pass

        # Clear button (right, hidden until text)
        self.clear_btn = tk.Label(self.entry_shell, text="\u00d7", font=("Segoe UI Variable", 14),
                                  bg="#2B2B2B", fg="#9A9A9A", cursor="hand2", padx=6, pady=4)
        self.clear_btn.bind("<Button-1>", lambda e: self._clear_entry())

        self.entry = tk.Entry(
            self.entry_shell,
            font=("Segoe UI Variable", 14),
            bg="#2B2B2B",
            fg="#FFFFFF",
            disabledbackground="#2B2B2B",
            disabledforeground="#C5C5C5",
            insertbackground="#9A9A9A",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
        )
        self.entry.pack(side="left", fill="x", expand=True, pady=4)
        self.placeholder_text = "Search actions..."
        self._placeholder_active = True
        self.entry.insert(0, self.placeholder_text)
        self.entry.config(fg="#C5C5C5")

        self.entry.bind("<FocusIn>", self._on_entry_focus_in)
        self.entry.bind("<FocusOut>", self._on_entry_focus_out)
        self.entry.bind("<KeyPress>", self._on_entry_keypress)
        self.entry.bind("<KeyRelease>", self._on_key)
        self.entry.bind("<Escape>", lambda e: self._hide())
        self.entry.bind("<Down>", self._select_next)
        self.entry.bind("<Up>", self._select_prev)

        self.window.bind("<Return>", self._on_enter)
        self.window.bind("<Escape>", lambda e: self._hide())

        # ── Result list (hidden until input) ──
        self.list_frame = tk.Frame(self.container, bg="#202020")
        self._skill_rows = []
        self._special_widgets = []

        # Scrollable skill list + thin custom scrollbar
        self.list_view = tk.Frame(self.list_frame, bg="#202020")
        self.list_view.pack_propagate(False)
        self.list_canvas = tk.Canvas(self.list_view, bg="#202020", highlightthickness=0, bd=0)
        self.list_inner = tk.Frame(self.list_canvas, bg="#202020")
        self._list_window = self.list_canvas.create_window((0, 0), window=self.list_inner, anchor="nw")
        self.list_inner.bind("<Configure>", lambda e: (self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all")), self._update_scrollbar()))
        self.list_canvas.bind("<Configure>", lambda e: (self.list_canvas.itemconfigure(self._list_window, width=e.width), self._update_scrollbar()))
        self.list_canvas.bind("<Enter>", lambda e: self.list_canvas.bind_all("<MouseWheel>", self._on_list_wheel))
        self.list_canvas.bind("<Leave>", lambda e: self.list_canvas.unbind_all("<MouseWheel>"))
        self.list_canvas.pack(side="left", fill="both", expand=True)
        self.scroll_canvas = tk.Canvas(self.list_view, bg="#202020", width=6, highlightthickness=0, bd=0)
        self.scroll_canvas.bind("<Button-1>", self._on_scrollbar_click)
        self.special_frame = tk.Frame(self.list_frame, bg="#202020")
        self.special_frame.pack(side="bottom", fill="x", padx=4, pady=(0, 2))
        self.list_view.pack(side="top", fill="x")

        # ── Response area (hidden until result) ──
        self.separator = tk.Frame(self.container, bg="#3C3C3C", height=1)
        self.result_box = tk.Text(
            self.container,
            font=("Segoe UI Variable", 14),
            bg="#202020",
            fg="#FFFFFF",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            wrap="word",
            state="disabled",
        )
        self.skill_hint = tk.Frame(self.container, bg="#202020")
        self._ctrl_alt_label = tk.Label(
            self.skill_hint,
            text="Ctrl+Alt - hide",
            font=("Segoe UI Variable", 12),
            bg="#202020",
            fg="#C5C5C5",
        )
        self._ctrl_alt_label.pack(side="left")
        tk.Label(
            self.skill_hint,
            text="Enter - run action",
            font=("Segoe UI Variable", 12),
            bg="#202020",
            fg="#C5C5C5",
        ).pack(side="right")
        self.copy_hint_label = tk.Label(
            self.skill_hint,
            text="Copy a file to see its exact price",
            font=("Segoe UI Variable", 12),
            bg="#202020",
            fg="#9A9A9A",
            anchor="center",
        )
        self.copy_hint_label.pack(side="left", fill="x", expand=True)
        self.hint_label = tk.Frame(self.container, bg="#202020")
        tk.Label(
            self.hint_label,
            text="Enter - copy to clipboard and close",
            font=("Segoe UI Variable", 12),
            bg="#202020",
            fg="#C5C5C5",
        ).pack(side="left")
        # Chain bar — quick actions on result
        self.chain_frame = tk.Frame(self.container, bg="#202020")
        self._chain_btns = []

        # Processing animation
        self._anim_job = None
        self._anim_skill = ""
        self._anim_frame = 0

        self.window.attributes("-topmost", True)
        self.window.update_idletasks()
        self.window.lift()

        # Drop topmost after focus so other windows can be clicked
        self.window.after(300, lambda: self.window and self.window.attributes("-topmost", False))

        # Hide when clicking outside
        self.window.bind("<FocusOut>", self._on_focus_out)

        # Hotkeys: chain actions (when result shown) or special actions (in menu)
        self.window.bind("<Control-Key-0>", lambda e: self._on_hotkey(0))
        self.window.bind("<Control-Key-1>", lambda e: self._on_hotkey(1))
        self.window.bind("<Control-Key-2>", lambda e: self._on_hotkey(2))
        self.window.bind("<Control-Key-3>", lambda e: self._on_hotkey(3))

        self.visible = True
        self.selected_index = 0
        self.in_store = False
        self.in_currency = False
        self.store_frame = None
        self.processing = False
        self._bar_fade_in()

        # If there's a pending result from a background task, show it
        if self.pending_result is not None:
            self.has_result = True
            self.last_result = self.pending_result
            self.pending_result = None
            self.processing = False
            self.list_frame.pack_forget()
            self.entry.config(state="disabled")
            self._show_result(self.last_result)
        else:
            self.has_result = False
            self.last_result = ""
            self._update_filter("")

        self.window.after(50, self._force_focus)

    def _force_focus(self, attempt=0):
        """Force focus via Windows API."""
        if not self.window:
            return

        try:
            hwnd = int(self.window.wm_frame(), 16)
            fg = ctypes.windll.user32.GetForegroundWindow()
            tid_fg = ctypes.windll.user32.GetWindowThreadProcessId(fg, None)
            tid_self = ctypes.windll.kernel32.GetCurrentThreadId()
            ctypes.windll.user32.AttachThreadInput(tid_fg, tid_self, True)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.BringWindowToTop(hwnd)
            ctypes.windll.user32.AttachThreadInput(tid_fg, tid_self, False)
        except Exception:
            pass

        self.window.focus_force()
        self.entry.focus_set()

        # Retry up to 3 times — sometimes OS delays focus
        if attempt < 3:
            self.window.after(80, lambda: self._force_focus(attempt + 1))

    def _on_focus_out(self, event):
        """Close only if focus truly left the window (delayed check)."""
        if not self.window or self.processing:
            return
        self.window.after(150, self._check_focus)

    def _check_focus(self):
        """Verify focus is still lost before hiding."""
        if not self.window:
            return
        try:
            focused = self.window.focus_get()
            if focused is None:
                self._hide()
        except (KeyError, tk.TclError):
            self._hide()

    def _bar_fade_in(self, step=0):
        if not self.window or not self.visible:
            return
        total = 12
        p = _ease_out_cubic(step / total)
        try:
            self.window.attributes("-alpha", p)
            ty = getattr(self, "_bar_y0", None)
            tx = getattr(self, "_bar_x0", None)
            if ty is not None and tx is not None:
                ny = ty + int(10 * (1 - p))
                self.window.geometry(f"+{tx}+{ny}")
        except Exception:
            return
        if step < total:
            self.root.after(16, lambda: self._bar_fade_in(step + 1))

    def _hide(self):
        if self.window:
            self.visible = False
            self._clip_seq_at_hide = _clip_seq()
            win = self.window
            self.window = None
            self._bar_fade_out(win, 1.0)

    def _bar_fade_out(self, win, alpha):
        alpha = max(alpha - 0.12, 0.0)
        try:
            win.attributes("-alpha", alpha)
        except Exception:
            return
        if alpha > 0.0:
            self.root.after(16, lambda: self._bar_fade_out(win, alpha))
        else:
            try:
                win.destroy()
            except Exception:
                pass

    def _restore_placeholder_cursor(self):
        if self._placeholder_active and self.entry.winfo_exists():
            self.entry.selection_clear()
            self.entry.icursor(0)

    def _redraw_entry_round(self, event=None):
        c = self.entry_border
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 10 or h < 10:
            return
        c.delete("round")
        _rounded_rect(c, 1, 1, w - 1, h - 1, 4, fill="#2B2B2B",
                      outline=self._entry_outline, width=1, tags="round")
        c.tag_lower("round")
        c.coords(self._entry_win, 4, 4)
        c.itemconfigure(self._entry_win, width=w - 8, height=h - 8)

    def _on_entry_focus_in(self, event):
        self._entry_outline = "#404040"
        self._redraw_entry_round()
        if self._placeholder_active:
            self._restore_placeholder_cursor()
            self.root.after_idle(self._restore_placeholder_cursor)

    def _on_entry_focus_out(self, event):
        self._entry_outline = "#3C3C3C"
        self._redraw_entry_round()
        if not self._placeholder_active and not self.entry.get():
            self.entry.insert(0, self.placeholder_text)
            self._placeholder_active = True
            self.entry.config(fg="#C5C5C5")
        self._update_clear_btn()

    def _on_entry_keypress(self, event):
        if not self._placeholder_active:
            return
        if event.keysym in ("BackSpace", "Delete"):
            return "break"
        if event.char:
            self.entry.delete(0, "end")
            self._placeholder_active = False
            self.entry.config(fg="#FFFFFF")

    def _update_clear_btn(self):
        """Show the × clear button only when there is real text."""
        if not hasattr(self, "clear_btn"):
            return
        has_text = not self._placeholder_active and bool(self.entry.get().strip())
        mapped = self.clear_btn.winfo_ismapped()
        if has_text and not mapped:
            self.clear_btn.pack(side="right", padx=(2, 0))
        elif not has_text and mapped:
            self.clear_btn.pack_forget()

    def _clear_entry(self):
        """Clear the search field and reset the filter."""
        self.entry.delete(0, "end")
        self._placeholder_active = False
        self.entry.config(fg="#FFFFFF")
        self._update_clear_btn()
        self._update_filter("")
        self.entry.focus_set()

    def _on_key(self, event):
        if event.keysym in ("Return", "Escape", "Up", "Down"):
            return
        if str(self.entry.cget("state")) == "disabled":
            return
        query = "" if self._placeholder_active else self.entry.get()
        if query:
            try:
                self._hide_chain()
            except Exception:
                pass
        self._update_filter(query)
        self._update_clear_btn()

    def _update_filter(self, query):
        """Filters skills by input. Pinned skills float to top when no filter."""
        q = query.lower().strip()
        if q:
            self.filtered = [
                s for s in self.skills
                if q in s["title"].lower()
            ]
        else:
            pinned = main_pins.get_pinned_skills(self.skills)
            rest = [s for s in self.skills if s["title"] not in main_pins.load()]
            self.filtered = pinned + rest

        self._render_list()

    def _render_list(self):
        """Renders the dropdown list."""
        if not self.window:
            return
        # Resolve the current file/URL (if any) for live per-file pricing.
        try:
            _inp = core.get_input()
            _file = ""
            _url = ""
            if _inp and _inp.get("type") == "file":
                _file = _inp["data"]
            elif _inp and _inp.get("type") == "text":
                _data = (_inp.get("data") or "").strip()
                if _data.lower().startswith(("http://", "https://")):
                    _url = _data
            # Reset a file that was already shown before the last hide.
            if _file and self._clip_seq_at_hide is not None and _clip_seq() == self._clip_seq_at_hide:
                _file = ""
            self._preview_file = _file
            self._preview_url = _url
        except Exception:
            self._preview_file = ""
            self._preview_url = ""
        # Float skills that accept the selected file type to the top.
        if self._preview_file:
            _ext = os.path.splitext(self._preview_file)[1].lower()
            if _ext:
                self.filtered.sort(key=lambda s: 0 if _ext in (s.get("input_type") or []) else 1)
        # Format file info (name + metadata) for both preview labels.
        self._preview_duration = None
        self._preview_unit = ""
        if self._preview_url:
            name = self._preview_url
            if len(name) > 32:
                name = name[:29] + "..."
            self.file_info_name_top.config(text=name, fg="#FFFFFF")
            self.file_info_dur_top.config(text="")
        elif self._preview_file:
            self._preview_duration, self._preview_unit = _measure_file(self.skills, self._preview_file)
        if self._preview_file:
            name = os.path.basename(self._preview_file)
            if len(name) > 32:
                ext = os.path.splitext(name)[1]
                head = 32 - len(ext) - 3
                name = name[:max(head, 4)] + "..." + ext
            dur = self._preview_duration
            dur_text = _format_measure(dur, self._preview_unit) if dur is not None else ""
            self.file_info_name_top.config(text=name, fg="#FFFFFF")
            self.file_info_dur_top.config(text=dur_text)
        elif not self._preview_url:
            self.file_info_name_top.config(text="file not selected", fg="#60CDFF")
            self.file_info_dur_top.config(text="")
        # Clear old rows
        for row in self._skill_rows:
            row.destroy()
        self._skill_rows = []
        for w in self._special_widgets:
            w.destroy()
        self._special_widgets = []

        if not self.filtered:
            # No actions installed: keep the bottom action bar (store, support,
            # wish box) reachable and give the window a minimal height instead
            # of collapsing it entirely.
            self.list_view.pack_forget()
            self.copy_hint_label.pack_forget()
            self.special_frame.pack(side="bottom", fill="x", padx=4, pady=(0, 2))
            self._render_special_actions()
            self.list_frame.pack(fill="x", padx=14, pady=(0, 2))
            self.skill_hint.pack(fill="x", padx=12, pady=(0, 6))
            self.window.update_idletasks()
            self._resize(self.container.winfo_reqheight() + 4)
            return

        # Restore the list area (hidden above when there were no actions).
        if self._preview_file:
            self.copy_hint_label.pack_forget()
        else:
            self.copy_hint_label.pack(side="left", fill="x", expand=True)
        self.list_view.pack(side="top", fill="x")

        for i, p in enumerate(self.filtered):
            skill_id = p.get("filename", "").replace(".py", "")
            row = self._make_row(p["title"], p["description"], i, pinnable=True, skill_id=skill_id)
            self._skill_rows.append(row)

        # Compact special-action bar — only when no filter is active
        if self._placeholder_active or not self.entry.get().strip():
            self.special_frame.pack(side="bottom", fill="x", padx=4, pady=(0, 2))
            self._render_special_actions()
        else:
            self.special_frame.pack_forget()

        self.list_frame.pack(fill="x", padx=14, pady=(0, 2))
        self.skill_hint.pack(fill="x", padx=12, pady=(0, 6))

        self.window.update_idletasks()

        wa = self._work_area()
        max_window_height = max(wa[3] - self.window.winfo_y() - 16, 100) if wa else None

        if max_window_height:
            # Fixed-height window: smaller than the full max, but still tall.
            work_h = wa[3] - wa[1]
            fixed_height = min(int(work_h * 0.55), max_window_height)
            self.list_view.config(height=1)
            self.window.update_idletasks()
            other = self.container.winfo_reqheight()
            list_height = max(fixed_height - other + 1, 80)
            self.list_view.config(height=list_height)
            self.window.update_idletasks()
            self._resize(fixed_height)
        else:
            # Non-Windows fallback: natural height.
            list_natural = self.list_inner.winfo_reqheight()
            self.list_view.config(height=list_natural)
            self.window.update_idletasks()
            needed = self.container.winfo_reqheight()
            self._resize(needed + 4)

        max_idx = len(self._skill_rows) - 1
        self.selected_index = max(0, min(self.selected_index, max_idx))
        self._highlight_row()
        self._update_scrollbar()

    def _make_row(self, title, desc, idx, pinnable=False, skill_id=None):
        """Creates a single skill row with title (bright) and description (dim)."""
        row = tk.Frame(self.list_inner, bg="#202020", cursor="hand2")
        row.pack(fill="x", padx=0, pady=1)

        skill_obj = self.filtered[idx] if idx < len(self.filtered) else None

        left = tk.Frame(row, bg="#202020")
        left.pack(side="left", fill="x", expand=True, padx=12, pady=6)

        title_lbl = tk.Label(left, text=_truncate(title, 40), font=("Segoe UI Variable", 14),
                             bg="#202020", fg="#FFFFFF", anchor="w")
        title_lbl.pack(anchor="w")

        # Description (secondary, truncated — never overlaps the price)
        desc_lbl = None
        if desc:
            desc_lbl = tk.Label(left, text=_truncate(desc, 60),
                                font=("Segoe UI Variable", 12),
                                bg="#202020", fg="#9A9A9A", anchor="w")
            desc_lbl.pack(anchor="w")

        # Input → output chip (separate, noticeable badge)
        io_chip = None
        if skill_obj:
            io_text = _io_label(skill_obj)
            if io_text:
                io_chip = tk.Label(left, text=io_text,
                                   font=("Segoe UI Variable", 11),
                                   bg="#2B2B2B", fg="#C5C5C5",
                                   padx=6, pady=1, anchor="w")
                io_chip._keep_bg = True
                io_chip.pack(anchor="w", pady=(3, 0))

        # Mode after title (grey, in parentheses)
        # if skill_obj:
        #     mode = str(skill_obj.get("mode", "cloud")).strip().lower()
        #     mode_text = "Cloud" if mode == "cloud" else "Local"
        #     mode_lbl = tk.Label(row, text=f"({mode_text})", font=("Segoe UI Variable", 12),
        #                         bg="#202020", fg="#C5C5C5")
        #     mode_lbl.pack(side="left", padx=(2, 0))
        #     mode_lbl.bind("<Button-1>", lambda e, i=idx: self._click_row(i))

        if pinnable:
            # Main-bar pin + star hidden for now.
            # mpinned = main_pins.is_pinned(title)
            # pin_lbl = tk.Label(
            #     row,
            #     text="\ue718" if mpinned else "\ue77a",
            #     font=("Segoe MDL2 Assets", 12),
            #     bg="#202020",
            #     fg="#60CDFF" if mpinned else "#C5C5C5",
            #     cursor="hand2",
            #     padx=4,
            # )
            # pin_lbl.pack(side="right")
            # pin_lbl.bind("<Button-1>", lambda e, t=title: self._toggle_main_pin(t))
            #
            # pinned = pins_module.is_pinned(title)
            # star_lbl = tk.Label(
            #     row,
            #     text="\ue735" if pinned else "\ue734",
            #     font=("Segoe MDL2 Assets", 13),
            #     bg="#202020",
            #     fg="#f9e2af" if pinned else "#C5C5C5",
            #     cursor="hand2",
            #     padx=6,
            # )
            # star_lbl.pack(side="right")
            # star_lbl.bind("<Button-1>", lambda e, t=title: self._toggle_pin(t))

            # Edit button for custom skills (left of star)
            if skill_obj and skill_obj.get("filename", "").startswith("custom_"):
                edit_lbl = tk.Label(
                    row, text="\ue70f",
                    font=("Segoe MDL2 Assets", 11),
                    bg="#202020", fg="#60CDFF",
                    cursor="hand2", padx=4,
                )
                edit_lbl.pack(side="right")
                edit_lbl.bind("<Button-1>", lambda e, s=skill_obj: self._open_edit_skill_editor(s))

            # Settings gear for skills that declare a settings schema (left of star)
            if skill_obj and skill_settings.has_settings(skill_obj):
                gear_lbl = tk.Label(
                    row, text="\ue713",
                    font=("Segoe MDL2 Assets", 12),
                    bg="#202020", fg="#C5C5C5",
                    cursor="hand2", padx=4,
                )
                gear_lbl.pack(side="right")
                gear_lbl.bind("<Button-1>", lambda e, s=skill_obj: self._open_skill_settings(s))

        # File support + price (right side)
        _price = int(skill_obj.get("price", 0) or 0) if skill_obj else 0
        _ppu = int(skill_obj.get("price_per_unit", 0) or 0) if skill_obj else 0
        _unit = (skill_obj.get("unit") or "").strip() if skill_obj else ""
        _file = getattr(self, "_preview_file", "")
        _ext = os.path.splitext(_file)[1].lower() if _file else ""
        _types = skill_obj.get("input_type") or []
        _unsupported = bool(_file) and bool(_types) and _ext not in _types

        if skill_obj and _unsupported:
            price_lbl = tk.Label(row, text="file type not supported",
                                 font=("Segoe UI Variable", 12),
                                 bg="#202020", fg="#9A9A9A")
            price_lbl.pack(side="right", padx=(8, 0), pady=13)
            price_lbl.bind("<Button-1>", lambda e, i=idx: self._click_row(i))
        elif skill_obj and (_price > 0 or _ppu > 0):
            icon_photo = self._slippers_icon(26)
            if icon_photo:
                icon_lbl = tk.Label(row, image=icon_photo, bg="#202020")
            else:
                icon_lbl = tk.Label(row, text="🩴", font=("Segoe UI Emoji", 11),
                                    bg="#202020", fg="#60CDFF")
            icon_lbl.pack(side="right", padx=(2, 4), pady=13)
            icon_lbl.bind("<Button-1>", lambda e, i=idx: self._click_row(i))

            if _ppu > 0 and _unit:
                if _file:
                    _label = f"{_format_price(_skill_price(skill_obj, _file))} for copied file"
                else:
                    _label = f"{_format_price(_ppu)}/{_unit}"
            else:
                _label = _format_price(_price)
            price_lbl = tk.Label(row, text=_label,
                                 font=("Segoe UI Variable", 12),
                                 bg="#202020", fg="#60CDFF")
            price_lbl.pack(side="right", padx=(8, 0), pady=13)
            price_lbl.bind("<Button-1>", lambda e, i=idx: self._click_row(i))

        # Click handler
        row.bind("<Button-1>", lambda e, i=idx: self._click_row(i))
        left.bind("<Button-1>", lambda e, i=idx: self._click_row(i))
        title_lbl.bind("<Button-1>", lambda e, i=idx: self._click_row(i))
        if desc_lbl:
            desc_lbl.bind("<Button-1>", lambda e, i=idx: self._click_row(i))
        if io_chip:
            io_chip.bind("<Button-1>", lambda e, i=idx: self._click_row(i))

        # Hover highlight (subtle)
        for w in [row, left, title_lbl] + ([desc_lbl] if desc_lbl else []) + ([io_chip] if io_chip else []):
            w.bind("<Enter>", lambda e, r=row: self._row_hover(r, True))
            w.bind("<Leave>", lambda e, r=row: self._row_hover(r, False))

        return row

    def _tinted_icon(self, filename, size=24, color="#FFFFFF"):
        """Return a cached tinted PhotoImage for a monochrome PNG, or None."""
        key = (filename, size, color)
        cache = getattr(self, "_tinted_icons", None)
        if cache is None:
            cache = {}
            self._tinted_icons = cache
        if key in cache:
            return cache[key]
        try:
            if getattr(sys, "frozen", False):
                assets_dir = os.path.join(sys._MEIPASS, "docs", "assets")
            else:
                assets_dir = os.path.join(BASE_DIR, "docs", "assets")
            icon_path = os.path.join(assets_dir, filename)
            source = Image.open(icon_path).convert("RGBA")
            alpha = source.getchannel("A").resize((size, size), Image.Resampling.LANCZOS)
            icon = Image.new("RGBA", (size, size), color)
            icon.putalpha(alpha)
            photo = ImageTk.PhotoImage(icon)
            cache[key] = photo
            return photo
        except Exception:
            return None

    def _slippers_icon(self, size=14):
        """Return a cached green slippers icon PhotoImage, or None."""
        return self._tinted_icon("slippers.png", size, "#60CDFF")

    def _render_special_actions(self):
        """Render compact special-action buttons below the skill list (chain-bar style)."""
        sep = tk.Frame(self.special_frame, bg="#3C3C3C", height=1)
        sep.pack(fill="x", padx=4, pady=(3, 2))
        self._special_widgets.append(sep)

        grid = tk.Frame(self.special_frame, bg="#202020")
        grid.pack(fill="x", padx=4, pady=(0, 0))
        self._special_widgets.append(grid)
        for c in range(3):
            grid.columnconfigure(c, weight=1, uniform="special")

        actions = [
            # ("📁", "Open actions folder", "Ctrl+1", self._open_skills_folder, False, None),
            ("", "Want another action?", "Ctrl+1", self._open_wish_box, False, "wish.png"),
            ("", "I have a problem", "Ctrl+2", self._open_problem, False, "support.png"),
            ("", "Actions Store", "Ctrl+3", self._open_store, True, "store.png"),
        ]
        for i, (icon, label, hotkey, handler, accent, icon_file) in enumerate(actions):
            fg = "#60CDFF" if accent else "#FFFFFF"
            hover_bg = "#0078D4" if accent else "#3C3C3C"

            photo = self._tinted_icon(icon_file, 19, "#FFFFFF") if icon_file else None
            if photo:
                btn = tk.Label(
                    grid, image=photo, text=f"{label}\n[{hotkey}]",
                    compound="top", font=("Segoe UI Variable", 12),
                    bg="#2B2B2B", fg=fg, cursor="hand2",
                    padx=4, pady=4.29, justify="center",
                )
            else:
                btn = tk.Label(
                    grid, text=f"{icon}\n{label}\n[{hotkey}]", font=("Segoe UI Variable", 12),
                    bg="#2B2B2B", fg=fg, cursor="hand2",
                    padx=4, pady=4, justify="center",
                )

            btn.grid(row=0, column=i, sticky="ew", padx=(0, 4) if i < 2 else (0, 0))
            btn.bind("<Button-1>", lambda e, h=handler: h())
            btn.bind("<Enter>", lambda e, b=btn, hb=hover_bg, f=fg: b.config(bg=hb, fg=f))
            btn.bind("<Leave>", lambda e, b=btn, f=fg: b.config(bg="#2B2B2B", fg=f))

    def _open_discord(self):
        import webbrowser
        telemetry.send("feedback_clicked")
        webbrowser.open("https://discord.gg/dc6VwAgCpc")

    def _open_telegram(self):
        import webbrowser
        telemetry.send("telegram_clicked")
        webbrowser.open("https://t.me/+dyNesmgH1w9lOGJi")

    def _open_new_skill_editor(self):
        def on_saved():
            self.skills = core.scan_skills()
            self._update_filter(self.entry.get())
        skill_editor.open_editor(self.root, SKILLS_DIR, on_saved=on_saved)

    def _open_edit_skill_editor(self, skill):
        def on_saved():
            self.skills = core.scan_skills()
            self._update_filter(self.entry.get())
        skill_editor.open_editor(self.root, SKILLS_DIR, on_saved=on_saved, skill=skill)

    def _open_skill_settings(self, skill):
        def on_saved():
            self.skills = core.scan_skills()
            self._update_filter(self.entry.get())
        skill_settings.open_settings(self.root, skill, on_saved=on_saved)

    def _toggle_pin(self, title):
        pins_module.toggle(title)
        self._render_list()

    def _toggle_main_pin(self, title):
        main_pins.toggle(title)
        self._update_filter(self.entry.get())

    def _click_row(self, idx):
        """Handle click on a skill row."""
        self.selected_index = idx
        self._highlight_row()
        self._on_enter(None)

    def _set_bg_recursive(self, widget, bg):
        """Set bg on a widget and all its descendants (nested frames)."""
        if getattr(widget, "_keep_bg", False):
            return
        try:
            widget.config(bg=bg)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._set_bg_recursive(child, bg)

    def _highlight_row(self):
        """Highlights the selected row."""
        for i, row in enumerate(self._skill_rows):
            bg = "#383838" if i == self.selected_index else "#202020"
            self._set_bg_recursive(row, bg)

    def _row_hover(self, row, entering):
        """Subtle hover highlight for a skill row (skips the selected row)."""
        try:
            idx = self._skill_rows.index(row)
        except ValueError:
            return
        if idx == self.selected_index:
            return
        self._set_bg_recursive(row, "#2E2E2E" if entering else "#202020")

    def _work_area(self):
        """Return (left, top, right, bottom) of the work area (screen minus taskbar)."""
        try:
            from ctypes import wintypes
            rect = wintypes.RECT()
            # SPI_GETWORKAREA = 0x0030 — primary monitor work area (excludes taskbar).
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                return (rect.left, rect.top, rect.right, rect.bottom)
        except Exception:
            pass
        return None

    def _resize(self, height):
        """Updates window height, clamped to the screen work area (above taskbar)."""
        if not self.window:
            return
        wa = self._work_area()
        if wa:
            # Never extend below the Windows taskbar; leave a small gap above it.
            max_height = max(wa[3] - self.window.winfo_y() - 16, 100)
            height = min(height, max_height)
        w = self.window.winfo_width()
        x = self.window.winfo_x()
        y = self.window.winfo_y()
        self.window.geometry(f"{w}x{height}+{x}+{y}")
        self.window.update_idletasks()

    def _on_list_wheel(self, event):
        """Scroll the skill list with the mouse wheel."""
        try:
            self.list_canvas.yview_scroll(int(-event.delta / 120), "units")
        except Exception:
            pass
        self._update_scrollbar()

    def _update_scrollbar(self):
        """Render the thin custom scrollbar (hidden when content fits)."""
        if not hasattr(self, "scroll_canvas"):
            return
        try:
            bbox = self.list_canvas.bbox("all") or (0, 0, 0, 0)
            content_h = bbox[3] - bbox[1]
            viewport_h = self.list_canvas.winfo_height()
        except Exception:
            return
        if content_h <= viewport_h + 2:
            self.scroll_canvas.place_forget()
            return
        # Overlay at the right edge (does not shift the list grid, like Win11).
        self.scroll_canvas.place(relx=1.0, x=-7, rely=0.0, y=3, relheight=1.0, height=-6, width=6)
        self.list_canvas.update_idletasks()
        sb_h = self.scroll_canvas.winfo_height()
        if sb_h <= 0:
            return
        thumb_h = max(20, int(viewport_h / content_h * sb_h))
        top_frac = self.list_canvas.yview()[0]
        thumb_y = int(top_frac * (sb_h - thumb_h))
        self.scroll_canvas.delete("all")
        _rounded_rect(self.scroll_canvas, 0, thumb_y, 6, thumb_y + thumb_h, 3, fill="#404040", outline="")

    def _on_scrollbar_click(self, event):
        """Jump the list to the clicked position on the thin scrollbar."""
        try:
            sb_h = self.scroll_canvas.winfo_height()
            if sb_h <= 0:
                return
            frac = max(0.0, min(1.0, event.y / sb_h))
            self.list_canvas.yview_moveto(frac)
            self._update_scrollbar()
        except Exception:
            pass

    def _scroll_to_selected(self):
        """Keep the selected row visible inside the scrollable list."""
        if not self._skill_rows:
            return
        try:
            row = self._skill_rows[self.selected_index]
            row_y = row.winfo_y()
            row_h = row.winfo_height()
            view_h = self.list_canvas.winfo_height()
            top = self.list_canvas.canvasy(0)
            bottom = top + view_h
            content_h = max(1, self.list_inner.winfo_height())
            if row_y < top:
                self.list_canvas.yview_moveto(row_y / content_h)
            elif row_y + row_h > bottom:
                self.list_canvas.yview_moveto((row_y + row_h - view_h) / content_h)
        except Exception:
            pass

    def _select_next(self, event):
        if self._skill_rows:
            max_idx = len(self._skill_rows) - 1
            self.selected_index = min(self.selected_index + 1, max_idx)
            self._highlight_row()
            self._scroll_to_selected()

    def _select_prev(self, event):
        if self._skill_rows:
            self.selected_index = max(self.selected_index - 1, 0)
            self._highlight_row()
            self._scroll_to_selected()

    def _auto_paste(self):
        """Restore focus to source window and paste result."""
        hwnd = self._source_hwnd
        self._source_hwnd = None
        if not hwnd:
            return
        def _do():
            time.sleep(0.12)
            try:
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                time.sleep(0.06)
                keyboard.send("ctrl+v")
            except Exception:
                pass
        threading.Thread(target=_do, daemon=True).start()

    def _run_command(self, query):
        """Handle slash commands typed in the search bar."""
        cmd = query[1:].strip().lower()
        if cmd == "id-mine":
            uid = wallet.user_id()
            self.last_result = uid
            self.last_skill_title = "id-mine"
            self.has_result = True
            self._show_result(uid)
        elif cmd == "actions-folder":
            os.makedirs(SKILLS_DIR, exist_ok=True)
            os.startfile(SKILLS_DIR)
            self.last_result = SKILLS_DIR
            self.last_skill_title = "actions-folder"
            self.has_result = True
            self._show_result(SKILLS_DIR)
        else:
            self._show_result(f"Unknown command: {query}")

    def _on_enter(self, event):
        """Runs the selected skill or copies the result."""
        if self.in_store or self.in_currency:
            return
        if self.has_result:
            if self.last_result:
                pyperclip.copy(self.last_result + "\n\n— Scryptian")
                self._auto_paste()
                telemetry.send("result_copied", {"skill": getattr(self, "last_skill_title", "unknown")})
                print("[Scryptian] Copied to clipboard.")
            self._hide()
            return

        # Slash commands (e.g. /id-mine, /actions-folder)
        query = "" if self._placeholder_active else self.entry.get().strip()
        if query.startswith("/"):
            self._run_command(query)
            return

        if not self.filtered:
            return

        skill = self.filtered[self.selected_index]
        is_bg = bool(skill.get("background", False))

        # Resolve input (files only)
        inp = core.get_input()
        input_text = inp["data"] if inp else ""

        if not input_text.strip():
            self._show_result("No file. Copy a file first (Ctrl+C in Explorer), then try again.")
            return

        if not _file_supported(skill, input_text):
            self._show_result("File type not supported by this action.")
            return

        # ── Background (fire-and-forget) skills: run detached, free the bar ──
        if is_bg:
            self._run_background(skill, input_text)
            return

        # Hide list, show status
        # self.list_frame.pack_forget()
        # self.skill_hint.pack_forget()
        # self.entry.config(state="disabled")
        # self._start_anim(skill["title"])
        start_msg = "Started. You'll get a notification when it's done."
        bridge.notify(skill["title"], start_msg)
        if self.window:
            self._hide()

        self.processing = True
        print(f"[Scryptian] Running: {skill['title']}...")
        _t0 = time.time()
        _src = source_detect.get_source_info(getattr(self, '_source_hwnd', None))

        def execute():
            try:
                if not _reserve_skill(skill):
                    self.processing = False
                    self.root.after(0, self._stop_anim)
                    self.root.after(0, lambda: self._show_result("Not enough slippers. Top up your balance to run this action."))
                    return
                result = core.run_skill(skill, input_text)
                self.processing = False
                if result and not result.startswith("[Scryptian Error]"):
                    self.last_skill_title = skill["title"]
                    # self.root.after(0, lambda r=result: self._present_result(r))
                    telemetry.send("skill_run", _build_skill_event(skill, input_text, time.time() - _t0, **_src))
                    _track_skill(skill["filename"].replace(".py", ""))
                    _settle_skill(skill)
                    print(f"[Scryptian] Done!")
                    out_path = None
                    if isinstance(result, str) and result.startswith("[Scryptian File] "):
                        out_path = result[len("[Scryptian File] "):].strip()
                    if out_path:
                        bridge.notify(
                            skill["title"],
                            f"Saved to {os.path.basename(os.path.dirname(out_path))}",
                            action={
                                "label": "Open file",
                                "hotkey": "alt+q",
                                "callback": lambda p=out_path: tray.open_in_explorer(p),
                            },
                        )
                    else:
                        bridge.notify(skill["title"], result if isinstance(result, str) and result.strip() else "Done.")
                elif result and result.startswith("[Scryptian Error]"):
                    telemetry.send("skill_failed", {"name": skill["title"], "reason": "error", "error": result[:200]})
                    # self.root.after(0, lambda r=result: self._present_result(r))
                    bridge.notify(skill["title"], "Something went wrong. Please try again.")
                    _refund_skill(skill)
                else:
                    telemetry.send("skill_failed", {"name": skill["title"], "reason": "empty"})
                    # self.root.after(0, lambda: self._present_result("Skill returned an empty result."))
                    bridge.notify(skill["title"], "Something went wrong. Please try again.")
                    _refund_skill(skill)
            except Exception as e:
                telemetry.send("skill_failed", {"name": skill["title"], "reason": "exception", "error": str(e)[:200]})
                err_msg = f"Error: {e}"
                # self.root.after(0, lambda msg=err_msg: self._present_result(msg))
                bridge.notify(skill["title"], "Something went wrong. Please try again.")
                _refund_skill(skill)

        threading.Thread(target=execute, daemon=True).start()

    def _run_background(self, skill, input_text):
        """Run a background skill detached, then notify when done."""
        if getattr(self, "_bg_running", False):
            self._show_result("A background task is already running.\nPlease wait for it to finish.")
            return
        # if not self.visible:
        #     self._show()
        price = _skill_price(skill, input_text)
        if not _reserve_skill(skill, price):
            return
        self._bg_running = True
        print(f"[Scryptian] Running (background): {skill['title']}...")
        _bt0 = time.time()
        _bg_src = source_detect.get_source_info(getattr(self, '_source_hwnd', None))
        def bg_execute():
            try:
                result = core.run_skill(skill, input_text)
                if isinstance(result, str) and result.startswith("[Scryptian Error]"):
                    print(f"[Scryptian] Failed (background): {skill['title']} — {result}")
                    bridge.notify(skill["title"], "Something went wrong. Please try again.")
                    telemetry.send("skill_failed", {"name": skill["title"], "reason": "bg_error", "error": result[:200]})
                    _refund_skill(skill, price)
                else:
                    telemetry.send("skill_run", _build_skill_event(skill, input_text, time.time() - _bt0, **_bg_src, background=True))
                    _track_skill(skill["filename"].replace(".py", ""))
                    _settle_skill(skill, price)
                    print(f"[Scryptian] Done (background): {skill['title']}")
                    out_path = None
                    if isinstance(result, str) and result.startswith("[Scryptian File] "):
                        out_path = result[len("[Scryptian File] "):].strip()
                    if out_path:
                        bridge.notify(
                            skill["title"],
                            f"Saved to {os.path.basename(os.path.dirname(out_path))}",
                            action={
                                "label": "Open file",
                                "hotkey": "alt+q",
                                "callback": lambda p=out_path: tray.open_in_explorer(p),
                            },
                        )
                    else:
                        bridge.notify(skill["title"], result if isinstance(result, str) and result.strip() else "Done.")
            except Exception as e:
                print(f"[Scryptian] Background skill error: {e}")
                telemetry.send("skill_failed", {"name": skill["title"], "reason": "bg_exception", "error": str(e)[:200]})
                bridge.notify(skill["title"], "Something went wrong. Please try again.")
                _refund_skill(skill, price)
            finally:
                self._bg_running = False

        threading.Thread(target=bg_execute, daemon=True).start()
        start_msg = "Started. You'll get a notification when it's done."
        # self._show_result(start_msg)
        bridge.notify(skill["title"], start_msg)
        # if self.window:
        #     self.window.after(2500, self._hide)
        if self.window:
            self._hide()

    def open_bar(self, source_hwnd=None):
        """Open the full bar without running a skill (called from SelectionToolbar)."""
        if source_hwnd:
            self._source_hwnd = source_hwnd
        self.root.after(0, self._show)

    def run_externally(self, skill, input_text, source_hwnd=None):
        """Open the bar and run a skill with given text (called from SelectionToolbar)."""
        self._source_hwnd = source_hwnd
        pyperclip.copy(input_text)
        self.root.after(0, lambda: self._run_external(skill, input_text))

    def _run_external(self, skill, input_text):
        if not _file_supported(skill, input_text):
            if not self.visible:
                self._show()
            self._show_result("File type not supported by this action.")
            return
        if bool(skill.get("background", False)):
            self._run_background(skill, input_text)
            return
        # if not self.visible:
        #     self._show()
        # self.list_frame.pack_forget()
        # self.skill_hint.pack_forget()
        # self.entry.config(state="disabled")
        # self._start_anim(skill["title"])
        start_msg = "Started. You'll get a notification when it's done."
        bridge.notify(skill["title"], start_msg)
        if self.window:
            self._hide()
        self.processing = True
        _t0 = time.time()
        _src = source_detect.get_source_info(getattr(self, '_source_hwnd', None))
        _price = _skill_price(skill, input_text)

        def execute():
            try:
                if not _reserve_skill(skill, _price):
                    self.processing = False
                    self.root.after(0, self._stop_anim)
                    self.root.after(0, lambda: self._show_result("Not enough slippers. Top up your balance to run this skill."))
                    return
                print(f"[Scryptian] Running (external): {skill['title']}...")
                result = core.run_skill(skill, input_text)
                print(f"[Scryptian] Done (external): {skill['title']}")
                self.processing = False
                if result and not result.startswith("[Scryptian Error]"):
                    self.last_skill_title = skill["title"]
                    # self.root.after(0, lambda r=result: self._present_result(r))
                    telemetry.send("skill_run", _build_skill_event(skill, input_text, time.time() - _t0, **_src, via="selection"))
                    _settle_skill(skill, _price)
                    out_path = None
                    if isinstance(result, str) and result.startswith("[Scryptian File] "):
                        out_path = result[len("[Scryptian File] "):].strip()
                    if out_path:
                        bridge.notify(
                            skill["title"],
                            f"Saved to {os.path.basename(os.path.dirname(out_path))}",
                            action={
                                "label": "Open",
                                "hotkey": "alt+q",
                                "callback": lambda p=out_path: tray.open_in_explorer(p),
                            },
                        )
                    else:
                        bridge.notify(skill["title"], "Done.")
                else:
                    telemetry.send("skill_failed", {"name": skill["title"], "via": "selection", "reason": "error_or_empty", "error": (result or "")[:200]})
                    # self.root.after(0, lambda t=result: self._present_result(t or "Skill returned an empty result."))
                    bridge.notify(skill["title"], "Something went wrong. Please try again.")
                    _refund_skill(skill, _price)
            except Exception as e:
                telemetry.send("skill_failed", {"name": skill["title"], "via": "selection", "reason": "exception", "error": str(e)[:200]})
                # self.root.after(0, lambda msg=str(e): self._present_result(f"Error: {msg}"))
                bridge.notify(skill["title"], "Something went wrong. Please try again.")
                _refund_skill(skill, _price)

        threading.Thread(target=execute, daemon=True).start()

    def _present_result(self, text):
        """Open the bar only to show a finished result, not the running state."""
        if not self.window or not self.visible:
            self.pending_result = None
            self._show()
        self.last_result = text
        self.has_result = True
        self._show_result(text)

    def _show_result(self, text):
        """Shows result below the bar, dynamically expanding the window."""
        if not self.window:
            return

        # Stop animation if this is a real result (not an animation frame)
        if self._anim_skill and not text.startswith(self._anim_skill):
            self._stop_anim()

        # Unpack everything before repacking
        self.list_frame.pack_forget()
        self.skill_hint.pack_forget()
        self.entry_border.pack_forget()
        self.separator.pack_forget()
        self.result_box.pack_forget()
        self.hint_label.pack_forget()
        self.chain_frame.pack_forget()

        # Update text
        self.result_box.config(state="normal")
        self.result_box.delete("1.0", tk.END)
        self.result_box.insert("1.0", text)
        self.result_box.config(state="disabled")

        # Height estimate based on dynamic bar width
        chars_per_line = max(40, self._bar_width // 12)
        visual_lines = 0
        for line in text.split("\n"):
            visual_lines += max(1, (len(line) // chars_per_line) + 1)

        max_lines = 25
        clamped = min(visual_lines, max_lines)
        clamped = max(clamped, 2)

        # Pack in correct order: separator → result → hint
        self.separator.pack(fill="x", padx=8, pady=(4, 0))
        self.result_box.config(height=clamped)
        self.result_box.pack(fill="x", padx=10, pady=(4, 4))

        if self.has_result:
            self.hint_label.pack(fill="x", padx=12, pady=(0, 6))
            # self._show_chain()

        self.window.update_idletasks()
        needed = self.container.winfo_reqheight()
        self._resize(needed + 4)

    def _start_anim(self, skill_title):
        """Start processing animation: Skill  |  •  →  ••  →  •••"""
        self._stop_anim()
        self._anim_skill = skill_title
        self._anim_frame = 0
        self._tick_anim()

    def _tick_anim(self):
        """Advance one frame of the processing animation."""
        if not self._anim_skill:
            return
        dots = "•" * (self._anim_frame + 1)
        self._show_result(f"{self._anim_skill} {dots}")
        self._anim_frame = (self._anim_frame + 1) % 3
        self._anim_job = self.root.after(200, self._tick_anim)

    def _stop_anim(self):
        """Stop processing animation."""
        if self._anim_job:
            self.root.after_cancel(self._anim_job)
            self._anim_job = None
        self._anim_skill = ""

    def _show_chain(self):
        """Show quick-action chain buttons below the result."""
        self.chain_frame.pack_forget()
        for b in self._chain_btns:
            b.destroy()
        self._chain_btns.clear()

        self.chain_frame.columnconfigure(0, weight=1, uniform="chain")
        self.chain_frame.columnconfigure(1, weight=1, uniform="chain")
        self.chain_frame.columnconfigure(2, weight=1, uniform="chain")

        chains = [
            ("Summarize", "Summarize", "Ctrl+1"),
            ("Change tone to professional", "Change Tone to Professional", "Ctrl+2"),
            ("Fact Check", "Fact Check", "Ctrl+3"),
        ]
        for i, (skill_title, label, hotkey) in enumerate(chains):
            btn = tk.Label(
                self.chain_frame,
                text=f"{label}\n[{hotkey}]",
                font=("Segoe UI Variable", 12),
                bg="#2B2B2B",
                fg="#FFFFFF",
                cursor="hand2",
                padx=6,
                pady=5,
                justify="center",
            )
            btn.grid(row=0, column=i, sticky="ew", padx=(0, 4) if i < 2 else (0, 0))
            btn.bind("<Button-1>", lambda e, t=skill_title: self._run_chain(t))
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#3C3C3C", fg="#FFFFFF"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg="#2B2B2B", fg="#FFFFFF"))
            self._chain_btns.append(btn)

        self.chain_frame.pack(fill="x", padx=10, pady=(0, 6))
        self.window.update_idletasks()
        needed = self.container.winfo_reqheight()
        self._resize(needed + 4)

    def _hide_chain(self):
        """Hide chain buttons (e.g. when starting a new skill)."""
        self.chain_frame.pack_forget()
        for b in self._chain_btns:
            b.destroy()
        self._chain_btns.clear()

    def _on_hotkey(self, n):
        """Dispatch Ctrl+0..3: chain actions when result shown, special actions in menu."""
        if self.has_result:
            chain_map = {
                1: "Summarize",
                2: "Change tone to professional",
                3: "Fact Check",
            }
            if n in chain_map:
                self._run_chain(chain_map[n])
            return
        if self.in_store or self.in_currency:
            return
        special_map = {
            0: self._open_currency,
            1: self._open_wish_box,
            2: self._open_problem,
            3: self._open_store,
        }
        if n in special_map:
            special_map[n]()

    def _run_chain(self, skill_title):
        """Run a chain skill on the current result text."""
        text = self.last_result
        if not text:
            return

        skill = next((s for s in self.skills if s["title"] == skill_title), None)
        if not skill:
            return

        from_skill = getattr(self, "last_skill_title", "unknown")

        self._hide_chain()
        self.processing = True
        self.entry.config(state="disabled")

        self._start_anim(skill_title)

        telemetry.send("chain_started", {
            "from_skill": from_skill,
            "chain_skill": skill_title,
            "input_len": len(text),
        })

        _t0 = time.time()

        def execute():
            try:
                stripped = core.run_skill(skill, text).strip()
                elapsed = round(time.time() - _t0, 2)
                if stripped.startswith("[Scryptian Error]"):
                    telemetry.send("chain_failed", {
                        "from_skill": from_skill,
                        "chain_skill": skill_title,
                        "error": stripped[:200],
                        "elapsed": elapsed,
                    })
                    self.root.after(0, lambda r=stripped: self._finish_chain(r))
                elif stripped:
                    telemetry.send("chain_completed", {
                        "from_skill": from_skill,
                        "chain_skill": skill_title,
                        "elapsed": elapsed,
                        "output_len": len(stripped),
                    })
                    self.last_result = stripped
                    self.root.after(0, lambda r=stripped: self._finish_chain(r))
                else:
                    telemetry.send("chain_failed", {
                        "from_skill": from_skill,
                        "chain_skill": skill_title,
                        "error": "empty_result",
                        "elapsed": elapsed,
                    })
                    self.root.after(0, lambda: self._finish_chain(text))
            except Exception as e:
                telemetry.send("chain_failed", {
                    "from_skill": from_skill,
                    "chain_skill": skill_title,
                    "error": str(e)[:200],
                })
                self.root.after(0, lambda msg=str(e): self._finish_chain(f"Error: {msg}"))

        threading.Thread(target=execute, daemon=True).start()

    def _finish_chain(self, result):
        """Called on main thread when chain skill completes."""
        self._stop_anim()
        self.processing = False
        self.has_result = True
        self._show_result(result)


    def _fade_dialog(self, dlg, alpha):
        alpha = min(alpha + 0.1, 1.0)
        try:
            dlg.attributes("-alpha", alpha)
        except Exception:
            return
        if alpha < 1.0:
            self.root.after(16, lambda: self._fade_dialog(dlg, alpha))

    def _open_wish_box(self):
        """Dialog where users request services they'd like to see on Scryptian."""
        dlg = tk.Toplevel(self.root)
        dlg.overrideredirect(True)
        dlg.attributes("-topmost", True)
        dlg.attributes("-toolwindow", True)
        dlg.configure(bg="#202020")
        _round_window_corners(dlg)

        outer = tk.Frame(dlg, bg="#3C3C3C", padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        inner = tk.Frame(outer, bg="#202020", padx=16, pady=14)
        inner.pack(fill="both", expand=True)

        tk.Label(inner, text="Wish Service Box", font=("Segoe UI Variable", 12, "bold"),
                 bg="#202020", fg="#FFFFFF", anchor="w").pack(fill="x", pady=(0, 4))

        tk.Label(inner, text="Which service would you like to see on Scryptian? (plz be much more specific)",
                 font=("Segoe UI Variable", 12), bg="#202020", fg="#C5C5C5",
                 anchor="w", wraplength=360, justify="left").pack(fill="x", pady=(0, 10))

        # Message input (boxed so it reads as a text field)
        msg_shell = tk.Frame(inner, bg="#2B2B2B", padx=6, pady=4)
        msg_shell.pack(fill="x", pady=(0, 6))
        msg_text = tk.Text(msg_shell, font=("Segoe UI Variable", 12), bg="#2B2B2B", fg="#9A9A9A",
                           insertbackground="#FFFFFF", relief="flat", bd=0,
                           height=4, wrap="word")
        msg_text.pack(fill="x")
        MSG_PLACEHOLDER = "Describe the service you'd like..."
        msg_text.insert("1.0", MSG_PLACEHOLDER)

        MAX_LEN = 200
        counter = tk.Label(inner, text=f"0 / {MAX_LEN}", font=("Segoe UI Variable", 11),
                           bg="#202020", fg="#9A9A9A", anchor="e")
        counter.pack(fill="x", pady=(0, 12))

        def _on_msg_focus_in(e):
            if msg_text.get("1.0", "end-1c") == MSG_PLACEHOLDER:
                msg_text.delete("1.0", "end")
                msg_text.config(fg="#FFFFFF")

        def _on_msg_focus_out(e):
            if not msg_text.get("1.0", "end-1c").strip():
                msg_text.insert("1.0", MSG_PLACEHOLDER)
                msg_text.config(fg="#9A9A9A")
            _update_counter()

        def _update_counter(e=None):
            text = msg_text.get("1.0", "end-1c")
            if text == MSG_PLACEHOLDER:
                text = ""
            if len(text) > MAX_LEN:
                text = text[:MAX_LEN]
                msg_text.delete("1.0", "end")
                msg_text.insert("1.0", text)
            counter.config(text=f"{len(text)} / {MAX_LEN}")

        msg_text.bind("<FocusIn>", _on_msg_focus_in)
        msg_text.bind("<FocusOut>", _on_msg_focus_out)
        msg_text.bind("<KeyRelease>", _update_counter)

        btn_row = tk.Frame(inner, bg="#202020")
        btn_row.pack(fill="x")

        cancel_btn = tk.Label(btn_row, text="Cancel", font=("Segoe UI Variable", 12),
                              bg="#202020", fg="#C5C5C5", cursor="hand2")
        cancel_btn.pack(side="right", padx=(8, 0))
        cancel_btn.bind("<Button-1>", lambda e: dlg.destroy())
        cancel_btn.bind("<Enter>", lambda e: cancel_btn.config(fg="#FFFFFF"))
        cancel_btn.bind("<Leave>", lambda e: cancel_btn.config(fg="#C5C5C5"))

        def _submit():
            msg = msg_text.get("1.0", "end").strip()
            if msg == MSG_PLACEHOLDER:
                msg = ""
            if not msg:
                return
            telemetry.send("wish_box", {
                "message": msg[:MAX_LEN],
                "skills_count": len(self.skills),
            })
            dlg.destroy()
            self._show_result("Thanks! Your wish has been noted.")

        send_btn = tk.Label(btn_row, text="Send", font=("Segoe UI Variable", 12, "bold"),
                            bg="#60CDFF", fg="#FFFFFF", cursor="hand2",
                            padx=14, pady=3)
        send_btn.pack(side="right")
        send_btn.bind("<Button-1>", lambda e: _submit())
        send_btn.bind("<Enter>", lambda e: send_btn.config(bg="#60CDFF"))
        send_btn.bind("<Leave>", lambda e: send_btn.config(bg="#60CDFF"))

        dlg.update_idletasks()
        w, h = dlg.winfo_reqwidth(), dlg.winfo_reqheight()
        if self.window:
            bx = self.window.winfo_x() + (self.window.winfo_width() - w) // 2
            by = self.window.winfo_y() + (self.window.winfo_height() - h) // 2
        else:
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            bx, by = (sw - w) // 2, (sh - h) // 2
        dlg.geometry(f"{w}x{h}+{bx}+{by}")
        dlg.attributes("-alpha", 0.0)
        self._fade_dialog(dlg, 0.0)
        msg_text.focus_set()

    def _open_problem(self):
        """Dialog where users report a problem and leave contact info."""
        dlg = tk.Toplevel(self.root)
        dlg.overrideredirect(True)
        dlg.attributes("-topmost", True)
        dlg.attributes("-toolwindow", True)
        dlg.configure(bg="#202020")
        _round_window_corners(dlg)

        outer = tk.Frame(dlg, bg="#3C3C3C", padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        inner = tk.Frame(outer, bg="#202020", padx=16, pady=14)
        inner.pack(fill="both", expand=True)

        tk.Label(inner, text="I have a problem", font=("Segoe UI Variable", 12, "bold"),
                 bg="#202020", fg="#FFFFFF", anchor="w").pack(fill="x", pady=(0, 10))

        # Message input (boxed so it reads as a text field)
        msg_shell = tk.Frame(inner, bg="#2B2B2B", padx=6, pady=4)
        msg_shell.pack(fill="x", pady=(0, 10))
        msg_text = tk.Text(msg_shell, font=("Segoe UI Variable", 12), bg="#2B2B2B", fg="#9A9A9A",
                           insertbackground="#FFFFFF", relief="flat", bd=0,
                           height=4, wrap="word")
        msg_text.pack(fill="x")
        MSG_PLACEHOLDER = "Describe what went wrong..."
        msg_text.insert("1.0", MSG_PLACEHOLDER)

        def _on_msg_focus_in(e):
            if msg_text.get("1.0", "end-1c") == MSG_PLACEHOLDER:
                msg_text.delete("1.0", "end")
                msg_text.config(fg="#FFFFFF")

        def _on_msg_focus_out(e):
            if not msg_text.get("1.0", "end-1c").strip():
                msg_text.insert("1.0", MSG_PLACEHOLDER)
                msg_text.config(fg="#9A9A9A")

        msg_text.bind("<FocusIn>", _on_msg_focus_in)
        msg_text.bind("<FocusOut>", _on_msg_focus_out)

        tk.Label(inner, text="How can I reach you?  (email / Discord / other)", font=("Segoe UI Variable", 12),
                 bg="#202020", fg="#C5C5C5", anchor="w").pack(fill="x", pady=(0, 4))

        # Contact input (boxed)
        contact_shell = tk.Frame(inner, bg="#2B2B2B", padx=6, pady=4)
        contact_shell.pack(fill="x", pady=(0, 12))
        CONTACT_PLACEHOLDER = "your email or Discord"
        contact_var = tk.StringVar(value=CONTACT_PLACEHOLDER)
        contact_entry = tk.Entry(contact_shell, textvariable=contact_var,
                                 font=("Segoe UI Variable", 12), bg="#2B2B2B", fg="#9A9A9A",
                                 insertbackground="#FFFFFF", relief="flat", bd=0)
        contact_entry.pack(fill="x", ipady=3)

        def _on_contact_focus_in(e):
            if contact_var.get() == CONTACT_PLACEHOLDER:
                contact_var.set("")
                contact_entry.config(fg="#FFFFFF")

        def _on_contact_focus_out(e):
            if not contact_var.get().strip():
                contact_var.set(CONTACT_PLACEHOLDER)
                contact_entry.config(fg="#9A9A9A")

        contact_entry.bind("<FocusIn>", _on_contact_focus_in)
        contact_entry.bind("<FocusOut>", _on_contact_focus_out)

        btn_row = tk.Frame(inner, bg="#202020")
        btn_row.pack(fill="x")

        cancel_btn = tk.Label(btn_row, text="Cancel", font=("Segoe UI Variable", 12),
                              bg="#202020", fg="#C5C5C5", cursor="hand2")
        cancel_btn.pack(side="right", padx=(8, 0))
        cancel_btn.bind("<Button-1>", lambda e: dlg.destroy())
        cancel_btn.bind("<Enter>", lambda e: cancel_btn.config(fg="#FFFFFF"))
        cancel_btn.bind("<Leave>", lambda e: cancel_btn.config(fg="#C5C5C5"))

        def _submit():
            msg = msg_text.get("1.0", "end").strip()
            if msg == MSG_PLACEHOLDER:
                msg = ""
            contact = contact_var.get().strip()
            if contact == CONTACT_PLACEHOLDER:
                contact = ""
            if not msg:
                return
            telemetry.send("i_have_a_problem", {
                "message": msg[:1000],
                "contact": contact[:200],
                "skills_count": len(self.skills),
            })
            dlg.destroy()
            self._show_result("Thanks! I'll get back to you.")

        send_btn = tk.Label(btn_row, text="Send", font=("Segoe UI Variable", 12, "bold"),
                            bg="#60CDFF", fg="#FFFFFF", cursor="hand2",
                            padx=14, pady=3)
        send_btn.pack(side="right")
        send_btn.bind("<Button-1>", lambda e: _submit())
        send_btn.bind("<Enter>", lambda e: send_btn.config(bg="#60CDFF"))
        send_btn.bind("<Leave>", lambda e: send_btn.config(bg="#60CDFF"))

        dlg.update_idletasks()
        w, h = dlg.winfo_reqwidth(), dlg.winfo_reqheight()
        if self.window:
            bx = self.window.winfo_x() + (self.window.winfo_width() - w) // 2
            by = self.window.winfo_y() + (self.window.winfo_height() - h) // 2
        else:
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            bx, by = (sw - w) // 2, (sh - h) // 2
        dlg.geometry(f"{w}x{h}+{bx}+{by}")
        dlg.attributes("-alpha", 0.0)
        self._fade_dialog(dlg, 0.0)
        msg_text.focus_set()

    def _open_skills_folder(self):
        """Open skills folder in file manager."""
        os.startfile(SKILLS_DIR)

    def _open_store(self):
        self.store_panel.open()

    def _close_store(self):
        self.store_panel.close()

    def _open_currency(self):
        self.currency_panel.open()

    def _close_currency(self):
        self.currency_panel.close()


class SelectionToolbar:
    """Small floating toolbar that appears near cursor after text selection."""

    def __init__(self, root, skills, bar=None):
        self.root = root
        self.skills = skills
        self.bar = bar
        self.window = None
        self._overlay = None
        self._source_hwnd = None
        self._input_text = None
        self._dismiss_job = None
        self._watch_active = False
        self._watch_rect = (0, 0, 0, 0)
        self._mini_rows = []
        self._mini_selected_index = 0
        self._visible_skills = []

    def show(self, file_path, x, y, source_hwnd):
        self._input_text = file_path
        self._source_hwnd = source_hwnd
        self.skills = core.scan_skills()  # Hot-reload
        self._show_window(x, y)

    def _show_window(self, x, y):
        self._cancel_dismiss()
        self._destroy_window()

        file_path = self._input_text or ""
        is_url = file_path.lower().startswith(("http://", "https://"))
        name = file_path if is_url else os.path.basename(file_path)
        if len(name) > 16:
            if is_url:
                name = name[:13] + "..."
            else:
                ext = os.path.splitext(name)[1]
                head = 16 - len(ext) - 3
                name = name[:max(head, 4)] + "..." + ext

        # Skills to show: URL skills for links, else skills matching the file type.
        if is_url:
            visible = [s for s in self.skills if "link" in (s.get("input_type") or [])]
        else:
            _ext = os.path.splitext(file_path)[1].lower() if file_path else ""
            visible = [s for s in self.skills if _ext and _ext in (s.get("input_type") or [])]
            # Pinned / default Transcribe Audio (commented out — show matching type instead).
            # pinned = pins_module.get_pinned_skills(self.skills)
            # if pinned:
            #     visible = pinned
            # else:
            #     visible = []
            #     for s in self.skills:
            #         if s.get("title") == "Transcribe Audio":
            #             visible = [s]
            #             break
            #     if not visible:
            #         for s in self.skills:
            #             m = s.get("module")
            #             if m and callable(getattr(m, "measure", None)):
            #                 visible = [s]
            #                 break

        # Limit the mini bar to four skills max.
        visible = visible[:4]

        # Metadata from the skill matching this file type.
        dur, unit = _measure_file(self.skills, file_path)
        dur_text = _format_measure(dur, unit) if dur is not None else ""

        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-toolwindow", True)
        win.configure(bg="#3C3C3C")
        win.attributes("-topmost", True)
        _round_window_corners(win)

        # 1px border + container, matching the main bar
        outer = tk.Frame(win, bg="#3C3C3C", padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        inner = tk.Frame(outer, bg="#202020")
        inner.pack(fill="both", expand=True)

        # File info header
        header = tk.Frame(inner, bg="#202020")
        header.pack(fill="x", padx=12, pady=(8, 6))
        tk.Label(header, text=name, bg="#202020", fg="#FFFFFF",
                 font=("Segoe UI Variable", 12, "bold"), anchor="w").pack(side="left", fill="x", expand=True)
        if dur_text:
            tk.Label(header, text=_truncate(dur_text, 14), bg="#202020", fg="#9A9A9A",
                     font=("Segoe UI Variable", 12), anchor="e").pack(side="right")

        # Skill rows
        self._visible_skills = visible
        self._mini_rows = []
        self._mini_selected_index = 0
        if visible:
            tk.Frame(inner, bg="#3C3C3C", height=1).pack(fill="x", padx=8, pady=(0, 2))
            for idx, skill in enumerate(visible):
                _ext = os.path.splitext(file_path)[1].lower() if file_path else ""
                _types = skill.get("input_type") or []
                _unsupported = bool(file_path) and bool(_types) and _ext not in _types

                row = tk.Frame(inner, bg="#202020", cursor="hand2")
                row.pack(fill="x", padx=0, pady=0)

                try:
                    _price = _skill_price(skill, file_path)
                except Exception:
                    _price = 0

                icon_lbl = None
                price_lbl = None

                if _unsupported:
                    price_lbl = tk.Label(row, text="not supported", bg="#202020", fg="#9A9A9A",
                                         font=("Segoe UI Variable", 12), anchor="e", cursor="hand2")
                    price_lbl.pack(side="right", padx=(0, 8), pady=4)
                elif _price > 0:
                    right = tk.Frame(row, bg="#202020")
                    right.pack(side="right", padx=(0, 8))
                    icon_photo = self._mini_slippers_icon(16)
                    if icon_photo is not None:
                        icon_lbl = tk.Label(right, image=icon_photo, bg="#202020", cursor="hand2")
                    else:
                        icon_lbl = tk.Label(right, text="🩴", font=("Segoe UI Emoji", 12),
                                            bg="#202020", fg="#60CDFF", cursor="hand2")
                    icon_lbl.pack(side="left", padx=(0, 4))
                    price_lbl = tk.Label(right, text=_format_price(_price), bg="#202020", fg="#60CDFF",
                                         font=("Segoe UI Variable", 12), anchor="e", cursor="hand2")
                    price_lbl.pack(side="left")
                # else: free skill — show nothing on the right

                # Title wraps instead of truncating; packed last so it fills the rest.
                lbl = tk.Label(row, text=skill["title"], bg="#202020", fg="#FFFFFF",
                               font=("Segoe UI Variable", 12), anchor="w", cursor="hand2",
                               padx=12, pady=4, wraplength=200, justify="left")
                lbl.pack(side="left", fill="x", expand=True)

                self._mini_rows.append(row)
                widgets = [row, lbl] + ([price_lbl] if price_lbl else []) + ([icon_lbl] if icon_lbl else [])
                for w in widgets:
                    w.bind("<Button-1>", lambda e, s=skill: self._run_skill(s))
                    w.bind("<Enter>", lambda e, i=idx: self._mini_select(i))

                # Subtle divider between rows (so wrapped titles stay scannable)
                if idx < len(visible) - 1:
                    tk.Frame(inner, bg="#2E2E2E", height=1).pack(fill="x", padx=12)
            self._highlight_mini_row()

        tk.Frame(inner, bg="#3C3C3C", height=1).pack(fill="x", padx=8, pady=(2, 0))

        # Footer: ghost "Open full bar" action (secondary, not a heavy block)
        footer = tk.Frame(inner, bg="#202020", cursor="hand2")
        footer.pack(fill="x", padx=0, pady=(0, 2))
        footer_lbl = tk.Label(footer, text="Open full bar", font=("Segoe UI Variable", 12),
                              bg="#202020", fg="#C5C5C5", anchor="w", cursor="hand2",
                              padx=12, pady=4)
        footer_lbl.pack(side="left")
        footer_arrow = tk.Label(footer, text="→", font=("Segoe UI Variable", 12),
                                bg="#202020", fg="#C5C5C5", anchor="e", cursor="hand2",
                                padx=12, pady=4)
        footer_arrow.pack(side="right")
        for w in (footer, footer_lbl, footer_arrow):
            w.bind("<Button-1>", lambda e: self._open_full_bar())
        footer.bind("<Enter>", lambda e: self._footer_hover(footer, True))
        footer.bind("<Leave>", lambda e: self._footer_hover(footer, False))

        win.bind("<Up>", self._select_mini_prev)
        win.bind("<Down>", self._select_mini_next)
        win.bind("<Return>", self._run_mini_selected)
        win.bind("<Escape>", lambda e: self._dismiss())

        win.update_idletasks()
        w = 320  # fixed width (Win11 compact card)
        h = win.winfo_reqheight()
        screen_w = self.root.winfo_screenwidth()

        px = min(x + 10, screen_w - w - 10)
        py = y - h - 12
        if py < 0:
            py = y + 20

        self._mini_px = px
        self._mini_py = py
        win.geometry(f"{w}x{h}+{px}+{py + 6}")
        win.attributes("-topmost", True)
        _round_window_corners(win)  # re-apply after geometry for reliable rounding
        win.attributes("-alpha", 0.0)
        self.window = win
        self._force_focus_mini()
        self._fade_in(win)
        self.root.after(400, self._start_click_watcher)
        self._start_focus_watcher()

    def _run_skill(self, skill):
        text = self._input_text
        source_hwnd = self._source_hwnd
        self._dismiss()

        if self.bar:
            self.bar.run_externally(skill, text, source_hwnd)

    def _open_full_bar(self):
        src = self._source_hwnd
        self._dismiss()
        if self.bar:
            self.bar.open_bar(src)

    def _mini_select(self, idx):
        self._mini_selected_index = idx
        self._highlight_mini_row()

    def _highlight_mini_row(self):
        for i, row in enumerate(self._mini_rows):
            self._mini_set_bg(row, "#2E2E2E" if i == self._mini_selected_index else "#202020")

    def _mini_set_bg(self, widget, bg):
        """Set bg on a widget and all its descendants."""
        try:
            widget.config(bg=bg)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._mini_set_bg(child, bg)

    def _mini_slippers_icon(self, size=14):
        """Return a cached blue slippers icon (matching the main bar), or None."""
        key = ("slippers.png", size, "#60CDFF")
        cache = getattr(self, "_icon_cache", None)
        if cache is None:
            cache = {}
            self._icon_cache = cache
        if key in cache:
            return cache[key]
        try:
            if getattr(sys, "frozen", False):
                assets_dir = os.path.join(sys._MEIPASS, "docs", "assets")
            else:
                assets_dir = os.path.join(BASE_DIR, "docs", "assets")
            icon_path = os.path.join(assets_dir, "slippers.png")
            source = Image.open(icon_path).convert("RGBA")
            alpha = source.getchannel("A").resize((size, size), Image.Resampling.LANCZOS)
            icon = Image.new("RGBA", (size, size), "#60CDFF")
            icon.putalpha(alpha)
            photo = ImageTk.PhotoImage(icon)
            cache[key] = photo
            return photo
        except Exception:
            return None

    def _footer_hover(self, footer, entering):
        """Hover state for the 'Open full bar' ghost footer."""
        bg = "#2E2E2E" if entering else "#202020"
        fg = "#FFFFFF" if entering else "#C5C5C5"
        try:
            footer.config(bg=bg)
        except Exception:
            pass
        for child in footer.winfo_children():
            try:
                child.config(bg=bg, fg=fg)
            except Exception:
                pass

    def _select_mini_next(self, event=None):
        if self._mini_rows:
            self._mini_selected_index = min(self._mini_selected_index + 1, len(self._mini_rows) - 1)
            self._highlight_mini_row()

    def _select_mini_prev(self, event=None):
        if self._mini_rows:
            self._mini_selected_index = max(self._mini_selected_index - 1, 0)
            self._highlight_mini_row()

    def _run_mini_selected(self, event=None):
        if self._visible_skills and 0 <= self._mini_selected_index < len(self._visible_skills):
            self._run_skill(self._visible_skills[self._mini_selected_index])

    def _force_focus_mini(self, attempt=0):
        if not self.window:
            return
        try:
            hwnd = int(self.window.wm_frame(), 16)
            fg = ctypes.windll.user32.GetForegroundWindow()
            tid_fg = ctypes.windll.user32.GetWindowThreadProcessId(fg, None)
            tid_self = ctypes.windll.kernel32.GetCurrentThreadId()
            ctypes.windll.user32.AttachThreadInput(tid_fg, tid_self, True)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.BringWindowToTop(hwnd)
            ctypes.windll.user32.AttachThreadInput(tid_fg, tid_self, False)
        except Exception:
            pass
        try:
            self.window.focus_force()
        except Exception:
            pass
        if attempt < 3:
            self.root.after(80, lambda: self._force_focus_mini(attempt + 1))

    def _fade_in(self, win, step=0):
        if not self.window or self.window is not win:
            return
        total = 10
        p = _ease_out_cubic(step / total)
        try:
            win.attributes("-alpha", p)
            ty = getattr(self, "_mini_py", None)
            tx = getattr(self, "_mini_px", None)
            if ty is not None and tx is not None:
                ny = ty + int(6 * (1 - p))
                win.geometry(f"+{tx}+{ny}")
        except Exception:
            return
        if step < total:
            self.root.after(16, lambda: self._fade_in(win, step + 1))

    def _fade_out(self, win, alpha):
        if not win:
            return
        alpha = max(alpha - 0.1, 0.0)
        try:
            win.attributes("-alpha", alpha)
        except Exception:
            return
        if alpha > 0.0:
            self.root.after(16, lambda: self._fade_out(win, alpha))
        else:
            try:
                win.destroy()
            except Exception:
                pass

    def _start_click_watcher(self):
        """Install WH_MOUSE_LL in a dedicated thread with its own message loop."""
        if not self.window:
            return
        # Cache rect on main thread
        self._watch_rect = (
            self.window.winfo_x(),
            self.window.winfo_y(),
            self.window.winfo_width(),
            self.window.winfo_height(),
        )
        self._watch_active = True

        def _run_hook():
            import ctypes
            import ctypes.wintypes

            WH_MOUSE_LL = 14
            WM_LBUTTONDOWN = 0x0201
            WM_RBUTTONDOWN = 0x0204

            HOOKPROC = ctypes.WINFUNCTYPE(
                ctypes.c_long, ctypes.c_int, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)
            )

            def low_level_mouse_proc(nCode, wParam, lParam):
                if nCode >= 0 and self._watch_active and wParam in (WM_LBUTTONDOWN, WM_RBUTTONDOWN):
                    try:
                        mx = ctypes.cast(lParam, ctypes.POINTER(ctypes.wintypes.POINT)).contents.x
                        my = ctypes.cast(lParam, ctypes.POINTER(ctypes.wintypes.POINT)).contents.y
                        wx, wy, ww, wh = self._watch_rect
                        if not (wx <= mx <= wx + ww and wy <= my <= wy + wh):
                            self._watch_active = False
                            self.root.after(0, self._dismiss)
                    except Exception:
                        pass
                return ctypes.windll.user32.CallNextHookEx(
                    ctypes.c_void_p(0), nCode, wParam, lParam
                )

            cb = HOOKPROC(low_level_mouse_proc)
            hook = ctypes.windll.user32.SetWindowsHookExW(WH_MOUSE_LL, cb, None, 0)

            msg = ctypes.wintypes.MSG()
            while self._watch_active:
                ret = ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret <= 0:
                    break
                ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

            ctypes.windll.user32.UnhookWindowsHookEx(hook)

        threading.Thread(target=_run_hook, daemon=True).start()

    def _dismiss(self):
        self._watch_active = False
        self._focus_watch_active = False
        self._cancel_dismiss()
        self.root.after(0, self._destroy_window)

    def _start_focus_watcher(self):
        self._focus_watch_active = True
        src = self._source_hwnd
        try:
            win_hwnd = int(self.window.wm_frame(), 16) if self.window else 0
        except Exception:
            win_hwnd = 0
        def _check():
            if not self._focus_watch_active or not self.window:
                return
            try:
                fg = ctypes.windll.user32.GetForegroundWindow()
                if src and fg != src and fg != win_hwnd:
                    self._dismiss()
                    return
            except Exception:
                pass
            self.root.after(300, _check)
        self.root.after(300, _check)

    def _cancel_dismiss(self):
        if self._dismiss_job:
            self.root.after_cancel(self._dismiss_job)
            self._dismiss_job = None

    def _destroy_window(self):
        if self.window:
            win = self.window
            self.window = None
            try:
                current_alpha = win.attributes("-alpha")
            except Exception:
                current_alpha = 1.0
            self._fade_out(win, current_alpha)


def _kill_other_instances():
    """Kill other Scryptian.exe processes, keeping only current instance."""
    import ctypes
    import ctypes.wintypes

    TH32CS_SNAPPROCESS = 0x00000002
    PROCESS_TERMINATE = 0x0001

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.wintypes.DWORD),
            ("cntUsage", ctypes.wintypes.DWORD),
            ("th32ProcessID", ctypes.wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", ctypes.wintypes.DWORD),
            ("cntThreads", ctypes.wintypes.DWORD),
            ("th32ParentProcessID", ctypes.wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("szExeFile", ctypes.c_char * 260),
        ]

    my_pid = os.getpid()
    my_ppid = None

    # Find my parent PID
    snap = ctypes.windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    pe = PROCESSENTRY32()
    pe.dwSize = ctypes.sizeof(PROCESSENTRY32)

    keep_pids = {my_pid}

    if ctypes.windll.kernel32.Process32First(snap, ctypes.byref(pe)):
        while True:
            if pe.th32ProcessID == my_pid:
                my_ppid = pe.th32ParentProcessID
                keep_pids.add(my_ppid)
                break
            if not ctypes.windll.kernel32.Process32Next(snap, ctypes.byref(pe)):
                break

    # Kill all other Scryptian.exe
    pe2 = PROCESSENTRY32()
    pe2.dwSize = ctypes.sizeof(PROCESSENTRY32)
    snap2 = ctypes.windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if ctypes.windll.kernel32.Process32First(snap2, ctypes.byref(pe2)):
        while True:
            name = pe2.szExeFile.decode("utf-8", errors="ignore").lower()
            if "scryptian" in name and pe2.th32ProcessID not in keep_pids:
                handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pe2.th32ProcessID)
                if handle:
                    ctypes.windll.kernel32.TerminateProcess(handle, 0)
                    ctypes.windll.kernel32.CloseHandle(handle)
            if not ctypes.windll.kernel32.Process32Next(snap2, ctypes.byref(pe2)):
                break

    ctypes.windll.kernel32.CloseHandle(snap)
    ctypes.windll.kernel32.CloseHandle(snap2)


def _ensure_installed():
    """Kill duplicate instances. Installer handles placement."""
    _kill_other_instances()
    return True


# ── Entry point ──
def main():
    if not _ensure_installed():
        return
    bootstrap.setup()

    # Register wallet in the background (grants 221 slippers on first run).
    threading.Thread(target=wallet.ensure_wallet, daemon=True).start()

    print("[Scryptian] Scanning skills...")
    skills = core.scan_skills()

    if not skills:
        print("[Scryptian] No skills found in skills/ folder")
        return

    for s in skills:
        print(f"  → {s['title']}: {s['description']}")

    print(f"\n[Scryptian] Skills loaded: {len(skills)}")

    print(f"[Scryptian] Hotkey: {HOTKEY}")
    print("[Scryptian] Waiting...")

    def _sys_info():
        info = {"skills": len(skills)}
        try:
            import subprocess, re
            r = subprocess.run(["wmic", "cpu", "get", "Name,NumberOfCores"], capture_output=True, text=True, timeout=5, creationflags=0x08000000)
            lines = [l.strip() for l in r.stdout.strip().splitlines() if l.strip() and l.strip().lower() != "name  numberofcores"]
            if lines:
                parts = lines[0].rsplit(None, 1)
                if len(parts) == 2:
                    info["cpu_name"] = parts[0].strip()
                    info["cpu_cores"] = int(parts[1])
        except Exception:
            pass
        try:
            import subprocess
            r = subprocess.run(["wmic", "computersystem", "get", "TotalPhysicalMemory"], capture_output=True, text=True, timeout=5, creationflags=0x08000000)
            for line in r.stdout.splitlines():
                line = line.strip()
                if line.isdigit():
                    info["ram_gb"] = round(int(line) / (1024 ** 3), 1)
                    break
        except Exception:
            pass
        try:
            import platform
            info["os_version"] = platform.version()
        except Exception:
            pass
        try:
            import ctypes
            pf = ctypes.windll.kernel32.IsProcessorFeaturePresent
            info["has_avx"]    = bool(pf(17))
            info["has_avx2"]   = bool(pf(40))
            info["has_avx512"] = bool(pf(41))
            info["has_fma"]    = bool(pf(19))
        except Exception:
            pass
        return info

    telemetry.send("app_started", _sys_info())
    telemetry.send_first_launch()

    # Register bundled Manrope fonts before creating any widgets
    _register_manrope()

    # Hidden root tkinter window — keeps mainloop on the main thread
    root = tk.Tk()
    root.withdraw()

    # First-launch runtime downloader (Discord-style centered window).
    import setup_window
    setup_window.show_setup_window(root)

    # Let skills raise branded notifications via bridge.notify()
    bridge.set_root(root)

    toolbar = SelectionToolbar(root, skills)
    bar = ScryptianBar(root, skills, toolbar=toolbar)
    toolbar.bar = bar

    sel_queue = queue.Queue()

    def _on_selection(text, x, y, source_hwnd):
        sel_queue.put((text, x, y, source_hwnd))

    def _poll_selection():
        try:
            while True:
                text, x, y, hwnd = sel_queue.get_nowait()
                toolbar.show(text, x, y, hwnd)
        except queue.Empty:
            pass
        root.after(150, _poll_selection)

    selection_watcher.start(_on_selection)
    root.after(150, _poll_selection)

    def _hotkey_handler():
        bar.toggle()

    keyboard.add_hotkey(HOTKEY, _hotkey_handler)

    def _rehook():
        """Re-register hotkey periodically to survive sleep/hibernate."""
        try:
            keyboard.remove_hotkey(HOTKEY)
        except Exception:
            pass
        keyboard.add_hotkey(HOTKEY, _hotkey_handler)
        root.after(300000, _rehook)  # every 5 minutes

    root.after(300000, _rehook)

    autostart.enable()
    print("[Scryptian] Autostart updated.")

    tray.start(on_quit=root.quit, on_open=bar.toggle)

    # Staged installer waiting to be applied when the user goes idle.
    # "since" marks when it became ready; if the silent apply never happens
    # (e.g. antivirus blocks it), we fall back to a manual-update prompt.
    _pending_update = {"path": None, "version": None, "since": None, "fallback_shown": False}
    _FALLBACK_AFTER = 6 * 60 * 60  # seconds before offering a manual update

    def _show_update_fallback(version):
        """Silent update didn't stick — let the user update manually."""
        if _pending_update["fallback_shown"]:
            return
        _pending_update["fallback_shown"] = True
        telemetry.send("update_fallback_shown", {"version": version})
        try:
            tray.set_update_available(version)
            tray.show_update_popup(version, tray.RELEASES_URL, root)
        except Exception:
            pass

    def _apply_update_when_idle():
        """Swap to the new version silently once the user is idle and not busy."""
        try:
            ready = _pending_update["path"] and os.path.exists(_pending_update["path"])
            busy = getattr(bar, "processing", False) or getattr(bar, "_bg_running", False)
            if ready and not busy and updater.idle_seconds() >= 120:
                telemetry.send("update_applying", {"version": _pending_update["version"]})
                updater.launch_installer(_pending_update["path"])
                root.quit()   # installer will close/replace/relaunch us
                return
            # Silent apply hasn't happened in time (blocked/never idle) → manual.
            since = _pending_update["since"]
            if since and (time.time() - since) >= _FALLBACK_AFTER:
                _show_update_fallback(_pending_update["version"])
        except Exception:
            pass
        root.after(60000, _apply_update_when_idle)

    def _start_auto_update(latest, assets):
        """Download the installer in the background, then poll for an idle moment."""
        def _dl():
            try:
                url = updater.find_setup_url(assets)
                if not url:
                    print("[Scryptian] No installer asset found in release.")
                    root.after(0, lambda: _show_update_fallback(latest))
                    return
                dest = os.path.join(updater.updates_dir(), f"Scryptian_Setup_{latest}.exe")
                if not os.path.exists(dest):
                    updater.download(url, dest)
                _pending_update["path"] = dest
                _pending_update["version"] = latest
                _pending_update["since"] = time.time()
                telemetry.send("update_downloaded", {"version": latest})
                print(f"[Scryptian] Update {latest} downloaded — will apply when idle.")
            except Exception as e:
                telemetry.send("update_download_failed", {"version": latest, "error": str(e)[:200]})
                print(f"[Scryptian] Update download failed: {e}")
                # Download itself failed (often AV) → offer manual update.
                _pending_update["version"] = latest
                root.after(0, lambda: _show_update_fallback(latest))

        threading.Thread(target=_dl, daemon=True).start()
        root.after(60000, _apply_update_when_idle)

    def _check_update():
        try:
            from urllib import request as _req
            import json as _json
            import ssl as _ssl
            from telemetry import APP_VERSION
            try:
                import certifi
                ctx = _ssl.create_default_context(cafile=certifi.where())
            except Exception:
                ctx = _ssl.create_default_context()
            url = "https://api.github.com/repos/adrianium/Scryptian/releases/latest"
            req = _req.Request(url, headers={"User-Agent": "Scryptian"})
            data = _json.loads(_req.urlopen(req, timeout=5, context=ctx).read())
            latest = data.get("tag_name", "").lstrip("v")
            current = APP_VERSION.lstrip("v")
            try:
                newer = latest and _version_ge(latest, current) and not _version_ge(current, latest)
            except Exception as e:
                telemetry.send("update_check", {
                    "current_version": current,
                    "latest_version": latest,
                    "error": f"{type(e).__name__}: {e}",
                })
                return
            telemetry.send("update_check", {"current_version": current, "latest_version": latest})
            if newer:
                telemetry.send("update_available", {"current_version": current, "latest_version": latest})
                if updater.is_frozen():
                    root.after(0, lambda v=latest, a=data.get("assets", []): _start_auto_update(v, a))
                else:
                    tray.set_update_available(latest)
                    root.after(0, lambda v=latest: tray.show_update_popup(v, tray.RELEASES_URL, root))
        except Exception:
            pass

    def _schedule_update_check():
        threading.Thread(target=_check_update, daemon=False).start()
        root.after(5 * 60 * 60 * 1000, _schedule_update_check)

    root.after(15000, _schedule_update_check)

    # Show bar on first launch so user knows it's working
    root.after(500, bar.toggle)

    import signal
    signal.signal(signal.SIGINT, lambda *_: root.quit())

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        print("\n[Scryptian] Stopped.")


if __name__ == "__main__":
    main()
