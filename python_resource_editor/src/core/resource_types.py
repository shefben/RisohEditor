# src/core/resource_types.py
from .resource_base import Resource, ResourceIdentifier, TextBlockResource, RT_STRING, RT_DIALOG, \
    RT_ICON, RT_GROUP_ICON, RT_BITMAP, RT_MENU, RT_ACCELERATOR, RT_VERSION, \
    RT_MANIFEST, RT_RCDATA, RT_HTML, RT_CURSOR, RT_GROUP_CURSOR, RT_ANICURSOR, \
    RT_ANIICON, RT_DLGINIT, LANG_NEUTRAL
from .rc_parser_util import StringTableEntry, parse_stringtable_rc_text, generate_stringtable_rc_text
from .menu_parser_util import MenuItemEntry, parse_menu_rc_text, generate_menu_rc_text
from .dialog_parser_util import DialogProperties, DialogControlEntry, parse_dialog_rc_text, generate_dialog_rc_text
from .version_parser_util import VersionFixedInfo, VersionStringTableInfo, VersionVarEntry, parse_versioninfo_rc_text, generate_versioninfo_rc_text
from .accelerator_parser_util import AcceleratorEntry, parse_accelerator_rc_text, generate_accelerator_rc_text # Import accelerator utils
from typing import List, Tuple, Union, Optional
import struct


class StringTableResource(Resource):
    def __init__(self, identifier: ResourceIdentifier, entries: List[StringTableEntry] = None):
        super().__init__(identifier, data=b'') # Data will be generated from entries
        self.entries: List[StringTableEntry] = entries if entries is not None else []
        if not entries and self.data: # If raw data was provided but not entries
            # This indicates it might be from a binary source, attempt to parse if needed
            # For now, this class expects entries to be primary or parsed from text.
            pass

    @classmethod
    def parse_from_text_block(cls, text_block_res: TextBlockResource) -> 'StringTableResource':
        """Creates a StringTableResource from a TextBlockResource containing RC string table text."""
        if not text_block_res.text_content:
            entries = []
        else:
            entries = parse_stringtable_rc_text(text_block_res.text_content)
        # The identifier from TextBlockResource is for the whole block.
        # StringTableResource uses this directly.
        return cls(text_block_res.identifier, entries)

    @classmethod
    def parse_from_binary_data(cls, raw_data: bytes, identifier: ResourceIdentifier) -> 'StringTableResource':
        """
        Parses RT_STRING data from PE/RES binary format.
        Each StringTable resource (identified by name_id which is block_num) contains up to 16 strings.
        Each string is stored as: WORD length (number of WCHARs), WCHARs string_data (not null-terminated).
        """
        entries: List[StringTableEntry] = []
        if not isinstance(identifier.name_id, int) or identifier.name_id < 1:
            # Binary string tables are always identified by an integer block ID.
            # print(f"Warning: StringTable from binary data expects an integer name_id (block number). Got {identifier.name_id}")
            return cls(identifier, [])

        base_id_for_block = (identifier.name_id - 1) * 16

        offset = 0
        for i in range(16): # Max 16 strings per block
            if offset + 2 > len(raw_data): # Not enough data for length WORD
                break

            str_len_chars = struct.unpack('<H', raw_data[offset:offset+2])[0]
            offset += 2

            if str_len_chars == 0: # Zero-length string (empty slot)
                continue

            str_data_bytes = raw_data[offset : offset + str_len_chars * 2] # 2 bytes per WCHAR
            if len(str_data_bytes) < str_len_chars * 2:
                # print(f"Warning: Incomplete string data for string index {i} in block {identifier.name_id}.")
                break

            value_str = str_data_bytes.decode('utf-16-le')
            string_id = base_id_for_block + i # Actual ID of the string

            entries.append(StringTableEntry(id_val=string_id, value_str=value_str, name_val=str(string_id)))
            offset += str_len_chars * 2

        return cls(identifier, entries)


    def to_rc_text(self) -> str:
        # Use the utility function, passing the language ID from the identifier
        return generate_stringtable_rc_text(self.entries, self.identifier.language_id)

    def get_display_entries(self) -> List[Tuple[str, str, str]]:
        """Helper to get (ID_str, Name_str, Value_str) for GUI display."""
        display_list = []
        for entry in self.entries:
            id_display = str(entry.id_val)
            name_display = entry.name_val if entry.name_val else "" # Show symbolic name if available
            if name_display == id_display and isinstance(entry.id_val, int): # If name is just numeric ID, clear it
                name_display = ""

            display_list.append((id_display, name_display, entry.value_str))
        return display_list

    def update_entry(self, old_id_val: Union[int,str], new_id_val: Union[int,str], new_name_val: Optional[str], new_value_str: str):
        """Updates an existing entry or adds if ID changed to a new one."""
        found_entry = None
        for entry in self.entries:
            if str(entry.id_val) == str(old_id_val) or (entry.name_val and entry.name_val == str(old_id_val)):
                found_entry = entry
                break

        if found_entry:
            found_entry.id_val = new_id_val
            found_entry.name_val = new_name_val if new_name_val else (str(new_id_val) if not isinstance(new_id_val, int) else None)
            found_entry.value_str = new_value_str
            self.dirty = True
        else: # If ID changed, it's like deleting old and adding new; or just add if it's truly new
            self.add_entry(new_id_val, new_name_val, new_value_str)


    def add_entry(self, id_val: Union[int,str], name_val: Optional[str], value_str: str):
        # Check for duplicate IDs before adding
        for entry in self.entries:
            if str(entry.id_val) == str(id_val) or (entry.name_val and entry.name_val == str(id_val)):
                # Handle error: duplicate ID
                raise ValueError(f"StringTable entry with ID '{id_val}' already exists.")

        new_entry = StringTableEntry(id_val, value_str, name_val if name_val else (str(id_val) if not isinstance(id_val, int) else None))
        self.entries.append(new_entry)
        self.dirty = True

    def delete_entry(self, id_to_delete: Union[int,str]):
        original_len = len(self.entries)
        self.entries = [entry for entry in self.entries if not (str(entry.id_val) == str(id_to_delete) or (entry.name_val and entry.name_val == str(id_to_delete)))]
        if len(self.entries) < original_len:
            self.dirty = True


