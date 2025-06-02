# src/core/resource_types.py
from collections import namedtuple
from .resource_base import Resource, ResourceIdentifier, TextBlockResource, RT_STRING, RT_DIALOG, \
    RT_ICON, RT_GROUP_ICON, RT_BITMAP, RT_MENU, RT_ACCELERATOR, RT_VERSION, \
    RT_MANIFEST, RT_RCDATA, RT_HTML, RT_CURSOR, RT_GROUP_CURSOR, RT_ANICURSOR, \
    RT_ANIICON, RT_DLGINIT, LANG_NEUTRAL
from .rc_parser_util import StringTableEntry, parse_stringtable_rc_text, generate_stringtable_rc_text
from .menu_parser_util import (MenuItemEntry, parse_menu_rc_text, generate_menu_rc_text,
                               MF_POPUP, MF_STRING, MF_SEPARATOR, MF_END, MF_GRAYED, MF_DISABLED, MF_CHECKED,
                               MF_MENUBARBREAK, MF_MENUBREAK, MF_HELP, MF_OWNERDRAW,
                               MFT_STRING, MFT_BITMAP, MFT_SEPARATOR, MFT_RADIOCHECK, MFT_OWNERDRAW, MFR_POPUP, MFR_END,
                               MFS_GRAYED, MFS_DISABLED, MFS_CHECKED, MFS_HILITE, MFS_DEFAULT,
                               MENUEX_TEMPLATE_SIGNATURE_VERSION, MENUEX_HEADER_OFFSET_TO_ITEMS, FLAG_TO_STR_MAP)
from .dialog_parser_util import DialogProperties, DialogControlEntry, parse_dialog_rc_text, generate_dialog_rc_text
from .version_parser_util import VersionFixedInfo, VersionStringTableInfo, VersionVarEntry, parse_versioninfo_rc_text, generate_versioninfo_rc_text
from .accelerator_parser_util import AcceleratorEntry, parse_accelerator_rc_text, generate_accelerator_rc_text
from typing import List, Tuple, Union, Optional
import struct
import io


class StringTableResource(Resource):
    def __init__(self, identifier: ResourceIdentifier, entries: List[StringTableEntry] = None):
        super().__init__(identifier, data=b'')
        self.entries: List[StringTableEntry] = entries if entries is not None else []
    @classmethod
    def parse_from_text_block(cls, text_block_res: TextBlockResource) -> 'StringTableResource':
        entries = parse_stringtable_rc_text(text_block_res.text_content) if text_block_res.text_content else []
        return cls(text_block_res.identifier, entries)
    @classmethod
    def parse_from_binary_data(cls, raw_data: bytes, identifier: ResourceIdentifier) -> 'StringTableResource':
        entries: List[StringTableEntry] = []
        block_name_id = identifier.name_id
        if not isinstance(block_name_id, int) or block_name_id <= 0:
            block_num_plus_1 = 1
            if isinstance(block_name_id, str) and block_name_id.isdigit(): block_num_plus_1 = int(block_name_id)
            if block_num_plus_1 <=0: block_num_plus_1 = 1 # Final fallback
        else: block_num_plus_1 = block_name_id
        base_id = (block_num_plus_1 - 1) * 16
        stream = io.BytesIO(raw_data)
        for i in range(16):
            if stream.tell() + 2 > len(raw_data): break
            length_bytes = stream.read(2)
            if not length_bytes or len(length_bytes) < 2: break
            str_len_chars = struct.unpack('<H', length_bytes)[0]
            current_str_id = base_id + i
            if str_len_chars == 0: continue
            str_data_bytes = stream.read(str_len_chars * 2)
            if len(str_data_bytes) < str_len_chars * 2: print(f"Warning: Incomplete string data for ID {current_str_id}."); break
            value_str = str_data_bytes.decode('utf-16-le', errors='replace')
            entries.append(StringTableEntry(id_val=current_str_id, name_val=None, value_str=value_str))
        return cls(identifier, entries=entries)
    def to_rc_text(self) -> str: return generate_stringtable_rc_text(self.entries, self.identifier.language_id)

    def to_binary_data(self) -> bytes:
        block_num_plus_1 = 1
        if isinstance(self.identifier.name_id, int) and self.identifier.name_id > 0:
            block_num_plus_1 = self.identifier.name_id
        elif isinstance(self.identifier.name_id, str) and self.identifier.name_id.isdigit():
            parsed_id = int(self.identifier.name_id)
            if parsed_id > 0: block_num_plus_1 = parsed_id

        base_id = (block_num_plus_1 - 1) * 16
        strings_in_block = ["" for _ in range(16)]
        for entry in self.entries:
            str_id_val = 0
            if isinstance(entry.id_val, str) and entry.id_val.isdigit():
                str_id_val = int(entry.id_val)
            elif isinstance(entry.id_val, int):
                str_id_val = entry.id_val
            else:
                print(f"Warning: String with non-numeric ID '{entry.id_val}' cannot be saved to binary StringTable.")
                continue
            if base_id <= str_id_val < base_id + 16:
                index_in_block = str_id_val - base_id
                strings_in_block[index_in_block] = entry.value_str
            else:
                print(f"Warning: String ID {str_id_val} is outside the current block {block_num_plus_1} (range {base_id}-{base_id+15}). Skipping.")
        stream = io.BytesIO()
        for value_str in strings_in_block:
            if not value_str:
                stream.write(struct.pack('<H', 0))
            else:
                encoded_str = value_str.encode('utf-16-le')
                num_chars = len(encoded_str) // 2
                stream.write(struct.pack('<H', num_chars))
                stream.write(encoded_str)
        return stream.getvalue()

    def get_display_entries(self) -> List[Tuple[str, str, str]]:
        return [(str(e.id_val), e.name_val or "", e.value_str) for e in self.entries]
    def update_entry(self, old_id_val: Union[int,str], new_id_val: Union[int,str], new_name_val: Optional[str], new_value_str: str): # Simplified
        idx_to_update = -1
        for i, entry in enumerate(self.entries):
            if str(entry.id_val) == str(old_id_val) or (entry.name_val and entry.name_val == str(old_id_val)): idx_to_update = i; break
        if idx_to_update != -1:
            self.entries[idx_to_update] = StringTableEntry(new_id_val, new_value_str, new_name_val); self.dirty = True
        else: self.add_entry(new_id_val, new_name_val, new_value_str) 
    def add_entry(self, id_val: Union[int,str], name_val: Optional[str], value_str: str): # Simplified
        self.entries.append(StringTableEntry(id_val, value_str, name_val)); self.dirty = True
    def delete_entry(self, id_to_delete: Union[int,str]): # Simplified
        self.entries = [e for e in self.entries if not (str(e.id_val) == str(id_to_delete) or (e.name_val and e.name_val == str(id_to_delete)))]; self.dirty = True

