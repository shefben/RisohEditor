import customtkinter
import tkinter.ttk as ttk
from tkinter import simpledialog, messagebox
from typing import List, Dict, Callable, Optional, Union
import copy

from ..core.menu_parser_util import MenuItemEntry
from ..core.resource_types import MenuResource # For type hinting

class MenuEditorFrame(customtkinter.CTkFrame):
    def __init__(self, master, menu_resource: MenuResource, app_callbacks: Dict[str, Callable]):
        super().__init__(master)
        self.menu_resource = menu_resource
        self.app_callbacks = app_callbacks

        # Deep copy for local editing to avoid modifying original until "Apply"
        self.menu_items: List[MenuItemEntry] = copy.deepcopy(menu_resource.items)
        self.is_ex = menu_resource.is_ex # Store if it's a MENUEX

        self.grid_columnconfigure(0, weight=1) # Tree
        self.grid_columnconfigure(1, weight=1) # Properties
        self.grid_rowconfigure(0, weight=1) # Tree and Properties
        self.grid_rowconfigure(1, weight=0) # Action buttons
        self.grid_rowconfigure(2, weight=0) # Apply All button

        # --- Menu Tree (Left Pane) ---
        self.tree_frame = customtkinter.CTkFrame(self)
        self.tree_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.tree_frame.grid_rowconfigure(0, weight=1)
        self.tree_frame.grid_columnconfigure(0, weight=1)

        self.menu_tree = ttk.Treeview(self.tree_frame, columns=("ID", "Flags"), show="tree headings")
        self.menu_tree.heading("#0", text="Caption / Item Text")
        self.menu_tree.heading("ID", text="ID/Name")
        self.menu_tree.heading("Flags", text="Flags")
        self.menu_tree.column("#0", width=200, stretch=True)
        self.menu_tree.column("ID", width=100, anchor="w")
        self.menu_tree.column("Flags", width=150, anchor="w")
        self.menu_tree.grid(row=0, column=0, sticky="nsew", padx=(0,0), pady=(0,0))
        self.menu_tree.bind("<<TreeviewSelect>>", self.on_menu_tree_select)

        tree_scroll_y = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.menu_tree.yview)
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        self.menu_tree.configure(yscrollcommand=tree_scroll_y.set)


        # --- Properties Pane (Right Pane) ---
        self.props_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.props_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        # Properties will be populated on selection

        # --- Action Buttons (Below Tree) ---
        action_button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        action_button_frame.grid(row=1, column=0, pady=5, sticky="ew")
        # action_button_frame.grid_columnconfigure((0,1,2,3,4), weight=1) # Distribute buttons

        customtkinter.CTkButton(action_button_frame, text="Add Item", command=self.on_add_item).pack(side="left", padx=2)
        customtkinter.CTkButton(action_button_frame, text="Add Popup", command=self.on_add_popup).pack(side="left", padx=2)
        customtkinter.CTkButton(action_button_frame, text="Add Separator", command=self.on_add_separator).pack(side="left", padx=2)
        customtkinter.CTkButton(action_button_frame, text="Delete", command=self.on_delete_selected).pack(side="left", padx=2)
        customtkinter.CTkButton(action_button_frame, text="Move Up", command=lambda: self.on_move_item(-1)).pack(side="left", padx=2)
        customtkinter.CTkButton(action_button_frame, text="Move Down", command=lambda: self.on_move_item(1)).pack(side="left", padx=2)

        # --- Apply All Button (Spanning bottom) ---
        self.apply_all_button = customtkinter.CTkButton(self, text="Apply All Changes to Resource", command=self.apply_all_changes_to_resource)
        self.apply_all_button.grid(row=2, column=0, columnspan=2, pady=10, sticky="s")

        self.selected_tree_item_id: Optional[str] = None
        self.selected_menu_entry: Optional[MenuItemEntry] = None
        self.prop_widgets: Dict[str, customtkinter.CTkBaseClass] = {}

        self.populate_menu_tree()
        self._clear_properties_pane() # Initially empty/disabled

    def _map_iid_to_menu_item(self, iid: str, items_list: Optional[List[MenuItemEntry]] = None) -> Optional[MenuItemEntry]:
        """Finds a MenuItemEntry by its treeview iid."""
        if items_list is None: items_list = self.menu_items

        for item in items_list:
            if id(item) == int(iid): # Assuming iid is str(id(item))
                return item
            if item.children:
                found = self._map_iid_to_menu_item(iid, item.children)
                if found: return found
        return None

    def _get_parent_and_index(self, target_item: MenuItemEntry, current_list: Optional[List[MenuItemEntry]] = None, parent_list: Optional[List[MenuItemEntry]] = None) -> Tuple[Optional[List[MenuItemEntry]], int]:
        """Finds the parent list and index of a target_item."""
        if current_list is None: current_list = self.menu_items

        for i, item in enumerate(current_list):
            if item is target_item:
                return (parent_list if parent_list is not None else self.menu_items), i
            if item.children:
                p_list, idx = self._get_parent_and_index(target_item, item.children, item.children)
                if idx != -1: return p_list, idx
        return None, -1


    def populate_menu_tree(self, parent_tree_id: str = "", current_menu_list: Optional[List[MenuItemEntry]] = None):
        if current_menu_list is None: # Initial call
            # Clear tree before populating
            for i in self.menu_tree.get_children():
                self.menu_tree.delete(i)
            current_menu_list = self.menu_items

        for item_obj in current_menu_list:
            item_iid = str(id(item_obj)) # Use object's memory ID as unique tree IID
            text = item_obj.text
            if item_obj.item_type == "SEPARATOR": text = "---- SEPARATOR ----"

            id_display = item_obj.get_id_display()
            flags_display = ", ".join(item_obj.flags)

            node = self.menu_tree.insert(parent_tree_id, "end", iid=item_iid, text=text,
                                         values=(id_display, flags_display))
            if item_obj.children:
                self.populate_menu_tree(node, item_obj.children)
                self.menu_tree.item(node, open=True) # Optionally open popups by default

    def _clear_properties_pane(self):
        for widget in self.props_frame.winfo_children():
            widget.destroy()
        self.prop_widgets.clear()

        customtkinter.CTkLabel(self.props_frame, text="Select an item to edit its properties.").pack(padx=10, pady=10)
        self.selected_menu_entry = None # Clear selected entry

    def on_menu_tree_select(self, event=None):
        selected_items = self.menu_tree.selection()
        if not selected_items:
            self._clear_properties_pane()
            self.selected_tree_item_id = None
            return

        self.selected_tree_item_id = selected_items[0]
        self.selected_menu_entry = self._map_iid_to_menu_item(self.selected_tree_item_id)

        self._clear_properties_pane()
        if not self.selected_menu_entry: return

        item = self.selected_menu_entry

        # --- Populate Properties Pane ---
        # Item Type (usually not editable directly, rather delete and add new type)
        customtkinter.CTkLabel(self.props_frame, text=f"Type: {item.item_type}").pack(anchor="w", padx=5)

        # Caption/Text
        customtkinter.CTkLabel(self.props_frame, text="Caption:").pack(anchor="w", padx=5)
        caption_entry = customtkinter.CTkEntry(self.props_frame)
        caption_entry.insert(0, item.text)
        caption_entry.pack(fill="x", padx=5, pady=(0,5))
        self.prop_widgets['text'] = caption_entry

        if item.item_type != "SEPARATOR":
            # ID/Name
            customtkinter.CTkLabel(self.props_frame, text="ID/Symbolic Name:").pack(anchor="w", padx=5)
            id_entry = customtkinter.CTkEntry(self.props_frame)
            id_entry.insert(0, item.get_id_display())
            id_entry.pack(fill="x", padx=5, pady=(0,5))
            self.prop_widgets['id'] = id_entry

        # Flags (Checkboxes) - for MENUITEM and POPUP
        if item.item_type != "SEPARATOR":
            customtkinter.CTkLabel(self.props_frame, text="Flags:").pack(anchor="w", padx=5)
            flags_frame = customtkinter.CTkFrame(self.props_frame, fg_color="transparent")
            flags_frame.pack(fill="x", padx=5, pady=(0,5))

            # Common flags, can be extended
            possible_flags = ["GRAYED", "INACTIVE", "CHECKED", "HELP", "MENUBARBREAK", "MENUBREAK"]
            self.prop_widgets['flags'] = {}
            for i, flag_name in enumerate(possible_flags):
                cb = customtkinter.CTkCheckBox(flags_frame, text=flag_name)
                if flag_name in item.flags:
                    cb.select()
                cb.grid(row=i//2, column=i%2, sticky="w", padx=2, pady=2)
                self.prop_widgets['flags'][flag_name] = cb

            # For MENUEX specific fields
        if item.is_ex:
                customtkinter.CTkLabel(self.props_frame, text="Type Numeric (MFT_):").pack(anchor="w", padx=5)
                type_num_entry = customtkinter.CTkEntry(self.props_frame)
                type_num_entry.insert(0, f"0x{item.type_numeric:08X}")
                type_num_entry.pack(fill="x", padx=5, pady=(0,5))
                self.prop_widgets['type_numeric'] = type_num_entry # For hex input

                customtkinter.CTkLabel(self.props_frame, text="State Numeric (MFS_):").pack(anchor="w", padx=5)
                state_num_entry = customtkinter.CTkEntry(self.props_frame)
                state_num_entry.insert(0, f"0x{item.state_numeric:08X}")
                state_num_entry.pack(fill="x", padx=5, pady=(0,5))
                self.prop_widgets['state_numeric'] = state_num_entry # For hex input

                customtkinter.CTkLabel(self.props_frame, text="Help ID:").pack(anchor="w", padx=5)
            help_id_entry = customtkinter.CTkEntry(self.props_frame)
                help_id_entry.insert(0, str(item.help_id or 0)) # Default to 0 if None
            help_id_entry.pack(fill="x", padx=5, pady=(0,5))
            self.prop_widgets['help_id'] = help_id_entry
            else: # Standard Menu, show combined flags_numeric
                customtkinter.CTkLabel(self.props_frame, text="Flags Numeric (MF_):").pack(anchor="w", padx=5)
                flags_num_entry = customtkinter.CTkEntry(self.props_frame)
                flags_num_entry.insert(0, f"0x{item.flags_numeric:04X}")
                flags_num_entry.pack(fill="x", padx=5, pady=(0,5))
                self.prop_widgets['flags_numeric'] = flags_num_entry


        apply_props_button = customtkinter.CTkButton(self.props_frame, text="Apply Item Changes", command=self.apply_item_changes)
        apply_props_button.pack(pady=10)


    def _get_selected_parent_and_target_list(self) -> Tuple[Optional[List[MenuItemEntry]], Optional[MenuItemEntry]]:
        """Gets the parent list for adding new items, or the list containing the selected item."""
        if not self.selected_tree_item_id: # No selection, add to root
            return self.menu_items, None

        selected_item_obj = self._map_iid_to_menu_item(self.selected_tree_item_id)
        if not selected_item_obj: return self.menu_items, None # Should not happen if iid is valid

        if selected_item_obj.item_type == "POPUP": # If a POPUP is selected, add to its children
            return selected_item_obj.children, selected_item_obj
        else: # If a MENUITEM or SEPARATOR is selected, add to its parent's list (i.e., as a sibling)
            parent_list, _ = self._get_parent_and_index(selected_item_obj)
            return parent_list if parent_list is not None else self.menu_items, None # Fallback to root if parent not found (should not happen)

    def on_add_item(self):
        target_list, _ = self._get_selected_parent_and_target_list()
        new_item = MenuItemEntry(text="New Item", id_val=0, is_ex=self.is_ex) # Default ID 0
        target_list.append(new_item)
        self.populate_menu_tree()
        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)

    def on_add_popup(self):
        target_list, _ = self._get_selected_parent_and_target_list()
        new_popup = MenuItemEntry(item_type="POPUP", text="New Popup", children=[], is_ex=self.is_ex)
        target_list.append(new_popup)
        self.populate_menu_tree()
        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)

    def on_add_separator(self):
        target_list, _ = self._get_selected_parent_and_target_list()
        new_sep = MenuItemEntry(item_type="SEPARATOR", text="SEPARATOR", is_ex=self.is_ex) # ID is irrelevant
        target_list.append(new_sep)
        self.populate_menu_tree()
        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)

    def on_delete_selected(self):
        if not self.selected_tree_item_id or not self.selected_menu_entry:
            messagebox.showinfo("Delete", "No item selected.", parent=self)
            return

        if messagebox.askyesno("Confirm Delete", f"Delete '{self.selected_menu_entry.text}'?", parent=self):
            parent_list, index = self._get_parent_and_index(self.selected_menu_entry)
            if parent_list is not None and index != -1:
                del parent_list[index]
                self.populate_menu_tree()
                self._clear_properties_pane()
                if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)

    def on_move_item(self, direction: int): # -1 for up, 1 for down
        if not self.selected_tree_item_id or not self.selected_menu_entry: return

        parent_list, index = self._get_parent_and_index(self.selected_menu_entry)
        if parent_list is None or index == -1: return

        new_index = index + direction
        if 0 <= new_index < len(parent_list):
            item_to_move = parent_list.pop(index)
            parent_list.insert(new_index, item_to_move)
            self.populate_menu_tree()
            # Re-select the moved item
            new_iid = str(id(item_to_move))
            if self.menu_tree.exists(new_iid):
                self.menu_tree.selection_set(new_iid)
                self.menu_tree.focus(new_iid)
            if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)


    def apply_item_changes(self):
        if not self.selected_menu_entry or not self.prop_widgets:
            messagebox.showinfo("Apply Changes", "No item selected or properties not loaded.", parent=self)
            return

        item = self.selected_menu_entry
        item.text = self.prop_widgets['text'].get()

        if item.item_type != "SEPARATOR":
            id_str = self.prop_widgets['id'].get().strip()
            if id_str.isdigit() or (id_str.startswith("0x")):
                try: item.id_val = int(id_str,0); item.name_val = None
                except ValueError: item.id_val = id_str; item.name_val = id_str
            else:
                item.id_val = id_str; item.name_val = id_str

        # Update flags based on checkboxes
        new_str_flags = []
        numeric_flags_from_checkboxes = 0
        for flag_name_key, cb_widget in self.prop_widgets['flags_ checkboxes'].items():
            if cb_widget.get() == 1:
                new_str_flags.append(flag_name_key)
                # Find the numeric value for this flag string (this needs the reverse map or iterating FLAG_TO_STR_MAP)
                for num_val, str_val in FLAG_TO_STR_MAP.items(): # This is inefficient, better to have STR_TO_FLAG_MAP
                    if str_val == flag_name_key:
                        numeric_flags_from_checkboxes |= num_val
                        break
        item.flags = new_str_flags

        if item.is_ex:
            try:
                item.type_numeric = int(self.prop_widgets['type_numeric_hex'].get(), 0)
                item.state_numeric = int(self.prop_widgets['state_numeric_hex'].get(), 0)
                help_id_str = self.prop_widgets['help_id'].get().strip()
                item.help_id = int(help_id_str) if help_id_str else 0 # Default to 0 if empty
            except ValueError:
                messagebox.showerror("Error", "Numeric Type/State/Help ID must be valid hex/decimal numbers.", parent=self)
                return
            # Update item.flags from MFT_ and MFS_ numeric fields if needed, or ensure consistency
            # This might be complex if text flags are also directly edited. For now, numeric fields are primary for binary.
        else: # Standard menu
            try:
                item.flags_numeric = int(self.prop_widgets['flags_numeric_hex'].get(), 0)
            except ValueError:
                messagebox.showerror("Error", "Flags Numeric must be a valid hex/decimal number.", parent=self)
                return

        self.populate_menu_tree()
        if self.selected_tree_item_id and self.menu_tree.exists(self.selected_tree_item_id):
             self.menu_tree.selection_set(self.selected_tree_item_id)
             self.menu_tree.focus(self.selected_tree_item_id)

        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
        # messagebox.showinfo("Item Updated", "Changes applied to the selected menu item locally.", parent=self)


    def apply_all_changes_to_resource(self):
        self.menu_resource.items = copy.deepcopy(self.menu_items) # Apply all local changes back
        self.menu_resource.dirty = True
        if self.app_callbacks.get('set_dirty_callback'):
            self.app_callbacks['set_dirty_callback'](True)
        messagebox.showinfo("Changes Applied", "All menu changes applied to in-memory resource. Save file to persist.", parent=self)