class DialogResource(Resource):
    def __init__(self, identifier: ResourceIdentifier,
                 properties: Optional[DialogProperties] = None,
                 controls: Optional[List[DialogControlEntry]] = None):
        super().__init__(identifier, data=b'') # Data will be generated from properties/controls
        self.properties: DialogProperties = properties if properties is not None else \
            DialogProperties(name=identifier.name_id, symbolic_name=str(identifier.name_id) if isinstance(identifier.name_id, str) else None)
        self.controls: List[DialogControlEntry] = controls if controls is not None else []

    @classmethod
    def parse_from_text_block(cls, text_block_res: TextBlockResource) -> 'DialogResource':
        """Creates a DialogResource from a TextBlockResource containing RC dialog text."""
        if not text_block_res.text_content:
            # Create a default DialogProperties if text block is empty
            props = DialogProperties(name=text_block_res.identifier.name_id,
                                     symbolic_name=str(text_block_res.identifier.name_id) if isinstance(text_block_res.identifier.name_id, str) else None,
                                     caption="New Dialog")
            return cls(text_block_res.identifier, props, [])

        props, controls = parse_dialog_rc_text(text_block_res.text_content)
        if props is None: # Parsing failed to find header, create default
             props = DialogProperties(name=text_block_res.identifier.name_id,
                                     symbolic_name=str(text_block_res.identifier.name_id) if isinstance(text_block_res.identifier.name_id, str) else None,
                                     caption="Dialog (Parsing Failed)")

        # Ensure the identifier of the DialogResource matches the one from the TextBlock
        dialog_identifier = ResourceIdentifier(RT_DIALOG, props.name, text_block_res.identifier.language_id)
        # Update props name if it was derived differently by parser, to match identifier
        props.name = dialog_identifier.name_id
        props.symbolic_name = str(dialog_identifier.name_id) if isinstance(dialog_identifier.name_id, str) else None

        return cls(dialog_identifier, props, controls)

    @classmethod
    def parse_from_binary_data(cls, raw_data: bytes, identifier: ResourceIdentifier) -> 'DialogResource':
        """Parses RT_DIALOG data from PE/RES binary format. Placeholder for now."""
        # This involves parsing DLGTEMPLATE / DLGTEMPLATEEX structures. Highly complex.
        print(f"Warning: Binary parsing for DialogResource (Type: {identifier.type_id}, Name: {identifier.name_id}) is not yet implemented. Returning basic dialog.")
        # Create DialogProperties with basic info from identifier
        props = DialogProperties(
            name=identifier.name_id,
            symbolic_name=str(identifier.name_id) if isinstance(identifier.name_id, str) else None,
            caption=f"Dialog {identifier.name_id}"
        )
        dialog_res = cls(identifier, props, [])
        dialog_res.data = raw_data # Store raw data
        return dialog_res

    def to_rc_text(self) -> str:
        # Use the utility function from dialog_parser_util
        return generate_dialog_rc_text(self.properties, self.controls, self.identifier.language_id)


