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
    ("pri_01m357negyzc7testdea8v9t8f", "$5", "5,000 slippers"),
    ("pri_01m35844jfbfczm49gqcx3p4zh", "$10", "11,000 slippers  (+10%)"),
    ("pri_01m35851en1vdv2qnd60b3whtw", "$20", "23,000 slippers  (+15%)"),
    ("pri_01m35863v0tzn69fjk1sb1v2n8", "$50", "60,000 slippers  (+20%)"),
]

RATE_TEXT = "1 dollar = 1000 slippers"

PAY_PER_OUTCOME_TEXT = (
    "On Scryptian works Pay per Result model: you pay only when you get a result. "
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
        self.bar.entry_shell.pack_forget()
        self.bar.entry.config(state="disabled")
        self.root.bind_all("<BackSpace>", self._on_backspace, add="+")
        self._backspace_hotkey = keyboard.add_hotkey(
            "backspace", self._on_backspace_global, suppress=True,
        )

        self._orig_geo = self.bar.window.geometry()

        if self.frame:
            self.frame.destroy()
        self.frame = tk.Frame(self.bar.container, bg="#0e0e10")
        self.frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self._build_header()
        self._build_body()

        self.bar.window.update_idletasks()
        self.bar._resize(self.bar.container.winfo_reqheight() + 4)

    def _on_backspace(self, event):
        self.close()
        return "break"

    def _on_backspace_global(self):
        if self._open:
            self.root.after(0, self.close)

    def close(self):
        self._open = False
        self.bar.in_currency = False
        self.bar.processing = False
        self.root.unbind_all("<BackSpace>")
        if self._backspace_hotkey is not None:
            keyboard.remove_hotkey(self._backspace_hotkey)
            self._backspace_hotkey = None
        if self.frame:
            self.frame.destroy()
            self.frame = None
        if self._orig_geo and self.bar.window:
            self.bar.window.geometry(self._orig_geo)
            self._orig_geo = None
        if not self.bar.window:
            return
        self.bar.entry.config(state="normal")
        self.bar.entry.delete(0, "end")
        self.bar.entry.insert(0, self.bar.placeholder_text)
        self.bar._placeholder_active = True
        self.bar.entry.config(fg="#adadb8")
        self.bar.entry_shell.pack(fill="x", padx=12, pady=8)
        self.bar._update_filter("")
        self.bar.entry.focus_set()
        self.bar.root.after_idle(self.bar._restore_placeholder_cursor)
        self.bar.root.after(50, self.bar._restore_placeholder_cursor)

    def _build_header(self):
        header = tk.Frame(self.frame, bg="#0e0e10")
        header.pack(fill="x", pady=(0, 8))

        tk.Label(header, text="Slippers", font=("Manrope", 13, "bold"),
                 bg="#0e0e10", fg="#efeff1").pack(side="left")

        back_group = tk.Frame(header, bg="#0e0e10")
        back_group.pack(side="right")

        back = tk.Label(back_group, text="← Back", font=("Manrope", 11),
                        bg="#0e0e10", fg="#3b82f6", cursor="hand2")
        back.pack(anchor="e")
        back.bind("<Button-1>", lambda e: self.close())
        back.bind("<Enter>", lambda e: back.config(fg="#60a5fa"))
        back.bind("<Leave>", lambda e: back.config(fg="#3b82f6"))

        back_hint = tk.Label(back_group, text="[ Backspace ]", font=("Manrope", 9),
                             bg="#0e0e10", fg="#adadb8")
        back_hint.pack(anchor="e")

    def _build_body(self):
        body = tk.Frame(self.frame, bg="#0e0e10")
        body.pack(fill="both", expand=True)

        card = tk.Frame(body, bg="#18181b", padx=20, pady=20,
                        highlightthickness=1, highlightbackground="#2d2d33")
        card.pack(fill="x", pady=(10, 16))

        tk.Label(card, text="Your balance", font=("Manrope", 11),
                 bg="#18181b", fg="#adadb8").pack(anchor="w")

        balance_row = tk.Frame(card, bg="#18181b")
        balance_row.pack(anchor="w", pady=(4, 0))

        self.balance_icon = tk.Label(balance_row, text="🩴", font=("Segoe UI Emoji", 22),
                                     bg="#18181b", fg="#3b82f6")
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
            icon = Image.new("RGBA", (32, 32), "#3b82f6")
            icon.putalpha(alpha)
            self.balance_photo = ImageTk.PhotoImage(icon)
            self.balance_icon.config(image=self.balance_photo, text="", width=32)
        except Exception:
            pass

        self.balance_value = tk.Label(balance_row, text="—", font=("Manrope", 26, "bold"),
                                      bg="#18181b", fg="#efeff1")
        self.balance_value.pack(side="left")

        rate = tk.Label(body, text=RATE_TEXT, font=("Manrope", 11),
                        bg="#0e0e10", fg="#adadb8")
        rate.pack(pady=(0, 10))

        

        for price_id, amount, credits in PRICES:
            btn = tk.Label(
                body,
                text=f"{amount}  →  {credits}",
                font=("Manrope", 12, "bold"),
                bg="#18181b", fg="#efeff1",
                padx=12, pady=10, cursor="hand2",
                highlightthickness=1, highlightbackground="#2d2d33",
            )
            btn.pack(fill="x", pady=3)
            btn.bind("<Button-1>", lambda e, pid=price_id: self._buy(pid))
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#1e3a8a"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg="#18181b"))

        self.buy_status = tk.Label(body, text="", font=("Manrope", 10),
                                   bg="#0e0e10", fg="#adadb8", wraplength=600, justify="center")
        self.buy_status.pack(fill="x", pady=(10, 0))

        info = tk.Label(body, text=PAY_PER_OUTCOME_TEXT, font=("Manrope", 10),
                        bg="#0e0e10", fg="#71717a", wraplength=600, justify="left")
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

    def _buy(self, price_id):
        user = wallet.user_id()
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
                    self.root.after(0, lambda u=url: os.startfile(u))
                else:
                    self.root.after(0, lambda: self.buy_status.config(text="No checkout link. Try again."))
            except Exception as e:
                msg = f"Checkout failed: {e}"
                self.root.after(0, lambda: self.buy_status.config(text=msg))

        threading.Thread(target=do, daemon=True).start()
