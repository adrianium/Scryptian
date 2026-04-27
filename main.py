# main.py — Scryptian Core
# Skill scanner | Hotkey | UI bar

import os
import sys
import re
import importlib.util
import threading
import tkinter as tk
import pyperclip
import keyboard
import bridge
import telemetry
import tray
import autostart

IS_WINDOWS = sys.platform == "win32"

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
from config import HOTKEY, BASE_DIR
import bootstrap
bootstrap.setup()
SKILLS_DIR = os.path.join(BASE_DIR, "skills")


# ── Skill scanner ──
def scan_skills():
    """
    Scans the skills/ folder, reads metadata (@title, @description)
    and loads modules. Returns a list of dicts.
    """
    skills = []
    if not os.path.isdir(SKILLS_DIR):
        return skills

    for filename in sorted(os.listdir(SKILLS_DIR)):
        if not filename.endswith(".py") or filename.startswith("_"):
            continue

        filepath = os.path.join(SKILLS_DIR, filename)
        meta = _parse_metadata(filepath)
        module = _load_module(filename, filepath)

        if module and hasattr(module, "run"):
            skills.append({
                "title": meta.get("title", filename.replace(".py", "")),
                "description": meta.get("description", ""),
                "author": meta.get("author", ""),
                "module": module,
                "filename": filename,
            })
    return skills


def _parse_metadata(filepath):
    """Reads @title, @description, @author from file header comments."""
    meta = {}
    pattern = re.compile(r"^#\s*@(\w+):\s*(.+)$")
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("#"):
                break
            match = pattern.match(line)
            if match:
                meta[match.group(1).lower()] = match.group(2).strip()
    return meta


def _load_module(name, filepath):
    """Dynamically loads a .py file as a module."""
    try:
        spec = importlib.util.spec_from_file_location(name.replace(".py", ""), filepath)
        module = importlib.util.module_from_spec(spec)

        parent_dir = os.path.dirname(os.path.abspath(__file__))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"[Scryptian] Failed to load {name}: {e}")
        return None


