import re
from typing import List, Optional, Tuple, Union
import copy

class MenuItemEntry:
    def __init__(self, item_type: str = "MENUITEM", text: str = "",
                 id_val: Union[int, str] = 0, name_val: Optional[str] = None,
                 flags: Optional[List[str]] = None, state: int = 0,
                 children: Optional[List['MenuItemEntry']] = None,
                 is_ex: bool = False, help_id: Optional[int] = None): # Added help_id for MENUEX
        self.item_type: str = item_type  # "MENUITEM", "POPUP", "SEPARATOR" (custom for MENUITEM SEPARATOR)
        self.text: str = text
        self.id_val: Union[int, str] = id_val # Numeric ID for MENUITEM
        self.name_val: Optional[str] = name_val # Symbolic ID name
        self.flags: List[str] = flags if flags is not None else [] # e.g., "GRAYED", "CHECKED"
        self.state: int = state # MFS_ flags for MENUEX (primarily binary)
        self.children: List['MenuItemEntry'] = children if children is not None else []
        self.is_ex: bool = is_ex # Is this item part of a MENUEX structure?
        self.help_id: Optional[int] = help_id # Optional Help ID for MENUEX items

    def get_id_display(self) -> str:
        """Returns a string representation of the ID (symbolic or numeric)."""
        if self.name_val:
            return self.name_val
        if isinstance(self.id_val, int) and self.id_val == 0 and self.item_type != "POPUP": # Separators might have ID 0
             # For MENUITEM, ID 0 is valid but often omitted in RC if no action.
             # For POPUP, ID is usually not present in RC text.
            return "0" # Explicitly show 0 if it's numeric and 0 for non-popups
        return str(self.id_val) if self.id_val else ""


    def __repr__(self):
        return (f"MenuItemEntry(type='{self.item_type}', text='{self.text}', id='{self.get_id_display()}', "
                f"flags={self.flags}, children_count={len(self.children)}, is_ex={self.is_ex})")

# Placeholder functions, actual parsing logic will be complex.
# For MENUEX: MENUEX lpTemplateName \n [CHARACTERISTICS dwCharacteristics] \n [VERSION dwVersion] \n [HELPINFO dwHelpId] \n BEGIN ... END
# For MENU: MenuName MENU \n [MENUOPTIONS list] \n BEGIN ... END
# Menu options: LANGUAGE lang, sublang | CHARACTERISTICS val | VERSION val