# --- Other Resource Type Classes (Placeholders / Minor Adjustments) ---

class IconResource(Resource):
    def __init__(self, identifier: ResourceIdentifier, icon_data: bytes = b''):
        super().__init__(identifier, icon_data)
        # icon_data is the raw .ico file content (or PE format icon data)

    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier):
        return cls(identifier, raw_data)

    # to_rc_text for ICON usually just references a file path
    # ICON "myicon.ico"
    # Or can be defined with raw data (less common in .rc but possible in .res)

class GroupIconResource(Resource):
    # Contains directory of icons, not actual icon images
    def __init__(self, identifier: ResourceIdentifier, icon_entries=None):
        super().__init__(identifier)
        self.icon_entries = icon_entries if icon_entries is not None else [] # List of icon directory entries

    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier):
        # Parses GRPICONDIR structure
        return cls(identifier) # Dummy

    def to_rc_text(self) -> str:
        # Example: IDI_MYAPP ICON "myapp.ico"
        # A GROUP_ICON resource itself doesn't have a direct simple RC text line like "MYGROUPICON GROUPICON BEGIN...END"
        # Instead, it's implicitly defined by a collection of ICON resources that make up the group.
        # The .rc file would list the main icon:
        # IDI_MYAPP ICON "path/to/icon.ico"
        # The compiler/linker figures out the group.
        # For now, let's assume the name_id is the relevant part for an RC definition.
        name_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id)
        # This is a simplification. The actual .ico file contains multiple images.
        # The GROUP_ICON resource in the PE file lists these images.
        # An RC file typically just points to the .ico file.
        return f"{name_str} ICON \"placeholder_icon_for_{name_str}.ico\""


class BitmapResource(Resource):
    def __init__(self, identifier: ResourceIdentifier, bitmap_data: bytes = b''):
        super().__init__(identifier, bitmap_data) # Raw BMP file data (or DIB)

    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier):
        return cls(identifier, raw_data)

    def to_rc_text(self) -> str:
        name_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id)
        return f"{name_str} BITMAP \"placeholder_bitmap_for_{name_str}.bmp\""

