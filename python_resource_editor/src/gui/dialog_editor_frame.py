import customtkinter
import tkinter
from tkinter import simpledialog, messagebox, colorchooser
from typing import List, Dict, Callable, Optional, Union, Tuple
import copy
import ctypes
from ..utils import winapi_ctypes as wct
from ..core.resource_base import RT_DIALOG

from ..core.dialog_parser_util import DialogProperties, DialogControlEntry
from ..core.dialog_parser_util import (
    ATOM_TO_CLASSNAME_MAP, KNOWN_STRING_CLASSES,
    STYLE_TO_STR_MAP_BY_CLASS, EXSTYLE_TO_STR_MAP,
    BUTTON_ATOM, EDIT_ATOM, STATIC_ATOM, LISTBOX_ATOM, COMBOBOX_ATOM, SCROLLBAR_ATOM,
    WC_LISTVIEW, WC_TREEVIEW, WC_TABCONTROL, WC_PROGRESS, WC_TOOLBAR,
    WC_TRACKBAR, WC_UPDOWN, WC_DATETIMEPICK, WC_MONTHCAL, WC_IPADDRESS, WC_LINK,
    BS_PUSHBUTTON, WS_CHILD, WS_VISIBLE, WS_TABSTOP, WS_CAPTION, WS_GROUP,
    ES_LEFT, WS_BORDER, LBS_STANDARD, CBS_DROPDOWNLIST, WS_VSCROLL,
    BS_GROUPBOX, SBS_HORZ, LVS_REPORT, TVS_HASLINES, TVS_LINESATROOT, TVS_HASBUTTONS
)
from ..core.resource_types import DialogResource


