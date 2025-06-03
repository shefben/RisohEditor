import re
from typing import List, Optional, Tuple, Union

# Accelerator flags (from fVirt field of ACCELTABLEENTRY)
FVIRTKEY = 0x01
FNOINVERT = 0x02 # For menu item accelerators
FSHIFT = 0x04
FCONTROL = 0x08
FALT = 0x10
ACCEL_LAST_ENTRY_FVIRT = 0x80 # Bit in fVirt indicating the last entry in the table (older format)
                               # Modern tables might just end, or have all-zero entry.

ACCEL_FLAG_MAP_TO_STR = {
    # FVIRTKEY is handled by "VIRTKEY" or "ASCII" text, not directly here for string list
    FSHIFT: "SHIFT",
    FCONTROL: "CONTROL",
    FALT: "ALT",
    FNOINVERT: "NOINVERT", # Rarely used as text in RC, but can be a flag
}

# Basic VK map for common keys. Can be expanded.
# Windows VK codes: https://docs.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes
VK_CODE_TO_STR_MAP = {
    0x08: "VK_BACK", 0x09: "VK_TAB", 0x0D: "VK_RETURN", 0x1B: "VK_ESCAPE",
    0x20: "VK_SPACE", 0x25: "VK_LEFT", 0x26: "VK_UP", 0x27: "VK_RIGHT", 0x28: "VK_DOWN",
    0x2C: "VK_SNAPSHOT", # Print Screen
    0x2D: "VK_INSERT", 0x2E: "VK_DELETE", 0x2F: "VK_HELP",
    # Digits 0-9 (same as ASCII '0'-'9')
    **{0x30 + i: str(i) for i in range(10)},
    # Characters A-Z (same as ASCII 'A'-'Z')
    **{0x41 + i: chr(ord('A') + i) for i in range(26)},
    # Function keys VK_F1 to VK_F24 (0x70 to 0x87)
    **{0x70 + i: f"VK_F{i+1}" for i in range(24)},
    0x90: "VK_NUMLOCK", 0x91: "VK_SCROLL",
    # More can be added: VK_LSHIFT, VK_RSHIFT, VK_LCONTROL, VK_RCONTROL, VK_LMENU, VK_RMENU
    # VK_OEM_1 (:;), VK_OEM_PLUS (+), VK_OEM_COMMA (,), VK_OEM_MINUS (-), VK_OEM_PERIOD (.)
    # VK_OEM_2 (/?), VK_OEM_3 (`~), VK_OEM_4 ([{), VK_OEM_5 (\|), VK_OEM_6 (]}), VK_OEM_7 ('")
}

def format_accel_key_event_str(key_code: int, fVirt_flags: int) -> str:
    """ Formats the key event information into a string representation for display or RC. """
    if not (fVirt_flags & FVIRTKEY): # ASCII key
        # For control characters in ASCII type, RC uses "^X" notation.
        # ASCII value for 'A' is 65. Ctrl+A is 1.
        if 1 <= key_code <= 26: # Ctrl+A to Ctrl+Z
            return f"^\"{chr(ord('A') + key_code - 1)}\"" # RC format often quotes the char
        return f'"{chr(key_code)}"' # Regular ASCII char, quoted in RC

    # VIRTKEY
    # Check for ^C, ^V, ^X style first if CONTROL flag is set
    # This is primarily for RC text generation, binary stores the VK code.
    # For display, if it's a common letter with CONTROL, we can show ^X.
    # However, a direct mapping from VK code is usually preferred for VIRTKEY type.
    # key_event_str in AcceleratorEntry should store what's in RC or the VK_ constant.
    # This function is more for *interpreting* binary to a displayable/RC-like key string.

    prefix = ""
    if fVirt_flags & FCONTROL: prefix += "^"
    # ALT and SHIFT are usually listed as flags, not part of key_event_str for VIRTKEYs
    # unless it's a specific notation like % for ALT (less common for accelerators).

    vk_str = VK_CODE_TO_STR_MAP.get(key_code)
    if vk_str:
        # If it's a simple char like 'A' that also has a VK_ code, and Control is pressed,
        # the RC text might be "^A". Otherwise, it's "VK_A".
        # This logic can get complex to exactly match RC syntax generation.
        # For binary parsing, just getting the VK_ constant is usually enough.
        if prefix and len(vk_str) == 1 and 'A' <= vk_str <= 'Z': # e.g. Control + A -> ^A
             return f"{prefix}\"{vk_str}\"" # Some RC formats quote it like "^A"
        return vk_str

    return str(key_code) # Fallback to numeric virtual key code if not in map

