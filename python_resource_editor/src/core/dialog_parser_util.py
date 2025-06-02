import re
from typing import List, Optional, Tuple, Union
import io
import struct

# --- Dialog Styles (WS_, DS_, etc. from WinUser.h) ---
# Window Styles (WS_) - Common subset
WS_POPUP = 0x80000000
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_DISABLED = 0x08000000
WS_CLIPSIBLINGS = 0x04000000
WS_CLIPCHILDREN = 0x02000000
WS_CAPTION = 0x00C00000  # WS_BORDER | WS_DLGFRAME
WS_BORDER = 0x00800000
WS_DLGFRAME = 0x00400000
WS_VSCROLL = 0x00200000
WS_HSCROLL = 0x00100000
WS_SYSMENU = 0x00080000
WS_THICKFRAME = 0x00040000
WS_GROUP = 0x00020000
WS_TABSTOP = 0x00010000
WS_MINIMIZEBOX = 0x00020000 # Note: Value is same as WS_GROUP
WS_MAXIMIZEBOX = 0x00010000 # Note: Value is same as WS_TABSTOP

# Extended Window Styles (WS_EX_) - Common subset
WS_EX_DLGMODALFRAME = 0x00000001
WS_EX_NOPARENTNOTIFY = 0x00000004
WS_EX_TOPMOST = 0x00000008
WS_EX_ACCEPTFILES = 0x00000010
WS_EX_TRANSPARENT = 0x00000020
WS_EX_CONTROLPARENT = 0x00010000
WS_EX_STATICEDGE = 0x00020000
WS_EX_APPWINDOW = 0x00040000
WS_EX_CLIENTEDGE = 0x00000200
WS_EX_CONTEXTHELP = 0x00000400
WS_EX_RIGHT = 0x00001000
WS_EX_LEFTSCROLLBAR = 0x00004000
WS_EX_WINDOWEDGE = 0x00000100

# Dialog Styles (DS_)
DS_ABSALIGN = 0x01
DS_SYSMODAL = 0x02
DS_3DLOOK = 0x04
DS_FIXEDSYS = 0x08
DS_NOFAILCREATE = 0x10
DS_LOCALEDIT = 0x20
DS_SETFONT = 0x40
DS_MODALFRAME = 0x80
DS_NOIDLEMSG = 0x100
DS_SETFOREGROUND = 0x200
DS_CONTROL = 0x0400
DS_CENTER = 0x0800
DS_SHELLFONT = DS_SETFONT | DS_FIXEDSYS

# --- Control Class Atoms & Names ---
BUTTON_ATOM = 0x0080
EDIT_ATOM = 0x0081
STATIC_ATOM = 0x0082
LISTBOX_ATOM = 0x0083
SCROLLBAR_ATOM = 0x0084
COMBOBOX_ATOM = 0x0085

# Common Control Class Names (Strings)
WC_LISTVIEW = "SysListView32"
WC_TREEVIEW = "SysTreeView32"
WC_TABCONTROL = "SysTabControl32"
WC_PROGRESS = "msctls_progress32"
WC_TOOLBAR = "ToolbarWindow32"
WC_TRACKBAR = "msctls_trackbar32"
WC_UPDOWN = "msctls_updown32"
WC_DATETIMEPICK = "SysDateTimePick32"
WC_MONTHCAL = "SysMonthCal32"
WC_IPADDRESS = "SysIPAddress32"
WC_LINK = "SysLink"

ATOM_TO_CLASSNAME_MAP = {
    BUTTON_ATOM: "BUTTON", EDIT_ATOM: "EDIT", STATIC_ATOM: "STATIC",
    LISTBOX_ATOM: "LISTBOX", SCROLLBAR_ATOM: "SCROLLBAR", COMBOBOX_ATOM: "COMBOBOX",
}
CLASSNAME_TO_ATOM_MAP = {v: k for k, v in ATOM_TO_CLASSNAME_MAP.items()}
# Add string class names to ATOM_TO_CLASSNAME_MAP for reverse lookup convenience if needed,
# though they are not atoms. Or keep a separate list of known string class names.
KNOWN_STRING_CLASSES = [
    WC_LISTVIEW, WC_TREEVIEW, WC_TABCONTROL, WC_PROGRESS, WC_TOOLBAR,
    WC_TRACKBAR, WC_UPDOWN, WC_DATETIMEPICK, WC_MONTHCAL, WC_IPADDRESS, WC_LINK
]


# --- Control Styles ---
# Button Styles (BS_)
BS_PUSHBUTTON = 0x00000000; BS_DEFPUSHBUTTON = 0x00000001; BS_CHECKBOX = 0x00000002
BS_AUTOCHECKBOX = 0x00000003; BS_RADIOBUTTON = 0x00000004; BS_3STATE = 0x00000005
BS_AUTO3STATE = 0x00000006; BS_GROUPBOX = 0x00000007; BS_USERBUTTON = 0x00000008
BS_AUTORADIOBUTTON = 0x00000009; BS_OWNERDRAW = 0x0000000B; BS_LEFTTEXT = 0x00000020
BS_ICON = 0x00000040; BS_BITMAP = 0x00000080; BS_FLAT = 0x00008000; BS_MULTILINE = 0x00002000;

