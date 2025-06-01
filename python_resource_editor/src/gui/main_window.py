import customtkinter
import tkinter # For tkinter.Menu, as customtkinter doesn't wrap it directly for menubars.
import tkinter.ttk as ttk
from tkinter import filedialog as tkfiledialog
from tkinter import messagebox as tkmessagebox
from tkinter import simpledialog # For simple input dialogs
import os
import tempfile
import io
import copy # For deepcopy
import shutil # For file copy on export
from PIL import Image, ImageTk, UnidentifiedImageError
from typing import List, Dict, Callable, Optional, Union, Tuple
from ..core.pe_parser import extract_resources_from_pe
from ..core.rc_parser import RCParser
from ..core.res_parser import parse_res_file
from ..core.resource_base import Resource, ResourceIdentifier, FileResource, TextBlockResource
from ..core.resource_types import StringTableResource, RCDataResource, MenuResource, DialogResource, VersionInfoResource, AcceleratorResource
from ..utils.external_tools import run_windres_compile, WindresError, get_tool_path # Import get_tool_path
from ..utils import image_utils
from ..core.resource_base import (
    RT_CURSOR, RT_BITMAP, RT_ICON, RT_MENU, RT_DIALOG, RT_STRING, RT_FONTDIR,
    RT_FONT, RT_ACCELERATOR, RT_RCDATA, RT_MESSAGETABLE, RT_GROUP_CURSOR,
    RT_GROUP_ICON, RT_VERSION, RT_DLGINCLUDE, RT_PLUGPLAY, RT_VXD,
    RT_ANICURSOR, RT_ANIICON, RT_HTML, RT_MANIFEST, LANG_NEUTRAL
)
from .add_resource_dialog import AddResourceDialog
from .import_resource_dialog import ImportResourceDialog # Import the new dialog
from .string_table_editor_frame import StringTableEditorFrame
from .menu_editor_frame import MenuEditorFrame
from .dialog_editor_frame import DialogEditorFrame
from .version_info_editor_frame import VersionInfoEditorFrame
from .accelerator_editor_frame import AcceleratorEditorFrame


