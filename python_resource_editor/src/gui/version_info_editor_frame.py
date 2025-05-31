import customtkinter
import tkinter.ttk as ttk
from tkinter import simpledialog, messagebox
from typing import List, Dict, Callable, Optional, Union, Tuple
import copy

from ..core.version_parser_util import VersionFixedInfo, VersionStringTableInfo, VersionStringEntry, VersionVarEntry
from ..core.resource_types import VersionInfoResource # For type hinting

class VersionInfoEditorFrame(customtkinter.CTkFrame):
    def __init__(self, master, version_info_resource: VersionInfoResource, app_callbacks: Dict[str, Callable]):
        super().__init__(master)
        self.resource = version_info_resource
        self.app_callbacks = app_callbacks

        self.fixed_info_copy: VersionFixedInfo = copy.deepcopy(version_info_resource.fixed_info)
        self.string_tables_copy: List[VersionStringTableInfo] = copy.deepcopy(version_info_resource.string_tables)
        self.var_info_copy: List[VersionVarEntry] = copy.deepcopy(version_info_resource.var_info)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1) # Tabview takes most space
        self.grid_rowconfigure(1, weight=0) # Apply button

        # --- Tab View for Different Sections ---
        self.tab_view = customtkinter.CTkTabview(self)
        self.tab_view.pack(expand=True, fill="both", padx=5, pady=5)

        self.tab_fixed = self.tab_view.add("Fixed Info")
        self.tab_strings = self.tab_view.add("String Tables")
        self.tab_vars = self.tab_view.add("VarFileInfo (Translation)")

        self.prop_widgets_fixed: Dict[str, List[customtkinter.CTkEntry]] = {}
        self.string_table_widgets: Dict[str, Union[customtkinter.CTkComboBox, ttk.Treeview, customtkinter.CTkButton]] = {}
        self.var_info_widgets: Dict[str, ttk.Treeview] = {}


        self._create_fixed_info_tab(self.tab_fixed)
        self._create_string_tables_tab(self.tab_strings)
        self._create_var_info_tab(self.tab_vars)

        # --- Apply All Button ---
        self.apply_all_button = customtkinter.CTkButton(self, text="Apply Changes to Resource", command=self.apply_all_changes_to_resource)
        self.apply_all_button.pack(pady=10, padx=5, side="bottom")

    def _create_fixed_info_tab(self, tab_frame):
        frame = customtkinter.CTkScrollableFrame(tab_frame) # Make scrollable if many fields
        frame.pack(expand=True, fill="both")

        fixed_props_layout = [
            ("File Version", "file_version", 4), ("Product Version", "product_version", 4),
            ("FileFlagsMask", "file_flags_mask", 1, "hex"), ("FileFlags", "file_flags", 1, "hex"),
            ("FileOS", "file_os", 1, "hex"), ("FileType", "file_type", 1, "hex"),
            ("FileSubtype", "file_subtype", 1, "hex"),
            # ("FileDateMS", "file_date_ms", 1, "hex"), ("FileDateLS", "file_date_ls", 1, "hex") # FileDate usually not edited manually
        ]
        self.prop_widgets_fixed = {}

        for i, (label_text, attr_name, num_entries, *display_type) in enumerate(fixed_props_layout):
            customtkinter.CTkLabel(frame, text=label_text).grid(row=i, column=0, padx=5, pady=2, sticky="w")
            current_val = getattr(self.fixed_info_copy, attr_name)

            entries_list = []
            if num_entries == 4: # Version tuples
                for j in range(4):
                    entry = customtkinter.CTkEntry(frame, width=50)
                    entry.insert(0, str(current_val[j] if current_val and len(current_val) == 4 else "0"))
                    entry.grid(row=i, column=j + 1, padx=2, pady=2, sticky="w")
                    entries_list.append(entry)
            else: # Single entry (possibly hex)
                entry = customtkinter.CTkEntry(frame, width=120)
                val_to_display = current_val
                if display_type and display_type[0] == "hex":
                    val_to_display = f"0x{current_val:X}"
                entry.insert(0, str(val_to_display))
                entry.grid(row=i, column=1, columnspan=4, padx=2, pady=2, sticky="ew")
                entries_list.append(entry)
            self.prop_widgets_fixed[attr_name] = entries_list

        # Apply button for this tab
        apply_button = customtkinter.CTkButton(frame, text="Apply Fixed Info", command=self._apply_fixed_info_changes)
        apply_button.grid(row=len(fixed_props_layout), column=0, columnspan=5, pady=10)


    def _create_string_tables_tab(self, tab_frame):
        top_frame = customtkinter.CTkFrame(tab_frame, fg_color="transparent")
        top_frame.pack(fill="x", padx=5, pady=5)

        customtkinter.CTkLabel(top_frame, text="Language/Codepage Block:").pack(side="left", padx=(0,5))

        lang_cp_keys = [st.lang_codepage_hex for st in self.string_tables_copy] if self.string_tables_copy else ["(No StringFileInfo Blocks)"]
        self.string_table_widgets["lang_combo"] = customtkinter.CTkComboBox(
            top_frame, values=lang_cp_keys, command=self._on_string_table_lang_select
        )
        if self.string_tables_copy: self.string_table_widgets["lang_combo"].set(lang_cp_keys[0])
        self.string_table_widgets["lang_combo"].pack(side="left", padx=5)

        customtkinter.CTkButton(top_frame, text="Add Block", width=80, command=self._add_string_table_block).pack(side="left", padx=5)
        customtkinter.CTkButton(top_frame, text="Del Block", width=80, command=self._delete_string_table_block).pack(side="left", padx=5)

        # Treeview for key-value pairs
        tree_frame = customtkinter.CTkFrame(tab_frame)
        tree_frame.pack(expand=True, fill="both", padx=5, pady=5)
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        str_tree = ttk.Treeview(tree_frame, columns=("Key", "Value"), show="headings")
        str_tree.heading("Key", text="Key"); str_tree.column("Key", width=150, anchor="w")
        str_tree.heading("Value", text="Value"); str_tree.column("Value", width=300, stretch=True, anchor="w")
        str_tree.grid(row=0, column=0, sticky="nsew")
        self.string_table_widgets["strings_tree"] = str_tree

        str_tree_scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=str_tree.yview)
        str_tree_scroll_y.grid(row=0, column=1, sticky="ns")
        str_tree.configure(yscrollcommand=str_tree_scroll_y.set)

        # Buttons for string entries
        str_button_frame = customtkinter.CTkFrame(tab_frame, fg_color="transparent")
        str_button_frame.pack(fill="x", padx=5, pady=5)
        customtkinter.CTkButton(str_button_frame, text="Add String", command=self._add_string_entry).pack(side="left", padx=5)
        customtkinter.CTkButton(str_button_frame, text="Edit String", command=self._edit_string_entry).pack(side="left", padx=5)
        customtkinter.CTkButton(str_button_frame, text="Delete String", command=self._delete_string_entry).pack(side="left", padx=5)

        if self.string_tables_copy: self._populate_string_entries_for_lang(self.string_tables_copy[0].lang_codepage_hex)


    def _create_var_info_tab(self, tab_frame):
        # Simplified: Display "Translation" only for now
        customtkinter.CTkLabel(tab_frame, text="VarFileInfo (Mainly Translation Block)").pack(anchor="w", padx=5, pady=5)

        tree = ttk.Treeview(tab_frame, columns=("Key", "Values"), show="headings")
        tree.heading("Key", text="Key"); tree.column("Key", width=150)
        tree.heading("Values", text="Language/Codepage Pairs (Hex)"); tree.column("Values", width=300)
        tree.pack(expand=True, fill="both", padx=5, pady=5)
        self.var_info_widgets["vars_tree"] = tree

        for var_entry in self.var_info_copy:
            if var_entry.key.upper() == "TRANSLATION":
                vals_str = ", ".join([f"0x{v:04X}" for v in var_entry.values])
                tree.insert("", "end", values=(var_entry.key, vals_str))

        customtkinter.CTkLabel(tab_frame, text="Note: Editing VarFileInfo is not fully implemented in this view.").pack(pady=5)


    # --- Event Handlers and Logic for Tabs ---
    def _apply_fixed_info_changes(self):
        changed = False
        for attr, entries in self.prop_widgets_fixed.items():
            if len(entries) == 4: # Version tuple
                new_vals = tuple(int(e.get() or "0") for e in entries)
                if getattr(self.fixed_info_copy, attr) != new_vals:
                    setattr(self.fixed_info_copy, attr, new_vals); changed = True
            else: # Single value
                val_str = entries[0].get()
                new_val = int(val_str, 0) if val_str.lower().startswith("0x") else int(val_str or "0")
                if getattr(self.fixed_info_copy, attr) != new_val:
                    setattr(self.fixed_info_copy, attr, new_val); changed = True
        if changed:
            if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
            messagebox.showinfo("Fixed Info", "Fixed info changes applied locally.", parent=self)

    def _on_string_table_lang_select(self, selected_lang_cp: str):
        self._populate_string_entries_for_lang(selected_lang_cp)

    def _populate_string_entries_for_lang(self, lang_cp_hex: str):
        tree = self.string_table_widgets["strings_tree"]
        for i in tree.get_children(): tree.delete(i)

        table_info = next((st for st in self.string_tables_copy if st.lang_codepage_hex == lang_cp_hex), None)
        if table_info:
            for idx, entry in enumerate(table_info.entries):
                tree.insert("", "end", iid=str(idx), values=(entry.key, entry.value))

    def _get_current_string_table(self) -> Optional[VersionStringTableInfo]:
        if not self.string_tables_copy: return None
        selected_lang_cp = self.string_table_widgets["lang_combo"].get()
        return next((st for st in self.string_tables_copy if st.lang_codepage_hex == selected_lang_cp), None)

    def _add_string_table_block(self):
        lang_cp = simpledialog.askstring("Add StringFileInfo Block", "Enter Lang/Codepage (e.g., 040904b0):", parent=self)
        if lang_cp and re.match(r"^[0-9a-fA-F]{8}$", lang_cp):
            if any(st.lang_codepage_hex == lang_cp for st in self.string_tables_copy):
                messagebox.showerror("Error", f"Block {lang_cp} already exists.", parent=self)
                return
            new_block = VersionStringTableInfo(lang_cp_hex=lang_cp, entries=[])
            self.string_tables_copy.append(new_block)
            self.string_table_widgets["lang_combo"].configure(values=[st.lang_codepage_hex for st in self.string_tables_copy])
            self.string_table_widgets["lang_combo"].set(lang_cp)
            self._populate_string_entries_for_lang(lang_cp)
            if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
        elif lang_cp:
            messagebox.showerror("Error", "Invalid Lang/Codepage format. Must be 8 hex digits.", parent=self)


    def _delete_string_table_block(self):
        current_table = self._get_current_string_table()
        if not current_table: messagebox.showinfo("Delete Block", "No block selected.", parent=self); return
        if messagebox.askyesno("Confirm Delete", f"Delete StringFileInfo block '{current_table.lang_codepage_hex}'?", parent=self):
            self.string_tables_copy.remove(current_table)
            lang_cp_keys = [st.lang_codepage_hex for st in self.string_tables_copy] or ["(No Blocks)"]
            self.string_table_widgets["lang_combo"].configure(values=lang_cp_keys)
            new_selection = lang_cp_keys[0] if lang_cp_keys[0] != "(No Blocks)" else None
            self.string_table_widgets["lang_combo"].set(new_selection if new_selection else "")
            self._populate_string_entries_for_lang(new_selection if new_selection else "") # Clears tree if no selection
            if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)


    def _add_string_entry(self):
        current_table = self._get_current_string_table()
        if not current_table: messagebox.showinfo("Add String", "No StringFileInfo block selected.", parent=self); return

        key = simpledialog.askstring("Add String", "Enter Key (e.g., CompanyName):", parent=self)
        if not key: return
        value = simpledialog.askstring("Add String", f"Enter Value for '{key}':", parent=self)
        if value is None: return # Cancelled

        current_table.entries.append(VersionStringEntry(key.strip(), value))
        self._populate_string_entries_for_lang(current_table.lang_codepage_hex)
        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)

    def _edit_string_entry(self):
        current_table = self._get_current_string_table()
        tree = self.string_table_widgets["strings_tree"]
        selected = tree.selection()
        if not current_table or not selected: messagebox.showinfo("Edit String", "No string selected.", parent=self); return

        item_idx = int(selected[0]) # Assuming IID is index
        entry = current_table.entries[item_idx]

        new_key = simpledialog.askstring("Edit String", "Enter Key:", initialvalue=entry.key, parent=self)
        if not new_key: return
        new_value = simpledialog.askstring("Edit String", f"Enter Value for '{new_key}':", initialvalue=entry.value, parent=self)
        if new_value is None: return

        entry.key = new_key.strip(); entry.value = new_value
        self._populate_string_entries_for_lang(current_table.lang_codepage_hex)
        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)

    def _delete_string_entry(self):
        current_table = self._get_current_string_table()
        tree = self.string_table_widgets["strings_tree"]
        selected = tree.selection()
        if not current_table or not selected: messagebox.showinfo("Delete String", "No string selected.", parent=self); return

        if messagebox.askyesno("Confirm Delete", "Delete selected string(s)?", parent=self):
            indices_to_delete = sorted([int(iid) for iid in selected], reverse=True)
            for idx in indices_to_delete: del current_table.entries[idx]
            self._populate_string_entries_for_lang(current_table.lang_codepage_hex)
            if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)


    # --- Apply All ---
    def apply_all_changes_to_resource(self):
        # Fixed info is applied directly via its button, but ensure it's current
        self._apply_fixed_info_changes() # Ensure any pending changes are committed

        self.resource.fixed_info = copy.deepcopy(self.fixed_info_copy)
        self.resource.string_tables = copy.deepcopy(self.string_tables_copy)
        self.resource.var_info = copy.deepcopy(self.var_info_copy) # VarInfo not editable yet, but good practice
        self.resource.dirty = True

        if self.app_callbacks.get('set_dirty_callback'):
            self.app_callbacks['set_dirty_callback'](True)
        messagebox.showinfo("Changes Applied", "All Version Info changes applied to in-memory resource. Save file to persist.", parent=self)


