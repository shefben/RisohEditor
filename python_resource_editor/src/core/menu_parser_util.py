import re
from typing import List, Optional, Tuple, Union
import copy
import struct # For binary parsing helpers
import io

# --- Windows API Menu Flags ---
# Standard MF_ flags (some are also MFT_ or MFS_ base types for MENUEX)
MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
MF_POPUP = 0x00000010
MF_END = 0x00000080  # Standard menus: marks the last item in a popup or the main menu list
MF_OWNERDRAW = 0x00000100

# Standard MF_ state/modifier flags
MF_GRAYED = 0x00000001
MF_DISABLED = 0x00000002
MF_CHECKED = 0x00000008
MF_MENUBARBREAK = 0x00000020
MF_MENUBREAK = 0x00000040
MF_HELP = 0x00004000        # Used in MENUITEM statement in RC, not usually a bitflag for item state
MF_BYCOMMAND = 0x00000000   # Default: ID is a command ID
MF_BYPOSITION = 0x00000400  # ID is a 0-based position; not typical in RC text

# MENUEX specific flags (dwType from MENUEX_TEMPLATE_ITEM)
MFT_STRING = MF_STRING          # Item is a string
MFT_BITMAP = 0x00000004         # Not MF_BITMAP, this is MFT_BITMAP
MFT_MENUBARBREAK = MF_MENUBARBREAK
MFT_MENUBREAK = MF_MENUBREAK
MFT_OWNERDRAW = MF_OWNERDRAW
MFT_RADIOCHECK = 0x00000200     # Item is a radio item (displays checkmark)
MFT_SEPARATOR = MF_SEPARATOR
MFT_RIGHTORDER = 0x00002000
MFT_RIGHTJUSTIFY = 0x00004000

# MENUEX specific bResInfo flag (for MENUEX_TEMPLATE_ITEM)
# If MF_POPUP is set in dwType, this item defines a submenu.
MFR_POPUP = 0x00000001 # If this bit is set in bResInfo, item is a popup (used with MF_POPUP in dwType)
                       # MSDN states: "If this value is specified, the dwType member must have the MFT_POPUP flag set."
MFR_END = 0x00000080   # Indicates the last item in this menu (same value as MF_END but contextually for bResInfo)
                       # However, often just checking dwType for MF_POPUP is sufficient.


# MENUEX specific state flags (dwState from MENUEX_TEMPLATE_ITEM)
MFS_GRAYED = 0x00000003     # Item is grayed and disabled (combines MF_GRAYED and MF_DISABLED)
MFS_DISABLED = MF_DISABLED  # Can also be set directly, MFS_GRAYED is preferred for full effect
MFS_CHECKED = MF_CHECKED
MFS_HILITE = 0x00000080
MFS_DEFAULT = 0x00001000
# MFS_ENABLED = 0x00000000 (default state, item is enabled)

# MENUEX Header constants
MENUEX_TEMPLATE_VERSION = 1 # wVersion in MENUEX_TEMPLATE_HEADER
MENUEX_HEADER_OFFSET = 4     # wOffset in MENUEX_TEMPLATE_HEADER (offset to first MENUEX_TEMPLATE_ITEM from start of header)

FLAG_TO_STR_MAP = {
    MF_GRAYED: "GRAYED",
    MF_DISABLED: "INACTIVE",
    MF_CHECKED: "CHECKED",
    MF_MENUBARBREAK: "MENUBARBREAK",
    MF_MENUBREAK: "MENUBREAK",
    MF_HELP: "HELP",
    MF_OWNERDRAW: "OWNERDRAW",
    MFT_RADIOCHECK: "RADIO", # Corresponds to MFT_RADIOCHECK
    MFT_BITMAP: "BITMAP",       # Corresponds to MFT_BITMAP
    MFS_DEFAULT: "DEFAULT",
    MFS_HILITE: "HILITE", # Usually transient, but can be specified
}


