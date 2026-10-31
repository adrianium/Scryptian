import tkinter as tk
import os
import sys
import threading
import keyboard
from PIL import Image, ImageTk
import store
import telemetry
import core
from config import SLIPPER_SCALE
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
        self.bar.balance_frame.pack_forget()
        self.bar.entry_border.pack_forget()
        self.bar.entry.config(state="disabled")
        self.root.bind_all("<BackSpace>", self._on_backspace, add="+")
        self._backspace_hotkey = keyboard.add_hotkey(
            "backspace", self._on_backspace_global, suppress=True,
        )
        for key in ("<Up>", "<Down>", "<Left>", "<Right>", "<Return>"):
            self.root.bind_all(key, self._on_card_key, add="+")

        if self.frame:
            self.frame.destroy()
        self.frame = tk.Frame(self.bar.container, bg="#202020")
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
        self._target_geo = f"{target_w}x{target_h}+{target_x}+{target_y}"

        def _apply_open():
            try:
                self.bar.window.geometry(self._target_geo)
                self.bar.window.update_idletasks()
            except Exception:
                pass
            self._fade_in()

        self._fade_out(_apply_open)

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

        def _restore_bar():
            if not self.bar.window:
                return
            self.bar.entry.config(state="normal")
            self.bar.entry.delete(0, "end")
            self.bar.entry.insert(0, self.bar.placeholder_text)
            self.bar._placeholder_active = True
            self.bar.entry.config(fg="#C5C5C5")
            self.bar.balance_frame.pack(fill="x", padx=14, pady=(8, 0))
            self.bar.entry_border.pack(fill="x", padx=14, pady=(8, 8))
            self.bar.skills = core.scan_skills()
            self.bar._update_filter("")
            self.bar.entry.focus_set()
            self.bar.root.after_idle(self.bar._restore_placeholder_cursor)
            self.bar.root.after(50, self.bar._restore_placeholder_cursor)

        def _apply_close():
            if self.frame:
                self.frame.destroy()
                self.frame = None
            if self._orig_geo and self.bar.window:
                try:
                    self.bar.window.geometry(self._orig_geo)
                    self.bar.window.update_idletasks()
                except Exception:
                    pass
            _restore_bar()
            self._fade_in()

        self._fade_out(_apply_close)

    def _apply_refreshed_skills(self, skills):
        if not self.bar.window or self._open:
            return
        self.bar.skills = skills
        if self.bar._placeholder_active:
            self.bar._update_filter("")

    # ── header ──────────────────────────────────────────────────

    def _build_header(self):
        header = tk.Frame(self.frame, bg="#202020")
        header.pack(fill="x", pady=(0, 8))

        tk.Label(header, text="Scryptian Store", font=("Segoe UI Variable", 13, "bold"),
                 bg="#202020", fg="#FFFFFF").pack(side="left")

        back_group = tk.Frame(header, bg="#202020")
        back_group.pack(side="right")

        back = tk.Label(back_group, text="← Back", font=("Segoe UI Variable", 11),
                        bg="#202020", fg="#60CDFF", cursor="hand2")
        back.pack(anchor="e")
        back.bind("<Button-1>", lambda e: self.close())
        back.bind("<Enter>", lambda e: back.config(fg="#60CDFF"))
        back.bind("<Leave>", lambda e: back.config(fg="#60CDFF"))

        back_hint = tk.Label(back_group, text="[ Backspace ]", font=("Segoe UI Variable", 9),
                             bg="#202020", fg="#9A9A9A")
        back_hint.pack(anchor="e")

        status_row = tk.Frame(self.frame, bg="#202020")
        status_row.pack(fill="x", pady=(0, 6))

        self.status = tk.Label(
            status_row,
            text="Loading...",
            font=("Segoe UI Variable", 11),
            bg="#202020",
            fg="#C5C5C5",
            anchor="w",
        )
        self.status.pack(side="left")

        navigation_hint = tk.Frame(status_row, bg="#202020")
        navigation_hint.pack(side="right")
        self.navigation_photo = None
        navigation_icon = tk.Label(
            navigation_hint,
            text="↕",
            font=("Segoe UI Symbol", 12),
            bg="#202020",
            fg="#60CDFF",
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
            icon = Image.new("RGBA", (16, 16), "#60CDFF")
            icon.putalpha(alpha)
            self.navigation_photo = ImageTk.PhotoImage(icon)
            navigation_icon.config(image=self.navigation_photo, text="", width=16)
        except Exception:
            pass

        tk.Label(
            navigation_hint,
            text="Use arrows to navigate  •  Enter to install",
            font=("Segoe UI Variable", 10),
            bg="#202020",
            fg="#9A9A9A",
        ).pack(side="left")

    # ── scrollable list ─────────────────────────────────────────

    def _build_list(self):
        shell = tk.Frame(self.frame, bg="#202020")
        shell.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(
            shell, bg="#202020", highlightthickness=0, bd=0,
        )
        self.canvas.pack(side="left", fill="both", expand=True)

        # Thin custom scrollbar
        self.scroll_canvas = tk.Canvas(shell, bg="#202020", width=6, highlightthickness=0, bd=0)
        self.scroll_canvas.bind("<Button-1>", self._on_scrollbar_click)

        self.rows = tk.Frame(self.canvas, bg="#202020")
        self._canvas_window = self.canvas.create_window(
            (0, 0), window=self.rows, anchor="nw",
        )
        self.rows.bind(
            "<Configure>",
            lambda e: (self.canvas.configure(scrollregion=self.canvas.bbox("all")), self._update_scrollbar()),
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: (self.canvas.itemconfigure(self._canvas_window, width=e.width), self._update_scrollbar()),
        )
        self.canvas.bind_all("<MouseWheel>", self._mousewheel)

    def _update_scrollbar(self):
        """Render the thin scrollbar (hidden when content fits)."""
        if not getattr(self, "scroll_canvas", None) or not getattr(self, "canvas", None):
            return
        try:
            bbox = self.canvas.bbox("all") or (0, 0, 0, 0)
            content_h = bbox[3] - bbox[1]
            viewport_h = self.canvas.winfo_height()
        except Exception:
            return
        if content_h <= viewport_h + 2:
            self.scroll_canvas.pack_forget()
            return
        self.scroll_canvas.pack(side="right", fill="y", padx=(0, 4), pady=4)
        self.canvas.update_idletasks()
        sb_h = self.scroll_canvas.winfo_height()
        if sb_h <= 0:
            return
        thumb_h = max(20, int(viewport_h / content_h * sb_h))
        top_frac = self.canvas.yview()[0]
        thumb_y = int(top_frac * (sb_h - thumb_h))
        self.scroll_canvas.delete("all")
        self.scroll_canvas.create_rectangle(0, thumb_y, 6, thumb_y + thumb_h, fill="#404040", outline="")

    def _on_scrollbar_click(self, event):
        """Jump the list to the clicked position on the thin scrollbar."""
        try:
            sb_h = self.scroll_canvas.winfo_height()
            if sb_h <= 0:
                return
            frac = max(0.0, min(1.0, event.y / sb_h))
            self.canvas.yview_moveto(frac)
            self._update_scrollbar()
        except Exception:
            pass

    # ── footer ──────────────────────────────────────────────────

    def _build_footer(self):
        # Footer ("Add your action" button) hidden for now.
        # footer = tk.Frame(self.frame, bg="#202020")
        # footer.pack(fill="x", pady=(12, 0))
        #
        # add_btn = tk.Label(
        #     footer,
        #     text="➕  Add your action here  →  Discord",
        #     font=("Segoe UI Variable", 11),
        #     bg="#202020", fg="#60CDFF",
        #     padx=6, pady=8, cursor="hand2",
        # )
        # add_btn.pack(fill="x")
        # add_btn.bind("<Button-1>", lambda e: self._open_discord())
        # add_btn.bind("<Enter>", lambda e: add_btn.config(bg="#0078D4"))
        # add_btn.bind("<Leave>", lambda e: add_btn.config(bg="#202020"))
        pass

    # ── animation ───────────────────────────────────────────────

    def _fade_out(self, on_swap, step=0):
        win = self.bar.window
        if not win:
            on_swap()
            return
        total = 4
        a = max(0.0, 1.0 - step / total)
        try:
            win.attributes("-alpha", a)
        except Exception:
            on_swap()
            return
        if step >= total:
            on_swap()
            return
        self.root.after(16, lambda: self._fade_out(on_swap, step + 1))

    def _fade_in(self, step=0, start=0.0):
        win = self.bar.window
        if not win:
            return
        total = 8
        p = start + (1.0 - start) * (1 - (1 - step / total) ** 3)
        try:
            win.attributes("-alpha", p)
        except Exception:
            return
        if step < total:
            self.root.after(16, lambda: self._fade_in(step + 1, start))

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
            self._update_scrollbar()

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
                     font=("Segoe UI Variable", 11), bg="#202020", fg="#9A9A9A").pack(pady=20)
        else:
            for skill in skills:
                self._row(skill)

        self._update_scrollbar()

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
            card.config(highlightbackground="#60CDFF" if i == self.selected_card else "#3C3C3C")
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
            self.rows, bg="#202020", padx=14, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground="#3C3C3C",
        )
        card.pack(fill="x", padx=4, pady=3)

        tk.Label(card, text=skill.get("title", ""),
                 font=("Segoe UI Variable", 13),
                 bg="#202020", fg="#FFFFFF", anchor="w").pack(fill="x")

        tk.Label(card, text=skill.get("description", ""),
                 font=("Segoe UI Variable", 11), bg="#202020", fg="#C5C5C5",
                 anchor="w", justify="left",
                 wraplength=int(self.root.winfo_screenwidth() * 0.45)).pack(fill="x", pady=(4, 8))

        bottom = tk.Frame(card, bg="#202020")
        bottom.pack(fill="x")

        meta = tk.Frame(bottom, bg="#202020")
        meta.pack(side="left")

        mode = str(skill.get("mode", "cloud")).strip().lower()
        mode_text = "Cloud" if mode == "cloud" else "Local"
        mode_fg = "#60CDFF"
        tk.Label(meta, text=mode_text, font=("Segoe UI Variable", 11, "bold"),
                 bg="#202020", fg=mode_fg).pack(side="left", padx=(0, 8))

        price = int(skill.get("price", 0) or 0)
        ppu = int(skill.get("price_per_unit", 0) or 0)
        unit = (skill.get("unit") or "").strip()
        if ppu > 0 and unit:
            price_text = f"{ppu / SLIPPER_SCALE:g} slippers / {unit}"
            price_fg = "#60CDFF"
        elif price > 0:
            price_text = f"{price / SLIPPER_SCALE:g} slippers per result"
            price_fg = "#60CDFF"
        else:
            price_text = "Free"
            price_fg = "#C5C5C5"
        tk.Label(meta, text=price_text,
                 font=("Segoe UI Variable", 11, "bold"),
                 bg="#202020", fg=price_fg).pack(side="left")

        installed = store.is_installed(skill, SKILLS_DIR)
        updatable = installed and store.has_update(skill, SKILLS_DIR)
        if updatable:
            label, bg, fg, cursor = "Update", "#60CDFF", "#FFFFFF", "hand2"
        elif installed:
            label, bg, fg, cursor = "Installed", "#3C3C3C", "#C5C5C5", "arrow"
        else:
            label, bg, fg, cursor = "Install", "#60CDFF", "#FFFFFF", "hand2"

        btn = tk.Label(bottom, text=label, font=("Segoe UI Variable", 11),
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
        btn.config(text="Installing...", bg="#f9e2af", fg="#202020", cursor="arrow")
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
                btn.config(text="Installed", bg="#3C3C3C", fg="#C5C5C5", cursor="arrow")
                self.bar.skills = core.scan_skills()
                telemetry.send("skill_installed", {"filename": skill.get("filename", "")})
            else:
                btn.config(text="Retry", bg="#f38ba8", fg="#202020", cursor="hand2")
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