class MenuResource(Resource):
    def __init__(self, identifier: ResourceIdentifier, items: List[MenuItemEntry] = None,
                 is_ex: bool = False, menu_name_rc:str = "",
                 characteristics_rc:str="0", version_rc:str="1", global_help_id_rc: Optional[int] = None):
        super().__init__(identifier, data=b'') # Data will be generated from items
        self.items: List[MenuItemEntry] = items if items is not None else []
        self.is_ex: bool = is_ex
        # Store original RC name/attributes if parsed from text, for faithful regeneration
        self.menu_name_rc: str = menu_name_rc if menu_name_rc else \
            (str(identifier.name_id) if isinstance(identifier.name_id, int) else identifier.name_id)
        self.characteristics_rc: str = characteristics_rc
        self.version_rc: str = version_rc
        self.global_help_id_rc: Optional[int] = global_help_id_rc


    @classmethod
    def parse_from_text_block(cls, text_block_res: TextBlockResource) -> 'MenuResource':
        """Creates a MenuResource from a TextBlockResource containing RC menu text."""
        if not text_block_res.text_content:
            return cls(text_block_res.identifier, []) # Return empty menu

        items, is_ex, name, chars, ver, help_id = parse_menu_rc_text(text_block_res.text_content)
        # The identifier from TextBlockResource is for the whole block.
        # We use its name_id, lang_id but specific type (RT_MENU) for MenuResource.
        menu_identifier = ResourceIdentifier(RT_MENU, text_block_res.identifier.name_id, text_block_res.identifier.language_id)
        return cls(menu_identifier, items, is_ex, name, chars, ver, help_id)

    @classmethod
    def parse_from_binary_data(cls, raw_data: bytes, identifier: ResourceIdentifier) -> 'MenuResource':
        """Parses RT_MENU data from PE/RES binary format. Placeholder for now."""
        # This is a very complex parsing task, involving nested structures.
        # Refer to Windows MENUITEMTEMPLATEHEADER, MENUITEMTEMPLATE, MENUEX_TEMPLATE_HEADER, MENUEX_TEMPLATE_ITEM.
        print(f"Warning: Binary parsing for MenuResource (Type: {identifier.type_id}, Name: {identifier.name_id}) is not yet implemented. Returning empty menu.")
        # Create a basic MenuResource to hold raw data at least
        menu_res = cls(identifier, [])
        menu_res.data = raw_data # Store raw data if we can't parse it
        return menu_res

    def to_rc_text(self) -> str:
        # Use the utility function from menu_parser_util
        return generate_menu_rc_text(
            menu_name_rc=self.menu_name_rc,
            items=self.items,
            is_ex=self.is_ex,
            characteristics_rc=self.characteristics_rc,
            version_rc=self.version_rc,
            lang_id=self.identifier.language_id,
            global_help_id_rc=self.global_help_id_rc
        )

class AcceleratorResource(Resource):
    def __init__(self, identifier: ResourceIdentifier,
                 entries: Optional[List[AcceleratorEntry]] = None,
                 table_name_rc: Optional[Union[str, int]] = None):
        super().__init__(identifier, data=b'') # Data generated from entries
        self.entries: List[AcceleratorEntry] = entries if entries is not None else []
        self.table_name_rc: Union[str, int] = table_name_rc if table_name_rc is not None else identifier.name_id

    @classmethod
    def parse_from_text_block(cls, text_block_res: TextBlockResource) -> 'AcceleratorResource':
        """Creates an AcceleratorResource from a TextBlockResource containing RC ACCELERATORS text."""
        # The actual name of the accelerator table is part of the resource identifier,
        # but the text block might also contain it. We prioritize the identifier's name.
        # parse_accelerator_rc_text can also return a name if found in the header.
        _parsed_name, entries = parse_accelerator_rc_text(text_block_res.text_content)

        # Use the name from the resource identifier as the definitive table name
        accel_identifier = ResourceIdentifier(RT_ACCELERATOR, text_block_res.identifier.name_id, text_block_res.identifier.language_id)
        return cls(accel_identifier, entries, table_name_rc=text_block_res.identifier.name_id)

    @classmethod
    def parse_from_binary_data(cls, raw_data: bytes, identifier: ResourceIdentifier) -> 'AcceleratorResource':
        """Parses RT_ACCELERATOR data from PE/RES binary format. Placeholder for now."""
        # Binary format is an array of ACCELTABLEENTRY structures.
        # struct ACCELTABLEENTRY { BYTE  fVirt; WORD  key; WORD  cmd; BYTE  padding; }; (8 bytes each)
        print(f"Warning: Binary parsing for AcceleratorResource (Type: {identifier.type_id}, Name: {identifier.name_id}) is not yet implemented. Returning empty.")
        accel_res = cls(identifier, [])
        accel_res.data = raw_data # Store raw data
        return accel_res

    def to_rc_text(self) -> str:
        # Use the utility function from accelerator_parser_util
        # Ensure table_name_rc is correctly passed (it should be the resource's actual name/ID)
        name_to_use = self.table_name_rc if self.table_name_rc is not None else self.identifier.name_id
        return generate_accelerator_rc_text(name_to_use, self.entries, self.identifier.language_id)

