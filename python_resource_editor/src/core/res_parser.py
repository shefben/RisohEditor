# src/core/res_parser.py

from typing import List, Tuple, Any, Optional
import struct # For unpacking binary data
import os

from .resource_base import Resource, ResourceIdentifier
from .resource_types import RCDataResource # Using RCDataResource for all initially

# Notes on RES File Format (.res):
# Structure: Sequence of resource entries.
# Each entry:
# 1. RESOURCEHEADER:
#    - DataSize (DWORD): Size of the resource data that follows.
#    - HeaderSize (DWORD): Size of this header (from Type field to Characteristics field).
#                          Typically 0x1C (28 bytes) if Type/Name are numeric IDs.
#                          Or 28 + len(TypeStrBytes) + len(NameStrBytes) + padding.
#    - Type (WORD/String): If WORD is 0xFFFF, next WORD is numeric ID. Else, null-terminated Unicode string. Padded to DWORD.
#    - Name (WORD/String): Same logic as Type. Padded to DWORD.
#    - DataVersion (DWORD): Typically 0.
#    - MemoryFlags (WORD): MOVEABLE, PURE, PRELOAD, DISCARDABLE.
#    - LanguageId (WORD): LANGID.
#    - Version (DWORD): User-defined.
#    - Characteristics (DWORD): User-defined.
# 2. Resource Data: Raw binary data (DataSize bytes).
# 3. Padding: Data is padded to align on DWORD boundary.

def _read_padding(file_obj, current_pos: Optional[int] = None) -> int:
    """Reads padding bytes to align to the next DWORD boundary."""
    if current_pos is None:
        current_pos = file_obj.tell()

    padding_needed = (4 - (current_pos % 4)) % 4
    if padding_needed > 0:
        pad_bytes = file_obj.read(padding_needed)
        if len(pad_bytes) < padding_needed:
            raise EOFError("Unexpected EOF while reading padding.")
    return padding_needed

def _read_id_or_string_field(file_obj) -> Tuple[Optional[Any], bool]:
    """
    Reads a Type or Name field from a RES file stream.
    A field can be a numeric ID (WORD preceded by 0xFFFF) or a null-terminated Unicode string.
    The field (including padding for strings) is aligned to a DWORD boundary.

    Returns:
        A tuple (value, is_string). value is int or str. is_string is True if a string was read.
        Returns (None, False) on EOF.
    """
    start_pos = file_obj.tell()

    # Read the first WORD to determine if it's an ID or string.
    first_word_bytes = file_obj.read(2)
    if not first_word_bytes or len(first_word_bytes) < 2:
        return None, False # EOF

    first_word = struct.unpack('<H', first_word_bytes)[0]

    if first_word == 0xFFFF: # Numeric ID follows
        id_bytes = file_obj.read(2)
        if not id_bytes or len(id_bytes) < 2:
            raise EOFError("Unexpected EOF reading numeric ID in RES Type/Name field.")
        actual_id = struct.unpack('<H', id_bytes)[0]
        # The 0xFFFF and the ID WORD make up 4 bytes, so it's already DWORD aligned.
        return actual_id, False
    else: # It's a string
        # We need to "put back" the first_word_bytes and read character by character.
        file_obj.seek(start_pos)

        char_bytes_list = []
        while True:
            two_bytes = file_obj.read(2)
            if not two_bytes or len(two_bytes) < 2:
                raise EOFError("Unexpected EOF reading string in RES Type/Name field.")
            if two_bytes[0] == 0 and two_bytes[1] == 0: # Null terminator (UTF-16LE)
                break
            char_bytes_list.append(two_bytes)

        val_str = b"".join(char_bytes_list).decode('utf-16-le')
        _read_padding(file_obj) # Align to DWORD boundary after the null-terminated string
        return val_str, True