class DialogEditorFrame(customtkinter.CTkFrame):
    def __init__(self, master, dialog_resource: DialogResource, app_callbacks: Dict[str, Callable]):
        super().__init__(master)
        self.dialog_resource = dialog_resource
        self.app_callbacks = app_callbacks

        self.dialog_props_copy: DialogProperties = copy.deepcopy(dialog_resource.properties)
        self.controls_copy: List[DialogControlEntry] = copy.deepcopy(dialog_resource.controls)

        self.selected_control_entry: Optional[DialogControlEntry] = None
        self.preview_widgets: Dict[DialogControlEntry, Union[customtkinter.CTkBaseClass, tkinter.Listbox]] = {}
        self._drag_data = {"widget": None, "control_entry": None, "start_x_widget": 0, "start_y_widget": 0, "start_x_event_root":0, "start_y_event_root":0}

        self.current_preview_hwnd = None
        self.py_dialog_proc = wct.DLGPROC(self._preview_dialog_proc_impl)
        self.lpTemplate_buffer = None

        self.resize_handle_widget: Optional[customtkinter.CTkFrame] = None
        self._resize_drag_data = {"widget": None, "control_entry": None, "start_x_event_root": 0, "start_y_event_root": 0, "start_width": 0, "start_height": 0}

        self.native_dlg_hwnd: Optional[wct.wintypes.HWND] = None
        self.native_wnd_proc_ref = wct.WNDPROC(self._external_dialog_wnd_proc)
        self.external_window_class_name = f"PyNativeDialogHost_{id(self)}"
        self.native_control_hwnds: Dict[DialogControlEntry, wct.wintypes.HWND] = {}


        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        self.preview_panel = customtkinter.CTkFrame(self, fg_color="gray20")
        self.preview_panel.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.preview_panel.grid_propagate(False)

        self.preview_canvas = customtkinter.CTkFrame(self.preview_panel, fg_color="transparent")
        self.preview_canvas.place(relx=0.5, rely=0.5, anchor="center")

        self.preview_canvas.grid_rowconfigure(0, weight=0)
        self.preview_canvas.grid_rowconfigure(1, weight=1)
        self.preview_canvas.grid_columnconfigure(0, weight=1)

        self.title_bar_label = customtkinter.CTkLabel(
            self.preview_canvas, text="Dialog Preview", fg_color=("gray75", "gray25"),
            corner_radius=0, anchor="w", height=24 )
        self.title_bar_label.grid(row=0, column=0, sticky="ew", padx=0, pady=0)

        self.hwnd_host_frame = customtkinter.CTkFrame(self.preview_canvas, fg_color="gray50")
        self.hwnd_host_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)

        self.hwnd_host_frame.bind("<Button-1>", lambda e: self.on_control_selected_on_preview(None))
        self.title_bar_label.bind("<Button-1>", lambda e: self.on_control_selected_on_preview(None))

        self.props_frame = customtkinter.CTkScrollableFrame(self, label_text="Properties")
        self.props_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self.prop_widgets_map: Dict[str, Union[customtkinter.CTkEntry, customtkinter.CTkCheckBox, customtkinter.CTkComboBox]] = {}

        action_button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        action_button_frame.grid(row=1, column=0, columnspan=2, pady=10, sticky="ew")
        action_button_frame.grid_columnconfigure((0,1,2,3,4), weight=1)

        customtkinter.CTkButton(action_button_frame, text="Add Control", command=self.on_add_control).grid(row=0, column=0, padx=5)
        customtkinter.CTkButton(action_button_frame, text="Delete Control", command=self.on_delete_control).grid(row=0, column=1, padx=5)
        customtkinter.CTkButton(action_button_frame, text="Show Native Window", command=self._create_external_native_window).grid(row=0, column=2, padx=5)
        customtkinter.CTkButton(action_button_frame, text="Apply All to Resource", command=self.apply_all_changes_to_resource).grid(row=0, column=4, padx=5)

        self.render_dialog_preview()
        self.display_dialog_properties()

    def destroy_win32_preview(self):
        if hasattr(self, 'current_preview_hwnd') and self.current_preview_hwnd and self.current_preview_hwnd.value != 0:
            wct.DestroyWindow(self.current_preview_hwnd)
            self.current_preview_hwnd = None
        if hasattr(self, 'lpTemplate_buffer'):
            self.lpTemplate_buffer = None

    def _preview_dialog_proc_impl(self, hwnd: wct.wintypes.HWND, uMsg: wct.wintypes.UINT, wParam: wct.wintypes.WPARAM, lParam: wct.wintypes.LPARAM) -> wct.wintypes.INT_PTR:
        if uMsg == wct.WM_INITDIALOG: return True
        return False

    def _external_dialog_wnd_proc(self, hwnd: wct.wintypes.HWND, uMsg: wct.wintypes.UINT, wParam: wct.wintypes.WPARAM, lParam: wct.wintypes.LPARAM) -> wct.wintypes.LPARAM:
        if uMsg == wct.WM_DESTROY:
            print(f"External native dialog WM_DESTROY received for HWND {hwnd.value if hwnd else 'N/A'}")
            if self.native_dlg_hwnd and hasattr(hwnd, 'value') and self.native_dlg_hwnd.value == hwnd.value:
                self.native_dlg_hwnd = None
            return wct.wintypes.LPARAM(0)
        elif uMsg == wct.WM_CLOSE:
            print(f"External native dialog WM_CLOSE received for HWND {hwnd.value if hwnd else 'N/A'}")
            if hwnd: wct.DestroyWindow(hwnd)
            return wct.wintypes.LPARAM(0)

        return wct.DefWindowProcW(hwnd, uMsg, wParam, lParam)

    def _create_external_native_window(self):
        if self.native_dlg_hwnd and self.native_dlg_hwnd.value != 0 :
            print("Attempting to focus existing external native window.")
            wct.ShowWindow(self.native_dlg_hwnd, wct.SW_SHOW)
            wct.user32.SetForegroundWindow(self.native_dlg_hwnd)
            return

        h_instance = wct.GetModuleHandleW(None)

        wc = wct.WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(wct.WNDCLASSEXW)
        wc.style = wct.CS_HREDRAW | wct.CS_VREDRAW
        wc.lpfnWndProc = self.native_wnd_proc_ref
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = h_instance
        wc.hIcon = wct.LoadIconW(None, wct.MAKEINTRESOURCE(wct.IDI_APPLICATION))
        wc.hCursor = wct.LoadCursorW(None, wct.MAKEINTRESOURCE(wct.IDC_ARROW))
        wc.hbrBackground = ctypes.cast(wct.COLOR_WINDOW + 1, wct.wintypes.HBRUSH)
        wc.lpszMenuName = None
        wc.lpszClassName = self.external_window_class_name
        wc.hIconSm = wct.LoadIconW(None, wct.MAKEINTRESOURCE(wct.IDI_APPLICATION))

        if not wct.RegisterClassExW(ctypes.byref(wc)):
            err = ctypes.get_last_error()
            if err != wct.ERROR_CLASS_ALREADY_EXISTS:
                print(f"Failed to register window class '{self.external_window_class_name}': Error {err}")
                return

        dialog_title = str(self.dialog_props_copy.caption or "Native Dialog Editor")

        # Convert dialog DLUs to pixels for the main window size
        # This assumes dialog_props_copy.x/y are not used for top-level window pos,
        # and width/height are content size in DLUs.
        main_dlu_rect = wct.RECT()
        main_dlu_rect.left = 0
        main_dlu_rect.top = 0
        main_dlu_rect.right = self.dialog_props_copy.width
        main_dlu_rect.bottom = self.dialog_props_copy.height

        # Create a temporary invisible dialog to use MapDialogRect, as it needs a valid HWND
        # that has the dialog font set (or system dialog font).
        # For a non-dialog window class, MapDialogRect might not use the correct base units
        # unless the window itself processes WM_SETFONT.
        # A simpler approach for the main window is to use a default size or calculate from screen.
        # For now, using a fixed pixel size for the main window, DLU conversion for controls.
        main_w, main_h = 500, 400
        # If we had a dummy HWND with dialog font:
        # wct.MapDialogRect(dummy_dialog_hwnd_for_font, ctypes.byref(main_dlu_rect))
        # main_w = main_dlu_rect.right
        # main_h = main_dlu_rect.bottom
        # if main_w < 100: main_w = 500 # Ensure minimum size
        # if main_h < 100: main_h = 400


        self.native_dlg_hwnd = wct.CreateWindowExW(
            0,
            self.external_window_class_name,
            dialog_title,
            wct.WS_OVERLAPPEDWINDOW | wct.WS_VISIBLE,
            wct.CW_USEDEFAULT, wct.CW_USEDEFAULT,
            main_w, main_h,
            None,
            None,
            h_instance,
            None
        )

        if not self.native_dlg_hwnd or self.native_dlg_hwnd.value == 0:
            print(f"Failed to create external native window: {ctypes.get_last_error()}")
            self.native_dlg_hwnd = None
        else:
            print(f"External native window '{dialog_title}' created with HWND: {self.native_dlg_hwnd.value}")
            self._populate_native_dialog_with_controls()

    def destroy_external_native_window(self):
        if self.native_dlg_hwnd and self.native_dlg_hwnd.value != 0:
            print(f"Destroying external native window: {self.native_dlg_hwnd.value}")
            wct.DestroyWindow(self.native_dlg_hwnd)
        self.native_control_hwnds.clear() # Cleared in WM_DESTROY of parent

    def _populate_native_dialog_with_controls(self):
        if not self.native_dlg_hwnd or self.native_dlg_hwnd.value == 0:
            print("Cannot populate controls: Native dialog host window does not exist.")
            return

        for control_entry, control_hwnd_val in list(self.native_control_hwnds.items()):
            if control_hwnd_val and control_hwnd_val.value != 0: # Check if HWND is valid before using
                 print(f"Native control HWND {control_hwnd_val.value} for ID {control_entry.get_id_display()} should be auto-destroyed with parent.")
            # No need to call DestroyWindow on children; parent destruction handles it.
            # Only remove from our tracking dictionary.
            if control_entry in self.native_control_hwnds: # Check existence before del
                del self.native_control_hwnds[control_entry]
        self.native_control_hwnds.clear() # Ensure it's empty before repopulating

        h_instance = wct.GetModuleHandleW(None) # Re-fetch h_instance

        for control_entry in self.controls_copy:
            native_class_name_str = ""
            if isinstance(control_entry.class_name, int):
                native_class_name_str = ATOM_TO_CLASSNAME_MAP.get(control_entry.class_name, str(control_entry.class_name))
            elif isinstance(control_entry.class_name, str):
                native_class_name_str = control_entry.class_name
            else:
                print(f"Warning: Unknown class name type for control ID {control_entry.get_id_display()}: {control_entry.class_name}")
                continue

            dw_style = control_entry.style | wct.WS_CHILD | wct.WS_VISIBLE

            control_id_int = 0
            if isinstance(control_entry.id_val, int):
                control_id_int = control_entry.id_val
            elif isinstance(control_entry.id_val, str):
                try: control_id_int = int(control_entry.id_val) # Handles "123"
                except ValueError: # Symbolic ID
                     print(f"Warning: Symbolic ID '{control_entry.id_val}' used for native control. Using hash. This may not be standard for non-dialog parents.")
                     control_id_int = hash(control_entry.id_val) & 0xFFFF

            h_menu_id = wct.wintypes.HMENU(control_id_int)
            window_text = str(control_entry.text or "")

            # Convert DLU to Pixels using MapDialogRect
            dlu_rect = wct.RECT()
            dlu_rect.left = control_entry.x
            dlu_rect.top = control_entry.y
            dlu_rect.right = control_entry.x + control_entry.width
            dlu_rect.bottom = control_entry.y + control_entry.height

            pixel_x, pixel_y, pixel_width, pixel_height = control_entry.x, control_entry.y, control_entry.width, control_entry.height # Fallback
            if self.native_dlg_hwnd and self.native_dlg_hwnd.value != 0: # Ensure parent HWND is valid
                if not wct.MapDialogRect(self.native_dlg_hwnd, ctypes.byref(dlu_rect)):
                    print(f"Warning: MapDialogRect failed for control ID {control_entry.get_id_display()}. Error: {ctypes.get_last_error()}. Using raw DLU values as pixels.")
                else:
                    pixel_x = dlu_rect.left
                    pixel_y = dlu_rect.top
                    pixel_width = dlu_rect.right - dlu_rect.left
                    pixel_height = dlu_rect.bottom - dlu_rect.top
                    if pixel_width < 0: pixel_width = 0
                    if pixel_height < 0: pixel_height = 0
            else:
                 print("Warning: Parent native_dlg_hwnd is invalid for MapDialogRect. Using raw DLU values.")


            control_hwnd = wct.CreateWindowExW(
                control_entry.ex_style, native_class_name_str, window_text, dw_style,
                pixel_x, pixel_y, pixel_width, pixel_height,
                self.native_dlg_hwnd, h_menu_id, h_instance, None )

            if control_hwnd and control_hwnd.value != 0:
                self.native_control_hwnds[control_entry] = control_hwnd
                print(f"Created native control: Class='{native_class_name_str}', Text='{window_text[:20]}', ID={control_id_int}, HWND={control_hwnd.value}, Pos=({pixel_x},{pixel_y}), Size=({pixel_width}x{pixel_height})")
            else:
                err = ctypes.get_last_error()
                print(f"Failed to create native control: Class='{native_class_name_str}', Text='{window_text[:20]}', ID={control_id_int}. Error: {err}")


    def render_dialog_preview(self):
        if hasattr(self, 'destroy_win32_preview'):
            self.destroy_win32_preview()
        for widget in self.hwnd_host_frame.winfo_children():
            widget.destroy()
        self.preview_widgets.clear()
        if self.resize_handle_widget:
            self.resize_handle_widget.destroy()
            self.resize_handle_widget = None
        self.title_bar_label.configure(text=str(self.dialog_props_copy.caption or "Dialog Preview"))
        self.title_bar_label.update_idletasks()
        host_width = max(100, self.dialog_props_copy.width)
        host_height = max(50, self.dialog_props_copy.height)
        self.hwnd_host_frame.configure(width=host_width, height=host_height)
        self.preview_canvas.update_idletasks()
        for control_entry in self.controls_copy:
            cn_str = ""
            if isinstance(control_entry.class_name, int):
                cn_str = ATOM_TO_CLASSNAME_MAP.get(control_entry.class_name, f"ATOM_0x{control_entry.class_name:04X}").upper()
            elif isinstance(control_entry.class_name, str):
                cn_str = control_entry.class_name.upper()
            widget_class = None
            widget_params = {"master": self.hwnd_host_frame}
            if cn_str == "BUTTON": widget_class = customtkinter.CTkButton; widget_params["text"] = control_entry.text
            elif cn_str == "EDIT": widget_class = customtkinter.CTkEntry; widget_params["placeholder_text"] = control_entry.text
            elif cn_str == "STATIC": widget_class = customtkinter.CTkLabel; widget_params["text"] = control_entry.text
            elif cn_str == "LISTBOX": widget_class = tkinter.Listbox; widget_params.update({"background": "#333333", "foreground": "white", "borderwidth":0, "highlightthickness":0})
            elif cn_str == "COMBOBOX": widget_class = customtkinter.CTkComboBox; widget_params["values"] = [control_entry.text] if control_entry.text else ["Sample"]; widget_params["state"] = "readonly"
            elif cn_str == "SCROLLBAR": widget_class = customtkinter.CTkScrollbar
            elif cn_str in [cls.upper() for cls in KNOWN_STRING_CLASSES]: widget_class = "placeholder_frame"
            preview_widget = None
            widget_constructor_params = { **widget_params, "width": control_entry.width, "height": control_entry.height }
            if widget_class == "placeholder_frame":
                preview_widget = customtkinter.CTkFrame(master=self.hwnd_host_frame, border_width=1, fg_color="gray40", width=control_entry.width, height=control_entry.height)
                display_class_name = control_entry.class_name if isinstance(control_entry.class_name, str) else ATOM_TO_CLASSNAME_MAP.get(control_entry.class_name, cn_str)
                customtkinter.CTkLabel(preview_widget, text=f"{display_class_name}\n'{control_entry.text[:20]}' ({control_entry.get_id_display()})").pack(padx=2,pady=2, expand=True, fill="both")
            elif widget_class:
                try:
                    if widget_class == tkinter.Listbox: preview_widget = widget_class(**widget_params); preview_widget.insert("end", control_entry.text if control_entry.text else "Listbox Item")
                    elif widget_class in [customtkinter.CTkButton, customtkinter.CTkEntry, customtkinter.CTkLabel, customtkinter.CTkComboBox, customtkinter.CTkScrollbar]: preview_widget = widget_class(**widget_constructor_params)
                    else: preview_widget = widget_class(**widget_constructor_params)
                except Exception as e:
                     print(f"Error creating widget for class '{cn_str}': {e}")
                     preview_widget = customtkinter.CTkFrame(master=self.hwnd_host_frame, border_width=1, fg_color="red", width=control_entry.width, height=control_entry.height)
                     customtkinter.CTkLabel(preview_widget, text=f"ERR: {cn_str}").pack()
            else:
                preview_widget = customtkinter.CTkFrame(master=self.hwnd_host_frame, border_width=1, fg_color="gray30", width=control_entry.width, height=control_entry.height)
                customtkinter.CTkLabel(preview_widget, text=f"Unknown: {cn_str}\n'{control_entry.text[:20]}'").pack(padx=2,pady=2, expand=True, fill="both")
            if preview_widget:
                if widget_class == tkinter.Listbox: preview_widget.place(x=control_entry.x, y=control_entry.y, width=control_entry.width, height=control_entry.height)
                else: preview_widget.place(x=control_entry.x, y=control_entry.y)
                preview_widget.bind("<Button-1>", lambda e, widget=preview_widget, ctrl=control_entry: self.on_control_drag_start(e, widget, ctrl))
                preview_widget.bind("<B1-Motion>", lambda e, widget=preview_widget, ctrl=control_entry: self.on_control_drag(e, widget, ctrl))
                preview_widget.bind("<ButtonRelease-1>", lambda e, widget=preview_widget, ctrl=control_entry: self.on_control_drag_release(e, widget, ctrl))
                self.preview_widgets[control_entry] = preview_widget
        if self.selected_control_entry: self.on_control_selected_on_preview(self.selected_control_entry)
        else: self.on_control_selected_on_preview(None)

    def on_control_drag_start(self, event, widget: Union[customtkinter.CTkBaseClass, tkinter.Listbox], control_entry: DialogControlEntry):
        self.on_control_selected_on_preview(control_entry)
        self._drag_data["widget"] = widget
        self._drag_data["control_entry"] = control_entry
        self._drag_data["start_x_widget"] = control_entry.x
        self._drag_data["start_y_widget"] = control_entry.y
        self._drag_data["start_x_event_root"] = event.x_root
        self._drag_data["start_y_event_root"] = event.y_root

    def on_control_drag(self, event, widget: Union[customtkinter.CTkBaseClass, tkinter.Listbox], control_entry: DialogControlEntry):
        if self._drag_data["widget"] is not widget: return
        delta_x = event.x_root - self._drag_data["start_x_event_root"]
        delta_y = event.y_root - self._drag_data["start_y_event_root"]
        new_x = self._drag_data["start_x_widget"] + delta_x
        new_y = self._drag_data["start_y_widget"] + delta_y
        new_x = max(0, new_x); new_y = max(0, new_y)
        control_entry.x = new_x; control_entry.y = new_y
        widget.place(x=new_x, y=new_y)
        if self.selected_control_entry == control_entry:
            if 'x' in self.prop_widgets_map: self.prop_widgets_map['x'].delete(0, tkinter.END); self.prop_widgets_map['x'].insert(0, str(new_x))
            if 'y' in self.prop_widgets_map: self.prop_widgets_map['y'].delete(0, tkinter.END); self.prop_widgets_map['y'].insert(0, str(new_y))
        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)

    def on_control_drag_release(self, event, widget: Union[customtkinter.CTkBaseClass, tkinter.Listbox], control_entry: DialogControlEntry):
        if self._drag_data["widget"] is widget:
            self._drag_data["widget"] = None
            self._drag_data["control_entry"] = None
            if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
            if self.selected_control_entry == control_entry: self.display_control_properties(control_entry)

    def on_resize_drag_start(self, event):
        if not self.selected_control_entry or not self.resize_handle_widget: return
        selected_widget = event.widget.master
        self._resize_drag_data["widget"] = selected_widget
        self._resize_drag_data["control_entry"] = self.selected_control_entry
        self._resize_drag_data["start_x_event_root"] = event.x_root
        self._resize_drag_data["start_y_event_root"] = event.y_root
        self._resize_drag_data["start_width"] = selected_widget.winfo_width()
        self._resize_drag_data["start_height"] = selected_widget.winfo_height()
        event.widget.configure(cursor="sizing")

    def on_resize_drag(self, event):
        if not self._resize_drag_data.get("widget") or not self._resize_drag_data.get("control_entry"): return
        widget = self._resize_drag_data["widget"]
        control_entry = self._resize_drag_data["control_entry"]
        delta_x = event.x_root - self._resize_drag_data["start_x_event_root"]
        delta_y = event.y_root - self._resize_drag_data["start_y_event_root"]
        new_width = max(10, self._resize_drag_data["start_width"] + delta_x)
        new_height = max(10, self._resize_drag_data["start_height"] + delta_y)
        control_entry.width = new_width
        control_entry.height = new_height
        widget.configure(width=new_width, height=new_height)
        if 'width' in self.prop_widgets_map:
            self.prop_widgets_map['width'].delete(0, tkinter.END); self.prop_widgets_map['width'].insert(0, str(new_width))
        if 'height' in self.prop_widgets_map:
            self.prop_widgets_map['height'].delete(0, tkinter.END); self.prop_widgets_map['height'].insert(0, str(new_height))
        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)

    def on_resize_drag_release(self, event):
        if self.resize_handle_widget and event.widget == self.resize_handle_widget : event.widget.configure(cursor="sizing")
        self._resize_drag_data["widget"] = None
        self._resize_drag_data["control_entry"] = None
        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
        if self.selected_control_entry: self.display_control_properties(self.selected_control_entry)

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
            entry_val = getattr(target_obj, attr_name, None)
            if entry_val is None and data_type not in ["id_str_or_int_optional", str]: entry_val = 0 if data_type in [int, "hex"] else ""
            if data_type == bool:
                widget = customtkinter.CTkCheckBox(self.props_frame, text="")
                if entry_val: widget.select()
            else:
                widget = customtkinter.CTkEntry(self.props_frame)
                if data_type == "hex": widget.insert(0, f"0x{entry_val:X}" if isinstance(entry_val, int) else str(entry_val or "0"))
                elif data_type == "id_str_or_int" and isinstance(target_obj, DialogControlEntry) : widget.insert(0, target_obj.get_id_display())
                elif data_type == "id_str_or_int_optional" :
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
        if isinstance(class_name_val, int): class_str_lookup = ATOM_TO_CLASSNAME_MAP.get(class_name_val, "").upper()
        elif isinstance(class_name_val, str): class_str_lookup = class_name_val.upper()
        if class_str_lookup in STYLE_TO_STR_MAP_BY_CLASS: return STYLE_TO_STR_MAP_BY_CLASS[class_str_lookup]
        for wc_const_val_str in KNOWN_STRING_CLASSES:
            if wc_const_val_str.upper() == class_str_lookup: return STYLE_TO_STR_MAP_BY_CLASS.get(wc_const_val_str, {})
        return {}

    def _display_decoded_styles(self, style_value: int, control_class_val: Optional[Union[str,int]], is_exstyle: bool):
        text_area = customtkinter.CTkTextbox(self.props_frame, height=80, font=("Segoe UI", 11), border_spacing=2)
        text_area.pack(fill="x", padx=5, pady=(0,5)); text_area.configure(state="normal")
        text_area.insert("1.0", "Known flags: "); found_flags = []
        base_style_map = {}
        if not is_exstyle: base_style_map.update(STYLE_TO_STR_MAP_BY_CLASS.get("GENERAL_WS", {}))
        if is_exstyle: style_map_source = EXSTYLE_TO_STR_MAP
        elif self.selected_control_entry is None: style_map_source = {**base_style_map, **STYLE_TO_STR_MAP_BY_CLASS.get("GENERAL_DS", {})}
        elif control_class_val: style_map_source = {**base_style_map, **self._get_style_map_for_control(control_class_val)}
        else: style_map_source = base_style_map
        for flag_val, flag_name in style_map_source.items():
            if style_value & flag_val == flag_val:
                is_sub = False;
                if not is_exstyle and flag_name in ["WS_BORDER", "WS_DLGFRAME"] and (style_value & WS_CAPTION == WS_CAPTION): is_sub = True
                if not is_sub: found_flags.append(flag_name)
        text_area.insert("end", ", ".join(sorted(list(set(found_flags)))) if found_flags else "None recognized")
        text_area.configure(state="disabled")

    def display_dialog_properties(self):
        self.selected_control_entry = None
        self._populate_props_pane(self.dialog_props_copy)
        self.on_control_selected_on_preview(None)

    def display_control_properties(self, control_entry: DialogControlEntry):
        self._populate_props_pane(control_entry)

    def on_control_selected_on_preview(self, control_entry: Optional[DialogControlEntry]):
        self.selected_control_entry = control_entry
        for ctrl, widget_preview in self.preview_widgets.items():
            is_selected = (ctrl == control_entry)
            border_color = "cyan" if is_selected else None
            border_width = 2 if is_selected else 0
            if isinstance(widget_preview, tkinter.Listbox):
                 widget_preview.configure(borderwidth=border_width, relief=tkinter.SOLID if is_selected else tkinter.FLAT)
                 if is_selected: widget_preview.configure(highlightbackground=border_color, highlightcolor=border_color, highlightthickness=1)
                 else: widget_preview.configure(highlightthickness=0)
            elif isinstance(widget_preview, customtkinter.CTkFrame) and not isinstance(widget_preview, customtkinter.CTkButton):
                widget_preview.configure(border_width=border_width if is_selected else 1, border_color=border_color if is_selected else "gray40")
            elif isinstance(widget_preview, customtkinter.CTkBaseClass):
                try: widget_preview.configure(border_width=border_width, border_color=border_color)
                except tkinter.TclError: pass
        if self.resize_handle_widget:
            self.resize_handle_widget.destroy()
            self.resize_handle_widget = None
        if control_entry:
            self._populate_props_pane(control_entry)
            selected_widget = self.preview_widgets.get(control_entry)
            if selected_widget and isinstance(selected_widget, customtkinter.CTkBaseClass):
                handle_size = 8
                self.resize_handle_widget = customtkinter.CTkFrame(
                    selected_widget, width=handle_size, height=handle_size,
                    fg_color="cyan", cursor="sizing" )
                self.resize_handle_widget.place(relx=1.0, rely=1.0, anchor="se")
                self.resize_handle_widget.bind("<Button-1>", self.on_resize_drag_start)
                self.resize_handle_widget.bind("<B1-Motion>", self.on_resize_drag)
                self.resize_handle_widget.bind("<ButtonRelease-1>", self.on_resize_drag_release)
        else:
            self._populate_props_pane(self.dialog_props_copy)

    def apply_properties_to_selection(self):
        target_obj = self.selected_control_entry if self.selected_control_entry else self.dialog_props_copy
        if not target_obj: return; changed = False
        try:
            for attr_name, entry_widget in self.prop_widgets_map.items():
                if isinstance(entry_widget, customtkinter.CTkCheckBox): new_val_typed = bool(entry_widget.get())
                else: new_val_str = entry_widget.get()
                current_val = getattr(target_obj, attr_name, None)
                expected_type = type(current_val) if current_val is not None else str
                if attr_name in ["style", "ex_style", "help_id", "font_weight", "font_charset"] or \
                   (isinstance(target_obj, DialogControlEntry) and attr_name == "id_val" and \
                    (new_val_str.isdigit() or new_val_str.lower().startswith("0x"))): expected_type = int
                elif attr_name == "font_italic": expected_type = bool
                elif current_val is None and isinstance(new_val_str, str): expected_type = str
                elif isinstance(current_val, (int,str)) and attr_name in ["menu_name", "class_name", "id_val"]: expected_type = "id_str_or_int"

                if expected_type == int: new_val_typed = int(str(new_val_str), 0) if str(new_val_str) else 0
                elif expected_type == bool: new_val_typed = bool(int(new_val_str)) if str(new_val_str).isdigit() else str(new_val_str).lower() in ['true', '1', 'yes']
                elif expected_type == str: new_val_typed = str(new_val_str)
                elif expected_type == "id_str_or_int":
                    if new_val_str.isdigit() or new_val_str.lower().startswith("0x"): new_val_typed = int(new_val_str,0)
                    else: new_val_typed = new_val_str
                else: new_val_typed = new_val_str

                if attr_name == "id_val" and isinstance(target_obj, DialogControlEntry):
                    if isinstance(new_val_typed, int): target_obj.symbolic_id_name = None
                    elif isinstance(new_val_typed, str) and not (new_val_typed.isdigit() or new_val_typed.lower().startswith("0x")):
                        target_obj.symbolic_id_name = new_val_typed

                if attr_name == "font_italic":
                    if bool(current_val) != new_val_typed: setattr(target_obj, attr_name, new_val_typed); changed = True
                elif str(current_val) != str(new_val_typed): setattr(target_obj, attr_name, new_val_typed); changed = True

            if isinstance(target_obj, DialogProperties):
                for sym_attr, main_attr in [("symbolic_menu_name", "menu_name"), ("symbolic_class_name", "class_name")]:
                    main_val = getattr(target_obj, main_attr)
                    sym_val_widget = self.prop_widgets_map.get(main_attr)
                    if sym_val_widget and not isinstance(sym_val_widget, customtkinter.CTkCheckBox):
                        sym_text_val = sym_val_widget.get()
                        if isinstance(main_val, int):
                             if getattr(target_obj, sym_attr) is not None: setattr(target_obj, sym_attr, None); changed = True
                        else:
                            if getattr(target_obj, sym_attr) != sym_text_val: setattr(target_obj, sym_attr, sym_text_val if sym_text_val else None); changed = True

            if changed:
                if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
                if self.app_callbacks.get('show_status_callback'): self.app_callbacks['show_status_callback']("Properties updated locally.", 3000)
                self.render_dialog_preview()
            else:
                if self.app_callbacks.get('show_status_callback'): self.app_callbacks['show_status_callback']("No changes detected.", 2000)
        except ValueError as e: messagebox.showerror("Input Error", f"Invalid value for a numeric/hex field: {e}", parent=self)
        except Exception as e: messagebox.showerror("Error", f"Could not apply properties: {e}", parent=self)

    def on_add_control(self):
        control_types = {
            "Button (Push)": ("BUTTON", "Button", BS_PUSHBUTTON | WS_VISIBLE | WS_CHILD | WS_TABSTOP, 50, 14),
            "Edit Control": ("EDIT", "", ES_LEFT | WS_BORDER | WS_VISIBLE | WS_CHILD | WS_TABSTOP, 100, 14),
            "Static Text": ("STATIC", "Static Text", WS_VISIBLE | WS_CHILD | WS_GROUP, 100, 14),
            "List Box": ("LISTBOX", "", LBS_STANDARD | WS_VISIBLE | WS_CHILD | WS_TABSTOP, 100, 50),
            "Combo Box": ("COMBOBOX", "", CBS_DROPDOWNLIST | WS_VISIBLE | WS_CHILD | WS_TABSTOP | WS_VSCROLL, 100, 14),
            "Group Box": ("BUTTON", "Group", BS_GROUPBOX | WS_VISIBLE | WS_CHILD, 100, 50),
            "Scrollbar": ("SCROLLBAR", "", SBS_HORZ | WS_VISIBLE | WS_CHILD, 100, 10),
            "SysListView32": (WC_LISTVIEW, "ListView", WS_VISIBLE | WS_CHILD | WS_BORDER | LVS_REPORT, 150, 80),
            "SysTreeView32": (WC_TREEVIEW, "TreeView", WS_VISIBLE | WS_CHILD | WS_BORDER | TVS_HASLINES | TVS_LINESATROOT | TVS_HASBUTTONS, 150, 80),
        }
        choices = list(control_types.keys())
        choice_str = simpledialog.askstring("Add Control", "Choose control type:\n\n" + "\n".join(choices), parent=self)
        if choice_str and choice_str in control_types:
            class_name_val, def_text, def_style, def_w, def_h = control_types[choice_str]
            new_id = max([ctrl.id_val for ctrl in self.controls_copy if isinstance(ctrl.id_val, int)], default=1000) + 1
            base_sym_name = class_name_val if isinstance(class_name_val, str) else ATOM_TO_CLASSNAME_MAP.get(class_name_val, "CONTROL")
            sym_id_name = f"IDC_{base_sym_name.upper()}{new_id}"
            new_control = DialogControlEntry(class_name=class_name_val, text=def_text, id_val=new_id, symbolic_id_name=sym_id_name,
                                            x=10, y=10, width=def_w, height=def_h, style=def_style )
            self.controls_copy.append(new_control)
            self.render_dialog_preview()
            if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
            self.on_control_selected_on_preview(new_control)
        elif choice_str: messagebox.showerror("Invalid Type", f"Control type '{choice_str}' is not recognized.", parent=self)

    def on_delete_control(self):
        if self.selected_control_entry:
            if messagebox.askyesno("Delete Control", f"Delete control '{self.selected_control_entry.text}' ({self.selected_control_entry.get_id_display()})?", parent=self):
                if self.resize_handle_widget and self.resize_handle_widget.master == self.preview_widgets.get(self.selected_control_entry):
                    self.resize_handle_widget.destroy()
                    self.resize_handle_widget = None
                self.controls_copy.remove(self.selected_control_entry)
                self.selected_control_entry = None
                self.render_dialog_preview()
                if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
        else: messagebox.showinfo("Delete Control", "No control selected to delete.", parent=self)

    def apply_all_changes_to_resource(self):
        if self.prop_widgets_map : self.apply_properties_to_selection()
        self.dialog_resource.properties = copy.deepcopy(self.dialog_props_copy)
        self.dialog_resource.controls = copy.deepcopy(self.controls_copy)
        self.dialog_resource.dirty = True
        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
        messagebox.showinfo("Changes Applied", "All dialog changes applied to in-memory resource. Save file to persist.", parent=self)