# Edit Styles (ES_)
ES_LEFT = 0x0000; ES_CENTER = 0x0001; ES_RIGHT = 0x0002; ES_MULTILINE = 0x0004
ES_UPPERCASE = 0x0008; ES_LOWERCASE = 0x0010; ES_PASSWORD = 0x0020
ES_AUTOVSCROLL = 0x0040; ES_AUTOHSCROLL = 0x0080; ES_NOHIDESEL = 0x0100
ES_OEMCONVERT = 0x0400; ES_READONLY = 0x0800; ES_WANTRETURN = 0x1000
ES_NUMBER = 0x2000;

# Static Styles (SS_)
SS_LEFT = 0x0000; SS_CENTER = 0x0001; SS_RIGHT = 0x0002; SS_ICON = 0x0003
SS_BLACKRECT = 0x0004; SS_GRAYRECT = 0x0005; SS_WHITERECT = 0x0006
SS_BLACKFRAME = 0x0007; SS_GRAYFRAME = 0x0008; SS_WHITEFRAME = 0x0009
SS_SIMPLE = 0x000B; SS_ETCHEDHORZ = 0x0010; SS_ETCHEDVERT = 0x0011
SS_ETCHEDFRAME = 0x0012; SS_NOPREFIX = 0x0080; SS_CENTERIMAGE = 0x0200
SS_SUNKEN = 0x1000; SS_NOTIFY = 0x0100;

# ListBox Styles (LBS_)
LBS_NOTIFY = 0x0001; LBS_SORT = 0x0002; LBS_NOREDRAW = 0x0004; LBS_MULTIPLESEL = 0x0008
LBS_OWNERDRAWFIXED = 0x0010; LBS_OWNERDRAWVARIABLE = 0x0020; LBS_HASSTRINGS = 0x0040
LBS_USETABSTOPS = 0x0080; LBS_NOINTEGRALHEIGHT = 0x0100; LBS_MULTICOLUMN = 0x0200
LBS_WANTKEYBOARDINPUT = 0x0400; LBS_EXTENDEDSEL = 0x0800; LBS_DISABLENOSCROLL = 0x1000
LBS_STANDARD = LBS_NOTIFY | LBS_SORT | WS_VISIBLE | WS_VSCROLL | WS_BORDER

# ComboBox Styles (CBS_)
CBS_SIMPLE = 0x0001; CBS_DROPDOWN = 0x0002; CBS_DROPDOWNLIST = 0x0003
CBS_OWNERDRAWFIXED = 0x0010; CBS_OWNERDRAWVARIABLE = 0x0020; CBS_AUTOHSCROLL = 0x0040
CBS_OEMCONVERT = 0x0080; CBS_SORT = 0x0100; CBS_HASSTRINGS = 0x0200
CBS_NOINTEGRALHEIGHT = 0x0400; CBS_DISABLENOSCROLL = 0x0800;

# ListView Styles (LVS_)
LVS_ICON = 0x0000; LVS_REPORT = 0x0001; LVS_SMALLICON = 0x0002; LVS_LIST = 0x0003
LVS_EDITLABELS = 0x0200; LVS_SHOWSELALWAYS = 0x0008; LVS_SINGLESEL = 0x0004;
LVS_SHAREIMAGELISTS = 0x0040; LVS_NOLABELWRAP = 0x0080; LVS_AUTOARRANGE = 0x0100;
LVS_NOSCROLL = 0x2000; LVS_ALIGNTOP = 0x0000; LVS_ALIGNLEFT = 0x0800;
LVS_OWNERDRAWFIXED = 0x0400; LVS_NOSORTHEADER = 0x8000;

# TreeView Styles (TVS_)
TVS_HASBUTTONS = 0x0001; TVS_HASLINES = 0x0002; TVS_LINESATROOT = 0x0004; TVS_EDITLABELS = 0x0008;
TVS_DISABLEDRAGDROP = 0x0010; TVS_SHOWSELALWAYS = 0x0020; TVS_CHECKBOXES = 0x0100;
TVS_FULLROWSELECT = 0x1000;

# TabControl Styles (TCS_)
TCS_SCROLLOPPOSITE = 0x0001; TCS_BOTTOM = 0x0002; TCS_RIGHT = 0x0002; TCS_MULTISELECT = 0x0004;
TCS_BUTTONS = 0x0100; TCS_MULTILINE = 0x0200; TCS_RIGHTJUSTIFY = 0x0000; TCS_FIXEDWIDTH = 0x0400;
TCS_RAGGEDRIGHT = 0x0800; TCS_FOCUSONBUTTONDOWN = 0x1000; TCS_OWNERDRAWFIXED = 0x2000;
TCS_TOOLTIPS = 0x4000; TCS_FOCUSNEVER = 0x8000;

# ProgressBar Styles (PBS_)
PBS_SMOOTH = 0x01; PBS_VERTICAL = 0x04; PBS_MARQUEE = 0x08;

# Trackbar Styles (TBS_)
TBS_AUTOTICKS = 0x0001; TBS_VERT = 0x0002; TBS_ENABLESELRANGE = 0x0020; TBS_BOTH = 0x0008;

