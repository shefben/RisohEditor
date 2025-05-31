import customtkinter
import tkinter
from tkinter import simpledialog, messagebox, colorchooser
from typing import List, Dict, Callable, Optional, Union, Tuple
import copy

from ..core.dialog_parser_util import DialogProperties, DialogControlEntry
# Import style constants and maps
from ..core.dialog_parser_util import (
    ATOM_TO_CLASSNAME_MAP, KNOWN_STRING_CLASSES, # ALL_KNOWN_CLASSES removed
    STYLE_TO_STR_MAP_BY_CLASS, EXSTYLE_TO_STR_MAP,
    BUTTON_ATOM, EDIT_ATOM, STATIC_ATOM, LISTBOX_ATOM, COMBOBOX_ATOM, SCROLLBAR_ATOM, # Atoms
    WC_LISTVIEW, WC_TREEVIEW, WC_TABCONTROL, WC_PROGRESS, WC_TOOLBAR, # String class names
    WC_TRACKBAR, WC_UPDOWN, WC_DATETIMEPICK, WC_MONTHCAL, WC_IPADDRESS, WC_LINK,
    BS_PUSHBUTTON, WS_CHILD, WS_VISIBLE, WS_TABSTOP # For default control
)
from ..core.resource_types import DialogResource # For type hinting