class DialogResource(Resource):
    def __init__(self, identifier: ResourceIdentifier, properties: Optional[DialogProperties]=None, controls: Optional[List[DialogControlEntry]]=None):
        super().__init__(identifier, data=b''); self.properties = properties or DialogProperties(name=identifier.name_id, symbolic_name=(str(identifier.name_id) if isinstance(identifier.name_id, str) else None)); self.controls = controls or []
    @classmethod
    def parse_from_text_block(cls, text_block_res: TextBlockResource) -> 'DialogResource':
        props, controls = parse_dialog_rc_text(text_block_res.text_content)
        props = props or DialogProperties(name=text_block_res.identifier.name_id, symbolic_name=(str(text_block_res.identifier.name_id) if isinstance(text_block_res.identifier.name_id, str) else None), caption="Dialog (Parse Failed)")
        dialog_identifier = ResourceIdentifier(RT_DIALOG, props.name, text_block_res.identifier.language_id)
        props.name = dialog_identifier.name_id; props.symbolic_name = str(dialog_identifier.name_id) if isinstance(dialog_identifier.name_id, str) else None
        return cls(dialog_identifier, props, controls)

    @classmethod
    def parse_from_binary_data(cls, raw_data: bytes, identifier: ResourceIdentifier) -> 'DialogResource':
        from ..core.dialog_parser_util import _read_unicode_string_align, _read_word_or_string_align, ATOM_TO_CLASSNAME_MAP, DS_SETFONT, DS_SHELLFONT
        stream = io.BytesIO(raw_data)
        props = DialogProperties(name=identifier.name_id, symbolic_name=(str(identifier.name_id) if isinstance(identifier.name_id, str) else None), is_ex=False)
        controls_list: List[DialogControlEntry] = []
        c_dlg_items = 0
        i = -1 
        current_field = "Dialog Header Signature" 
        try:
            initial_pos = stream.tell()
            sig_check_bytes = stream.read(4)
            if len(sig_check_bytes) < 4: raise EOFError(f"Incomplete data for {current_field} (expected 4, got {len(sig_check_bytes)}).")
            stream.seek(initial_pos) 
            word1, word2 = struct.unpack('<HH', sig_check_bytes)

            if word1 == 1 and word2 == 0xFFFF: # DIALOGEX
                props.is_ex = True
                hdr_fmt = '<HHLLLHHHHH' 
                hdr_size = struct.calcsize(hdr_fmt) 
                current_field = "DIALOGEX Header"
                header_data = stream.read(hdr_size) 
                if len(header_data) < hdr_size: raise EOFError(f"Incomplete data for {current_field} (expected {hdr_size}, got {len(header_data)}).")
                header_tuple_ex = struct.unpack(hdr_fmt, header_data)
                props.help_id = header_tuple_ex[2]; props.ex_style = header_tuple_ex[3]; props.style = header_tuple_ex[4]; c_dlg_items = header_tuple_ex[5]; props.x, props.y, props.width, props.height = header_tuple_ex[6:10]
            else: # DLGTEMPLATE
                props.is_ex = False
                hdr_fmt = '<LLHHHHH' 
                hdr_size = struct.calcsize(hdr_fmt)
                current_field = "DLGTEMPLATE Header"
                header_data_std = stream.read(hdr_size)
                if len(header_data_std) < hdr_size: raise EOFError(f"Incomplete data for {current_field} (expected {hdr_size}, got {len(header_data_std)}).")
                header_tuple_std = struct.unpack(hdr_fmt, header_data_std)
                props.style = header_tuple_std[0]; props.ex_style = header_tuple_std[1]; c_dlg_items = header_tuple_std[2]; props.x, props.y, props.width, props.height = header_tuple_std[3:7]
            
            current_field = "Menu Name"
            menu_val, menu_is_str = _read_word_or_string_align(stream)
            if menu_val is None: 
                raise EOFError(f"Failed to read {current_field} at offset {stream.tell()} due to EOF or incomplete data from helper.")
            props.menu_name = menu_val if menu_val not in ["", 0] else None
            if menu_is_str and isinstance(menu_val, str) and menu_val != "": props.symbolic_menu_name = menu_val
            
            current_field = "Class Name"
            class_val, class_is_str = _read_word_or_string_align(stream)
            if class_val is None: 
                raise EOFError(f"Failed to read {current_field} at offset {stream.tell()} due to EOF or incomplete data from helper.")
            props.class_name = class_val if class_val not in ["", 0] else None
            if class_is_str and isinstance(class_val, str) and class_val != "": props.symbolic_class_name = class_val
            
            current_field = "Caption"
            caption_val = _read_unicode_string_align(stream)
            if caption_val is None: # Caption is mandatory, even if empty. None here means stream ended prematurely.
                raise EOFError(f"Failed to read {current_field} at offset {stream.tell()} due to EOF or incomplete data from helper.")
            props.caption = caption_val
            
            if props.style & (DS_SETFONT | DS_SHELLFONT):
                current_field = "Font PointSize"
                font_info_bytes = stream.read(2)
                if len(font_info_bytes) < 2: raise EOFError(f"Incomplete {current_field} data (expected 2, got {len(font_info_bytes)}).")
                props.font_size = struct.unpack('<H', font_info_bytes)[0]
                
                if props.is_ex:
                    current_field = "DIALOGEX Font extra data (Weight, Italic, Charset)"
                    font_extra_bytes = stream.read(4)
                    if len(font_extra_bytes) < 4 : raise EOFError(f"Incomplete {current_field} (expected 4, got {len(font_extra_bytes)}).")
                    props.font_weight, props.font_italic_byte, props.font_charset = struct.unpack('<HBB', font_extra_bytes); props.font_italic = bool(props.font_italic_byte)
                
                current_field = "Font Name"
                font_name_val = _read_unicode_string_align(stream)
                if font_name_val is None: # If DS_SETFONT is set, font name is expected.
                    raise EOFError(f"Failed to read {current_field} at offset {stream.tell()} due to EOF or incomplete data from helper.")
                props.font_name = font_name_val
            
            for i in range(c_dlg_items):
                current_field = f"Control #{i+1} alignment padding"
                align_pos = (stream.tell() + 3) & ~3
                if align_pos > len(raw_data):
                    raise EOFError(f"Alignment seek for control #{i+1} would go past EOF (current: {stream.tell()}, align_to: {align_pos}, total: {len(raw_data)}).")
                if stream.tell() < align_pos:
                    padding_bytes_to_read = align_pos - stream.tell()
                    padding_read = stream.read(padding_bytes_to_read)
                    if len(padding_read) < padding_bytes_to_read:
                        raise EOFError(f"EOF while reading alignment padding for control #{i+1} (expected {padding_bytes_to_read}, got {len(padding_read)}).")
                
                if stream.tell() >= len(raw_data):
                    print(f"Warning: Expected {c_dlg_items} controls, but found EOF at offset {stream.tell()} before reading header of control #{i+1}")
                    break 

                item_is_ex = props.is_ex
                help_id_ctrl, ex_style_ctrl, style_ctrl, x_ctrl, y_ctrl, w_ctrl, h_ctrl, id_ctrl = (0,0,0,0,0,0,0,0)
                
                if item_is_ex:
                    current_field = f"DLGITEMTEMPLATEEX header for ctrl #{i+1}"
                    item_hdr_fmt = '<LLLhhhhL'; item_hdr_size = struct.calcsize(item_hdr_fmt) 
                    item_header_data = stream.read(item_hdr_size)
                    if len(item_header_data) < item_hdr_size: raise EOFError(f"Incomplete data for {current_field} (expected {item_hdr_size}, got {len(item_header_data)}).")
                    help_id_ctrl, ex_style_ctrl, style_ctrl, x_ctrl, y_ctrl, w_ctrl, h_ctrl, id_ctrl = struct.unpack(item_hdr_fmt, item_header_data)
                else:
                    current_field = f"DLGITEMTEMPLATE header for ctrl #{i+1}"
                    item_hdr_fmt = '<LLhhhhH'; item_hdr_size = struct.calcsize(item_hdr_fmt) 
                    item_header_data = stream.read(item_hdr_size)
                    if len(item_header_data) < item_hdr_size: raise EOFError(f"Incomplete data for {current_field} (expected {item_hdr_size}, got {len(item_header_data)}).")
                    style_ctrl, ex_style_ctrl, x_ctrl, y_ctrl, w_ctrl, h_ctrl, id_ctrl_word = struct.unpack(item_hdr_fmt, item_header_data); id_ctrl = id_ctrl_word
                
                current_field = f"Control #{i+1} Class String/Ordinal"
                class_val_ctrl, _ = _read_word_or_string_align(stream)
                if class_val_ctrl is None: raise EOFError(f"EOF while reading {current_field}.")
                    
                current_field = f"Control #{i+1} Text String/Ordinal"
                text_val_ctrl, _ = _read_word_or_string_align(stream)
                if text_val_ctrl is None: raise EOFError(f"EOF while reading {current_field}.")

                class_name_str_ctrl = str(class_val_ctrl)
                if isinstance(class_val_ctrl, int): class_name_str_ctrl = ATOM_TO_CLASSNAME_MAP.get(class_val_ctrl, f"0x{class_val_ctrl:04X}")
                text_str_ctrl = str(text_val_ctrl) if isinstance(text_val_ctrl, str) else ""
                
                control_creation_data: Optional[bytes] = b''
                creation_data_size = 0
                
                current_field = f"Control #{i+1} Creation Data Size (WORD)"
                creation_data_size_bytes = stream.read(2)
                if len(creation_data_size_bytes) < 2:
                    raise EOFError(f"Incomplete {current_field} (expected 2, got {len(creation_data_size_bytes)}).")
                creation_data_size = struct.unpack('<H', creation_data_size_bytes)[0]

                if item_is_ex and creation_data_size == 0xFFFF:
                    current_field = f"Control #{i+1} Extended Creation Data Size (DWORD)"
                    actual_size_bytes = stream.read(4)
                    if len(actual_size_bytes) < 4:
                        raise EOFError(f"Incomplete {current_field} (expected 4, got {len(actual_size_bytes)}).")
                    creation_data_size = struct.unpack('<L', actual_size_bytes)[0]
                
                current_field = f"Control #{i+1} Creation Data (size: {creation_data_size})"
                current_stream_pos = stream.tell()
                if current_stream_pos + creation_data_size > len(raw_data):
                    print(f"Warning: control #{i+1} creation_data_size ({creation_data_size}) at offset {current_stream_pos} would overflow buffer (size {len(raw_data)}). Adjusting to {len(raw_data) - current_stream_pos}.")
                    creation_data_size = len(raw_data) - current_stream_pos
                    if creation_data_size < 0: creation_data_size = 0 

                if creation_data_size > 0:
                    control_creation_data = stream.read(creation_data_size)
                    if len(control_creation_data) < creation_data_size:
                        print(f"Warning: Short read for {current_field}. Expected {creation_data_size}, got {len(control_creation_data)} (stream pos: {stream.tell()}). Resource may be corrupt.")
                elif creation_data_size == 0: 
                    control_creation_data = b''

                ctrl = DialogControlEntry(class_name=class_name_str_ctrl, text=text_str_ctrl, id_val=id_ctrl,
                                          x=x_ctrl, y=y_ctrl, width=w_ctrl, height=h_ctrl,
                                          style=style_ctrl, ex_style=ex_style_ctrl,
                                          help_id=help_id_ctrl if item_is_ex else 0,
                                          symbolic_id_name=str(id_ctrl) if isinstance(id_ctrl, str) else None,
                                          creation_data=control_creation_data)
                controls_list.append(ctrl)
        except EOFError as e:
            err_msg = f"EOFError parsing dialog {repr(identifier.name_id)}"
            if 'current_field' in locals() and current_field:
                err_msg += f" while processing field: {repr(current_field)}"
            err_msg += f" at stream offset {stream.tell() if stream else 'N/A'}: {repr(e)}"
            print(err_msg)
        except struct.error as e:
            err_msg = f"Struct error parsing dialog {repr(identifier.name_id)}"
            if 'current_field' in locals() and current_field:
                err_msg += f" (field hint: {repr(current_field)})"
            err_msg += f" at stream offset {stream.tell() if stream else 'N/A'}: {repr(e)}"
            print(err_msg)
        except Exception as e:
            err_msg = f"Unexpected error parsing dialog {repr(identifier.name_id)}"
            if 'current_field' in locals() and current_field:
                 err_msg += f" (field hint: {repr(current_field)})"
            err_msg += f" at stream offset {stream.tell() if stream else 'N/A'}: {repr(e)}"
            print(err_msg)
            import traceback; traceback.print_exc()
        
        if 'props' not in locals() or props is None : 
            props = DialogProperties(name=identifier.name_id, caption=f"Dialog (Parse Fail for {repr(identifier.name_id)})")
        return cls(identifier, properties=props, controls=controls_list)

    def to_rc_text(self) -> str: return generate_dialog_rc_text(self.properties, self.controls, self.identifier.language_id)

    def _write_dialog_string_or_ordinal(self, stream: io.BytesIO, value: Union[str, int, None]):
        if value is None: 
            stream.write(struct.pack('<H', 0)) 
        elif isinstance(value, str):
            if not value: 
                 stream.write(struct.pack('<H', 0))
            else:
                encoded_value = value.encode('utf-16-le') + b'\x00\x00' 
                stream.write(encoded_value)
        elif isinstance(value, int): 
            stream.write(struct.pack('<HH', 0xFFFF, value))
        

    def to_binary_data(self) -> bytes:
        from ..core.dialog_parser_util import DS_SETFONT, DS_SHELLFONT, BUTTON_ATOM, EDIT_ATOM, STATIC_ATOM, LISTBOX_ATOM, SCROLLBAR_ATOM, COMBOBOX_ATOM, CLASSNAME_TO_ATOM_MAP
        stream = io.BytesIO()
        props = self.properties

        if props.is_ex:
            header_part1 = struct.pack('<HHLLLHHHHH',
                                     1, 0xFFFF, 
                                     props.help_id, props.ex_style, props.style,
                                     len(self.controls), props.x, props.y, props.width, props.height)
            stream.write(header_part1)
        else:
            header_part1 = struct.pack('<LLHHHHH',
                                     props.style, props.ex_style,
                                     len(self.controls), props.x, props.y, props.width, props.height)
            stream.write(header_part1)

        self._write_dialog_string_or_ordinal(stream, props.menu_name or props.symbolic_menu_name)
        current_pos = stream.tell(); padding = (4 - (current_pos % 4)) % 4
        if padding > 0: stream.write(b'\x00' * padding)

        self._write_dialog_string_or_ordinal(stream, props.class_name or props.symbolic_class_name)
        current_pos = stream.tell(); padding = (4 - (current_pos % 4)) % 4
        if padding > 0: stream.write(b'\x00' * padding)

        stream.write(props.caption.encode('utf-16-le') + b'\x00\x00')
        current_pos = stream.tell(); padding = (4 - (current_pos % 4)) % 4
        if padding > 0: stream.write(b'\x00' * padding)

        if props.style & (DS_SETFONT | DS_SHELLFONT):
            stream.write(struct.pack('<H', props.font_size))
            if props.is_ex:
                stream.write(struct.pack('<HBB', props.font_weight, 1 if props.font_italic else 0, props.font_charset))
            stream.write(props.font_name.encode('utf-16-le') + b'\x00\x00')
            current_pos = stream.tell(); padding = (4 - (current_pos % 4)) % 4
            if padding > 0: stream.write(b'\x00' * padding)

        for ctrl in self.controls:
            current_pos = stream.tell(); padding = (4 - (current_pos % 4)) % 4
            if padding > 0: stream.write(b'\x00' * padding)

            if props.is_ex:
                item_header = struct.pack('<LLLhhhhL',
                                          ctrl.help_id, ctrl.ex_style, ctrl.style,
                                          ctrl.x, ctrl.y, ctrl.width, ctrl.height,
                                          ctrl.id_val if isinstance(ctrl.id_val, int) else 0) 
                stream.write(item_header)
            else:
                item_header = struct.pack('<LLhhhhH',
                                          ctrl.style, ctrl.ex_style,
                                          ctrl.x, ctrl.y, ctrl.width, ctrl.height,
                                          ctrl.id_val if isinstance(ctrl.id_val, int) else 0) 
                stream.write(item_header)

            class_to_write: Union[str, int, None] = None
            if isinstance(ctrl.class_name, str):
                class_to_write = CLASSNAME_TO_ATOM_MAP.get(ctrl.class_name.upper(), ctrl.class_name)
            elif isinstance(ctrl.class_name, int): 
                class_to_write = ctrl.class_name
            self._write_dialog_string_or_ordinal(stream, class_to_write)
            current_pos = stream.tell(); padding = (4 - (current_pos % 4)) % 4
            if padding > 0: stream.write(b'\x00' * padding)
            
            ctrl_text_to_write: Union[str, int, None] = ctrl.text
            if isinstance(ctrl.text, str) and ctrl.text.startswith("#") and ctrl.text[1:].isdigit():
                 ctrl_text_to_write = int(ctrl.text[1:]) 
            self._write_dialog_string_or_ordinal(stream, ctrl_text_to_write)
            current_pos = stream.tell(); padding = (4 - (current_pos % 4)) % 4
            if padding > 0: stream.write(b'\x00' * padding)

            creation_data_bytes = ctrl.creation_data if ctrl.creation_data is not None else b''
            creation_data_len = len(creation_data_bytes)

            if props.is_ex:
                if creation_data_len > 0xFFFF:
                    stream.write(struct.pack('<HL', 0xFFFF, creation_data_len))
                else:
                    stream.write(struct.pack('<H', creation_data_len)) 
            else: 
                 stream.write(struct.pack('<H', creation_data_len)) 

            if creation_data_len > 0:
                stream.write(creation_data_bytes)
        return stream.getvalue()