class VersionInfoResource(Resource):
    def __init__(self, identifier: ResourceIdentifier,
                 fixed_info: Optional[VersionFixedInfo] = None,
                 string_tables: Optional[List[VersionStringTableInfo]] = None,
                 var_info: Optional[List[VersionVarEntry]] = None):
        super().__init__(identifier, data=b'') # Data generated from structured info
        self.fixed_info: VersionFixedInfo = fixed_info if fixed_info is not None else VersionFixedInfo()
        self.string_tables: List[VersionStringTableInfo] = string_tables if string_tables is not None else []
        self.var_info: List[VersionVarEntry] = var_info if var_info is not None else []

    @classmethod
    def parse_from_text_block(cls, text_block_res: TextBlockResource) -> 'VersionInfoResource':
        """Creates a VersionInfoResource from a TextBlockResource containing RC VERSIONINFO text."""
        if not text_block_res.text_content:
            # Create a default VersionInfo if text block is empty
            return cls(text_block_res.identifier)

        fixed, str_tbls, var_tbls = parse_versioninfo_rc_text(text_block_res.text_content)

        # The identifier from TextBlockResource is for the VS_VERSION_INFO resource itself.
        # Typically, its name_id is 1.
        version_identifier = ResourceIdentifier(RT_VERSION, text_block_res.identifier.name_id, text_block_res.identifier.language_id)
        return cls(version_identifier, fixed, str_tbls, var_tbls)

    @classmethod
    def parse_from_binary_data(cls, raw_data: bytes, identifier: ResourceIdentifier) -> 'VersionInfoResource':
        """Parses RT_VERSION data from PE/RES binary format. Placeholder for now."""
        # This involves parsing the complex VS_VERSIONINFO structure.
        print(f"Warning: Binary parsing for VersionInfoResource (Type: {identifier.type_id}, Name: {identifier.name_id}) is not yet implemented. Returning basic/empty VersionInfo.")
        # For now, just store raw data and return a default structure.
        # A real implementation would use struct.unpack and careful offset management.
        ver_res = cls(identifier)
        ver_res.data = raw_data # Store raw data if we can't parse it yet
        # Optionally, try to parse at least the fixed part if possible, as a simple example:
        # (This is highly simplified and likely incorrect for real VS_VERSIONINFO without full parsing)
        # try:
        #     if len(raw_data) >= 52: # Minimum size for VS_FIXEDFILEINFO
        #         # This assumes raw_data starts directly with VS_FIXEDFILEINFO, which is not true.
        #         # VS_VERSIONINFO has headers (wLength, wValueLength, wType, szKey "VS_VERSION_INFO", Padding, VS_FIXEDFILEINFO)
        #         # This placeholder will not correctly parse binary data.
        #         pass # Actual parsing is too complex for this placeholder
        # except struct.error:
        #     print("Error trying to minimally parse binary VersionInfo data.")
        return ver_res

    def to_rc_text(self) -> str:
        # Use the utility function from version_parser_util
        # The resource ID name for VERSIONINFO is usually 1, or "VS_VERSION_INFO" (which rc.exe treats as 1)
        # self.identifier.name_id should typically be 1 for standard version resources.
        id_name = self.identifier.name_id
        if isinstance(id_name, int) and id_name == 1:
            id_name = "VS_VERSION_INFO" # Use common symbolic name for default case
        elif not isinstance(id_name, str):
            id_name = str(id_name)

        return generate_versioninfo_rc_text(
            fixed_info=self.fixed_info,
            string_tables=self.string_tables,
            var_info_list=self.var_info,
            resource_id_name=id_name,
            lang_id=self.identifier.language_id # Pass the overall resource language
        )

