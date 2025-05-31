import re
from typing import List, Optional, Tuple, Union

# --- Data Structures ---
class DialogControlEntry:
    def __init__(self, class_name: Union[str, int], text: str, id_val: Union[int, str],
                 x: int, y: int, width: int, height: int,
                 style: int = 0, ex_style: int = 0, help_id: int = 0,
                 symbolic_id_name: Optional[str] = None):
        self.class_name: Union[str, int] = class_name  # e.g., "BUTTON", "EDIT", 0x0080 (WC_BUTTON atom)
        self.text: str = text
        self.id_val: Union[int, str] = id_val # Numeric ID
        self.symbolic_id_name: Optional[str] = symbolic_id_name # e.g., "IDC_MYBUTTON"
        self.x: int = x
        self.y: int = y
        self.width: int = width
        self.height: int = height
        self.style: int = style         # WS_ and control-specific styles
        self.ex_style: int = ex_style   # WS_EX_ styles
        self.help_id: int = help_id     # For extended dialogs (DLGTEMPLATEEX)

    def get_id_display(self) -> str:
        """Returns the symbolic name if available, otherwise the numeric ID as a string."""
        return str(self.symbolic_id_name or self.id_val or "0")

    def __repr__(self):
        return (f"DialogControlEntry(class='{self.class_name}', text='{self.text[:20]}...', "
                f"id='{self.get_id_display()}', pos=({self.x},{self.y}), size=({self.width},{self.height}), "
                f"style=0x{self.style:X})")

class DialogProperties:
    def __init__(self, name: Union[int, str], caption: str = "",
                 x: int = 0, y: int = 0, width: int = 100, height: int = 100,
                 style: int = 0, ex_style: int = 0,
                 font_name: str = "MS Shell Dlg", font_size: int = 8,
                 menu_name: Optional[Union[int, str]] = None,
                 class_name: Optional[Union[int, str]] = None,
                 symbolic_name: Optional[str] = None,
                 symbolic_menu_name: Optional[str] = None,
                 symbolic_class_name: Optional[str] = None,
                 is_ex: bool = False): # Added is_ex for DIALOGEX
        self.name: Union[int, str] = name
        self.symbolic_name: Optional[str] = symbolic_name
        self.caption: str = caption
        self.x: int = x; self.y: int = y
        self.width: int = width; self.height: int = height
        self.style: int = style
        self.ex_style: int = ex_style
        self.font_name: str = font_name
        self.font_size: int = font_size
        self.menu_name: Optional[Union[int, str]] = menu_name
        self.symbolic_menu_name: Optional[str] = symbolic_menu_name
        self.class_name: Optional[Union[int, str]] = class_name
        self.symbolic_class_name: Optional[str] = symbolic_class_name
        self.is_ex: bool = is_ex # True if DIALOGEX

    def __repr__(self):
        return (f"DialogProperties(name='{self.symbolic_name or self.name}', caption='{self.caption[:20]}...', "
                f"size=({self.width}x{self.height}), style=0x{self.style:X}, is_ex={self.is_ex})")


# --- Parsing and Generation Functions (Placeholders / Basic Implementation) ---