class IconResource(Resource):
    def __init__(self, identifier: ResourceIdentifier, icon_data: bytes = b''): super().__init__(identifier, icon_data)
    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier): return cls(identifier, raw_data)

GrpIconDirEntryData = namedtuple("GrpIconDirEntryData", [
    "width", "height", "color_count", "reserved",
    "planes_or_x", "bit_count_or_y", "bytes_in_res", "icon_id"
])

class GroupIconResource(Resource):
    def __init__(self, identifier: ResourceIdentifier, icon_entries: Optional[List[GrpIconDirEntryData]] = None):
        super().__init__(identifier)
        self.icon_entries: List[GrpIconDirEntryData] = icon_entries if icon_entries is not None else []

    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier) -> 'GroupIconResource':
        entries: List[GrpIconDirEntryData] = []
        stream = io.BytesIO(raw_data)
        try:
            id_reserved, id_type, id_count = struct.unpack('<HHH', stream.read(6))
            for _ in range(id_count):
                entry_data = stream.read(14) 
                if len(entry_data) < 14:
                    print("Warning: Incomplete GRPICONDIRENTRY data.")
                    break
                bW, bH, bCC, bR, wPorX, wBorY, dwBytes, nID = struct.unpack('<BBBBHHLLH', entry_data)
                entries.append(GrpIconDirEntryData(bW, bH, bCC, bR, wPorX, wBorY, dwBytes, nID))
        except struct.error as e:
            print(f"Struct error parsing GroupIcon/Cursor data: {e}")
        except EOFError:
            print("EOFError parsing GroupIcon/Cursor data.")
        return cls(identifier, entries)

    def to_rc_text(self) -> str: name_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id); return f"{name_str} ICON \"placeholder_icon_for_{name_str}.ico\""

    def to_binary_data(self) -> bytes:
        if not self.icon_entries: return b''
        stream = io.BytesIO()
        is_cursor_group = self.identifier.type_id == RT_GROUP_CURSOR
        stream.write(struct.pack('<HHH', 0, (2 if is_cursor_group else 1), len(self.icon_entries)))
        for entry in self.icon_entries:
            if not isinstance(entry, dict) and not hasattr(entry, 'width'):
                print(f"Warning: Skipping invalid icon_entry in GroupIconResource: {entry}")
                continue
            width = entry.get('width', 0) if isinstance(entry, dict) else entry.width
            height = entry.get('height', 0) if isinstance(entry, dict) else entry.height
            color_count = entry.get('color_count', 0) if isinstance(entry, dict) else entry.color_count
            reserved = entry.get('reserved', 0) if isinstance(entry, dict) else entry.reserved
            planes_or_x = entry.get('planes_or_x', 0) if isinstance(entry, dict) else entry.planes_or_x
            bit_count_or_y = entry.get('bit_count_or_y', 0) if isinstance(entry, dict) else entry.bit_count_or_y
            bytes_in_res = entry.get('bytes_in_res', 0) if isinstance(entry, dict) else entry.bytes_in_res
            icon_id = entry.get('icon_id', 0) if isinstance(entry, dict) else entry.icon_id
            stream.write(struct.pack('<BBBBHHLLH',
                                     width, height, color_count, reserved,
                                     planes_or_x, bit_count_or_y,
                                     bytes_in_res, icon_id))
        return stream.getvalue()

