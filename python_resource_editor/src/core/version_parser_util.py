import re
from typing import List, Optional, Tuple, Union

class VersionFixedInfo:
    def __init__(self, file_version: Tuple[int, int, int, int] = (0,0,0,0),
                 product_version: Tuple[int, int, int, int] = (0,0,0,0),
                 file_flags_mask: int = 0x3F, # Common default
                 file_flags: int = 0x0,      # Common default
                 file_os: int = 0x40004,     # VOS_NT_WINDOWS32
                 file_type: int = 0x1,       # VFT_APP
                 file_subtype: int = 0x0,
                 file_date_ms: int = 0,
                 file_date_ls: int = 0):
        self.file_version: Tuple[int, int, int, int] = file_version
        self.product_version: Tuple[int, int, int, int] = product_version
        self.file_flags_mask: int = file_flags_mask
        self.file_flags: int = file_flags
        self.file_os: int = file_os
        self.file_type: int = file_type
        self.file_subtype: int = file_subtype
        self.file_date_ms: int = file_date_ms
        self.file_date_ls: int = file_date_ls

    def __repr__(self):
        return (f"VersionFixedInfo(FV={self.file_version}, PV={self.product_version}, "
                f"Flags=0x{self.file_flags:X}, OS=0x{self.file_os:X}, Type=0x{self.file_type:X})")

class VersionStringEntry:
    def __init__(self, key: str, value: str):
        self.key: str = key
        self.value: str = value

    def __repr__(self):
        return f"VersionStringEntry(key='{self.key}', value='{self.value[:30]}...')"

class VersionStringTableInfo:
    def __init__(self, lang_codepage_hex: str, entries: Optional[List[VersionStringEntry]] = None):
        self.lang_codepage_hex: str = lang_codepage_hex # e.g., "040904b0"
        self.entries: List[VersionStringEntry] = entries if entries is not None else []

    def __repr__(self):
        return f"VersionStringTableInfo(lang_cp='{self.lang_codepage_hex}', num_entries={len(self.entries)})"

class VersionVarEntry:
    def __init__(self, key: str, values: Optional[List[int]] = None): # Values are usually pairs of langID, charsetID
        self.key: str = key
        self.values: List[int] = values if values is not None else []

    def __repr__(self):
        return f"VersionVarEntry(key='{self.key}', values={self.values})"


# --- Parsing and Generation Functions (Placeholders / Basic Implementation) ---

