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
