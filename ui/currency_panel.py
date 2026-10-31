# ui/currency_panel.py — Slippers wallet UI rendered inside the Scryptian bar.

import os
import sys
import json
import threading
import tkinter as tk
from urllib import request

from PIL import Image, ImageTk

import bridge
import keyboard
import store
import telemetry
import wallet
from config import BASE_DIR, SLIPPER_SCALE

# Paddle checkout worker (sandbox). Creates a transaction and returns a checkout URL.
CHECKOUT_URL = "https://paddle-checkout.nurlannapo.workers.dev/"

# price_id -> (button amount, credits text)
PRICES = [
    ("pri_01m35eacd1ak226p80qe74c5es", "$5", "5,000 slippers"),
    ("pri_01m35eb4mhvs36qksw814rt1fg", "$10", "11,000 slippers  (+10%)"),
    ("pri_01m35ec7qtnxt3xpxy4w6zvnaq", "$20", "23,000 slippers  (+15%)"),
    ("pri_01m35edejvhf8dk5tpvtrzxk2n", "$50", "60,000 slippers  (+20%)"),
]

RATE_TEXT = "1 dollar = 1000 slippers"

REFRESH_INTERVAL_MS = 10000  # poll balance every 10s while the panel is open

PAY_PER_OUTCOME_TEXT = (
    "On Scryptian works Pay per Result model: balance decreases only when you get a result. "
    "If an action fails, you pay nothing - the developer takes the loss."
)