class MenuItemEntry:
    def __init__(self, item_type: str = "MENUITEM", text: str = "",
                 id_val: Union[int, str] = 0, name_val: Optional[str] = None,
                 flags: Optional[List[str]] = None,
                 flags_numeric: int = 0,
                 state_numeric: int = 0,
                 children: Optional[List['MenuItemEntry']] = None,
                 is_ex: bool = False, help_id: Optional[int] = None,
                 bResInfo_word: Optional[int] = None):
        self.item_type: str = item_type
        self.text: str = text
        self.id_val: Union[int, str] = id_val
        self.name_val: Optional[str] = name_val

        self.flags: List[str] = flags if flags is not None else []
        self.type_numeric: int = flags_numeric # For MENUEX: MFT_ type flags from dwType. Standard: MF_ flags value.
        self.state_numeric: int = state_numeric # MENUEX: MFS_ state flags from dwState. Standard: (flags_numeric has state).

        self.children: List['MenuItemEntry'] = children if children is not None else []
        self.is_ex: bool = is_ex
        self.help_id: Optional[int] = help_id
        self.bResInfo_word: Optional[int] = bResInfo_word

    def get_id_display(self) -> str:
        if self.name_val: return self.name_val
        if self.item_type == "POPUP": return ""
        if self.item_type == "SEPARATOR": return ""
        return str(self.id_val if self.id_val is not None else 0)

    def get_flags_display_list(self) -> List[str]:
        display_flags = list(self.flags)

        source_flags_for_state = self.state_numeric if self.is_ex else self.type_numeric

        for flag_val, flag_name in FLAG_TO_STR_MAP.items():
            is_set = False
            if self.is_ex:
                # For MENUEX, state flags are in state_numeric, type flags in type_numeric
                if flag_val in [MF_GRAYED, MF_DISABLED, MF_CHECKED, MFS_DEFAULT, MFS_HILITE]: # These are MFS_ states
                    is_set = bool(self.state_numeric & flag_val)
                    if flag_val == MF_GRAYED and (self.state_numeric & MFS_GRAYED) == MFS_GRAYED : is_set = True # MFS_GRAYED implies MF_GRAYED
                elif flag_val in [MF_MENUBARBREAK, MF_MENUBREAK, MF_OWNERDRAW, MFT_RADIOCHECK]: # These are MFT_ types
                    is_set = bool(self.type_numeric & flag_val)
            else: # Standard Menu
                is_set = bool(self.type_numeric & flag_val)

            if is_set and flag_name not in display_flags:
                if self.is_ex and flag_name == "DISABLED" and (self.state_numeric & MFS_GRAYED) == MFS_GRAYED:
                    # If MFS_GRAYED is set, "GRAYED" will be added. Avoid adding "INACTIVE"/"DISABLED" as redundant.
                    continue
                display_flags.append(flag_name)

        return sorted(list(set(display_flags)))

    def __repr__(self):
        return (f"MenuItemEntry(type='{self.item_type}', text='{self.text}', id='{self.get_id_display()}', "
                f"flags={self.get_flags_display_list()}, type_num=0x{self.type_numeric:X}, state_num=0x{self.state_numeric:X}, "
                f"children={len(self.children)}, ex={self.is_ex}, help=0x{self.help_id if self.help_id else 0:X}, bRes=0x{self.bResInfo_word if self.bResInfo_word else 0:X})")