class BitmapResource(Resource):
    def __init__(self, identifier: ResourceIdentifier, bitmap_data: bytes = b''): super().__init__(identifier, bitmap_data)
    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier): return cls(identifier, raw_data)
    def to_rc_text(self) -> str: name_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id); return f"{name_str} BITMAP \"placeholder_bitmap_for_{name_str}.bmp\""

class MenuResource(Resource):
    def __init__(self, identifier: ResourceIdentifier, items: List[MenuItemEntry] = None,
                 is_ex: bool = False, menu_name_rc:str = "",
                 characteristics_rc:str="0", version_rc:str="1", global_help_id_rc: Optional[int] = None):
        super().__init__(identifier, data=b'')
        self.items: List[MenuItemEntry] = items if items is not None else []
        self.is_ex: bool = is_ex
        self.menu_name_rc: str = menu_name_rc if menu_name_rc else \
            (str(identifier.name_id) if isinstance(identifier.name_id, int) else identifier.name_id)
        self.characteristics_rc: str = characteristics_rc
        self.version_rc: str = version_rc
        self.global_help_id_rc: Optional[int] = global_help_id_rc

    @classmethod
    def parse_from_text_block(cls, text_block_res: TextBlockResource) -> 'MenuResource':
        if not text_block_res.text_content: return cls(text_block_res.identifier, [])
        items, is_ex, name, chars, ver, help_id = parse_menu_rc_text(text_block_res.text_content)
        menu_identifier = ResourceIdentifier(RT_MENU, text_block_res.identifier.name_id, text_block_res.identifier.language_id)
        return cls(menu_identifier, items, is_ex, name, chars, ver, help_id)

    @classmethod
    def parse_from_binary_data(cls, raw_data: bytes, identifier: ResourceIdentifier) -> 'MenuResource':
        stream = io.BytesIO(raw_data); items: List[MenuItemEntry] = []; is_ex = False; menu_global_help_id: Optional[int] = None
        def _read_str_utf16_null_terminated(s: io.BytesIO) -> str:
            chars = [];
            while True:
                b = s.read(2)
                if not b or len(b) < 2 or b == b'\x00\x00': break;
                chars.append(b.decode('utf-16-le', errors='replace'));
            return "".join(chars)
        def _read_unicode_string_align_dword(s: io.BytesIO) -> str:
            start_pos = s.tell(); text = _read_str_utf16_null_terminated(s)
            bytes_read_for_text_and_null = (len(text) + 1) * 2
            total_field_len = (bytes_read_for_text_and_null + 3) & ~3
            s.seek(start_pos + total_field_len)
            return text
        def _parse_standard_items_binary_recursive(s: io.BytesIO, is_submenu: bool) -> List[MenuItemEntry]:
            current_items = []
            while s.tell() < len(raw_data):
                if s.tell() + 2 > len(raw_data): break
                item_flags_value = struct.unpack('<H', s.read(2))[0]
                item_type_str = "MENUITEM"
                if item_flags_value & MF_POPUP: item_type_str = "POPUP"
                elif item_flags_value & MF_SEPARATOR: item_type_str = "SEPARATOR"
                entry = MenuItemEntry(item_type=item_type_str, flags_numeric=item_flags_value, is_ex=False)
                flags_numeric=item_flags_value
                if not (item_flags_value & MF_POPUP) and item_type_str != "SEPARATOR":
                    if s.tell() + 2 > len(raw_data): break 
                    entry.id_val = struct.unpack('<H', s.read(2))[0]
                entry.text = _read_str_utf16_null_terminated(s)
                if item_flags_value & MF_POPUP:
                    entry.children, _ = _parse_standard_items_binary_recursive(s, True)
                current_items.append(entry)
                if flags_numeric & MF_END and is_submenu: return current_items, True 
                if s.tell() >= len(raw_data) and not (flags_numeric & MF_END and is_submenu) and not is_submenu: break
            return current_items, False 

        def _parse_menuex_items_binary_recursive(s: io.BytesIO) -> Tuple[List[MenuItemEntry], bool]: 
            current_items: List[MenuItemEntry] = []
            item_ended_menu = False
            while True: 
                align_offset = s.tell() % 4
                if align_offset != 0: s.read(4 - align_offset)
                if s.tell() + 12 > len(raw_data): break 
                dwType, dwState, ulId, bResInfo_val = struct.unpack('<LLLH', s.read(12))
                item_type_str_ex = "MENUITEM"
                if dwType & MF_POPUP: item_type_str_ex = "POPUP"
                elif dwType & MFT_SEPARATOR: item_type_str_ex = "SEPARATOR"
                item_text_ex = _read_unicode_string_align_dword(s)
                item_help_id = 0
                if not (dwType & MF_POPUP) and not (dwType & MFT_SEPARATOR):
                    if s.tell() + 4 > len(raw_data): break
                    item_help_id = struct.unpack('<L', s.read(4))[0]
                entry = MenuItemEntry(item_type=item_type_str_ex, text=item_text_ex, id_val=ulId, is_ex=True, type_numeric=dwType, state_numeric=dwState, help_id=item_help_id, bResInfo_word=bResInfo_val)
                current_items.append(entry)
                if dwType & MF_POPUP:
                    children, child_ended_menu = _parse_menuex_items_binary_recursive(s)
                    entry.children = children
                    if bResInfo_val & MFR_END: item_ended_menu = True; break
                if bResInfo_val & MFR_END: 
                    item_ended_menu = True; break
                if s.tell() >= len(raw_data) : break
            return current_items, item_ended_menu

        header_data = stream.read(4)
        if len(header_data) < 4: raise EOFError("Incomplete menu header.")
        version, header_word_2 = struct.unpack('<HH', header_data) 
        if version == MENUEX_TEMPLATE_SIGNATURE_VERSION and header_word_2 == MENUEX_HEADER_OFFSET_TO_ITEMS:
            is_ex = True
            help_id_data = stream.read(4) 
            if len(help_id_data) < 4: raise EOFError("Incomplete MENUEX_TEMPLATE_HEADER helpID.")
            menu_global_help_id = struct.unpack('<L', help_id_data)[0]
            items, _ = _parse_menuex_items_binary_recursive(stream) 
        else: 
            is_ex = False
            if header_word_2 > 0: 
                stream.read(header_word_2) 
            items, _ = _parse_standard_items_binary_recursive(stream, False) 
        menu_name = str(identifier.name_id) if isinstance(identifier.name_id, int) else identifier.name_id
        return cls(identifier, items=items, is_ex=is_ex, menu_name_rc=menu_name, global_help_id_rc=menu_global_help_id if is_ex else None)

    def to_rc_text(self) -> str:
        return generate_menu_rc_text(menu_name_rc=self.menu_name_rc, items=self.items, is_ex=self.is_ex, characteristics_rc=self.characteristics_rc, version_rc=self.version_rc, lang_id=self.identifier.language_id, global_help_id_rc=self.global_help_id_rc)

    def _get_numeric_flags_from_strings(self, item: MenuItemEntry, is_ex: bool) -> Tuple[int, int, int]:
        from ..core.menu_parser_util import (MF_POPUP, MF_STRING, MF_SEPARATOR, MF_END, MF_GRAYED, MF_DISABLED, MF_CHECKED,
                                           MF_MENUBARBREAK, MF_MENUBREAK, MF_OWNERDRAW, MF_HELP,
                                           MFT_STRING, MFT_BITMAP, MFT_MENUBARBREAK, MFT_MENUBREAK,
                                           MFT_OWNERDRAW, MFT_RADIOCHECK, MFT_SEPARATOR,
                                           MFS_GRAYED, MFS_DISABLED, MFS_CHECKED, MFS_HILITE, MFS_DEFAULT,
                                           MFR_POPUP, MFR_END, FLAG_TO_STR_MAP)
        type_numeric = 0; state_numeric = 0; bResInfo_numeric = 0
        is_popup_type = item.item_type == "POPUP"; is_separator_type = item.item_type == "SEPARATOR"
        if is_ex:
            if is_popup_type: type_numeric |= MF_POPUP 
            if is_separator_type: type_numeric |= MFT_SEPARATOR
            if "BITMAP" in item.flags: type_numeric |= MFT_BITMAP
            if "MENUBARBREAK" in item.flags: type_numeric |= MFT_MENUBARBREAK
            if "MENUBREAK" in item.flags: type_numeric |= MFT_MENUBREAK
            if "OWNERDRAW" in item.flags: type_numeric |= MFT_OWNERDRAW
            if "RADIO" in item.flags: type_numeric |= MFT_RADIOCHECK 
            if "CHECKED" in item.flags: state_numeric |= MFS_CHECKED
            if "DEFAULT" in item.flags: state_numeric |= MFS_DEFAULT
            if "GRAYED" in item.flags: state_numeric |= MFS_GRAYED 
            elif "INACTIVE" in item.flags: state_numeric |= MFS_DISABLED 
            if "HILITE" in item.flags: state_numeric |= MFS_HILITE
            if is_popup_type: bResInfo_numeric |= MFR_POPUP
        else: 
            type_numeric = 0 
            if is_popup_type: type_numeric |= MF_POPUP
            if is_separator_type: type_numeric |= MF_SEPARATOR
            if "GRAYED" in item.flags: type_numeric |= MF_GRAYED
            if "INACTIVE" in item.flags: type_numeric |= MF_DISABLED 
            if "CHECKED" in item.flags: type_numeric |= MF_CHECKED
            if "MENUBARBREAK" in item.flags: type_numeric |= MF_MENUBARBREAK
            if "MENUBREAK" in item.flags: type_numeric |= MF_MENUBREAK
            if "OWNERDRAW" in item.flags: type_numeric |= MF_OWNERDRAW
        return type_numeric, state_numeric, bResInfo_numeric

    def _write_standard_items_binary_recursive(self, stream: io.BytesIO, items_list: List[MenuItemEntry]):
        from ..core.menu_parser_util import MF_END
        num_items = len(items_list)
        for i, item in enumerate(items_list):
            mtOption, _, _ = self._get_numeric_flags_from_strings(item, is_ex=False)
            if i == num_items - 1: mtOption |= MF_END
            wId = 0
            if item.item_type != "POPUP" and item.item_type != "SEPARATOR":
                if isinstance(item.id_val, int): wId = item.id_val
            item_text_bytes = item.text.encode('utf-16-le') + b'\x00\x00' 
            stream.write(struct.pack('<H', mtOption))
            if not (mtOption & MF_POPUP) and item.item_type != "SEPARATOR":
                stream.write(struct.pack('<H', wId))
            stream.write(item_text_bytes)
            if item.item_type == "POPUP" and item.children:
                self._write_standard_items_binary_recursive(stream, item.children)

    def _write_menuex_items_binary_recursive(self, stream: io.BytesIO, items_list: List[MenuItemEntry]):
        from ..core.menu_parser_util import MF_POPUP, MFR_END 
        num_items = len(items_list)
        for i, item in enumerate(items_list):
            current_pos = stream.tell(); padding = (4 - (current_pos % 4)) % 4
            if padding > 0: stream.write(b'\x00' * padding)
            dwType, dwState, bResInfo = self._get_numeric_flags_from_strings(item, is_ex=True)
            if i == num_items - 1: bResInfo |= MFR_END
            ulId = 0
            if not (dwType & MF_POPUP) and item.item_type != "SEPARATOR": 
                 if isinstance(item.id_val, int): ulId = item.id_val
            item_text_bytes = item.text.encode('utf-16-le') + b'\x00\x00'
            stream.write(struct.pack('<LLLH', dwType, dwState, ulId, bResInfo))
            stream.write(item_text_bytes)
            current_pos_after_text = stream.tell(); padding_after_text = (4 - (current_pos_after_text % 4)) % 4
            if padding_after_text > 0: stream.write(b'\x00' * padding_after_text)
            if not (dwType & MF_POPUP) and item.item_type != "SEPARATOR":
                help_id_val = item.help_id if item.help_id is not None else 0
                stream.write(struct.pack('<L', help_id_val))
            if item.item_type == "POPUP" and item.children:
                self._write_menuex_items_binary_recursive(stream, item.children)

    def to_binary_data(self) -> bytes:
        from ..core.menu_parser_util import MENUEX_TEMPLATE_SIGNATURE_VERSION, MENUEX_HEADER_OFFSET_TO_ITEMS
        stream = io.BytesIO()
        if self.is_ex:
            version = MENUEX_TEMPLATE_SIGNATURE_VERSION 
            offset = MENUEX_HEADER_OFFSET_TO_ITEMS   
            help_id = self.global_help_id_rc if self.global_help_id_rc is not None else 0
            stream.write(struct.pack('<HH L', version, offset, help_id))
            self._write_menuex_items_binary_recursive(stream, self.items)
        else:
            stream.write(struct.pack('<HH', 0, 0)) 
            self._write_standard_items_binary_recursive(stream, self.items)
        return stream.getvalue()

