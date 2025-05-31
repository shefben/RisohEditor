import re
from collections import namedtuple
from typing import List, Optional, Union

# Using a simple class for StringTableEntry to potentially add methods later
class StringTableEntry:
    def __init__(self, id_val: Union[int, str], value_str: str, name_val: Optional[str] = None):
        self.id_val: Union[int, str] = id_val # Numeric ID or symbolic name as string
        self.value_str: str = value_str
        # self.name_val is kept for potential future use if IDs are symbolic AND have a numeric equivalent.
        # For typical RC STRINGTABLE, the first part is the ID (numeric or symbolic)
        # and name_val is not explicitly a separate entity in the line.
        # If id_val is symbolic, name_val could be that symbol. If id_val is numeric, name_val is None.
        if isinstance(id_val, str) and not id_val.isdigit():
            self.name_val = id_val # Store symbolic ID as name_val
        else: # id_val is numeric or a string of digits
            self.name_val = name_val


    def __repr__(self):
        return f"StringTableEntry(id_val={self.id_val!r}, value_str={self.value_str!r}, name_val={self.name_val!r})"

    @property
    def display_id(self) -> str:
        """Returns the ID in a format suitable for display or RC generation."""
        if self.name_val and not isinstance(self.id_val, int): # Prefer name_val if it's the symbolic ID
            return self.name_val
        return str(self.id_val)


def parse_stringtable_rc_text(rc_text: str) -> List[StringTableEntry]:
    """
    Parses lines within a STRINGTABLE BEGIN ... END block.
    Expected format:
    STRINGTABLE [options]
    BEGIN
        ID_STRING_SOMETHING, "My String Value"
        12345, "Another String on Next Line"
        // Comments are ignored by mcpp usually, but good to be aware.
        /* Multi-line comments */
    END
    """
    entries: List[StringTableEntry] = []
    # Regex to capture:
    # Group 1: ID (numeric or symbolic like IDS_MY_STRING)
    # Group 2: Quoted string value (handles escaped quotes inside)
    # Example: IDS_MY_STRING, "Hello, ""World""!"
    # Example: 123, "Some text"
    # Pattern needs to be careful with commas inside strings if not handled by simple splitting.
    # This regex assumes one entry per line, after BEGIN and before END.
    # It tries to match ID, comma, then a quoted string.
    # The string part "([^"]*(?:""[^"]*)*)" handles escaped double quotes ("").
    entry_pattern = re.compile(r'^\s*([A-Za-z0-9_#\.]+)\s*,\s*\"((?:[^\"]|\"\")*)\"\s*$', re.UNICODE)

    in_begin_end_block = False
    for line in rc_text.splitlines():
        line_upper = line.strip().upper()
        if line_upper == "BEGIN":
            in_begin_end_block = True
            continue
        if line_upper == "END":
            in_begin_end_block = False
            continue
        if not in_begin_end_block or not line.strip() or line.strip().startswith("//") or line.strip().startswith("/*"):
            continue

        match = entry_pattern.match(line.strip())
        if match:
            id_str, value_str = match.groups()

            # Unescape "" to " within the value string
            value_str = value_str.replace('""', '"')

            # Determine if ID is numeric or symbolic
            id_val: Union[int, str]
            name_val_for_entry: Optional[str] = None
            if id_str.isdigit() or (id_str.startswith("0x") and all(c in "0123456789abcdefABCDEF" for c in id_str[2:])):
                try:
                    id_val = int(id_str, 0) # Handles decimal, hex
                except ValueError: # Should not happen due to isdigit/ishex check, but as fallback
                    id_val = id_str
                    name_val_for_entry = id_str
            else: # Symbolic ID
                id_val = id_str # Store the symbolic string as the primary ID for now
                name_val_for_entry = id_str

            entries.append(StringTableEntry(id_val=id_val, value_str=value_str, name_val=name_val_for_entry))
        # else:
            # print(f"DEBUG: Line did not match string table entry pattern: '{line.strip()}'")

    return entries