def parse_res_file(res_filepath: str) -> List[RCDataResource]:
    """
    Parses a RES (compiled Windows Resource) file.
    """
    resources: List[RCDataResource] = []

    try:
        with open(res_filepath, 'rb') as f:
            while True:
                # Read DataSize and HeaderSize (each 4 bytes)
                data_header_size_bytes = f.read(8)
                if not data_header_size_bytes: # Clean EOF
                    break
                if len(data_header_size_bytes) < 8:
                    raise EOFError("Unexpected EOF reading DataSize/HeaderSize.")

                data_size, header_size = struct.unpack('<LL', data_header_size_bytes)

                # Record start of header to verify HeaderSize later, if needed for debugging
                # header_content_start_pos = f.tell()

                # Parse Type field
                type_val, _ = _read_id_or_string_field(f)
                if type_val is None: # Should indicate parse error or unclean EOF
                    print("Warning: Failed to parse Type field or unexpected EOF.")
                    break

                # Parse Name field
                name_val, _ = _read_id_or_string_field(f)
                if name_val is None:
                    print("Warning: Failed to parse Name field or unexpected EOF.")
                    break

                # The rest of the header fields (fixed size: 16 bytes)
                # DataVersion (4), MemoryFlags (2), LanguageId (2), Version (4), Characteristics (4)
                fixed_header_part_bytes = f.read(16)
                if len(fixed_header_part_bytes) < 16:
                    raise EOFError("Unexpected EOF reading fixed part of resource header.")

                _data_version, memory_flags, language_id, _version, _characteristics = \
                    struct.unpack('<LHHLL', fixed_header_part_bytes)

                # Optional: Validate HeaderSize if it's a concern
                # current_header_bytes_read = f.tell() - header_content_start_pos
                # if current_header_bytes_read != header_size:
                #    print(f"Warning: Parsed header size ({current_header_bytes_read}) differs from HeaderSize field ({header_size}).")
                #    This can happen if strings were not padded correctly or if HeaderSize definition varies.
                #    The logic of _read_id_or_string_field already handles its own padding.
                #    The fixed 16 bytes are DWORD aligned. So, HeaderSize should be correct if file is well-formed.

                resource_data = f.read(data_size)
                if len(resource_data) < data_size:
                    raise EOFError(f"Unexpected EOF reading resource data for {type_val}/{name_val}. Expected {data_size}, got {len(resource_data)}.")

                # Data block itself must be padded to DWORD boundary
                _read_padding(f, f.tell()) # Pass f.tell() to make explicit current position for padding calculation

                identifier = ResourceIdentifier(type_id=type_val, name_id=name_val, language_id=language_id)
                # For now, all RES file resources are stored as RCDataResource
                # In future, could use get_resource_class(type_val).parse_from_data(...)
                resources.append(RCDataResource(identifier, resource_data))

    except FileNotFoundError:
        print(f"Error: RES file not found at {res_filepath}")
    except EOFError as e:
        print(f"Error: Unexpected end of file while parsing RES: {e}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"An error occurred during RES parsing of '{res_filepath}': {e}")

    return resources


if __name__ == '__main__':
    print("res_parser.py executed directly for testing purposes.")
    # To test this properly, you would need a sample .res file.
    # You can create one using `rc.exe /r my_script.rc` which produces `my_script.res`.
    # For example, if you have `mytest.rc`:
    #   `rc /r mytest.rc` (will create mytest.res)
    # Then run this script or the main __main__.py with `mytest.res`.

    # Create a dummy RES file for a very basic test (highly simplified)
    # This dummy is likely not perfectly conforming but tests basic flow.
    dummy_res_filepath = "dummy_test.res"
    try:
        with open(dummy_res_filepath, 'wb')as f:
            # Resource 1: Numeric Type (ICON=3), Numeric Name (101)
            data1 = b"ICON_DATA_BYTES"
            data_size1 = len(data1)
            header_size1 = 28 # (Type: 4, Name: 4, FixedFields: 16) = 24, not 28. Let's assume _read_id_or_string_field handles alignment.
                               # Standard header size for numeric type/name is 28 (0x1C) bytes.
                               # This is: Type(2+2), Name(2+2), DataVersion(4), MemFlags(2), LangID(2), Version(4), Chars(4) = 24.
                               # The HeaderSize in RES file is from Type field start to end of Characteristics.
                               # It does not include DataSize and HeaderSize fields themselves.
                               # Let's use a more accurate calculation for HeaderSize if types are numeric.
                               # Type (0xFFFF + ID) = 4 bytes. Name (0xFFFF + ID) = 4 bytes. Fixed fields = 16 bytes. Total = 24 bytes.
            header_size1_calc = 4 + 4 + 16 # 24 bytes for numeric type/name

            f.write(struct.pack('<LL', data_size1, header_size1_calc)) # DataSize, HeaderSize
            f.write(struct.pack('<HH', 0xFFFF, 3))  # Type: RT_ICON (numeric)
            f.write(struct.pack('<HH', 0xFFFF, 101)) # Name: 101 (numeric)
            f.write(struct.pack('<LHHLL', 0, 0x10, 1033, 0, 0)) # DataVersion, MemFlags, LangID, Version, Chars
            f.write(data1)
            padding_needed = (4 - (len(data1) % 4)) % 4
            if padding_needed > 0: f.write(b'\0' * padding_needed)

            # Resource 2: String Type ("MYTYPE"), String Name ("MyResourceName")
            type_str2 = "MYTYPE".encode('utf-16-le') + b'\0\0' # Null terminated
            name_str2 = "MyResourceName".encode('utf-16-le') + b'\0\0'
            data2 = b"SOME_OTHER_DATA"
            data_size2 = len(data2)

            type_str_len_padded = (len(type_str2) + 3) & ~3
            name_str_len_padded = (len(name_str2) + 3) & ~3
            header_size2_calc = type_str_len_padded + name_str_len_padded + 16

            f.write(struct.pack('<LL', data_size2, header_size2_calc))
            f.write(type_str2)
            if len(type_str2) % 4 != 0: f.write(b'\0' * ((4 - (len(type_str2) % 4)) % 4)) # padding for type string
            f.write(name_str2)
            if len(name_str2) % 4 != 0: f.write(b'\0' * ((4 - (len(name_str2) % 4)) % 4)) # padding for name string
            f.write(struct.pack('<LHHLL', 0, 0x10, 1033, 0, 0))
            f.write(data2)
            padding_needed = (4 - (len(data2) % 4)) % 4
            if padding_needed > 0: f.write(b'\0' * padding_needed)

        print(f"\n--- Parsing dummy RES file: {dummy_res_filepath} ---")
        extracted_resources = parse_res_file(dummy_res_filepath)
        for i, res in enumerate(extracted_resources):
            print(f"Resource #{i+1}:")
            print(f"  Identifier: Type='{res.identifier.type_id}', Name='{res.identifier.name_id}', Lang={res.identifier.language_id}")
            print(f"  Data (first 20 bytes): {res.data[:20]}")
            print(f"  Data size: {len(res.data)}")
        print("--- Dummy RES parsing finished ---")

    except Exception as e:
        print(f"Error in dummy RES test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if os.path.exists(dummy_res_filepath):
            os.remove(dummy_res_filepath)

    print("\nTo test with a real RES file, run through src.__main__.py with a RES file path argument.")

```
