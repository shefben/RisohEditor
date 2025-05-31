# src/core/rc_parser.py

from typing import List, Optional, Tuple
import os
import re

from .resource_base import (
    Resource, ResourceIdentifier, FileResource, TextBlockResource,
    LANG_NEUTRAL, RT_ICON, RT_BITMAP, RT_CURSOR, RT_HTML, RT_MANIFEST,
    RT_DLGINCLUDE, RT_FONT, RT_PLUGPLAY, RT_VXD, RT_ANICURSOR, RT_ANIICON,
    RT_MENU, RT_DIALOG, RT_STRING, RT_ACCELERATOR, RT_RCDATA, RT_VERSION
    # Note: RT_TOOLBAR, RT_TYPELIB are not standard integer constants.
    # They are usually strings in RC files, e.g., "TOOLBAR" or custom numeric type.
)
from ..utils.external_tools import run_mcpp, MCPPError

# Mapping of RC type strings to our RT_ constants (integer IDs)
# This helps standardize the type_id in ResourceIdentifier.
# Not all RC types have predefined integer constants (e.g., "TOOLBAR").
# For those, we might use a hash or a custom scheme if an integer ID is strictly needed,
# or store the string type directly in ResourceIdentifier if we adapt it.
# For now, let's focus on those with existing RT_ constants.
RC_TYPE_TO_RT_ID = {
    "ICON": RT_ICON,
    "BITMAP": RT_BITMAP,
    "CURSOR": RT_CURSOR,
    "HTML": RT_HTML,
    "MANIFEST": RT_MANIFEST,
    "DLGINCLUDE": RT_DLGINCLUDE,
    "FONT": RT_FONT,
    "PLUGPLAY": RT_PLUGPLAY,
    "VXD": RT_VXD,
    "ANICURSOR": RT_ANICURSOR,
    "ANIICON": RT_ANIICON,
    "MENU": RT_MENU,
    "DIALOG": RT_DIALOG,
    "DIALOGEX": RT_DIALOG, # DIALOGEX is an extended DIALOG
    "STRINGTABLE": RT_STRING,
    "ACCELERATORS": RT_ACCELERATOR,
    "RCDATA": RT_RCDATA,
    "VERSIONINFO": RT_VERSION,
    # "TOOLBAR": Some custom ID or handle as string type.
    # "TYPELIB": Some custom ID or handle as string type.
}
# Resource types that are defined by referencing a file path
FILE_RESOURCE_TYPES = {
    "ICON", "BITMAP", "CURSOR", "HTML", "MANIFEST", "DLGINCLUDE",
    "FONT", "PLUGPLAY", "VXD", "ANICURSOR", "ANIICON",
    "TOOLBAR", "TYPELIB" # These often reference files too.
}
# Resource types that are defined by a BEGIN...END block
BLOCK_RESOURCE_TYPES = {
    "MENU", "MENUEX", "DIALOG", "DIALOGEX", "STRINGTABLE",
    "ACCELERATORS", "VERSIONINFO", "RCDATA"
    # HTML and other custom types can also be in blocks.
}