class ManifestResource(Resource):
    def __init__(self, identifier: ResourceIdentifier, manifest_text: str = ""):
        super().__init__(identifier) # Data is manifest XML text encoded to bytes
        self.manifest_text = manifest_text

    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier):
        try:
            manifest_text = raw_data.decode('utf-8') # Or other detected encoding
        except UnicodeDecodeError:
            manifest_text = "<!-- Manifest data could not be decoded as UTF-8 -->"
        return cls(identifier, manifest_text)

    def to_binary_data(self) -> bytes:
        return self.manifest_text.encode('utf-8') # Assuming UTF-8 for manifests

    def to_rc_text(self) -> str:
        # Example: CREATEPROCESS_MANIFEST_RESOURCE_ID RT_MANIFEST "app.manifest"
        name_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id)
        # RC files typically reference an external manifest file.
        # For embedding, the resource compiler handles reading the file.
        # If we want to embed the text directly, it's more like RCDATA.
        # However, standard practice is linking:
        return f"{name_str} RT_MANIFEST \"placeholder_for_{name_str}.manifest\""
        # If we were to try and embed it (non-standard for RT_MANIFEST in RC):
        # return f"{name_str} RT_MANIFEST DISCARDABLE\nBEGIN\n    /* Need to embed raw bytes of UTF-8 XML here, properly formatted */\nEND"


class HTMLResource(Resource):
    def __init__(self, identifier: ResourceIdentifier, html_content: str = ""):
        super().__init__(identifier) # Data is HTML text encoded to bytes
        self.html_content = html_content

    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier):
        try:
            # HTML resources might have various encodings; UTF-8 is a common guess.
            # BOM (Byte Order Mark) might be present.
            if raw_data.startswith(b'\xef\xbb\xbf'): # UTF-8 BOM
                html_content = raw_data[3:].decode('utf-8')
            else:
                # Try UTF-8, then fallback or use a specified encoding if known
                html_content = raw_data.decode('utf-8')
        except UnicodeDecodeError:
            html_content = raw_data.decode('latin-1', errors='replace') # Fallback
        return cls(identifier, html_content)

    def to_binary_data(self) -> bytes:
        # Should ideally use the original encoding if known, or a standard one like UTF-8
        return self.html_content.encode('utf-8')

    def to_rc_text(self) -> str:
        name_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id)
        # HTML resources are often referenced as files:
        # IDR_MYHTML HTML "myhelp.htm"
        return f"{name_str} HTML \"placeholder_for_{name_str}.html\""

