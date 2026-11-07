from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002

NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010

NIIF_INFO = 0x00000001
IDI_INFORMATION = 32516
TRAY_UID = 0xE7E5


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class _NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", _GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


class WindowsNotifier:
    """Small Win32 tray notification helper that works while minimized.

    It deliberately uses Shell_NotifyIcon instead of an in-window overlay so
    reminders remain visible when the pygame window is minimized.
    """

    def __init__(self) -> None:
        self.available = False
        self._hwnd = 0
        self._added = False
        self._icon = None
        self._shell32 = None
        if sys.platform != "win32":
            return
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            shell32 = ctypes.WinDLL("shell32", use_last_error=True)
            user32.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
            user32.LoadIconW.restype = wintypes.HICON
            shell32.Shell_NotifyIconW.argtypes = [
                wintypes.DWORD,
                ctypes.POINTER(_NOTIFYICONDATAW),
            ]
            shell32.Shell_NotifyIconW.restype = wintypes.BOOL
            self._icon = user32.LoadIconW(None, IDI_INFORMATION)
            self._shell32 = shell32
            self.available = True
        except (OSError, AttributeError):
            self.available = False

    def set_window(self, hwnd: int) -> None:
        hwnd = int(hwnd or 0)
        if self._hwnd == hwnd:
            return
        if self._added and self._hwnd:
            self.remove()
        self._hwnd = hwnd

    def _base(self) -> _NOTIFYICONDATAW:
        data = _NOTIFYICONDATAW()
        data.cbSize = ctypes.sizeof(_NOTIFYICONDATAW)
        data.hWnd = self._hwnd
        data.uID = TRAY_UID
        data.hIcon = self._icon
        data.szTip = "EyesTrainer"
        data.uTimeoutOrVersion = 10000
        return data

    def _add_icon(self) -> bool:
        if not self.available or not self._hwnd or self._shell32 is None:
            return False
        data = self._base()
        data.uFlags = NIF_ICON | NIF_TIP | NIF_MESSAGE
        data.uCallbackMessage = 0x8000
        if self._shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(data)):
            self._added = True
            return True
        return False

    def notify(self, hwnd: int, title: str, message: str) -> bool:
        if not self.available or self._shell32 is None:
            return False
        self.set_window(hwnd)
        if not self._added and not self._add_icon():
            return False
        data = self._base()
        data.uFlags = NIF_INFO | NIF_ICON | NIF_TIP
        data.szInfoTitle = str(title)[:63]
        data.szInfo = str(message)[:255]
        data.dwInfoFlags = NIIF_INFO
        return bool(self._shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(data)))

    def remove(self) -> None:
        if not self.available or not self._added or not self._hwnd:
            return
        if self._shell32 is not None:
            data = self._base()
            self._shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(data))
        self._added = False
