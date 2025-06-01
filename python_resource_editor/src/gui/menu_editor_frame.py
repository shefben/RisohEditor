import customtkinter
import tkinter.ttk as ttk
from tkinter import simpledialog, messagebox
from typing import List, Dict, Callable, Optional, Union, Tuple
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

        self.grid_columnconfigure(0, weight=1) # Left pane (Tree + Actions)
        self.grid_columnconfigure(1, weight=1) # Right pane (Properties)
        self.grid_rowconfigure(0, weight=0) # Interactive Menu Bar
        self.grid_rowconfigure(1, weight=1) # Tree and Properties
        self.grid_rowconfigure(2, weight=0) # Action buttons
        self.grid_rowconfigure(3, weight=0) # Apply All button

        # --- Interactive Menu Bar (Top, Spanning Both Columns) ---
        self.interactive_menu_bar_frame = customtkinter.CTkFrame(self, height=30, fg_color="transparent")
        self.interactive_menu_bar_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=(5,0), sticky="new")
        # Menubuttons will be added here by render_interactive_menu_bar

        # --- Menu Tree (Left Pane, Below Interactive Menu Bar) ---
        self.tree_frame = customtkinter.CTkFrame(self)
        self.tree_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
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


        # --- Properties Pane (Right Pane, Below Interactive Menu Bar) ---
        self.props_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.props_frame.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")
        # Properties will be populated on selection

        # --- Action Buttons (Below Tree) ---
        action_button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        action_button_frame.grid(row=2, column=0, pady=5, sticky="ew") # Adjusted row

        customtkinter.CTkButton(action_button_frame, text="Add Item", command=self.on_add_item).pack(side="left", padx=2)
        customtkinter.CTkButton(action_button_frame, text="Add Popup", command=self.on_add_popup).pack(side="left", padx=2)
        customtkinter.CTkButton(action_button_frame, text="Add Separator", command=self.on_add_separator).pack(side="left", padx=2)
        customtkinter.CTkButton(action_button_frame, text="Delete", command=self.on_delete_selected).pack(side="left", padx=2)
        customtkinter.CTkButton(action_button_frame, text="Move Up", command=lambda: self.on_move_item(-1)).pack(side="left", padx=2)
        customtkinter.CTkButton(action_button_frame, text="Move Down", command=lambda: self.on_move_item(1)).pack(side="left", padx=2)
        # Removed "Show Menu Preview" button as it's now persistent

        # --- Apply All Button (Spanning bottom) ---
        self.apply_all_button = customtkinter.CTkButton(self, text="Apply All Changes to Resource", command=self.apply_all_changes_to_resource)
        self.apply_all_button.grid(row=3, column=0, columnspan=2, pady=10, sticky="s") # Adjusted row

        self.selected_tree_item_id: Optional[str] = None
        self.selected_menu_entry: Optional[MenuItemEntry] = None
        self.prop_widgets: Dict[str, customtkinter.CTkBaseClass] = {}

        self.populate_menu_tree() # Populates tree
        self.render_interactive_menu_bar() # Renders the new menu bar
        self._clear_properties_pane() # Initially empty/disabled

    def _find_item_by_path(self, path: str) -> Optional[MenuItemEntry]:
        """Finds a MenuItemEntry using a path of indices (e.g., "0.1.2")."""
        indices = [int(i) for i in path.split('.')]
        current_list = self.menu_items
        found_item: Optional[MenuItemEntry] = None
        for index in indices:
            if index < len(current_list):
                found_item = current_list[index]
                current_list = found_item.children
            else:
                return None # Path is invalid
        return found_item

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
        # Ensure string flags are up-to-date before populating UI from them
        item.update_string_flags_from_numeric()

        # --- Populate Properties Pane using .grid ---
        self.props_frame.grid_columnconfigure(0, weight=0) # Labels
        self.props_frame.grid_columnconfigure(1, weight=1) # Inputs
        current_row = 0

        # Item Type
        customtkinter.CTkLabel(self.props_frame, text="Type:").grid(row=current_row, column=0, sticky="w", padx=5, pady=2)
        customtkinter.CTkLabel(self.props_frame, text=item.item_type_str).grid(row=current_row, column=1, sticky="w", padx=5, pady=2)
        current_row += 1

        # Caption/Text
        customtkinter.CTkLabel(self.props_frame, text="Caption:").grid(row=current_row, column=0, sticky="w", padx=5, pady=2)
        caption_entry = customtkinter.CTkEntry(self.props_frame)
        caption_entry.insert(0, item.text)
        caption_entry.grid(row=current_row, column=1, sticky="ew", padx=5, pady=(0,5))
        self.prop_widgets['text'] = caption_entry
        current_row += 1

        if item.item_type_str != "SEPARATOR":
            # ID/Name
            customtkinter.CTkLabel(self.props_frame, text="ID/Symbolic Name:").grid(row=current_row, column=0, sticky="w", padx=5, pady=2)
            id_entry = customtkinter.CTkEntry(self.props_frame)
            id_entry.insert(0, item.get_id_display()) # get_id_display handles name_val or id_val
            id_entry.grid(row=current_row, column=1, sticky="ew", padx=5, pady=(0,5))
            self.prop_widgets['id'] = id_entry
            current_row += 1

        # Flags (Checkboxes) - for MENUITEM and POPUP
        if item.item_type_str != "SEPARATOR":
            customtkinter.CTkLabel(self.props_frame, text="Flags:").grid(row=current_row, column=0, sticky="nw", padx=5, pady=2)
            flags_frame = customtkinter.CTkFrame(self.props_frame, fg_color="transparent")
            flags_frame.grid(row=current_row, column=1, sticky="ew", padx=5, pady=(0,5))
            flags_frame.grid_columnconfigure((0,1), weight=1) # Allow checkboxes to spread
            current_row += 1

            # Use item.get_flags_display_list() to determine checkbox states
            current_item_flags_as_strings = item.get_flags_display_list()

            # Define which flags are relevant for checkboxes
            # This list can be expanded or made context-aware (std vs ex)
            # For now, common ones. Note: POPUP/SEPARATOR are item types, not flags here.
            # STRING is usually implicit.
            checkbox_flags = ["GRAYED", "INACTIVE", "CHECKED", "HELP", "MENUBARBREAK", "MENUBREAK", "OWNERDRAW", "RADIO", "DEFAULT", "HILITE", "BITMAP"]
            self.prop_widgets['flags'] = {} # Store checkbox widgets
            cb_row, cb_col = 0, 0
            for flag_name in checkbox_flags:
                # Only show relevant flags, e.g., MENUEX specific flags for MENUEX items
                if not item.is_ex and flag_name in ["DEFAULT", "HILITE", "RADIO", "BITMAP"]: # MFS/MFT specific
                    continue
                if item.is_ex and flag_name in ["HELP"]: # HELP is not a typical MFS/MFT flag string
                     continue

                cb = customtkinter.CTkCheckBox(flags_frame, text=flag_name)
                if flag_name in current_item_flags_as_strings:
                    cb.select()
                cb.grid(row=cb_row, column=cb_col, sticky="w", padx=2, pady=2)
                self.prop_widgets['flags'][flag_name] = cb
                cb_col += 1
                if cb_col > 1: cb_col = 0; cb_row +=1

        # For MENUEX specific fields (numeric display/edit)
        if item.is_ex:
            customtkinter.CTkLabel(self.props_frame, text="Type Numeric (MFT_):").grid(row=current_row, column=0, sticky="w", padx=5, pady=2)
            type_num_entry = customtkinter.CTkEntry(self.props_frame)
            type_num_entry.insert(0, f"0x{item.type_numeric:08X}")
            type_num_entry.grid(row=current_row, column=1, sticky="ew", padx=5, pady=(0,5))
            self.prop_widgets['type_numeric_hex'] = type_num_entry
            current_row += 1

            customtkinter.CTkLabel(self.props_frame, text="State Numeric (MFS_):").grid(row=current_row, column=0, sticky="w", padx=5, pady=2)
            state_num_entry = customtkinter.CTkEntry(self.props_frame)
            state_num_entry.insert(0, f"0x{item.state_numeric:08X}")
            state_num_entry.grid(row=current_row, column=1, sticky="ew", padx=5, pady=(0,5))
            self.prop_widgets['state_numeric_hex'] = state_num_entry
            current_row += 1

            customtkinter.CTkLabel(self.props_frame, text="Help ID:").grid(row=current_row, column=0, sticky="w", padx=5, pady=2)
            help_id_entry = customtkinter.CTkEntry(self.props_frame)
            help_id_entry.insert(0, str(item.help_id or 0))
            help_id_entry.grid(row=current_row, column=1, sticky="ew", padx=5, pady=(0,5))
            self.prop_widgets['help_id'] = help_id_entry
            current_row += 1
        elif item.item_type_str != "SEPARATOR": # Standard Menu, show combined flags_numeric
            customtkinter.CTkLabel(self.props_frame, text="Flags Numeric (MF_):").grid(row=current_row, column=0, sticky="w", padx=5, pady=2)
            flags_num_entry = customtkinter.CTkEntry(self.props_frame)
            # For standard menus, all flags are in type_numeric as per MenuItemEntry internal logic
            flags_num_entry.insert(0, f"0x{item.type_numeric:04X}")
            flags_num_entry.grid(row=current_row, column=1, sticky="ew", padx=5, pady=(0,5))
            self.prop_widgets['flags_numeric_hex'] = flags_num_entry
            current_row += 1

        apply_props_button = customtkinter.CTkButton(self.props_frame, text="Apply Item Changes", command=self.apply_item_changes)
        apply_props_button.grid(row=current_row, column=0, columnspan=2, pady=10)
        current_row +=1

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
        self.render_interactive_menu_bar()
        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)

    def on_add_popup(self):
        target_list, _ = self._get_selected_parent_and_target_list()
        new_popup = MenuItemEntry(item_type="POPUP", text="New Popup", children=[], is_ex=self.is_ex)
        target_list.append(new_popup)
        self.populate_menu_tree()
        self.render_interactive_menu_bar()
        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)

    def on_add_separator(self):
        target_list, _ = self._get_selected_parent_and_target_list()
        new_sep = MenuItemEntry(item_type="SEPARATOR", text="SEPARATOR", is_ex=self.is_ex) # ID is irrelevant
        target_list.append(new_sep)
        self.populate_menu_tree()
        self.render_interactive_menu_bar()
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
                self.render_interactive_menu_bar()
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
            self.render_interactive_menu_bar()
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

        if item.item_type_str != "SEPARATOR": # Use item_type_str
            id_str = self.prop_widgets['id'].get().strip()
            if id_str.isdigit() or (id_str.startswith("0x")):
                try: item.id_val = int(id_str,0); item.name_val = None
                except ValueError: item.id_val = id_str; item.name_val = id_str
            else:
                item.id_val = id_str; item.name_val = id_str

        # Update item.flags_list based on checkboxes
        # This will be the source of truth for string flags.
        item.flags_list.clear()
        if 'flags' in self.prop_widgets: # Check if flags frame was populated
            for flag_name_key, cb_widget in self.prop_widgets['flags'].items():
                if cb_widget.get() == 1:
                    item.flags_list.append(flag_name_key) # item.flags_list is actually item.flags in MenuItemEntry

        # After updating flags_list from checkboxes, update numeric representations
        item.update_numeric_flags_from_strings()

        # Update numeric fields if they were edited by user, then update string flags from them
        # This ensures consistency if user edits hex fields.
        user_edited_numeric = False
        if item.is_ex:
            try:
                if 'type_numeric_hex' in self.prop_widgets:
                    new_type_numeric = int(self.prop_widgets['type_numeric_hex'].get(), 0)
                    if new_type_numeric != item.type_numeric: item.type_numeric = new_type_numeric; user_edited_numeric = True
                if 'state_numeric_hex' in self.prop_widgets:
                    new_state_numeric = int(self.prop_widgets['state_numeric_hex'].get(), 0)
                    if new_state_numeric != item.state_numeric: item.state_numeric = new_state_numeric; user_edited_numeric = True
                if 'help_id' in self.prop_widgets:
                    help_id_str = self.prop_widgets['help_id'].get().strip()
                    new_help_id = int(help_id_str) if help_id_str.isdigit() else (item.help_id or 0)
                    if new_help_id != item.help_id: item.help_id = new_help_id # No need to set user_edited_numeric for help_id alone for flag sync
            except ValueError:
                messagebox.showerror("Error", "MENUEX Numeric Type/State/Help ID must be valid hex/decimal numbers.", parent=self)
                return
        elif item.item_type_str != "SEPARATOR": # Standard menu
            try:
                if 'flags_numeric_hex' in self.prop_widgets:
                     # For standard menus, flags_numeric effectively maps to item.type_numeric
                    new_flags_numeric = int(self.prop_widgets['flags_numeric_hex'].get(), 0)
                    if new_flags_numeric != item.type_numeric: item.type_numeric = new_flags_numeric; user_edited_numeric = True
            except ValueError:
                messagebox.showerror("Error", "Standard Flags Numeric must be a valid hex/decimal number.", parent=self)
                return

        if user_edited_numeric: # If numeric hex fields were changed by user
            item.update_string_flags_from_numeric() # Update string flags list from these new numeric values
            # This will make get_flags_display_list (used by tree) and checkbox population (if pane is re-rendered) consistent.
            # Also, call update_numeric_flags_from_strings again to ensure item_type (POPUP/SEPARATOR) is consistent if numeric change implied it.
            item.update_numeric_flags_from_strings()


        self.populate_menu_tree()
        self.render_interactive_menu_bar() # Update menu bar after changes
        if self.selected_tree_item_id and self.menu_tree.exists(self.selected_tree_item_id):
             self.menu_tree.selection_set(self.selected_tree_item_id)
             self.menu_tree.focus(self.selected_tree_item_id)

        if self.app_callbacks.get('set_dirty_callback'): self.app_callbacks['set_dirty_callback'](True)
        # messagebox.showinfo("Item Updated", "Changes applied to the selected menu item locally.", parent=self)


    def apply_all_changes_to_resource(self):
        self.menu_resource.items = copy.deepcopy(self.menu_items) # Apply all local changes back
        self.menu_resource.is_ex = self.is_ex # Ensure is_ex status is also copied
        self.menu_resource.dirty = True
        if self.app_callbacks.get('set_dirty_callback'):
            self.app_callbacks['set_dirty_callback'](True)
        messagebox.showinfo("Changes Applied", "All menu changes applied to in-memory resource. Save file to persist.", parent=self)

    def _on_interactive_menu_item_click(self, item_path: str):
        """Handles clicks on items from the interactive menu bar."""
        # print(f"Interactive menu item clicked. Path: {item_path}")
        item_entry = self._find_item_by_path(item_path)
        if item_entry:
            # Find the corresponding tree item iid
            # This is a bit inefficient, a reverse map from MenuItemEntry to iid could be useful
            # or pass item_entry directly to on_menu_tree_select if we adapt it.
            iid_to_select = None
            for iid, entry_in_map in self._get_all_tree_iids_and_items().items():
                if entry_in_map is item_entry:
                    iid_to_select = iid
                    break

            if iid_to_select and self.menu_tree.exists(iid_to_select):
                self.menu_tree.focus(iid_to_select)
                self.menu_tree.selection_set(iid_to_select)
                # self.on_menu_tree_select() # This will be triggered by selection_set
            else: # Fallback if tree selection fails, directly populate props
                self.selected_menu_entry = item_entry
                self.selected_tree_item_id = None # Clear tree selection if direct
                self._clear_properties_pane()
                # Code from on_menu_tree_select to populate props pane:
                item = self.selected_menu_entry
                item.update_string_flags_from_numeric()
                # ... (rest of _populate_props_pane logic, simplified for now) ...
                customtkinter.CTkLabel(self.props_frame, text=f"Selected (Menu Bar): {item.text}").pack()

                # For now, just a simple message. A full property pane update like in on_menu_tree_select
                # would be needed for full interactivity via menu bar clicks.
                messagebox.showinfo("Menu Item Clicked (Interactive)",
                                    f"Text: '{item_entry.text}'\n"
                                    f"ID: {item_entry.get_id_display()}\n"
                                    f"Path: {item_path}",
                                    parent=self)
        else:
            print(f"Warning: Could not find menu item for path {item_path}")

    def _get_all_tree_iids_and_items(self, parent_node_id:str = "") -> Dict[str, MenuItemEntry]:
        """ Helper to get a flat dict of all tree iids to menu items. """
        # This is a temporary helper, ideally we'd have a direct mapping or better way to find iid.
        # For now, this is not used in the primary path.
        # The goal is to select in tree, which calls on_menu_tree_select, which populates props.
        # So, _map_iid_to_menu_item is primary for tree->item, and _find_item_by_path for menu->item.
        # The selection logic in _on_interactive_menu_item_click needs to find the iid for an item.
        # This might require iterating through self.menu_tree.get_children recursively.
        # Or, if tree iids are stable (str(id(item_obj))), we can build this map once.
        # For now, the selection in tree is the most robust way to trigger property pane update.
        # This function is more of a placeholder for a more direct iid lookup if needed.
        all_items = {}
        children = self.menu_tree.get_children(parent_node_id)
        for child_iid in children:
            item = self._map_iid_to_menu_item(child_iid) # Assuming iid is str(id(item))
            if item: all_items[child_iid] = item
            all_items.update(self._get_all_tree_iids_and_items(child_iid))
        return all_items


    def render_interactive_menu_bar(self):
        """Clears and rebuilds the interactive menu bar using tkinter.Menubuttons."""
        for widget in self.interactive_menu_bar_frame.winfo_children():
            widget.destroy()

        bg_color = self._apply_appearance_mode(customtkinter.ThemeManager.theme["CTkFrame"]["fg_color"])
        fg_color = self._apply_appearance_mode(customtkinter.ThemeManager.theme["CTkButton"]["text_color"])
        active_bg = self._apply_appearance_mode(customtkinter.ThemeManager.theme["CTkButton"]["hover_color"])
        active_fg = self._apply_appearance_mode(customtkinter.ThemeManager.theme["CTkButton"]["text_color"])


        def _populate_menu_recursive(tk_menu_parent, item_list: List[MenuItemEntry], current_path: str):
            for idx, item_entry in enumerate(item_list):
                item_local_path = f"{current_path}.{idx}" if current_path else str(idx)
                flags_as_strings = item_entry.get_flags_display_list()
                item_state = "disabled" if ("GRAYED" in flags_as_strings or "INACTIVE" in flags_as_strings) else "normal"

                if item_entry.item_type == "SEPARATOR":
                    tk_menu_parent.add_separator()
                elif item_entry.item_type == "POPUP":
                    submenu = tkinter.Menu(tk_menu_parent, tearoff=0)
                    _populate_menu_recursive(submenu, item_entry.children, item_local_path)
                    tk_menu_parent.add_cascade(label=item_entry.text, menu=submenu, state=item_state)
                else: # Regular MENUITEM
                    is_checked = "CHECKED" in flags_as_strings # Basic check state
                    # For tkinter.Menu, checkbuttons need a variable. We simulate state for preview.
                    # If we wanted actual check behavior, we'd need to store tkinter.BooleanVar() per item.
                    if is_checked: # Visually indicate check, but it's a command item
                         # Simple way: prefix label. Or use add_checkbutton and manage var (more complex for dynamic).
                         # tk_menu_parent.add_checkbutton(label=item_entry.text, onvalue=1, offvalue=0, variable=...)
                        tk_menu_parent.add_command(label=f"{item_entry.text} (\u2713)" if is_checked else item_entry.text,
                                                   command=lambda p=item_local_path: self._on_interactive_menu_item_click(p),
                                                   state=item_state)
                    else:
                        tk_menu_parent.add_command(label=item_entry.text,
                                                   command=lambda p=item_local_path: self._on_interactive_menu_item_click(p),
                                                   state=item_state)

        if not self.menu_items:
            # Perhaps show a disabled "Empty Menu" label in the bar frame
            # empty_label = customtkinter.CTkLabel(self.interactive_menu_bar_frame, text="(No menu items to display)")
            # empty_label.pack(side="left", padx=5, pady=5)
            return

        # Create Menubuttons for top-level POPUP items, or a single Menubutton for a flat list
        if any(item.item_type == "POPUP" for item in self.menu_items): # If top level has popups, treat as menubar
            for top_level_idx, top_item in enumerate(self.menu_items):
                path_str = str(top_level_idx)
                if top_item.item_type == "POPUP":
                    mb = tkinter.Menubutton(self.interactive_menu_bar_frame, text=top_item.text,
                                            relief="raised", borderwidth=1,
                                            bg=bg_color, fg=fg_color,
                                            activebackground=active_bg, activeforeground=active_fg)
                    mb.menu = tkinter.Menu(mb, tearoff=0, bg=bg_color, fg=fg_color,
                                           activebackground=active_bg, activeforeground=active_fg)
                    mb["menu"] = mb.menu
                    _populate_menu_recursive(mb.menu, top_item.children, path_str)
                    mb.pack(side="left", padx=1, pady=1)
                else: # Top-level item that is not a POPUP (e.g. a single command)
                    # This is unusual for a main menubar but possible for simple menus
                    btn = tkinter.Button(self.interactive_menu_bar_frame, text=top_item.text,
                                         command=lambda p=path_str: self._on_interactive_menu_item_click(p),
                                         relief="raised", borderwidth=1,
                                         bg=bg_color, fg=fg_color,
                                         activebackground=active_bg, activeforeground=active_fg)
                    if "GRAYED" in top_item.get_flags_display_list() or "INACTIVE" in top_item.get_flags_display_list():
                        btn.config(state="disabled")
                    btn.pack(side="left", padx=1, pady=1)
        elif self.menu_items: # A flat list of items, treat as a single popup menu under a default name
            default_menu_name = self.menu_resource.identifier.name_id_to_str() or "Menu"
            mb = tkinter.Menubutton(self.interactive_menu_bar_frame, text=default_menu_name,
                                    relief="raised", borderwidth=1,
                                    bg=bg_color, fg=fg_color,
                                    activebackground=active_bg, activeforeground=active_fg)
            mb.menu = tkinter.Menu(mb, tearoff=0, bg=bg_color, fg=fg_color,
                                   activebackground=active_bg, activeforeground=active_fg)
            mb["menu"] = mb.menu
            _populate_menu_recursive(mb.menu, self.menu_items, "") # Start path from empty for direct children
            mb.pack(side="left", padx=1, pady=1)
        # If self.menu_items is empty, nothing is packed.

    # Remove the Toplevel based preview as we now have an embedded one
    # def show_menu_preview(self): ... (old method to be removed or commented out)


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