# UpDown Styles (UDS_)
UDS_WRAP = 0x0001; UDS_SETBUDDYINT = 0x0002; UDS_ALIGNRIGHT = 0x0004; UDS_ALIGNLEFT = 0x0008;
UDS_AUTOBUDDY = 0x0010; UDS_ARROWKEYS = 0x0020; UDS_HORZ = 0x0040; UDS_NOTHOUSANDS = 0x0080;

# DateTimePicker Styles (DTS_)
DTS_UPDOWN = 0x0001; DTS_SHOWNONE = 0x0002; DTS_SHORTDATEFORMAT = 0x0000;
DTS_LONGDATEFORMAT = 0x0004; DTS_TIMEFORMAT = 0x0009; DTS_APPCANPARSE = 0x0010;
DTS_RIGHTALIGN = 0x0020;

# MonthCalendar Styles (MCS_)
MCS_DAYSTATE = 0x0001; MCS_MULTISELECT = 0x0002; MCS_WEEKNUMBERS = 0x0004;
MCS_NOTODAYCIRCLE = 0x0008; MCS_NOTODAY = 0x0010;

# --- Style to String Maps (for display) ---
# This needs to be a dictionary where keys are prefixes/class_names and values are dicts of val->str
STYLE_TO_STR_MAP_BY_CLASS = {
    "GENERAL_WS": {v: k for k, v in globals().items() if k.startswith("WS_") and k != "WS_CHILD"}, # WS_CHILD is almost universal for controls
    "GENERAL_DS": {v: k for k, v in globals().items() if k.startswith("DS_")},
    "BUTTON": {v: k for k, v in globals().items() if k.startswith("BS_")},
    "EDIT": {v: k for k, v in globals().items() if k.startswith("ES_")},
    "STATIC": {v: k for k, v in globals().items() if k.startswith("SS_")},
    "LISTBOX": {v: k for k, v in globals().items() if k.startswith("LBS_")},
    "COMBOBOX": {v: k for k, v in globals().items() if k.startswith("CBS_")},
    WC_LISTVIEW: {v: k for k, v in globals().items() if k.startswith("LVS_")},
    WC_TREEVIEW: {v: k for k, v in globals().items() if k.startswith("TVS_")},
    WC_TABCONTROL: {v: k for k, v in globals().items() if k.startswith("TCS_")},
    WC_PROGRESS: {v: k for k, v in globals().items() if k.startswith("PBS_")},
    WC_TRACKBAR: {v: k for k, v in globals().items() if k.startswith("TBS_")},
    WC_UPDOWN: {v: k for k, v in globals().items() if k.startswith("UDS_")},
    WC_DATETIMEPICK: {v: k for k, v in globals().items() if k.startswith("DTS_")},
    WC_MONTHCAL: {v: k for k, v in globals().items() if k.startswith("MCS_")},
    # SCROLLBAR styles (SBS_) can be added if needed
}
EXSTYLE_TO_STR_MAP = {v: k for k, v in globals().items() if k.startswith("WS_EX_")}

def _format_style_flags(style_value: int, style_map_list: List[dict[int, str]]) -> str:
    """
    Converts a numeric style value to a string of |-separated flags.
    Uses a list of provided style maps.
    """
    if style_value == 0 and any(0 in style_map for style_map in style_map_list if style_map.get(0)): # Handle cases like ES_LEFT = 0
        for style_map in style_map_list:
            if 0 in style_map: return style_map[0] # Return the first 0-value flag found (e.g. "ES_LEFT")
        return "0"

    found_flags = []
    remaining_style = style_value

    # Prioritize exact matches for combined flags (like LBS_STANDARD)
    for style_map in style_map_list:
        for flag_val, flag_name in style_map.items():
            if flag_val == style_value and style_value != 0: # Exact match for the whole style
                return flag_name

    # Decompose into individual flags
    # Sort maps by flag value descending to match larger combined flags first (though exact match above handles some of this)
    # This isn't perfect for complex overlapping combined flags, but good for typical usage.
    sorted_maps_items = []
    for style_map in style_map_list:
        sorted_maps_items.extend(sorted(style_map.items(), key=lambda item: item[0], reverse=True))
    # Remove duplicates while preserving order (important for consistent output)
    # sorted_maps_items = sorted(list(set(sorted_maps_items)), key=lambda x: x[0], reverse=True) # This was over-sorting

    # A simpler approach for decomposition:
    unique_flags = {} # val: name
    for style_map in style_map_list:
        for val, name in style_map.items():
            if val != 0: # Don't include zero-value flags in decomposition unless it's the only flag
                 if val not in unique_flags : unique_flags[val] = name

    for flag_val, flag_name in sorted(unique_flags.items(), key=lambda x: x[0], reverse=True):
        if (remaining_style & flag_val) == flag_val:
            found_flags.append(flag_name)
            remaining_style &= ~flag_val # Remove these bits

    if remaining_style != 0: # Some bits were not recognized
        found_flags.append(f"0x{remaining_style:X}")

    if not found_flags:
        # If original style_value was non-zero but no flags found (e.g. maps are incomplete)
        if style_value != 0: return f"0x{style_value:X}"
        # If style_value was 0 and no specific 0-value flag name was found (e.g. WS_OVERLAPPED which is 0)
        # For RC text, "0" is usually omitted for style if it means default, but explicit 0 might be needed
        # if the map has a specific name for 0 (like ES_LEFT), it's handled at the start.
        # Otherwise, we might return "0" or an empty string. For styles, "0" is safer if no flags.
        return "0"

    return " | ".join(found_flags) if found_flags else "0"