class RCDataResource(Resource): # Generic binary data
    def __init__(self, identifier: ResourceIdentifier, raw_data: bytes = b''):
        super().__init__(identifier, raw_data)

    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier):
        return cls(identifier, raw_data)

    def to_rc_text(self) -> str:
        name_id_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id)
        type_id_str = self.identifier.type_id
        if isinstance(type_id_str, int): # Map known RT_ constant to string, else use number
            type_map = {RT_RCDATA: "RCDATA"} # Add other types if RCDataResource handles them
            type_id_str = type_map.get(self.identifier.type_id, str(self.identifier.type_id))

        # For arbitrary binary data, embedding directly into RC text is complex.
        # Option 1: Reference an external file (simplest if data can be saved)
        # return f"{name_id_str} {type_id_str} \"placeholder_for_binary_data.bin\""

        # Option 2: Embed as a BEGIN/END block with hex bytes (for small data)
        # This is a simplified representation. Windres expects comma-separated WORDs/DWORDs or strings.
        # A more compliant way might involve writing bytes as comma-separated hex values,
        # potentially grouped into lines. Max 256 bytes per line for strings.
        # For pure binary, it's tricky.
        lines = [f"{name_id_str} {type_id_str} DISCARDABLE"] # DISCARDABLE is common for RCDATA
        lines.append("BEGIN")

        # Represent bytes as hex strings, e.g., "01,02,03,04,05,06,07,08,"
        # Or as quoted strings for text-like data.
        # For simplicity, let's show a small hex dump. Max 16 bytes per line.
        data_to_write = self.data
        max_bytes_per_line = 16
        for i in range(0, len(data_to_write), max_bytes_per_line):
            chunk = data_to_write[i:i+max_bytes_per_line]
            hex_values = ", ".join([f"0x{b:02x}" for b in chunk])
            lines.append(f"    {hex_values}{',' if i + max_bytes_per_line < len(data_to_write) else ''}")

        # Alternative for string-like data (if it's mostly printable ASCII):
        # try:
        #     decoded_str = self.data.decode('ascii')
        #     if all(c in string.printable for c in decoded_str):
        #         # Escape quotes and backslashes, then wrap in quotes
        #         escaped_str = decoded_str.replace('\\', '\\\\').replace('"', '\\"')
        #         lines.append(f"    \"{escaped_str}\"")
        #     else:
        #         # Fallback to hex if not printable ASCII
        #         # (hex generation as above)
        # except UnicodeDecodeError:
        #     # Fallback to hex if not ASCII
        #     # (hex generation as above)

        lines.append("END")
        return "\n".join(lines)

class CursorResource(IconResource): # Essentially same structure as Icon for .cur files
    def to_rc_text(self) -> str:
        name_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id)
        # CURSOR type is identified by RT_CURSOR, but RC syntax uses CURSOR keyword
        return f"{name_str} CURSOR \"placeholder_for_{name_str}.cur\""

class GroupCursorResource(GroupIconResource): # Essentially same structure as GroupIcon for .cur files
    def to_rc_text(self) -> str:

class GroupCursorResource(GroupIconResource): # Essentially same structure as GroupIcon for .cur files
    def to_rc_text(self) -> str:
        name_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id)
        return f"{name_str} CURSOR \"placeholder_cursor_for_{name_str}.cur\""


class AniIconResource(Resource): # Animated Icon
    def __init__(self, identifier: ResourceIdentifier, ani_icon_data: bytes = b''):
        super().__init__(identifier, ani_icon_data) # Raw .ani file data

    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier):
        return cls(identifier, raw_data)

    def to_rc_text(self) -> str:
        name_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id)
        return f"{name_str} ANIICON \"placeholder_for_{name_str}.ani\"" # Custom type, not standard RC keyword


class AniCursorResource(Resource): # Animated Cursor
    def __init__(self, identifier: ResourceIdentifier, ani_cursor_data: bytes = b''):
        super().__init__(identifier, ani_cursor_data) # Raw .ani file data (same format as AniIcon)

    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier):
        return cls(identifier, raw_data)

    def to_rc_text(self) -> str:
        name_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id)
        return f"{name_str} ANICURSOR \"placeholder_for_{name_str}.ani\"" # Custom type, not standard RC keyword

class DlgInitResource(Resource): # Dialog Initialization Data
    def __init__(self, identifier: ResourceIdentifier, dlg_init_data: bytes = b''):
        super().__init__(identifier, dlg_init_data)

    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier):
        return cls(identifier, raw_data)

    def to_rc_text(self) -> str:
        name_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id)
        # DLGINIT is usually associated with a dialog, referenced by the dialog's ID
        # Example:
        # IDD_MYDIALOG DLGINIT
        # BEGIN
        #   IDC_COMBOBOX, 0x403, 4, "Item1\0Item2\0"
        #   ...
        # END
        # For now, a simple representation:
        return f"{name_str} DLGINIT\nBEGIN\n    // Raw data for control initialization\nEND"