class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.title("Python Resource Editor")
        self.geometry("1100x750")

        self.resources: list[Resource] = []
        self.current_filepath: str | None = None
        self.current_file_type: str | None = None # Will be ".rc", ".res", or "PE"
        # self.mcpp_path: str = "mcpp.exe" # Old
        # self.windres_path: str = "windres.exe" # Old
        self.include_paths: list[str] = []
        self.treeview: ttk.Treeview | None = None
        self.tree_item_to_resource = {}

        self.app_dirty_flag: bool = False
        self.current_editor_widget: customtkinter.CTkBaseClass | None = None
        self.current_selected_resource_item_id: str | None = None
        self.save_text_changes_button: customtkinter.CTkButton | None = None

        # Resolve tool paths
        self.mcpp_path: str = get_tool_path("mcpp.exe")
        self.windres_path: str = get_tool_path("windres.exe")

        if not os.path.exists(self.mcpp_path) or not os.access(self.mcpp_path, os.X_OK):
            print(f"FATAL: mcpp.exe not found or not executable at '{self.mcpp_path}'. RC file operations will fail.")
            # Optionally, disable RC functionality or show error dialog here.
            # For now, a print warning. The actual MCPPError will be raised on use.
        if not os.path.exists(self.windres_path) or not os.access(self.windres_path, os.X_OK):
            print(f"FATAL: windres.exe not found or not executable at '{self.windres_path}'. Saving to .RES will fail.")
            # Optionally, disable RES saving. WindresError will be raised on use.

        self.filemenu_reference: tkinter.Menu | None = None
        self.editmenu_reference: tkinter.Menu | None = None


        self.RT_MAP = {
            RT_CURSOR: "RT_CURSOR", RT_BITMAP: "RT_BITMAP", RT_ICON: "RT_ICON",
            RT_MENU: "RT_MENU", RT_DIALOG: "RT_DIALOG", RT_STRING: "RT_STRING",
            RT_FONTDIR: "RT_FONTDIR", RT_FONT: "RT_FONT", RT_ACCELERATOR: "RT_ACCELERATOR",
            RT_RCDATA: "RT_RCDATA", RT_MESSAGETABLE: "RT_MESSAGETABLE",
            RT_GROUP_CURSOR: "RT_GROUP_CURSOR", RT_GROUP_ICON: "RT_GROUP_ICON",
            RT_VERSION: "RT_VERSION", RT_DLGINCLUDE: "RT_DLGINCLUDE",
            RT_PLUGPLAY: "RT_PLUGPLAY", RT_VXD: "RT_VXD",
            RT_ANICURSOR: "RT_ANICURSOR", RT_ANIICON: "RT_ANIICON",
            RT_HTML: "RT_HTML", RT_MANIFEST: "RT_MANIFEST",
            "TOOLBAR": "TOOLBAR", "TYPELIB": "TYPELIB", "DLGINIT": "DLGINIT",
            "VERSIONINFO": "VERSIONINFO", "ACCELERATORS": "ACCELERATORS"
        }
        self.RT_NAME_TO_ID_MAP = {v: k for k, v in self.RT_MAP.items() if isinstance(k, int)}
        for str_type in ["TOOLBAR", "TYPELIB", "DLGINIT", "DIALOGEX", "VERSIONINFO", "ACCELERATORS"]:
            if str_type == "DIALOGEX": self.RT_NAME_TO_ID_MAP[str_type] = RT_DIALOG
            elif str_type == "VERSIONINFO": self.RT_NAME_TO_ID_MAP[str_type] = RT_VERSION
            elif str_type == "ACCELERATORS": self.RT_NAME_TO_ID_MAP[str_type] = RT_ACCELERATOR
            elif str_type in self.RT_MAP: self.RT_NAME_TO_ID_MAP[str_type] = str_type


        self.create_menu_bar()
        self.create_main_layout()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def get_type_display_name(self, type_id_or_str):
        if isinstance(type_id_or_str, int):
            return self.RT_MAP.get(type_id_or_str, str(type_id_or_str))
        return str(type_id_or_str)

    def _clear_editor_frame(self):
        for widget in self.editor_frame.winfo_children():
            widget.destroy()
        self.current_editor_widget = None
        if self.save_text_changes_button:
            self.save_text_changes_button.destroy()
            self.save_text_changes_button = None

    def set_app_dirty(self, dirty: bool):
        if dirty == self.app_dirty_flag: return
        self.app_dirty_flag = dirty
        title_suffix = "*" if dirty else ""
        base_title = "Python Resource Editor"
        if self.current_filepath:
            base_title += f" - {os.path.basename(self.current_filepath)}"
        self.title(f"{base_title}{title_suffix}")


    def create_main_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        self.tree_frame = customtkinter.CTkFrame(self, width=350)
        self.tree_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.tree_frame.grid_propagate(False)
        self.tree_frame.grid_rowconfigure(0, weight=1) # Make treeview expand

        self.treeview = ttk.Treeview(self.tree_frame, columns=("Name", "Type", "Language"), show="tree headings")
        self.treeview.heading("#0", text="Resource Path")
        self.treeview.heading("Name", text="Name/ID")
        self.treeview.heading("Type", text="Type")
        self.treeview.heading("Language", text="Language")
        self.treeview.column("#0", width=180, stretch=True)
        self.treeview.column("Name", width=120, anchor="w", stretch=True)
        self.treeview.column("Type", width=100, anchor="w", stretch=False)
        self.treeview.column("Language", width=80, anchor="center", stretch=False)
        self.treeview.pack(expand=True, fill="both", padx=2, pady=2)
        self.treeview.bind("<<TreeviewSelect>>", self.on_treeview_select)

        self.editor_frame = customtkinter.CTkFrame(self)
        self.editor_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self.editor_frame.grid_propagate(False)
        # editor_label = customtkinter.CTkLabel(self.editor_frame, text="Select a resource to view/edit.")
        # editor_label.pack(padx=10, pady=10, anchor="center") # Initial label removed, handled by _clear_editor_frame

        # Status Bar
        self.grid_rowconfigure(1, weight=0) # Status bar row
        self.statusbar_label = customtkinter.CTkLabel(self, text="Ready", anchor="w")
        self.statusbar_label.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=(2, 5))
        self._status_clear_job = None # For scheduling status clear


    def create_menu_bar(self):
        self.menubar = tkinter.Menu(self)

        self.filemenu_reference = tkinter.Menu(self.menubar, tearoff=0)
        self.filemenu_reference.add_command(label="Open", command=self.on_open_file)
        self.filemenu_reference.add_command(label="Save", command=self.on_save_file, state="disabled")
        self.filemenu_reference.add_command(label="Save As...", command=self.on_save_as_file, state="disabled")
        self.filemenu_reference.add_separator()
        self.filemenu_reference.add_command(label="Import Resource from File...", command=self.on_import_resource_from_file, state="normal") # Or "disabled" until file open
        self.filemenu_reference.add_separator()
        self.filemenu_reference.add_command(label="Exit", command=self.on_closing)
        self.menubar.add_cascade(label="File", menu=self.filemenu_reference)

        self.editmenu_reference = tkinter.Menu(self.menubar, tearoff=0)
        self.editmenu_reference.add_command(label="Add Resource...", command=self.on_add_resource, state="disabled")
        self.editmenu_reference.add_command(label="Delete Resource", command=self.on_delete_resource, state="disabled")
        self.editmenu_reference.add_separator()
        self.editmenu_reference.add_command(label="Change Language...", command=self.on_change_resource_language, state="disabled")
        self.editmenu_reference.add_command(label="Clone to New Language...", command=self.on_clone_to_new_language, state="disabled")
        self.editmenu_reference.add_separator()
        self.editmenu_reference.add_command(label="Export Selected Resource As...", command=self.on_export_selected_resource, state="disabled")
        self.menubar.add_cascade(label="Edit", menu=self.editmenu_reference)

        viewmenu = tkinter.Menu(self.menubar, tearoff=0)
        viewmenu.add_command(label="Toggle Light/Dark", command=self.toggle_appearance_mode)
        self.menubar.add_cascade(label="View", menu=viewmenu)
        helpmenu = tkinter.Menu(self.menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self.on_about)
        self.menubar.add_cascade(label="Help", menu=helpmenu)
        self.config(menu=self.menubar)

    def show_error_message(self, title: str, message: str):
        tkmessagebox.showerror(title, message, parent=self)

    def show_info_message(self, title: str, message: str):
        tkmessagebox.showinfo(title, message, parent=self)

    def on_open_file(self):
        # ... (same as before, ensure menu items are correctly enabled/disabled) ...
        if self.app_dirty_flag:
            if not self.prompt_save_if_dirty(): return
        filepath = tkfiledialog.askopenfilename(title="Open Resource File", filetypes=(("All Resource Files", "*.exe *.dll *.res *.rc *.ocx *.sys *.scr *.mui"),("Executable Files", "*.exe *.dll *.ocx *.sys *.scr *.mui"),("Resource Scripts", "*.rc"), ("Compiled Resources", "*.res"), ("All files", "*.*")))
        if not filepath: return

        self.current_filepath = filepath
        if self.treeview: self.treeview.delete(*self.treeview.get_children())
        self.resources = []; self.tree_item_to_resource.clear(); self.set_app_dirty(False); self._clear_editor_frame(); self.current_selected_resource_item_id = None

        _, ext_with_dot = os.path.splitext(filepath)
        ext = ext_with_dot.lower()

        try:
            self.title(f"Python Resource Editor - {os.path.basename(filepath)}")
            if ext == ".rc":
                self.current_file_type = ".rc" # Explicitly set
                rc_dir = os.path.dirname(filepath); current_includes = (self.include_paths or []) + [rc_dir]
                parser = RCParser(mcpp_path=self.mcpp_path, include_paths=current_includes)
                parsed_rc_resources = parser.parse_rc_file(filepath)
                for res in parsed_rc_resources:
                    if isinstance(res, TextBlockResource):
                        if res.resource_type_name == "STRINGTABLE": self.resources.append(StringTableResource.parse_from_text_block(res))
                        elif res.resource_type_name in ["MENU", "MENUEX"]: self.resources.append(MenuResource.parse_from_text_block(res))
                        elif res.resource_type_name in ["DIALOG", "DIALOGEX"]: self.resources.append(DialogResource.parse_from_text_block(res))
                        elif res.resource_type_name == "VERSIONINFO": self.resources.append(VersionInfoResource.parse_from_text_block(res))
                        elif res.resource_type_name == "ACCELERATORS": self.resources.append(AcceleratorResource.parse_from_text_block(res))
                        else: self.resources.append(res)
                    else: self.resources.append(res)
            elif ext == ".res":
                self.current_file_type = ".res" # Explicitly set
                binary_resources = parse_res_file(filepath)
                for res in binary_resources:
                    if res.identifier.type_id == RT_STRING: self.resources.append(StringTableResource.parse_from_binary_data(res.data, res.identifier))
                    elif res.identifier.type_id == RT_MENU: self.resources.append(MenuResource.parse_from_binary_data(res.data, res.identifier))
                    elif res.identifier.type_id == RT_DIALOG: self.resources.append(DialogResource.parse_from_binary_data(res.data, res.identifier))
                    elif res.identifier.type_id == RT_VERSION: self.resources.append(VersionInfoResource.parse_from_binary_data(res.data, res.identifier))
                    elif res.identifier.type_id == RT_ACCELERATOR: self.resources.append(AcceleratorResource.parse_from_binary_data(res.data, res.identifier))
                    else: self.resources.append(res)
            elif ext in [".exe", ".dll", ".ocx", ".sys", ".scr", ".cpl", ".ime", ".mui"]:
                self.current_file_type = "PE" # Use generic "PE" type
                pe_resources = extract_resources_from_pe(filepath)
                for res in pe_resources:
                    if res.identifier.type_id == RT_STRING: self.resources.append(StringTableResource.parse_from_binary_data(res.data, res.identifier))
                    elif res.identifier.type_id == RT_MENU: self.resources.append(MenuResource.parse_from_binary_data(res.data, res.identifier))
                    elif res.identifier.type_id == RT_DIALOG: self.resources.append(DialogResource.parse_from_binary_data(res.data, res.identifier))
                    elif res.identifier.type_id == RT_VERSION: self.resources.append(VersionInfoResource.parse_from_binary_data(res.data, res.identifier))
                    elif res.identifier.type_id == RT_ACCELERATOR: self.resources.append(AcceleratorResource.parse_from_binary_data(res.data, res.identifier))
                    else: self.resources.append(res)
            else:
                self.current_file_type = None # Unknown
                self.show_error_message("Unsupported File Type", f"The file type '{ext}' is not currently supported for opening.")
                self.title("Python Resource Editor - Error"); return

            self.populate_treeview()
            if self.filemenu_reference:
                 self.filemenu_reference.entryconfig("Save", state="normal" if self.current_file_type in ['.rc', '.res', 'PE'] else "disabled")
                 self.filemenu_reference.entryconfig("Save As...", state="normal") # Save As is always possible if resources are loaded
                 self.filemenu_reference.entryconfig("Import Resource from File...", state="normal")
            self.show_status(f"Opened: {os.path.basename(self.current_filepath)} ({len(self.resources)} resources found)", 5000)
            if self.editmenu_reference:
                 self.editmenu_reference.entryconfig("Add Resource...", state="normal")
                 # Other edit items depend on selection
                 self.editmenu_reference.entryconfig("Delete Resource", state="disabled")
                 self.editmenu_reference.entryconfig("Change Language...", state="disabled")
                 self.editmenu_reference.entryconfig("Clone to New Language...", state="disabled")
                 self.editmenu_reference.entryconfig("Export Selected Resource As...", state="disabled")
        except Exception as e:
            err_msg = f"Error opening {os.path.basename(filepath)}: {e}"
            self.show_error_message("Parsing Error", f"An error occurred: {e}") # Keep messagebox for critical errors
            self.show_status(err_msg, 7000, is_error=True)
            self.title(f"Python Resource Editor - Error loading {os.path.basename(filepath)}")
            import traceback; traceback.print_exc()


    def populate_treeview(self):
        # ... (same as before) ...
        if not self.treeview: return
        for i in self.treeview.get_children(): self.treeview.delete(i)
        self.tree_item_to_resource.clear()
        grouped_resources = {}
        for res_obj in self.resources:
            type_name = self.get_type_display_name(res_obj.identifier.type_id)
            name_str = str(res_obj.identifier.name_id)
            grouped_resources.setdefault(type_name, {}).setdefault(name_str, []).append(res_obj)
        for type_name, names in sorted(grouped_resources.items()):
            type_node_id = self.treeview.insert("", "end", text=type_name, open=False, values=("", type_name, ""))
            for name_str, res_list_for_langs in sorted(names.items()):
                if len(res_list_for_langs) == 1:
                    res_obj = res_list_for_langs[0]
                    lang_display = str(res_obj.identifier.language_id)
                    item_id_str = f"item_{id(res_obj)}"
                    self.treeview.insert(type_node_id, "end", iid=item_id_str, text=name_str, values=(name_str, "", lang_display))
                    self.tree_item_to_resource[item_id_str] = res_obj
                else:
                    name_node_id_str = f"name_{type_name}_{name_str}"
                    name_node_id = self.treeview.insert(type_node_id, "end", iid=name_node_id_str, text=name_str, values=(name_str, "", "Multiple"), open=False)
                    for res_obj in sorted(res_list_for_langs, key=lambda r: r.identifier.language_id):
                        lang_display = str(res_obj.identifier.language_id)
                        item_id_str = f"item_{id(res_obj)}"
                        self.treeview.insert(name_node_id, "end", iid=item_id_str, text=lang_display, values=(name_str, "", lang_display))
                        self.tree_item_to_resource[item_id_str] = res_obj
        style = ttk.Style()
        try:
            bg_color = self._apply_appearance_mode(customtkinter.ThemeManager.theme["CTkFrame"]["fg_color"])
            text_color = self._apply_appearance_mode(customtkinter.ThemeManager.theme["CTkLabel"]["text_color"])
            style.configure("Treeview", background=bg_color, foreground=text_color, fieldbackground=bg_color)
        except: pass


    def on_treeview_select(self, event=None):
        selected_item_id = self.treeview.focus()
        if not selected_item_id:
            self.current_selected_resource_item_id = None
            if self.editmenu_reference:
                self.editmenu_reference.entryconfig("Delete Resource", state="disabled")
                self.editmenu_reference.entryconfig("Change Language...", state="disabled")
                self.editmenu_reference.entryconfig("Clone to New Language...", state="disabled")
                self.editmenu_reference.entryconfig("Export Selected Resource As...", state="disabled")
            return

        self.current_selected_resource_item_id = selected_item_id
        res_obj = self.tree_item_to_resource.get(selected_item_id)
        self._clear_editor_frame()

        is_actual_resource = res_obj and res_obj in self.resources
        action_state = "normal" if is_actual_resource else "disabled"
        if self.editmenu_reference:
            self.editmenu_reference.entryconfig("Delete Resource", state=action_state)
            self.editmenu_reference.entryconfig("Change Language...", state=action_state)
            self.editmenu_reference.entryconfig("Clone to New Language...", state=action_state)
            self.editmenu_reference.entryconfig("Export Selected Resource As...", state=action_state)


        if res_obj:
            info_text_parts = [f"Type: {self.get_type_display_name(res_obj.identifier.type_id)}", f"Name/ID: {res_obj.identifier.name_id}", f"Language: {res_obj.identifier.language_id} (0x{res_obj.identifier.language_id:04X})", f"Data Class: {type(res_obj).__name__}"]
            is_image_type = res_obj.identifier.type_id in [RT_ICON, RT_BITMAP, RT_GROUP_ICON, RT_GROUP_CURSOR] or (isinstance(res_obj, FileResource) and any(res_obj.filepath.lower().endswith(ext) for ext in ['.ico', '.bmp', '.png', '.jpg', '.jpeg', '.gif']))
            app_callbacks = {'set_dirty_callback': self.set_app_dirty}

            if isinstance(res_obj, StringTableResource):
                editor = StringTableEditorFrame(self.editor_frame, res_obj, app_callbacks)
                editor.pack(expand=True, fill="both"); self.current_editor_widget = editor
            elif isinstance(res_obj, MenuResource):
                editor = MenuEditorFrame(self.editor_frame, res_obj, app_callbacks)
                editor.pack(expand=True, fill="both"); self.current_editor_widget = editor
            elif isinstance(res_obj, DialogResource):
                editor = DialogEditorFrame(self.editor_frame, res_obj, app_callbacks)
                editor.pack(expand=True, fill="both"); self.current_editor_widget = editor
            elif isinstance(res_obj, VersionInfoResource):
                editor = VersionInfoEditorFrame(self.editor_frame, res_obj, app_callbacks)
                editor.pack(expand=True, fill="both"); self.current_editor_widget = editor
            elif isinstance(res_obj, AcceleratorResource):
                editor = AcceleratorEditorFrame(self.editor_frame, res_obj, app_callbacks)
                editor.pack(expand=True, fill="both"); self.current_editor_widget = editor
            elif is_image_type:
                try:
                    img_data = None
                    if isinstance(res_obj, FileResource):
                        if res_obj.data is None:
                            try: base_dir = os.path.dirname(self.current_filepath) if self.current_filepath else ""; res_obj.load_data(base_dir=base_dir)
                            except Exception as load_err: raise UnidentifiedImageError(f"Could not load image file {res_obj.filepath}: {load_err}")
                        img_data = io.BytesIO(res_obj.data)
                    elif res_obj.data: img_data = io.BytesIO(res_obj.data)
                    if img_data:
                        img = Image.open(img_data)
                        if res_obj.identifier.type_id == RT_ICON or (isinstance(res_obj, FileResource) and res_obj.filepath.lower().endswith('.ico')):
                            if hasattr(img, 'ico'): sizes = img.ico.sizes();
                            if sizes: target_size = (32,32); img.size = target_size if target_size in sizes else sizes[-1]
                        max_dim = 256
                        if img.width > max_dim or img.height > max_dim: img.thumbnail((max_dim, max_dim))
                        ctk_image = customtkinter.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
                        image_label = customtkinter.CTkLabel(self.editor_frame, image=ctk_image, text="")
                        image_label.pack(padx=10, pady=10, expand=True, anchor="center"); image_label.image = ctk_image
                        info_text_parts.append(f"Image Size: {img.width}x{img.height}")
                    else: raise UnidentifiedImageError("No image data available")
                except (UnidentifiedImageError, IOError, EOFError, TypeError, ValueError) as img_err:
                    info_text_parts.append(f"Image Preview Error: {img_err}")
                    if res_obj.data: info_text_parts.append(f"\n--- Data Preview (Hex, up to 256 bytes) ---\n{res_obj.data[:256].hex(' ', 16)}")
            elif isinstance(res_obj, TextBlockResource):
                info_text_parts.append(f"Text Length: {len(res_obj.text_content)}")
                self.current_editor_widget = customtkinter.CTkTextbox(self.editor_frame, font=("monospace", 12))
                self.current_editor_widget.pack(expand=True, fill="both", padx=5, pady=(5,0))
                self.current_editor_widget.insert("1.0", res_obj.text_content)
                self.current_editor_widget.configure(state="normal")
                self.current_editor_widget.bind("<KeyRelease>", lambda event: self.on_text_editor_change())
                self.save_text_changes_button = customtkinter.CTkButton(self.editor_frame, text="Save Text Changes", command=self.save_text_resource_changes, state="disabled")
                self.save_text_changes_button.pack(pady=5)
            elif isinstance(res_obj, RCDataResource) and res_obj.data:
                info_text_parts.append(f"Data Length: {len(res_obj.data)}")
                hex_textbox = customtkinter.CTkTextbox(self.editor_frame, wrap="none", font=("monospace", 12))
                hex_textbox.pack(expand=True, fill="both", padx=5, pady=5)
                formatted_hex = []
                for i in range(0, len(res_obj.data), 16):
                    chunk = res_obj.data[i:i+16]; addr = f"{i:08X}: "; hex_bytes = " ".join(f"{b:02X}" for b in chunk); ascii_repr = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
                    formatted_hex.append(f"{addr}{hex_bytes:<48} {ascii_repr}")
                hex_textbox.insert("1.0", "\n".join(formatted_hex)); hex_textbox.configure(state="disabled")
            elif res_obj.data:
                info_text_parts.append(f"Data Length: {len(res_obj.data)}")
                hex_textbox = customtkinter.CTkTextbox(self.editor_frame, wrap="none", font=("monospace", 12))
                hex_textbox.pack(expand=True, fill="both", padx=5, pady=5)
                formatted_hex = []
                for i in range(0, len(res_obj.data), 16):
                    chunk = res_obj.data[i:i+16]; addr = f"{i:08X}: "; hex_bytes = " ".join(f"{b:02X}" for b in chunk); ascii_repr = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
                    formatted_hex.append(f"{addr}{hex_bytes:<48} {ascii_repr}")
                hex_textbox.insert("1.0", "\n".join(formatted_hex)); hex_textbox.configure(state="disabled")

            if not isinstance(res_obj, (StringTableResource, MenuResource, DialogResource, VersionInfoResource, AcceleratorResource, TextBlockResource)) and \
               not (is_image_type and 'ctk_image' in locals()) and \
               not (isinstance(res_obj, RCDataResource) and res_obj.data):
                 info_label = customtkinter.CTkLabel(self.editor_frame, text="\n".join(info_text_parts), justify="left", anchor="nw")
                 info_label.pack(padx=10, pady=10, expand=True, fill="both", anchor="nw")
        else: # Category node
            self.current_selected_resource_item_id = None
            node_text = self.treeview.item(selected_item_id, "text"); node_values = self.treeview.item(selected_item_id, "values")
            info_text = f"Selected Category Node:\n  Display Text: {node_text}\n"
            if node_values: info_text += f"  Name/ID Col: {node_values[0]}\n  Type Col: {node_values[1]}\n  Lang Col: {node_values[2]}\n"
            info_label = customtkinter.CTkLabel(self.editor_frame, text=info_text, justify="left", anchor="nw")
            info_label.pack(padx=10, pady=10, expand=True, fill="both", anchor="nw")

    def on_text_editor_change(self, event=None):
        if self.save_text_changes_button: self.save_text_changes_button.configure(state="normal")

    def save_text_resource_changes(self):
        if not self.current_selected_resource_item_id or not self.current_editor_widget: return
        res_obj = self.tree_item_to_resource.get(self.current_selected_resource_item_id)
        if isinstance(res_obj, TextBlockResource) and isinstance(self.current_editor_widget, customtkinter.CTkTextbox):
            new_text = self.current_editor_widget.get("1.0", "end-1c")
            if new_text != res_obj.text_content:
                res_obj.text_content = new_text; res_obj.data = new_text.encode('utf-8'); res_obj.dirty = True
                self.set_app_dirty(True)
                if self.save_text_changes_button: self.save_text_changes_button.configure(state="disabled")

    def on_add_resource(self):
        # ... (same as before) ...
        rt_display_names = list(self.RT_MAP.keys())
        rt_display_names = [self.get_type_display_name(rt) for rt in rt_display_names if isinstance(rt, int) or rt in ["TOOLBAR", "ACCELERATORS", "VERSIONINFO"]]
        dialog = AddResourceDialog(self, available_types=sorted(list(set(rt_display_names))))
        if dialog.result:
            res_type_str, res_name_or_id_str, res_lang_str, res_filepath = dialog.result
            try:
                parsed_name = int(res_name_or_id_str) if res_name_or_id_str.isdigit() or (res_name_or_id_str.startswith("0x")) else res_name_or_id_str
                parsed_lang = int(res_lang_str)
            except ValueError: self.show_error_message("Invalid Input", "Name/ID or Language ID is not valid."); return
            actual_res_type = self.RT_NAME_TO_ID_MAP.get(res_type_str, res_type_str)
            identifier = ResourceIdentifier(type_id=actual_res_type, name_id=parsed_name, language_id=parsed_lang)
            new_res = None; name_keyword = f'"{parsed_name}"' if isinstance(parsed_name, str) else str(parsed_name)
            rc_type_keyword = res_type_str

            if res_filepath and actual_res_type in [RT_ICON, RT_BITMAP, RT_CURSOR] or (isinstance(actual_res_type, str) and actual_res_type.upper() in ["ICON", "BITMAP", "CURSOR"]):
                new_res = FileResource(identifier, res_filepath, original_rc_statement=f"{name_keyword} {rc_type_keyword} \"{os.path.basename(res_filepath)}\"")
                try: new_res.load_data(base_dir=os.path.dirname(res_filepath))
                except Exception as e: self.show_error_message("File Load Error", f"Could not load data from {res_filepath}: {e}"); new_res.data = b""
            elif actual_res_type == RT_STRING: new_res = StringTableResource(identifier, entries=[StringTableEntry(id_val=0, value_str="New String", name_val="IDS_NEW_STRING")])
            elif actual_res_type == RT_MENU: new_res = MenuResource(identifier, items=[MenuItemEntry(text="File", item_type="POPUP", children=[MenuItemEntry(text="Exit", id_val=1000)])], menu_name_rc=str(parsed_name))
            elif actual_res_type == RT_DIALOG:
                props = DialogProperties(name=parsed_name, symbolic_name=str(parsed_name) if isinstance(parsed_name, str) else None, caption="New Dialog", is_ex= (rc_type_keyword=="DIALOGEX"))
                new_res = DialogResource(identifier, properties=props, controls=[DialogControlEntry("LTEXT","Sample Text", -1, 10,10,50,10)])
            elif actual_res_type == RT_VERSION: new_res = VersionInfoResource(identifier)
            elif actual_res_type == RT_ACCELERATOR: new_res = AcceleratorResource(identifier, entries=[AcceleratorEntry("VK_F1", 1000, "ID_ACCEL_NEW", ["VIRTKEY"])], table_name_rc=str(parsed_name))
            else:
                text_content = f"// Placeholder for {res_type_str} Name: {parsed_name} Lang: {parsed_lang}\n";
                if actual_res_type == RT_RCDATA or rc_type_keyword == "RCDATA": text_content = f"{name_keyword} RCDATA\nBEGIN\n    \"Your raw data here\"\nEND"
                new_res = TextBlockResource(identifier, text_content, resource_type_name=rc_type_keyword)
            if new_res:
                self.resources.append(new_res); new_res.dirty = True; self.populate_treeview(); self.set_app_dirty(True)
                for item_id, res_in_map in self.tree_item_to_resource.items():
                    if res_in_map == new_res: self.treeview.focus(item_id); self.treeview.selection_set(item_id); break
                self.show_status(f"Added resource: {res_type_str} - {parsed_name}", 4000)


    def on_delete_resource(self):
        # ... (same as before) ...
        if not self.current_selected_resource_item_id : return
        res_obj = self.tree_item_to_resource.get(self.current_selected_resource_item_id)
        if res_obj:
            res_id_str = f"Type: {self.get_type_display_name(res_obj.identifier.type_id)}, Name: {res_obj.identifier.name_id}, Lang: {res_obj.identifier.language_id}"
            if tkmessagebox.askyesno("Delete Resource", f"Are you sure you want to delete this resource?\n\n{res_id_str}", parent=self):
                try:
                    self.resources.remove(res_obj); self.populate_treeview(); self.set_app_dirty(True); self._clear_editor_frame(); self.current_selected_resource_item_id = None
                    if self.editmenu_reference: self.editmenu_reference.entryconfig("Delete Resource", state="disabled")
                    self.show_status(f"Resource '{res_obj.identifier.name_id_to_str()}' deleted.", 3000)
                except ValueError:
                    self.show_error_message("Delete Error", "Could not find resource in list.")
                    self.show_status("Error deleting resource.", 5000, is_error=True)
        else:
            self.show_error_message("Delete Error", "No valid resource selected.")
            self.show_status("Delete Error: No valid resource selected.", 5000, is_error=True)

    def on_change_resource_language(self):
        # ... (same as before) ...
        if not self.current_selected_resource_item_id: return
        res_obj = self.tree_item_to_resource.get(self.current_selected_resource_item_id)
        if not (res_obj and res_obj in self.resources): self.show_error_message("Error", "No valid resource selected."); return
        new_lang_str = simpledialog.askstring("Change Language", f"New Language ID for '{res_obj.identifier.name_id}' (Type: {self.get_type_display_name(res_obj.identifier.type_id)}):\n(Current: {res_obj.identifier.language_id})", parent=self)
        if new_lang_str is None: return
        try: new_lang_id = int(new_lang_str); assert 0 <= new_lang_id <= 0xFFFF
        except: self.show_error_message("Invalid Input", "Language ID must be a number (0-65535)."); return
        for r in self.resources:
            if r != res_obj and r.identifier.type_id == res_obj.identifier.type_id and r.identifier.name_id == res_obj.identifier.name_id and r.identifier.language_id == new_lang_id:
                self.show_error_message("Conflict", "Resource with this Type, Name, and new Language ID already exists.");
                self.show_status("Error: Language ID conflict.", 5000, is_error=True)
                return
        res_obj.identifier.language_id = new_lang_id; res_obj.dirty = True; self.set_app_dirty(True); self.populate_treeview()
        self.show_status(f"Language changed for '{res_obj.identifier.name_id_to_str()}'.", 3000)


    def on_clone_to_new_language(self):
        # ... (same as before) ...
        if not self.current_selected_resource_item_id: return
        res_obj = self.tree_item_to_resource.get(self.current_selected_resource_item_id)
        if not (res_obj and res_obj in self.resources): self.show_error_message("Error", "No valid resource selected for cloning."); return
        new_lang_str = simpledialog.askstring("Clone to New Language", f"New Language ID for clone of '{res_obj.identifier.name_id}' (Type: {self.get_type_display_name(res_obj.identifier.type_id)}):", parent=self)
        if new_lang_str is None: return
        try: new_lang_id = int(new_lang_str); assert 0 <= new_lang_id <= 0xFFFF
        except: self.show_error_message("Invalid Input", "Language ID must be a number (0-65535)."); return
        if new_lang_id == res_obj.identifier.language_id: self.show_error_message("Error", "New language is same as current."); return
        for r in self.resources:
            if r.identifier.type_id == res_obj.identifier.type_id and r.identifier.name_id == res_obj.identifier.name_id and r.identifier.language_id == new_lang_id:
                self.show_error_message("Conflict", "Resource with this Type, Name, and target Language ID already exists.");
                self.show_status("Error: Cloned language ID conflict.", 5000, is_error=True)
                return
        cloned_res = copy.deepcopy(res_obj); cloned_res.identifier.language_id = new_lang_id; cloned_res.dirty = True
        self.resources.append(cloned_res); self.set_app_dirty(True); self.populate_treeview()
        self.show_status(f"Resource '{res_obj.identifier.name_id_to_str()}' cloned to lang {new_lang_id}.", 4000)

    def on_import_resource_from_file(self): # Already has show_info_message, status update can be added
        rt_display_names = [self.get_type_display_name(rt) for rt in self.RT_MAP.keys() if isinstance(rt, int) or rt in ["TOOLBAR", "ACCELERATORS", "VERSIONINFO", "HTML", "MANIFEST", "RCDATA"]]
        dialog = ImportResourceDialog(self, available_types=sorted(list(set(rt_display_names))))
        if dialog.result:
            filepath, res_type_str, res_name_or_id_str, res_lang_str = dialog.result
            try:
                parsed_name = int(res_name_or_id_str) if res_name_or_id_str.isdigit() or res_name_or_id_str.startswith("0x") else res_name_or_id_str
                parsed_lang = int(res_lang_str)
            except ValueError:
                self.show_error_message("Invalid Input", "Name/ID or Language ID is not valid.")
                self.show_status("Import Error: Invalid Name/ID or Language.", 5000, is_error=True)
                return

            actual_res_type = self.RT_NAME_TO_ID_MAP.get(res_type_str, res_type_str)
            identifier = ResourceIdentifier(type_id=actual_res_type, name_id=parsed_name, language_id=parsed_lang)
            new_res = None
            name_id_str = str(identifier.name_id) if isinstance(identifier.name_id, int) else f'"{identifier.name_id}"'
            original_rc_line = f'{name_id_str} {res_type_str} "{os.path.basename(filepath)}"'

            if actual_res_type in [RT_HTML, RT_MANIFEST] or \
               (isinstance(actual_res_type, str) and actual_res_type.upper() in ["TEXT", "HTML", "MANIFEST"]) or \
               filepath.lower().endswith((".txt", ".html", ".htm", ".xml", ".json", ".js")): # Guess text types
                try:
                    with open(filepath, 'r', encoding='utf-8-sig') as f: # utf-8-sig handles BOM
                        content = f.read()
                    new_res = TextBlockResource(identifier, content, resource_type_name=res_type_str)
                except Exception as e:
                    print(f"Could not read {filepath} as text: {e}, importing as FileResource.")
                    # Fallback to FileResource if text read fails or if it's not a primarily text type
                    new_res = FileResource(identifier, filepath, original_rc_statement=original_rc_line)
            else: # For images, binaries, etc.
                new_res = FileResource(identifier, filepath, original_rc_statement=original_rc_line)

            if new_res:
                self.resources.append(new_res); new_res.dirty = True
                self.populate_treeview(); self.set_app_dirty(True)
                self.show_info_message("Import Successful", f"Resource '{parsed_name}' imported from {os.path.basename(filepath)}.") # Keep info box
                self.show_status(f"Imported '{parsed_name}' from {os.path.basename(filepath)}.", 4000)


    def on_export_selected_resource(self):
        if not self.current_selected_resource_item_id: return
        res_obj = self.tree_item_to_resource.get(self.current_selected_resource_item_id)
        if not (res_obj and res_obj in self.resources):
            self.show_error_message("Export Error", "No valid resource selected for export."); return

        default_name = str(res_obj.identifier.name_id if not isinstance(res_obj.identifier.name_id, str) else res_obj.identifier.name_id.replace("\"", ""))
        default_ext = ".bin" # Default extension

        if isinstance(res_obj, FileResource): _, default_ext = os.path.splitext(res_obj.filepath)
        elif isinstance(res_obj, TextBlockResource): default_ext = ".txt"
        elif isinstance(res_obj, StringTableResource): default_ext = ".txt" # Or .rc fragment
        elif isinstance(res_obj, MenuResource): default_ext = ".rc" # Menus are best as RC
        elif isinstance(res_obj, DialogResource): default_ext = ".rc" # Dialogs best as RC
        elif isinstance(res_obj, AcceleratorResource): default_ext = ".rc"
        elif isinstance(res_obj, VersionInfoResource): default_ext = ".rc"
        elif res_obj.identifier.type_id == RT_BITMAP: default_ext = ".bmp"
        elif res_obj.identifier.type_id in [RT_ICON, RT_GROUP_ICON]: default_ext = ".ico"
        elif res_obj.identifier.type_id in [RT_CURSOR, RT_GROUP_CURSOR]: default_ext = ".cur"
        elif res_obj.identifier.type_id == RT_HTML: default_ext = ".html"
        elif res_obj.identifier.type_id == RT_MANIFEST: default_ext = ".manifest"

        file_types = [(f"{default_ext.upper()} files", f"*{default_ext}"), ("All files", "*.*")]
        if default_ext == ".bin" and res_obj.data: # If it's generic binary, offer .dat too
            file_types.insert(0, ("Data files", "*.dat"))


        save_path = tkfiledialog.asksaveasfilename(parent=self, title="Export Resource As", initialfile=f"{default_name}{default_ext}", defaultextension=default_ext, filetypes=file_types)
        if not save_path: return

        try:
            if isinstance(res_obj, FileResource):
                if res_obj.data is None: res_obj.load_data(base_dir=os.path.dirname(self.current_filepath or ".")) # Ensure data is loaded
                if res_obj.data:
                     with open(save_path, "wb") as f: f.write(res_obj.data)
                else: # If still no data (e.g. file not found on load), try to copy original if path exists
                    if os.path.exists(res_obj.filepath): shutil.copy(res_obj.filepath, save_path)
                    else: raise FileNotFoundError(f"Original file for FileResource not found: {res_obj.filepath}")
            elif isinstance(res_obj, TextBlockResource):
                with open(save_path, "w", encoding="utf-8") as f: f.write(res_obj.text_content)
            elif isinstance(res_obj, (StringTableResource, MenuResource, DialogResource, AcceleratorResource, VersionInfoResource)):
                # These are best exported as their RC text representation
                with open(save_path, "w", encoding="utf-8") as f: f.write(res_obj.to_rc_text())
            elif res_obj.data: # For RCDataResource and other binary types
                # Try specific image saving if applicable
                is_known_image_type = res_obj.identifier.type_id in [RT_BITMAP, RT_ICON, RT_GROUP_ICON, RT_CURSOR, RT_GROUP_CURSOR]
                if is_known_image_type:
                    if image_utils.save_resource_data_as_image(res_obj.data, save_path, res_obj.identifier.type_id, self.RT_MAP):
                        self.show_info_message("Export Successful", f"Resource exported to {save_path}")
                        return # Success
                    else: # Fallback to binary write if save_resource_data_as_image failed but indicated it might be an image
                        self.show_warning_message("Image Export Note", "Could not save as specific image type using Pillow directly. Saved as raw binary. You may need to verify the file format.")

                # Generic binary write for all other cases or if image save failed structurally
                with open(save_path, "wb") as f: f.write(res_obj.data)
            else:
                raise ValueError("Resource has no data to export.")
            self.show_info_message("Export Successful", f"Resource exported to {save_path}")
        except Exception as e:
            self.show_error_message("Export Error", f"Failed to export resource: {e}")
            import traceback; traceback.print_exc()


    def save_as_rc_file(self, filepath: str):
        # ... (same as before) ...
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                current_lang_id = -1
                sorted_resources = sorted(self.resources, key=lambda r: (str(self.get_type_display_name(r.identifier.type_id)), str(r.identifier.name_id), r.identifier.language_id))
                for res_obj in sorted_resources:
                    if res_obj.identifier.language_id != current_lang_id:
                        if res_obj.identifier.language_id != LANG_NEUTRAL: primary = res_obj.identifier.language_id & 0x3FF; sub = (res_obj.identifier.language_id >> 10) & 0x3F; f.write(f"LANGUAGE {primary}, {sub}\n")
                        current_lang_id = res_obj.identifier.language_id
                    f.write(res_obj.to_rc_text() + "\n\n")
            self.current_filepath = filepath; self.current_file_type = ".rc"; self.set_app_dirty(False); self.title(f"Python Resource Editor - {os.path.basename(filepath)}")
            self.show_info_message("Save Successful", f"File saved as RC: {filepath}") # Keep messagebox
            self.show_status(f"Saved RC: {os.path.basename(filepath)}", 5000)
        except Exception as e:
            self.show_error_message("Save RC Error", f"Failed to save RC file: {e}")
            self.show_status(f"Error saving RC: {e}", 7000, is_error=True)


    def _write_res_string_or_id(self, stream: io.BytesIO, value: Union[str, int]) -> int:
        """Writes a Type/Name field to a RES stream. Returns size of written field (including padding)."""
        if isinstance(value, int): # Numeric ID
            stream.write(struct.pack('<HH', 0xFFFF, value))
            return 4
        elif isinstance(value, str): # String
            # Must be null-terminated UTF-16LE, then padded to DWORD
            str_bytes = value.encode('utf-16-le') + b'\x00\x00'
            stream.write(str_bytes)
            padding_needed = (4 - (len(str_bytes) % 4)) % 4
            if padding_needed > 0:
                stream.write(b'\x00' * padding_needed)
            return len(str_bytes) + padding_needed
        else:
            # Fallback for safety, should not happen with ResourceIdentifier
            stream.write(struct.pack('<HH', 0xFFFF, 0))
            return 4

    def save_as_res_file(self, filepath: str):
        """Saves resources directly to a binary .RES file."""
        try:
            with open(filepath, 'wb') as f:
                sorted_resources = sorted(self.resources, key=lambda r: (str(self.get_type_display_name(r.identifier.type_id)), str(r.identifier.name_id), r.identifier.language_id))

                for res_obj in sorted_resources:
                    if not hasattr(res_obj, 'to_binary_data') or not callable(res_obj.to_binary_data):
                        print(f"Warning: Resource {res_obj.identifier} does not have a to_binary_data method. Skipping for RES save.")
                        skipped_count +=1
                        continue

                    binary_data = res_obj.to_binary_data()
                    if binary_data is None:
                        print(f"Warning: to_binary_data for {res_obj.identifier} returned None. Skipping.")
                        skipped_count +=1
                        continue

                    data_size = len(binary_data)

                    # Calculate HeaderSize:
                    # Type field size + Name field size + fixed fields size (16 bytes)
                    type_field_size = 0
                    name_field_size = 0

                    # Temp stream to calculate Type/Name field sizes without writing to main file yet
                    temp_stream = io.BytesIO()
                    type_field_size = self._write_res_string_or_id(temp_stream, res_obj.identifier.type_id)
                    name_field_size = self._write_res_string_or_id(temp_stream, res_obj.identifier.name_id)
                    temp_stream.close()

                    fixed_header_fields_size = 16 # DataVersion, MemoryFlags, LanguageId, Version, Characteristics
                    header_size = type_field_size + name_field_size + fixed_header_fields_size

                    # Write DataSize and HeaderSize
                    f.write(struct.pack('<LL', data_size, header_size))

                    # Write Type field
                    self._write_res_string_or_id(f, res_obj.identifier.type_id)

                    # Write Name field
                    self._write_res_string_or_id(f, res_obj.identifier.name_id)

                    # Write fixed header fields
                    data_version = 0
                    memory_flags = 0x0030 # MOVEABLE | PURE | PRELOAD (common default)
                    language_id = res_obj.identifier.language_id
                    version = 0 # User-defined
                    characteristics = 0 # User-defined
                    f.write(struct.pack('<LHHLL', data_version, memory_flags, language_id, version, characteristics))

                    # Write resource data
                    f.write(binary_data)

                    # Pad resource data to DWORD boundary
                    padding_needed = (4 - (data_size % 4)) % 4
                    if padding_needed > 0:
                        f.write(b'\x00' * padding_needed)

            self.current_filepath = filepath
            self.current_file_type = ".res"
            self.set_app_dirty(False)
            self.title(f"Python Resource Editor - {os.path.basename(filepath)}")
            msg = f"File saved as RES: {os.path.basename(filepath)}"
            if skipped_count > 0: msg += f" ({skipped_count} resources skipped due to missing binary data capability)."
            self.show_info_message("Save Successful", msg) # Keep messagebox
            self.show_status(msg, 5000)

        except Exception as e:
            self.show_error_message("Save RES Error", f"Failed to save RES file directly: {e}")
            self.show_status(f"Error saving RES: {e}", 7000, is_error=True)
            import traceback
            traceback.print_exc()


    def on_save_as_file(self):
        # ... (same as before) ...
        if not self.resources and not tkmessagebox.askyesno("Save Empty File?", "No resources. Create empty file?", parent=self): return

        pe_file_types = [("PE Files", "*.exe *.dll *.ocx *.sys *.scr"), ("All files", "*.*")]
        script_file_types = [("RC Script", "*.rc"), ("RES File", "*.res")]
        all_save_types = script_file_types + pe_file_types

        filepath = tkfiledialog.asksaveasfilename(title="Save As", defaultextension=".rc", filetypes=all_save_types)
        if not filepath: return
        _, ext = os.path.splitext(filepath); ext = ext.lower()

        if ext == ".rc": self.save_as_rc_file(filepath)
        elif ext == ".res": self.save_as_res_file(filepath)
        elif ext in [".exe", ".dll", ".ocx", ".sys", ".scr"]:
            # Check if current_filepath is the same to determine if it's a "Save" or "Save As" for PE.
            # For PE, "Save As" implies copying the original PE and then updating resources in the copy.
            # "Save" updates the currently opened PE file (with backup).
            if self.current_filepath and os.path.normpath(self.current_filepath) == os.path.normpath(filepath):
                # This is a "Save" operation on an already opened PE file
                if self.save_pe_file(filepath):
                    self.show_info_message("Save Successful", f"PE File '{os.path.basename(filepath)}' updated successfully.")
                # save_pe_file already shows error messages
            else:
                # This is a "Save As" operation for a PE file.
                # We need to copy the original PE file (if one is open) or a template PE to the new location,
                # then update resources in that copy. This is more complex than a direct save.
                # For now, let's restrict direct save to only the currently open PE file.
                if self.current_file_type in [".exe", ".dll", ".ocx", ".sys", ".scr"] and self.current_filepath:
                    try:
                        shutil.copy2(self.current_filepath, filepath)
                        self.current_filepath = filepath # Update current path to the new copy
                        self.current_file_type = ext
                        if self.save_pe_file(filepath): # Update the new copy
                             self.show_info_message("Save As Successful", f"PE File saved as '{os.path.basename(filepath)}' and updated.")
                             self.show_status(f"Saved PE As: {os.path.basename(filepath)}", 5000)
                        # save_pe_file already shows error messages and status
                    except Exception as e:
                        self.show_error_message("Save As PE Error", f"Failed to copy file to '{filepath}': {e}")
                        self.show_status(f"Error saving PE As: {e}", 7000, is_error=True)
                else:
                    self.show_error_message("Save As PE Error", "To save as a new PE file, please open an existing PE file first to use as a template, modify resources, then 'Save As'. Direct creation of PE from scratch is not supported.")
                    self.show_status("Save As PE Error: No template PE file open.", 7000, is_error=True)
        else:
            self.show_error_message("Save As Error", f"Unsupported file type: {ext}. Choose .rc, .res, .exe, or .dll.")
            self.show_status(f"Save As Error: Unsupported type '{ext}'.", 5000, is_error=True)

    def on_save_file(self):
        if not self.current_filepath:
            self.on_save_as_file()
            return

        if not self.resources and self.current_filepath:
            if not tkmessagebox.askyesno("Save Empty?", "No resources. Save empty file? (This might corrupt PE files or create empty RC/RES)", parent=self):
                return

        if self.current_file_type == ".rc":
            self.save_as_rc_file(self.current_filepath)
        elif self.current_file_type == ".res":
            self.save_as_res_file(self.current_filepath)
        elif self.current_file_type == "PE": # Check against generic "PE" type
            if self.save_pe_file(self.current_filepath):
                 self.show_info_message("Save Successful", f"PE File '{os.path.basename(self.current_filepath)}' updated successfully.")
                 self.show_status(f"Saved PE: {os.path.basename(self.current_filepath)}", 5000)
            # save_pe_file handles its own error messages and status for failures
        else:
            self.on_save_as_file()


    def save_pe_file(self, filepath: str) -> bool:
        # Ensure imports are at the top of the file for clarity, but this is functional.
        from ..utils.winapi_ctypes import BeginUpdateResourcesW, UpdateResourceW, EndUpdateResourcesW, MAKEINTRESOURCE
        import ctypes # For get_last_error and wintypes
        import shutil
        import os

        backup_path = filepath + ".pyre.bak"
        try:
            if os.path.exists(backup_path): os.remove(backup_path)
            shutil.copy2(filepath, backup_path)
            self.show_status(f"Backup created: {os.path.basename(backup_path)}", 2000)
        except Exception as e:
            self.show_error_message("Backup Error", f"Failed to create backup for '{filepath}': {e}")
            self.show_status(f"Backup Error for '{os.path.basename(filepath)}': {e}", 7000, is_error=True)
            return False

        # Note: BeginUpdateResourcesW's first argument is LPCWSTR.
        # ctypes handles string conversion for LPCWSTR.
        hUpdate = BeginUpdateResourcesW(filepath, True) # True = delete existing resources

        # A NULL handle from ctypes for wintypes.HANDLE is often represented as None or an int 0.
        # Let's check against None, as that's common for failed HANDLE returns via ctypes.
        if hUpdate is None:
            err = ctypes.get_last_error()
            try:
                if os.path.exists(backup_path): os.remove(backup_path)
            except OSError: pass # Ignore error if backup removal fails
            self.show_error_message("PE Update Error", f"BeginUpdateResourcesW failed (Error {err}). Cannot update PE file.")
            self.show_status(f"BeginUpdateResourcesW failed (Error {err}) on {os.path.basename(filepath)}", 7000, is_error=True)
            return False

        success_all = True; updated_resource_count = 0; skipped_resource_count = 0
        self.show_status(f"Starting resource update for {os.path.basename(filepath)}...", 2000)

        for res_obj in self.resources:
            res_type_val = res_obj.identifier.type_id
            res_name_val = res_obj.identifier.name_id

            # Prepare lpType and lpName
            if isinstance(res_type_val, int): lpType = MAKEINTRESOURCE(res_type_val)
            elif isinstance(res_type_val, str): lpType = ctypes.wintypes.LPWSTR(res_type_val)
            else: # Should not happen with valid ResourceIdentifier
                print(f"Warning: Invalid resource type for {res_obj.identifier}. Skipping.")
                skipped_resource_count +=1; continue

            if isinstance(res_name_val, int): lpName = MAKEINTRESOURCE(res_name_val)
            elif isinstance(res_name_val, str): lpName = ctypes.wintypes.LPWSTR(res_name_val)
            else: # Should not happen
                print(f"Warning: Invalid resource name for {res_obj.identifier}. Skipping.")
                skipped_resource_count +=1; continue

            wLang = res_obj.identifier.language_id

            try: binary_data = res_obj.to_binary_data()
            except Exception as e_data:
                msg = f"Failed to get binary data for resource {res_obj.identifier.type_id_to_str()}/{res_obj.identifier.name_id_to_str()}: {e_data}"
                print(f"Error getting binary data for {res_obj.identifier}: {e_data}")
                self.show_error_message("Data Conversion Error", msg)
                self.show_status(f"Data error for res {res_obj.identifier.name_id_to_str()}", 5000, is_error=True)
                skipped_resource_count +=1; continue

            if binary_data is None:
                print(f"Warning: No binary data for resource {res_obj.identifier}. Skipping update for this resource.")
                skipped_resource_count +=1; continue

            # Create a buffer from the bytes data that UpdateResourceW can use.
            # ctypes.c_char_p(binary_data) might be problematic if data contains null bytes prematurely.
            # Using a buffer ensures the whole data is passed.
            # However, UpdateResourceW expects LPVOID which can be a pointer to any data.
            # Python's `bytes` type when passed to a c_void_p (LPVOID) argtype in ctypes
            # is generally handled correctly as a pointer to its buffer.
            lpData = binary_data
            cbData = len(binary_data)

            if not UpdateResourceW(hUpdate, lpType, lpName, wLang, lpData, cbData):
                err = ctypes.get_last_error()
                msg = f"UpdateResourceW failed for {res_obj.identifier.type_id_to_str()}/{res_obj.identifier.name_id_to_str()} (Error {err})."
                self.show_error_message("PE Update Error", msg)
                self.show_status(msg, 7000, is_error=True)
                success_all = False; break
            updated_resource_count +=1

        if success_all and (updated_resource_count > 0 or (len(self.resources) == 0 and skipped_resource_count == 0) ):
            # If successful and we updated something, OR if we successfully deleted all resources (0 resources, 0 skipped)
            if not EndUpdateResourcesW(hUpdate, False): # False = Write changes
                err = ctypes.get_last_error()
                self.show_error_message("PE Update Error", f"EndUpdateResourcesW (commit) failed (Error {err}). Restoring from backup.")
                self.show_status(f"EndUpdateResourcesW (commit) failed (Error {err}) for {os.path.basename(filepath)}", 7000, is_error=True)
                try:
                    if os.path.exists(backup_path): shutil.move(backup_path, filepath)
                    else: print("Error: Backup file missing, cannot restore.")
                except Exception as e_restore:
                    self.show_error_message("Restore Error", f"Failed to restore from backup '{backup_path}': {e_restore}")
                return False
            else: # Successfully committed
                try:
                    if os.path.exists(backup_path): os.remove(backup_path)
                except OSError: pass
                self.set_app_dirty(False)
                return True
        else: # Loop broke (success_all=False) or all resources were skipped but there were some to begin with
            EndUpdateResourcesW(hUpdate, True) # True = Discard changes
            restore_msg_suffix = ""
            try:
                if os.path.exists(backup_path): shutil.move(backup_path, filepath)
                else: restore_msg_suffix = " Backup missing, could not restore."
            except Exception as e_restore:
                restore_msg_suffix = f" Restore from backup also failed: {e_restore}"

            final_msg = f"Resource updates failed for {os.path.basename(filepath)}. Changes discarded.{restore_msg_suffix}"
            if updated_resource_count == 0 and skipped_resource_count > 0 and len(self.resources) > 0 :
                 # This means no UpdateResourceW calls succeeded or were even attempted if all skipped.
                 self.show_info_message("PE Update Information", final_msg) # Use info if no update call actually failed.
            # If success_all is False, an error message was already shown by UpdateResourceW failure.
            self.show_status(final_msg, 7000, is_error=not success_all) # is_error if an update failed.
            return False

    def on_about(self):
        # ... (same as before) ...
        about = customtkinter.CTkToplevel(self); about.title("About"); about.geometry("350x180"); about.transient(self); about.grab_set()
        text = "Python Resource Editor\nVersion 0.1\n\nInspect/modify resources in PE, RES, RC files."
        customtkinter.CTkLabel(about, text=text, wraplength=320).pack(padx=20, pady=15, expand=True)
        customtkinter.CTkButton(about, text="OK", command=about.destroy).pack(pady=10)
        about.wait_window()


    def toggle_appearance_mode(self):
        # ... (same as before) ...
        customtkinter.set_appearance_mode("Light" if customtkinter.get_appearance_mode() == "Dark" else "Dark")
        self.populate_treeview()

    def prompt_save_if_dirty(self) -> bool:
        # ... (same as before) ...
        if not self.app_dirty_flag: return True
        res = tkmessagebox.askyesnocancel("Unsaved Changes", "Save changes before proceeding?", parent=self)
        if res is True:
            self.on_save_file()
            # If on_save_file failed (e.g. user cancelled Save As), app is still dirty.
            return not self.app_dirty_flag
        return res is False

    def show_status(self, message: str, duration_ms: int = 0, is_error: bool = False):
        if not hasattr(self, 'statusbar_label') or self.statusbar_label is None:
            print(f"Status (no bar): {message}")
            return

        # TODO: Add color change for error
        # current_fg_color = self.statusbar_label.cget("fg_color") # This might not be text color
        # error_color = ("#ffcccc", "#552222") # Example light/dark error bg or text color
        # normal_color = ...
        # self.statusbar_label.configure(text_color=error_color if is_error else normal_color)

        self.statusbar_label.configure(text=message)

        if hasattr(self, '_status_clear_job') and self._status_clear_job is not None:
            self.after_cancel(self._status_clear_job)
            self._status_clear_job = None

        if duration_ms > 0:
            self._status_clear_job = self.after(duration_ms, lambda: self.statusbar_label.configure(text="Ready"))
        elif not message or message == "Ready": # If clearing or setting to Ready, don't schedule clear
             if hasattr(self, '_status_clear_job') and self._status_clear_job is not None:
                self.after_cancel(self._status_clear_job)
                self._status_clear_job = None


    def on_closing(self):
        # ... (same as before) ...
        if self.prompt_save_if_dirty(): self.destroy()

if __name__ == '__main__':
    customtkinter.set_appearance_mode("System")
    customtkinter.set_default_color_theme("blue")
    app = App()
    app.mainloop()

