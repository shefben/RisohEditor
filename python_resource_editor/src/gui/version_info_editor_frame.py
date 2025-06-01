import customtkinter
import tkinter.ttk as ttk
from tkinter import simpledialog, messagebox
from typing import List, Dict, Callable, Optional, Union, Tuple
import copy
import re

from ..core.version_parser_util import VersionFixedInfo, VersionStringTableInfo, VersionStringEntry, VersionVarEntry
from ..core.resource_types import VersionInfoResource

class VersionInfoEditorFrame(customtkinter.CTkFrame):
    def __init__(self, master, version_info_resource: VersionInfoResource, app_callbacks: Dict[str, Callable]):
        super().__init__(master)
        self.resource = version_info_resource
        self.app_callbacks = app_callbacks

        self.fixed_info_copy: VersionFixedInfo = copy.deepcopy(version_info_resource.fixed_info)
        self.string_tables_copy: List[VersionStringTableInfo] = copy.deepcopy(version_info_resource.string_tables)
        self.var_info_copy: List[VersionVarEntry] = copy.deepcopy(version_info_resource.var_info)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        self.tab_view = customtkinter.CTkTabview(self)
        self.tab_view.pack(expand=True, fill="both", padx=5, pady=5)

        self.tab_fixed = self.tab_view.add("Fixed Info")
        self.tab_strings = self.tab_view.add("String Tables")
        self.tab_vars = self.tab_view.add("VarFileInfo (Translation)")

        self.prop_widgets_fixed: Dict[str, List[customtkinter.CTkEntry]] = {}
        self.sfi_widgets: Dict[str, Union[customtkinter.CTkComboBox, ttk.Treeview, customtkinter.CTkButton]] = {}
        self.vfi_widgets: Dict[str, Union[ttk.Treeview, customtkinter.CTkButton]] = {}

        self._create_fixed_info_tab(self.tab_fixed)
        self._create_string_tables_tab(self.tab_strings)
        self._create_var_info_tab(self.tab_vars)

        self.apply_all_button = customtkinter.CTkButton(self, text="Apply All Changes to Resource", command=self.apply_all_changes_to_resource)
        self.apply_all_button.pack(pady=10, padx=5, side="bottom")

    def _create_fixed_info_tab(self, tab_frame):
        frame = customtkinter.CTkScrollableFrame(tab_frame)
        frame.pack(expand=True, fill="both", padx=5, pady=5)
        frame.grid_columnconfigure(1, weight=1)

        fixed_props_layout = [
            ("File Version", "file_version", 4, "version"),
            ("Product Version", "product_version", 4, "version"),
            ("FileFlagsMask", "file_flags_mask", 1, "hex"),
            ("FileFlags", "file_flags", 1, "hex"),
            ("FileOS", "file_os", 1, "hex"),
            ("FileType", "file_type", 1, "hex"),
            ("FileSubtype", "file_subtype", 1, "hex"),
        ]
        self.prop_widgets_fixed = {}

        for i, (label_text, attr_name, num_entries, entry_type) in enumerate(fixed_props_layout):
            customtkinter.CTkLabel(frame, text=label_text).grid(row=i, column=0, padx=5, pady=3, sticky="w")
            current_val = getattr(self.fixed_info_copy, attr_name)
            entries_list = []
            if num_entries == 4:
                for j in range(4):
                    entry = customtkinter.CTkEntry(frame, width=60)
                    entry.insert(0, str(current_val[j] if current_val and len(current_val) == 4 else "0"))
                    entry.grid(row=i, column=j + 1, padx=2, pady=3, sticky="w")
                    entries_list.append(entry)
            else:
                entry = customtkinter.CTkEntry(frame, width=150)
                val_to_display = f"0x{current_val:X}" if entry_type == "hex" else str(current_val or "0")
                entry.insert(0, val_to_display)
                entry.grid(row=i, column=1, columnspan=num_entries, padx=2, pady=3, sticky="ew")
                entries_list.append(entry)
            self.prop_widgets_fixed[attr_name] = entries_list

        apply_button = customtkinter.CTkButton(frame, text="Apply Fixed Info Changes", command=self._apply_fixed_info_changes)
        apply_button.grid(row=len(fixed_props_layout), column=0, columnspan=5, pady=10, sticky="s")

    def _create_string_tables_tab(self, tab_frame):
        top_frame = customtkinter.CTkFrame(tab_frame, fg_color="transparent")
        top_frame.pack(fill="x", padx=5, pady=5)
        customtkinter.CTkLabel(top_frame, text="Language/Codepage Block:").pack(side="left", padx=(0,5))

        self.sfi_widgets["lang_combo"] = customtkinter.CTkComboBox(top_frame, values=[], command=self._on_sfi_lang_select, width=150) # Initial empty
        self.sfi_widgets["lang_combo"].pack(side="left", padx=5)
        self._populate_sfi_blocks_combobox() # Populate and set initial

        customtkinter.CTkButton(top_frame, text="Add Block", width=80, command=self._on_add_sfi_block).pack(side="left", padx=5)
        customtkinter.CTkButton(top_frame, text="Del Block", width=80, command=self._on_delete_sfi_block).pack(side="left", padx=5)

        tree_frame = customtkinter.CTkFrame(tab_frame)
        tree_frame.pack(expand=True, fill="both", padx=5, pady=5)
        tree_frame.grid_columnconfigure(0, weight=1); tree_frame.grid_rowconfigure(0, weight=1)

        str_tree = ttk.Treeview(tree_frame, columns=("Key", "Value"), show="headings")
        str_tree.heading("Key", text="Key"); str_tree.column("Key", width=150, anchor="w")
        str_tree.heading("Value", text="Value"); str_tree.column("Value", width=300, stretch=True, anchor="w")
        str_tree.grid(row=0, column=0, sticky="nsew")
        self.sfi_widgets["strings_tree"] = str_tree
        str_tree.bind("<Double-1>", lambda e: self._on_edit_sfi_entry())

        str_tree_scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=str_tree.yview)
        str_tree_scroll_y.grid(row=0, column=1, sticky="ns"); str_tree.configure(yscrollcommand=str_tree_scroll_y.set)

        str_button_frame = customtkinter.CTkFrame(tab_frame, fg_color="transparent")
        str_button_frame.pack(fill="x", padx=5, pady=5)
        customtkinter.CTkButton(str_button_frame, text="Add String", command=self._on_add_sfi_entry).pack(side="left", padx=5)
        customtkinter.CTkButton(str_button_frame, text="Edit String", command=self._on_edit_sfi_entry).pack(side="left", padx=5)
        customtkinter.CTkButton(str_button_frame, text="Delete String", command=self._on_delete_sfi_entry).pack(side="left", padx=5)

        if self.string_tables_copy: self._populate_sfi_entries_for_lang(self.string_tables_copy[0].lang_codepage_hex)
        else: self._populate_sfi_entries_for_lang(None) # Clear tree


    def _create_var_info_tab(self, tab_frame):
        customtkinter.CTkLabel(tab_frame, text="VarFileInfo (Primarily 'Translation' Block)").pack(anchor="w", padx=5, pady=5)
        tree_frame = customtkinter.CTkFrame(tab_frame)
        tree_frame.pack(expand=True, fill="both", padx=5, pady=5)
        tree_frame.grid_columnconfigure(0, weight=1); tree_frame.grid_rowconfigure(0, weight=1)

        tree = ttk.Treeview(tree_frame, columns=("LangID_Hex", "CodepageID_Hex"), show="headings")
        tree.heading("LangID_Hex", text="Language ID (Hex)"); tree.column("LangID_Hex", width=150, anchor="w")
        tree.heading("CodepageID_Hex", text="Codepage ID (Hex)"); tree.column("CodepageID_Hex", width=150, anchor="w")
        tree.grid(row=0, column=0, sticky="nsew")
        self.vfi_widgets["vars_tree"] = tree

        vfi_tree_scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        vfi_tree_scroll_y.grid(row=0, column=1, sticky="ns"); tree.configure(yscrollcommand=vfi_tree_scroll_y.set)

        vfi_button_frame = customtkinter.CTkFrame(tab_frame, fg_color="transparent")
        vfi_button_frame.pack(fill="x", padx=5, pady=5)
        customtkinter.CTkButton(vfi_button_frame, text="Add Translation", command=self._on_add_translation_entry).pack(side="left", padx=5)
        customtkinter.CTkButton(vfi_button_frame, text="Delete Selected Translation", command=self._on_delete_translation_entry).pack(side="left", padx=5)
        self._populate_var_info_tab()

    def _apply_fixed_info_changes(self):
        changed = False
        for attr, entries_list in self.prop_widgets_fixed.items():
            current_fixed_val = getattr(self.fixed_info_copy, attr)
            if isinstance(current_fixed_val, tuple) and len(entries_list) == 4 :
                try: new_vals = tuple(int(e.get().strip() or "0") for e in entries_list)
                except ValueError: messagebox.showerror("Input Error", f"Invalid number in version field for {attr}.", parent=self); return
                if current_fixed_val != new_vals: setattr(self.fixed_info_copy, attr, new_vals); changed = True
            elif len(entries_list) == 1:
                val_str = entries_list[0].get().strip()
                try:
                    new_val = int(val_str, 0) if val_str else 0
                    if current_fixed_val != new_val: setattr(self.fixed_info_copy, attr, new_val); changed = True
                except ValueError: messagebox.showerror("Input Error", f"Invalid numeric/hex value for {attr}: {val_str}", parent=self); return
        if changed:
            if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)

    def _populate_sfi_blocks_combobox(self):
        lang_cp_keys = [st.lang_codepage_hex for st in self.string_tables_copy] if self.string_tables_copy else ["(No StringFileInfo Blocks)"]
        self.sfi_widgets["lang_combo"].configure(values=lang_cp_keys)
        current_selection = lang_cp_keys[0] if lang_cp_keys[0] != "(No StringFileInfo Blocks)" else ""
        self.sfi_widgets["lang_combo"].set(current_selection)
        self._populate_sfi_entries_for_lang(current_selection if current_selection else None)


    def _on_sfi_lang_select(self, selected_lang_cp: str): self._populate_sfi_entries_for_lang(selected_lang_cp)
    def _populate_sfi_entries_for_lang(self, lang_cp_hex: Optional[str]):
        tree = self.sfi_widgets["strings_tree"]
        for i in tree.get_children(): tree.delete(i)
        if not lang_cp_hex: return
        table_info = next((st for st in self.string_tables_copy if st.lang_codepage_hex == lang_cp_hex), None)
        if table_info:
            for idx, entry in enumerate(table_info.entries): tree.insert("", "end", iid=str(idx), values=(entry.key, entry.value))

    def _get_current_sfi_table(self) -> Optional[VersionStringTableInfo]:
        if not self.string_tables_copy or self.sfi_widgets["lang_combo"].get() == "(No StringFileInfo Blocks)": return None
        return next((st for st in self.string_tables_copy if st.lang_codepage_hex == self.sfi_widgets["lang_combo"].get()), None)

    def _on_add_sfi_block(self):
        lang_cp = simpledialog.askstring("Add StringFileInfo Block", "Enter Lang/Codepage (e.g., 040904E4):", parent=self)
        if lang_cp and re.fullmatch(r"[0-9a-fA-F]{8}", lang_cp.strip()):
            lang_cp = lang_cp.strip().upper()
            if any(st.lang_codepage_hex.upper() == lang_cp for st in self.string_tables_copy):
                messagebox.showerror("Error", f"Block {lang_cp} already exists.", parent=self); return
            new_block = VersionStringTableInfo(lang_codepage_hex=lang_cp, entries=[VersionStringEntry("ExampleKey", "ExampleValue")])
            self.string_tables_copy.append(new_block)
            self._populate_sfi_blocks_combobox()
            self.sfi_widgets["lang_combo"].set(lang_cp) # Select the new block
            if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
        elif lang_cp: messagebox.showerror("Error", "Invalid Lang/Codepage format. Must be 8 hex digits.", parent=self)

    def _on_delete_sfi_block(self):
        current_table = self._get_current_sfi_table()
        if not current_table: messagebox.showinfo("Delete Block", "No block selected.", parent=self); return
        if messagebox.askyesno("Confirm Delete", f"Delete StringFileInfo block '{current_table.lang_codepage_hex}' and all its strings?", parent=self):
            self.string_tables_copy.remove(current_table)
            self._populate_sfi_blocks_combobox() # This will refresh and select first or "(No Blocks)"
            if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)

    def _on_add_sfi_entry(self):
        current_table = self._get_current_sfi_table()
        if not current_table: messagebox.showinfo("Add String", "No StringFileInfo block selected.", parent=self); return
        key = simpledialog.askstring("Add String", "Enter Key (e.g., CompanyName):", parent=self)
        if not key or not key.strip(): return
        value = simpledialog.askstring("Add String", f"Enter Value for '{key.strip()}':", parent=self)
        if value is None: return
        current_table.entries.append(VersionStringEntry(key.strip(), value))
        self._populate_sfi_entries_for_lang(current_table.lang_codepage_hex)
        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)

    def _on_edit_sfi_entry(self):
        current_table = self._get_current_sfi_table(); tree = self.sfi_widgets["strings_tree"]
        selected = tree.selection()
        if not current_table or not selected: messagebox.showinfo("Edit String", "No string selected.", parent=self); return
        item_idx = int(tree.index(selected[0]))
        entry = current_table.entries[item_idx]
        new_key = simpledialog.askstring("Edit String", "Enter Key:", initialvalue=entry.key, parent=self)
        if not new_key or not new_key.strip(): return
        new_value = simpledialog.askstring("Edit String", f"Enter Value for '{new_key.strip()}':", initialvalue=entry.value, parent=self)
        if new_value is None: return
        entry.key = new_key.strip(); entry.value = new_value
        self._populate_sfi_entries_for_lang(current_table.lang_codepage_hex)
        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)

    def _on_delete_sfi_entry(self):
        current_table = self._get_current_sfi_table(); tree = self.sfi_widgets["strings_tree"]
        selected = tree.selection()
        if not current_table or not selected: messagebox.showinfo("Delete String", "No string selected.", parent=self); return
        if messagebox.askyesno("Confirm Delete", "Delete selected string(s)?", parent=self):
            indices_to_delete = sorted([int(tree.index(iid)) for iid in selected], reverse=True)
            for idx in indices_to_delete: del current_table.entries[idx]
            self._populate_sfi_entries_for_lang(current_table.lang_codepage_hex)
            if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)

    def _populate_var_info_tab(self):
        tree = self.vfi_widgets["vars_tree"]
        for i in tree.get_children(): tree.delete(i)
        trans_entry = next((vi for vi in self.var_info_copy if vi.key.upper() == "TRANSLATION"), None)
        if trans_entry:
            for i in range(0, len(trans_entry.values), 2):
                if i+1 < len(trans_entry.values):
                    lang_id, cp_id = trans_entry.values[i], trans_entry.values[i+1]
                    tree.insert("", "end", iid=str(i//2), values=(f"0x{lang_id:04X}", f"0x{cp_id:04X}"))

    def _on_add_translation_entry(self):
        trans_entry = next((vi for vi in self.var_info_copy if vi.key.upper() == "TRANSLATION"), None)
        if not trans_entry:
            trans_entry = VersionVarEntry("Translation", [])
            self.var_info_copy.append(trans_entry)
        lang_str = simpledialog.askstring("Add Translation", "Language ID (e.g., 1033 or 0x409):", parent=self)
        if not lang_str: return
        cp_str = simpledialog.askstring("Add Translation", "Codepage ID (e.g., 1200 or 0x4E4):", parent=self)
        if not cp_str: return
        try:
            lang_id = int(lang_str,0); cp_id = int(cp_str,0)
            if not (0 <= lang_id <= 0xFFFF and 0 <= cp_id <= 0xFFFF): raise ValueError("Out of WORD range")
        except ValueError: messagebox.showerror("Error", "Invalid Language or Codepage ID.", parent=self); return
        trans_entry.values.extend([lang_id, cp_id])
        self._populate_var_info_tab()
        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)

    def _on_delete_translation_entry(self):
        tree = self.vfi_widgets["vars_tree"]; selected = tree.selection()
        if not selected: messagebox.showinfo("Delete Translation", "No translation selected.", parent=self); return
        trans_entry = next((vi for vi in self.var_info_copy if vi.key.upper() == "TRANSLATION"), None)
        if not trans_entry: return
        if messagebox.askyesno("Confirm Delete", "Delete selected translation(s)?", parent=self):
            indices_to_delete = sorted([int(iid) for iid in selected], reverse=True)
            for pair_idx in indices_to_delete:
                actual_idx_in_list = pair_idx * 2
                if 0 <= actual_idx_in_list < len(trans_entry.values) -1 :
                    del trans_entry.values[actual_idx_in_list : actual_idx_in_list+2]
            self._populate_var_info_tab()
            if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)

    def apply_all_changes_to_resource(self):
        self._apply_fixed_info_changes()
        self.resource.fixed_info = copy.deepcopy(self.fixed_info_copy)
        self.resource.string_tables = copy.deepcopy(self.string_tables_copy)
        self.resource.var_info = copy.deepcopy(self.var_info_copy)
        self.resource.dirty = True
        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
        messagebox.showinfo("Changes Applied", "All Version Info changes applied. Save the main file to persist.", parent=self)

if __name__ == '__main__':
    pass