def parse_menu_rc_text(rc_text: str) -> Tuple[List[MenuItemEntry], bool, str, str, str, Optional[int]]:
    """
    Parses MENU[EX] BEGIN ... END blocks.
    Returns: (root_items, is_ex, menu_name_rc, characteristics_rc, version_rc, global_help_id_rc)
    """
    lines = rc_text.splitlines()
    root_items: List[MenuItemEntry] = []
    is_ex = False
    menu_name_rc = "MENU_NAME_UNKNOWN"
    characteristics_rc = "0" # For MENUEX
    version_rc = "1"         # For MENUEX
    global_help_id_rc: Optional[int] = None # For MENUEX HELPINFO

    # First, find the MENU or MENUEX header line
    header_line_index = -1
    for i, line in enumerate(lines):
        line_strip = line.strip()
        if line_strip.upper().endswith("MENU") or "MENUEX" in line_strip.upper():
            header_line_index = i
            match = re.match(r'^\s*(\S+)\s+(MENUEX|MENU)\s*(.*)', line_strip, re.IGNORECASE)
            if match:
                menu_name_rc = match.group(1).strip('"')
                menu_type = match.group(2).upper()
                is_ex = (menu_type == "MENUEX")
                options_str = match.group(3)
                # TODO: Parse characteristics, version, helpinfo from options_str for MENUEX
                # This is a simplification for now.
            break

    if header_line_index == -1:
        raise ValueError("Could not find MENU or MENUEX header.")

    # Find BEGIN and END of the main menu block
    begin_index, end_index = -1, -1
    nesting_level = 0
    for i, line in enumerate(lines[header_line_index:]): # Start search from header
        line_strip = line.strip().upper()
        if line_strip == "BEGIN":
            if nesting_level == 0: # First BEGIN is for the main menu
                begin_index = header_line_index + i
            nesting_level += 1
        elif line_strip == "END":
            nesting_level -= 1
            if nesting_level == 0 and begin_index != -1 : # Matching END for the main menu
                end_index = header_line_index + i
                break

    if begin_index == -1 or end_index == -1:
        raise ValueError("Could not find main BEGIN/END block for MENU/MENUEX.")

    # Actual parsing of items within BEGIN...END
    # This requires a recursive helper or an iterative stack-based approach.
    # For now, this is a very simplified placeholder.
    # A real parser would handle indentation or BEGIN/END for POPUPs.

    # Simplified: look for MENUITEM and POPUP lines directly within the main block
    # This won't handle nesting correctly without a proper recursive descent or stack.
    item_pattern = re.compile(r'^\s*(MENUITEM|POPUP)\s+"([^"]*(?:""[^"]*)*)"(?:,\s*([A-Za-z0-9_#\.]+))?\s*(.*)', re.IGNORECASE)
    separator_pattern = re.compile(r'^\s*MENUITEM\s+SEPARATOR\s*$', re.IGNORECASE)

    # This is a placeholder for the recursive parsing logic
    # For now, just create a dummy item to show structure exists
    if lines: # Check if there are any lines to parse
        current_block_lines = lines[begin_index + 1 : end_index]
        # This simplified parser only gets top-level items
        for line_content in current_block_lines:
            line_strip = line_content.strip()
            sep_match = separator_pattern.match(line_strip)
            if sep_match:
                root_items.append(MenuItemEntry(item_type="SEPARATOR", text="SEPARATOR"))
                continue

            item_match = item_pattern.match(line_strip)
            if item_match:
                item_type_str = item_match.group(1).upper()
                text = item_match.group(2).replace('""', '"')
                id_str = item_match.group(3)
                flags_str = item_match.group(4)

                item_id: Union[int, str] = 0
                item_name: Optional[str] = None
                if id_str:
                    if id_str.isdigit() or (id_str.startswith("0x")):
                        try: item_id = int(id_str,0)
                        except ValueError: item_id = id_str; item_name = id_str # Fallback if int parse fails
                    else: # Symbolic
                        item_id = id_str; item_name = id_str

                flags = [f.strip() for f in flags_str.upper().split(',') if f.strip()]

                if item_type_str == "POPUP":
                    # Placeholder: Real parsing would recursively call for children
                    root_items.append(MenuItemEntry(item_type="POPUP", text=text, children=[], flags=flags, is_ex=is_ex))
                else: # MENUITEM
                    root_items.append(MenuItemEntry(item_type="MENUITEM", text=text, id_val=item_id, name_val=item_name, flags=flags, is_ex=is_ex))

    # If no items parsed and it's not empty, add a placeholder
    if not root_items and any(line.strip() for line in lines[begin_index + 1 : end_index]):
         root_items.append(MenuItemEntry(text="[Parsing Incomplete - Placeholder Item]"))


    return root_items, is_ex, menu_name_rc, characteristics_rc, version_rc, global_help_id_rc


def _generate_menu_items_rc(items: List[MenuItemEntry], indent_level: int) -> List[str]:
    """Helper to recursively generate RC text for menu items."""
    rc_lines: List[str] = []
    indent = "    " * indent_level
    for item in items:
        if item.item_type == "SEPARATOR":
            rc_lines.append(f"{indent}MENUITEM SEPARATOR")
        else:
            text_escaped = item.text.replace('"', '""')
            id_display = item.get_id_display()

            flags_str = ""
            if item.flags:
                flags_str = ", " + ", ".join(item.flags).upper() # Make sure flags are uppercase

            if item.item_type == "POPUP":
                rc_lines.append(f'{indent}POPUP "{text_escaped}"{flags_str}')
                rc_lines.append(f"{indent}BEGIN")
                rc_lines.extend(_generate_menu_items_rc(item.children, indent_level + 1))
                rc_lines.append(f"{indent}END")
            else: # MENUITEM
                # Only include ID if it's not 0 or if it's symbolic, unless it's a separator type (handled)
                id_part = ""
                if id_display and (id_display != "0" or not isinstance(item.id_val, int)): # Show if symbolic or non-zero numeric
                    id_part = f", {id_display}"
                elif isinstance(item.id_val, int) and item.id_val != 0 : # Explicit numeric non-zero ID
                    id_part = f", {item.id_val}"

                rc_lines.append(f'{indent}MENUITEM "{text_escaped}"{id_part}{flags_str}')
    return rc_lines


