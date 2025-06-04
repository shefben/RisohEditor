import ctypes
from ctypes import wintypes

# Load kernel32.dll and user32.dll
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
user32 = ctypes.WinDLL('user32', use_last_error=True)

# Define constants often used with these functions if not already in wintypes
INVALID_HANDLE_VALUE = wintypes.HANDLE(0)
LPVOID = ctypes.c_void_p

# --- Constants ---
WM_INITDIALOG = 0x0110
WM_COMMAND = 0x0111
WM_CLOSE = 0x0010
GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_POPUP = 0x80000000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_THICKFRAME = 0x00040000
DS_CONTROL = 0x0400 # Dialog specific style, might be useful
SW_SHOW = 5
SWP_FRAMECHANGED = 0x0020
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010

# RECT structure
class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG)]

# DLGPROC type definition
DLGPROC = ctypes.WINFUNCTYPE(wintypes.INT_PTR, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


# Helper function to create resource strings (LPWSTR) for integer IDs
def MAKEINTRESOURCE(value: int) -> wintypes.LPWSTR:
    """
    Macro to convert an integer ID to a LPWSTR type for resource functions.
    """
    return ctypes.cast(wintypes.HANDLE(value), wintypes.LPWSTR)

# --- Kernel32 Functions ---
BeginUpdateResourcesW = kernel32.BeginUpdateResourcesW
BeginUpdateResourcesW.restype = wintypes.HANDLE
BeginUpdateResourcesW.argtypes = [
    wintypes.LPCWSTR, # pFileName
    wintypes.BOOL     # bDeleteExistingResources
]

UpdateResourceW = kernel32.UpdateResourceW
UpdateResourceW.restype = wintypes.BOOL
UpdateResourceW.argtypes = [
    wintypes.HANDLE,    # hUpdate
    wintypes.LPWSTR,    # lpType
    wintypes.LPWSTR,    # lpName
    wintypes.WORD,      # wLanguage
    LPVOID,             # lpData (ctypes.c_void_p or directly pass bytes buffer)
    wintypes.DWORD      # cbData
]

EndUpdateResourcesW = kernel32.EndUpdateResourcesW
EndUpdateResourcesW.restype = wintypes.BOOL
EndUpdateResourcesW.argtypes = [
    wintypes.HANDLE,    # hUpdate
    wintypes.BOOL       # fDiscard
]

GetModuleHandleW = kernel32.GetModuleHandleW
GetModuleHandleW.restype = wintypes.HMODULE
GetModuleHandleW.argtypes = [wintypes.LPCWSTR]


# --- User32 Functions ---
CreateDialogIndirectParamW = user32.CreateDialogIndirectParamW
CreateDialogIndirectParamW.restype = wintypes.HWND
CreateDialogIndirectParamW.argtypes = [wintypes.HINSTANCE, LPVOID, wintypes.HWND, DLGPROC, wintypes.LPARAM]

DestroyWindow = user32.DestroyWindow
DestroyWindow.restype = wintypes.BOOL
DestroyWindow.argtypes = [wintypes.HWND]

DefDlgProcW = user32.DefDlgProcW
DefDlgProcW.restype = wintypes.LRESULT
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

ShowWindow = user32.ShowWindow
ShowWindow.restype = wintypes.BOOL
ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]

MoveWindow = user32.MoveWindow
MoveWindow.restype = wintypes.BOOL
MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]

SetWindowPos = user32.SetWindowPos
SetWindowPos.restype = wintypes.BOOL
SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]


if __name__ == '__main__':
    # Basic test to ensure functions are loaded (won't do anything useful)
    print("winapi_ctypes.py loaded.")
    print(f"BeginUpdateResourcesW: {BeginUpdateResourcesW}")
    print(f"UpdateResourceW: {UpdateResourceW}")
    print(f"EndUpdateResourcesW: {EndUpdateResourcesW}")
    print(f"GetModuleHandleW: {GetModuleHandleW}")
    print(f"CreateDialogIndirectParamW: {CreateDialogIndirectParamW}")
    print(f"DestroyWindow: {DestroyWindow}")
    print(f"DefDlgProcW: {DefDlgProcW}")
    # ... add other prints if desired for testing ...

    # Example usage of MAKEINTRESOURCE
    rt_icon_ptr = MAKEINTRESOURCE(3) # RT_ICON
    print(f"MAKEINTRESOURCE(3) = {rt_icon_ptr}, type: {type(rt_icon_ptr)}")

    try:
        err_code = ctypes.get_last_error()
        print(f"Last error (if any from loading): {err_code}")
    except Exception as e:
        print(f"Could not get last error (expected on non-Windows): {e}")