class RCParser:
    def __init__(self, mcpp_path: str = "mcpp.exe", include_paths: Optional[List[str]] = None, encoding: str = 'utf-8'):
        self.mcpp_path = mcpp_path
        self.include_paths = include_paths if include_paths is not None else []
        self.encoding = encoding # Encoding of the RC file itself
        self.resources: List[Resource] = []
        self.current_language: int = LANG_NEUTRAL # Default: LANGID(LANG_NEUTRAL, SUBLANG_NEUTRAL)
        self.rc_file_directory: str = "" # Base directory of the currently parsed RC file

    def _parse_name_id(self, name_id_str: str) -> any:
        """Converts a string name/ID to int if numeric, else returns string."""
        if name_id_str.isdigit() or (name_id_str.startswith("0x") and all(c in "0123456789abcdefABCDEF" for c in name_id_str[2:])):
            try:
                return int(name_id_str, 0) # Automatically handles decimal, hex (0x)
            except ValueError:
                return name_id_str.strip('"') # Fallback to string if somehow not parsable as int
        return name_id_str.strip('"') # Remove quotes for string names

    def _parse_language_statement(self, line: str):
        # LANGUAGE lang, sublang
        # Example: LANGUAGE LANG_ENGLISH, SUBLANG_ENGLISH_US
        # Example: LANGUAGE 0x09, 0x01
        # These symbolic names need to be resolved to integer values.
        # This is a complex part, as it requires a map of LANG_xxx/SUBLANG_xxx to numbers.
        # For now, we'll assume numeric or skip if symbolic and unresolved.
        match = re.match(r"LANGUAGE\s+([A-Za-z0-9_]+)\s*,\s*([A-Za-z0-9_]+)", line, re.IGNORECASE)
        if match:
            lang_str, sublang_str = match.groups()
            try:
                # Attempt to convert, assuming they might be numeric (decimal or hex)
                primary_lang = int(lang_str, 0)
                sub_lang = int(sublang_str, 0)
                # MAKELANGID macro: (sublang << 10) | primary_lang
                self.current_language = (sub_lang << 10) | primary_lang
                # print(f"Debug: Language set to {self.current_language} (Primary: {primary_lang}, Sub: {sub_lang}) from '{line}'")
            except ValueError:
                # If symbolic names are used (e.g., LANG_ENGLISH), we need a lookup table.
                # This is a simplification for now.
                print(f"Warning: Symbolic language names '{lang_str}', '{sublang_str}' require a lookup table. Language context may be incorrect.")
                # Fallback or keep previous language. For now, we'll keep the previous.

    def _parse_line_for_resource(self, line: str, line_iterator: Optional[iter] = None) -> Optional[Resource]:
        # Try to match file resources first (e.g., ICON, BITMAP)
        # NAME TYPE [options] "filepath"
        # Example: IDI_MYICON ICON "myicon.ico"
        # Example: IDB_MYBMP BITMAP DISCARDABLE "mybmp.bmp"
        # Regex needs to capture: name, type, options (optional), filepath
        # Options can include PRELOAD, LOADONCALL, FIXED, MOVEABLE, DISCARDABLE, PURE.
        file_res_match = re.match(r'^\s*([^\s"]+|\"[^\"]+\")\s+([A-Z0-9_#]+)\s*(?:[A-Z\s]*)?\"([^\"]+)\"', line, re.IGNORECASE)
        # Simpler regex focusing on name, type, and quoted filename for file resources:
        # (\S+) is the name (can be quoted or not)
        # (\S+) is the type string
        # "([^"]+)" is the quoted filename
        file_res_pattern = r'^\s*([^\s"]+(?:\s"[^"]+")?|\"[^\"]+\"|[0-9A-Za-z_#]+)\s+([A-Z0-9_#]+)\s+(?:[A-Z]+\s+)*(?:DISCARDABLE\s+)?(?:FIXED\s+)?(?:MOVEABLE\s+)?(?:PRELOAD\s+)?(?:LOADONCALL\s+)?\"([^\"]+)\"\s*$'
        # A slightly more robust regex for file resources:
        # It handles quoted names like "My Resource Name" ICON "icon.ico"
        # And unquoted names like MYRESOURCE ICON "icon.ico"
        file_res_match = re.match(r'^\s*(.+?)\s+([A-Z0-9_#]+)\s+(?:[A-Z\s]+\s+)?\"([^\"]+)\"\s*$', line, re.IGNORECASE)


        if file_res_match:
            name_id_str, type_str, filepath = file_res_match.groups()
            name_id_str = name_id_str.strip() # Clean up potential extra spaces if not quoted
            type_str_upper = type_str.upper()

            if type_str_upper in FILE_RESOURCE_TYPES:
                name_id = self._parse_name_id(name_id_str)
                res_type_id = RC_TYPE_TO_RT_ID.get(type_str_upper, type_str_upper) # Use string type if no const

                identifier = ResourceIdentifier(res_type_id, name_id, self.current_language)
                # print(f"Debug: Matched FileResource: Name='{name_id_str}'({name_id}), Type='{type_str_upper}'({res_type_id}), File='{filepath}', Line: '{line[:50]}...'")
                return FileResource(identifier, filepath, line.strip())

        # Try to match block resources (e.g., DIALOG, MENU, STRINGTABLE)
        # NAME TYPE [options]
        # BEGIN
        # ...
        # END
        # Example: MY_DIALOG DIALOGEX 0, 0, 100, 100
        # Example: STRINGTABLE [LANGUAGE lang, sublang]
        block_res_match = re.match(r'^\s*([^\s"]+|\"[^\"]+\")\s+([A-Z0-9_#]+)\s*(.*)', line, re.IGNORECASE)
        # More specific:
        # (\S+|\"[^\"]+\") captures unquoted or quoted name
        # ([A-Z0-9_#]+) captures the resource type keyword
        # (.*) captures the rest of the line (options, coordinates, etc.)
        block_res_header_pattern = r'^\s*(.+?)\s+([A-Z0-9_#]+)\s*(.*)'
        block_res_match = re.match(block_res_header_pattern, line, re.IGNORECASE)

        if block_res_match:
            name_id_str, type_str, options_str = block_res_match.groups()
            name_id_str = name_id_str.strip()
            type_str_upper = type_str.upper()

            if type_str_upper in BLOCK_RESOURCE_TYPES or \
               (type_str_upper == "RCDATA" and "BEGIN" in options_str.upper()) or \
               ("BEGIN" in options_str.upper() and type_str_upper not in FILE_RESOURCE_TYPES) : # Generic block

                # Check if the options string itself contains BEGIN, or if the next line is BEGIN
                # This regex is still too greedy for options_str.
                # Let's refine how we detect the start of a block.
                # A block usually has its type keyword, then options, and then "BEGIN" on the same line or next.

                # If "BEGIN" is on the same line (often for RCDATA, etc.)
                # or if the type is known to be a block type and options are just coords/styles.

                # We need to consume lines until "END"
                if line_iterator is None: return None # Cannot parse block without line iterator

                current_block_lines = [line.strip()]
                # Check for LANGUAGE statement immediately after for some resource types
                # This is a simplification; language can be before or inside for some.
                # e.g. STRINGTABLE LANGUAGE x, y \n BEGIN...
                if "LANGUAGE" in options_str.upper():
                    self._parse_language_statement(options_str.strip())


                # Consume lines until END
                # Need to handle nested BEGIN/END blocks carefully if they exist (e.g. MENU)
                # For now, simple non-nested matching.
                begin_found_on_first_line = "BEGIN" in options_str.upper()

                # If BEGIN was not on the first line, expect it on the next.
                if not begin_found_on_first_line:
                    try:
                        next_line = next(line_iterator)
                        current_block_lines.append(next_line.strip())
                        if not next_line.strip().upper().startswith("BEGIN"):
                            # Not a valid block start as expected
                            # print(f"Debug: Expected BEGIN after '{line.strip()}', got '{next_line.strip()}'. Not a block.")
                            return None # Or rewind iterator if possible
                    except StopIteration:
                        return None # End of file

                # Now, consume until END
                nesting_level = 1
                while True:
                    try:
                        block_line = next(line_iterator)
                        block_line_stripped = block_line.strip()
                        current_block_lines.append(block_line_stripped)

                        # Check for nested BEGIN/END, common in MENU, DIALOG
                        if block_line_stripped.upper().startswith("BEGIN"): # Could be simplified to just "BEGIN"
                            nesting_level += 1
                        elif block_line_stripped.upper() == "END":
                            nesting_level -= 1
                            if nesting_level == 0:
                                break # Found the matching END for our block
                    except StopIteration:
                        print(f"Warning: EOF reached while parsing block for '{name_id_str} {type_str_upper}'. Block may be incomplete.")
                        break # EOF

                full_block_text = "\n".join(current_block_lines)
                name_id = self._parse_name_id(name_id_str)
                res_type_id = RC_TYPE_TO_RT_ID.get(type_str_upper, type_str_upper)

                identifier = ResourceIdentifier(res_type_id, name_id, self.current_language)
                # print(f"Debug: Matched TextBlock: Name='{name_id_str}'({name_id}), Type='{type_str_upper}'({res_type_id}), Options='{options_str[:30]}...'")
                return TextBlockResource(identifier, full_block_text, type_str_upper)

        return None


    def parse_rc_file(self, rc_filepath: str) -> List[Resource]:
        self.resources = []
        self.current_language = LANG_NEUTRAL # Reset language for each file
        self.rc_file_directory = os.path.dirname(os.path.abspath(rc_filepath))

        try:
            # print(f"Debug: Running mcpp: Path='{self.mcpp_path}', RC='{rc_filepath}', Includes='{self.include_paths}'")
            preprocessed_content = run_mcpp(rc_filepath, self.mcpp_path, self.include_paths)
        except MCPPError as e:
            print(f"Error during mcpp preprocessing of '{rc_filepath}': {e}")
            return self.resources
        except FileNotFoundError as e: # For rc_filepath itself
            print(f"Error: RC file '{rc_filepath}' not found: {e}")
            return self.resources

        lines = preprocessed_content.splitlines()
        line_iterator = iter(lines)

        for line in line_iterator: # line_iterator will be advanced by _parse_line_for_resource for blocks
            line = line.strip()
            if not line or line.startswith("//") or line.startswith("/*") or line.startswith("#"): # Skip empty/comments/#line directives
                continue

            # Check for LANGUAGE statement first, as it sets context
            if line.upper().startswith("LANGUAGE "):
                self._parse_language_statement(line)
                continue

            resource = self._parse_line_for_resource(line, line_iterator)
            if resource:
                self.resources.append(resource)
            # else:
                # print(f"Debug: No resource parsed from line: '{line[:100]}'")


        # print(f"Debug: Parsing complete. Found {len(self.resources)} resources.")
        return self.resources