def parse_versioninfo_rc_text(rc_text: str) -> Tuple[Optional[VersionFixedInfo], List[VersionStringTableInfo], List[VersionVarEntry]]:
    """
    Parses VERSIONINFO resource script text.
    This is a simplified parser focusing on common structures.
    """
    fixed_info: Optional[VersionFixedInfo] = None
    string_tables: List[VersionStringTableInfo] = []
    var_info_list: List[VersionVarEntry] = [] # VarFileInfo usually has one "Translation" entry

    lines = rc_text.splitlines()

    # --- Parse Fixed Info ---
    # FILEVERSION w,x,y,z
    # PRODUCTVERSION w,x,y,z
    # FILEFLAGSMASK mask
    # FILEFLAGS flags
    # FILEOS os
    # FILETYPE type
    # FILESUBTYPE subtype
    fv_match = re.search(r"FILEVERSION\s+(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", rc_text, re.IGNORECASE)
    pv_match = re.search(r"PRODUCTVERSION\s+(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", rc_text, re.IGNORECASE)
    ffm_match = re.search(r"FILEFLAGSMASK\s+(0x[0-9a-fA-F]+|[0-9]+)", rc_text, re.IGNORECASE)
    ff_match = re.search(r"FILEFLAGS\s+(0x[0-9a-fA-F]+|[0-9]+)", rc_text, re.IGNORECASE)
    fos_match = re.search(r"FILEOS\s+(0x[0-9a-fA-F]+|[0-9]+)", rc_text, re.IGNORECASE)
    ft_match = re.search(r"FILETYPE\s+(0x[0-9a-fA-F]+|[0-9]+)", rc_text, re.IGNORECASE)
    fst_match = re.search(r"FILESUBTYPE\s+(0x[0-9a-fA-F]+|[0-9]+)", rc_text, re.IGNORECASE)

    fixed_info = VersionFixedInfo() # Initialize with defaults
    if fv_match: fixed_info.file_version = tuple(map(int, fv_match.groups()))
    if pv_match: fixed_info.product_version = tuple(map(int, pv_match.groups()))
    if ffm_match: fixed_info.file_flags_mask = int(ffm_match.group(1), 0)
    if ff_match: fixed_info.file_flags = int(ff_match.group(1), 0)
    if fos_match: fixed_info.file_os = int(fos_match.group(1), 0)
    if ft_match: fixed_info.file_type = int(ft_match.group(1), 0)
    if fst_match: fixed_info.file_subtype = int(fst_match.group(1), 0)


    # --- Parse StringFileInfo and VarFileInfo Blocks ---
    # This requires parsing nested BEGIN/END blocks.
    # Simplified: Find first StringFileInfo and VarFileInfo.

    # BLOCK "StringFileInfo"
    # BEGIN
    #   BLOCK "langIDcharsetID" (e.g. "040904b0")
    #   BEGIN
    #     VALUE "Key", "Value"
    #     ...
    #   END
    # END
    sfi_block_match = re.search(r'BLOCK\s+"StringFileInfo"\s*\n\s*BEGIN((?:.|\n)*?)END', rc_text, re.IGNORECASE | re.MULTILINE)
    if sfi_block_match:
        sfi_content = sfi_block_match.group(1)
        lang_block_matches = re.finditer(r'BLOCK\s+"([0-9a-fA-F]{8})"\s*\n\s*BEGIN((?:.|\n)*?)END', sfi_content, re.IGNORECASE | re.MULTILINE)
        for lang_match in lang_block_matches:
            lang_cp_hex = lang_match.group(1)
            lang_block_content = lang_match.group(2)
            current_entries: List[VersionStringEntry] = []
            value_matches = re.finditer(r'VALUE\s+"([^"]+)"\s*,\s*"([^"]*(?:""[^"]*)*)"', lang_block_content, re.IGNORECASE)
            for val_match in value_matches:
                key = val_match.group(1)
                value = val_match.group(2).replace('""', '"') # Unescape ""
                current_entries.append(VersionStringEntry(key, value))
            if current_entries:
                string_tables.append(VersionStringTableInfo(lang_cp_hex, current_entries))

    # BLOCK "VarFileInfo"
    # BEGIN
    #   VALUE "Translation", langID, charsetID [, langID2, charsetID2, ...]
    # END
    vfi_block_match = re.search(r'BLOCK\s+"VarFileInfo"\s*\n\s*BEGIN((?:.|\n)*?)END', rc_text, re.IGNORECASE | re.MULTILINE)
    if vfi_block_match:
        vfi_content = vfi_block_match.group(1)
        # VALUE "Translation", lang1, cp1 [, lang2, cp2, ...]
        trans_match = re.search(r'VALUE\s+"Translation"\s*,\s*((?:0x[0-9a-fA-F]+|[0-9]+)(?:\s*,\s*(?:0x[0-9a-fA-F]+|[0-9]+))*)', vfi_content, re.IGNORECASE)
        if trans_match:
            values_str = trans_match.group(1).split(',')
            values_int = [int(v.strip(), 0) for v in values_str if v.strip()]
            var_info_list.append(VersionVarEntry("Translation", values_int))

    return fixed_info, string_tables, var_info_list


def generate_versioninfo_rc_text(fixed_info: Optional[VersionFixedInfo],
                                 string_tables: List[VersionStringTableInfo],
                                 var_info_list: List[VersionVarEntry],
                                 resource_id_name: Union[str,int] = "VS_VERSION_INFO", # Usually 1 or "VS_VERSION_INFO"
                                 lang_id: Optional[int] = None # Global lang for VERSIONINFO statement itself
                                 ) -> str:
    """Generates VERSIONINFO resource script text."""
    lines: List[str] = []

    if lang_id is not None: # Language for the VERSIONINFO resource itself
        lines.append(f"LANGUAGE {lang_id & 0x3FF}, {(lang_id >> 10) & 0x3F}")

    id_str = f'"{resource_id_name}"' if isinstance(resource_id_name, str) and not resource_id_name.isdigit() else str(resource_id_name)
    lines.append(f"{id_str} VERSIONINFO")

    if fixed_info:
        lines.append(f" FILEVERSION {','.join(map(str, fixed_info.file_version))}")
        lines.append(f" PRODUCTVERSION {','.join(map(str, fixed_info.product_version))}")
        lines.append(f" FILEFLAGSMASK 0x{fixed_info.file_flags_mask:X}L")
        lines.append(f" FILEFLAGS 0x{fixed_info.file_flags:X}L")
        lines.append(f" FILEOS 0x{fixed_info.file_os:X}L")
        lines.append(f" FILETYPE 0x{fixed_info.file_type:X}L")
        lines.append(f" FILESUBTYPE 0x{fixed_info.file_subtype:X}L") # Often 0 for VFT_APP

    lines.append("BEGIN")
    if string_tables:
        lines.append("    BLOCK \"StringFileInfo\"")
        lines.append("    BEGIN")
        for st_table in string_tables:
            lines.append(f'        BLOCK "{st_table.lang_codepage_hex}"')
            lines.append("        BEGIN")
            for entry in st_table.entries:
                # Values in RC strings need quotes escaped ("" becomes """") and null terminators are often written as \0,
                # but usually VALUE statements handle this by just taking the string.
                # Here, ensure internal quotes are doubled. Nulls are implicit if data comes from Windows APIs.
                # For RC text, it's common to just write the string.
                val_escaped = entry.value.replace('"', '""')
                lines.append(f'            VALUE "{entry.key}", "{val_escaped}"')
            lines.append("        END")
        lines.append("    END")

    if var_info_list:
        lines.append("    BLOCK \"VarFileInfo\"")
        lines.append("    BEGIN")
        for var_entry in var_info_list:
            if var_entry.key.upper() == "TRANSLATION" and var_entry.values:
                # Format values as hex for readability, common in RC
                vals_str = ", ".join([f"0x{v:04x}" for v in var_entry.values])
                lines.append(f'        VALUE "{var_entry.key}", {vals_str}')
            # Add other VarFileInfo types if necessary
        lines.append("    END")

    lines.append("END")
    return "\n".join(lines)


