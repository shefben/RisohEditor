import ctypes
from ctypes import wintypes

# Load kernel32.dll and user32.dll
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)

# Define constants often used with these functions if not already in wintypes
INVALID_HANDLE_VALUE = wintypes.HANDLE(0)
LPVOID = ctypes.c_void_p
wintypes.INT_PTR = ctypes.c_ssize_t # For pointer-sized integers, suitable for INT_PTR

# --- Constants ---
# Window Messages
WM_INITDIALOG = 0x0110
WM_COMMAND = 0x0111
WM_CLOSE = 0x0010 # Already defined
WM_DESTROY = 0x0002 # Added

# GetWindowLong/SetWindowLong Indeces
GWL_STYLE = -16
GWL_EXSTYLE = -20

# Window Styles
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000 # Already defined
WS_POPUP = 0x80000000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_THICKFRAME = 0x00040000
CS_HREDRAW = 0x0002 # Added
CS_VREDRAW = 0x0001 # Added
WS_OVERLAPPEDWINDOW = 0x00CF0000 # Added
CW_USEDEFAULT = 0x80000000 # Added (Note: This is an int, not a pointer)

# Dialog Specific Styles
DS_CONTROL = 0x0400
SW_SHOW = 5

# SetWindowPos Flags
SWP_FRAMECHANGED = 0x0020
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010

# GDI constants
BI_RGB = 0
DIB_RGB_COLORS = 0

# LoadImage/CreateIconFromResourceEx flags
LR_DEFAULTCOLOR = 0x00000000
LR_MONOCHROME = 0x00000001
LR_LOADFROMFILE = 0x00000010
LR_SHARED = 0x00008000

# Image types (for LoadImage)
IMAGE_BITMAP = 0
IMAGE_ICON = 1
IMAGE_CURSOR = 2

# Cursor IDs (for LoadCursorW)
IDC_ARROW = 32512

# Icon IDs (for LoadIconW)
IDI_APPLICATION = 32512

# System Colors
COLOR_WINDOW = 5 # Added

# Error Codes
ERROR_CLASS_ALREADY_EXISTS = 1410 # Added


# --- Structures ---
class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG)]

class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wintypes.BOOL),
                ("xHotspot", wintypes.DWORD),
                ("yHotspot", wintypes.DWORD),
                ("hbmMask", wintypes.HBITMAP),
                ("hbmColor", wintypes.HBITMAP)]

class BITMAP(ctypes.Structure):
    _fields_ = [("bmType", wintypes.LONG),
                ("bmWidth", wintypes.LONG),
                ("bmHeight", wintypes.LONG),
                ("bmWidthBytes", wintypes.LONG),
                ("bmPlanes", wintypes.WORD),
                ("bmBitsPixel", wintypes.WORD),
                ("bmBits", LPVOID)]

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD),
                ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]

class RGBQUAD(ctypes.Structure):
    _fields_ = [("rgbBlue", wintypes.BYTE),
                ("rgbGreen", wintypes.BYTE),
                ("rgbRed", wintypes.BYTE),
                ("rgbReserved", wintypes.BYTE)]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER),
                ("bmiColors", RGBQUAD * 1)]

# Window Procedure and Dialog Procedure types
WNDPROC = ctypes.WINFUNCTYPE(wintypes.INT_PTR, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM) # Changed to INT_PTR
DLGPROC = ctypes.WINFUNCTYPE(wintypes.INT_PTR, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

class WNDCLASSEXW(ctypes.Structure): # Added
    _fields_ = [("cbSize", wintypes.UINT),
                ("style", wintypes.UINT),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HCURSOR),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
                ("hIconSm", wintypes.HICON)]


# Helper function to create resource strings (LPWSTR) for integer IDs
def MAKEINTRESOURCE(value: int) -> wintypes.LPWSTR:
    return ctypes.cast(wintypes.HANDLE(value), wintypes.LPWSTR)

# --- Kernel32 Functions ---
BeginUpdateResourceW = kernel32.BeginUpdateResourceW
BeginUpdateResourceW.restype = wintypes.HANDLE
BeginUpdateResourceW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL]

UpdateResourceW = kernel32.UpdateResourceW
UpdateResourceW.restype = wintypes.BOOL
UpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.LPWSTR, wintypes.WORD, LPVOID, wintypes.DWORD]

EndUpdateResourceW = kernel32.EndUpdateResourceW
EndUpdateResourceW.restype = wintypes.BOOL
EndUpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.BOOL]

GetModuleHandleW = kernel32.GetModuleHandleW
GetModuleHandleW.restype = wintypes.HMODULE
GetModuleHandleW.argtypes = [wintypes.LPCWSTR]


# --- User32 Functions ---
RegisterClassExW = user32.RegisterClassExW # Added
RegisterClassExW.restype = wintypes.ATOM
RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]

CreateWindowExW = user32.CreateWindowExW # Added
CreateWindowExW.restype = wintypes.HWND
CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, LPVOID]