class CurrencyPanel:
    """Slippers wallet UI rendered inside the Scryptian bar."""

    def __init__(self, bar):
        self.bar = bar
        self.root = bar.root
        self.frame = None
        self._open = False
        self._backspace_hotkey = None
        self.balance_value = None
        self.buy_status = None
        self._orig_geo = None
        self._refresh_job = None

    def open(self):
        if not self.bar.window:
            return
        telemetry.send("wallet_opened")
        self._open = True
        self.bar.in_currency = True
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

        self._orig_geo = self.bar.window.geometry()

        if self.frame:
            self.frame.destroy()
        self.frame = tk.Frame(self.bar.container, bg="#202020")
        self.frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self._build_header()
        self._build_body()

        self.bar.window.update_idletasks()
        target_h = self.bar.container.winfo_reqheight() + 4
        self._animate_height(target_h)
        self._start_refresh()

    def _on_backspace(self, event):
        self.close()
        return "break"

    def _on_backspace_global(self):
        if self._open:
            self.root.after(0, self.close)

    def close(self):
        self._open = False
        self._stop_refresh()
        self.bar.in_currency = False
        self.bar.processing = False
        self.root.unbind_all("<BackSpace>")
        if self._backspace_hotkey is not None:
            keyboard.remove_hotkey(self._backspace_hotkey)
            self._backspace_hotkey = None

        def _restore_bar():
            if self.frame:
                self.frame.destroy()
                self.frame = None
            if not self.bar.window:
                return
            self.bar.entry.config(state="normal")
            self.bar.entry.delete(0, "end")
            self.bar.entry.insert(0, self.bar.placeholder_text)
            self.bar._placeholder_active = True
            self.bar.entry.config(fg="#C5C5C5")
            self.bar.balance_frame.pack(fill="x", padx=14, pady=(8, 0))
            self.bar.entry_border.pack(fill="x", padx=14, pady=(8, 8))
            self.bar._update_filter("")
            self.bar.entry.focus_set()
            self.bar.root.after_idle(self.bar._restore_placeholder_cursor)
            self.bar.root.after(50, self.bar._restore_placeholder_cursor)

        if self._orig_geo:
            parts = self._orig_geo.split("+")
            target_h = int(parts[0].split("x")[1])
            self._orig_geo = None
            self._animate_height(target_h, on_done=_restore_bar, check_open=False)
        else:
            _restore_bar()

    def _animate_height(self, target_h, on_done=None, check_open=True):
        if not self.bar.window:
            if on_done:
                on_done()
            return
        cur_h = self.bar.window.winfo_height()
        w = self.bar.window.winfo_width()
        x = self.bar.window.winfo_x()
        y = self.bar.window.winfo_y()
        steps = 12

        def _step(i):
            if check_open and not self._open:
                return
            if not self.bar.window:
                if on_done:
                    on_done()
                return
            if i >= steps:
                try:
                    self.bar.window.geometry(f"{w}x{target_h}+{x}+{y}")
                    self.bar.window.update_idletasks()
                except Exception:
                    pass
                if on_done:
                    on_done()
                return
            p = 1 - (1 - i / steps) ** 3  # ease-out cubic
            nh = int(cur_h + (target_h - cur_h) * p)
            try:
                self.bar.window.geometry(f"{w}x{nh}+{x}+{y}")
                self.bar.window.update_idletasks()
            except Exception:
                if on_done:
                    on_done()
                return
            self.root.after(16, lambda: _step(i + 1))

        _step(1)

    def _build_header(self):
        header = tk.Frame(self.frame, bg="#202020")
        header.pack(fill="x", pady=(0, 8))

        tk.Label(header, text="Slippers", font=("Segoe UI Variable", 13, "bold"),
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
                             bg="#202020", fg="#C5C5C5")
        back_hint.pack(anchor="e")

    def _build_body(self):
        body = tk.Frame(self.frame, bg="#202020")
        body.pack(fill="both", expand=True)

        card = tk.Frame(body, bg="#202020", padx=20, pady=20,
                        highlightthickness=1, highlightbackground="#3C3C3C")
        card.pack(fill="x", pady=(10, 16))

        tk.Label(card, text="Your balance", font=("Segoe UI Variable", 11),
                 bg="#202020", fg="#C5C5C5").pack(anchor="w")

        balance_row = tk.Frame(card, bg="#202020")
        balance_row.pack(anchor="w", pady=(4, 0))

        self.balance_icon = tk.Label(balance_row, text="🩴", font=("Segoe UI Emoji", 22),
                                     bg="#202020", fg="#60CDFF")
        self.balance_icon.pack(side="left", padx=(0, 8))
        self.balance_photo = None
        try:
            if getattr(sys, "frozen", False):
                assets_dir = os.path.join(sys._MEIPASS, "docs", "assets")
            else:
                assets_dir = os.path.join(BASE_DIR, "docs", "assets")
            icon_path = os.path.join(assets_dir, "slippers.png")
            source = Image.open(icon_path).convert("RGBA")
            alpha = source.getchannel("A").resize((32, 32), Image.Resampling.LANCZOS)
            icon = Image.new("RGBA", (32, 32), "#60CDFF")
            icon.putalpha(alpha)
            self.balance_photo = ImageTk.PhotoImage(icon)
            self.balance_icon.config(image=self.balance_photo, text="", width=32)
        except Exception:
            pass

        self.balance_value = tk.Label(balance_row, text="—", font=("Segoe UI Variable", 26, "bold"),
                                      bg="#202020", fg="#FFFFFF")
        self.balance_value.pack(side="left")

        rate = tk.Label(body, text=RATE_TEXT, font=("Segoe UI Variable", 11),
                        bg="#202020", fg="#C5C5C5")
        rate.pack(pady=(0, 10))

        

        for price_id, amount, credits in PRICES:
            btn = tk.Label(
                body,
                text=f"{amount}  →  {credits}",
                font=("Segoe UI Variable", 12, "bold"),
                bg="#202020", fg="#FFFFFF",
                padx=12, pady=10, cursor="hand2",
                highlightthickness=1, highlightbackground="#3C3C3C",
            )
            btn.pack(fill="x", pady=3)
            btn.bind("<Button-1>", lambda e, pid=price_id, amt=amount: self._buy(pid, amt))
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#2E2E2E"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg="#202020"))

        self.buy_status = tk.Label(body, text="", font=("Segoe UI Variable", 10),
                                   bg="#202020", fg="#C5C5C5", wraplength=600, justify="center")
        self.buy_status.pack(fill="x", pady=(10, 0))

        info = tk.Label(body, text=PAY_PER_OUTCOME_TEXT, font=("Segoe UI Variable", 10),
                        bg="#202020", fg="#9A9A9A", wraplength=600, justify="left")
        info.pack(fill="x", pady=(14, 0))

        self._set_balance(wallet.cached_balance())
        threading.Thread(target=self._load_balance, daemon=True).start()

    def _set_balance(self, bal):
        if not self._open or self.balance_value is None:
            return
        if bal is None:
            self.balance_value.config(text="—")
            return
        # Balance is stored in micro-slippers (1 slipper = SLIPPER_SCALE).
        if bal % SLIPPER_SCALE == 0:
            text = str(bal // SLIPPER_SCALE)
        else:
            text = f"{bal / SLIPPER_SCALE:.3f}".rstrip("0").rstrip(".")
        self.balance_value.config(text=text)

    def _load_balance(self):
        bal = wallet.refresh()
        if bal is not None:
            self.root.after(0, lambda: self._set_balance(bal))

    def _start_refresh(self):
        self._stop_refresh()
        self._refresh_job = self.root.after(REFRESH_INTERVAL_MS, self._auto_refresh)

    def _stop_refresh(self):
        if self._refresh_job is not None:
            try:
                self.root.after_cancel(self._refresh_job)
            except Exception:
                pass
            self._refresh_job = None

    def _auto_refresh(self):
        self._refresh_job = None
        if not self._open:
            return
        threading.Thread(target=self._load_balance, daemon=True).start()
        self._refresh_job = self.root.after(REFRESH_INTERVAL_MS, self._auto_refresh)

    def _buy(self, price_id, amount=""):
        user = wallet.user_id()
        telemetry.send("buy_clicked", {"price_id": price_id, "amount": amount})
        if self.buy_status is not None:
            self.buy_status.config(text="Opening checkout…")

        def do():
            try:
                req = request.Request(
                    CHECKOUT_URL,
                    data=json.dumps({"user_id": user, "price_id": price_id}).encode("utf-8"),
                    headers={"Content-Type": "application/json", "User-Agent": "Scryptian"},
                )
                with request.urlopen(req, timeout=15, context=store._ssl_ctx()) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                url = data.get("url")
                if url:
                    telemetry.send("checkout_opened", {"price_id": price_id})
                    self.root.after(0, lambda u=url: os.startfile(u))
                else:
                    telemetry.send("checkout_failed", {"price_id": price_id, "reason": "no_url"})
                    self.root.after(0, lambda: self.buy_status.config(text="No checkout link. Try again."))
            except Exception as e:
                telemetry.send("checkout_failed", {"price_id": price_id, "reason": "error"})
                msg = f"Checkout failed: {e}"
                self.root.after(0, lambda: self.buy_status.config(text=msg))

        threading.Thread(target=do, daemon=True).start()
