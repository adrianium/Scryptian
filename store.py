# store.py — Online skill store: fetches registry.json from GitHub and installs skills locally.

import os
import io
import json
import ssl
import zipfile
from urllib import request

REGISTRY_URL = "https://raw.githubusercontent.com/adrianium/Scryptian/refs/heads/main/store/registry.json"
SKILL_BASE_URL = "https://raw.githubusercontent.com/adrianium/Scryptian/refs/heads/main/store/skills/"


def _ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def fetch_registry(timeout=10):
    """Fetch registry.json from GitHub. Returns list of skill dicts."""
    resp = request.urlopen(REGISTRY_URL, timeout=timeout, context=_ssl_ctx())
    data = json.loads(resp.read())
    return data.get("skills", [])


def _bundle_dir_name(skill):
    """Folder name a bundle installs into."""
    name = skill.get("filename", "")
    return name[:-4] if name.endswith(".zip") else name


def is_installed(skill, skills_dir):
    """skill is a registry dict. Handles both single-file and bundle skills."""
    if skill.get("type") == "bundle":
        return os.path.isdir(os.path.join(skills_dir, _bundle_dir_name(skill)))
    return os.path.exists(os.path.join(skills_dir, skill.get("filename", "")))


def _version_tuple(v):
    """Parse a dotted version string into a comparable tuple. Bad input -> (0,)."""
    try:
        return tuple(int(x) for x in str(v).strip().split("."))
    except Exception:
        return (0,)


def installed_version(skill, skills_dir):
    """Return the locally installed version of a bundle skill, or None.

    Single-file skills carry no version metadata, so this only applies to
    bundles (which have a manifest.json).
    """
    if skill.get("type") != "bundle":
        return None
    manifest_path = os.path.join(skills_dir, _bundle_dir_name(skill), "manifest.json")
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f).get("version")
    except Exception:
        return None


def has_update(skill, skills_dir):
    """True if the skill is installed but the registry offers a newer version."""
    if not is_installed(skill, skills_dir):
        return False
    registry_ver = skill.get("version")
    local_ver = installed_version(skill, skills_dir)
    if not registry_ver or not local_ver:
        return False
    return _version_tuple(registry_ver) > _version_tuple(local_ver)


def install_skill(skill, skills_dir):
    """Download and install a skill. Returns the installed path."""
    os.makedirs(skills_dir, exist_ok=True)

    if skill.get("type") == "bundle":
        archive = skill.get("archive") or (_bundle_dir_name(skill) + ".zip")
        url = SKILL_BASE_URL + archive
        resp = request.urlopen(url, timeout=30, context=_ssl_ctx())
        data = resp.read()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(skills_dir)
        return os.path.join(skills_dir, _bundle_dir_name(skill))

    filename = skill.get("filename", "")
    url = SKILL_BASE_URL + filename
    resp = request.urlopen(url, timeout=15, context=_ssl_ctx())
    content = resp.read()
    path = os.path.join(skills_dir, filename)
    with open(path, "wb") as f:
        f.write(content)
    return path