class AcceleratorEntry:
    def __init__(self, key_event_str: str, command_id: Union[int, str],
                 command_id_str: Optional[str] = None,
                 type_flags_str: Optional[List[str]] = None):
        self.key_event_str: str = key_event_str
        self.command_id: Union[int, str] = command_id
        self.command_id_str: Optional[str] = command_id_str

        self.type_flags_str: List[str] = []
        if type_flags_str:
            for flag in type_flags_str:
                if isinstance(flag, str):
                    self.type_flags_str.append(flag.upper().strip())

    def get_command_id_display(self) -> str:
        return self.command_id_str if self.command_id_str else str(self.command_id)

    def __repr__(self):
        return (f"AcceleratorEntry(key='{self.key_event_str}', cmd='{self.get_command_id_display()}', "
                f"flags={self.type_flags_str})")


def parse_accelerator_rc_text(rc_text: str) -> Tuple[Optional[Union[str, int]], List[AcceleratorEntry]]:
    entries: List[AcceleratorEntry] = []
    table_name_or_id: Optional[Union[str, int]] = None

    entry_pattern = re.compile(
        r'^\s*(\^?"[^A-Za-z0-9\s]"|\^?[A-Za-z0-9_#\.\-\+\^"]+|\S+)\s*,\s*'  # Key: Quoted char, VK_*, ^char, or other symbols
        r'([A-Za-z0-9_#\.]+)\s*'  # Command ID
        r'(?:,\s*(.*))?$',  # Optional flags string
        re.IGNORECASE
    )

    in_block = False
    for line in rc_text.splitlines():
        line_strip = line.strip()
        if not line_strip or line_strip.startswith("//") or line_strip.startswith("/*"):
            continue

        if line_strip.upper().startswith("ACCELERATORS "):
            header_match = re.match(r'^\s*([A-Za-z0-9_#\."\+\-\^]+)\s+ACCELERATORS\b', line_strip, re.IGNORECASE)
            if header_match:
                name_str = header_match.group(1).strip('"')
                if name_str.isdigit() or name_str.startswith("0x"): table_name_or_id = int(name_str,0)
                else: table_name_or_id = name_str
            continue

        if line_strip.upper() == "BEGIN": in_block = True; continue
        if line_strip.upper() == "END": in_block = False; break

        if in_block:
            match = entry_pattern.match(line_strip)
            if match:
                key_event_str = match.group(1).strip()
                command_id_str_from_rc = match.group(2).strip()
                flags_rc_str = match.group(3)

                cmd_id: Union[int, str]; cmd_id_symbolic: Optional[str] = None
                if command_id_str_from_rc.isdigit() or (command_id_str_from_rc.startswith("0x")):
                    try: cmd_id = int(command_id_str_from_rc, 0)
                    except ValueError: cmd_id = command_id_str_from_rc; cmd_id_symbolic = command_id_str_from_rc
                else: cmd_id = command_id_str_from_rc; cmd_id_symbolic = command_id_str_from_rc

                type_flags: List[str] = []
                if flags_rc_str:
                    type_flags = [f.strip().upper() for f in flags_rc_str.split(',') if f.strip()]

                # Ensure key_event_str is not double-quoted if it was already quoted
                if key_event_str.startswith('"') and key_event_str.endswith('"') and len(key_event_str) > 1:
                    key_event_str = key_event_str[1:-1]

                # Infer VIRTKEY if key is ^X or VK_ style and no ASCII flag
                is_virtkey_style_key = key_event_str.startswith("VK_") or key_event_str.startswith("^")
                if is_virtkey_style_key and "ASCII" not in type_flags and "VIRTKEY" not in type_flags:
                    type_flags.append("VIRTKEY")
                elif not is_virtkey_style_key and "VIRTKEY" not in type_flags and "ASCII" not in type_flags:
                    type_flags.append("ASCII") # Default for simple char keys

                entries.append(AcceleratorEntry(key_event_str, cmd_id, cmd_id_symbolic, type_flags))
    return table_name_or_id, entries