# Mapping of RT_ constants to their respective classes
RESOURCE_TYPE_MAP = {
    RT_STRING: StringTableResource,
    RT_DIALOG: DialogResource,
    RT_ICON: IconResource,
    RT_GROUP_ICON: GroupIconResource,
    RT_BITMAP: BitmapResource,
    RT_MENU: MenuResource,
    RT_ACCELERATOR: AcceleratorResource,
    RT_VERSION: VersionInfoResource,
    RT_MANIFEST: ManifestResource,
    RT_HTML: HTMLResource,
    RT_RCDATA: RCDataResource,
    RT_CURSOR: CursorResource,
    RT_GROUP_CURSOR: GroupCursorResource,
    RT_ANICURSOR: AniCursorResource,
    RT_ANIICON: AniIconResource,
    RT_DLGINIT: DlgInitResource,
    # RT_FONTDIR, RT_FONT, RT_MESSAGETABLE, RT_PLUGPLAY, RT_VXD, RT_DLGINCLUDE
    # are less common or more complex and omitted for now.
}

def get_resource_class(type_id):
    return RESOURCE_TYPE_MAP.get(type_id, RCDataResource) # Default to RCData for unknown types

# Example Usage (Illustrative)
if __name__ == '__main__':
    # String Table Example
    str_id = ResourceIdentifier(RT_STRING, name_id=1, language_id=1033) # Block 1 (IDs 0-15)
    st_res = StringTableResource(str_id)
    st_res.add_string(0, "Hello World")
    st_res.add_string(1, "Another String")
    print(st_res.to_rc_text())
    print("-" * 20)

    # Dialog Example
    dlg_id = ResourceIdentifier(RT_DIALOG, name_id="MY_DIALOG", language_id=1033)
    dlg_res = DialogResource(dlg_id, caption="Test Dialog")
    print(dlg_res.to_rc_text())
    print("-" * 20)

    # Version Info Example
    ver_id = ResourceIdentifier(RT_VERSION, name_id=1, language_id=1033) # VS_VERSION_INFO
    ver_res = VersionInfoResource(ver_id)
    print(ver_res.to_rc_text())
    print("-" * 20)

    # Manifest Example
    manifest_id = ResourceIdentifier(RT_MANIFEST, name_id=1, language_id=0) # Usually lang neutral
                                        # Name usually 1 (CREATEPROCESS_MANIFEST_RESOURCE_ID)
                                        # or 2 (ISOLATIONAWARE_MANIFEST_RESOURCE_ID)
    manifest_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1">
    <application>
      <!-- Windows 10 -->
      <supportedOS Id="{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}"/>
    </application>
  </compatibility>
</assembly>"""
    manifest_res = ManifestResource(manifest_id, manifest_content)
    print(manifest_res.to_rc_text()) # Shows file reference
    # To get binary data for PE embedding:
    # binary_manifest = manifest_res.to_binary_data()
    # print(f"Binary manifest length: {len(binary_manifest)}")

    # Generic RCDATA Example
    rcdata_id = ResourceIdentifier(RT_RCDATA, name_id="MY_CUSTOM_DATA", language_id=1033)
    rcdata_res = RCDataResource(rcdata_id, raw_data=b"\x01\x02\x03\x04Hello")
    print(rcdata_res.to_rc_text()) # Shows file reference
    print(f"RCDATA binary data: {rcdata_res.to_binary_data()}")
    print("-" * 20)

    # HTML resource example
    html_id = ResourceIdentifier(RT_HTML, name_id="MY_HTML_PAGE", language_id=1033)
    html_res = HTMLResource(html_id, "<h1>Hello from HTML Resource</h1>")
    print(html_res.to_rc_text())
    print(f"HTML binary (UTF-8): {html_res.to_binary_data()}")
    print("-" * 20)

    # Group Icon (illustrative RC output)
    grp_icon_id = ResourceIdentifier(RT_GROUP_ICON, name_id="MAIN_ICON_GROUP", language_id=1033)
    grp_icon_res = GroupIconResource(grp_icon_id)
    print(grp_icon_res.to_rc_text())
    print("-" * 20)

```