class DialogEditorFrame(customtkinter.CTkFrame):
    def __init__(self, master, dialog_resource: DialogResource, app_callbacks: Dict[str, Callable]):
        super().__init__(master)
        self.dialog_resource = dialog_resource
        self.app_callbacks = app_callbacks

        self.dialog_props_copy: DialogProperties = copy.deepcopy(dialog_resource.properties)
        self.controls_copy: List[DialogControlEntry] = copy.deepcopy(dialog_resource.controls)

        self.selected_control_entry: Optional[DialogControlEntry] = None
        self.preview_widgets: Dict[DialogControlEntry, customtkinter.CTkBaseClass] = {}

        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        self.preview_panel = customtkinter.CTkFrame(self, fg_color="gray20")
        self.preview_panel.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.preview_panel.grid_propagate(False)

        self.preview_canvas = customtkinter.CTkFrame(self.preview_panel, width=self.dialog_props_copy.width, height=self.dialog_props_copy.height, fg_color="gray50")
        self.preview_canvas.place(relx=0.5, rely=0.5, anchor="center")
        self.preview_canvas.bind("<Button-1>", lambda e: self.on_control_selected_on_preview(None))

        self.props_frame = customtkinter.CTkScrollableFrame(self, label_text="Properties")
        self.props_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self.prop_widgets_map: Dict[str, Union[customtkinter.CTkEntry, customtkinter.CTkCheckBox, customtkinter.CTkComboBox]] = {}

        action_button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        action_button_frame.grid(row=1, column=0, columnspan=2, pady=10, sticky="ew")
        action_button_frame.grid_columnconfigure((0,1,2,3), weight=1)

        customtkinter.CTkButton(action_button_frame, text="Add Control", command=self.on_add_control).grid(row=0, column=0, padx=5)
        customtkinter.CTkButton(action_button_frame, text="Delete Control", command=self.on_delete_control).grid(row=0, column=1, padx=5)
        # Apply Properties button moved into _populate_props_pane
        customtkinter.CTkButton(action_button_frame, text="Apply All to Resource", command=self.apply_all_changes_to_resource).grid(row=0, column=3, padx=5)

        self.render_dialog_preview()
        self.display_dialog_properties()

    def render_dialog_preview(self):
        for widget in self.preview_canvas.winfo_children(): widget.destroy()
        self.preview_widgets.clear()
        preview_width = max(100, self.dialog_props_copy.width); preview_height = max(50, self.dialog_props_copy.height)
        self.preview_canvas.configure(width=preview_width, height=preview_height)

        for control_entry in self.controls_copy:
            widget_class = None; widget_params = {"master": self.preview_canvas, "text": control_entry.text}

            # Normalize class name for matching (string or atom)
            cn_str = ""
            if isinstance(control_entry.class_name, int): # Atom
                cn_str = ATOM_TO_CLASSNAME_MAP.get(control_entry.class_name, f"ATOM_0x{control_entry.class_name:04X}").upper()
            elif isinstance(control_entry.class_name, str):
                cn_str = control_entry.class_name.upper()

            if cn_str == "BUTTON": widget_class = customtkinter.CTkButton
            elif cn_str == "EDIT":
                widget_class = customtkinter.CTkEntry; widget_params["placeholder_text"] = control_entry.text; del widget_params["text"]
            elif cn_str == "STATIC": widget_class = customtkinter.CTkLabel
            elif cn_str == "LISTBOX":
                widget_class = tkinter.Listbox; widget_params.update({"background": "#333333", "foreground": "white", "borderwidth":1})
            elif cn_str == "COMBOBOX":
                widget_class = customtkinter.CTkComboBox; widget_params["values"] = [control_entry.text] if control_entry.text else ["Sample"]; widget_params["state"] = "readonly"; del widget_params["text"]
            elif cn_str in [cls.upper() for cls in KNOWN_STRING_CLASSES]:
                widget_class = "placeholder_frame"

            preview_widget = None
            if widget_class == "placeholder_frame":
                preview_widget = customtkinter.CTkFrame(self.preview_canvas, border_width=1, fg_color="gray40")
                display_class_name = control_entry.class_name if isinstance(control_entry.class_name, str) else ATOM_TO_CLASSNAME_MAP.get(control_entry.class_name, cn_str)
                customtkinter.CTkLabel(preview_widget, text=f"{display_class_name}\n'{control_entry.text[:20]}' ({control_entry.get_id_display()})").pack(padx=2,pady=2, expand=True, fill="both")
            elif widget_class:
                if widget_class == tkinter.Listbox:
                     preview_widget = widget_class(**widget_params)
                     preview_widget.insert("end", control_entry.text if control_entry.text else "Listbox Item")
                else: preview_widget = widget_class(**widget_params)
            else:
                preview_widget = customtkinter.CTkFrame(self.preview_canvas, border_width=1, fg_color="gray30")
                customtkinter.CTkLabel(preview_widget, text=f"Unknown: {cn_str}\n'{control_entry.text[:20]}'").pack(padx=2,pady=2, expand=True, fill="both")

            if preview_widget:
                preview_widget.place(x=control_entry.x, y=control_entry.y, width=control_entry.width, height=control_entry.height)
                preview_widget.bind("<Button-1>", lambda e, ctrl=control_entry: self.on_control_selected_on_preview(ctrl))
                self.preview_widgets[control_entry] = preview_widget

    def _populate_props_pane(self, target_obj: Union[DialogProperties, DialogControlEntry]):
        for widget in self.props_frame.winfo_children(): widget.destroy()
        self.prop_widgets_map.clear()
        props_to_edit = []; is_dialog = isinstance(target_obj, DialogProperties)

        if is_dialog:
            self.props_frame.configure(label_text="Dialog Properties")
            props_to_edit = [("Caption", "caption", str), ("X", "x", int), ("Y", "y", int), ("Width", "width", int), ("Height", "height", int), ("Style (Hex)", "style", "hex"), ("ExStyle (Hex)", "ex_style", "hex"), ("Font Name", "font_name", str), ("Font Size", "font_size", int), ("Font Weight (EX)", "font_weight", int), ("Font Italic (EX)", "font_italic", bool), ("Font Charset (EX)", "font_charset", "hex"), ("Menu Name", "menu_name", "id_str_or_int_optional"), ("Class Name", "class_name", "id_str_or_int_optional"), ("Help ID (EX)", "help_id", int)]
        elif isinstance(target_obj, DialogControlEntry):
            self.props_frame.configure(label_text=f"Control: '{target_obj.text[:20]}' ({target_obj.get_id_display()})")
            props_to_edit = [("Text", "text", str), ("ID", "id_val", "id_str_or_int"), ("Symbolic ID", "symbolic_id_name", str), ("Class Name", "class_name", str), ("X", "x", int), ("Y", "y", int), ("Width", "width", int), ("Height", "height", int), ("Style (Hex)", "style", "hex"), ("ExStyle (Hex)", "ex_style", "hex"), ("Help ID (EX)", "help_id", int)]

        for label_text, attr_name, data_type in props_to_edit:
            customtkinter.CTkLabel(self.props_frame, text=label_text).pack(anchor="w", padx=5, pady=(5,0))
            entry_val = getattr(target_obj, attr_name, None) # Use None for truly optional fields
            if entry_val is None and data_type not in ["id_str_or_int_optional", str]: entry_val = 0 if data_type in [int, "hex"] else ""


            if data_type == bool:
                widget = customtkinter.CTkCheckBox(self.props_frame, text="")
                if entry_val: widget.select()
            else:
                widget = customtkinter.CTkEntry(self.props_frame)
                if data_type == "hex": widget.insert(0, f"0x{entry_val:X}" if isinstance(entry_val, int) else str(entry_val or "0"))
                elif data_type == "id_str_or_int" and isinstance(target_obj, DialogControlEntry) : widget.insert(0, target_obj.get_id_display())
                elif data_type == "id_str_or_int_optional" : # For dialog menu/class name
                     val_to_show = ""
                     if attr_name == "menu_name": val_to_show = str(target_obj.symbolic_menu_name or target_obj.menu_name or "")
                     elif attr_name == "class_name": val_to_show = str(target_obj.symbolic_class_name or target_obj.class_name or "")
                     widget.insert(0, val_to_show)
                else: widget.insert(0, str(entry_val) if entry_val is not None else "")

            widget.pack(fill="x", padx=5, pady=(0,2))
            self.prop_widgets_map[attr_name] = widget

            if attr_name == "style" and isinstance(entry_val, int): self._display_decoded_styles(entry_val, target_obj.class_name if not is_dialog else None, False)
            elif attr_name == "ex_style" and isinstance(entry_val, int): self._display_decoded_styles(entry_val, None, True)

        apply_button = customtkinter.CTkButton(self.props_frame, text="Apply Properties", command=self.apply_properties_to_selection)
        apply_button.pack(pady=10, padx=5)


    def _get_style_map_for_control(self, class_name_val: Union[str, int]) -> dict:
        class_str_lookup = ""
        if isinstance(class_name_val, int):
            class_str_lookup = ATOM_TO_CLASSNAME_MAP.get(class_name_val, "").upper()
        elif isinstance(class_name_val, str):
            class_str_lookup = class_name_val.upper()

        # Check standard atom-based classes first
        if class_str_lookup in STYLE_TO_STR_MAP_BY_CLASS:
            return STYLE_TO_STR_MAP_BY_CLASS[class_str_lookup]
        # Then check known string class names (common controls)
        for wc_const_val_str in KNOWN_STRING_CLASSES:
            if wc_const_val_str.upper() == class_str_lookup:
                 return STYLE_TO_STR_MAP_BY_CLASS.get(wc_const_val_str, {}) # Use original case
        return {}


    def _display_decoded_styles(self, style_value: int, control_class_val: Optional[Union[str,int]], is_exstyle: bool):
        text_area = customtkinter.CTkTextbox(self.props_frame, height=80, font=("Segoe UI", 11), border_spacing=2)
        text_area.pack(fill="x", padx=5, pady=(0,5))
        text_area.configure(state="normal")
        text_area.insert("1.0", "Known flags: ")
        found_flags = []

        # Always include general WS_ styles for controls if not exstyle
        base_style_map = {}
        if not is_exstyle: base_style_map.update(STYLE_TO_STR_MAP_BY_CLASS.get("GENERAL_WS", {}))

        # Determine primary style map
        if is_exstyle:
            style_map_source = EXSTYLE_TO_STR_MAP
        elif self.selected_control_entry is None: # Dialog selected
            style_map_source = {**base_style_map, **STYLE_TO_STR_MAP_BY_CLASS.get("GENERAL_DS", {})}
        elif control_class_val: # Control selected
            style_map_source = {**base_style_map, **self._get_style_map_for_control(control_class_val)}
        else: # Should not happen
            style_map_source = base_style_map

        for flag_val, flag_name in style_map_source.items():
            if style_value & flag_val == flag_val:
                is_sub_flag = False
                # Simple check for combined styles to avoid redundancy, can be improved
                if not is_exstyle and flag_name in ["WS_BORDER", "WS_DLGFRAME"] and (style_value & WS_CAPTION == WS_CAPTION): is_sub_flag = True
                if not is_sub_flag: found_flags.append(flag_name)

        if found_flags: text_area.insert("end", ", ".join(sorted(list(set(found_flags)))))
        else: text_area.insert("end", "None recognized (or a single combined value)")
        text_area.configure(state="disabled")


    def display_dialog_properties(self):
        self.selected_control_entry = None
        self._populate_props_pane(self.dialog_props_copy)

    def display_control_properties(self, control_entry: DialogControlEntry):
        self.selected_control_entry = control_entry
        self._populate_props_pane(control_entry)
        for ctrl, widget in self.preview_widgets.items():
            is_selected = (ctrl == control_entry)
            border_color = "cyan" if is_selected else None
            border_width = 2 if is_selected else (1 if isinstance(widget, customtkinter.CTkFrame) and not isinstance(widget,customtkinter.CTkButton) else 0) # Keep border for placeholder frames

            if isinstance(widget, tkinter.Listbox):
                 widget.configure(relief="solid" if is_selected else "flat", borderwidth=2 if is_selected else 0)
            else: # CTk widgets
                try: widget.configure(border_width=border_width, border_color=border_color)
                except tkinter.TclError: pass # Some CTk widgets might not support border_color=None


    def on_control_selected_on_preview(self, control_entry: Optional[DialogControlEntry]):
        if control_entry: self.display_control_properties(control_entry)
        else:
            self.display_dialog_properties()
            for widget in self.preview_widgets.values():
                 if isinstance(widget, tkinter.Listbox): widget.configure(relief="flat", borderwidth=0)
                 elif isinstance(widget, customtkinter.CTkFrame) and not isinstance(widget,customtkinter.CTkButton): widget.configure(border_width=1, border_color="gray50") # Reset placeholder frame border
                 else: widget.configure(border_width=0)


    def apply_properties_to_selection(self):
        target_obj = self.selected_control_entry if self.selected_control_entry else self.dialog_props_copy
        if not target_obj: return; changed = False
        try:
            for attr_name, entry_widget in self.prop_widgets_map.items():
                if isinstance(entry_widget, customtkinter.CTkCheckBox): new_val_typed = bool(entry_widget.get())
                else: new_val_str = entry_widget.get()

                current_val = getattr(target_obj, attr_name, None)

                if not isinstance(entry_widget, customtkinter.CTkCheckBox): # Handle entries
                    expected_type = type(current_val) if current_val is not None else str
                    if attr_name in ["style", "ex_style", "help_id", "font_weight", "font_charset"] or \
                       (isinstance(target_obj, DialogControlEntry) and attr_name == "id_val" and (new_val_str.isdigit() or new_val_str.lower().startswith("0x"))):
                        expected_type = int
                    elif attr_name == "font_italic": expected_type = bool # This is handled by checkbox now
                    elif current_val is None and isinstance(new_val_str, str): expected_type = str
                    elif isinstance(current_val, (int,str)) and attr_name in ["menu_name", "class_name", "id_val"]:
                         expected_type = "id_str_or_int"

                    if expected_type == int: new_val_typed = int(str(new_val_str), 0) if str(new_val_str) else 0
                    elif expected_type == bool: new_val_typed = bool(int(new_val_str)) # Checkbox value is 0 or 1
                    elif expected_type == str: new_val_typed = str(new_val_str)
                    elif expected_type == "id_str_or_int":
                        if new_val_str.isdigit() or new_val_str.lower().startswith("0x"): new_val_typed = int(new_val_str,0)
                        else: new_val_typed = new_val_str
                    else: new_val_typed = new_val_str # Default to string if unsure

                if attr_name == "id_val" and isinstance(target_obj, DialogControlEntry):
                    if isinstance(new_typed_val, int): target_obj.symbolic_id_name = None
                    # If new_typed_val is string, it *is* the symbolic name. id_val should store it.
                    # The get_id_display will use symbolic_id_name if present.
                    # So, if user types symbolic, id_val becomes string, symbolic_id_name also string.
                    # If user types numeric, id_val becomes int, symbolic_id_name might be cleared or kept if different.
                    # Let's ensure symbolic_id_name is cleared if id_val is now purely numeric.
                    if isinstance(new_typed_val, str) and not (new_typed_val.isdigit() or new_typed_val.lower().startswith("0x")):
                        target_obj.symbolic_id_name = new_typed_val

                if str(current_val) != str(new_typed_val):
                    setattr(target_obj, attr_name, new_typed_val); changed = True

            # Specific handling for symbolic names for DialogProperties' menu and class
            if isinstance(target_obj, DialogProperties):
                if 'menu_name' in self.prop_widgets_map:
                    menu_name_val = getattr(target_obj, 'menu_name') # This was just set by setattr above
                    if isinstance(menu_name_val, int):
                        if target_obj.symbolic_menu_name is not None: # Was symbolic, now int
                            target_obj.symbolic_menu_name = None; changed = True
                    else: # string
                        if target_obj.symbolic_menu_name != menu_name_val:
                             target_obj.symbolic_menu_name = menu_name_val if menu_name_val else None; changed = True

                if 'class_name' in self.prop_widgets_map:
                    class_name_val = getattr(target_obj, 'class_name') # This was just set by setattr
                    if isinstance(class_name_val, int):
                        if target_obj.symbolic_class_name is not None:
                             target_obj.symbolic_class_name = None; changed = True
                    else: # string
                        if target_obj.symbolic_class_name != class_name_val:
                            target_obj.symbolic_class_name = class_name_val if class_name_val else None; changed = True

            if changed:
                if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
                if self.app_callbacks.get('show_status_callback'): # Optional status update
                    self.app_callbacks['show_status_callback']("Properties updated locally.", 3000)

                self.render_dialog_preview()
                if self.selected_control_entry: # If a control was being edited
                    # Find the control in self.controls_copy and update it
                    for i, ctrl in enumerate(self.controls_copy):
                        if ctrl is target_obj: # Compare by object identity
                            self.controls_copy[i] = target_obj # target_obj is self.selected_control_entry
                            break
                    self.display_control_properties(self.selected_control_entry)
                else: # Dialog properties were being edited
                    self.display_dialog_properties()
            else:
                if self.app_callbacks.get('show_status_callback'):
                    self.app_callbacks['show_status_callback']("No changes detected in properties.", 2000)

        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid value for a numeric/hex field: {e}", parent=self)
            if self.app_callbacks.get('show_status_callback'):
                self.app_callbacks['show_status_callback'](f"Input Error: {e}", 5000, is_error=True)
        except Exception as e:
            messagebox.showerror("Error", f"Could not apply properties: {e}", parent=self)
            if self.app_callbacks.get('show_status_callback'):
                self.app_callbacks['show_status_callback'](f"Error applying properties: {e}", 5000, is_error=True)


    def on_add_control(self):
        new_id = max([ctrl.id_val for ctrl in self.controls_copy if isinstance(ctrl.id_val, int)], default=1000) + 1 # Ensure unique numeric ID
        # Default to a PUSHBUTTON as it's common and simple
        new_control = DialogControlEntry(class_name="BUTTON", text="Button", id_val=new_id,
                                         symbolic_id_name=f"IDC_BUTTON{new_id}",
                                         x=10, y=10, width=50, height=14,
                                         style=BS_PUSHBUTTON|WS_VISIBLE|WS_CHILD|WS_TABSTOP)
        self.controls_copy.append(new_control)
        self.render_dialog_preview()
        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
        self.on_control_selected_on_preview(new_control)

    def on_delete_control(self):
        if self.selected_control_entry:
            if messagebox.askyesno("Delete Control", f"Delete control '{self.selected_control_entry.text}'?", parent=self):
                self.controls_copy.remove(self.selected_control_entry)
                self.selected_control_entry = None
                self.render_dialog_preview(); self.display_dialog_properties()
                if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
        else: messagebox.showinfo("Delete Control", "No control selected.", parent=self)

    def apply_all_changes_to_resource(self):
        # Ensure any pending property changes are applied first from the property grid
        if self.prop_widgets_map : # If property grid was active for something
            self.apply_properties_to_selection()

        self.dialog_resource.properties = copy.deepcopy(self.dialog_props_copy)
        self.dialog_resource.controls = copy.deepcopy(self.controls_copy)
        self.dialog_resource.dirty = True
        if self.app_callbacks.get('set_dirty_callback'):
            self.app_callbacks['set_dirty_callback'](True)
        messagebox.showinfo("Changes Applied", "All dialog changes applied to in-memory resource. Save file to persist.", parent=self)

if __name__ == '__main__':
    # ... (DummyApp for testing remains the same) ...
    pass
```