class AcceleratorResource(Resource):
    def __init__(self, identifier: ResourceIdentifier, entries: Optional[List[AcceleratorEntry]] = None, table_name_rc: Optional[Union[str, int]] = None): super().__init__(identifier, data=b''); self.entries: List[AcceleratorEntry] = entries if entries is not None else []; self.table_name_rc: Union[str, int] = table_name_rc if table_name_rc is not None else identifier.name_id
    @classmethod
    def parse_from_text_block(cls, text_block_res: TextBlockResource) -> 'AcceleratorResource': _parsed_name, entries = parse_accelerator_rc_text(text_block_res.text_content); accel_identifier = ResourceIdentifier(RT_ACCELERATOR, text_block_res.identifier.name_id, text_block_res.identifier.language_id); return cls(accel_identifier, entries, table_name_rc=text_block_res.identifier.name_id)
    @classmethod
    def parse_from_binary_data(cls, raw_data: bytes, identifier: ResourceIdentifier) -> 'AcceleratorResource':
        from ..core.accelerator_parser_util import (AcceleratorEntry, FVIRTKEY, FSHIFT, FCONTROL, FALT, FNOINVERT, ACCEL_FLAG_MAP_TO_STR, format_accel_key_event_str, ACCEL_LAST_ENTRY_FVIRT)
        entries = []; stream = io.BytesIO(raw_data); entry_size = 8
        while stream.tell() < len(raw_data):
            entry_data = stream.read(entry_size)
            if len(entry_data) < entry_size: print(f"Warning: Incomplete accelerator entry data. Expected {entry_size}, got {len(entry_data)}."); break
            fFlags, key_code, cmd_id, _reserved = struct.unpack('<HHHH', entry_data)
            actual_fVirt = fFlags & 0xFF; is_last_entry_marker = (fFlags & (ACCEL_LAST_ENTRY_FVIRT << 8)) != 0
            if is_last_entry_marker and key_code == 0 and cmd_id == 0: break
            if fFlags == 0 and key_code == 0 and cmd_id == 0 and _reserved == 0 :
                 if stream.tell() >= len(raw_data) or len(raw_data) == entry_size: break
            type_flags_str_list = ["VIRTKEY"] if actual_fVirt & FVIRTKEY else ["ASCII"]
            for flag_val, flag_name in ACCEL_FLAG_MAP_TO_STR.items():
                if flag_val == FVIRTKEY: continue
                if actual_fVirt & flag_val: type_flags_str_list.append(flag_name)
            key_event_display_str = format_accel_key_event_str(key_code, actual_fVirt)
            entries.append(AcceleratorEntry(key_event_str=key_event_display_str, command_id=cmd_id, command_id_str=None, type_flags_str=type_flags_str_list))
            if is_last_entry_marker: break
        table_name_rc = str(identifier.name_id) if isinstance(identifier.name_id, int) else identifier.name_id
        return cls(identifier, entries=entries, table_name_rc=table_name_rc)

    def to_binary_data(self) -> bytes:
        from ..core.accelerator_parser_util import (FVIRTKEY, FSHIFT, FCONTROL, FALT, FNOINVERT, ACCEL_LAST_ENTRY_FVIRT,
                                                    VK_CODE_TO_STR_MAP)
        STR_TO_VK_CODE_MAP = {v: k for k, v in reversed(list(VK_CODE_TO_STR_MAP.items()))}
        stream = io.BytesIO()
        num_entries = len(self.entries)
        for i, entry in enumerate(self.entries):
            fFlags: int = 0; wAscii: int = 0; wId: int = 0 
            if isinstance(entry.command_id, int): wId = entry.command_id
            elif isinstance(entry.command_id, str) and entry.command_id.isdigit(): wId = int(entry.command_id)
            else: print(f"Warning: Symbolic command ID '{entry.command_id}' for accelerator not resolved to numeric. Using 0."); wId = 0
            is_virt_key_type = "VIRTKEY" in entry.type_flags_str; is_ascii_type = "ASCII" in entry.type_flags_str
            if "SHIFT" in entry.type_flags_str: fFlags |= FSHIFT
            if "CONTROL" in entry.type_flags_str: fFlags |= FCONTROL
            if "ALT" in entry.type_flags_str: fFlags |= FALT
            if "NOINVERT" in entry.type_flags_str: fFlags |= FNOINVERT
            key_str = entry.key_event_str.upper() 
            if is_virt_key_type or (not is_ascii_type and key_str.startswith("VK_")):
                fFlags |= FVIRTKEY
                if key_str in STR_TO_VK_CODE_MAP: wAscii = STR_TO_VK_CODE_MAP[key_str]
                elif key_str.startswith("VK_") and hasattr(globals(), key_str): wAscii = globals()[key_str]
                else:
                    try: wAscii = int(key_str) 
                    except ValueError: print(f"Warning: VIRTKEY '{entry.key_event_str}' not found in map or globals. Using 0."); wAscii = 0
            elif key_str.startswith("^"): 
                fFlags |= FVIRTKEY; fFlags |= FCONTROL 
                if len(key_str) == 2 and 'A' <= key_str[1] <= 'Z': wAscii = ord(key_str[1]) 
                else: print(f"Warning: Unrecognized ^-key format: '{entry.key_event_str}'. Using 0."); wAscii = 0
            else: 
                if not is_virt_key_type: 
                    if len(entry.key_event_str) == 1: wAscii = ord(entry.key_event_str[0])
                    else: print(f"Warning: ASCII key '{entry.key_event_str}' is not a single char. Using first char or 0."); wAscii = ord(entry.key_event_str[0]) if entry.key_event_str else 0
                else: print(f"Warning: VIRTKEY specified but key '{entry.key_event_str}' is unusual. Attempting direct char to code."); wAscii = ord(entry.key_event_str[0]) if entry.key_event_str else 0
            if i == num_entries - 1: fFlags |= (ACCEL_LAST_ENTRY_FVIRT << 8) 
            final_fFlags_word = fFlags & 0xFF 
            if i == num_entries - 1: final_fFlags_word |= (ACCEL_LAST_ENTRY_FVIRT << 8)
            stream.write(struct.pack('<HHHH', final_fFlags_word, wAscii, wId, 0)) 
        return stream.getvalue()

    def to_rc_text(self) -> str: name_to_use = self.table_name_rc if self.table_name_rc is not None else self.identifier.name_id; return generate_accelerator_rc_text(name_to_use, self.entries, self.identifier.language_id)