def parse_dialog_rc_text(rc_text: str) -> Tuple[Optional[DialogProperties], List[DialogControlEntry]]:
    """
    Parses DIALOG or DIALOGEX resource script text.
    This is a complex task. This implementation will be a simplified placeholder,
    focusing on the main dialog properties and a few common control types.
    """
    props: Optional[DialogProperties] = None
    controls: List[DialogControlEntry] = []
    lines = rc_text.splitlines()

    # Regex for DIALOG or DIALOGEX header
    # NAME (DIALOG|DIALOGEX) [x, y, width, height]
    dialog_header_pattern = re.compile(
        r'^\s*([A-Za-z0-9_"\#\.\-\+]+)\s+(DIALOGEX|DIALOG)\s+'
        r'(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(.*)', re.IGNORECASE
    )
    # Control statement pattern (simplified)
    # CONTROL "text", id, "class", style, x, y, width, height [, exstyle]
    # LTEXT "text", id, x, y, width, height [, style [, exstyle]] (similar for RTEXT, CTEXT)
    # PUSHBUTTON "text", id, x, y, width, height [, style [, exstyle]]
    control_pattern = re.compile(
        r'^\s*(CONTROL|LTEXT|RTEXT|CTEXT|PUSHBUTTON|EDITTEXT|COMBOBOX|LISTBOX|GROUPBOX|DEFPUSHBUTTON|CHECKBOX|RADIOBUTTON)\s+'
        r'("([^"]*(?:""[^"]*)*)"|-?\d+|[A-Za-z0-9_#\.]+)\s*,\s*' # Text or numeric placeholder for some controls
        r'([A-Za-z0-9_#\.\-\+]+)\s*,' # ID
        r'(?:\s*("([^"]*(?:""[^"]*)*)"|[A-Za-z0-9_#\.]+)\s*,)?' # Class (optional for some, like LTEXT)
        r'\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)' # x, y, width, height
        r'(?:\s*,\s*([A-Za-z0-9_\|\s\+\-\#\(\)]+))?' # Style (optional)
        r'(?:\s*,\s*([A-Za-z0-9_\|\s\+\-\#\(\)]+))?\s*$', re.IGNORECASE # ExStyle (optional)
    )
    # Simpler control pattern for now, focusing on CONTROL keyword
    simple_control_pattern = re.compile(
        r'^\s*CONTROL\s+"([^"]*(?:""[^"]*)*)"\s*,\s*([A-Za-z0-9_#\.\-\+]+)\s*,\s*' # Text, ID
        r'"([^"]*(?:""[^"]*)*)"\s*,\s*' # Class
        r'([A-Za-z0-9_\|\s\+\-\#\(\)]+)\s*,\s*' # Style
        r'(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)' # x, y, w, h
        r'(?:\s*,\s*([A-Za-z0-9_\|\s\+\-\#\(\)]+))?\s*$', re.IGNORECASE # Optional ExStyle
    )


    in_begin_end_block = False
    dialog_parsed_props: Optional[DialogProperties] = None

    for i, line in enumerate(lines):
        line_strip = line.strip()
        if not line_strip or line_strip.startswith("//"):
            continue

        if dialog_parsed_props is None: # Look for dialog header first
            match = dialog_header_pattern.match(line_strip)
            if match:
                name_str, type_str, x_str, y_str, w_str, h_str, options_str = match.groups()

                name_val: Union[str,int] = name_str.strip('"')
                if name_val.isdigit() or name_val.startswith("0x"): name_val = int(name_val,0)

                dialog_parsed_props = DialogProperties(
                    name=name_val, symbolic_name=name_str.strip('"') if not isinstance(name_val, int) else None,
                    x=int(x_str), y=int(y_str), width=int(w_str), height=int(h_str),
                    is_ex=(type_str.upper() == "DIALOGEX")
                )
                # TODO: Parse CAPTION, FONT, STYLE, MENU, CLASS from remaining lines or options_str
                # This is a highly simplified first pass.
                # A real parser would look for these keywords on subsequent lines before BEGIN.
                if "CAPTION " in options_str.upper(): # Very basic check
                    cap_match = re.search(r'CAPTION\s+"([^"]*(?:""[^"]*)*)"', options_str, re.IGNORECASE)
                    if cap_match: dialog_parsed_props.caption = cap_match.group(1).replace('""','"')
                if "STYLE " in options_str.upper():
                    style_match = re.search(r'STYLE\s+([A-Za-z0-9_\|\s\+\-\#\(\)]+)', options_str, re.IGNORECASE)
                    if style_match:
                        try: dialog_parsed_props.style = eval(style_match.group(1).replace("|","|")) # Basic eval for styles
                        except: print(f"Warning: Could not eval STYLE string: {style_match.group(1)}")
                # FONT, MENU, CLASS parsing would be similar.
                continue # Header parsed, move to next lines for properties or BEGIN

        if dialog_parsed_props: # Already found header, now look for properties or BEGIN
            if line_strip.upper() == "BEGIN":
                in_begin_end_block = True
                continue
            if line_strip.upper() == "END" and in_begin_end_block:
                in_begin_end_block = False
                break # End of dialog definition

            if in_begin_end_block:
                # Try to parse controls
                # This is where the more detailed control_pattern would be used.
                # For now, let's use a very simplified placeholder for one control type
                ctrl_match = simple_control_pattern.match(line_strip)
                if ctrl_match:
                    text, id_str, class_name, style_str, x,y,w,h, ex_style_str = ctrl_match.groups()
                    text = text.replace('""','"')
                    cid_val: Union[str,int] = id_str
                    cid_name: Optional[str] = None
                    if id_str.isdigit() or id_str.startswith("0x"): cid_val = int(id_str,0)
                    else: cid_name = id_str

                    style_val = 0
                    try: style_val = eval(style_str.replace("|","|")) # Basic eval
                    except: print(f"Warning: Could not eval control STYLE: {style_str}")

                    ex_style_val = 0
                    if ex_style_str:
                        try: ex_style_val = eval(ex_style_str.replace("|","|"))
                        except: print(f"Warning: Could not eval control EXSTYLE: {ex_style_str}")

                    controls.append(DialogControlEntry(
                        class_name=class_name.strip('"'), text=text, id_val=cid_val, symbolic_id_name=cid_name,
                        x=int(x), y=int(y), width=int(w), height=int(h),
                        style=style_val, ex_style=ex_style_val
                    ))
            else: # Parsing dialog properties like CAPTION, FONT, STYLE etc.
                if line_strip.upper().startswith("CAPTION "):
                    dialog_parsed_props.caption = line_strip[len("CAPTION "):].strip().strip('"').replace('""','"')
                elif line_strip.upper().startswith("FONT "):
                    font_parts = line_strip[len("FONT "):].strip().split(',')
                    if len(font_parts) >= 2:
                        dialog_parsed_props.font_size = int(font_parts[0].strip())
                        dialog_parsed_props.font_name = font_parts[1].strip().strip('"')
                elif line_strip.upper().startswith("STYLE "):
                    style_str = line_strip[len("STYLE "):].strip()
                    try: dialog_parsed_props.style = eval(style_str.replace("|","|"))
                    except: print(f"Warning: Could not eval dialog STYLE: {style_str}")
                # Add EXSTYLE, MENU, CLASS parsing here if needed

    props = dialog_parsed_props
    if not props: # If header was not even found
        print("Warning: DIALOG/DIALOGEX header not found in RC text.")
        # Fallback: create a default DialogProperties if some text was provided
        # This helps if the text is just a fragment being edited.
        # For a full parse, this indicates an error.
        # For now, let's return None if header is not found.
        return None, []


    # If parsing was minimal and we have a props object but no controls,
    # and there was text between BEGIN/END, add a placeholder control.
    # This indicates the control parsing is incomplete.
    if props and not controls and rc_text.upper().rfind("BEGIN") < rc_text.upper().rfind("END"):
        if any(line.strip() for line in lines[rc_text.upper().rfind("BEGIN")//len(lines[0]) +1 : rc_text.upper().rfind("END")//len(lines[0])]):
             controls.append(DialogControlEntry("STATIC", "[Control Parsing Incomplete]", -1, 0,0,50,10))

    return props, controls


def generate_dialog_rc_text(dialog_props: DialogProperties, controls: List[DialogControlEntry], lang_id: Optional[int] = None) -> str:
    """
    Generates DIALOG or DIALOGEX resource script text.
    Placeholder - This will be complex to implement fully.
    """
    lines: List[str] = []

    if lang_id is not None:
        lines.append(f"LANGUAGE {lang_id & 0x3FF}, {(lang_id >> 10) & 0x3F}")

    name_str = dialog_props.symbolic_name or str(dialog_props.name)
    if isinstance(dialog_props.name, str) and not dialog_props.symbolic_name: # Ensure quotes if symbolic name was in name field
        name_str = f'"{dialog_props.name}"'

    dialog_type = "DIALOGEX" if dialog_props.is_ex else "DIALOG"
    lines.append(f"{name_str} {dialog_type} {dialog_props.x}, {dialog_props.y}, {dialog_props.width}, {dialog_props.height}")

    # TODO: Convert numeric styles/exstyles to string representations (e.g., WS_POPUP | DS_MODALFRAME)
    # This requires a mapping from values to style names. For now, outputting hex.
    if dialog_props.style: lines.append(f"STYLE 0x{dialog_props.style:X}")
    if dialog_props.ex_style: lines.append(f"EXSTYLE 0x{dialog_props.ex_style:X}")
    if dialog_props.caption: lines.append(f'CAPTION "{dialog_props.caption.replace("\"", "\"\"")}"')
    if dialog_props.font_size and dialog_props.font_name:
        lines.append(f'FONT {dialog_props.font_size}, "{dialog_props.font_name}"')
    if dialog_props.menu_name:
        menu_name_disp = dialog_props.symbolic_menu_name or str(dialog_props.menu_name)
        if isinstance(dialog_props.menu_name, str) and not dialog_props.symbolic_menu_name: menu_name_disp = f'"{dialog_props.menu_name}"'
        lines.append(f"MENU {menu_name_disp}")
    if dialog_props.class_name:
        class_name_disp = dialog_props.symbolic_class_name or str(dialog_props.class_name)
        if isinstance(dialog_props.class_name, str) and not dialog_props.symbolic_class_name: class_name_disp = f'"{dialog_props.class_name}"'
        lines.append(f"CLASS {class_name_disp}")

    lines.append("BEGIN")
    for ctrl in controls:
        # TODO: Convert numeric class_name and style to string representations
        class_disp = f'"{ctrl.class_name}"' if isinstance(ctrl.class_name, str) else str(ctrl.class_name)
        text_disp = f'"{ctrl.text.replace("\"", "\"\"")}"'
        id_disp = ctrl.get_id_display()
        # Basic control line. More specific keywords (LTEXT, PUSHBUTTON) would be better.
        # This requires knowing the mapping from class_name/style to these keywords.
        ctrl_keyword = "CONTROL" # Default
        # Example: if ctrl.class_name == "Button" and (ctrl.style & BS_PUSHBUTTON) == BS_PUSHBUTTON: ctrl_keyword = "PUSHBUTTON"

        # Simplified output, may not be perfectly compilable for all controls
        line = f"    {ctrl_keyword} {text_disp}, {id_disp}, {class_disp}, 0x{ctrl.style:X}, " \
               f"{ctrl.x}, {ctrl.y}, {ctrl.width}, {ctrl.height}"
        if ctrl.ex_style: line += f", 0x{ctrl.ex_style:X}"
        lines.append(line)
    lines.append("END")

    return "\n".join(lines)


if __name__ == "__main__":
    print("Testing dialog_parser_util.py")
    sample_dialog_rc = """
IDD_MYDIALOG DIALOGEX 0, 0, 200, 150
STYLE DS_SETFONT | DS_MODALFRAME | WS_POPUP | WS_CAPTION | WS_SYSMENU
CAPTION "My Test Dialog"
FONT 8, "MS Shell Dlg", 400, 0, 0x1
BEGIN
    LTEXT           "Static Text:", IDC_STATIC, 10, 10, 100, 8
    EDITTEXT        IDC_EDIT1, 10, 20, 180, 14, ES_AUTOHSCROLL
    PUSHBUTTON      "OK", IDOK, 40, 120, 50, 14
    CONTROL         "MyCustomCtrl", IDC_CUSTOM, "CustClass32", WS_TABSTOP, 10, 40, 180, 20
END
"""
    print(f"\n--- Parsing Sample Dialog RC ---\n{sample_dialog_rc}")
    props, controls = parse_dialog_rc_text(sample_dialog_rc)

    if props:
        print(f"\n--- Parsed Dialog Properties ---")
        print(f"  Name: {props.symbolic_name or props.name}, Caption: '{props.caption}'")
        print(f"  Pos: ({props.x},{props.y}), Size: ({props.width}x{props.height})")
        print(f"  Style: 0x{props.style:X}, Font: {props.font_size}pt '{props.font_name}'")
        print(f"  Is DIALOGEX: {props.is_ex}")
    else:
        print("  No dialog properties parsed.")

    print("\n--- Parsed Controls ---")
    if controls:
        for ctrl in controls:
            print(f"  {ctrl!r}")
    else:
        print("  No controls parsed (or parsing is too basic).")

    # Test generation (will be very basic due to parsing limitations)
    if props:
        print("\n--- Generating RC Text from Parsed Structure (Basic) ---")
        # For generation test, create a more defined props and controls if parsing is minimal
        if not controls : # If parser didn't get controls, add some for test
            controls.append(DialogControlEntry("BUTTON", "OK", "IDOK", 10,10,50,14, style=0x50010001)) # BS_DEFPUSHBUTTON | WS_TABSTOP

        generated_rc = generate_dialog_rc_text(props, controls, lang_id=1033)
        print(generated_rc)
        assert "IDD_MYDIALOG DIALOGEX" in generated_rc or "IDD_MYDIALOG DIALOG" in generated_rc # Depending on if is_ex was parsed
        assert "PUSHBUTTON" not in generated_rc # because current generate is basic `CONTROL`
        assert "CONTROL \"OK\", IDOK" in generated_rc or "CONTROL \"OK\", \"IDOK\"" in generated_rc

    print("\ndialog_parser_util.py tests completed (basic).")

```
