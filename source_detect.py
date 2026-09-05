# source_detect.py — Reliable source-window + site detection (ctypes only, no deps).
#
# Detects the app/window that was active before Scryptian opened, and for
# browsers reads the real URL from the address bar via Windows UI Automation,
# then extracts only the domain. No site keyword list, no raw titles sent.

import os
import sys
import ctypes
from ctypes import wintypes
from urllib.parse import urlparse

IS_WINDOWS = sys.platform == "win32"

# ── WinAPI helpers ──────────────────────────────────────────────

def _get_exe(hwnd):
    """Return the lowercase exe name of the process owning hwnd, or ''."""
    try:
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        if pid.value == ctypes.windll.kernel32.GetCurrentProcessId():
            return ""
        h = ctypes.windll.kernel32.OpenProcess(0x0410, False, pid.value)
        if not h:
            return ""
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.psapi.GetModuleFileNameExW(h, None, buf, 260)
        ctypes.windll.kernel32.CloseHandle(h)
        return os.path.basename(buf.value).lower()
    except Exception:
        return ""


def get_source_window():
    """Return the top-level HWND that had focus before Scryptian opened.

    Uses GetGUIThreadInfo -> hwndFocus -> GetAncestor(GA_ROOT), which follows
    the real focus instead of relying only on GetForegroundWindow().
    """
    if not IS_WINDOWS:
        return None
    try:
        fg = ctypes.windll.user32.GetForegroundWindow()
        if not fg:
            return None
        class GTI(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("hwndActive", wintypes.HWND),
                ("hwndFocus", wintypes.HWND),
                ("hwndCapture", wintypes.HWND),
                ("hwndMenuOwner", wintypes.HWND),
                ("hwndMoveSize", wintypes.HWND),
                ("hwndCaret", wintypes.HWND),
                ("rcCaret", wintypes.RECT),
            ]
        gti = GTI()
        gti.cbSize = ctypes.sizeof(GTI)
        tid = ctypes.windll.user32.GetWindowThreadProcessId(fg, None)
        if tid and ctypes.windll.user32.GetGUIThreadInfo(tid, ctypes.byref(gti)):
            if gti.hwndFocus:
                root = ctypes.windll.user32.GetAncestor(gti.hwndFocus, 2)  # GA_ROOT
                if root:
                    return root
        return fg
    except Exception:
        return None


# ── UI Automation (ctypes COM) ──────────────────────────────────

_UIA_ControlTypePropertyId = 30003
_UIA_ValueValuePropertyId = 30045
_UIA_EditControlTypeId = 50004
_TreeScope_Descendants = 4
_VT_I4 = 3
_VT_BSTR = 8


def _guid(s):
    import uuid
    u = uuid.UUID(s)
    return (ctypes.c_ubyte * 16)(
        *u.bytes_le
    )


class _VARIANT_UNION(ctypes.Union):
    _fields_ = [
        ("lVal", ctypes.c_long),
        ("bstrVal", ctypes.c_void_p),
        ("punkVal", ctypes.c_void_p),
        ("_pad", ctypes.c_ubyte * 16),  # keep union 16 bytes (DECIMAL-sized)
    ]


class VARIANT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("wReserved1", ctypes.c_ushort),
        ("wReserved2", ctypes.c_ushort),
        ("wReserved3", ctypes.c_ushort),
        ("u", _VARIANT_UNION),
    ]


def _variant_i4(v):
    var = VARIANT()
    var.vt = _VT_I4
    var.lVal = v
    return var


# Function pointer types (stdcall). On 64-bit the calling convention is unified.
_HRESULT = ctypes.c_long

_ElementFromHandle = ctypes.WINFUNCTYPE(
    _HRESULT, ctypes.c_void_p, wintypes.HWND, ctypes.POINTER(ctypes.c_void_p))
_CreatePropertyCondition = ctypes.WINFUNCTYPE(
    _HRESULT, ctypes.c_void_p, ctypes.c_int, VARIANT, ctypes.POINTER(ctypes.c_void_p))
_FindFirst = ctypes.WINFUNCTYPE(
    _HRESULT, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
_GetCurrentPropertyValue = ctypes.WINFUNCTYPE(
    _HRESULT, ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(VARIANT))


def _vtbl(ptr):
    """Dereference a COM object pointer to its vtable array."""
    lp = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_void_p))[0]
    return ctypes.cast(lp, ctypes.POINTER(ctypes.c_void_p))