class VersionInfoResource(Resource): 
    def __init__(self, identifier: ResourceIdentifier, fixed_info: Optional[VersionFixedInfo] = None, string_tables: Optional[List[VersionStringTableInfo]] = None, var_info: Optional[List[VersionVarEntry]] = None): super().__init__(identifier, data=b''); self.fixed_info: VersionFixedInfo = fixed_info if fixed_info is not None else VersionFixedInfo(); self.string_tables: List[VersionStringTableInfo] = string_tables if string_tables is not None else []; self.var_info: List[VersionVarEntry] = var_info if var_info is not None else []
    @classmethod
    def parse_from_text_block(cls, text_block_res: TextBlockResource) -> 'VersionInfoResource':
        if not text_block_res.text_content: return cls(text_block_res.identifier)
        fixed, str_tbls, var_tbls = parse_versioninfo_rc_text(text_block_res.text_content)
        version_identifier = ResourceIdentifier(RT_VERSION, text_block_res.identifier.name_id, text_block_res.identifier.language_id)
        return cls(version_identifier, fixed, str_tbls, var_tbls)
    @classmethod
    def parse_from_binary_data(cls, raw_data: bytes, identifier: ResourceIdentifier) -> 'VersionInfoResource':
        from ..core.version_parser_util import (VersionFixedInfo, VersionStringEntry, VersionStringTableInfo, VersionVarEntry, _read_version_block_header, _read_version_string_value)
        stream = io.BytesIO(raw_data); fixed_info_obj: Optional[VersionFixedInfo] = None; sfi_list: List[VersionStringTableInfo] = []; vfi_list: List[VersionVarEntry] = []
        try:
            vi_len, vi_val_len, vi_type, vi_szkey, vi_header_len = _read_version_block_header(stream)
            if vi_szkey != "VS_VERSION_INFO": print(f"Warning: Expected 'VS_VERSION_INFO', got '{vi_szkey}'.")
            if vi_val_len == 52:
                ffi_data = stream.read(vi_val_len)
                if len(ffi_data) < 52: raise EOFError("Incomplete VS_FIXEDFILEINFO data.")
                ffi_values = struct.unpack('<13L', ffi_data)
                if ffi_values[0] == 0xFEEF04BD:
                    fixed_info_obj = VersionFixedInfo( file_version=(((ffi_values[2] >> 16) & 0xFFFF), (ffi_values[2] & 0xFFFF), ((ffi_values[3] >> 16) & 0xFFFF), (ffi_values[3] & 0xFFFF)), product_version=(((ffi_values[4] >> 16) & 0xFFFF), (ffi_values[4] & 0xFFFF), ((ffi_values[5] >> 16) & 0xFFFF), (ffi_values[5] & 0xFFFF)), file_flags_mask=ffi_values[6], file_flags=ffi_values[7], file_os=ffi_values[8], file_type=ffi_values[9], file_subtype=ffi_values[10], file_date_ms=ffi_values[11], file_date_ls=ffi_values[12])
                else: print("Warning: VS_FIXEDFILEINFO signature mismatch.")
            elif vi_val_len > 0: stream.read(vi_val_len) 
            current_pos_after_ffi_val = stream.tell(); padding = (4 - (current_pos_after_ffi_val % 4)) % 4
            if padding > 0: stream.read(padding)
            while stream.tell() < vi_len:
                child_block_start_pos = stream.tell();
                if child_block_start_pos >= vi_len : break
                child_len, child_val_len, child_type, child_szkey, child_hdr_len = _read_version_block_header(stream)
                if not child_len: break
                current_child_data_offset = stream.tell()
                if child_szkey == "StringFileInfo":
                    while stream.tell() < child_block_start_pos + child_len :
                        st_block_start_pos = stream.tell();
                        if st_block_start_pos >= child_block_start_pos + child_len: break
                        st_len, st_val_len, st_type, st_szkey_langpage, st_hdr_len = _read_version_block_header(stream)
                        if not st_len: break
                        current_sfi_table = VersionStringTableInfo(lang_codepage_hex=st_szkey_langpage, entries=[])
                        while stream.tell() < st_block_start_pos + st_len:
                            s_block_start_pos = stream.tell();
                            if s_block_start_pos >= st_block_start_pos + st_len: break
                            s_len, s_val_len_words, s_type, s_szkey, s_hdr_len = _read_version_block_header(stream)
                            if not s_len: break
                            s_value = _read_version_string_value(stream, s_val_len_words)
                            current_sfi_table.entries.append(VersionStringEntry(key=s_szkey, value=s_value))
                            stream.seek(s_block_start_pos + s_len); padding = (4 - (stream.tell() % 4)) % 4
                            if padding > 0: stream.read(padding)
                        sfi_list.append(current_sfi_table)
                        stream.seek(st_block_start_pos + st_len); padding = (4 - (stream.tell() % 4)) % 4
                        if padding > 0: stream.read(padding)
                elif child_szkey == "VarFileInfo":
                    while stream.tell() < child_block_start_pos + child_len:
                        var_block_start_pos = stream.tell();
                        if var_block_start_pos >= child_block_start_pos + child_len: break
                        var_len, var_val_len_bytes, var_type, var_szkey, var_hdr_len = _read_version_block_header(stream)
                        if not var_len: break
                        if var_szkey == "Translation" and var_val_len_bytes > 0:
                            var_data_values = []
                            for _i in range(var_val_len_bytes // 4):
                                lang_charset_bytes = stream.read(4)
                                if len(lang_charset_bytes) < 4: break
                                lang_id, charset_id = struct.unpack("<HH", lang_charset_bytes)
                                var_data_values.extend([lang_id, charset_id])
                            vfi_list.append(VersionVarEntry(key=var_szkey, values=var_data_values))
                        else: stream.read(var_val_len_bytes)
                        stream.seek(var_block_start_pos + var_len); padding = (4 - (stream.tell() % 4)) % 4
                        if padding > 0: stream.read(padding)
                else: stream.seek(child_block_start_pos + child_len)
                current_pos_after_child = stream.tell(); padding = (4 - (current_pos_after_child % 4)) % 4
                if padding > 0: stream.read(padding)
        except EOFError as e: print(f"EOFError parsing VersionInfo: {e}.")
        except struct.error as e: print(f"Struct error parsing VersionInfo: {e}.")
        except Exception as e: print(f"Unexpected error parsing VersionInfo: {e}"); import traceback; traceback.print_exc()
        if fixed_info_obj is None and not sfi_list and not vfi_list: return cls(identifier)
        return cls(identifier, fixed_info=fixed_info_obj, string_tables=sfi_list, var_info=vfi_list)
    def to_rc_text(self) -> str: id_name = self.identifier.name_id; id_name = "VS_VERSION_INFO" if isinstance(id_name, int) and id_name == 1 else (str(id_name) if not isinstance(id_name, str) else id_name); return generate_versioninfo_rc_text(fixed_info=self.fixed_info, string_tables=self.string_tables, var_info_list=self.var_info, resource_id_name=id_name, lang_id=self.identifier.language_id)

    def _write_version_block(self, stream: io.BytesIO, szKey: str, wValueLength: int, wType: int, value_data: bytes = b'', children_writer_func = None):
        block_start_pos = stream.tell()
        stream.write(struct.pack('<HHH', 0, wValueLength, wType))
        szKey_bytes = szKey.encode('utf-16-le') + b'\x00\x00'
        stream.write(szKey_bytes)
        current_pos = stream.tell(); padding = (4 - (current_pos % 4)) % 4
        if padding > 0: stream.write(b'\x00' * padding)
        if value_data:
            stream.write(value_data)
            current_pos = stream.tell(); padding = (4 - (current_pos % 4)) % 4
            if padding > 0: stream.write(b'\x00' * padding)
        if children_writer_func:
            children_writer_func() 
        block_end_pos = stream.tell(); wLength = block_end_pos - block_start_pos
        stream.seek(block_start_pos); stream.write(struct.pack('<H', wLength)); stream.seek(block_end_pos)

    def to_binary_data(self) -> bytes:
        stream = io.BytesIO()
        fixed_file_info_data = b''
        if self.fixed_info:
            ffi = self.fixed_info
            fixed_file_info_data = struct.pack(
                '<LLLLLLLLLLLLL', 
                0xFEEF04BD, 0x00010000, 
                (ffi.file_version[0] << 16) | ffi.file_version[1], 
                (ffi.file_version[2] << 16) | ffi.file_version[3], 
                (ffi.product_version[0] << 16) | ffi.product_version[1], 
                (ffi.product_version[2] << 16) | ffi.product_version[3], 
                ffi.file_flags_mask, ffi.file_flags, ffi.file_os, ffi.file_type, ffi.file_subtype,
                ffi.file_date_ms, ffi.file_date_ls
            )
        wValueLength_vs_version_info = len(fixed_file_info_data)
        def write_vs_version_info_children():
            if self.string_tables:
                def write_sfi_children():
                    for st_table in self.string_tables:
                        def write_stringtable_children():
                            for entry in st_table.entries:
                                value_bytes = entry.value.encode('utf-16-le') + b'\x00\x00'
                                str_val_len_words = (len(value_bytes) // 2)
                                self._write_version_block(stream, entry.key, str_val_len_words, 1, value_bytes)
                        self._write_version_block(stream, st_table.lang_codepage_hex, 0, 1, children_writer_func=write_stringtable_children)
                self._write_version_block(stream, "StringFileInfo", 0, 1, children_writer_func=write_sfi_children)
            if self.var_info:
                def write_vfi_children():
                    for var_entry in self.var_info:
                        if var_entry.key.upper() == "TRANSLATION" and var_entry.values:
                            var_data = b''
                            for i in range(0, len(var_entry.values), 2):
                                if i + 1 < len(var_entry.values): var_data += struct.pack('<HH', var_entry.values[i], var_entry.values[i+1])
                                else: var_data += struct.pack('<H', var_entry.values[i])
                            self._write_version_block(stream, var_entry.key, len(var_data), 0, var_data)
                self._write_version_block(stream, "VarFileInfo", 0, 1, children_writer_func=write_vfi_children)
        self._write_version_block(stream, "VS_VERSION_INFO", wValueLength_vs_version_info, 0, fixed_file_info_data, write_vs_version_info_children)
        return stream.getvalue()

class ManifestResource(Resource):
    def __init__(self, identifier: ResourceIdentifier, manifest_text: str = ""): super().__init__(identifier); self.manifest_text = manifest_text
    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier): manifest_text = raw_data.decode('utf-8', errors="replace"); return cls(identifier, manifest_text)
    def to_binary_data(self) -> bytes: return self.manifest_text.encode('utf-8')
    def to_rc_text(self) -> str: name_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id); return f"{name_str} RT_MANIFEST \"placeholder_for_{name_str}.manifest\""