CreateDialogIndirectParamW = user32.CreateDialogIndirectParamW
CreateDialogIndirectParamW.restype = wintypes.HWND
CreateDialogIndirectParamW.argtypes = [wintypes.HINSTANCE, LPVOID, wintypes.HWND, DLGPROC, wintypes.LPARAM]

DestroyWindow = user32.DestroyWindow
DestroyWindow.restype = wintypes.BOOL
DestroyWindow.argtypes = [wintypes.HWND]

DefWindowProcW = user32.DefWindowProcW # Added
DefWindowProcW.restype = wintypes.LPARAM
DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

DefDlgProcW = user32.DefDlgProcW
DefDlgProcW.restype = wintypes.LPARAM # Corrected as per previous subtask (matches WNDPROC return)
DefDlgProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

SetParent = user32.SetParent
SetParent.restype = wintypes.HWND
SetParent.argtypes = [wintypes.HWND, wintypes.HWND]

GetWindowLongW = user32.GetWindowLongW
GetWindowLongW.restype = wintypes.LONG
GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]

SetWindowLongW = user32.SetWindowLongW
SetWindowLongW.restype = wintypes.LONG
SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]

ShowWindow = user32.ShowWindow # Verified Present
ShowWindow.restype = wintypes.BOOL
ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]

UpdateWindow = user32.UpdateWindow # Added
UpdateWindow.restype = wintypes.BOOL
UpdateWindow.argtypes = [wintypes.HWND]

MoveWindow = user32.MoveWindow
MoveWindow.restype = wintypes.BOOL
MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]

SetWindowPos = user32.SetWindowPos
SetWindowPos.restype = wintypes.BOOL
SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]

CreateIconFromResourceEx = user32.CreateIconFromResourceEx
CreateIconFromResourceEx.restype = wintypes.HICON
CreateIconFromResourceEx.argtypes = [
    ctypes.POINTER(wintypes.BYTE),
    wintypes.DWORD,
    wintypes.BOOL,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT
]

LookupIconIdFromDirectoryEx = user32.LookupIconIdFromDirectoryEx
LookupIconIdFromDirectoryEx.restype = ctypes.c_int
LookupIconIdFromDirectoryEx.argtypes = [
    ctypes.POINTER(wintypes.BYTE),
    wintypes.BOOL,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT
]

GetIconInfo = user32.GetIconInfo
GetIconInfo.restype = wintypes.BOOL
GetIconInfo.argtypes = [wintypes.HICON, ctypes.POINTER(ICONINFO)]

DestroyIcon = user32.DestroyIcon
DestroyIcon.restype = wintypes.BOOL
DestroyIcon.argtypes = [wintypes.HICON]

LoadCursorW = user32.LoadCursorW # Added
LoadCursorW.restype = wintypes.HCURSOR
LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]

LoadIconW = user32.LoadIconW # Added
LoadIconW.restype = wintypes.HICON
LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]

GetMessageW = user32.GetMessageW # Added
GetMessageW.restype = wintypes.BOOL
GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]

TranslateMessage = user32.TranslateMessage # Added
TranslateMessage.restype = wintypes.BOOL
TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]

DispatchMessageW = user32.DispatchMessageW # Added
DispatchMessageW.restype = wintypes.LPARAM
DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]

PostQuitMessage = user32.PostQuitMessage # Added
PostQuitMessage.restype = None
PostQuitMessage.argtypes = [ctypes.c_int]


# --- GDI32 Functions ---
CreateCompatibleDC = gdi32.CreateCompatibleDC
CreateCompatibleDC.restype = wintypes.HDC
CreateCompatibleDC.argtypes = [wintypes.HDC]

GetDIBits = gdi32.GetDIBits
GetDIBits.restype = ctypes.c_int
GetDIBits.argtypes = [
    wintypes.HDC,
    wintypes.HBITMAP,
    wintypes.UINT,
    wintypes.UINT,
    LPVOID,
    ctypes.POINTER(BITMAPINFO),
    wintypes.UINT
]

SelectObject = gdi32.SelectObject
SelectObject.restype = wintypes.HGDIOBJ
SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]

DeleteDC = gdi32.DeleteDC
DeleteDC.restype = wintypes.BOOL
DeleteDC.argtypes = [wintypes.HDC]

DeleteObject = gdi32.DeleteObject
DeleteObject.restype = wintypes.BOOL
DeleteObject.argtypes = [wintypes.HGDIOBJ]

GetObjectW = gdi32.GetObjectW
GetObjectW.restype = ctypes.c_int
GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, LPVOID]


if __name__ == '__main__':
    print("winapi_ctypes.py loaded.")
    print(f"CreateIconFromResourceEx: {CreateIconFromResourceEx}")
    print(f"GetDIBits: {GetDIBits}")
    try:
        err_code = ctypes.get_last_error()
        print(f"Last error (if any from loading): {err_code}")
    except Exception as e:
        print(f"Could not get last error (expected on non-Windows): {e}")
