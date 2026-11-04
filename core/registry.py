# core/registry.py — Skill scanner and registry.
#
# Scans the skills/ folder and returns a list of skill dicts.
# Every skill is a bundle: a folder with `manifest.json` + entry module + optional `libs/`.

import json
import os
import sys
import importlib.util
from urllib.parse import urlparse

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


def _load_hosts(manifest, bundle_dir):
    """Host list for a link skill. A hosts_file is shared by several skills."""
    raw = manifest.get("hosts")
    if isinstance(raw, list):
        return [str(item).strip().lower().lstrip(".") for item in raw if str(item).strip()]
    ref = manifest.get("hosts_file")
    if not isinstance(ref, str) or not ref.strip():
        return []
    path = os.path.normpath(os.path.join(bundle_dir, ref.strip()))
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return []
    items = data.get("hosts") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    return [str(item).strip().lower().lstrip(".") for item in items if str(item).strip()]


def claims_link(skill, url):
    """True when this link skill asked to pop up for the URL's site."""
    if "link" not in (skill.get("input_type") or []):
        return False
    hosts = skill.get("hosts") or []
    if not hosts:
        return False
    try:
        host = (urlparse(url).hostname or "").lower().rstrip(".")
    except Exception:
        return False
    if host.startswith("www."):
        host = host[4:]
    for item in hosts:
        name = item[4:] if item.startswith("www.") else item
        if host == name or host.endswith("." + name):
            return True
    return False


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
        print(f"[nespatch] Failed to load {name}: {e}")
        return None


def _load_bundle(name, bundle_dir):
    import json
    try:
        with open(os.path.join(bundle_dir, "manifest.json"), "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        print(f"[nespatch] Bad manifest in bundle '{name}': {e}")
        return None

    min_ver = manifest.get("min_app_version")
    if min_ver and not _version_ge(APP_VERSION, min_ver):
        print(f"[nespatch] Skipping '{name}': needs app >= {min_ver} (current {APP_VERSION}).")
        return None

    libs_dir = os.path.join(bundle_dir, "libs")
    if os.path.isdir(libs_dir) and libs_dir not in sys.path:
        sys.path.insert(0, libs_dir)

    entry = manifest.get("entry", "skill.py")
    entry_path = os.path.join(bundle_dir, entry)
    if not os.path.exists(entry_path):
        print(f"[nespatch] Bundle '{name}' entry '{entry}' not found.")
        return None

    module = _load_module(f"{name}_{entry}", entry_path)
    if not module or not hasattr(module, "run"):
        print(f"[nespatch] Bundle '{name}' has no run().")
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
        "hosts": _load_hosts(manifest, bundle_dir),
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