if __name__ == '__main__':
    # Test the MenuEditorFrame
    class DummyApp(customtkinter.CTk):
        def __init__(self):
            super().__init__()
            self.title("Menu Editor Test")
            self.geometry("800x600")

            from ..core.resource_base import ResourceIdentifier, RT_MENU
            ident = ResourceIdentifier(type_id=RT_MENU, name_id="IDR_MYMENU", language_id=1033)

            # Create sample menu items for testing
            items = [
                MenuItemEntry(item_type="POPUP", text="&File", children=[
                    MenuItemEntry(text="&New", id_val=101, name_val="ID_FILE_NEW"),
                    MenuItemEntry(item_type="SEPARATOR"),
                    MenuItemEntry(text="E&xit", id_val=102, name_val="ID_FILE_EXIT", flags=["GRAYED"])
                ]),
                MenuItemEntry(text="&Help", id_val=201, name_val="ID_HELP")
            ]
            self.menu_res = MenuResource(identifier=ident, items=items, menu_name_rc="IDR_MYMENU")

            def set_dirty_test(is_dirty):
                print(f"App dirty state set to: {is_dirty}")
                self.title(f"Menu Editor Test {'*' if is_dirty else ''}")

            editor = MenuEditorFrame(self, self.menu_res, app_callbacks={'set_dirty_callback': set_dirty_test})
            editor.pack(expand=True, fill="both")

            self.protocol("WM_DELETE_WINDOW", self.quit_app)

        def quit_app(self):
            print("\nFinal MenuResource items on quit:")
            def print_items_final(items, indent=0):
                for item in items:
                    print("  " * indent + repr(item))
                    if item.children: print_items_final(item.children, indent + 1)
            print_items_final(self.menu_res.items)
            print(f"Is MENUEX: {self.menu_res.is_ex}")
            print(f"RC Name: {self.menu_res.menu_name_rc}")

            self.destroy(); self.quit()

    customtkinter.set_appearance_mode("System")
    customtkinter.set_default_color_theme("blue")
    app = DummyApp()
    app.mainloop()

```
