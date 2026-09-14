# ui/currency_panel.py — Slippers wallet UI rendered inside the Scryptian bar.

import os
import sys
import threading
import tkinter as tk

from PIL import Image, ImageTk

import bridge
import keyboard
import telemetry
import wallet
from config import BASE_DIR

# Paste your Stripe Payment Link here (sandbox/test mode for now).
BUY_URL = "https://buy.stripe.com/test_4gMbJ24Vm6bggZR8J57Vm00"

RATE_TEXT = "1 dollar = 1000 slippers"

PAY_PER_OUTCOME_TEXT = (
    "On Scryptian works Pay per Outcome model: you pay only when you get a result. "
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
        self.root.bind_all("<Return>", self._on_return, add="+")
        self._backspace_hotkey = keyboard.add_hotkey(
            "backspace", self._on_backspace_global, suppress=True,
        )

        if self.frame:
            self.frame.destroy()
        self.frame = tk.Frame(self.bar.container, bg="#0e0e10")
        self.frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self._build_header()
        self._build_body()

    def _on_backspace(self, event):
        self.close()
        return "break"

    def _on_backspace_global(self):
        if self._open:
            self.root.after(0, self.close)

    def _on_return(self, event):
        self._buy()
        return "break"

    def close(self):
        self._open = False
        self.bar.in_currency = False
        self.bar.processing = False
        self.root.unbind_all("<BackSpace>")
        self.root.unbind_all("<Return>")
        if self._backspace_hotkey is not None:
            keyboard.remove_hotkey(self._backspace_hotkey)
            self._backspace_hotkey = None
        if self.frame:
            self.frame.destroy()
            self.frame = None
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

        tk.Label(header, text="Slippers", font=("Segoe UI", 13, "bold"),
                 bg="#0e0e10", fg="#efeff1").pack(side="left")

        back_group = tk.Frame(header, bg="#0e0e10")
        back_group.pack(side="right")

        back = tk.Label(back_group, text="← Back", font=("Segoe UI", 11),
                        bg="#0e0e10", fg="#3b82f6", cursor="hand2")
        back.pack(anchor="e")
        back.bind("<Button-1>", lambda e: self.close())
        back.bind("<Enter>", lambda e: back.config(fg="#60a5fa"))
        back.bind("<Leave>", lambda e: back.config(fg="#3b82f6"))

        back_hint = tk.Label(back_group, text="[ Backspace ]", font=("Segoe UI", 9),
                             bg="#0e0e10", fg="#adadb8")
        back_hint.pack(anchor="e")

    def _build_body(self):
        body = tk.Frame(self.frame, bg="#0e0e10")
        body.pack(fill="both", expand=True)

        card = tk.Frame(body, bg="#18181b", padx=20, pady=20,
                        highlightthickness=1, highlightbackground="#2d2d33")
        card.pack(fill="x", pady=(10, 16))

        tk.Label(card, text="Your balance", font=("Segoe UI", 11),
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

        self.balance_value = tk.Label(balance_row, text="—", font=("Segoe UI", 26, "bold"),
                                      bg="#18181b", fg="#efeff1")
        self.balance_value.pack(side="left")

        rate = tk.Label(body, text=RATE_TEXT, font=("Segoe UI", 11),
                        bg="#0e0e10", fg="#adadb8")
        rate.pack(pady=(0, 10))

        

        self.buy_btn = tk.Label(body, text="Buy slippers - unavailable", font=("Segoe UI", 13, "bold"),
                                bg="#2d2d33", fg="#adadb8", padx=6, pady=12, cursor="arrow",
                                highlightthickness=1, highlightbackground="#3f3f46")
        self.buy_btn.pack(fill="x")

        notice = tk.Label(body, text="Purchases are temporarily unavailable.\nContact the author via Telegram (main menu).",
                          font=("Segoe UI", 11, "bold"),
                          bg="#18181b", fg="#60a5fa", padx=12, pady=10, wraplength=400, justify="center",
                          highlightthickness=1, highlightbackground="#60a5fa")
        notice.pack(fill="x", pady=(10, 0))

        info = tk.Label(body, text=PAY_PER_OUTCOME_TEXT, font=("Segoe UI", 10),
                        bg="#0e0e10", fg="#71717a", wraplength=600, justify="left")
        info.pack(fill="x", pady=(14, 0))

        self._set_balance(wallet.cached_balance())
        threading.Thread(target=self._load_balance, daemon=True).start()

    def _set_balance(self, bal):
        if not self._open or self.balance_value is None:
            return
        self.balance_value.config(text=str(bal) if bal is not None else "—")

    def _load_balance(self):
        bal = wallet.refresh()
        if bal is not None:
            self.root.after(0, lambda: self._set_balance(bal))

    def _buy(self):
        bridge.notify("Purchases unavailable", "Contact the author via Telegram (main menu).")
