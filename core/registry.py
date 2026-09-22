# core/registry.py — Skill scanner and registry.
#
# Scans the skills/ folder and returns a list of skill dicts.
# Every skill is a bundle: a folder with `manifest.json` + entry module + optional `libs/`.

import os
import sys
import importlib.util

from config import APP_VERSION, BASE_DIR

SKILLS_DIR = os.path.join(BASE_DIR, "skills")


def _version_tuple(v):
    try:
        return tuple(int(x) for x in str(v).strip().split("."))
    except Exception:
        return (0,)


def _version_ge(a, b):
    ta, tb = _version_tuple(a), _version_tuple(b)
    length = max(len(ta), len(tb))
    ta += (0,) * (length - len(ta))
    tb += (0,) * (length - len(tb))
    return ta >= tb


def _safe_int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return 0


def _ext_list(v):
    if isinstance(v, list):
        return [str(x).strip().lower() for x in v if str(x).strip()]
    if isinstance(v, str) and v.strip():
        return [v.strip().lower()]
    return []


def _load_module(name, filepath):
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


def _load_bundle(name, bundle_dir):
    import json
    try:
        with open(os.path.join(bundle_dir, "manifest.json"), "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        print(f"[Scryptian] Bad manifest in bundle '{name}': {e}")
        return None

    min_ver = manifest.get("min_app_version")
    if min_ver and not _version_ge(APP_VERSION, min_ver):
        print(f"[Scryptian] Skipping '{name}': needs app >= {min_ver} (current {APP_VERSION}).")
        return None

    libs_dir = os.path.join(bundle_dir, "libs")
    if os.path.isdir(libs_dir) and libs_dir not in sys.path:
        sys.path.insert(0, libs_dir)

    entry = manifest.get("entry", "skill.py")
    entry_path = os.path.join(bundle_dir, entry)
    if not os.path.exists(entry_path):
        print(f"[Scryptian] Bundle '{name}' entry '{entry}' not found.")
        return None

    module = _load_module(f"{name}_{entry}", entry_path)
    if not module or not hasattr(module, "run"):
        print(f"[Scryptian] Bundle '{name}' has no run().")
        return None

    return {
        "id": manifest.get("id", name),
        "title": manifest.get("title", name),
        "description": manifest.get("description", ""),
        "author": manifest.get("author", ""),
        "author_id": manifest.get("author_id", ""),
        "price": _safe_int(manifest.get("price", 0)),
        "unit": manifest.get("unit", ""),
        "price_per_unit": _safe_int(manifest.get("price_per_unit", 0)),
        "version": manifest.get("version", ""),
        "module": module,
        "filename": name,
        "mode": manifest.get("mode", "cloud").strip().lower(),
        "background": bool(manifest.get("background", False)),
        "settings": manifest.get("settings", []),
        "input_type": _ext_list(manifest.get("input_type", "")),
        "output_type": _ext_list(manifest.get("output_type", "")),
        "format": "bundle",
        "_dir": bundle_dir,
    }


def scan_skills():
    skills = []
    if not os.path.isdir(SKILLS_DIR):
        return skills

    for entry in sorted(os.listdir(SKILLS_DIR)):
        path = os.path.join(SKILLS_DIR, entry)

        if not os.path.isdir(path):
            continue
        if entry.startswith("_") or entry == "libs":
            continue
        if os.path.exists(os.path.join(path, "manifest.json")):
            skill = _load_bundle(entry, path)
            if skill:
                skills.append(skill)
    return skills


def find_skill(skills, skill_id):
    for s in skills:
        if s.get("id") == skill_id or s.get("filename", "").replace(".py", "") == skill_id:
            return s
    return None