# ── UI ──
class ScryptianBar:
    def __init__(self, root, skills):
        self.root = root
        self.skills = skills
        self.filtered = list(skills)
        self.selected_index = 0
        self.window = None
        self.visible = False
        self.has_result = False
        self.last_result = ""
        self.processing = False
        self.pending_result = None
        self._has_add_item = False

    def toggle(self):
        """Show/hide the bar (called from any thread)."""
        self.root.after(0, self._do_toggle)

    def _do_toggle(self):
        """Toggle visibility (runs on tkinter main thread)."""
        if self.visible:
            self._hide()
        else:
            self._show()

    def _show(self):
        if self.window and self.visible:
            return

        # Hot-reload skills on every open
        self.skills = scan_skills()
        self.filtered = list(self.skills)

        self.window = tk.Toplevel(self.root)
        self.window.title("Scryptian")
        self.window.overrideredirect(True)
        self.window.configure(bg="#313244")

        # ── Size and center position ──
        bar_width = 560
        bar_height = 42
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - bar_width) // 2
        y = int(screen_h * 0.3)

        self.window.geometry(f"{bar_width}x{bar_height}+{x}+{y}")
        self.window.update_idletasks()

        # ── Border ──
        self.border = tk.Frame(self.window, bg="#45475a", padx=1, pady=1)
        self.border.pack(fill="both", expand=True)

        # ── Container ──
        self.container = tk.Frame(self.border, bg="#1e1e2e")
        self.container.pack(fill="both", expand=True)

        # ── Input field ──
        self.entry = tk.Entry(
            self.container,
            font=("Segoe UI", 13),
            bg="#1e1e2e",
            fg="#cdd6f4",
            disabledbackground="#1e1e2e",
            disabledforeground="#585b70",
            insertbackground="#cdd6f4",
            relief="flat",
            borderwidth=0,
        )
        self.entry.pack(fill="x", padx=12, pady=8)

        self.placeholder = tk.Label(
            self.container,
            text="Works with text from clipboard",
            font=("Segoe UI", 13),
            bg="#1e1e2e",
            fg="#585b70",
        )
        self.placeholder.place(x=14, y=8)
        self.placeholder.bind("<Button-1>", lambda e: self.entry.focus_set())

        self.entry.bind("<KeyRelease>", self._on_key)
        self.entry.bind("<Escape>", lambda e: self._hide())
        self.entry.bind("<Down>", self._select_next)
        self.entry.bind("<Up>", self._select_prev)

        self.window.bind("<Return>", self._on_enter)
        self.window.bind("<Escape>", lambda e: self._hide())

        # ── Result list (hidden until input) ──
        self.listbox = tk.Listbox(
            self.container,
            font=("Segoe UI", 11),
            bg="#1e1e2e",
            fg="#a6adc8",
            selectbackground="#45475a",
            selectforeground="#cdd6f4",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
        )

        # ── Response area (hidden until result) ──
        self.separator = tk.Frame(self.container, bg="#45475a", height=1)
        self.result_box = tk.Text(
            self.container,
            font=("Consolas", 11),
            bg="#1e1e2e",
            fg="#a6adc8",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            wrap="word",
            state="disabled",
        )
        self.skill_hint = tk.Label(
            self.container,
            text="Enter — run skill",
            font=("Segoe UI", 9),
            bg="#1e1e2e",
            fg="#585b70",
            anchor="e",
        )
        self.hint_label = tk.Label(
            self.container,
            text="Enter — copy to clipboard and close",
            font=("Segoe UI", 9),
            bg="#1e1e2e",
            fg="#585b70",
            anchor="e",
        )

        self.window.attributes("-topmost", True)
        self.window.update_idletasks()
        self.window.lift()

        self.visible = True
        self.selected_index = 0

        # If there's a pending result from a background task, show it
        if self.pending_result is not None:
            self.has_result = True
            self.last_result = self.pending_result
            self.pending_result = None
            self.processing = False
            self.listbox.pack_forget()
            self.entry.config(state="disabled")
            self._show_result(self.last_result)
        else:
            self.has_result = False
            self.last_result = ""
            self._update_filter("")

        self.window.after(50, self._force_focus)

    def _force_focus(self, attempt=0):
        """Force focus — Windows API on Win, fallback on Linux/Mac."""
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
        """Close only if focus left the window."""
        if not self.window:
            return
        try:
            focused = self.window.focus_get()
            if focused is None:
                self._hide()
        except KeyError:
            self._hide()

    def _hide(self):
        if self.window:
            self.visible = False
            self.window.destroy()
            self.window = None

    def _on_key(self, event):
        if event.keysym in ("Return", "Escape", "Up", "Down"):
            return
        query = self.entry.get()
        if query:
            self.placeholder.place_forget()
        else:
            self.placeholder.place(x=14, y=8)
        self._update_filter(query)

    def _update_filter(self, query):
        """Filters skills by input."""
        q = query.lower().strip()
        if q:
            self.filtered = [
                s for s in self.skills
                if q in s["title"].lower()
            ]
        else:
            self.filtered = list(self.skills)

        self._render_list()

    def _render_list(self):
        """Renders the dropdown list."""
        self.listbox.delete(0, tk.END)

        if not self.filtered:
            self.listbox.pack_forget()
            self.skill_hint.pack_forget()
            self._resize(42)
            return

        for p in self.filtered:
            self.listbox.insert(tk.END, f"  {p['title']}  —  {p['description']}")

        # "Add skill" shortcut — only when no filter is active
        self._has_add_item = False
        if not self.entry.get().strip():
            self.listbox.insert(tk.END, "  + Add your own skill...")
            self._has_add_item = True

        num_items = self.listbox.size()
        self.listbox.config(height=num_items)
        self.listbox.pack(fill="x", padx=6, pady=(0, 2))
        self.skill_hint.pack(fill="x", padx=12, pady=(0, 6))

        self.window.update_idletasks()
        needed = self.container.winfo_reqheight()
        self._resize(needed + 4)

        max_idx = len(self.filtered) - 1 + (1 if self._has_add_item else 0)
        self.selected_index = max(0, min(self.selected_index, max_idx))
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(self.selected_index)
        self.listbox.see(self.selected_index)

    def _resize(self, height):
        """Updates window height."""
        if not self.window:
            return
        geo = self.window.geometry()
        parts = geo.split("+")
        wh = parts[0].split("x")
        self.window.geometry(f"{wh[0]}x{height}+{parts[1]}+{parts[2]}")

    def _select_next(self, event):
        if self.filtered:
            max_idx = len(self.filtered) - 1 + (1 if self._has_add_item else 0)
            self.selected_index = min(self.selected_index + 1, max_idx)
            self._render_list()

    def _select_prev(self, event):
        if self.filtered:
            self.selected_index = max(self.selected_index - 1, 0)
            self._render_list()

    def _on_enter(self, event):
        """Runs the selected skill or copies the result."""
        if self.has_result:
            if self.last_result:
                pyperclip.copy(self.last_result)
                print("[Scryptian] Copied to clipboard.")
            self._hide()
            return

        if not self.filtered:
            return

        # "Add skill" item selected
        if self._has_add_item and self.selected_index >= len(self.filtered):
            self._open_skills_folder()
            self._hide()
            return

        skill = self.filtered[self.selected_index]

        # Get text from clipboard
        try:
            input_text = pyperclip.paste()
        except Exception:
            input_text = ""

        if not input_text.strip():
            self._show_result("Clipboard is empty.")
            return

        # Hide list, show status
        self.listbox.pack_forget()
        self.skill_hint.pack_forget()
        self.entry.config(state="disabled")
        self._show_result(f"⚙ {skill['title']}  —  processing...")

        self.processing = True
        print(f"[Scryptian] Running: {skill['title']}...")

        def execute():
            try:
                # Ensure model is ready (download/load if needed)
                if not bridge.is_model_ready():
                    def on_progress(msg):
                        self.root.after(0, lambda m=msg: self._show_result(m))
                    bridge._get_llm(on_progress=on_progress)

                mod = skill["module"]
                if hasattr(mod, "prompt"):
                    # Streaming mode
                    p = mod.prompt(input_text)
                    full_text = ""
                    for chunk in bridge.generate_stream(p):
                        full_text += chunk
                        text_snapshot = full_text
                        self.root.after(0, lambda t=text_snapshot: self._update_stream(t))
                    stripped = full_text.strip()
                    self.processing = False
                    if stripped and not stripped.startswith("[Scryptian Error]"):
                        if self.window and self.visible:
                            self.last_result = stripped
                            self.has_result = True
                            self.root.after(0, lambda: self._finish_stream())
                        else:
                            self.pending_result = stripped
                        telemetry.send("skill_run", {"name": skill["title"]})
                        print(f"[Scryptian] Done!")
                    elif stripped.startswith("[Scryptian Error]"):
                        self.root.after(0, lambda t=stripped: self._show_result(t))
                    else:
                        self.root.after(0, lambda: self._show_result("Skill returned an empty result."))
                else:
                    # Fallback: non-streaming
                    result = mod.run(input_text)
                    self.processing = False
                    if result and not result.startswith("[Scryptian Error]"):
                        if self.window and self.visible:
                            self.last_result = result
                            self.has_result = True
                            self.root.after(0, lambda: self._show_result(result))
                        else:
                            self.pending_result = result
                        telemetry.send("skill_run", {"name": skill["title"]})
                        print(f"[Scryptian] Done!")
                    elif result and result.startswith("[Scryptian Error]"):
                        self.root.after(0, lambda: self._show_result(result))
                    else:
                        self.root.after(0, lambda: self._show_result("Skill returned an empty result."))
            except Exception as e:
                self.root.after(0, lambda: self._show_result(f"Error: {e}"))

        threading.Thread(target=execute, daemon=True).start()

    def _update_stream(self, text):
        """Updates result box with streaming text in real-time."""
        if not self.window:
            return

        self.separator.pack_forget()
        self.result_box.pack_forget()
        self.hint_label.pack_forget()

        self.result_box.config(state="normal")
        self.result_box.delete("1.0", tk.END)
        self.result_box.insert("1.0", text)
        self.result_box.config(state="disabled")
        self.result_box.see(tk.END)

        chars_per_line = 60
        visual_lines = 0
        for line in text.split("\n"):
            visual_lines += max(1, (len(line) // chars_per_line) + 1)

        max_lines = 20
        clamped = min(visual_lines, max_lines)
        clamped = max(clamped, 2)

        self.separator.pack(fill="x", padx=8, pady=(4, 0))
        self.result_box.config(height=clamped)
        self.result_box.pack(fill="x", padx=10, pady=(4, 4))

        self.window.update_idletasks()
        needed = self.container.winfo_reqheight()
        self._resize(needed + 4)

    def _finish_stream(self):
        """Called when streaming is complete — shows hint label."""
        if not self.window:
            return
        self.hint_label.pack(fill="x", padx=12, pady=(0, 6))
        self.window.update_idletasks()
        needed = self.container.winfo_reqheight()
        self._resize(needed + 4)

    def _show_result(self, text):
        """Shows result below the bar, dynamically expanding the window."""
        if not self.window:
            return

        # Unpack everything before repacking
        self.separator.pack_forget()
        self.result_box.pack_forget()
        self.hint_label.pack_forget()

        # Update text
        self.result_box.config(state="normal")
        self.result_box.delete("1.0", tk.END)
        self.result_box.insert("1.0", text)
        self.result_box.config(state="disabled")

        # Height estimate: ~60 chars per line at width 560
        chars_per_line = 60
        visual_lines = 0
        for line in text.split("\n"):
            visual_lines += max(1, (len(line) // chars_per_line) + 1)

        max_lines = 20
        clamped = min(visual_lines, max_lines)
        clamped = max(clamped, 2)

        # Pack in correct order: separator → result → hint
        self.separator.pack(fill="x", padx=8, pady=(4, 0))
        self.result_box.config(height=clamped)
        self.result_box.pack(fill="x", padx=10, pady=(4, 4))

        if self.has_result:
            self.hint_label.pack(fill="x", padx=12, pady=(0, 6))

        self.window.update_idletasks()
        needed = self.container.winfo_reqheight()
        self._resize(needed + 4)


    def _open_skills_folder(self):
        """Open skills folder in file manager (cross-platform)."""
        import subprocess
        if IS_WINDOWS:
            os.startfile(SKILLS_DIR)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", SKILLS_DIR])
        else:
            subprocess.Popen(["xdg-open", SKILLS_DIR])


# ── Entry point ──
def main():
    print("[Scryptian] Scanning skills...")
    skills = scan_skills()

    if not skills:
        print("[Scryptian] No skills found in skills/ folder")
        return

    for s in skills:
        print(f"  → {s['title']}: {s['description']}")

    print(f"\n[Scryptian] Skills loaded: {len(skills)}")

    # Check model file
    from config import MODEL_PATH, MODEL_FILE
    if os.path.exists(MODEL_PATH):
        print(f"[Scryptian] Model: {MODEL_FILE}")
    else:
        print(f"[Scryptian] WARNING: Model not found. Run Run_Scryptian.bat to download it.")

    print(f"[Scryptian] Hotkey: {HOTKEY}")
    print("[Scryptian] Waiting...")

    telemetry.send("app_started", {"skills": len(skills)})

    # Hidden root tkinter window — keeps mainloop on the main thread
    root = tk.Tk()
    root.withdraw()

    bar = ScryptianBar(root, skills)

    keyboard.add_hotkey(HOTKEY, bar.toggle)

    if not autostart.is_enabled():
        autostart.enable()
        print("[Scryptian] Added to startup.")

    tray.start(on_quit=root.quit)

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
