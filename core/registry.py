# core/registry.py — Skill scanner and registry.
#
# Scans the skills/ folder and returns a list of skill dicts.
# Supports two formats:
#   - legacy: a single `<name>.py` file with `# @title:` header comments
#   - bundle: a folder with `manifest.json` + entry module + optional `libs/`

import os
import sys
import re
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


def _parse_metadata(filepath):
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
        "version": manifest.get("version", ""),
        "module": module,
        "filename": name,
        "needs_llm": bool(manifest.get("needs_llm", True)),
        "background": bool(manifest.get("background", False)),
        "settings": manifest.get("settings", []),
        "format": "bundle",
    }


def scan_skills():
    skills = []
    if not os.path.isdir(SKILLS_DIR):
        return skills

    for entry in sorted(os.listdir(SKILLS_DIR)):
        path = os.path.join(SKILLS_DIR, entry)

        if os.path.isdir(path):
            if entry.startswith("_") or entry == "libs":
                continue
            if os.path.exists(os.path.join(path, "manifest.json")):
                skill = _load_bundle(entry, path)
                if skill:
                    skills.append(skill)
            continue

        if not entry.endswith(".py") or entry.startswith("_"):
            continue

        meta = _parse_metadata(path)
        module = _load_module(entry, path)
        if module and hasattr(module, "run"):
            skills.append({
                "title": meta.get("title", entry.replace(".py", "")),
                "description": meta.get("description", ""),
                "author": meta.get("author", ""),
                "module": module,
                "filename": entry,
                "needs_llm": True,
                "format": "legacy",
            })
    return skills


def find_skill(skills, skill_id):
    for s in skills:
        if s.get("id") == skill_id or s.get("filename", "").replace(".py", "") == skill_id:
            return s
    return None
