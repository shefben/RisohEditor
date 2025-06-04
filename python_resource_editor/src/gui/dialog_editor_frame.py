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
    BS_PUSHBUTTON, WS_CHILD, WS_VISIBLE, WS_TABSTOP, WS_CAPTION, # Existing
    # Added for on_add_control control_types:
    ES_LEFT, WS_BORDER, WS_GROUP, LBS_STANDARD, CBS_DROPDOWNLIST, WS_VSCROLL,
    BS_GROUPBOX, SBS_HORZ, LVS_REPORT, TVS_HASLINES, TVS_LINESATROOT, TVS_HASBUTTONS
)
from ..core.resource_types import DialogResource # For type hinting
import ctypes
from ..utils import winapi_ctypes as wct
from ..core.resource_base import RT_DIALOG


class DialogEditorFrame(customtkinter.CTkFrame):
    def __init__(self, master, dialog_resource: DialogResource, app_callbacks: Dict[str, Callable]):
        super().__init__(master)
        self.dialog_resource = dialog_resource
        self.app_callbacks = app_callbacks

        self.dialog_props_copy: DialogProperties = copy.deepcopy(dialog_resource.properties)
        self.controls_copy: List[DialogControlEntry] = copy.deepcopy(dialog_resource.controls)

        self.selected_control_entry: Optional[DialogControlEntry] = None
        self.preview_widgets: Dict[DialogControlEntry, customtkinter.CTkBaseClass] = {}
        self._drag_data = {"widget": None, "control_entry": None, "start_x_widget": 0, "start_y_widget": 0, "start_x_event_root":0, "start_y_event_root":0}

        self.current_preview_hwnd: Optional[wct.HWND] = None
        self.py_dialog_proc = wct.DLGPROC(self._preview_dialog_proc_impl) # Keep reference


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

    def _preview_dialog_proc_impl(self, hwnd: wct.HWND, uMsg: wct.UINT, wParam: wct.WPARAM, lParam: wct.LPARAM) -> wct.INT_PTR:
        if uMsg == wct.WM_INITDIALOG:
            # Store the HWND of the created dialog if needed for later manipulation
            # self.actual_created_dialog_hwnd = hwnd
            return True # Processed
        # Add more message handling if needed for a preview (e.g., disabling controls)
        return False # Not processed

    def destroy_win32_preview(self):
        if self.current_preview_hwnd:
            wct.DestroyWindow(self.current_preview_hwnd)
            self.current_preview_hwnd = None

    def render_dialog_preview(self):
        self.destroy_win32_preview() # Clear previous Win32 preview first
        for widget in self.preview_canvas.winfo_children(): widget.destroy()
        self.preview_widgets.clear()
        preview_width = max(100, self.dialog_props_copy.width); preview_height = max(50, self.dialog_props_copy.height)
        self.preview_canvas.configure(width=preview_width, height=preview_height) # Keep this for canvas sizing

        # --- New Win32 Preview Logic ---
        template_data = self.dialog_resource.to_binary_data()
        if not template_data:
            customtkinter.CTkLabel(self.preview_canvas, text="Error: Failed to generate binary template for preview.").pack(padx=5, pady=5, expand=True)
            return
        if not isinstance(template_data, bytes) or len(template_data) == 0:
            customtkinter.CTkLabel(self.preview_canvas, text="Error: Generated binary template is empty or invalid.").pack(padx=5, pady=5, expand=True)
            return

        # Ensure lpTemplate is not garbage collected before CreateDialogIndirectParamW is called
        # by keeping a reference to it in the class or passing it appropriately.
        # For now, it's local to this function, which might be okay if CreateDialog is synchronous.
        self.lpTemplate_buffer = ctypes.create_string_buffer(template_data, len(template_data))
        lpTemplatePtr = ctypes.cast(self.lpTemplate_buffer, wct.LPVOID)

        try:
            hwnd_parent_preview = self.preview_canvas.winfo_id()
        except tkinter.TclError: # If canvas not yet mapped
            self.preview_canvas.update_idletasks()
            hwnd_parent_preview = self.preview_canvas.winfo_id()

        hInst = wct.GetModuleHandleW(None)
        if not hInst: # Fallback if GetModuleHandleW(None) returns 0
            hInst = wct.HINSTANCE(0) # For memory-based templates, hInstance can often be NULL or the current process's base.
                                     # Using 0 if GetModuleHandleW(None) fails, which might happen in some contexts.

        self.current_preview_hwnd = wct.CreateDialogIndirectParamW(
            hInst,
            lpTemplatePtr,
            hwnd_parent_preview,
            self.py_dialog_proc,
            0  # dwInitParam (lParam)
        )

        if not self.current_preview_hwnd or self.current_preview_hwnd.value == 0:
            error_code = ctypes.get_last_error()
            error_text = (f"Win32 Preview Error:\nCreateDialogIndirectParamW failed.\n"
                          f"Error Code: {error_code} (0x{error_code:X})\n"
                          f"Template Size: {len(template_data)} bytes\n"
                          f"hInst: {hInst.value if hInst else 'None'}\n"
                          f"Parent HWND: {hwnd_parent_preview}")
            customtkinter.CTkLabel(self.preview_canvas, text=error_text, wraplength=300).pack(padx=5, pady=5, expand=True)
            print(f"DEBUG: CreateDialogIndirectParamW failed with code {error_code}")
            print(f"DEBUG: Template (first 64 bytes): {template_data[:64].hex(' ', 1)}")
            self.current_preview_hwnd = None
        else:
            # Attempt to make it a child and remove frame for basic embedding
            original_style = wct.GetWindowLongW(self.current_preview_hwnd, wct.GWL_STYLE)
            new_style = (original_style & ~(wct.WS_POPUP | wct.WS_CAPTION | wct.WS_THICKFRAME | wct.WS_SYSMENU)) | wct.WS_CHILD

            # Ensure WS_VISIBLE is set if it was originally meant to be or if CreateDialog doesn't force it.
            # CreateDialogIndirectParam usually shows the dialog if DS_VISIBLE or WS_VISIBLE is in template.
            # Adding it here ensures it if it was stripped by FixupForRad for example.
            new_style |= wct.WS_VISIBLE

            wct.SetWindowLongW(self.current_preview_hwnd, wct.GWL_STYLE, new_style)

            original_ex_style = wct.GetWindowLongW(self.current_preview_hwnd, wct.GWL_EXSTYLE)
            new_ex_style = original_ex_style & ~(wct.WS_EX_DLGMODALFRAME | wct.WS_EX_WINDOWEDGE | wct.WS_EX_STATICEDGE | wct.WS_EX_APPWINDOW)
            wct.SetWindowLongW(self.current_preview_hwnd, wct.GWL_EXSTYLE, new_ex_style)

            # Set parent again after style changes
            wct.SetParent(self.current_preview_hwnd, hwnd_parent_preview)

            rect = wct.RECT()
            wct.user32.GetWindowRect(self.current_preview_hwnd, ctypes.byref(rect))
            dlg_width = rect.right - rect.left
            dlg_height = rect.bottom - rect.top

            # Ensure preview_canvas is at least as large as the dialog that was created
            # The DLU conversion happens inside Windows based on the dialog's font.
            current_canvas_width = self.preview_canvas.winfo_width()
            current_canvas_height = self.preview_canvas.winfo_height()

            new_canvas_width = max(current_canvas_width, dlg_width + 4) # Add some padding
            new_canvas_height = max(current_canvas_height, dlg_height + 4)

            if new_canvas_width > current_canvas_width or new_canvas_height > current_canvas_height:
                self.preview_canvas.configure(width=new_canvas_width, height=new_canvas_height)
                self.preview_canvas.update_idletasks() # Ensure canvas size is updated before placing dialog

            # Center the dialog within the preview_canvas
            final_canvas_width = self.preview_canvas.winfo_width()
            final_canvas_height = self.preview_canvas.winfo_height()
            place_x = (final_canvas_width - dlg_width) // 2
            place_y = (final_canvas_height - dlg_height) // 2

            wct.SetWindowPos(self.current_preview_hwnd, 0, place_x, place_y, dlg_width, dlg_height,
                               wct.SWP_FRAMECHANGED | wct.SWP_NOZORDER | wct.SWP_NOACTIVATE) # Removed SWP_NOSIZE, SWP_NOMOVE

            wct.ShowWindow(self.current_preview_hwnd, wct.SW_SHOW)

            # Create a CTk overlay to capture clicks on the canvas for deselection
            # This is a workaround as the Win32 dialog will capture mouse events over it.
            # We need a way to detect clicks on the "background" of the preview_canvas.
            # This overlay should be transparent to mouse events itself if possible, or handle them.
            # For now, the existing preview_canvas.bind("<Button-1>") might still work for areas not covered by the HWND.

            # No CTk widgets are created in this mode, so preview_widgets remains empty.
            # Selection/drag logic will need to be rethought if Win32 controls are to be interactive.
            # For now, this is a static preview.
            self.preview_widgets.clear() # Ensure this is clear as we are not adding CTk widgets

    def on_control_drag_start(self, event, widget: Union[customtkinter.CTkBaseClass, tkinter.Listbox], control_entry: DialogControlEntry):
        self.on_control_selected_on_preview(control_entry) # Select the control first

        # Record initial properties for dragging
        self._drag_data["widget"] = widget
        self._drag_data["control_entry"] = control_entry
        # Position of the widget itself on the canvas
        self._drag_data["start_x_widget"] = control_entry.x
        self._drag_data["start_y_widget"] = control_entry.y
        # Mouse position relative to root window (for calculating delta)
        self._drag_data["start_x_event_root"] = event.x_root
        self._drag_data["start_y_event_root"] = event.y_root


    def on_control_drag(self, event, widget: Union[customtkinter.CTkBaseClass, tkinter.Listbox], control_entry: DialogControlEntry):
        if self._drag_data["widget"] is not widget: # Not dragging this widget
            return

        delta_x = event.x_root - self._drag_data["start_x_event_root"]
        delta_y = event.y_root - self._drag_data["start_y_event_root"]

        new_x = self._drag_data["start_x_widget"] + delta_x
        new_y = self._drag_data["start_y_widget"] + delta_y

        # Basic boundary check against canvas (0,0)
        new_x = max(0, new_x)
        new_y = max(0, new_y)
        # Could add boundary check against canvas width/height if needed

        control_entry.x = new_x
        control_entry.y = new_y

        # Update widget placement visually
        if isinstance(widget, customtkinter.CTkBaseClass): # Covers CTkButton, CTkEntry, CTkLabel, CTkComboBox, CTkFrame, etc.
            widget.place(x=new_x, y=new_y)
        else: # Listbox or other
            widget.place(x=new_x, y=new_y, width=control_entry.width, height=control_entry.height)


        # Update properties pane if this control is selected
        if self.selected_control_entry == control_entry:
            if 'x' in self.prop_widgets_map: self.prop_widgets_map['x'].delete(0, tkinter.END); self.prop_widgets_map['x'].insert(0, str(new_x))
            if 'y' in self.prop_widgets_map: self.prop_widgets_map['y'].delete(0, tkinter.END); self.prop_widgets_map['y'].insert(0, str(new_y))

        if self.app_callbacks.get('set_dirty_callback'):
            self.app_callbacks['set_dirty_callback'](True)


    def on_control_drag_release(self, event, widget: Union[customtkinter.CTkBaseClass, tkinter.Listbox], control_entry: DialogControlEntry):
        if self._drag_data["widget"] is widget: # Finalize drag for this widget
            # Update the control_entry with the final position (already done in on_control_drag)
            # control_entry.x = widget.winfo_x() # This might be slightly off due to place() behavior
            # control_entry.y = widget.winfo_y()

            # Reset drag data
            self._drag_data["widget"] = None
            self._drag_data["control_entry"] = None

            # Persist changes and refresh UI if needed (already done by set_dirty and property update)
            if self.app_callbacks.get('set_dirty_callback'):
                self.app_callbacks['set_dirty_callback'](True)
            # Re-render or update properties if something wasn't real-time
            # self.display_control_properties(control_entry) # Could be called to ensure pane is perfectly synced


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
                effective_border_color = border_color
                if effective_border_color is None:
                    effective_border_color = "transparent"
                try: widget.configure(border_width=border_width, border_color=effective_border_color)
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
        control_types = { # Display Name: (class_name_val, default_text, default_style_val, default_width, default_height)
            "Button (Push)": ("BUTTON", "Button", BS_PUSHBUTTON | WS_VISIBLE | WS_CHILD | WS_TABSTOP, 50, 14),
            "Edit Control": ("EDIT", "", ES_LEFT | WS_BORDER | WS_VISIBLE | WS_CHILD | WS_TABSTOP, 100, 14), # ES_LEFT is 0
            "Static Text": ("STATIC", "Static Text", WS_VISIBLE | WS_CHILD | WS_GROUP, 100, 14), # SS_LEFT is 0
            "List Box": ("LISTBOX", "", LBS_STANDARD | WS_VISIBLE | WS_CHILD | WS_TABSTOP, 100, 50), # LBS_STANDARD includes border, vscroll
            "Combo Box": ("COMBOBOX", "", CBS_DROPDOWNLIST | WS_VISIBLE | WS_CHILD | WS_TABSTOP | WS_VSCROLL, 100, 14), # CBS_DROPDOWNLIST common
            "Group Box": ("BUTTON", "Group", BS_GROUPBOX | WS_VISIBLE | WS_CHILD, 100, 50),
            "Scrollbar": ("SCROLLBAR", "", SBS_HORZ | WS_VISIBLE | WS_CHILD, 100, 10), # SBS_HORZ=0
            # Common Controls (using string class names)
            "SysListView32": (WC_LISTVIEW, "ListView", WS_VISIBLE | WS_CHILD | WS_BORDER | LVS_REPORT, 150, 80), # LVS_REPORT=1
            "SysTreeView32": (WC_TREEVIEW, "TreeView", WS_VISIBLE | WS_CHILD | WS_BORDER | TVS_HASLINES | TVS_LINESATROOT | TVS_HASBUTTONS, 150, 80),
        }
        # TODO: Add more styles from dialog_parser_util as needed (e.g. ES_LEFT, CBS_DROPDOWNLIST, LVS_REPORT etc.)
        # For now, using some common combinations. ES_LEFT, SS_LEFT, SBS_HORZ are often 0.

        dialog = customtkinter.CTkInputDialog(text="Enter control type:", title="Add Control",
                                             # This InputDialog doesn't support combobox directly.
                                             # We'll ask for text and validate. A custom dialog would be better for fixed choices.
                                             # For now, let's list the options in the prompt.
                                             )
        # Hacky way to show options with CTkInputDialog:
        # This is not ideal. A proper CTkToplevel with a Combobox is better.
        # For this exercise, let's simplify and use a predefined list and ask for one by name via simpledialog.

        choices = list(control_types.keys())
        choice_str = simpledialog.askstring("Add Control", "Choose control type:\n\n" + "\n".join(choices), parent=self)

        if choice_str and choice_str in control_types:
            class_name_val, def_text, def_style, def_w, def_h = control_types[choice_str]

            new_id = max([ctrl.id_val for ctrl in self.controls_copy if isinstance(ctrl.id_val, int)], default=1000) + 1
            # Create a somewhat unique symbolic ID if possible
            base_symbolic_name = class_name_val if isinstance(class_name_val, str) else ATOM_TO_CLASSNAME_MAP.get(class_name_val, "CONTROL")
            symbolic_id_name = f"IDC_{base_symbolic_name.upper()}{new_id}"

            new_control = DialogControlEntry(
                class_name=class_name_val, text=def_text, id_val=new_id,
                symbolic_id_name=symbolic_id_name,
                x=10, y=10, width=def_w, height=def_h,
                style=def_style
            )
            self.controls_copy.append(new_control)
            self.render_dialog_preview()
            if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
            self.on_control_selected_on_preview(new_control) # Select the new control
        elif choice_str: # User entered something not in the list
             messagebox.showerror("Invalid Type", f"Control type '{choice_str}' is not recognized.", parent=self)


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

