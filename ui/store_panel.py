import tkinter as tk
from tkinter import ttk
import os
import sys
import threading
import keyboard
from PIL import Image, ImageTk
import store
import telemetry
import core
from core.registry import SKILLS_DIR


class StorePanel:
    """Standalone store UI rendered inside the Scryptian bar."""

    def __init__(self, bar):
        self.bar = bar
        self.root = bar.root
        self.frame = None
        self.canvas = None
        self.rows = None
        self.status = None
        self._open = False
        self._anim_job = None
        self._orig_geo = None
        self._backspace_hotkey = None
        self.cards = []
        self.selected_card = 0

    # ── public API ──────────────────────────────────────────────

    def open(self):
        if not self.bar.window:
            return
        telemetry.send("store_opened")
        self._open = True
        self.bar.in_store = True
        self.bar.processing = True

        self.bar.list_frame.pack_forget()
        self.bar.skill_hint.pack_forget()
        self.bar.separator.pack_forget()
        self.bar.result_box.pack_forget()
        self.bar.hint_label.pack_forget()
        self.bar.entry_shell.pack_forget()
        self.bar.entry.config(state="disabled")
        self.root.bind_all("<BackSpace>", self._on_backspace, add="+")
        self._backspace_hotkey = keyboard.add_hotkey(
            "backspace", self._on_backspace_global, suppress=True,
        )
        for key in ("<Up>", "<Down>", "<Left>", "<Right>", "<Return>"):
            self.root.bind_all(key, self._on_card_key, add="+")

        if self.frame:
            self.frame.destroy()
        self.frame = tk.Frame(self.bar.container, bg="#1c2030")
        self.frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self._build_header()
        self._build_list()
        self._build_footer()

        self._orig_geo = self.bar.window.geometry()
        current_w = self.bar.window.winfo_width()
        current_h = self.bar.window.winfo_height()
        target_w = int(self.root.winfo_screenwidth() * 0.55)
        target_h = int(self.root.winfo_screenheight() * 0.65)
        work_area = self.bar._work_area()
        if work_area:
            work_left, work_top, work_right, work_bottom = work_area
            target_w = min(target_w, work_right - work_left - 32)
            target_h = min(target_h, work_bottom - work_top - 32)
        target_x = self.bar.window.winfo_x() - (target_w - current_w) // 2
        target_y = self.bar.window.winfo_y() - (target_h - current_h) // 2
        if work_area:
            target_x = max(work_left + 16, min(target_x, work_right - target_w - 16))
            target_y = max(work_top + 16, min(target_y, work_bottom - target_h - 16))
        self.bar.window.geometry(f"{target_w}x{target_h}+{target_x}+{target_y}")

        threading.Thread(target=self._load_store, daemon=True).start()

    def _on_backspace(self, event):
        self.close()
        return "break"

    def _on_backspace_global(self):
        if self._open:
            self.root.after(0, self.close)

    def close(self):
        self._open = False
        self.bar.in_store = False
        self.bar.processing = False
        self.root.unbind_all("<MouseWheel>")
        self.root.unbind_all("<BackSpace>")
        for key in ("<Up>", "<Down>", "<Left>", "<Right>", "<Return>"):
            self.root.unbind_all(key)
        if self._backspace_hotkey is not None:
            keyboard.remove_hotkey(self._backspace_hotkey)
            self._backspace_hotkey = None
        if self._anim_job:
            self.root.after_cancel(self._anim_job)
            self._anim_job = None
        if self.frame:
            self.frame.destroy()
            self.frame = None
        if self._orig_geo and self.bar.window:
            self.bar.window.geometry(self._orig_geo)
        if not self.bar.window:
            return
        self.bar.entry.config(state="normal")
        self.bar.entry.delete(0, "end")
        self.bar.entry.insert(0, self.bar.placeholder_text)
        self.bar._placeholder_active = True
        self.bar.entry.config(fg="#b0b0b0")
        self.bar.entry_shell.pack(fill="x", padx=12, pady=8)
        self.bar._update_filter("")

        def refresh_skills():
            skills = core.scan_skills()
            self.root.after(0, lambda: self._apply_refreshed_skills(skills))

        threading.Thread(target=refresh_skills, daemon=True).start()
        self.bar.entry.focus_set()
        self.bar.root.after_idle(self.bar._restore_placeholder_cursor)
        self.bar.root.after(50, self.bar._restore_placeholder_cursor)

    def _apply_refreshed_skills(self, skills):
        if not self.bar.window or self._open:
            return
        self.bar.skills = skills
        if self.bar._placeholder_active:
            self.bar._update_filter("")

    # ── header ──────────────────────────────────────────────────

    def _build_header(self):
        header = tk.Frame(self.frame, bg="#1c2030")
        header.pack(fill="x", pady=(0, 8))

        tk.Label(header, text="Scryptian Store", font=("Segoe UI", 13, "bold"),
                 bg="#1c2030", fg="#ffffff").pack(side="left")

        back_group = tk.Frame(header, bg="#1c2030")
        back_group.pack(side="right")

        back = tk.Label(back_group, text="← Back", font=("Segoe UI", 11),
                        bg="#1c2030", fg="#2cff00", cursor="hand2")
        back.pack(anchor="e")
        back.bind("<Button-1>", lambda e: self.close())
        back.bind("<Enter>", lambda e: back.config(fg="#6dff55"))
        back.bind("<Leave>", lambda e: back.config(fg="#2cff00"))

        back_hint = tk.Label(back_group, text="[ Backspace ]", font=("Segoe UI", 9),
                             bg="#1c2030", fg="#707080")
        back_hint.pack(anchor="e")

        status_row = tk.Frame(self.frame, bg="#1c2030")
        status_row.pack(fill="x", pady=(0, 6))

        self.status = tk.Label(
            status_row,
            text="Loading...",
            font=("Segoe UI", 11),
            bg="#1c2030",
            fg="#b0b0b0",
            anchor="w",
        )
        self.status.pack(side="left")

        navigation_hint = tk.Frame(status_row, bg="#1c2030")
        navigation_hint.pack(side="right")
        self.navigation_photo = None
        navigation_icon = tk.Label(
            navigation_hint,
            text="↕",
            font=("Segoe UI Symbol", 12),
            bg="#1c2030",
            fg="#2cff00",
            width=2,
        )
        navigation_icon.pack(side="left", padx=(0, 4))
        try:
            if getattr(sys, "frozen", False):
                assets_dir = os.path.join(sys._MEIPASS, "docs", "assets")
            else:
                assets_dir = os.path.join(os.path.dirname(SKILLS_DIR), "docs", "assets")
            icon_path = os.path.join(assets_dir, "up-and-down.png")
            source = Image.open(icon_path).convert("RGBA")
            alpha = source.getchannel("A").resize((16, 16), Image.Resampling.LANCZOS)
            icon = Image.new("RGBA", (16, 16), "#2cff00")
            icon.putalpha(alpha)
            self.navigation_photo = ImageTk.PhotoImage(icon)
            navigation_icon.config(image=self.navigation_photo, text="", width=16)
        except Exception:
            pass

        tk.Label(
            navigation_hint,
            text="Use arrows to navigate  •  Enter to install",
            font=("Segoe UI", 10),
            bg="#1c2030",
            fg="#707080",
        ).pack(side="left")

    # ── scrollable list ─────────────────────────────────────────

    def _build_list(self):
        shell = tk.Frame(self.frame, bg="#1c2030")
        shell.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.Vertical.TScrollbar",
                        background="#252a3c", troughcolor="#1c2030",
                        arrowcolor="#1c2030", bordercolor="#1c2030",
                        lightcolor="#252a3c", darkcolor="#252a3c")
        style.map("Dark.Vertical.TScrollbar",
                  background=[("active", "#2e3348")])

        self.canvas = tk.Canvas(
            shell, bg="#1c2030", highlightthickness=0, bd=0,
        )
        scrollbar = ttk.Scrollbar(
            shell, orient="vertical", command=self.canvas.yview,
            style="Dark.Vertical.TScrollbar",
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.rows = tk.Frame(self.canvas, bg="#1c2030")
        self._canvas_window = self.canvas.create_window(
            (0, 0), window=self.rows, anchor="nw",
        )
        self.rows.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self._canvas_window, width=e.width),
        )
        self.canvas.bind_all("<MouseWheel>", self._mousewheel)

    # ── footer ──────────────────────────────────────────────────

    def _build_footer(self):
        footer = tk.Frame(self.frame, bg="#1c2030")
        footer.pack(fill="x", pady=(12, 0))

        add_btn = tk.Label(
            footer,
            text="➕  Add your action here  →  Discord",
            font=("Segoe UI", 11),
            bg="#252a3c", fg="#2cff00",
            padx=6, pady=8, cursor="hand2",
        )
        add_btn.pack(fill="x")
        add_btn.bind("<Button-1>", lambda e: self._open_discord())
        add_btn.bind("<Enter>", lambda e: add_btn.config(bg="#1a331a"))
        add_btn.bind("<Leave>", lambda e: add_btn.config(bg="#252a3c"))

    # ── animation ───────────────────────────────────────────────

    def _animate_open(self):
        geo = self._orig_geo or self.bar.window.geometry()
        parts = geo.split("+")
        wh = parts[0].split("x")
        cur_w, cur_h = int(wh[0]), int(wh[1])
        cur_x, cur_y = int(parts[1]), int(parts[2])

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        target_w = int(sw * 0.55)
        target_h = int(sh * 0.65)

        steps = 12
        dw = (target_w - cur_w) / steps
        dh = (target_h - cur_h) / steps

        def _step(i):
            if i > steps or not self._open or not self.bar.window:
                return
            nw = int(cur_w + dw * i)
            nh = int(cur_h + dh * i)
            nx = cur_x - (nw - cur_w) // 2
            ny = cur_y - (nh - cur_h) // 2
            try:
                self.bar.window.geometry(f"{nw}x{nh}+{nx}+{ny}")
                self.bar.window.update_idletasks()
            except Exception:
                return
            self._anim_job = self.root.after(16, lambda: _step(i + 1))

        _step(1)

    def _animate_close(self):
        geo = self.bar.window.geometry()
        parts = geo.split("+")
        wh = parts[0].split("x")
        cur_w, cur_h = int(wh[0]), int(wh[1])
        cur_x, cur_y = int(parts[1]), int(parts[2])

        orig_parts = self._orig_geo.split("+")
        orig_wh = orig_parts[0].split("x")
        target_w, target_h = int(orig_wh[0]), int(orig_wh[1])
        target_x, target_y = int(orig_parts[1]), int(orig_parts[2])

        steps = 10
        dw = (target_w - cur_w) / steps
        dh = (target_h - cur_h) / steps
        dx = (target_x - cur_x) / steps
        dy = (target_y - cur_y) / steps

        def _step(i):
            if i > steps or not self.bar.window:
                return
            nw = int(cur_w + dw * i)
            nh = int(cur_h + dh * i)
            nx = int(cur_x + dx * i)
            ny = int(cur_y + dy * i)
            try:
                self.bar.window.geometry(f"{nw}x{nh}+{nx}+{ny}")
                self.bar.window.update_idletasks()
            except Exception:
                return
            self._anim_job = self.root.after(16, lambda: _step(i + 1))

        _step(1)

    # ── data loading ────────────────────────────────────────────

    def _load_store(self):
        try:
            skills = store.fetch_registry()
            self.root.after(0, lambda: self._render(skills))
        except Exception as e:
            self.root.after(0, lambda: self._error(str(e)))

    def _error(self, err):
        if not self._open:
            return
        self.status.config(text=f"Failed to load store: {err}")

    def _mousewheel(self, event):
        if self._open and self.canvas:
            self.canvas.yview_scroll(-int(event.delta / 120), "units")

    # ── rendering ───────────────────────────────────────────────

    def _render(self, skills):
        if not self._open:
            return
        self.status.config(text=f"{len(skills)} actions available")
        for w in self.rows.winfo_children():
            w.destroy()
        self.cards = []
        self.selected_card = 0

        if not skills:
            tk.Label(self.rows, text="No actions available right now.",
                     font=("Segoe UI", 11), bg="#1c2030", fg="#707080").pack(pady=20)
        else:
            for skill in skills:
                self._row(skill)

    def _on_card_key(self, event):
        if not self._open or not self.cards:
            return
        if event.keysym in ("Up", "Left"):
            self._select_card(self.selected_card - 1)
        elif event.keysym in ("Down", "Right"):
            self._select_card(self.selected_card + 1)
        elif event.keysym == "Return":
            self._activate_card()
        else:
            return
        return "break"

    def _select_card(self, index):
        if not self.cards:
            return
        self.selected_card = max(0, min(index, len(self.cards) - 1))
        for i, (card, _, _, _) in enumerate(self.cards):
            card.config(highlightbackground="#3d6a4c" if i == self.selected_card else "#2e3348")
        self._scroll_to_card()

    def _scroll_to_card(self):
        if not self.cards or not self.canvas:
            return
        try:
            card = self.cards[self.selected_card][0]
            self.canvas.update_idletasks()
            card_y = card.winfo_y()
            card_h = card.winfo_height()
            top = self.canvas.canvasy(0)
            bottom = top + self.canvas.winfo_height()
            content_h = max(1, self.rows.winfo_height())
            if card_y < top:
                self.canvas.yview_moveto(card_y / content_h)
            elif card_y + card_h > bottom:
                self.canvas.yview_moveto((card_y + card_h - self.canvas.winfo_height()) / content_h)
        except Exception:
            pass

    def _activate_card(self):
        card, skill, btn, can_install = self.cards[self.selected_card]
        if can_install:
            self._install(skill, btn)
        else:
            self.status.config(text=f"{skill.get('title', '')} is already installed")

    def _row(self, skill):
        card = tk.Frame(
            self.rows, bg="#252a3c", padx=14, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground="#2e3348",
        )
        card.pack(fill="x", padx=4, pady=3)

        tk.Label(card, text=skill.get("title", ""),
                 font=("Segoe UI", 13),
                 bg="#252a3c", fg="#ffffff", anchor="w").pack(fill="x")

        tk.Label(card, text=skill.get("description", ""),
                 font=("Segoe UI", 11), bg="#252a3c", fg="#b0b0b0",
                 anchor="w", justify="left",
                 wraplength=int(self.root.winfo_screenwidth() * 0.45)).pack(fill="x", pady=(4, 8))

        bottom = tk.Frame(card, bg="#252a3c")
        bottom.pack(fill="x")

        meta = tk.Frame(bottom, bg="#252a3c")
        meta.pack(side="left")

        mode = str(skill.get("mode", "cloud")).strip().lower()
        mode_text = "Cloud" if mode == "cloud" else "Local"
        mode_fg = "#00bfff"
        tk.Label(meta, text=mode_text, font=("Segoe UI", 11, "bold"),
                 bg="#252a3c", fg=mode_fg).pack(side="left", padx=(0, 8))

        price = skill.get("price", 0)
        if price > 0:
            price_text = f"{price} slippers per result"
            price_fg = "#2cff00"
        else:
            price_text = "Free"
            price_fg = "#b0b0b0"
        tk.Label(meta, text=price_text,
                 font=("Segoe UI", 11, "bold"),
                 bg="#252a3c", fg=price_fg).pack(side="left")

        installed = store.is_installed(skill, SKILLS_DIR)
        updatable = installed and store.has_update(skill, SKILLS_DIR)
        if updatable:
            label, bg, fg, cursor = "Update", "#2cff00", "#1c2030", "hand2"
        elif installed:
            label, bg, fg, cursor = "Installed", "#2e3348", "#b0b0b0", "arrow"
        else:
            label, bg, fg, cursor = "Install", "#2cff00", "#1c2030", "hand2"

        btn = tk.Label(bottom, text=label, font=("Segoe UI", 11),
                       bg=bg, fg=fg, padx=14, pady=5, cursor=cursor)
        btn.pack(side="right")
        can_install = updatable or not installed
        if can_install:
            btn.bind("<Button-1>", lambda e, s=skill, b=btn: self._install(s, b))

        index = len(self.cards)
        self.cards.append((card, skill, btn, can_install))
        card.bind("<Button-1>", lambda e, i=index: self._select_card(i))
        self._select_card(self.selected_card)

    # ── install ─────────────────────────────────────────────────

    def _install(self, skill, btn):
        btn.config(text="Installing...", bg="#f9e2af", fg="#1c2030", cursor="arrow")
        btn.unbind("<Button-1>")

        def do():
            try:
                store.install_skill(skill, SKILLS_DIR)
                self.root.after(0, lambda: self._install_done(skill, btn, True))
            except Exception as e:
                self.root.after(0, lambda: self._install_done(skill, btn, False, str(e)))

        threading.Thread(target=do, daemon=True).start()

    def _install_done(self, skill, btn, success, error=None):
        if not self._open:
            return
        try:
            if success:
                btn.config(text="Installed", bg="#2e3348", fg="#b0b0b0", cursor="arrow")
                self.bar.skills = core.scan_skills()
                telemetry.send("skill_installed", {"filename": skill.get("filename", "")})
            else:
                btn.config(text="Retry", bg="#f38ba8", fg="#1c2030", cursor="hand2")
                btn.bind("<Button-1>", lambda e, s=skill, b=btn: self._install(s, b))
                if error:
                    self.status.config(text=f"Install failed: {error}")
        except Exception:
            pass

    # ── discord ─────────────────────────────────────────────────

    def _open_discord(self):
        import webbrowser
        telemetry.send("store_add_skill_clicked")
        webbrowser.open("https://discord.gg/dc6VwAgCpc")
