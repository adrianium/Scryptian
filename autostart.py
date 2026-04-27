# autostart.py — Add/remove Scryptian from system startup

import sys
import os

IS_WINDOWS = sys.platform == "win32"


def _get_exe_path():
    """Get path to current executable (works for both .py and .exe)."""
    if getattr(sys, 'frozen', False):
        return sys.executable  # .exe mode (PyInstaller)
    return f'pythonw "{os.path.abspath("main.py")}"'


def enable():
    """Add Scryptian to startup."""
    if IS_WINDOWS:
        _enable_windows()
    elif sys.platform == "linux":
        _enable_linux()


def is_enabled():
    """Check if Scryptian is in startup."""
    if IS_WINDOWS:
        return _is_enabled_windows()
    return False


def _enable_windows():
    """Add to Windows startup via registry."""
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "Scryptian", 0, winreg.REG_SZ, _get_exe_path())
        winreg.CloseKey(key)
    except Exception:
        pass


def _is_enabled_windows():
    """Check if registry entry exists."""
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, "Scryptian")
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def _enable_linux():
    """Add .desktop file to autostart."""
    autostart_dir = os.path.expanduser("~/.config/autostart")
    os.makedirs(autostart_dir, exist_ok=True)
    desktop_file = os.path.join(autostart_dir, "scryptian.desktop")
    exe = _get_exe_path()
    with open(desktop_file, "w") as f:
        f.write(f"""[Desktop Entry]
Type=Application
Name=Scryptian
Exec={exe}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
""")