if __name__ == '__main__':
    class DummyApp:
        def __init__(self):
            self.root = customtkinter.CTk(); self.root.title("Dialog Editor Test"); self.root.geometry("1000x700")
            customtkinter.set_appearance_mode("dark"); customtkinter.set_default_color_theme("blue")
            props = DialogProperties(caption="Test Dialog", width=220, height=180, style=WS_CAPTION | WS_VISIBLE)
            controls = [
                DialogControlEntry(class_name="BUTTON", text="OK", id_val=1, x=10, y=10, width=50, height=14, style=BS_PUSHBUTTON|WS_TABSTOP|WS_VISIBLE|WS_CHILD),
                DialogControlEntry(class_name="EDIT", text="Some text", id_val=101, x=10, y=30, width=100, height=14, style=ES_LEFT|WS_BORDER|WS_TABSTOP|WS_VISIBLE|WS_CHILD),
                DialogControlEntry(class_name=STATIC_ATOM, text="A Static Label", id_val=102, x=10, y=55, width=100, height=14, style=WS_CHILD|WS_VISIBLE),
                DialogControlEntry(class_name=LISTBOX_ATOM, text="", id_val=103, x=10, y=75, width=100, height=40, style=LBS_STANDARD|WS_CHILD|WS_VISIBLE),
            ]
            self.dialog_res = DialogResource(properties=props, controls=controls)
            app_callbacks = {
                'set_dirty_callback': lambda dirty: print(f"Set dirty: {dirty}"),
                'show_status_callback': lambda msg, dur, err=False: print(f"Status ({'Err' if err else 'Info'}, {dur}ms): {msg}")
            }
            self.editor_frame = DialogEditorFrame(self.root, self.dialog_res, app_callbacks)
            self.editor_frame.pack(fill="both", expand=True, padx=10, pady=10)
            customtkinter.CTkButton(self.root, text="Simulate Update", command=self.simulate_update).pack(pady=5)
        def simulate_update(self):
            new_ctrl = DialogControlEntry(class_name="STATIC", text="Added Label", id_val=1002, x=70,y=5,width=70,height=14, style=WS_CHILD|WS_VISIBLE)
            self.dialog_res.controls.append(new_ctrl)
            self.editor_frame.dialog_props_copy = copy.deepcopy(self.dialog_res.properties)
            self.editor_frame.controls_copy = copy.deepcopy(self.dialog_res.controls)
            self.editor_frame.render_dialog_preview()
            self.editor_frame.display_dialog_properties()
            print("Simulated resource update and re-rendered preview.")
        def run(self): self.root.mainloop()
    app = DummyApp(); app.run()
    pass

[end of python_resource_editor/src/gui/dialog_editor_frame.py]