class HTMLResource(Resource): 
    def __init__(self, identifier: ResourceIdentifier, html_content: str = ""): super().__init__(identifier); self.html_content = html_content
    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier):
        try:
            if raw_data.startswith(b'\xef\xbb\xbf'): html_content = raw_data[3:].decode('utf-8')
            else: html_content = raw_data.decode('utf-8')
        except UnicodeDecodeError: html_content = raw_data.decode('latin-1', errors='replace')
        return cls(identifier, html_content)
    def to_binary_data(self) -> bytes: return self.html_content.encode('utf-8')
    def to_rc_text(self) -> str: name_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id); return f"{name_str} HTML \"placeholder_for_{name_str}.html\""

class RCDataResource(Resource): 
    def __init__(self, identifier: ResourceIdentifier, raw_data: bytes = b''): super().__init__(identifier, raw_data)
    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier): return cls(identifier, raw_data)
    def to_rc_text(self) -> str:
        name_id_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id)
        type_id_str = self.identifier.type_id
        if isinstance(type_id_str, int): type_id_str = {RT_RCDATA: "RCDATA"}.get(self.identifier.type_id, str(self.identifier.type_id))
        lines = [f"{name_id_str} {type_id_str} DISCARDABLE", "BEGIN"]
        for i in range(0, len(self.data), 16):
            chunk = self.data[i:i+16]; hex_values = ", ".join([f"0x{b:02x}" for b in chunk])
            lines.append(f"    {hex_values}{',' if i + 16 < len(self.data) else ''}")
        lines.append("END"); return "\n".join(lines)