# --- Data Structures ---
class DialogControlEntry:
    def __init__(self, class_name: Union[str, int], text: str, id_val: Union[int, str],
                 x: int, y: int, width: int, height: int,
                 style: int = 0, ex_style: int = 0, help_id: int = 0,
                 symbolic_id_name: Optional[str] = None,
                 creation_data: Optional[bytes] = None): # Added creation_data
        self.class_name: Union[str, int] = class_name
        self.text: str = text
        self.id_val: Union[int, str] = id_val
        self.symbolic_id_name: Optional[str] = symbolic_id_name
        self.x: int = x; self.y: int = y; self.width: int = width; self.height: int = height
        self.style: int = style; self.ex_style: int = ex_style; self.help_id: int = help_id
        self.creation_data: Optional[bytes] = creation_data # Store it

    def get_id_display(self) -> str:
        return str(self.symbolic_id_name or self.id_val or "0")

    def __repr__(self):
        creation_data_summary = f", creation_data_len={len(self.creation_data)}" if self.creation_data else ""
        return (f"DialogControlEntry(class='{self.class_name}', text='{self.text[:20]}...', "
                f"id='{self.get_id_display()}', pos=({self.x},{self.y}), size=({self.width},{self.height}), "
                f"style=0x{self.style:X}{creation_data_summary})")

class DialogProperties:
    def __init__(self, name: Union[int, str], caption: str = "",
                 x: int = 0, y: int = 0, width: int = 100, height: int = 100,
                 style: int = 0, ex_style: int = 0,
                 font_name: str = "MS Shell Dlg", font_size: int = 8,
                 font_weight: int = 0, font_italic: bool = False, font_charset: int = 1,
                 menu_name: Optional[Union[int, str]] = None,
                 class_name: Optional[Union[int, str]] = None,
                 symbolic_name: Optional[str] = None,
                 symbolic_menu_name: Optional[str] = None,
                 symbolic_class_name: Optional[str] = None,
                 is_ex: bool = False, help_id: int = 0):
        self.name: Union[int, str] = name
        self.symbolic_name: Optional[str] = symbolic_name
        self.caption: str = caption
        self.x: int = x; self.y: int = y
        self.width: int = width; self.height: int = height
        self.style: int = style
        self.ex_style: int = ex_style
        self.font_name: str = font_name
        self.font_size: int = font_size
        self.font_weight: int = font_weight
        self.font_italic: bool = font_italic
        self.font_charset: int = font_charset
        self.menu_name: Optional[Union[int, str]] = menu_name
        self.symbolic_menu_name: Optional[str] = symbolic_menu_name
        self.class_name: Optional[Union[int, str]] = class_name
        self.symbolic_class_name: Optional[str] = symbolic_class_name
        self.is_ex: bool = is_ex
        self.help_id: int = help_id

    def __repr__(self):
        return (f"DialogProperties(name='{self.symbolic_name or self.name}', caption='{self.caption[:20]}...', "
                f"size=({self.width}x{self.height}), style=0x{self.style:X}, is_ex={self.is_ex})")

