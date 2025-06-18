import ctypes
from ctypes import wintypes
from typing import List, Dict

from ..core.dialog_parser_util import DialogProperties, DialogControlEntry, ATOM_TO_CLASSNAME_MAP

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WS_OVERLAPPEDWINDOW = 0x00CF0000
WS_VISIBLE = 0x10000000
WS_CHILD = 0x40000000
WS_CLIPSIBLINGS = 0x04000000
WS_CLIPCHILDREN = 0x02000000

MK_LBUTTON = 0x0001

CW_USEDEFAULT = 0x80000000
GWL_WNDPROC = -4

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, wintypes.UINT,
                              wintypes.WPARAM, wintypes.LPARAM)

class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG),
                ("y", wintypes.LONG)]

class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG)]

class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HCURSOR),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR)
    ]


class Win32DialogPreview:
    """Simple Win32 dialog preview using ctypes."""

    def __init__(self, dialog_props: DialogProperties,
                 controls: List[DialogControlEntry]):
        self.dialog_props = dialog_props
        self.controls = controls
        self.hInstance = kernel32.GetModuleHandleW(None)
        self.class_atom = None
        self.hwnd = None
        self.wnd_proc = None
        self.control_map: Dict[int, DialogControlEntry] = {}
        self.subclass_map: Dict[int, tuple] = {}
        self.drag_hwnd = None
        self.drag_start = POINT()
        self.drag_rect = RECT()
        self.resizing = False
        self.resize_start = POINT()

    def _wnd_proc(self, hwnd, msg, wParam, lParam):
        if msg == 0x0002:  # WM_DESTROY
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wParam, lParam)

    def register_class(self):
        wndclass = WNDCLASSW()
        self.wnd_proc = WNDPROC(self._wnd_proc)
        wndclass.lpfnWndProc = self.wnd_proc
        wndclass.lpszClassName = "PyREPreview"
        wndclass.hInstance = self.hInstance
        wndclass.hbrBackground = ctypes.c_void_p(6)  # COLOR_WINDOW + 1
        self.class_atom = user32.RegisterClassW(ctypes.byref(wndclass))

    def create_window(self):
        style = WS_OVERLAPPEDWINDOW | WS_VISIBLE
        width = max(self.dialog_props.width, 100) + 20
        height = max(self.dialog_props.height, 50) + 40
        self.hwnd = user32.CreateWindowExW(
            0,
            ctypes.cast(self.class_atom, wintypes.LPCWSTR),
            self.dialog_props.caption,
            style,
            CW_USEDEFAULT, CW_USEDEFAULT,
            width, height,
            None, None, self.hInstance, None)
        self.create_controls()

    def _subclass_control(self, hwnd):
        old_proc = user32.GetWindowLongPtrW(hwnd, GWL_WNDPROC)
        OldProcType = WNDPROC
        old_proc_func = OldProcType(old_proc)

        @WNDPROC
        def proc(h, msg, wp, lp):
            if msg == 0x0201:  # WM_LBUTTONDOWN
                self.drag_hwnd = h
                self.drag_start.x = ctypes.c_short(lp & 0xFFFF).value
                self.drag_start.y = ctypes.c_short((lp >> 16) & 0xFFFF).value
                user32.GetWindowRect(h, ctypes.byref(self.drag_rect))
                parent = user32.GetParent(h)
                user32.ScreenToClient(parent, ctypes.byref(self.drag_rect))
                shift = user32.GetKeyState(0x10) & 0x8000
                self.resizing = bool(shift)
                self.resize_start.x = self.drag_start.x
                self.resize_start.y = self.drag_start.y
                user32.SetCapture(h)
                return 0
            elif msg == 0x0200 and self.drag_hwnd == h and wp & MK_LBUTTON:
                dx = ctypes.c_short(lp & 0xFFFF).value - self.drag_start.x
                dy = ctypes.c_short((lp >> 16) & 0xFFFF).value - self.drag_start.y
                if self.resizing:
                    new_w = max(10, self.drag_rect.right - self.drag_rect.left + dx)
                    new_h = max(10, self.drag_rect.bottom - self.drag_rect.top + dy)
                    user32.MoveWindow(h, self.drag_rect.left, self.drag_rect.top, new_w, new_h, True)
                else:
                    new_x = self.drag_rect.left + dx
                    new_y = self.drag_rect.top + dy
                    w = self.drag_rect.right - self.drag_rect.left
                    hgt = self.drag_rect.bottom - self.drag_rect.top
                    user32.MoveWindow(h, new_x, new_y, w, hgt, True)
                return 0
            elif msg == 0x0202 and self.drag_hwnd == h:
                user32.ReleaseCapture()
                rect = RECT()
                user32.GetWindowRect(h, ctypes.byref(rect))
                parent = user32.GetParent(h)
                user32.ScreenToClient(parent, ctypes.byref(rect))
                entry = self.control_map.get(h)
                if entry:
                    entry.x = rect.left
                    entry.y = rect.top
                    entry.width = rect.right - rect.left
                    entry.height = rect.bottom - rect.top
                self.drag_hwnd = None
                self.resizing = False
                return 0
            return user32.CallWindowProcW(old_proc, h, msg, wp, lp)

        user32.SetWindowLongPtrW(hwnd, GWL_WNDPROC, proc)
        self.subclass_map[hwnd] = (old_proc, proc)

    def create_controls(self):
        for idx, ctrl in enumerate(self.controls):
            cn = ctrl.class_name
            if isinstance(cn, int):
                cn = ATOM_TO_CLASSNAME_MAP.get(cn, "STATIC")
            hwnd_ctrl = user32.CreateWindowExW(
                0,
                cn,
                ctrl.text,
                WS_CHILD | WS_VISIBLE | ctrl.style,
                ctrl.x, ctrl.y, ctrl.width, ctrl.height,
                self.hwnd,
                ctypes.c_void_p(idx + 1),
                self.hInstance,
                None)
            self.control_map[hwnd_ctrl] = ctrl
            self._subclass_control(hwnd_ctrl)

    def show(self):
        self.register_class()
        self.create_window()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        self.cleanup()

    def cleanup(self):
        for hwnd, (old_proc, _) in self.subclass_map.items():
            user32.SetWindowLongPtrW(hwnd, GWL_WNDPROC, old_proc)
        if self.class_atom:
            user32.UnregisterClassW(ctypes.cast(self.class_atom, wintypes.LPCWSTR), self.hInstance)

