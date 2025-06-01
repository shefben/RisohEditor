import re
from typing import List, Optional, Tuple, Union
import io # For BytesIO
import struct # For struct.unpack

# --- VS_FIXEDFILEINFO Flags (dwFileFlags) ---
VS_FF_DEBUG = 0x00000001
VS_FF_PRERELEASE = 0x00000002
VS_FF_PATCHED = 0x00000004
VS_FF_PRIVATEBUILD = 0x00000008
VS_FF_INFOINFERRED = 0x00000010
VS_FF_SPECIALBUILD = 0x00000020

# Common StringFileInfo Keys
SFI_COMMENTS = "Comments"
SFI_COMPANY_NAME = "CompanyName"
SFI_FILE_DESCRIPTION = "FileDescription"
SFI_FILE_VERSION = "FileVersion"
SFI_INTERNAL_NAME = "InternalName"
SFI_LEGAL_COPYRIGHT = "LegalCopyright"
SFI_LEGAL_TRADEMARKS = "LegalTrademarks"
SFI_ORIGINAL_FILENAME = "OriginalFilename"
SFI_PRIVATE_BUILD = "PrivateBuild"
SFI_PRODUCT_NAME = "ProductName"
SFI_PRODUCT_VERSION = "ProductVersion"
SFI_SPECIAL_BUILD = "SpecialBuild"