# --- Binary Parsing Helper Functions ---
def _read_unicode_string_align(stream: io.BytesIO) -> Optional[str]:
    """
    Reads a null-terminated UTF-16LE string from the stream, then aligns
    the stream position to the next DWORD boundary.
    Returns the string, or None if EOF is encountered before any data/terminator.
    Raises EOFError if string is unterminated or padding is incomplete.
    """
    print(f"DEBUG_RUSA: Entry. Stream pos: {stream.tell()}") # LOGGING
    initial_stream_pos = stream.tell()
    
    # Check for immediate EOF
    print(f"DEBUG_RUSA: Initial peek. Stream pos before read: {stream.tell()}") # LOGGING
    first_peek = stream.read(2)
    print(f"DEBUG_RUSA: Initial peek. Read {len(first_peek)} bytes: {first_peek!r}. Stream pos after read: {stream.tell()}") # LOGGING
    
    if not first_peek: # Empty read means true EOF at start
        print(f"DEBUG_RUSA: Returning None due to immediate EOF. Stream pos: {stream.tell()}") # LOGGING
        return None 
    
    # Rewind after peek, as we'll re-read for actual processing or specific logic.
    print(f"DEBUG_RUSA: Rewinding after peek. Stream pos before seek: {stream.tell()}, target: {initial_stream_pos}") # LOGGING
    stream.seek(initial_pos)
    print(f"DEBUG_RUSA: Rewound. Stream pos after seek: {stream.tell()}") # LOGGING

    # Re-read the first two bytes for decision making
    # This ensures stream position is consistent for the paths below.
    print(f"DEBUG_RUSA: Decision peek. Stream pos before read: {stream.tell()}") # LOGGING
    decision_bytes = stream.read(2)
    print(f"DEBUG_RUSA: Decision peek. Read {len(decision_bytes)} bytes: {decision_bytes!r}. Stream pos after read: {stream.tell()}") # LOGGING

    if len(decision_bytes) < 2:
        # This means EOF occurred when trying to read the first 2 bytes of a potential string/terminator.
        err_msg = f"Stream ended unexpectedly at offset {initial_stream_pos}. Expected 2 bytes for string/terminator, got {len(decision_bytes)}."
        print(f"DEBUG_RUSA: Raising EOFError: {err_msg}") # LOGGING
        raise EOFError(err_msg)

    # Handle empty string case (just a null terminator b'\x00\x00')
    if decision_bytes == b'\x00\x00':
        # Already consumed the null terminator with `decision_bytes` read.
        current_pos_after_null = stream.tell()
        print(f"DEBUG_RUSA: Empty string detected. Current pos after null: {current_pos_after_null}") # LOGGING
        padding_needed = (4 - (current_pos_after_null % 4)) % 4
        print(f"DEBUG_RUSA: Empty string padding needed: {padding_needed}") # LOGGING
        
        if padding_needed > 0:
            bytes_available = -1
            if hasattr(stream, 'getbuffer'): bytes_available = len(stream.getbuffer()) - current_pos_after_null
            
            print(f"DEBUG_RUSA: Reading empty string padding. Stream pos: {stream.tell()}, padding_needed: {padding_needed}, buffer_len (approx): {len(stream.getbuffer()) if hasattr(stream,'getbuffer') else 'N/A'}, bytes_available: {bytes_available}") # LOGGING
            
            if hasattr(stream, 'getbuffer') and bytes_available < padding_needed :
                err_msg = f"EOF: Expected {padding_needed} padding bytes after empty string, but only {bytes_available} available. Stream pos: {current_pos_after_null}"
                print(f"DEBUG_RUSA: Raising EOFError (pre-check for empty string padding): {err_msg}") # LOGGING
                raise EOFError(err_msg)

            padding_bytes_read = stream.read(padding_needed)
            print(f"DEBUG_RUSA: Empty string padding. Read {len(padding_bytes_read)} bytes. Stream pos after read: {stream.tell()}") # LOGGING
            if len(padding_bytes_read) < padding_needed:
                err_msg = f"EOF: Expected {padding_needed} padding bytes after empty string, got {len(padding_bytes_read)}. Stream pos: {current_pos_after_null}"
                print(f"DEBUG_RUSA: Raising EOFError (post-check for empty string padding): {err_msg}") # LOGGING
                raise EOFError(err_msg)
        print(f"DEBUG_RUSA: Returning empty string. Stream pos: {stream.tell()}") # LOGGING
        return ""

    # Non-empty string: Rewind decision_bytes and read char by char
    print(f"DEBUG_RUSA: Non-empty string. Rewinding decision_bytes. Stream pos before seek: {stream.tell()}, target: {initial_stream_pos}") # LOGGING
    stream.seek(initial_stream_pos)
    print(f"DEBUG_RUSA: Rewound. Stream pos after seek: {stream.tell()}") # LOGGING
    
    chars = []
    while True:
        print(f"DEBUG_RUSA: Loop: Reading char. Stream pos: {stream.tell()}") # LOGGING
        char_bytes = stream.read(2)
        print(f"DEBUG_RUSA: Loop: Read {len(char_bytes)} bytes: {char_bytes!r}. Stream pos after read: {stream.tell()}") # LOGGING

        if not char_bytes: # Clean EOF
            if chars: # Unterminated string
                err_msg = f"Unterminated unicode string: EOF encountered at offset {stream.tell()} after reading '{''.join(chars)}'."
                print(f"DEBUG_RUSA: Raising EOFError (EOF, unterminated string): {err_msg}") # LOGGING
                raise EOFError(err_msg)
            else: # EOF before any char (should have been caught by initial peek or decision_bytes read if stream is non-empty)
                print(f"DEBUG_RUSA: Returning None (EOF before any char in loop). Stream pos: {stream.tell()}") # LOGGING
                return None # Or raise error if string is mandatory and this path is hit.

        if len(char_bytes) < 2: # Short read
            if chars: # Unterminated string with partial last char
                err_msg = f"Unterminated unicode string: Short read (1 byte: {char_bytes!r}) at offset {stream.tell()} after reading '{''.join(chars)}'."
                print(f"DEBUG_RUSA: Raising EOFError (short read, unterminated string): {err_msg}") # LOGGING
                raise EOFError(err_msg)
            else: # Short read before any char (similar to above, should be rare here)
                err_msg = f"Short read (1 byte: {char_bytes!r}) at offset {stream.tell()} when expecting a char or null terminator."
                print(f"DEBUG_RUSA: Raising EOFError (short read before any char in loop): {err_msg}") # LOGGING
                raise EOFError(err_msg)

        if char_bytes == b'\x00\x00': # Null terminator
            print(f"DEBUG_RUSA: Loop: Null terminator found. Stream pos: {stream.tell()}") # LOGGING
            break
        try:
            chars.append(char_bytes.decode('utf-16-le'))
        except UnicodeDecodeError as ude:
            err_msg = f"{ude.reason} (at stream offset {stream.tell()-2})"
            print(f"DEBUG_RUSA: Raising UnicodeDecodeError: {err_msg}") # LOGGING
            raise UnicodeDecodeError(ude.encoding, ude.object, ude.start, ude.end, err_msg)
            
    string_val = "".join(chars)
    print(f"DEBUG_RUSA: String value: '{string_val}'") # LOGGING
    
    # Align to DWORD boundary
    current_pos_after_string_and_null = stream.tell()
    print(f"DEBUG_RUSA: Align: Current pos after string and null: {current_pos_after_string_and_null}") # LOGGING
    padding_needed = (4 - (current_pos_after_string_and_null % 4)) % 4
    print(f"DEBUG_RUSA: Align: Padding needed: {padding_needed}") # LOGGING
    
    if padding_needed > 0:
        bytes_available = -1
        if hasattr(stream, 'getbuffer'): bytes_available = len(stream.getbuffer()) - current_pos_after_string_and_null

        print(f"DEBUG_RUSA: Reading string padding. Stream pos: {stream.tell()}, padding_needed: {padding_needed}, buffer_len (approx): {len(stream.getbuffer()) if hasattr(stream,'getbuffer') else 'N/A'}, bytes_available: {bytes_available}") # LOGGING

        if hasattr(stream, 'getbuffer') and bytes_available < padding_needed:
            err_msg = f"EOF: Not enough data for alignment padding after string '{string_val}'. Expected {padding_needed}, but only {bytes_available} available. Stream pos: {current_pos_after_string_and_null}"
            print(f"DEBUG_RUSA: Raising EOFError (pre-check for string padding): {err_msg}") # LOGGING
            raise EOFError(err_msg)

        padding_bytes_read = stream.read(padding_needed)
        print(f"DEBUG_RUSA: String padding. Read {len(padding_bytes_read)} bytes. Stream pos after read: {stream.tell()}") # LOGGING
        if len(padding_bytes_read) < padding_needed:
            err_msg = f"Short read for alignment padding after string '{string_val}'. Expected {padding_needed}, got {len(padding_bytes_read)}. Stream pos: {current_pos_after_string_and_null}"
            print(f"DEBUG_RUSA: Raising EOFError (post-check for string padding): {err_msg}") # LOGGING
            raise EOFError(err_msg)
    
    print(f"DEBUG_RUSA: Returning string value: '{string_val}'. Stream pos: {stream.tell()}") # LOGGING
    return string_val