if __name__ == '__main__':
    print("Testing version_parser_util.py")
    sample_version_rc = """
1 VERSIONINFO
 FILEVERSION 1,0,0,1
 PRODUCTVERSION 1,0,0,1
 FILEFLAGSMASK 0x3fL
 FILEFLAGS 0x0L
 FILEOS 0x40004L // VOS_NT_WINDOWS32
 FILETYPE 0x1L   // VFT_APP
 FILESUBTYPE 0x0L // VFT2_UNKNOWN
BEGIN
    BLOCK "StringFileInfo"
    BEGIN
        BLOCK "040904b0" // Lang: US English, Charset: Unicode
        BEGIN
            VALUE "CompanyName", "My Company Inc."
            VALUE "FileDescription", "My Application"
            VALUE "FileVersion", "1.0.0.1"
            VALUE "InternalName", "MyApp.exe"
            VALUE "LegalCopyright", "Copyright (C) 2023 My Company Inc."
            VALUE "OriginalFilename", "MyApp.exe"
            VALUE "ProductName", "My Application"
            VALUE "ProductVersion", "1.0.0.1"
        END
        BLOCK "040C04b0" // Lang: French (Standard), Charset: Unicode
        BEGIN
            VALUE "CompanyName", "Ma Compagnie Inc."
            VALUE "FileDescription", "Mon Application"
        END
    END
    BLOCK "VarFileInfo"
    BEGIN
        VALUE "Translation", 0x409, 1200, 0x40c, 1200
    END
END
"""
    print(f"\n--- Parsing Sample Version RC ---\n{sample_version_rc[:200]}...")
    fixed, str_tables, var_info = parse_versioninfo_rc_text(sample_version_rc)

    print("\n--- Parsed Fixed Info ---")
    print(fixed)
    if fixed: assert fixed.file_version == (1,0,0,1)

    print("\n--- Parsed String Tables ---")
    for st in str_tables:
        print(st)
        for entry in st.entries: print(f"  {entry}")
    assert len(str_tables) == 2
    if str_tables: assert str_tables[0].lang_codepage_hex == "040904b0"
    if str_tables and str_tables[0].entries: assert str_tables[0].entries[0].key == "CompanyName"

    print("\n--- Parsed VarInfo ---")
    for vi in var_info: print(vi)
    assert len(var_info) == 1
    if var_info: assert var_info[0].key == "Translation"
    if var_info and var_info[0].values: assert var_info[0].values == [0x409, 1200, 0x40c, 1200]

    print("\n--- Generating RC Text from Parsed Structure ---")
    generated_rc = generate_versioninfo_rc_text(fixed, str_tables, var_info, resource_id_name=1) # Use numeric ID 1
    print(generated_rc)
    assert "1 VERSIONINFO" in generated_rc
    assert 'VALUE "CompanyName", "My Company Inc."' in generated_rc
    assert 'VALUE "Translation", 0x0409, 0x04b0, 0x040c, 0x04b0' in generated_rc # 1200 is 0x4b0

    print("\nversion_parser_util.py tests completed.")

```