if __name__ == '__main__':
    # This is a placeholder for testing.
    # To test this properly, you would need a sample RC file and mcpp.exe.
    print("rc_parser.py executed. For testing, run through src.__main__.py or a dedicated test script.")

    # Create a dummy rc file for basic testing:
    sample_rc_content = """
#define MY_ICON 101
#define PRODUCT_NAME "My Product"
// Some comment

LANGUAGE 0x09, 0x01 // English US

MY_ICON ICON "myrealicon.ico"
ANOTHER_ICON ICON DISCARDABLE "another.ico"

ID_MYMENU MENU
BEGIN
    POPUP "&File"
    BEGIN
        MENUITEM "E&xit", 1000
    END
END

STRINGTABLE PRELOAD // Preload is an option
LANGUAGE 0x0c, 0x03 // French Canadian
BEGIN
    10, "Bonjour"
    11, "Au revoir"
END

MY_DIALOG DIALOGEX 10, 20, 200, 100
STYLE DS_MODALFRAME | WS_POPUP
CAPTION "My Dialog Title"
FONT 8, "MS Shell Dlg"
LANGUAGE 0x07, 0x01 // German Standard
BEGIN
    CTEXT "Hello!", -1, 10,10,50,10
    PUSHBUTTON "OK", 1, 150, 80, 40, 14
END

// RCDATA block
MY_RCDATA RCDATA BEGIN
    "This is raw data line 1.\\0"
    "This is raw data line 2.\\r\\n"
    0x01, 0x02, 0x03, 0x04
END
"""
    sample_rc_path = "dummy_test_parser.rc"
    with open(sample_rc_path, "w", encoding="utf-8") as f:
       f.write(sample_rc_content)

    # Adjust mcpp_path as needed for your environment
    # mcpp_exe = os.path.join(os.getcwd(), "..", "data", "bin", "mcpp.exe") # If CWD is src/core
    mcpp_exe = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "bin", "mcpp.exe"))
    if not os.path.exists(mcpp_exe):
        mcpp_exe = "mcpp" # Fallback to PATH

    print(f"Using mcpp: {mcpp_exe}")

    parser = RCParser(mcpp_path=mcpp_exe, include_paths=[os.path.dirname(sample_rc_path)])

    try:
        parsed_resources = parser.parse_rc_file(sample_rc_path)
        print(f"\n--- Parsed {len(parsed_resources)} resources from '{sample_rc_path}' ---")
        for i, res in enumerate(parsed_resources):
            print(f"Resource #{i+1}: {res!r}")
            if isinstance(res, FileResource):
                print(f"  Filepath: {res.filepath}")
                print(f"  Original Line: {res.original_rc_statement}")
            elif isinstance(res, TextBlockResource):
                print(f"  Block Type: {res.resource_type_name}")
                print(f"  Content Preview (first 100 chars):\n{res.text_content[:100]}...")
            print(f"  Identifier: Type={res.identifier.type_id}, Name={res.identifier.name_id}, Lang={res.identifier.language_id} (0x{res.identifier.language_id:04X})")
            print("-" * 10)
    except Exception as e:
        print(f"Error during test parsing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if os.path.exists(sample_rc_path):
            os.remove(sample_rc_path)
```