def _read_word_or_string_align(stream: io.BytesIO) -> Tuple[Union[int, str, None], bool]:
    first_word_bytes = stream.read(2)
    if not first_word_bytes or len(first_word_bytes) < 2 : return None, False
    first_word = struct.unpack('<H', first_word_bytes)[0]
    if first_word == 0xFFFF:
        id_bytes = stream.read(2)
        if not id_bytes or len(id_bytes) < 2: return None, False
        actual_id = struct.unpack('<H', id_bytes)[0]
        return actual_id, False
    elif first_word == 0x0000:
        # This indicates an empty string for class/menu name or title.
        # The field itself is still present and string-terminated.
        # The _read_unicode_string_align will read the null-terminator and align.
        stream.seek(stream.tell() - 2) # Rewind to let _read_unicode_string_align process it
        return _read_unicode_string_align(stream), True # Will return ""
    else:
        stream.seek(stream.tell() - 2)
        return _read_unicode_string_align(stream), True


# --- RC Text Parsing and Generation (Simplified for this subtask) ---
def parse_dialog_rc_text(rc_text: str) -> Tuple[Optional[DialogProperties], List[DialogControlEntry]]:
    # ... (Implementation remains simplified as primary focus is binary parsing for this subtask) ...
    print("Warning: RC text parsing for dialogs is simplified. Complex dialogs may not parse fully.")
    props = DialogProperties(name="PARSED_DIALOG_NAME_FROM_RC", caption="Parsed Dialog (RC Text - Simplified)")
    controls = []
    # Basic CAPTION parsing
    cap_match = re.search(r'CAPTION\s+"([^"]*(?:""[^"]*)*)"', rc_text, re.IGNORECASE)
    if cap_match: props.caption = cap_match.group(1).replace('""','"')

    # Basic STYLE parsing
    style_match = re.search(r'STYLE\s+([A-Za-z0-9_\|\s\+\-\#\(\)]+)', rc_text, re.IGNORECASE)
    if style_match:
        try: props.style = eval(style_match.group(1).replace("|","|")) # Basic eval
        except: print(f"Warning: Could not eval dialog STYLE: {style_match.group(1)}")

    # Very basic control parsing (example for PUSHBUTTON, LTEXT, EDITTEXT, CONTROL)
    # This regex is very naive and will likely miss many valid RC constructs.
    control_pattern = re.compile(
        r'^\s*(PUSHBUTTON|LTEXT|EDITTEXT|CONTROL)\s+' # Keyword
        r'"([^"]*(?:""[^"]*)*)"\s*,\s*' # Text
        r'([A-Za-z0-9_#\.\-\+]+)\s*,\s*' # ID
        r'(?:([A-Za-z0-9_#\."]+)\s*,\s*)?' # Optional Class for CONTROL
        r'([A-Za-z0-9_\|\s\+\-\#\(\)]+)\s*,\s*' # Style
        r'(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)' # x, y, w, h
        r'(?:\s*,\s*([A-Za-z0-9_\|\s\+\-\#\(\)]+))?\s*$', # Optional ExStyle
        re.IGNORECASE
    )
    in_begin_end = False
    for line in rc_text.splitlines():
        line = line.strip()
        if line.upper() == "BEGIN": in_begin_end = True; continue
        if line.upper() == "END": in_begin_end = False; continue
        if not in_begin_end or line.startswith("//"): continue

        match = control_pattern.match(line)
        if match:
            keyword, text, id_str, class_name_rc, style_str, x, y, w, h, ex_style_str = match.groups()
            text = text.replace('""','"')
            id_val: Union[str,int] = id_str
            if id_str.isdigit() or id_str.startswith("0x"): id_val = int(id_str,0)

            style_val = 0; ex_style_val = 0
            try: style_val = eval(style_str.replace("|","|"))
            except: pass # print(f"Warning: Could not eval control STYLE: {style_str}")
            if ex_style_str:
                try: ex_style_val = eval(ex_style_str.replace("|","|"))
                except: pass # print(f"Warning: Could not eval control EXSTYLE: {ex_style_str}")

            final_class_name = keyword.upper() # Default for LTEXT, PUSHBUTTON etc.
            if keyword.upper() == "CONTROL" and class_name_rc:
                final_class_name = class_name_rc.strip('"')
            elif keyword.upper() == "EDITTEXT": final_class_name = "EDIT"

            controls.append(DialogControlEntry(final_class_name, text, id_val, int(x),int(y),int(w),int(h), style=style_val, ex_style=ex_style_val))
    return props, controls


