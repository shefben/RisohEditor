import re
from typing import List, Optional, Tuple, Union

class AcceleratorEntry:
    def __init__(self, key_event_str: str, command_id: Union[int, str],
                 command_id_str: Optional[str] = None, # Symbolic name if command_id is int
                 type_flags_str: Optional[List[str]] = None): # e.g., ["VIRTKEY", "CONTROL", "SHIFT"]
        self.key_event_str: str = key_event_str  # e.g., "VK_F1", "^A", "a"
        self.command_id: Union[int, str] = command_id # Numeric or symbolic if not resolved
        self.command_id_str: Optional[str] = command_id_str # Explicit symbolic name for command_id

        # Ensure type_flags_str is a list of uppercase strings
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

# ACCELERATORS table_name
# BEGIN
#   key, command, [type] [,options...]
#   "A", ID_A_COMMAND, ASCII, SHIFT, CONTROL
#   VK_F1, ID_F1_COMMAND, VIRTKEY, ALT
#   "^C", ID_COPY_COMMAND   // Implicitly VIRTKEY
# END

def parse_accelerator_rc_text(rc_text: str) -> Tuple[Optional[Union[str, int]], List[AcceleratorEntry]]:
    """
    Parses ACCELERATORS resource script text.
    Returns (table_name_or_id, list_of_AcceleratorEntry).
    Table name is often not explicitly in the TextBlockResource.text_content directly,
    but is the name of the resource itself. This function focuses on BEGIN...END block.
    """
    entries: List[AcceleratorEntry] = []
    table_name_or_id: Optional[Union[str, int]] = None # Name is usually part of the resource identifier, not in this block

    # Simplified: Assume rc_text is the content between BEGIN and END, or includes it.
    # A more robust parser would handle the ACCELERATORS name BEGIN ... END structure.
    # This regex focuses on the entry lines.
    # Format: key, id, [type_flags...]
    # key: "c", VK_*, ^c
    # id: numeric or symbolic
    # type_flags: VIRTKEY, ASCII, SHIFT, CONTROL, ALT, NOINVERT
    # Example: "a", ID_CHAR_A, ASCII, SHIFT
    # Example: VK_DELETE, ID_DELETE, VIRTKEY
    # Example: "^X", ID_CUT_ACCEL // VIRTKEY implied

    # Regex to capture key, command ID, and optional flags string
    # Key can be quoted char, VK_ constant, or ^char.
    # Command ID is numeric or symbolic.
    # Flags are comma-separated strings.
    entry_pattern = re.compile(
        r'^\s*(\^"[A-Za-z]"|\^[@-\[\]\^_`]|[A-Za-z0-9_#\."\+\-\^]+)\s*,\s*'  # Key (Group 1)
        r'([A-Za-z0-9_#\.]+)\s*'  # Command ID (Group 2)
        r'(?:,\s*(.*))?$',  # Optional flags string (Group 3)
        re.IGNORECASE
    )

    in_block = False
    for line in rc_text.splitlines():
        line_strip = line.strip()
        if not line_strip or line_strip.startswith("//") or line_strip.startswith("/*"):
            continue

        if line_strip.upper().startswith("ACCELERATORS "): # Could extract name here if needed
            # Match for ACCELERATORS name BEGIN
            header_match = re.match(r'^\s*([A-Za-z0-9_#\."\+\-\^]+)\s+ACCELERATORS\b', line_strip, re.IGNORECASE)
            if header_match:
                name_str = header_match.group(1).strip('"')
                if name_str.isdigit() or name_str.startswith("0x"): table_name_or_id = int(name_str,0)
                else: table_name_or_id = name_str
            continue # Header line processed (or skipped if not perfectly matched)

        if line_strip.upper() == "BEGIN":
            in_block = True
            continue
        if line_strip.upper() == "END":
            in_block = False
            break

        if in_block:
            match = entry_pattern.match(line_strip)
            if match:
                key_event_str = match.group(1).strip()
                command_id_str_from_rc = match.group(2).strip()
                flags_rc_str = match.group(3)

                cmd_id: Union[int, str]
                cmd_id_symbolic: Optional[str] = None
                if command_id_str_from_rc.isdigit() or (command_id_str_from_rc.startswith("0x")):
                    try: cmd_id = int(command_id_str_from_rc, 0)
                    except ValueError: cmd_id = command_id_str_from_rc; cmd_id_symbolic = command_id_str_from_rc
                else:
                    cmd_id = command_id_str_from_rc # Store symbolic as main ID if not numeric
                    cmd_id_symbolic = command_id_str_from_rc

                type_flags: List[str] = []
                if flags_rc_str:
                    type_flags = [f.strip().upper() for f in flags_rc_str.split(',') if f.strip()]

                # Infer VIRTKEY if key is ^X or VK_ style and no ASCII flag
                is_virtkey_style_key = key_event_str.startswith("VK_") or key_event_str.startswith("^")
                if is_virtkey_style_key and "ASCII" not in type_flags and "VIRTKEY" not in type_flags:
                    type_flags.append("VIRTKEY")
                elif not is_virtkey_style_key and "VIRTKEY" not in type_flags and "ASCII" not in type_flags:
                    # If simple char like "a" and no explicit type, it's ASCII
                    type_flags.append("ASCII")


                entries.append(AcceleratorEntry(key_event_str.strip('"'), cmd_id, cmd_id_symbolic, type_flags))

    # If table_name_or_id wasn't found in header but we have entries, it's likely the resource name itself.
    # The caller (AcceleratorResource.parse_from_text_block) will use its own identifier.name for this.
    # So, we can return None for table_name_or_id if not explicitly found in the block itself.

    return table_name_or_id, entries


