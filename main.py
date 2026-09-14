# main.py — Scryptian Core
# Skill scanner | Hotkey | UI bar

import os
import sys
import re
import importlib.util
import threading
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import pyperclip
import keyboard
import time
import datetime
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

IS_WINDOWS = sys.platform == "win32"


def _reserve_skill(skill):
    """Reserve the skill's price before running. Returns False (and notifies) if not."""
    price = int(skill.get("price", 0) or 0)
    if price <= 0:
        return True
    if wallet.reserve(price):
        return True
    bal = wallet.cached_balance() or 0
    bridge.notify("Not enough slippers", f"Need {price}, you have {bal}.")
    return False


def _settle_skill(skill):
    """Pay author (70%) + platform (30%) from the reserved amount on success."""
    price = int(skill.get("price", 0) or 0)
    author_id = skill.get("author_id", "") or ""
    if price <= 0 or not author_id:
        return
    skill_id = skill.get("id") or skill.get("filename", "").replace(".py", "")
    wallet.settle(price, author_id, skill_id)


def _refund_skill(skill):
    """Return the reserved amount to the user on failure."""
    price = int(skill.get("price", 0) or 0)
    if price <= 0:
        return
    wallet.refund(price)

if IS_WINDOWS:
    import ctypes


# ── DPI (crisp rendering on Windows) ──
if IS_WINDOWS:
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
    ext = None
    if input_type == "file" and input_text:
        _, ext = os.path.splitext(input_text)
        ext = ext.lower() if ext else None
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
        "input_ext": ext,
        "text_len": len(input_text or ""),
        "word_count": len((input_text or "").split()),
        "elapsed_sec": sec,
        "duration_bucket": bucket,
        "is_first_run": is_first,
        **extra,
    }


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

    def toggle(self):
        """Show/hide the bar (called from any thread)."""
        if IS_WINDOWS and not self.visible:
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

    def _update_balance(self):
        if not hasattr(self, "balance_label"):
            return
        try:
            bal = wallet.cached_balance()
            if bal is None:
                self.balance_label.config(text="Balance: ")
            else:
                self.balance_label.config(text=f"Balance: {bal} slippers")
        except Exception:
            pass

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
        self.window.configure(bg="#2d2d33")

        # ── Size and center position ──
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        bar_width = max(560, int(screen_w * 0.4))
        bar_height = 52
        x = (screen_w - bar_width) // 2
        y = int(screen_h * 0.3)
        self._bar_width = bar_width

        self.window.geometry(f"{bar_width}x{bar_height}+{x}+{y}")
        self.window.attributes("-alpha", 0.0)
        self.window.update_idletasks()

        # ── Border ──
        self.border = tk.Frame(self.window, bg="#2d2d33", padx=1, pady=1)
        self.border.pack(fill="both", expand=True)

        # ── Container ──
        self.container = tk.Frame(self.border, bg="#0e0e10")
        self.container.pack(fill="both", expand=True)

        # ── Balance (right side) ──
        self.balance_frame = tk.Frame(self.container, bg="#0e0e10")
        self.balance_frame.pack(fill="x", padx=12, pady=(4, 0))

        self.balance_content = tk.Frame(self.balance_frame, bg="#0e0e10")
        self.balance_content.pack(side="right")

        self.balance_icon = tk.Label(
            self.balance_content,
            text="🩴",
            font=("Segoe UI Emoji", 13),
            bg="#0e0e10",
            fg="#3b82f6",
            width=2,
            anchor="center",
        )
        self.balance_icon.pack(side="left", padx=(0, 2), pady=(0, 1))
        self.balance_photo = None
        try:
            if getattr(sys, "frozen", False):
                assets_dir = os.path.join(sys._MEIPASS, "docs", "assets")
            else:
                assets_dir = os.path.join(BASE_DIR, "docs", "assets")
            icon_path = os.path.join(assets_dir, "slippers.png")
            source = Image.open(icon_path).convert("RGBA")
            alpha = source.getchannel("A").resize((26, 26), Image.Resampling.LANCZOS)
            icon = Image.new("RGBA", (26, 26), "#3b82f6")
            icon.putalpha(alpha)
            self.balance_photo = ImageTk.PhotoImage(icon)
            self.balance_icon.config(image=self.balance_photo, text="", width=26)
        except Exception:
            pass

        self.balance_label = tk.Label(
            self.balance_content,
            text="",
            font=("Segoe UI", 11),
            bg="#0e0e10",
            fg="#3b82f6",
            anchor="e",
        )
        self.balance_label.pack(side="left")

        self.balance_hotkey = tk.Label(
            self.balance_frame,
            text="[ Ctrl+0 ]",
            font=("Segoe UI", 10),
            bg="#0e0e10",
            fg="#adadb8",
            anchor="e",
        )
        self.balance_hotkey.pack(side="right", padx=(0, 16), pady=(3, 0))
        self._update_balance()
        threading.Thread(target=self._refresh_balance, daemon=True).start()

        # ── Input field ──
        self.entry_shell = tk.Frame(
            self.container,
            bg="#18181b",
            padx=6,
            pady=3,
            highlightthickness=0,
        )
        self.entry_shell.pack(fill="x", padx=12, pady=8)
        self.entry = tk.Entry(
            self.entry_shell,
            font=("Segoe UI", 14),
            bg="#18181b",
            fg="#efeff1",
            disabledbackground="#18181b",
            disabledforeground="#adadb8",
            insertbackground="#71717a",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
        )
        self.entry.pack(fill="x")
        self.placeholder_text = "Works with text from clipboard"
        self._placeholder_active = True
        self.entry.insert(0, self.placeholder_text)
        self.entry.config(fg="#adadb8")

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
        self.list_frame = tk.Frame(self.container, bg="#0e0e10")
        self._skill_rows = []
        self._special_widgets = []

        # Scrollable skill list + fixed special-action bar
        self.list_view = tk.Frame(self.list_frame, bg="#0e0e10")
        self.list_view.pack_propagate(False)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Scryptian.Vertical.TScrollbar",
                        background="#3f3f46", troughcolor="#0e0e10",
                        arrowcolor="#0e0e10", bordercolor="#0e0e10",
                        lightcolor="#3f3f46", darkcolor="#3f3f46",
                        relief="flat")
        style.map("Scryptian.Vertical.TScrollbar",
                  background=[("active", "#2d2d33")])
        self.list_canvas = tk.Canvas(self.list_view, bg="#0e0e10", highlightthickness=0, bd=0)
        self.list_scroll = ttk.Scrollbar(self.list_view, orient="vertical", command=self.list_canvas.yview, style="Scryptian.Vertical.TScrollbar")
        self.list_inner = tk.Frame(self.list_canvas, bg="#0e0e10")
        self.list_canvas.configure(yscrollcommand=self.list_scroll.set)
        self._list_window = self.list_canvas.create_window((0, 0), window=self.list_inner, anchor="nw")
        self.list_inner.bind("<Configure>", lambda e: self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all")))
        self.list_canvas.bind("<Configure>", lambda e: self.list_canvas.itemconfigure(self._list_window, width=e.width))
        self.list_canvas.bind("<Enter>", lambda e: self.list_canvas.bind_all("<MouseWheel>", self._on_list_wheel))
        self.list_canvas.bind("<Leave>", lambda e: self.list_canvas.unbind_all("<MouseWheel>"))
        self.list_canvas.pack(side="left", fill="both", expand=True)
        self.list_scroll.pack(side="right", fill="y")
        self.special_frame = tk.Frame(self.list_frame, bg="#0e0e10")
        self.special_frame.pack(side="bottom", fill="x", padx=4, pady=(0, 2))
        self.list_view.pack(side="top", fill="x")

        # ── Response area (hidden until result) ──
        self.separator = tk.Frame(self.container, bg="#2d2d33", height=1)
        self.result_box = tk.Text(
            self.container,
            font=("Segoe UI", 13),
            bg="#0e0e10",
            fg="#efeff1",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            wrap="word",
            state="disabled",
        )
        self.skill_hint = tk.Frame(self.container, bg="#0e0e10")
        tk.Label(
            self.skill_hint,
            text="Ctrl+Alt - hide",
            font=("Segoe UI", 11),
            bg="#0e0e10",
            fg="#adadb8",
        ).pack(side="left")
        tk.Label(
            self.skill_hint,
            text="Enter - run action",
            font=("Segoe UI", 11),
            bg="#0e0e10",
            fg="#adadb8",
        ).pack(side="right")
        self.hint_label = tk.Frame(self.container, bg="#0e0e10")
        tk.Label(
            self.hint_label,
            text="Enter - copy to clipboard and close",
            font=("Segoe UI", 11),
            bg="#0e0e10",
            fg="#adadb8",
        ).pack(side="left")
        report_btn = tk.Label(
            self.hint_label,
            text="[ Report ]",
            font=("Segoe UI", 11),
            bg="#0e0e10",
            fg="#adadb8",
            cursor="hand2",
        )
        report_btn.pack(side="right")
        report_btn.bind("<Button-1>", lambda e: self._open_report_dialog())
        report_btn.bind("<Enter>", lambda e: report_btn.config(fg="#efeff1"))
        report_btn.bind("<Leave>", lambda e: report_btn.config(fg="#adadb8"))

        # Chain bar — quick actions on result
        self.chain_frame = tk.Frame(self.container, bg="#0e0e10")
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
        self._bar_fade_in(0.0)

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

        if IS_WINDOWS:
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

    def _bar_fade_in(self, alpha):
        if not self.window or not self.visible:
            return
        alpha = min(alpha + 0.1, 1.0)
        try:
            self.window.attributes("-alpha", alpha)
        except Exception:
            return
        if alpha < 1.0:
            self.root.after(16, lambda: self._bar_fade_in(alpha))

    def _hide(self):
        if self.window:
            self.visible = False
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

    def _on_entry_focus_in(self, event):
        self.entry_shell.config(bg="#1f1f23")
        if self._placeholder_active:
            self._restore_placeholder_cursor()
            self.root.after_idle(self._restore_placeholder_cursor)

    def _on_entry_focus_out(self, event):
        self.entry_shell.config(bg="#18181b")
        if not self._placeholder_active and not self.entry.get():
            self.entry.insert(0, self.placeholder_text)
            self._placeholder_active = True
            self.entry.config(fg="#adadb8")

    def _on_entry_keypress(self, event):
        if not self._placeholder_active:
            return
        if event.keysym in ("BackSpace", "Delete"):
            return "break"
        if event.char:
            self.entry.delete(0, "end")
            self._placeholder_active = False
            self.entry.config(fg="#efeff1")

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
        # Clear old rows
        for row in self._skill_rows:
            row.destroy()
        self._skill_rows = []
        for w in self._special_widgets:
            w.destroy()
        self._special_widgets = []

        if not self.filtered:
            self.list_frame.pack_forget()
            self.skill_hint.pack_forget()
            self.window.update_idletasks()
            self._resize(self.container.winfo_reqheight() + 4)
            return

        for i, p in enumerate(self.filtered):
            skill_id = p.get("filename", "").replace(".py", "")
            row = self._make_row(p["title"], p["description"], i, pinnable=True, skill_id=skill_id)
            self._skill_rows.append(row)

        # Compact special-action bar — only when no filter is active
        if self._placeholder_active or not self.entry.get().strip():
            self._render_special_actions()

        self.list_frame.pack(fill="x", padx=6, pady=(0, 2))
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

    def _make_row(self, title, desc, idx, pinnable=False, skill_id=None):
        """Creates a single skill row with title (bright) and description (dim)."""
        row = tk.Frame(self.list_inner, bg="#0e0e10", cursor="hand2")
        row.pack(fill="x", padx=4, pady=1)

        skill_obj = self.filtered[idx] if idx < len(self.filtered) else None

        title_lbl = tk.Label(
            row, text=f"  {title}", font=("Segoe UI", 13),
            bg="#0e0e10", fg="#efeff1", anchor="w",
        )
        title_lbl.pack(side="left")

        # Mode after title (grey, in parentheses)
        if skill_obj:
            mode = str(skill_obj.get("mode", "cloud")).strip().lower()
            mode_text = "Cloud" if mode == "cloud" else "Local"
            mode_lbl = tk.Label(row, text=f"({mode_text})", font=("Segoe UI", 10),
                                bg="#0e0e10", fg="#adadb8")
            mode_lbl.pack(side="left", padx=(2, 0))
            mode_lbl.bind("<Button-1>", lambda e, i=idx: self._click_row(i))

        if pinnable:
            # Main-bar pin (left of star)
            mpinned = main_pins.is_pinned(title)
            pin_lbl = tk.Label(
                row,
                text="\ue718" if mpinned else "\ue77a",
                font=("Segoe MDL2 Assets", 12),
                bg="#0e0e10",
                fg="#60a5fa" if mpinned else "#adadb8",
                cursor="hand2",
                padx=4,
            )
            pin_lbl.pack(side="right")
            pin_lbl.bind("<Button-1>", lambda e, t=title: self._toggle_main_pin(t))

            # Star always rightmost
            pinned = pins_module.is_pinned(title)
            star_lbl = tk.Label(
                row,
                text="\ue735" if pinned else "\ue734",
                font=("Segoe MDL2 Assets", 13),
                bg="#0e0e10",
                fg="#f9e2af" if pinned else "#adadb8",
                cursor="hand2",
                padx=6,
            )
            star_lbl.pack(side="right")
            star_lbl.bind("<Button-1>", lambda e, t=title: self._toggle_pin(t))

            # Edit button for custom skills (left of star)
            if skill_obj and skill_obj.get("filename", "").startswith("custom_"):
                edit_lbl = tk.Label(
                    row, text="\ue70f",
                    font=("Segoe MDL2 Assets", 11),
                    bg="#0e0e10", fg="#60a5fa",
                    cursor="hand2", padx=4,
                )
                edit_lbl.pack(side="right")
                edit_lbl.bind("<Button-1>", lambda e, s=skill_obj: self._open_edit_skill_editor(s))

            # Settings gear for skills that declare a settings schema (left of star)
            if skill_obj and skill_settings.has_settings(skill_obj):
                gear_lbl = tk.Label(
                    row, text="\ue713",
                    font=("Segoe MDL2 Assets", 12),
                    bg="#0e0e10", fg="#adadb8",
                    cursor="hand2", padx=4,
                )
                gear_lbl.pack(side="right")
                gear_lbl.bind("<Button-1>", lambda e, s=skill_obj: self._open_skill_settings(s))

        # Price (right side, only when paid)
        if skill_obj and skill_obj.get("price", 0) > 0:
            icon_photo = self._slippers_icon(26)
            if icon_photo:
                icon_lbl = tk.Label(row, image=icon_photo, bg="#0e0e10")
            else:
                icon_lbl = tk.Label(row, text="🩴", font=("Segoe UI Emoji", 11),
                                    bg="#0e0e10", fg="#3b82f6")
            icon_lbl.pack(side="right", padx=(2, 4))
            icon_lbl.bind("<Button-1>", lambda e, i=idx: self._click_row(i))

            price_lbl = tk.Label(row, text=str(skill_obj.get("price", 0)),
                                 font=("Segoe UI", 11, "bold"),
                                 bg="#0e0e10", fg="#3b82f6")
            price_lbl.pack(side="right", padx=(8, 0))
            price_lbl.bind("<Button-1>", lambda e, i=idx: self._click_row(i))

        # Click handler
        row.bind("<Button-1>", lambda e, i=idx: self._click_row(i))
        title_lbl.bind("<Button-1>", lambda e, i=idx: self._click_row(i))

        return row

    def _tinted_icon(self, filename, size=24, color="#efeff1"):
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
        return self._tinted_icon("slippers.png", size, "#3b82f6")

    def _render_special_actions(self):
        """Render compact special-action buttons below the skill list (chain-bar style)."""
        sep = tk.Frame(self.special_frame, bg="#2d2d33", height=1)
        sep.pack(fill="x", padx=4, pady=(3, 2))
        self._special_widgets.append(sep)

        grid = tk.Frame(self.special_frame, bg="#0e0e10")
        grid.pack(fill="x", padx=4, pady=(0, 0))
        self._special_widgets.append(grid)
        for c in range(3):
            grid.columnconfigure(c, weight=1, uniform="special")

        actions = [
            ("📁", "Open actions folder", "Ctrl+1", self._open_skills_folder, False, None),
            ("💬", "Contact Author (Telegram)", "Ctrl+2", self._open_telegram, False, "support.png"),
            ("📦", "Actions Store", "Ctrl+3", self._open_store, True, None),
        ]
        for i, (icon, label, hotkey, handler, accent, icon_file) in enumerate(actions):
            fg = "#3b82f6" if accent else "#efeff1"
            hover_bg = "#1e3a8a" if accent else "#2d2d33"

            photo = self._tinted_icon(icon_file, 19, "#efeff1") if icon_file else None
            if photo:
                btn = tk.Label(
                    grid, image=photo, text=f"{label}\n[{hotkey}]",
                    compound="top", font=("Segoe UI", 10),
                    bg="#18181b", fg=fg, cursor="hand2",
                    padx=4, pady=4.29, justify="center",
                )
            else:
                btn = tk.Label(
                    grid, text=f"{icon}\n{label}\n[{hotkey}]", font=("Segoe UI", 10),
                    bg="#18181b", fg=fg, cursor="hand2",
                    padx=4, pady=4, justify="center",
                )

            btn.grid(row=0, column=i, sticky="ew", padx=(0, 4) if i < 2 else (0, 0))
            btn.bind("<Button-1>", lambda e, h=handler: h())
            btn.bind("<Enter>", lambda e, b=btn, hb=hover_bg, f=fg: b.config(bg=hb, fg=f))
            btn.bind("<Leave>", lambda e, b=btn, f=fg: b.config(bg="#18181b", fg=f))

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

    def _highlight_row(self):
        """Highlights the selected row."""
        for i, row in enumerate(self._skill_rows):
            if i == self.selected_index:
                row.config(bg="#2d2d33")
                for child in row.winfo_children():
                    child.config(bg="#2d2d33")
            else:
                row.config(bg="#0e0e10")
                for child in row.winfo_children():
                    child.config(bg="#0e0e10")

    def _work_area(self):
        """Return (left, top, right, bottom) of the work area (screen minus taskbar)."""
        if not IS_WINDOWS:
            return None
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

        # Slash commands (e.g. /id-mine)
        query = "" if self._placeholder_active else self.entry.get().strip()
        if query.startswith("/"):
            self._run_command(query)
            return

        if not self.filtered:
            return

        skill = self.filtered[self.selected_index]
        is_bg = bool(skill.get("background", False))

        # Resolve input (files → text → nothing)
        inp = core.get_input()
        input_text = inp["data"] if inp else ""
        if not input_text.strip():
            try:
                input_text = pyperclip.paste()
            except Exception:
                input_text = ""

        # Background skills (long file jobs) don't rely on clipboard text.
        if not input_text.strip() and not is_bg:
            self._show_result("Clipboard is empty. Copy some text first (Ctrl+C), then try again.")
            return

        # ── Background (fire-and-forget) skills: run detached, free the bar ──
        if is_bg:
            if getattr(self, "_bg_running", False):
                self._show_result("A background task is already running.\nPlease wait for it to finish.")
                return
            if not _reserve_skill(skill):
                return
            self._bg_running = True
            print(f"[Scryptian] Running (background): {skill['title']}...")
            _bt0 = time.time()
            _bg_src = source_detect.get_source_info(getattr(self, '_source_hwnd', None))
            def bg_execute():
                try:
                    result = core.run_skill(skill, input_text)
                    if isinstance(result, str) and result.startswith("[Scryptian Error]"):
                        bridge.notify(skill["title"], result.replace("[Scryptian Error]", "").strip() or "Task failed.")
                        telemetry.send("skill_failed", {"name": skill["title"], "reason": "bg_error", "error": result[:200]})
                        _refund_skill(skill)
                    else:
                        telemetry.send("skill_run", _build_skill_event(skill, input_text, time.time() - _bt0, **_bg_src, background=True))
                        _track_skill(skill["filename"].replace(".py", ""))
                        _settle_skill(skill)
                        print(f"[Scryptian] Done (background): {skill['title']}")
                except Exception as e:
                    print(f"[Scryptian] Background skill error: {e}")
                    bridge.notify(skill["title"], f"Task failed: {e}")
                    _refund_skill(skill)
                finally:
                    self._bg_running = False

            threading.Thread(target=bg_execute, daemon=True).start()
            self._show_result(f"'{skill['title']}' started in the background.\nYou'll be notified when it's done.")
            if self.window:
                self.window.after(2500, self._hide)
            return

        # Hide list, show status
        self.list_frame.pack_forget()
        self.skill_hint.pack_forget()
        self.entry.config(state="disabled")
        self._start_anim(skill["title"])

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
                    if self.window and self.visible:
                        self.last_result = result
                        self.last_skill_title = skill["title"]
                        self.has_result = True
                        self.root.after(0, lambda: self._show_result(result))
                    else:
                        self.pending_result = result
                    telemetry.send("skill_run", _build_skill_event(skill, input_text, time.time() - _t0, **_src))
                    _track_skill(skill["filename"].replace(".py", ""))
                    _settle_skill(skill)
                    print(f"[Scryptian] Done!")
                elif result and result.startswith("[Scryptian Error]"):
                    telemetry.send("skill_failed", {"name": skill["title"], "reason": "error", "error": result[:200]})
                    self.root.after(0, lambda: self._show_result(result))
                    _refund_skill(skill)
                else:
                    telemetry.send("skill_failed", {"name": skill["title"], "reason": "empty"})
                    self.root.after(0, lambda: self._show_result("Skill returned an empty result."))
                    _refund_skill(skill)
            except Exception as e:
                telemetry.send("skill_failed", {"name": skill["title"], "reason": "exception", "error": str(e)[:200]})
                err_msg = f"Error: {e}"
                self.root.after(0, lambda msg=err_msg: self._show_result(msg))
                _refund_skill(skill)

        threading.Thread(target=execute, daemon=True).start()

    def run_externally(self, skill, input_text, source_hwnd=None):
        """Open the bar and run a skill with given text (called from SelectionToolbar)."""
        self._source_hwnd = source_hwnd
        pyperclip.copy(input_text)
        self.root.after(0, lambda: self._run_external(skill, input_text))

    def _run_external(self, skill, input_text):
        if not self.visible:
            self._show()
        self.list_frame.pack_forget()
        self.skill_hint.pack_forget()
        self.entry.config(state="disabled")
        self._start_anim(skill["title"])
        self.processing = True
        _t0 = time.time()
        _src = source_detect.get_source_info(getattr(self, '_source_hwnd', None))

        def execute():
            try:
                if not _reserve_skill(skill):
                    self.processing = False
                    self.root.after(0, self._stop_anim)
                    self.root.after(0, lambda: self._show_result("Not enough slippers. Top up your balance to run this skill."))
                    return
                result = core.run_skill(skill, input_text)
                self.processing = False
                if result and not result.startswith("[Scryptian Error]"):
                    self.last_result = result
                    self.has_result = True
                    self.root.after(0, lambda: self._show_result(result))
                    telemetry.send("skill_run", _build_skill_event(skill, input_text, time.time() - _t0, **_src, via="selection"))
                    _settle_skill(skill)
                else:
                    telemetry.send("skill_failed", {"name": skill["title"], "via": "selection", "reason": "error_or_empty", "error": (result or "")[:200]})
                    self.root.after(0, lambda t=result: self._show_result(t or "Skill returned an empty result."))
                    _refund_skill(skill)
            except Exception as e:
                telemetry.send("skill_failed", {"name": skill["title"], "via": "selection", "reason": "exception", "error": str(e)[:200]})
                self.root.after(0, lambda msg=str(e): self._show_result(f"Error: {msg}"))
                _refund_skill(skill)

        threading.Thread(target=execute, daemon=True).start()

    def _show_result(self, text):
        """Shows result below the bar, dynamically expanding the window."""
        if not self.window:
            return

        # Stop animation if this is a real result (not an animation frame)
        if self._anim_skill and not text.startswith(self._anim_skill):
            self._stop_anim()

        # Unpack everything before repacking
        self.entry_shell.pack_forget()
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
            self._show_chain()

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
                font=("Segoe UI", 11),
                bg="#18181b",
                fg="#efeff1",
                cursor="hand2",
                padx=6,
                pady=5,
                justify="center",
            )
            btn.grid(row=0, column=i, sticky="ew", padx=(0, 4) if i < 2 else (0, 0))
            btn.bind("<Button-1>", lambda e, t=skill_title: self._run_chain(t))
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#2d2d33", fg="#efeff1"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg="#18181b", fg="#efeff1"))
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
            1: self._open_skills_folder,
            2: self._open_telegram,
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


    def _open_report_dialog(self):
        """Compact styled feedback/bug report dialog."""
        import platform
        last_result_snapshot = self.last_result

        dlg = tk.Toplevel(self.root)
        dlg.overrideredirect(True)
        dlg.attributes("-topmost", True)
        dlg.attributes("-toolwindow", True)
        dlg.configure(bg="#0e0e10")

        outer = tk.Frame(dlg, bg="#2d2d33", padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        inner = tk.Frame(outer, bg="#0e0e10", padx=16, pady=14)
        inner.pack(fill="both", expand=True)

        tk.Label(inner, text="Send feedback", font=("Segoe UI", 11, "bold"),
                 bg="#0e0e10", fg="#efeff1", anchor="w").pack(fill="x", pady=(0, 10))

        # Contact field
        tk.Label(inner, text="Contact  (optional)", font=("Segoe UI", 11),
                 bg="#0e0e10", fg="#adadb8", anchor="w").pack(fill="x")
        contact_var = tk.StringVar()
        contact_entry = tk.Entry(inner, textvariable=contact_var,
                                 font=("Segoe UI", 11), bg="#18181b", fg="#efeff1",
                                 insertbackground="#efeff1", relief="flat", bd=0)
        contact_entry.pack(fill="x", pady=(2, 10), ipady=5)

        # Message field
        tk.Label(inner, text="Message", font=("Segoe UI", 11),
                 bg="#0e0e10", fg="#adadb8", anchor="w").pack(fill="x")
        msg_text = tk.Text(inner, font=("Segoe UI", 11), bg="#18181b", fg="#efeff1",
                           insertbackground="#efeff1", relief="flat", bd=0,
                           height=4, wrap="word")
        msg_text.pack(fill="x", pady=(2, 12))

        btn_row = tk.Frame(inner, bg="#0e0e10")
        btn_row.pack(fill="x")

        cancel_btn = tk.Label(btn_row, text="Cancel", font=("Segoe UI", 11),
                              bg="#0e0e10", fg="#adadb8", cursor="hand2")
        cancel_btn.pack(side="right", padx=(8, 0))
        cancel_btn.bind("<Button-1>", lambda e: dlg.destroy())
        cancel_btn.bind("<Enter>", lambda e: cancel_btn.config(fg="#efeff1"))
        cancel_btn.bind("<Leave>", lambda e: cancel_btn.config(fg="#adadb8"))

        def _submit():
            msg = msg_text.get("1.0", "end").strip()
            contact = contact_var.get().strip()
            telemetry.send("feedback", {
                "contact": contact,
                "message": msg[:1000],
                "last_result": last_result_snapshot[:500] if last_result_snapshot else "",
                "platform": platform.platform(),
                "skills_count": len(self.skills),
            })
            dlg.destroy()
            self._show_result("Thanks for the feedback!")

        send_btn = tk.Label(btn_row, text="Send", font=("Segoe UI", 11, "bold"),
                            bg="#3b82f6", fg="#efeff1", cursor="hand2",
                            padx=14, pady=3)
        send_btn.pack(side="right")
        send_btn.bind("<Button-1>", lambda e: _submit())
        send_btn.bind("<Enter>", lambda e: send_btn.config(bg="#60a5fa"))
        send_btn.bind("<Leave>", lambda e: send_btn.config(bg="#3b82f6"))

        dlg.update_idletasks()
        w, h = dlg.winfo_reqwidth(), dlg.winfo_reqheight()
        if self.window:
            bx = self.window.winfo_x() + (self.window.winfo_width() - w) // 2
            by = self.window.winfo_y() + self.window.winfo_height() + 6
        else:
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            bx, by = (sw - w) // 2, (sh - h) // 2
        dlg.geometry(f"{w}x{h}+{bx}+{by}")
        dlg.attributes("-alpha", 0.0)
        self._fade_dialog(dlg, 0.0)
        contact_entry.focus_set()

    def _fade_dialog(self, dlg, alpha):
        alpha = min(alpha + 0.1, 1.0)
        try:
            dlg.attributes("-alpha", alpha)
        except Exception:
            return
        if alpha < 1.0:
            self.root.after(16, lambda: self._fade_dialog(dlg, alpha))

    def _open_skills_folder(self):
        """Open skills folder in file manager (cross-platform)."""
        import subprocess
        if IS_WINDOWS:
            os.startfile(SKILLS_DIR)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", SKILLS_DIR])
        else:
            subprocess.Popen(["xdg-open", SKILLS_DIR])

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

    def show(self, text, x, y, source_hwnd):
        self._input_text = text
        self._source_hwnd = source_hwnd
        self.skills = core.scan_skills()  # Hot-reload
        self._show_window(x, y)

    def _show_window(self, x, y):
        self._cancel_dismiss()
        self._destroy_window()

        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.configure(bg="#0e0e10")
        win.attributes("-topmost", True)

        outer = tk.Frame(win, bg="#18181b", padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        inner = tk.Frame(outer, bg="#0e0e10", padx=0, pady=2)
        inner.pack(fill="both", expand=True)

        pinned = pins_module.get_pinned_skills(self.skills)
        if pinned:
            visible = pinned
        else:
            default_titles = ("Summarize", "Translate to English")
            by_title = {s["title"]: s for s in self.skills}
            visible = [by_title[t] for t in default_titles if t in by_title]
        for skill in visible:
            row = tk.Frame(inner, bg="#0e0e10", cursor="hand2")
            row.pack(fill="x", padx=0, pady=0)
            lbl = tk.Label(
                row,
                text=f"  {skill['title']}",
                bg="#0e0e10", fg="#efeff1",
                font=("Segoe UI", 11), anchor="w",
                cursor="hand2", padx=4, pady=4,
            )
            lbl.pack(fill="x")
            cmd = lambda s=skill, r=row, l=lbl: self._run_skill(s)
            row.bind("<Button-1>", lambda e, s=skill: self._run_skill(s))
            lbl.bind("<Button-1>", lambda e, s=skill: self._run_skill(s))
            row.bind("<Enter>", lambda e, r=row, l=lbl: (r.config(bg="#18181b"), l.config(bg="#18181b")))
            row.bind("<Leave>", lambda e, r=row, l=lbl: (r.config(bg="#0e0e10"), l.config(bg="#0e0e10")))

        tk.Frame(inner, bg="#18181b", height=1).pack(fill="x", padx=4)

        close = tk.Label(
            inner, text="  dismiss",
            bg="#0e0e10", fg="#2d2d33",
            font=("Segoe UI", 11), anchor="w",
            cursor="hand2", padx=4, pady=3,
        )
        close.pack(fill="x")
        close.bind("<Button-1>", lambda e: self._dismiss())

        win.update_idletasks()
        w = win.winfo_reqwidth()
        h = win.winfo_reqheight()
        screen_w = self.root.winfo_screenwidth()

        px = min(x + 10, screen_w - w - 10)
        py = y - h - 12
        if py < 0:
            py = y + 20

        win.geometry(f"+{px}+{py}")
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0)
        self.window = win
        self._fade_in(win, 0.0)
        self.root.after(400, self._start_click_watcher)
        self._start_focus_watcher()

    def _run_skill(self, skill):
        text = self._input_text
        source_hwnd = self._source_hwnd
        self._dismiss()

        # Check caret synchronously (fast WinAPI call) before deciding flow
        editable = False
        if IS_WINDOWS and source_hwnd:
            try:
                class _GTI(ctypes.Structure):
                    _fields_ = [("cbSize", ctypes.c_ulong), ("flags", ctypes.c_ulong),
                                 ("hwndActive", ctypes.c_void_p), ("hwndFocus", ctypes.c_void_p),
                                 ("hwndCapture", ctypes.c_void_p), ("hwndMenuOwner", ctypes.c_void_p),
                                 ("hwndMoveSize", ctypes.c_void_p), ("hwndCaret", ctypes.c_void_p),
                                 ("rcCaret", ctypes.c_long * 4)]
                gti = _GTI()
                gti.cbSize = ctypes.sizeof(_GTI)
                tid = ctypes.windll.user32.GetWindowThreadProcessId(source_hwnd, None)
                ctypes.windll.user32.GetGUIThreadInfo(tid, ctypes.byref(gti))
                editable = bool(gti.hwndCaret)
            except Exception:
                pass

        if not editable and self.bar:
            # Open full bar immediately — model runs inside it
            self.bar.run_externally(skill, text, source_hwnd)
            return

        # Editable field: run inline and paste back
        _src = source_detect.get_source_info(source_hwnd)

        def execute():
            _t0 = time.time()
            try:
                if not _reserve_skill(skill):
                    return
                result = core.run_skill(skill, text)
                if result and not result.startswith("[Scryptian Error]"):
                    pyperclip.copy(result)
                    telemetry.send("skill_run", _build_skill_event(skill, text, time.time() - _t0, **_src, via="selection"))
                    _settle_skill(skill)
                    time.sleep(0.12)
                    ctypes.windll.user32.SetForegroundWindow(source_hwnd)
                    time.sleep(0.06)
                    keyboard.send("ctrl+v")
                else:
                    telemetry.send("skill_failed", {"name": skill["title"], "via": "selection_inline", "reason": "error_or_empty", "error": (result or "")[:200]})
                    _refund_skill(skill)
            except Exception as e:
                telemetry.send("skill_failed", {"name": skill["title"], "via": "selection_inline", "reason": "exception", "error": str(e)[:200]})
                print(f"[Scryptian] Selection skill error: {e}")
                _refund_skill(skill)

        threading.Thread(target=execute, daemon=True).start()

    def _fade_in(self, win, alpha):
        if not self.window or self.window is not win:
            return
        alpha = min(alpha + 0.08, 1.0)
        try:
            win.attributes("-alpha", alpha)
        except Exception:
            return
        if alpha < 1.0:
            self.root.after(16, lambda: self._fade_in(win, alpha))

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
        def _check():
            if not self._focus_watch_active or not self.window:
                return
            try:
                fg = ctypes.windll.user32.GetForegroundWindow()
                if src and fg != src:
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

    # Hidden root tkinter window — keeps mainloop on the main thread
    root = tk.Tk()
    root.withdraw()

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

    if IS_WINDOWS:
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