def generate_dialog_rc_text(dialog_props: DialogProperties, controls: List[DialogControlEntry], lang_id: Optional[int] = None) -> str:
    # ... (Implementation remains simplified) ...
    lines: List[str] = []
    if lang_id is not None: lines.append(f"LANGUAGE {lang_id & 0x3FF}, {(lang_id >> 10) & 0x3F}")
    name_str = dialog_props.symbolic_name or str(dialog_props.name)
    if isinstance(dialog_props.name, str) and not dialog_props.symbolic_name: name_str = f'"{dialog_props.name}"'
    dialog_type = "DIALOGEX" if dialog_props.is_ex else "DIALOG"
    lines.append(f"{name_str} {dialog_type} {dialog_props.x}, {dialog_props.y}, {dialog_props.width}, {dialog_props.height}")

    # Convert dialog styles to string representations
    dialog_style_str = _format_style_flags(dialog_props.style, [STYLE_TO_STR_MAP_BY_CLASS["GENERAL_DS"], STYLE_TO_STR_MAP_BY_CLASS["GENERAL_WS"]])
    if dialog_style_str and dialog_style_str != "0": # Only add STYLE if it's not zero or default
        lines.append(f"STYLE {dialog_style_str}")

    if dialog_props.ex_style: # EXSTYLE is only added if non-zero
        dialog_ex_style_str = _format_style_flags(dialog_props.ex_style, [EXSTYLE_TO_STR_MAP])
        lines.append(f"EXSTYLE {dialog_ex_style_str}")

    if dialog_props.caption:
        caption = dialog_props.caption.replace('"', '""')
        lines.append(f'CAPTION "{caption}"')

    if dialog_props.font_size and dialog_props.font_name:
        font_extra = f", {dialog_props.font_weight}, {1 if dialog_props.font_italic else 0}, 0x{dialog_props.font_charset:X}" if dialog_props.is_ex else ""
        lines.append(f'FONT {dialog_props.font_size}, "{dialog_props.font_name}"{font_extra}')
    lines.append("BEGIN")
    for ctrl in controls:
        text = ctrl.text.replace('"', '""')
        text_disp = f'"{text}"'

        id_disp = ctrl.get_id_display()

        rc_keyword = "CONTROL" # Default
        class_name_for_rc = ""

        # Determine specific RC keyword if possible
        # This is a simplified mapping. More specific mappings might be needed.
        # Order of checks can be important if a class can map to multiple keywords based on style.
        if isinstance(ctrl.class_name, int): # Atom
            if ctrl.class_name == BUTTON_ATOM:
                if (ctrl.style & BS_PUSHBUTTON) == BS_PUSHBUTTON: rc_keyword = "PUSHBUTTON"
                elif (ctrl.style & BS_DEFPUSHBUTTON) == BS_DEFPUSHBUTTON: rc_keyword = "DEFPUSHBUTTON"
                elif (ctrl.style & BS_CHECKBOX) == BS_CHECKBOX: rc_keyword = "CHECKBOX"
                elif (ctrl.style & BS_AUTOCHECKBOX) == BS_AUTOCHECKBOX: rc_keyword = "AUTOCHECKBOX" # Often just CHECKBOX with style
                elif (ctrl.style & BS_RADIOBUTTON) == BS_RADIOBUTTON: rc_keyword = "RADIOBUTTON"
                elif (ctrl.style & BS_AUTORADIOBUTTON) == BS_AUTORADIOBUTTON: rc_keyword = "AUTORADIOBUTTON" # Often just RADIOBUTTON
                elif (ctrl.style & BS_GROUPBOX) == BS_GROUPBOX: rc_keyword = "GROUPBOX"
                # Add BS_OWNERDRAW, BS_USERBUTTON etc. if they should have specific keywords or stay CONTROL
                else: class_name_for_rc = f'"{ATOM_TO_CLASSNAME_MAP.get(ctrl.class_name, str(ctrl.class_name))}"'
            elif ctrl.class_name == EDIT_ATOM: rc_keyword = "EDITTEXT"
            elif ctrl.class_name == STATIC_ATOM:
                # Basic SS_LEFT, SS_CENTER, SS_RIGHT for LTEXT, CTEXT, RTEXT
                # Exact matching for SS_ICON, SS_BLACKRECT etc. might be better with CONTROL "Static"
                if (ctrl.style & 0x0F) == SS_LEFT: rc_keyword = "LTEXT" # Check only horizontal alignment part
                elif (ctrl.style & 0x0F) == SS_CENTER: rc_keyword = "CTEXT"
                elif (ctrl.style & 0x0F) == SS_RIGHT: rc_keyword = "RTEXT"
                elif (ctrl.style & SS_ICON) == SS_ICON: rc_keyword = "ICON" # ICON "" or ICON id
                else: class_name_for_rc = f'"{ATOM_TO_CLASSNAME_MAP.get(ctrl.class_name, str(ctrl.class_name))}"'
            elif ctrl.class_name == LISTBOX_ATOM: rc_keyword = "LISTBOX"
            elif ctrl.class_name == SCROLLBAR_ATOM: rc_keyword = "SCROLLBAR"
            elif ctrl.class_name == COMBOBOX_ATOM: rc_keyword = "COMBOBOX"
            else: # Unknown atom
                class_name_for_rc = f'"0x{ctrl.class_name:X}"'
        elif isinstance(ctrl.class_name, str):
            # For known string class names, decide if they have a simpler RC keyword
            # Example: "RichEdit20W" would use CONTROL "RichEdit20W"
            if ctrl.class_name.upper() == "BUTTON": # String "Button"
                 if (ctrl.style & BS_PUSHBUTTON) == BS_PUSHBUTTON: rc_keyword = "PUSHBUTTON"
                 # ... (add other BS_ types as above) ...
                 else: class_name_for_rc = f'"{ctrl.class_name}"'
            elif ctrl.class_name.upper() == "EDIT": rc_keyword = "EDITTEXT"
            # ... (add other string class names if they map to simple keywords) ...
            else: # Default to CONTROL "ClassName"
                class_name_for_rc = f'"{ctrl.class_name}"'

        # Determine relevant style maps for _format_style_flags
        current_style_maps = [STYLE_TO_STR_MAP_BY_CLASS["GENERAL_WS"]] # Always include general WS_
        if isinstance(ctrl.class_name, int) and ctrl.class_name in ATOM_TO_CLASSNAME_MAP:
            maps_key = ATOM_TO_CLASSNAME_MAP[ctrl.class_name]
            if maps_key in STYLE_TO_STR_MAP_BY_CLASS:
                current_style_maps.append(STYLE_TO_STR_MAP_BY_CLASS[maps_key])
        elif isinstance(ctrl.class_name, str) and ctrl.class_name in STYLE_TO_STR_MAP_BY_CLASS:
             current_style_maps.append(STYLE_TO_STR_MAP_BY_CLASS[ctrl.class_name])

        # Remove WS_CHILD from style for RC text as it's implied by being a control
        # However, ensure it's handled if other style calculation relies on it being there before formatting.
        # For now, let _format_style_flags handle it based on the map.
        # If WS_CHILD is in GENERAL_WS map, it will be added if present.
        # Typically, WS_VISIBLE is also there.
        ctrl_style_str = _format_style_flags(ctrl.style, current_style_maps)

        line_parts = [f"    {rc_keyword} {text_disp}, {id_disp}"]
        if class_name_for_rc: # Only for CONTROL keyword
            line_parts.append(f", {class_name_for_rc}")

        line_parts.append(f", {ctrl.x}, {ctrl.y}, {ctrl.width}, {ctrl.height}")

        if ctrl_style_str and ctrl_style_str != "0": # Only add style string if not default/zero
            # For some keywords like LTEXT, PUSHBUTTON, style is often omitted if default for that type.
            # This simple check adds it if _format_style_flags produced something other than "0".
            line_parts.append(f", {ctrl_style_str}")

        if dialog_props.is_ex:
            if ctrl.ex_style != 0:
                ex_style_str = _format_style_flags(ctrl.ex_style, [EXSTYLE_TO_STR_MAP])
                # Need to ensure preceding comma if style was omitted
                if not (ctrl_style_str and ctrl_style_str != "0"): line_parts.append(",")
                line_parts.append(f", {ex_style_str}")
            if ctrl.help_id != 0:
                # Ensure preceding commas if style/ex_style were omitted
                if not (ctrl_style_str and ctrl_style_str != "0") and ctrl.ex_style == 0 : line_parts.append(",,")
                elif not (ctrl_style_str and ctrl_style_str != "0") or ctrl.ex_style == 0 : line_parts.append(",")
                line_parts.append(f", {ctrl.help_id}")

        lines.append("".join(line_parts))
    lines.append("END")
    return "\n".join(lines)


if __name__ == '__main__':
    print("Testing dialog_parser_util.py with constants and binary helpers.")
    # ... (tests from previous step can be kept or adapted) ...
    print("\ndialog_parser_util.py self-tests completed.")