def generate_accelerator_rc_text(table_name_or_id: Union[str, int],
                                 entries: List[AcceleratorEntry],
                                 lang_id: Optional[int] = None) -> str:
    """Generates ACCELERATORS resource script text."""
    lines: List[str] = []

    if lang_id is not None:
        lines.append(f"LANGUAGE {lang_id & 0x3FF}, {(lang_id >> 10) & 0x3F}")

    name_str = f'"{table_name_or_id}"' if isinstance(table_name_or_id, str) and not table_name_or_id.isdigit() else str(table_name_or_id)
    lines.append(f"{name_str} ACCELERATORS")
    lines.append("BEGIN")
    for entry in entries:
        key_part = entry.key_event_str
        # RC files quote single characters or control char sequences like "^C"
        if len(entry.key_event_str) == 1 or entry.key_event_str.startswith("^"):
            key_part = f'"{entry.key_event_str}"'

        cmd_part = entry.get_command_id_display()
        flags_part = ", ".join(entry.type_flags_str) if entry.type_flags_str else ""

        line = f"    {key_part}, {cmd_part}"
        if flags_part:
            line += f", {flags_part}"
        lines.append(line)
    lines.append("END")
    return "\n".join(lines)


if __name__ == '__main__':
    print("Testing accelerator_parser_util.py")

    sample_accel_rc = """
IDA_MYACCEL ACCELERATORS
LANGUAGE 0, 0 // Optional language statement
BEGIN
    VK_F1, ID_HELP, VIRTKEY, CONTROL, SHIFT
    "a", ID_ACTION_A, ASCII, ALT
    "^C", ID_COPY_COMMAND // Implicit VIRTKEY
    "B", ID_B_COMMAND, ASCII // ASCII explicit
    VK_DELETE, ID_DO_DELETE // VIRTKEY implied by VK_
END
"""
    print(f"\n--- Parsing Sample Accelerator RC ---\n{sample_accel_rc}")
    name, parsed_entries = parse_accelerator_rc_text(sample_accel_rc)

    print(f"\n--- Parsed Accelerator Table (Name: {name}) ---")
    for entry in parsed_entries:
        print(entry)

    assert name == "IDA_MYACCEL"
    assert len(parsed_entries) == 5
    if len(parsed_entries) == 5:
        assert parsed_entries[0].key_event_str == "VK_F1"
        assert parsed_entries[0].command_id_str == "ID_HELP"
        assert "VIRTKEY" in parsed_entries[0].type_flags_str and "CONTROL" in parsed_entries[0].type_flags_str

        assert parsed_entries[2].key_event_str == "^C" # Not quoted in AcceleratorEntry
        assert "VIRTKEY" in parsed_entries[2].type_flags_str # Implicit

        assert parsed_entries[4].key_event_str == "VK_DELETE"
        assert "VIRTKEY" in parsed_entries[4].type_flags_str

    print("\n--- Generating RC Text from Parsed Structure ---")
    if name and parsed_entries: # Check if parsing was successful enough
        generated_rc = generate_accelerator_rc_text(name, parsed_entries, lang_id=1033)
        print(generated_rc)
        assert "LANGUAGE 9, 1" in generated_rc
        assert "IDA_MYACCEL ACCELERATORS" in generated_rc
        assert '"^C", ID_COPY_COMMAND, VIRTKEY' in generated_rc or '"^C", ID_COPY_COMMAND, VIRTKEY' in generated_rc # Order of flags might vary
        assert '    VK_F1, ID_HELP, VIRTKEY, CONTROL, SHIFT' in generated_rc # Flags order should be preserved if possible, or normalized.

    print("\naccelerator_parser_util.py tests completed.")

```
