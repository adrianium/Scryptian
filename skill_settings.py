# skill_settings.py — Standard per-skill settings dialog.
#
# A skill declares its settings in manifest.json under a "settings" list, e.g.:
#   "settings": [
#     {
#       "key": "lang",
#       "label": "Language",
#       "type": "select",
#       "default": "auto",
#       "options": [ {"value": "auto", "label": "Auto-detect"}, ... ]
#     }
#   ]
#
# Values are persisted via bridge state under the skill's id, in a reserved
# "settings" sub-dict, so they survive restarts and app updates and never clash
# with usage stats (count/last_used). Skills read them with:
#   bridge.get_state(<id>).get("settings", {}).get(<key>, <default>)

import tkinter as tk

import bridge

BG = "#1e1e2e"
BG2 = "#313244"
FG = "#cdd6f4"
FG_DIM = "#6c7086"
ACCENT = "#89b4fa"
FONT = ("Segoe UI", 10)
FONT_SM = ("Segoe UI", 9)


def _skill_id(skill):
    return skill.get("id") or skill.get("filename", "").replace(".py", "")


def has_settings(skill) -> bool:
    """True if the skill declares a non-empty settings schema."""
    return bool(skill.get("settings"))


def get_values(skill) -> dict:
    """Current settings for a skill: saved values merged over schema defaults."""
    spec = skill.get("settings", []) or []
    defaults = {f.get("key"): f.get("default") for f in spec if f.get("key")}
    try:
        saved = bridge.get_state(_skill_id(skill)).get("settings", {}) or {}
    except Exception:
        saved = {}
    defaults.update({k: v for k, v in saved.items() if k in defaults})
    return defaults


def open_settings(root, skill, on_saved=None):
    """Open a settings dialog rendered from the skill's manifest schema."""
    spec = skill.get("settings", []) or []
    if not spec:
        return

    current = get_values(skill)

    dlg = tk.Toplevel(root)
    dlg.title(f"{skill.get('title', 'Action')} — Settings")
    dlg.configure(bg=BG)
    dlg.resizable(False, False)
    dlg.attributes("-topmost", True)
    dlg.grab_set()

    tk.Label(dlg, text=f"\u2699  {skill.get('title', 'Action')} settings",
             bg=BG, fg=FG, font=("Segoe UI", 12, "bold"), anchor="w").pack(
        fill="x", padx=12, pady=(12, 4))

    vars_by_key = {}       # key -> tk.StringVar (holds the value, not the label)

    for field in spec:
        key = field.get("key")
        if not key:
            continue
        ftype = field.get("type", "select")
        label = field.get("label", key)

        tk.Label(dlg, text=label, bg=BG, fg=FG_DIM, font=FONT_SM,
                 anchor="w").pack(fill="x", padx=12, pady=(8, 0))

        cur_val = current.get(key, field.get("default"))

        if ftype == "select":
            options = field.get("options", []) or []
            value_to_label = {o.get("value"): o.get("label", o.get("value")) for o in options}
            label_to_value = {v: k for k, v in value_to_label.items()}

            var = tk.StringVar(value=value_to_label.get(cur_val, ""))
            vars_by_key[key] = (var, label_to_value)

            labels = [o.get("label", o.get("value")) for o in options]
            om = tk.OptionMenu(dlg, var, *labels) if labels else tk.OptionMenu(dlg, var, "")
            om.configure(bg=BG2, fg=FG, font=FONT, relief="flat",
                         highlightthickness=0, activebackground=ACCENT,
                         activeforeground=BG, anchor="w")
            om["menu"].configure(bg=BG2, fg=FG, activebackground=ACCENT,
                                 activeforeground=BG)
            om.pack(fill="x", padx=12, pady=2)
        else:
            # Fallback: free-text entry for unknown/text types.
            var = tk.StringVar(value="" if cur_val is None else str(cur_val))
            vars_by_key[key] = (var, None)
            tk.Entry(dlg, textvariable=var, bg=BG2, fg=FG, insertbackground=FG,
                     font=FONT, relief="flat", bd=4).pack(fill="x", padx=12, pady=2)

    def save():
        values = {}
        for key, (var, label_to_value) in vars_by_key.items():
            raw = var.get()
            values[key] = label_to_value.get(raw, raw) if label_to_value else raw
        try:
            bridge.set_state(_skill_id(skill), {"settings": values})
        except Exception:
            pass
        try:
            import telemetry
            telemetry.send("skill_settings_saved",
                           {"skill": skill.get("title", ""), **{f"set_{k}": v for k, v in values.items()}})
        except Exception:
            pass
        dlg.destroy()
        if on_saved:
            on_saved()

    btns = tk.Frame(dlg, bg=BG)
    btns.pack(fill="x", padx=12, pady=(12, 12))

    def _btn(text, cmd, fg=FG, bg=BG2):
        b = tk.Label(btns, text=text, bg=bg, fg=fg, font=FONT,
                     padx=10, pady=4, cursor="hand2")
        b.pack(side="left", padx=(0, 6))
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.config(bg=ACCENT, fg=BG))
        b.bind("<Leave>", lambda e: b.config(bg=bg, fg=fg))
        return b

    _btn("Save", save, fg=BG, bg=ACCENT)
    _btn("Cancel", dlg.destroy)

    dlg.update_idletasks()
    w, h = 360, dlg.winfo_reqheight()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    dlg.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