def _read_url(hwnd):
    """Read the browser address-bar URL via UIA. Returns '' on any failure."""
    ole32 = ctypes.windll.ole32
    oleaut32 = ctypes.windll.oleaut32
    oleaut32.SysFreeString.argtypes = [ctypes.c_void_p]
    need_uninit = False
    try:
        # S_OK (0) means we initialized COM; S_FALSE (1) means it was already
        # initialized on this thread. Only uninitialize when we did the init.
        hr = ole32.CoInitializeEx(None, 2)  # COINIT_APARTMENTTHREADED
        if hr < 0:
            return ""
        need_uninit = (hr == 0)

        clsid = _guid("ff48dba4-60ef-4201-aa87-54103eef594e")
        iid = _guid("30cbe57d-d9d0-452a-ab13-7ac5ac4825ee")

        pAuto = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(
            ctypes.byref(clsid), None, 1,  # CLSCTX_INPROC_SERVER
            ctypes.byref(iid), ctypes.byref(pAuto),
        )
        if hr != 0 or not pAuto.value:
            return ""

        vtbl = _vtbl(pAuto.value)

        # ElementFromHandle (vtable index 6)
        pRoot = ctypes.c_void_p()
        fn = _ElementFromHandle(vtbl[6])
        hr = fn(pAuto.value, hwnd, ctypes.byref(pRoot))
        if hr != 0 or not pRoot.value:
            return ""

        # CreatePropertyCondition(ControlType == Edit) (vtable index 23)
        pCond = ctypes.c_void_p()
        fn = _CreatePropertyCondition(vtbl[23])
        hr = fn(pAuto.value, _UIA_ControlTypePropertyId,
                _variant_i4(_UIA_EditControlTypeId), ctypes.byref(pCond))
        if hr != 0 or not pCond.value:
            return ""

        # FindFirst(Descendants, cond) (element vtable index 5)
        evtbl = _vtbl(pRoot.value)
        pEdit = ctypes.c_void_p()
        fn = _FindFirst(evtbl[5])
        hr = fn(pRoot.value, _TreeScope_Descendants, pCond.value, ctypes.byref(pEdit))
        if hr != 0 or not pEdit.value:
            return ""

        # GetCurrentPropertyValue(Value) (element vtable index 10)
        var = VARIANT()
        fn = _GetCurrentPropertyValue(evtbl[10])
        hr = fn(pEdit.value, _UIA_ValueValuePropertyId, ctypes.byref(var))
        if hr != 0:
            return ""

        url = ""
        if var.vt == _VT_BSTR and var.bstrVal:
            url = ctypes.cast(var.bstrVal, ctypes.c_wchar_p).value or ""
            oleaut32.SysFreeString(var.bstrVal)

        return url or ""
    except Exception:
        return ""
    finally:
        if need_uninit:
            try:
                ole32.CoUninitialize()
            except Exception:
                pass


def _domain(url):
    """Extract a clean domain from a URL, or '' if not a URL."""
    try:
        url = (url or "").strip()
        if not url:
            return ""
        # Chrome's omnibox omits the scheme ("gemini.google.com/..."), so
        # prepend "//" so urlparse sees a netloc.
        if "://" not in url:
            url = "//" + url
        u = urlparse(url)
        netloc = (u.netloc or "").lower()
        if not netloc:
            return ""
        # strip userinfo, port and leading 'www.'
        host = netloc.split("@")[-1].split(":")[0]
        if host.startswith("www."):
            host = host[4:]
        # a real domain has at least one dot; filters out search queries
        if "." not in host:
            return ""
        return host
    except Exception:
        return ""


def get_source_info(hwnd):
    """Return {"source_app": exe, "source_site": domain} for the source window.

    source_site is only set for browsers and is the real domain (e.g.
    "youtube.com"), read from the address bar. No keyword list, no raw titles.
    """
    result = {"source_app": "unknown"}
    if not IS_WINDOWS or not hwnd:
        return result
    exe = _get_exe(hwnd)
    if not exe:
        return result
    result["source_app"] = exe

    if exe in ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
               "opera.exe", "opera_gx.exe", "vivaldi.exe", "arc.exe"):
        url = _read_url(hwnd)
        dom = _domain(url)
        if dom:
            result["source_site"] = dom
    return result