# --- RC Text Parsing ---
def _parse_menu_items_recursive(lines_iterator, is_ex_menu: bool) -> List[MenuItemEntry]:
    items: List[MenuItemEntry] = []
    # MENUEX item: MENUITEM "text" [, id] [, type] [, state] [, helpID]
    # Standard item: MENUITEM "text" [, id] [, flags...]
    # POPUP "text" [[, id] [, type] [, state] [, helpID]] (MENUEX)
    # POPUP "text" [[, id] [, flags...]] (Standard)
    item_pattern_str = r'^\s*(MENUITEM|POPUP)\s+"([^"]*(?:""[^"]*)*)"' \
                       r'(?:\s*,\s*([A-Za-z0-9_#\.\+\-]+))?' \
                       r'(?:\s*,\s*([A-Za-z0-9_\|\s\+\-\#\(\)]+))?' \
                       r'(?:\s*,\s*([A-Za-z0-9_\|\s\+\-\#\(\)]+))?' \
                       r'(?:\s*,\s*(0x[0-9a-fA-F]+|[0-9]+))?\s*$' # HelpID for MENUEX

    item_pattern = re.compile(item_pattern_str, re.IGNORECASE)
    separator_pattern = re.compile(r'^\s*MENUITEM\s+SEPARATOR\s*$', re.IGNORECASE)

    while True:
        try: line = next(lines_iterator); line_strip = line.strip()
        except StopIteration: break
        if not line_strip or line_strip.startswith("//") or line_strip.startswith("/*"): continue
        if line_strip.upper() == "END": break

        sep_match = separator_pattern.match(line_strip)
        if sep_match: items.append(MenuItemEntry(item_type="SEPARATOR", text="SEPARATOR", is_ex=is_ex_menu)); continue

        item_match = item_pattern.match(line_strip)
        if item_match:
            keyword, text, id_str, group4, group5, group6 = item_match.groups()
            item_type_str = keyword.upper(); text = text.replace('""', '"')
            flags_list = []
            help_id_val = None

            if is_ex_menu:
                # MENUITEM "text", id, [type], [state], [helpID]
                # POPUP "text", [id], [type], [state], [helpID] (id is optional for POPUP)
                type_str = group4; state_str = group5; help_id_str = group6
                if type_str: flags_list.extend([f.strip().upper() for f in type_str.split('|') if f.strip()])
                if state_str: flags_list.extend([f.strip().upper() for f in state_str.split('|') if f.strip()])
                if help_id_str: help_id_val = int(help_id_str, 0)
            else: # Standard Menu
                # MENUITEM "text", id, [flags...]
                # POPUP "text", [flags...] (id usually not here for standard POPUP)
                flags_rc_str = group4 # group4 contains all flags for standard menu
                if flags_rc_str: flags_list = [f.strip().upper() for f in flags_rc_str.split(',') if f.strip()]

            item_id: Union[int, str] = 0; item_name: Optional[str] = None
            if id_str:
                id_str = id_str.strip()
                if id_str.isdigit() or (id_str.startswith("0x")):
                    try: item_id = int(id_str,0)
                    except ValueError: item_id = id_str; item_name = id_str
                else: item_id = id_str; item_name = id_str

            entry = MenuItemEntry(item_type=item_type_str, text=text, id_val=item_id, name_val=item_name,
                                  flags=flags_list, is_ex=is_ex_menu, help_id=help_id_val)
            if item_type_str == "POPUP":
                try:
                    next_line = next(lines_iterator).strip().upper()
                    if next_line == "BEGIN": entry.children = _parse_menu_items_recursive(lines_iterator, is_ex_menu)
                    else: print(f"Warning: Expected BEGIN after POPUP '{text}', found '{next_line}'.")
                except StopIteration: print(f"Warning: EOF after POPUP '{text}' expecting BEGIN.")
            items.append(entry)
    return items

