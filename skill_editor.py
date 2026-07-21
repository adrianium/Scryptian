# skill_editor.py — Create/edit/delete custom skills via UI dialog
import os
import re
import tkinter as tk
from tkinter import messagebox

BG = "#1e1e2e"
BG2 = "#313244"
FG = "#cdd6f4"
FG_DIM = "#6c7086"
ACCENT = "#89b4fa"
FONT = ("Segoe UI", 10)
FONT_SM = ("Segoe UI", 9)

_TEMPLATE = '''\
# @title: {title}
# @description: {description}
# @author: custom

import bridge

def run(text):
    prompt = """{prompt}"""
    return bridge.generate(prompt.format(text=text))
'''


def _slug(title):
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return f"custom_{slug}.py"


def open_editor(root, skills_dir, on_saved=None, skill=None):
    """
    Open create/edit dialog.
    skill: existing skill dict (edit mode) or None (create mode).
    on_saved: callback() called after save.
    """
    dlg = tk.Toplevel(root)
    dlg.title("Edit Action" if skill else "New Action")
    dlg.configure(bg=BG)
    dlg.resizable(False, False)
    dlg.attributes("-topmost", True)
    dlg.grab_set()

    pad = {"padx": 12, "pady": 4}

    def label(text):
        tk.Label(dlg, text=text, bg=BG, fg=FG_DIM, font=FONT_SM, anchor="w").pack(
            fill="x", padx=12, pady=(8, 0)
        )

    # Title
    label("Title")
    title_var = tk.StringVar()
    title_entry = tk.Entry(dlg, textvariable=title_var, bg=BG2, fg=FG,
                           insertbackground=FG, font=FONT, relief="flat", bd=4)
    title_entry.pack(fill="x", **pad)

    # Description
    label("Description  (optional)")
    desc_var = tk.StringVar()
    desc_entry = tk.Entry(dlg, textvariable=desc_var, bg=BG2, fg=FG,
                          insertbackground=FG, font=FONT, relief="flat", bd=4)
    desc_entry.pack(fill="x", **pad)

    # Instructions
    label("What should the AI do with the selected text?")
    PLACEHOLDER = "e.g. extract all numbers"
    prompt_box = tk.Text(dlg, bg=BG2, fg=FG_DIM, insertbackground=FG,
                         font=FONT, relief="flat", bd=4,
                         height=5, wrap="word", undo=True)
    prompt_box.insert("1.0", PLACEHOLDER)
    prompt_box.pack(fill="x", **pad)

    def _on_focus_in(e):
        if prompt_box.get("1.0", "end-1c") == PLACEHOLDER:
            prompt_box.delete("1.0", "end")
            prompt_box.config(fg=FG)

    def _on_focus_out(e):
        if not prompt_box.get("1.0", "end-1c").strip():
            prompt_box.insert("1.0", PLACEHOLDER)
            prompt_box.config(fg=FG_DIM)

    prompt_box.bind("<FocusIn>", _on_focus_in)
    prompt_box.bind("<FocusOut>", _on_focus_out)

    # Pre-fill in edit mode
    if skill:
        title_var.set(skill.get("title", ""))
        desc_var.set(skill.get("description", ""))
        # Read prompt from file
        fpath = os.path.join(skills_dir, skill.get("filename", ""))
        if os.path.exists(fpath):
            src = open(fpath, encoding="utf-8").read()
            m = re.search(r'prompt\s*=\s*"""(.*?)"""', src, re.DOTALL)
            if m:
                raw = m.group(1).strip()
                # Remove trailing \n{text} placeholder if present
                raw = re.sub(r"\n\n\{text\}$", "", raw).strip()
                prompt_box.insert("1.0", raw)

    # Buttons
    btn_frame = tk.Frame(dlg, bg=BG)
    btn_frame.pack(fill="x", padx=12, pady=(8, 12))

    def _btn(parent, text, cmd, fg=FG, bg=BG2):
        b = tk.Label(parent, text=text, bg=bg, fg=fg, font=FONT,
                     padx=10, pady=4, cursor="hand2")
        b.pack(side="left", padx=(0, 6))
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.config(bg=ACCENT, fg=BG))
        b.bind("<Leave>", lambda e: b.config(bg=bg, fg=fg))
        return b

    def save():
        title = title_var.get().strip()
        desc = desc_var.get().strip()
        prompt = prompt_box.get("1.0", "end-1c").strip()
        if prompt == PLACEHOLDER:
            prompt = ""

        if not title:
            messagebox.showwarning("Missing title", "Please enter an action title.", parent=dlg)
            return
        if not prompt:
            messagebox.showwarning("Missing instructions", "Please enter instructions.", parent=dlg)
            return

        # If {text} not in prompt, append it automatically
        if "{text}" not in prompt:
            prompt_with_var = prompt + "\n\n{text}"
        else:
            prompt_with_var = prompt

        code = _TEMPLATE.format(
            title=title,
            description=desc or title,
            prompt=prompt_with_var,
        )

        filename = _slug(title)
        fpath = os.path.join(skills_dir, filename)

        # If editing and filename changed, remove old file
        if skill and skill.get("filename") and skill["filename"] != filename:
            old = os.path.join(skills_dir, skill["filename"])
            if os.path.exists(old):
                os.remove(old)

        with open(fpath, "w", encoding="utf-8") as f:
            f.write(code)

        try:
            import telemetry
            event = "skill_edited" if skill else "skill_created"
            telemetry.send(event, {"title": title})
        except Exception:
            pass

        dlg.destroy()
        if on_saved:
            on_saved()

    def delete():
        if not skill:
            return
        if messagebox.askyesno("Delete action",
                               f"Delete '{skill['title']}'?", parent=dlg):
            fpath = os.path.join(skills_dir, skill.get("filename", ""))
            if os.path.exists(fpath):
                os.remove(fpath)
            try:
                import telemetry
                telemetry.send("skill_deleted", {"title": skill.get("title", "")})
            except Exception:
                pass
            dlg.destroy()
            if on_saved:
                on_saved()

    def open_folder():
        import subprocess
        subprocess.Popen(f'explorer "{skills_dir}"')

    _btn(btn_frame, "Save", save, fg=BG, bg=ACCENT)
    _btn(btn_frame, "Cancel", dlg.destroy)
    if skill:
        _btn(btn_frame, "Delete", delete, fg="#f38ba8", bg=BG2)
    _btn(btn_frame, "Open folder", open_folder, fg=FG_DIM, bg=BG)

    # Size and center
    dlg.update_idletasks()
    w, h = 420, dlg.winfo_reqheight()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    dlg.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
    title_entry.focus_set()