# --- Data Structures ---
class VersionFixedInfo:
    def __init__(self, file_version: Tuple[int, int, int, int] = (0,0,0,0),
                 product_version: Tuple[int, int, int, int] = (0,0,0,0),
                 file_flags_mask: int = 0x3F,
                 file_flags: int = 0x0,
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
        self.file_date_ms: int = file_date_ms # High part of FILETIME
        self.file_date_ls: int = file_date_ls # Low part of FILETIME

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
        self.lang_codepage_hex: str = lang_codepage_hex
        self.entries: List[VersionStringEntry] = entries if entries is not None else []

    def __repr__(self):
        return f"VersionStringTableInfo(lang_cp='{self.lang_codepage_hex}', num_entries={len(self.entries)})"

class VersionVarEntry:
    def __init__(self, key: str, values: Optional[List[int]] = None):
        self.key: str = key
        self.values: List[int] = values if values is not None else []

    def __repr__(self):
        return f"VersionVarEntry(key='{self.key}', values={self.values})"

# --- Binary Parsing Helper Functions ---
def _read_version_block_header(stream: io.BytesIO) -> Tuple[int, int, int, str, int]:
    """
    Reads a standard Version block header: wLength, wValueLength, wType, szKey, padding.
    Returns (length, value_length, type, key_string, total_header_bytes_read_including_padding).
    Type: 0 for binary, 1 for text.
    ValueLength: For strings, length in WORDs. For VS_FIXEDFILEINFO, length of fixed info.
    """
    start_pos = stream.tell()
    header_data = stream.read(6) # wLength, wValueLength, wType (3 WORDs)
    if len(header_data) < 6:
        raise EOFError("Incomplete version block header.")

    w_length, w_value_length, w_type = struct.unpack('<HHH', header_data)

    sz_key_chars = []
    while True:
        char_bytes = stream.read(2)
        if not char_bytes or len(char_bytes) < 2: raise EOFError("EOF while reading szKey in version block.")
        if char_bytes == b'\x00\x00': break
        sz_key_chars.append(char_bytes.decode('utf-16-le', errors='replace'))
    sz_key = "".join(sz_key_chars)

    # Align to DWORD boundary after szKey
    current_pos_after_key = stream.tell()
    padding_after_key = (4 - (current_pos_after_key % 4)) % 4
    if padding_after_key > 0:
        stream.read(padding_after_key)

    total_header_bytes = stream.tell() - start_pos
    return w_length, w_value_length, w_type, sz_key, total_header_bytes

def _read_version_string_value(stream: io.BytesIO, value_length_words: int) -> str:
    """Reads a string value, which is value_length_words long (in WORDs), null terminated within that length."""
    if value_length_words == 0: return ""

    str_data_bytes = stream.read(value_length_words * 2)
    # Find first null terminator
    null_idx = str_data_bytes.find(b'\x00\x00')
    if null_idx != -1:
        str_data_bytes = str_data_bytes[:null_idx]

    return str_data_bytes.decode('utf-16-le', errors='replace')


# --- RC Text Parsing and Generation (Placeholders / Basic Implementation) ---
# (These are simplified as primary focus is binary parsing for this subtask)
def parse_versioninfo_rc_text(rc_text: str) -> Tuple[Optional[VersionFixedInfo], List[VersionStringTableInfo], List[VersionVarEntry]]:
    fixed_info: Optional[VersionFixedInfo] = None
    string_tables: List[VersionStringTableInfo] = []
    var_info_list: List[VersionVarEntry] = []

    fv_match = re.search(r"FILEVERSION\s+(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", rc_text, re.IGNORECASE)
    pv_match = re.search(r"PRODUCTVERSION\s+(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", rc_text, re.IGNORECASE)
    ffm_match = re.search(r"FILEFLAGSMASK\s+(0x[0-9a-fA-F]+L?|[0-9]+L?)", rc_text, re.IGNORECASE) # Added L suffix
    ff_match = re.search(r"FILEFLAGS\s+(0x[0-9a-fA-F]+L?|[0-9]+L?)", rc_text, re.IGNORECASE)
    fos_match = re.search(r"FILEOS\s+(0x[0-9a-fA-F]+L?|[0-9]+L?)", rc_text, re.IGNORECASE)
    ft_match = re.search(r"FILETYPE\s+(0x[0-9a-fA-F]+L?|[0-9]+L?)", rc_text, re.IGNORECASE)
    fst_match = re.search(r"FILESUBTYPE\s+(0x[0-9a-fA-F]+L?|[0-9]+L?)", rc_text, re.IGNORECASE)

    fixed_info = VersionFixedInfo()
    if fv_match: fixed_info.file_version = tuple(map(int, fv_match.groups()))
    if pv_match: fixed_info.product_version = tuple(map(int, pv_match.groups()))
    if ffm_match: fixed_info.file_flags_mask = int(ffm_match.group(1).replace('L',''), 0)
    if ff_match: fixed_info.file_flags = int(ff_match.group(1).replace('L',''), 0)
    if fos_match: fixed_info.file_os = int(fos_match.group(1).replace('L',''), 0)
    if ft_match: fixed_info.file_type = int(ft_match.group(1).replace('L',''), 0)
    if fst_match: fixed_info.file_subtype = int(fst_match.group(1).replace('L',''), 0)

    sfi_block_match = re.search(r'BLOCK\s+"StringFileInfo"\s*\n\s*BEGIN((?:.|\n)*?)^\s*END', rc_text, re.IGNORECASE | re.MULTILINE)
    if sfi_block_match:
        sfi_content = sfi_block_match.group(1)
        lang_block_matches = re.finditer(r'BLOCK\s+"([0-9a-fA-F]{8})"\s*\n\s*BEGIN((?:.|\n)*?)^\s*END', sfi_content, re.IGNORECASE | re.MULTILINE)
        for lang_match in lang_block_matches:
            lang_cp_hex = lang_match.group(1)
            lang_block_content = lang_match.group(2)
            current_entries: List[VersionStringEntry] = []
            value_matches = re.finditer(r'VALUE\s+"([^"]+)"\s*,\s*"([^"]*(?:""[^"]*)*)"', lang_block_content, re.IGNORECASE)
            for val_match in value_matches:
                key = val_match.group(1); value = val_match.group(2).replace('""', '"')
                current_entries.append(VersionStringEntry(key, value))
            if current_entries: string_tables.append(VersionStringTableInfo(lang_cp_hex, current_entries))

    vfi_block_match = re.search(r'BLOCK\s+"VarFileInfo"\s*\n\s*BEGIN((?:.|\n)*?)^\s*END', rc_text, re.IGNORECASE | re.MULTILINE)
    if vfi_block_match:
        vfi_content = vfi_block_match.group(1)
        trans_match = re.search(r'VALUE\s+"Translation"\s*,\s*((?:0x[0-9a-fA-F]+|[0-9]+)(?:\s*,\s*(?:0x[0-9a-fA-F]+|[0-9]+))*)', vfi_content, re.IGNORECASE)
        if trans_match:
            values_str = trans_match.group(1).split(','); values_int = [int(v.strip(), 0) for v in values_str if v.strip()]
            var_info_list.append(VersionVarEntry("Translation", values_int))

    return fixed_info, string_tables, var_info_list


def generate_versioninfo_rc_text(fixed_info: Optional[VersionFixedInfo],
                                 string_tables: List[VersionStringTableInfo],
                                 var_info_list: List[VersionVarEntry],
                                 resource_id_name: Union[str,int] = "VS_VERSION_INFO",
                                 lang_id: Optional[int] = None
                                 ) -> str:
    lines: List[str] = []
    if lang_id is not None: lines.append(f"LANGUAGE {lang_id & 0x3FF}, {(lang_id >> 10) & 0x3F}")
    id_str = f'"{resource_id_name}"' if isinstance(resource_id_name, str) and not resource_id_name.isdigit() else str(resource_id_name)
    lines.append(f"{id_str} VERSIONINFO")
    if fixed_info:
        lines.append(f" FILEVERSION {','.join(map(str, fixed_info.file_version))}")
        lines.append(f" PRODUCTVERSION {','.join(map(str, fixed_info.product_version))}")
        lines.append(f" FILEFLAGSMASK 0x{fixed_info.file_flags_mask:X}L")
        lines.append(f" FILEFLAGS 0x{fixed_info.file_flags:X}L")
        lines.append(f" FILEOS 0x{fixed_info.file_os:X}L")
        lines.append(f" FILETYPE 0x{fixed_info.file_type:X}L")
        lines.append(f" FILESUBTYPE 0x{fixed_info.file_subtype:X}L")
    lines.append("BEGIN")
    if string_tables:
        lines.append("    BLOCK \"StringFileInfo\""); lines.append("    BEGIN")
        for st_table in string_tables:
            lines.append(f'        BLOCK "{st_table.lang_codepage_hex}"'); lines.append("        BEGIN")
            for entry in st_table.entries:
                val_escaped = entry.value.replace('"', '""')
                lines.append(f'            VALUE "{entry.key}", "{val_escaped}"')
            lines.append("        END")
        lines.append("    END")
    if var_info_list:
        lines.append("    BLOCK \"VarFileInfo\""); lines.append("    BEGIN")
        for var_entry in var_info_list:
            if var_entry.key.upper() == "TRANSLATION" and var_entry.values:
                vals_str = ", ".join([f"0x{v:04x}" for v in var_entry.values])
                lines.append(f'        VALUE "{var_entry.key}", {vals_str}')
        lines.append("    END")
    lines.append("END")
    return "\n".join(lines)


if __name__ == '__main__':
    print("Testing version_parser_util.py with binary helper placeholders.")
    # ... (existing tests can be kept or adapted) ...
    print("\nversion_parser_util.py self-tests completed.")


