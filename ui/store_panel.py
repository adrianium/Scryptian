import tkinter as tk
from tkinter import ttk
import threading
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
        self.bar.placeholder.place_forget()
        self.bar.entry.config(state="disabled")

        if self.frame:
            self.frame.destroy()
        self.frame = tk.Frame(self.bar.container, bg="#1e1e2e")
        self.frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self._build_header()
        self._build_list()
        self._build_footer()

        self._orig_geo = self.bar.window.geometry()
        self._animate_open()

        threading.Thread(target=self._load_store, daemon=True).start()

    def close(self):
        self._open = False
        self.bar.in_store = False
        self.bar.processing = False
        self.root.unbind_all("<MouseWheel>")
        if self._anim_job:
            self.root.after_cancel(self._anim_job)
            self._anim_job = None
        if self.frame:
            self.frame.destroy()
            self.frame = None
        if self._orig_geo and self.bar.window:
            self._animate_close()
        if not self.bar.window:
            return
        self.bar.entry.config(state="normal")
        self.bar.skills = core.scan_skills()
        self.bar._update_filter("")
        self.bar.entry.focus_set()

    # ── header ──────────────────────────────────────────────────

    def _build_header(self):
        header = tk.Frame(self.frame, bg="#1e1e2e")
        header.pack(fill="x", pady=(0, 8))

        tk.Label(header, text="Scryptian Store", font=("Segoe UI", 13, "bold"),
                 bg="#1e1e2e", fg="#cdd6f4").pack(side="left")

        back = tk.Label(header, text="← Back", font=("Segoe UI", 10),
                        bg="#1e1e2e", fg="#89b4fa", cursor="hand2")
        back.pack(side="right")
        back.bind("<Button-1>", lambda e: self.close())
        back.bind("<Enter>", lambda e: back.config(fg="#b4befe"))
        back.bind("<Leave>", lambda e: back.config(fg="#89b4fa"))

        self.status = tk.Label(self.frame, text="Loading...",
                               font=("Segoe UI", 9), bg="#1e1e2e",
                               fg="#a6adc8", anchor="w")
        self.status.pack(fill="x", pady=(0, 6))

    # ── scrollable list ─────────────────────────────────────────

    def _build_list(self):
        shell = tk.Frame(self.frame, bg="#1e1e2e")
        shell.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.Vertical.TScrollbar",
                        background="#313244", troughcolor="#1e1e2e",
                        arrowcolor="#585b70", bordercolor="#1e1e2e",
                        lightcolor="#313244", darkcolor="#313244")
        style.map("Dark.Vertical.TScrollbar",
                  background=[("active", "#45475a")])

        self.canvas = tk.Canvas(
            shell, bg="#1e1e2e", highlightthickness=0, bd=0,
        )
        scrollbar = ttk.Scrollbar(
            shell, orient="vertical", command=self.canvas.yview,
            style="Dark.Vertical.TScrollbar",
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.rows = tk.Frame(self.canvas, bg="#1e1e2e")
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
        footer = tk.Frame(self.frame, bg="#1e1e2e")
        footer.pack(fill="x", pady=(12, 0))

        add_btn = tk.Label(
            footer,
            text="➕  Add your action here  →  Discord",
            font=("Segoe UI", 10, "bold"),
            bg="#5865f2", fg="#ffffff",
            padx=12, pady=8, cursor="hand2",
        )
        add_btn.pack(fill="x")
        add_btn.bind("<Button-1>", lambda e: self._open_discord())
        add_btn.bind("<Enter>", lambda e: add_btn.config(bg="#4752c4"))
        add_btn.bind("<Leave>", lambda e: add_btn.config(bg="#5865f2"))

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

        if not skills:
            tk.Label(self.rows, text="No actions available right now.",
                     font=("Segoe UI", 11), bg="#1e1e2e", fg="#585b70").pack(pady=20)
        else:
            for skill in skills:
                self._row(skill)

    def _row(self, skill):
        card = tk.Frame(
            self.rows, bg="#313244", padx=14, pady=10,
            highlightthickness=1, highlightbackground="#45475a",
        )
        card.pack(fill="x", padx=4, pady=3)

        top = tk.Frame(card, bg="#313244")
        top.pack(fill="x")

        tk.Label(top, text=skill.get("title", ""),
                 font=("Segoe UI", 11, "bold"),
                 bg="#313244", fg="#cdd6f4", anchor="w").pack(side="left")

        price = skill.get("price", 0)
        if price > 0:
            price_text = f"${price:.2f}"
            price_fg = "#a6e3a1"
        else:
            price_text = "Free"
            price_fg = "#a6adc8"
        tk.Label(top, text=price_text,
                 font=("Segoe UI", 10, "bold"),
                 bg="#313244", fg=price_fg).pack(side="right")

        tk.Label(card, text=skill.get("description", ""),
                 font=("Segoe UI", 9), bg="#313244", fg="#a6adc8",
                 anchor="w", justify="left",
                 wraplength=int(self.root.winfo_screenwidth() * 0.45)).pack(fill="x", pady=(4, 8))

        installed = store.is_installed(skill, SKILLS_DIR)
        updatable = installed and store.has_update(skill, SKILLS_DIR)
        if updatable:
            label, bg, fg, cursor = "Update", "#89b4fa", "#1e1e2e", "hand2"
        elif installed:
            label, bg, fg, cursor = "Installed", "#45475a", "#a6adc8", "arrow"
        else:
            label, bg, fg, cursor = "Install", "#89b4fa", "#1e1e2e", "hand2"

        btn = tk.Label(card, text=label, font=("Segoe UI", 10, "bold"),
                       bg=bg, fg=fg, padx=14, pady=5, cursor=cursor)
        btn.pack(anchor="e")
        if updatable or not installed:
            btn.bind("<Button-1>", lambda e, s=skill, b=btn: self._install(s, b))

    # ── install ─────────────────────────────────────────────────

    def _install(self, skill, btn):
        btn.config(text="Installing...", bg="#f9e2af", fg="#1e1e2e", cursor="arrow")
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
                btn.config(text="Installed", bg="#45475a", fg="#a6adc8", cursor="arrow")
                self.bar.skills = core.scan_skills()
                telemetry.send("skill_installed", {"filename": skill.get("filename", "")})
            else:
                btn.config(text="Retry", bg="#f38ba8", fg="#1e1e2e", cursor="hand2")
                btn.bind("<Button-1>", lambda e, s=skill, b=btn: self._install(s, b))
                if error:
                    self.status.config(text=f"Install failed: {error}")
        except Exception:
            pass

    # ── discord ─────────────────────────────────────────────────

    def _open_discord(self):
        import webbrowser
        telemetry.send("store_add_skill_clicked")
        webbrowser.open("https://discord.gg/xDgwGNpsx")