def parse_menu_rc_text(rc_text: str) -> Tuple[List[MenuItemEntry], bool, str, str, str, Optional[int]]:
    # ... (Header parsing largely unchanged) ...
    lines = rc_text.splitlines()
    root_items: List[MenuItemEntry] = []
    is_ex = False; menu_name_rc = "MENU_NAME_FROM_IDENTIFIER"; characteristics_rc = "0"; version_rc = "1"; global_help_id_rc: Optional[int] = None
    header_line_index = -1; begin_found = False; options_parsed_up_to_line = -1

    for i, line in enumerate(lines):
        line_strip = line.strip()
        if not line_strip or line_strip.startswith("//") or line_strip.startswith("/*"): options_parsed_up_to_line = i; continue
        if header_line_index == -1:
            match = re.match(r'^\s*([A-Za-z0-9_"\#\.\-\+]+)\s+(MENUEX|MENU)\b(.*)', line_strip, re.IGNORECASE)
            if match:
                menu_name_rc = match.group(1).strip('"'); menu_type = match.group(2).upper(); is_ex = (menu_type == "MENUEX")
                options_str_on_header = match.group(3).strip(); header_line_index = i; options_parsed_up_to_line = i

                # Process options on header line first
                current_options_set = options_str_on_header
                if is_ex:
                    char_match = re.search(r'CHARACTERISTICS\s+(0x[0-9a-fA-F]+|[0-9]+)', current_options_set, re.IGNORECASE)
                    if char_match: characteristics_rc = char_match.group(1)
                    ver_match = re.search(r'VERSION\s+(0x[0-9a-fA-F]+|[0-9]+)', current_options_set, re.IGNORECASE)
                    if ver_match: version_rc = ver_match.group(1)
                    help_match = re.search(r'HELPINFO\s+(0x[0-9a_fA-F]+|[0-9]+)', current_options_set, re.IGNORECASE)
                    if help_match: global_help_id_rc = int(help_match.group(1),0)
            else: options_parsed_up_to_line = i # If not header, mark line as processed for option parsing
            continue

        if not begin_found:
            if line_strip.upper() == "BEGIN":
                begin_found = True; root_items = _parse_menu_items_recursive(iter(lines[i+1:]), is_ex); break
            elif is_ex: # Still parsing MENUEX options on subsequent lines
                current_options_set = line_strip
                char_match = re.search(r'CHARACTERISTICS\s+(0x[0-9a-fA-F]+|[0-9]+)', current_options_set, re.IGNORECASE)
                if char_match: characteristics_rc = char_match.group(1)
                ver_match = re.search(r'VERSION\s+(0x[0-9a-fA-F]+|[0-9]+)', current_options_set, re.IGNORECASE)
                if ver_match: version_rc = ver_match.group(1)
                help_match = re.search(r'HELPINFO\s+(0x[0-9a_fA-F]+|[0-9]+)', current_options_set, re.IGNORECASE)
                if help_match: global_help_id_rc = int(help_match.group(1),0)
            options_parsed_up_to_line = i

    if not begin_found and header_line_index != -1 : print(f"Warning: Menu '{menu_name_rc}' has no BEGIN block or items.")
    return root_items, is_ex, menu_name_rc, characteristics_rc, version_rc, global_help_id_rc

# --- RC Text Generation ---
def _generate_menu_items_rc(items: List[MenuItemEntry], indent_level: int, is_ex_menu: bool) -> List[str]:
    rc_lines: List[str] = []; indent = "    " * indent_level

    # Define which flags from FLAG_TO_STR_MAP belong to MFT (type) and MFS (state) for MENUEX
    # These should be the string representations as they appear in item.flags or get_flags_display_list()
    MFT_RC_KEYWORDS = {"BITMAP", "MENUBARBREAK", "MENUBREAK", "OWNERDRAW", "RADIO", "STRING"} # STRING is implicit usually
    MFS_RC_KEYWORDS = {"CHECKED", "DEFAULT", "GRAYED", "HILITE", "INACTIVE"}


    for item in items:
        if item.item_type == "SEPARATOR":
            # For MENUEX, SEPARATOR can have type/state, but usually doesn't.
            # For standard MENU, it's just MENUITEM SEPARATOR.
            # The binary parser puts MFT_SEPARATOR in item.flags for MENUEX if it was there.
            # For simplicity, RC generation will use the simple form.
            rc_lines.append(f"{indent}MENUITEM SEPARATOR")
            continue

        text_escaped = item.text.replace('"', '""')
        id_display = item.get_id_display()
        all_flags_list = item.get_flags_display_list() # Get all flags initially

        if is_ex_menu:
            type_ex_flags = [f for f in all_flags_list if f in MFT_RC_KEYWORDS and f != "STRING"] # STRING is default, not listed
            state_ex_flags = [f for f in all_flags_list if f in MFS_RC_KEYWORDS]

            type_ex_str = "|".join(type_ex_flags) if type_ex_flags else ""
            state_ex_str = "|".join(state_ex_flags) if state_ex_flags else ""

            # For MENUEX: keyword "text"[, id][, type][, state][, helpID]
            line_parts = [item.item_type, f'"{text_escaped}"']

            id_val_for_line = id_display if (item.item_type == "MENUITEM" or (item.item_type == "POPUP" and id_display and item.id_val !=0)) else None
            help_id_val_for_line = item.help_id if item.help_id is not None and item.help_id != 0 else None

            # Logic for adding comma-separated optional fields for MENUEX
            if id_val_for_line is not None:
                line_parts.append(f", {id_val_for_line}")
            elif type_ex_str or state_ex_str or help_id_val_for_line is not None: # Need comma if id is skipped but others exist
                line_parts.append(",")

            if type_ex_str:
                line_parts.append(f" {type_ex_str}")
            elif state_ex_str or help_id_val_for_line is not None: # Need comma if type is skipped but state/help exist
                 line_parts.append(",")

            if state_ex_str:
                line_parts.append(f" {state_ex_str}")
            elif help_id_val_for_line is not None: # Need comma if state is skipped but help exists
                line_parts.append(",")

            if help_id_val_for_line is not None:
                line_parts.append(f" {help_id_val_for_line}")

            rc_lines.append(f"{indent}{''.join(line_parts)}")

        else: # Standard Menu
            # Standard: MENUITEM "text", id, [flags...] or POPUP "text", [flags...]
            flags_str = ", " + ", ".join(all_flags_list) if all_flags_list else ""
            if item.item_type == "POPUP":
                rc_lines.append(f'{indent}POPUP "{text_escaped}"{flags_str}')
            else: # MENUITEM
                id_part = f", {id_display}" if id_display else ", 0"
                rc_lines.append(f'{indent}MENUITEM "{text_escaped}"{id_part}{flags_str}')

        if item.item_type == "POPUP" and item.children:
            rc_lines.append(f"{indent}BEGIN")
            rc_lines.extend(_generate_menu_items_rc(item.children, indent_level + 1, is_ex_menu))
            rc_lines.append(f"{indent}END")

    return rc_lines