if __name__ == '__main__':
    # Test the VersionInfoEditorFrame
    class DummyApp(customtkinter.CTk):
        def __init__(self):
            super().__init__()
            self.title("VersionInfo Editor Test")
            self.geometry("700x600")

            from ..core.resource_base import ResourceIdentifier, RT_VERSION
            ident = ResourceIdentifier(type_id=RT_VERSION, name_id=1, language_id=1033) # Standard VS_VERSION_INFO

            fixed = VersionFixedInfo(file_version=(1,0,0,1), product_version=(1,0,0,1))
            st1 = VersionStringTableInfo("040904B0", [VersionStringEntry("ProductName", "Test Product")])
            vi1 = VersionVarEntry("Translation", [0x0409, 0x04B0])
            self.ver_res = VersionInfoResource(identifier=ident, fixed_info=fixed, string_tables=[st1], var_info=[vi1])

            def set_dirty_test(is_dirty):
                print(f"App dirty state set to: {is_dirty}")
                self.title(f"VersionInfo Editor Test {'*' if is_dirty else ''}")

            editor = VersionInfoEditorFrame(self, self.ver_res, app_callbacks={'set_dirty_callback': set_dirty_test})
            editor.pack(expand=True, fill="both")

            self.protocol("WM_DELETE_WINDOW", self.quit_app)

        def quit_app(self):
            print("\nFinal VersionInfoResource on quit:")
            print(self.ver_res.fixed_info)
            for st in self.ver_res.string_tables: print(st)
            for vi in self.ver_res.var_info: print(vi)
            self.destroy(); self.quit()

    customtkinter.set_appearance_mode("System")
    customtkinter.set_default_color_theme("blue")
    app = DummyApp()
    app.mainloop()
```
