import customtkinter
import tkinter
from tkinter import simpledialog, messagebox, colorchooser
from typing import List, Dict, Callable, Optional, Union
import copy

from ..core.dialog_parser_util import DialogProperties, DialogControlEntry
from ..core.resource_types import DialogResource # For type hinting

# --- Control Class to RC Keyword Mapping (Simplified) ---
# This helps in generating more specific RC statements if needed, or identifying control types.
WIN_CONTROL_CLASSES = {
    "BUTTON": "BUTTON", "EDIT": "EDIT", "STATIC": "STATIC", "LISTBOX": "LISTBOX",
    "SCROLLBAR": "SCROLLBAR", "COMBOBOX": "COMBOBOX",
    # Common class atoms (hex strings or integers) - these are just examples
    0x0080: "BUTTON", 0x0081: "EDIT", 0x0082: "STATIC",
    0x0083: "LISTBOX", 0x0084: "SCROLLBAR", 0x0085: "COMBOBOX",
}
# Specific RC keywords for certain styles (e.g. PUSHBUTTON is a BUTTON with BS_PUSHBUTTON style)
# This mapping is more for RC text generation than strict parsing.
RC_KEYWORDS_TO_CLASS_STYLE = {
    "LTEXT": ("STATIC", 0x00000000), # SS_LEFT | WS_GROUP
    "RTEXT": ("STATIC", 0x00000002), # SS_RIGHT | WS_GROUP
    "CTEXT": ("STATIC", 0x00000001), # SS_CENTER | WS_GROUP
    "PUSHBUTTON": ("BUTTON", 0x00000000), # BS_PUSHBUTTON
    "DEFPUSHBUTTON": ("BUTTON", 0x00000001), # BS_DEFPUSHBUTTON
    "CHECKBOX": ("BUTTON", 0x00000002), # BS_CHECKBOX
    "RADIOBUTTON": ("BUTTON", 0x00000004), # BS_RADIOBUTTON
    "GROUPBOX": ("BUTTON", 0x00000007), # BS_GROUPBOX
    "EDITTEXT": ("EDIT", 0 ), # Basic edit control
    # LISTBOX, COMBOBOX etc. usually use their class name directly.
}