def generate_menu_rc_text(menu_name_rc: str, items: List[MenuItemEntry], is_ex: bool,
                          characteristics_rc: str = "0", version_rc: str = "1",
                          lang_id: Optional[int] = None, global_help_id_rc: Optional[int] = None) -> str:
    lines: List[str] = []
    if lang_id is not None: primary = lang_id & 0x3FF; sub = (lang_id >> 10) & 0x3F; lines.append(f"LANGUAGE {primary}, {sub}")
    menu_keyword = "MENUEX" if is_ex else "MENU"
    name_part = f'"{menu_name_rc}"' if isinstance(menu_name_rc, str) and not menu_name_rc.isdigit() else menu_name_rc
    lines.append(f"{name_part} {menu_keyword}")
    if is_ex:
        # Only write non-default CHARACTERISTICS, VERSION, HELPINFO for MENUEX
        if characteristics_rc and characteristics_rc != "0" and characteristics_rc != "0x0":
            lines.append(f"CHARACTERISTICS {characteristics_rc}")
        if version_rc and version_rc != "1":
            lines.append(f"VERSION {version_rc}")
        if global_help_id_rc is not None and global_help_id_rc != 0 :
            lines.append(f"HELPINFO {global_help_id_rc}")
    lines.append("BEGIN"); lines.extend(_generate_menu_items_rc(items, 1, is_ex)); lines.append("END")
    return "\n".join(lines)


if __name__ == '__main__':
    print("Testing menu_parser_util.py with constants and refined MenuItemEntry.")
    entry_ex = MenuItemEntry(is_ex=True, type_numeric=MF_POPUP, state_numeric=MFS_GRAYED) # type_numeric for MFT_
    print(f"MENUEX POPUP with MFS_GRAYED: {entry_ex.get_flags_display_list()}")
    assert "GRAYED" in entry_ex.get_flags_display_list()

    entry_std = MenuItemEntry(is_ex=False, flags_numeric=MF_POPUP | MF_CHECKED) # flags_numeric for MF_
    print(f"Standard POPUP with MF_CHECKED: {entry_std.get_flags_display_list()}")
    assert "CHECKED" in entry_std.get_flags_display_list()

    print("menu_parser_util.py self-tests completed.")

```
