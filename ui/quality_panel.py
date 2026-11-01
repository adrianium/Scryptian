# ui/quality_panel.py — "Rate the result" list inside the Scryptian bar.

import datetime
import tkinter as tk

import keyboard
import result_history
import telemetry


class QualityPanel:
    """Recent file results, with a Bad result button on each row."""

    def __init__(self, bar):
        self.bar = bar
        self.root = bar.root
        self.frame = None
        self._open = False
        self._backspace_hotkey = None

    def open(self):
        if not self.bar.window:
            return
        telemetry.send("quality_opened")
        self._open = True
        self.bar.in_quality = True
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
        try:
            self._backspace_hotkey = keyboard.add_hotkey(
                "backspace", self._on_backspace_global, suppress=True,
            )
        except Exception:
            self._backspace_hotkey = None

        if self.frame:
            self.frame.destroy()
        self.frame = tk.Frame(self.bar.container, bg="#202020")
        self.frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self._build_header()
        self._build_list()
        self._fit_window()

    def _on_backspace(self, event):
        self.close()
        return "break"

    def _on_backspace_global(self):
        if self._open:
            self.root.after(0, self.close)

    def _release_keys(self):
        try:
            self.root.unbind_all("<BackSpace>")
        except Exception:
            pass
        if self._backspace_hotkey is not None:
            try:
                keyboard.remove_hotkey(self._backspace_hotkey)
            except Exception:
                pass
            self._backspace_hotkey = None

    def dismiss(self):
        """Drop key hooks when the bar itself is closing."""
        self._open = False
        self.bar.in_quality = False
        self._release_keys()
        self.frame = None

    def close(self):
        self._open = False
        self.bar.in_quality = False
        self.bar.processing = False
        self._release_keys()
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

    def _fit_window(self):
        """Size the bar to the rate page, with room under the last row."""
        if not self.bar.window:
            return
        self.bar.window.update_idletasks()
        target = self.bar.border.winfo_reqheight() + 36
        win = self.bar.window
        w = win.winfo_width()
        x = win.winfo_x()
        y = win.winfo_y()
        wa = self.bar._work_area()
        if wa:
            top, bottom = wa[1], wa[3]
            limit = max(bottom - top - 32, 220)
            target = min(target, limit)
            if y + target > bottom - 16:
                y = max(top + 16, bottom - 16 - target)
        win.geometry(f"{w}x{target}+{x}+{y}")
        win.update_idletasks()

    def _build_header(self):
        header = tk.Frame(self.frame, bg="#202020")
        header.pack(fill="x", pady=(0, 4))

        tk.Label(header, text="Rate the result", font=("Segoe UI Variable", 13, "bold"),
                 bg="#202020", fg="#FFFFFF").pack(side="left")

        back_group = tk.Frame(header, bg="#202020")
        back_group.pack(side="right")

        back = tk.Label(back_group, text="← Back", font=("Segoe UI Variable", 11),
                        bg="#202020", fg="#60CDFF", cursor="hand2")
        back.pack(anchor="e")
        back.bind("<Button-1>", lambda e: self.close())

        tk.Label(back_group, text="[ Backspace ]", font=("Segoe UI Variable", 9),
                 bg="#202020", fg="#C5C5C5").pack(anchor="e")

        tk.Label(self.frame, text="Mark a result that came out badly.",
                 font=("Segoe UI Variable", 11),
                 bg="#202020", fg="#9A9A9A", anchor="w").pack(fill="x", pady=(0, 8))

    def _build_list(self):
        items = result_history.recent()
        if not items:
            tk.Label(
                self.frame,
                text="No results yet.\nRun an action, then come back if the result was bad.",
                font=("Segoe UI Variable", 12),
                bg="#202020", fg="#C5C5C5", justify="left", anchor="w",
            ).pack(fill="x", pady=(8, 4))
            return

        canvas = tk.Canvas(self.frame, bg="#202020", height=120,
                           highlightthickness=0, bd=0)
        canvas.pack(fill="x", pady=(0, 8))
        inner = tk.Frame(canvas, bg="#202020")
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _fit(event=None):
            canvas.itemconfigure(window_id, width=canvas.winfo_width())
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner.bind("<Configure>", _fit)
        canvas.bind("<Configure>", _fit)

        def _wheel(event):
            canvas.yview_scroll(int(-event.delta / 120), "units")

        canvas.bind("<MouseWheel>", _wheel)
        inner.bind("<MouseWheel>", _wheel)

        for item in items:
            self._make_row(inner, item, _wheel)

        inner.update_idletasks()
        content_h = inner.winfo_reqheight()
        if content_h < 40:
            content_h = len(items) * 88
        row_h = max(88, content_h // max(len(items), 1))
        show = min(len(items), 6)
        canvas.config(height=min(content_h + 24, show * row_h + 24))

    def _make_row(self, parent, item, wheel):
        row = tk.Frame(parent, bg="#2B2B2B")
        row.pack(fill="x", pady=3)

        left = tk.Frame(row, bg="#2B2B2B")
        left.pack(side="left", fill="x", expand=True, padx=10, pady=8)

        title = tk.Label(left, text=item.get("skill_title") or "Action",
                         font=("Segoe UI Variable", 13),
                         bg="#2B2B2B", fg="#FFFFFF", anchor="w")
        title.pack(anchor="w")

        pair = f"{str(item.get('input_type') or '').upper()} → {str(item.get('output_type') or '').upper()}"
        when = _format_when(item.get("at") or "")
        meta = tk.Label(left, text=f"{pair}    {when}".rstrip(),
                        font=("Segoe UI Variable", 11),
                        bg="#2B2B2B", fg="#9A9A9A", anchor="w")
        meta.pack(anchor="w")

        already = item.get("verdict") == "bad"
        btn = _rounded_text_button(
            row,
            "Sent" if already else "Bad result",
            enabled=not already,
        )
        btn.pack(side="right", padx=10, pady=8)

        def _mark(_event=None, entry=item, button=btn):
            if not button.enabled:
                return
            saved = result_history.mark_bad(entry.get("id"))
            button.set_sent()
            if not saved:
                return
            telemetry.send("skill_quality", {
                "skill_id": saved.get("skill_id", ""),
                "skill_title": saved.get("skill_title", ""),
                "input_type": saved.get("input_type", ""),
                "output_type": saved.get("output_type", ""),
                "verdict": "bad",
            })

        if not already:
            btn.bind("<Button-1>", _mark)

        for widget in (row, left, title, meta, btn):
            widget.bind("<MouseWheel>", wheel)


def _rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


def _rounded_text_button(parent, text, enabled):
    """Small strict-radius button used for Bad result."""
    import tkinter.font as tkfont
    font = tkfont.Font(family="Segoe UI Variable", size=11)
    width = font.measure(text) + 28
    height = 30
    canvas = tk.Canvas(
        parent, width=width, height=height, bg=parent.cget("bg"),
        highlightthickness=0, bd=0, cursor="hand2" if enabled else "arrow",
    )
    canvas.enabled = enabled
    canvas._label = text
    canvas._font = font

    def redraw(color=None):
        if color is None:
            color = "#3C3C3C" if canvas.enabled else "#2B2B2B"
        fg = "#FFFFFF" if canvas.enabled else "#9A9A9A"
        canvas.delete("all")
        _rounded_rect(canvas, 1, 1, width - 1, height - 1, 6, fill=color, outline=color)
        canvas.create_text(width / 2, height / 2, text=canvas._label, fill=fg, font=font)

    def set_sent():
        canvas.enabled = False
        canvas._label = "Sent"
        canvas.config(cursor="arrow")
        canvas.unbind("<Enter>")
        canvas.unbind("<Leave>")
        redraw()

    canvas.set_sent = set_sent
    if enabled:
        canvas.bind("<Enter>", lambda e: redraw("#4A4A4A"))
        canvas.bind("<Leave>", lambda e: redraw("#3C3C3C"))
    redraw()
    return canvas


def _format_when(iso):
    try:
        dt = datetime.datetime.fromisoformat(iso)
    except Exception:
        return ""
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.strftime("%b %d, %H:%M")