class DialogEditorFrame(customtkinter.CTkFrame):
    def __init__(self, master, dialog_resource: DialogResource, app_callbacks: Dict[str, Callable]):
        super().__init__(master)
        self.dialog_resource = dialog_resource
        self.app_callbacks = app_callbacks

        self.dialog_props_copy: DialogProperties = copy.deepcopy(dialog_resource.properties)
        self.controls_copy: List[DialogControlEntry] = copy.deepcopy(dialog_resource.controls)

        self.selected_control_entry: Optional[DialogControlEntry] = None
        self.preview_widgets: Dict[DialogControlEntry, customtkinter.CTkBaseClass] = {} # Map entry to widget

        self.grid_columnconfigure(0, weight=2)  # Preview area
        self.grid_columnconfigure(1, weight=1)  # Properties area
        self.grid_rowconfigure(0, weight=1)     # Preview and Properties
        self.grid_rowconfigure(1, weight=0)     # Action buttons at bottom

        # --- Dialog Preview Pane ---
        self.preview_panel = customtkinter.CTkFrame(self, fg_color="gray20") # Darker background for contrast
        self.preview_panel.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.preview_panel.grid_propagate(False) # Ensure it keeps its allocated size

        # The actual canvas/frame where dialog controls will be rendered
        # Using a CTkFrame for now, which can act like a canvas for placing widgets by coordinates
        self.preview_canvas = customtkinter.CTkFrame(self.preview_panel, width=self.dialog_props_copy.width, height=self.dialog_props_copy.height, fg_color="gray50")
        # Center the preview_canvas within preview_panel if panel is larger
        self.preview_canvas.place(relx=0.5, rely=0.5, anchor="center")
        # Add binding to select dialog properties if canvas itself is clicked
        self.preview_canvas.bind("<Button-1>", lambda e: self.on_control_selected_on_preview(None))


        # --- Properties Pane ---
        self.props_frame = customtkinter.CTkScrollableFrame(self, label_text="Properties")
        self.props_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self.prop_widgets_map: Dict[str, Union[customtkinter.CTkEntry, customtkinter.CTkCheckBox, customtkinter.CTkComboBox]] = {}

        # --- Action Buttons (Bottom, spanning both columns) ---
        action_button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        action_button_frame.grid(row=1, column=0, columnspan=2, pady=10, sticky="ew")
        # Configure columns to distribute buttons
        action_button_frame.grid_columnconfigure((0,1,2,3), weight=1)

        customtkinter.CTkButton(action_button_frame, text="Add Control", command=self.on_add_control).grid(row=0, column=0, padx=5)
        customtkinter.CTkButton(action_button_frame, text="Delete Control", command=self.on_delete_control).grid(row=0, column=1, padx=5)
        self.apply_props_button = customtkinter.CTkButton(action_button_frame, text="Apply Properties", command=self.apply_properties_to_selection)
        self.apply_props_button.grid(row=0, column=2, padx=5)
        customtkinter.CTkButton(action_button_frame, text="Apply All to Resource", command=self.apply_all_changes_to_resource).grid(row=0, column=3, padx=5)

        self.render_dialog_preview()
        self.display_dialog_properties() # Initially show dialog's own properties


    def render_dialog_preview(self):
        for widget in self.preview_canvas.winfo_children():
            widget.destroy()
        self.preview_widgets.clear()

        # Update canvas size based on dialog properties
        # Scale factor can be introduced if dialog units (DLUs) are used and need conversion to pixels.
        # For now, assume 1 DLU = 1 pixel for simplicity of preview.
        preview_width = max(100, self.dialog_props_copy.width) # Ensure minimum size for visibility
        preview_height = max(50, self.dialog_props_copy.height)
        self.preview_canvas.configure(width=preview_width, height=preview_height)

        # Render caption as a label on the preview_canvas (if it's a top-level dialog)
        # For a true preview, the caption is part of the window frame, not the canvas.
        # This is a visual cue.
        # customtkinter.CTkLabel(self.preview_canvas, text=self.dialog_props_copy.caption).place(x=5, y=2) # Example

        for control_entry in self.controls_copy:
            # Map control class_name to CTk widget types (simplified)
            widget_class = None
            widget_params = {"master": self.preview_canvas, "text": control_entry.text}

            # Basic class name mapping
            cn_upper = str(control_entry.class_name).upper()
            if "BUTTON" in cn_upper or cn_upper == str(WIN_CONTROL_CLASSES.get(0x0080)):
                widget_class = customtkinter.CTkButton
            elif "EDIT" in cn_upper or cn_upper == str(WIN_CONTROL_CLASSES.get(0x0081)):
                widget_class = customtkinter.CTkEntry
                widget_params["placeholder_text"] = control_entry.text # Entry uses placeholder for text
                del widget_params["text"]
            elif "STATIC" in cn_upper or cn_upper == str(WIN_CONTROL_CLASSES.get(0x0082)):
                widget_class = customtkinter.CTkLabel
            elif "LISTBOX" in cn_upper or cn_upper == str(WIN_CONTROL_CLASSES.get(0x0083)):
                widget_class = tkinter.Listbox # CTk doesn't have direct Listbox, use ttk or tk
                widget_params["master"] = self.preview_canvas # Ensure master is correct
                # Basic Listbox styling to some extent
                # widget_params.update({"bg": "gray30", "fg": "white", "borderwidth":0, "highlightthickness":0})
            elif "COMBOBOX" in cn_upper or cn_upper == str(WIN_CONTROL_CLASSES.get(0x0085)):
                widget_class = customtkinter.CTkComboBox
                widget_params["values"] = [control_entry.text] if control_entry.text else ["Sample Item"]
                widget_params["state"] = "readonly"
                del widget_params["text"] # ComboBox text is set via values/variable

            if widget_class:
                # For tkinter.Listbox, CTk theming won't apply directly.
                if widget_class == tkinter.Listbox:
                     preview_widget = widget_class(**widget_params)
                     preview_widget.insert("end", control_entry.text if control_entry.text else "Listbox Item")
                else:
                    preview_widget = widget_class(**widget_params)

                # Place according to dialog units (assuming 1 DLU = 1 pixel for now)
                preview_widget.place(x=control_entry.x, y=control_entry.y,
                                     width=control_entry.width, height=control_entry.height)

                # Make widget selectable
                preview_widget.bind("<Button-1>", lambda e, ctrl=control_entry: self.on_control_selected_on_preview(ctrl))
                self.preview_widgets[control_entry] = preview_widget
            else:
                # Fallback for unknown controls: show a simple frame
                fb_widget = customtkinter.CTkFrame(self.preview_canvas, border_width=1)
                fb_widget.place(x=control_entry.x, y=control_entry.y, width=control_entry.width, height=control_entry.height)
                customtkinter.CTkLabel(fb_widget, text=f"{control_entry.class_name}\n(Preview N/A)").pack(expand=True, fill="both")
                fb_widget.bind("<Button-1>", lambda e, ctrl=control_entry: self.on_control_selected_on_preview(ctrl))
                self.preview_widgets[control_entry] = fb_widget


    def _populate_props_pane(self, target_obj: Union[DialogProperties, DialogControlEntry]):
        for widget in self.props_frame.winfo_children(): widget.destroy()
        self.prop_widgets_map.clear()

        props_to_edit = []
        is_dialog = isinstance(target_obj, DialogProperties)

        if is_dialog:
            self.props_frame.configure(label_text="Dialog Properties")
            props_to_edit = [
                ("Caption", "caption", str), ("X", "x", int), ("Y", "y", int),
                ("Width", "width", int), ("Height", "height", int),
                ("Style (Hex)", "style", "hex"), ("ExStyle (Hex)", "ex_style", "hex"),
                ("Font Name", "font_name", str), ("Font Size", "font_size", int),
                ("Menu Name", "menu_name", str), ("Class Name", "class_name", str)
            ]
        elif isinstance(target_obj, DialogControlEntry):
            self.props_frame.configure(label_text=f"Control Properties ('{target_obj.text[:20]}...')")
            props_to_edit = [
                ("Text", "text", str), ("ID", "id_val", "id_str_or_int"), # Special handling for ID
                ("Symbolic ID", "symbolic_id_name", str),
                ("Class Name", "class_name", str),
                ("X", "x", int), ("Y", "y", int), ("Width", "width", int), ("Height", "height", int),
                ("Style (Hex)", "style", "hex"), ("ExStyle (Hex)", "ex_style", "hex"),
                ("Help ID", "help_id", int)
            ]

        for label_text, attr_name, data_type in props_to_edit:
            customtkinter.CTkLabel(self.props_frame, text=label_text).pack(anchor="w", padx=5, pady=(5,0))
            entry = customtkinter.CTkEntry(self.props_frame)
            current_val = getattr(target_obj, attr_name, "")
            if data_type == "hex":
                entry.insert(0, f"0x{current_val:X}" if isinstance(current_val, int) else str(current_val or "0"))
            elif data_type == "id_str_or_int": # For control ID
                 entry.insert(0, target_obj.get_id_display())
            else:
                entry.insert(0, str(current_val) if current_val is not None else "")

            entry.pack(fill="x", padx=5, pady=(0,5))
            self.prop_widgets_map[attr_name] = entry

    def display_dialog_properties(self):
        self.selected_control_entry = None # No control selected, showing dialog props
        self._populate_props_pane(self.dialog_props_copy)

    def display_control_properties(self, control_entry: DialogControlEntry):
        self.selected_control_entry = control_entry
        self._populate_props_pane(control_entry)
        # Highlight selected control in preview (e.g., change border)
        for ctrl, widget in self.preview_widgets.items():
            border_width = 2 if ctrl == control_entry else 0
            if isinstance(widget, (customtkinter.CTkButton, customtkinter.CTkLabel, customtkinter.CTkEntry, customtkinter.CTkComboBox)):
                 widget.configure(border_width=border_width, border_color="cyan" if border_width else None)
            elif isinstance(widget, customtkinter.CTkFrame): # Fallback widget
                 widget.configure(border_width=border_width, border_color="cyan" if border_width else "gray50")


    def on_control_selected_on_preview(self, control_entry: Optional[DialogControlEntry]):
        if control_entry:
            self.display_control_properties(control_entry)
        else: # Clicked on dialog canvas itself
            self.display_dialog_properties()
            # Clear highlights from any controls
            for widget in self.preview_widgets.values():
                 if isinstance(widget, (customtkinter.CTkButton, customtkinter.CTkLabel, customtkinter.CTkEntry, customtkinter.CTkComboBox)):
                     widget.configure(border_width=0)
                 elif isinstance(widget, customtkinter.CTkFrame):
                     widget.configure(border_width=1, border_color="gray50") # Reset border


    def apply_properties_to_selection(self):
        target_obj = self.selected_control_entry if self.selected_control_entry else self.dialog_props_copy
        if not target_obj: return

        changed = False
        for attr_name, entry_widget in self.prop_widgets_map.items():
            new_val_str = entry_widget.get()
            current_val = getattr(target_obj, attr_name, None)

            new_typed_val = None
            original_type = type(current_val) if current_val is not None else str # Default to str

            # Special handling for ID fields
            if isinstance(target_obj, DialogControlEntry) and attr_name == "id_val":
                if new_val_str.isdigit() or (new_val_str.startswith("0x")):
                    new_typed_val = int(new_val_str, 0)
                    # If ID becomes numeric, clear symbolic name if it was the same as old numeric ID
                    if target_obj.symbolic_id_name == str(current_val): setattr(target_obj, "symbolic_id_name", None)
                else: # Symbolic ID
                    new_typed_val = new_val_str # Keep as string, this is symbolic_id_name effectively
                    setattr(target_obj, "symbolic_id_name", new_val_str) # Store it in symbolic
                    # The actual numeric id_val might be 0 or some other convention for symbolic IDs
                    # For simplicity, let's keep id_val as the string too if it's symbolic
                    # This needs to be reconciled with how DialogControlEntry handles id_val vs symbolic_id_name
                if str(current_val) != str(new_typed_val) or (getattr(target_obj, "symbolic_id_name", None) != new_val_str and isinstance(new_typed_val, str)): changed = True

            elif isinstance(target_obj, DialogControlEntry) and attr_name == "symbolic_id_name":
                if current_val != new_val_str: setattr(target_obj, attr_name, new_val_str if new_val_str else None); changed = True
                continue # Handled with id_val or separately

            elif original_type is int or original_type is float : # Handles style, ex_style, help_id, x,y,w,h, font_size
                if new_val_str.lower().startswith("0x"): new_typed_val = int(new_val_str, 16)
                else: new_typed_val = int(new_val_str) if new_val_str else 0
            elif original_type is str:
                new_typed_val = new_val_str
            elif current_val is None: # For optional fields like menu_name, class_name if they were None
                new_typed_val = new_val_str if new_val_str else None

            if new_typed_val is not None and str(current_val) != str(new_typed_val): # Compare as string to handle type changes gracefully
                setattr(target_obj, attr_name, new_typed_val)
                changed = True

        if changed:
            if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
            self.render_dialog_preview() # Update preview if anything changed
            # Re-populate properties for the currently selected object to reflect type changes or cleaned values
            if self.selected_control_entry: self.display_control_properties(self.selected_control_entry)
            else: self.display_dialog_properties()


    def on_add_control(self):
        # Add a default new control (e.g., a button) to self.controls_copy
        new_id = 0
        # Find a unique ID (simple increment for now)
        existing_ids = {ctrl.id_val for ctrl in self.controls_copy if isinstance(ctrl.id_val, int)}
        new_id = max(existing_ids, default=-1) + 1
        if new_id < 100 : new_id = 100 # Start user IDs from a higher range

        new_control = DialogControlEntry(
            class_name="BUTTON", text="Button", id_val=new_id, symbolic_id_name=f"IDC_BUTTON{new_id}",
            x=10, y=10, width=50, height=14, style=0x50010000 # WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON
        )
        self.controls_copy.append(new_control)
        self.render_dialog_preview()
        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
        # Select the new control
        self.on_control_selected_on_preview(new_control)

    def on_delete_control(self):
        if self.selected_control_entry:
            if messagebox.askyesno("Delete Control", f"Delete control '{self.selected_control_entry.text}'?", parent=self):
                self.controls_copy.remove(self.selected_control_entry)
                self.selected_control_entry = None
                self.render_dialog_preview()
                self.display_dialog_properties() # Show dialog props after deleting a control
                if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
        else:
            messagebox.showinfo("Delete Control", "No control selected.", parent=self)

    def apply_all_changes_to_resource(self):
        self.dialog_resource.properties = copy.deepcopy(self.dialog_props_copy)
        self.dialog_resource.controls = copy.deepcopy(self.controls_copy)
        self.dialog_resource.dirty = True
        if self.app_callbacks.get('set_dirty_callback'):
            self.app_callbacks['set_dirty_callback'](True)
        messagebox.showinfo("Changes Applied", "All dialog changes applied to in-memory resource. Save file to persist.", parent=self)