def generate_stringtable_rc_text(entries: List[StringTableEntry], lang_id: Optional[int] = None) -> str:
    """
    Generates the STRINGTABLE RC text block from a list of StringTableEntry.
    Optionally includes a LANGUAGE directive if lang_id is provided.
    """
    lines = []
    if lang_id is not None: # Add LANGUAGE statement if provided
        primary = lang_id & 0x3FF
        sub = (lang_id >> 10) & 0x3F
        lines.append(f"LANGUAGE {primary}, {sub}")

    lines.append("STRINGTABLE")
    lines.append("BEGIN")
    for entry in entries:
        # Escape " to "" for RC format within the value string
        escaped_value = entry.value_str.replace('"', '""')
        # Use entry.display_id for the ID part
        lines.append(f"    {entry.display_id}, \"{escaped_value}\"")
    lines.append("END")
    return "\n".join(lines)


if __name__ == '__main__':
    print("Testing rc_parser_util.py")

    # Test parsing
    sample_rc_block_text = """
LANGUAGE 9, 1
STRINGTABLE PRELOAD DISCARDABLE
BEGIN
    IDS_APP_TITLE, "My Application"
    IDS_GREETING, "Hello, ""User""!"
    103, "Another string with ID."
    // This is a comment line inside
    IDS_WITH_DOTS.AND_MORE, "Value for dotted ID"
    0x7B, "Hex ID String"    // 7B hex is 123 decimal
END
"""
    parsed_entries = parse_stringtable_rc_text(sample_rc_block_text)
    print("\n--- Parsed Entries ---")
    for entry in parsed_entries:
        print(entry)
        assert isinstance(entry.id_val, (str, int))
        assert isinstance(entry.value_str, str)

    assert len(parsed_entries) == 5
    assert parsed_entries[0].id_val == "IDS_APP_TITLE"
    assert parsed_entries[0].value_str == "My Application"
    assert parsed_entries[1].value_str == 'Hello, "User"!'
    assert parsed_entries[2].id_val == 103
    assert parsed_entries[3].id_val == "IDS_WITH_DOTS.AND_MORE"
    assert parsed_entries[4].id_val == 0x7B # Stored as int

    # Test generation
    print("\n--- Generated RC Text (from parsed) ---")
    generated_text = generate_stringtable_rc_text(parsed_entries, lang_id=0x0409) # English US
    print(generated_text)
    assert "LANGUAGE 9, 1" in generated_text # Check for language statement
    assert 'IDS_APP_TITLE, "My Application"' in generated_text
    assert 'IDS_GREETING, "Hello, ""User""!"' in generated_text # Quotes should be re-escaped
    assert '103, "Another string with ID."' in generated_text
    assert '123, "Hex ID String"' in generated_text # 0x7B becomes 123 when str(int_id) used by display_id

    # Test generation with mixed ID types, some numeric strings
    test_entries_for_gen = [
        StringTableEntry(id_val="IDS_SYMBOL", value_str="Symbolic"),
        StringTableEntry(id_val=123, value_str="Numeric"),
        StringTableEntry(id_val="456", value_str="Numeric String", name_val="IDS_NUM_STR"), # name_val should be preferred if id_val is not int
        StringTableEntry(id_val="IDS_SYMBOL_WITH_NUMERIC_NAME", value_str="Symbolic with name", name_val="IDS_SYMBOL_WITH_NUMERIC_NAME"),
    ]
    test_entries_for_gen[2].id_val = 456 # Correcting after init if id_val was string but numeric

    print("\n--- Generated RC Text (custom entries) ---")
    generated_custom_text = generate_stringtable_rc_text(test_entries_for_gen)
    print(generated_custom_text)
    assert 'IDS_SYMBOL, "Symbolic"' in generated_custom_text
    assert '123, "Numeric"' in generated_custom_text
    assert '456, "Numeric String"' in generated_custom_text # name_val 'IDS_NUM_STR' not used as id_val is int
    assert 'IDS_SYMBOL_WITH_NUMERIC_NAME, "Symbolic with name"' in generated_custom_text


    print("\nAll rc_parser_util.py tests passed.")

```