def generate_accelerator_rc_text(table_name_or_id: Union[str, int],
                                 entries: List[AcceleratorEntry],
                                 lang_id: Optional[int] = None) -> str:
    lines: List[str] = []
    if lang_id is not None: lines.append(f"LANGUAGE {lang_id & 0x3FF}, {(lang_id >> 10) & 0x3F}")
    name_str = f'"{table_name_or_id}"' if isinstance(table_name_or_id, str) and not table_name_or_id.isdigit() else str(table_name_or_id)
    lines.append(f"{name_str} ACCELERATORS")
    lines.append("BEGIN")
    for entry in entries:
        key_part = entry.key_event_str
        if len(entry.key_event_str) == 1 or entry.key_event_str.startswith("^"): # Quote single chars and ^X style
            key_part = f'"{entry.key_event_str}"'

        cmd_part = entry.get_command_id_display()
        # Filter out VIRTKEY/ASCII from flags list for RC text if it's implied by key_part
        # or if it's the default (ASCII for single char, VIRTKEY for VK_ or ^)
        flags_to_write = []
        is_vk_style = entry.key_event_str.startswith("VK_") or entry.key_event_str.startswith("^")
        explicit_ascii = "ASCII" in entry.type_flags_str
        explicit_virtkey = "VIRTKEY" in entry.type_flags_str

        for flag in entry.type_flags_str:
            if flag == "VIRTKEY" and is_vk_style and not explicit_ascii: continue # Implied
            if flag == "ASCII" and not is_vk_style and not explicit_virtkey: continue # Implied
            flags_to_write.append(flag)

        flags_part = ", ".join(flags_to_write) if flags_to_write else ""
        line = f"    {key_part}, {cmd_part}"
        if flags_part: line += f", {flags_part}"
        lines.append(line)
    lines.append("END")
    return "\n".join(lines)


if __name__ == '__main__':
    print("Testing accelerator_parser_util.py")
    # ... (existing tests) ...
    # Test format_accel_key_event_str
    assert format_accel_key_event_str(ord('A'), 0) == '"A"' # ASCII 'A'
    assert format_accel_key_event_str(1, 0) == '"^A"' # ASCII Ctrl+A
    assert format_accel_key_event_str(0x70, FVIRTKEY) == "VK_F1" # VIRTKEY F1
    assert format_accel_key_event_str(ord('B'), FVIRTKEY | FCONTROL) == "^\"B\"" # VIRTKEY Ctrl+B (becomes "^B" in RC)

    sample_rc = 'IDA_ACCEL ACCELERATORS\nBEGIN\n  "A", 101, ASCII, ALT\n  VK_F2, 102, VIRTKEY\n  "^C", 103\nEND'
    name, ents = parse_accelerator_rc_text(sample_rc)
    assert name == "IDA_ACCEL"
    assert len(ents) == 3
    if ents:
        assert ents[0].key_event_str == "A"
        assert "ASCII" in ents[0].type_flags_str
        assert ents[2].key_event_str == "^C"
        assert "VIRTKEY" in ents[2].type_flags_str # Implicit VIRTKEY

    generated = generate_accelerator_rc_text(name, ents)
    print("\nGenerated from parsed:\n", generated)
    assert '"A", 101, ASCII, ALT' in generated
    assert 'VK_F2, 102, VIRTKEY' in generated
    assert '"^C", 103, VIRTKEY' in generated # VIRTKEY added back

    print("\naccelerator_parser_util.py tests completed.")