if __name__ == '__main__':
    # Test DialogEditorFrame
    class DummyApp(customtkinter.CTk):
        def __init__(self):
            super().__init__()
            self.title("Dialog Editor Test")
            self.geometry("900x700")

            from ..core.resource_base import ResourceIdentifier, RT_DIALOG
            ident = ResourceIdentifier(type_id=RT_DIALOG, name_id="IDD_TEST_DIALOG", language_id=1033)

            props = DialogProperties(name="IDD_TEST_DIALOG", caption="Test Dialog", width=250, height=150, style=0x90CA0000)
            controls = [
                DialogControlEntry("LTEXT", "Sample Static Text", "IDC_STATIC1", 10, 10, 100, 8, style=0x50000000),
                DialogControlEntry("EDITTEXT", "", "IDC_EDIT1", 10, 25, 150, 14, style=0x50010080), # WS_BORDER + ES_AUTOHSCROLL
                DialogControlEntry("BUTTON", "OK", "IDOK", 30, 120, 50, 14, style=0x50010001), # BS_DEFPUSHBUTTON
                DialogControlEntry("BUTTON", "Cancel", "IDCANCEL", 90, 120, 50, 14, style=0x50010000) # BS_PUSHBUTTON
            ]
            self.dialog_res = DialogResource(identifier=ident, properties=props, controls=controls)

            def set_dirty_test(is_dirty):
                print(f"App dirty state set to: {is_dirty}")
                self.title(f"Dialog Editor Test {'*' if is_dirty else ''}")

            editor = DialogEditorFrame(self, self.dialog_res, app_callbacks={'set_dirty_callback': set_dirty_test})
            editor.pack(expand=True, fill="both")

            self.protocol("WM_DELETE_WINDOW", self.quit_app)

        def quit_app(self):
            print("\nFinal DialogResource properties on quit:")
            print(self.dialog_res.properties)
            print("\nFinal DialogResource controls on quit:")
            for ctrl in self.dialog_res.controls:
                print(ctrl)
            self.destroy(); self.quit()

    customtkinter.set_appearance_mode("System")
    customtkinter.set_default_color_theme("blue")
    app = DummyApp()
    app.mainloop()
```