class CursorResource(IconResource): 
    def to_rc_text(self) -> str: name_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id); return f"{name_str} CURSOR \"placeholder_for_{name_str}.cur\""
class GroupCursorResource(GroupIconResource):
    def to_rc_text(self) -> str: name_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id); return f"{name_str} CURSOR \"placeholder_cursor_for_{name_str}.cur\"" 

class AniIconResource(Resource):
    def __init__(self, identifier: ResourceIdentifier, ani_icon_data: bytes = b''): super().__init__(identifier, ani_icon_data)
    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier): return cls(identifier, raw_data)
    def to_rc_text(self) -> str: name_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id); return f"{name_str} ANIICON \"placeholder_for_{name_str}.ani\""
class AniCursorResource(Resource): 
    def __init__(self, identifier: ResourceIdentifier, ani_cursor_data: bytes = b''): super().__init__(identifier, ani_cursor_data)
    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier): return cls(identifier, raw_data)
    def to_rc_text(self) -> str: name_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id); return f"{name_str} ANICURSOR \"placeholder_for_{name_str}.ani\""
class DlgInitResource(Resource): 
    def __init__(self, identifier: ResourceIdentifier, dlg_init_data: bytes = b''): super().__init__(identifier, dlg_init_data)
    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier): return cls(identifier, raw_data)
    def to_rc_text(self) -> str: name_str = f'"{self.identifier.name_id}"' if isinstance(self.identifier.name_id, str) else str(self.identifier.name_id); return f"{name_str} DLGINIT\nBEGIN\n    // Raw data\nEND"

RESOURCE_TYPE_MAP = { 
    RT_STRING: StringTableResource, RT_DIALOG: DialogResource, RT_ICON: IconResource, RT_GROUP_ICON: GroupIconResource,
    RT_BITMAP: BitmapResource, RT_MENU: MenuResource, RT_ACCELERATOR: AcceleratorResource, RT_VERSION: VersionInfoResource,
    RT_MANIFEST: ManifestResource, RT_HTML: HTMLResource, RT_RCDATA: RCDataResource, RT_CURSOR: CursorResource,
    RT_GROUP_CURSOR: GroupCursorResource, RT_ANICURSOR: AniCursorResource, RT_ANIICON: AniIconResource, RT_DLGINIT: DlgInitResource,
}
def get_resource_class(type_id): return RESOURCE_TYPE_MAP.get(type_id, RCDataResource)

if __name__ == '__main__': 
    str_id = ResourceIdentifier(RT_STRING, name_id=1, language_id=1033); st_res = StringTableResource(str_id); st_res.add_entry(0, None, "Hello World"); print(st_res.to_rc_text()); print("-" * 20)