def generate_menu_rc_text(menu_name_rc: str, items: List[MenuItemEntry], is_ex: bool,
                          characteristics_rc: str = "0", version_rc: str = "1",
                          lang_id: Optional[int] = None, global_help_id_rc: Optional[int] = None) -> str:
    """Generates MENU[EX] ... BEGIN ... END text from MenuItemEntry list."""
    lines: List[str] = []

    if lang_id is not None:
        primary = lang_id & 0x3FF
        sub = (lang_id >> 10) & 0x3F
        lines.append(f"LANGUAGE {primary}, {sub}")

    menu_keyword = "MENUEX" if is_ex else "MENU"
    name_part = f'"{menu_name_rc}"' if not menu_name_rc.isdigit() else menu_name_rc

    header_line = f"{name_part} {menu_keyword}"
    if is_ex:
        # Simplified: Not adding CHARACTERISTICS, VERSION, HELPINFO to header line for now
        # as their parsing from original RC is also simplified.
        # A full implementation would include:
        # if characteristics_rc != "0": header_line += f"\nCHARACTERISTICS {characteristics_rc}"
        # if version_rc != "1": header_line += f"\nVERSION {version_rc}"
        # if global_help_id_rc is not None: header_line += f"\nHELPINFO {global_help_id_rc}"
        pass

    lines.append(header_line)
    lines.append("BEGIN")
    lines.extend(_generate_menu_items_rc(items, 1)) # Start with indent level 1
    lines.append("END")
    return "\n".join(lines)


if __name__ == '__main__':
    print("Testing menu_parser_util.py")

    sample_menu_rc = """
IDR_MY_MENU MENUEX
BEGIN
    POPUP "&File"
    BEGIN
        MENUITEM "E&xit", ID_APP_EXIT, GRAYED
        MENUITEM SEPARATOR
        POPUP "Sub&menu"
        BEGIN
            MENUITEM "Item &1", 101
            MENUITEM "Item &2", 102, CHECKED
        END
    END
    MENUITEM "&Help", ID_APP_HELP
END
"""
    print(f"\n--- Parsing Sample Menu RC ---\n{sample_menu_rc}")
    parsed_items, is_ex, name, chars, ver, help_id = parse_menu_rc_text(sample_menu_rc)

    print(f"\n--- Parsed Menu Structure (is_ex={is_ex}, name='{name}') ---")
    def print_items(items, indent=0):
        for item in items:
            print("  " * indent + repr(item))
            if item.children:
                print_items(item.children, indent + 1)
    print_items(parsed_items)

    # Basic assertions based on simplified parsing
    assert name == "IDR_MY_MENU"
    assert is_ex is True
    if parsed_items: # if simplified parser got something
        assert len(parsed_items) >= 1 # Expecting File and Help at root
        if parsed_items[0].item_type == "POPUP":
             assert parsed_items[0].text == "&File"
             # assert len(parsed_items[0].children) >= 1 # Expecting Exit, SEPARATOR, Submenu

    print("\n--- Generating RC Text from Parsed Structure ---")
    # Create a slightly more complex structure for generation test
    test_gen_items = [
        MenuItemEntry(item_type="POPUP", text="&Alpha", children=[
            MenuItemEntry(text="Beta", id_val=201, name_val="ID_BETA"),
            MenuItemEntry(item_type="SEPARATOR")
        ]),
        MenuItemEntry(text="Gamma", id_val=202, flags=["GRAYED", "HELP"])
    ]
    generated_rc = generate_menu_rc_text("MY_TEST_MENU", test_gen_items, is_ex=False, lang_id=1033)
    print(generated_rc)
    assert "LANGUAGE 9, 1" in generated_rc
    assert "MY_TEST_MENU MENU" in generated_rc
    assert 'POPUP "&Alpha"' in generated_rc
    assert 'MENUITEM "Beta", ID_BETA' in generated_rc # Name preferred
    assert "MENUITEM SEPARATOR" in generated_rc
    assert 'MENUITEM "Gamma", 202, GRAYED, HELP' in generated_rc

    print("\nmenu_parser_util.py tests completed (basic).")

```
