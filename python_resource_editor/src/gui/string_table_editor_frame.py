import customtkinter
import tkinter.ttk as ttk
from tkinter import simpledialog, messagebox
from typing import List, Dict, Callable, Optional, Union

# Assuming StringTableEntry is in rc_parser_util and StringTableResource in resource_types
from ..core.rc_parser_util import StringTableEntry
from ..core.resource_types import StringTableResource # For type hinting

class StringTableEditorFrame(customtkinter.CTkFrame):
    def __init__(self, master, string_table_resource: StringTableResource, app_callbacks: Dict[str, Callable]):
        super().__init__(master)
        self.resource = string_table_resource
        self.app_callbacks = app_callbacks # e.g., {'set_dirty_callback': self.main_app.set_app_dirty}

        # Make a mutable copy of entries for editing
        self.entries: List[StringTableEntry] = list(string_table_resource.entries)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1) # Treeview/table takes most space
        self.grid_rowconfigure(1, weight=0) # Buttons frame

        # Treeview (acting as a table)
        self.tree = ttk.Treeview(self, columns=("ID", "Name", "Value"), show="headings")
        self.tree.heading("ID", text="ID")
        self.tree.heading("Name", text="Symbolic Name")
        self.tree.heading("Value", text="Value")

        self.tree.column("ID", width=100, anchor="w")
        self.tree.column("Name", width=150, anchor="w")
        self.tree.column("Value", width=300, stretch=True, anchor="w")

        self.tree.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.tree.bind("<Double-1>", self.on_edit_selected_via_double_click) # Double click to edit

        # Scrollbar for Treeview
        tree_scrollbar_y = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        tree_scrollbar_y.grid(row=0, column=1, sticky="ns", pady=5)
        self.tree.configure(yscrollcommand=tree_scrollbar_y.set)

        # Buttons Frame
        button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky="ew")
        button_frame.grid_columnconfigure((0,1,2,3), weight=1) # Distribute buttons

        add_button = customtkinter.CTkButton(button_frame, text="Add Entry", command=self.on_add_entry)
        add_button.grid(row=0, column=0, padx=5)

        edit_button = customtkinter.CTkButton(button_frame, text="Edit Selected", command=self.on_edit_selected)
        edit_button.grid(row=0, column=1, padx=5)

        delete_button = customtkinter.CTkButton(button_frame, text="Delete Selected", command=self.on_delete_selected)
        delete_button.grid(row=0, column=2, padx=5)

        apply_button = customtkinter.CTkButton(button_frame, text="Apply Changes to Resource", command=self.apply_changes_to_resource)
        apply_button.grid(row=0, column=3, padx=5)

        self.populate_table()

    def populate_table(self):
        # Clear existing items
        for i in self.tree.get_children():
            self.tree.delete(i)

        # Add new items from self.entries
        for idx, entry in enumerate(self.entries):
            # Use display_id for the ID column, name_val for Name column
            id_text = str(entry.id_val) if isinstance(entry.id_val, int) else entry.id_val
            name_text = entry.name_val if entry.name_val and entry.name_val != id_text else ""
            self.tree.insert("", "end", iid=str(idx), values=(id_text, name_text, entry.value_str))

    def _get_input_values(self, title: str, current_id: str = "", current_name: str = "", current_value: str = "") -> Optional[tuple]:
        # Using CTkInputDialog might be better if available and suitable for multiple fields,
        # or create a custom CTkToplevel dialog for this.
        # For simplicity, using simpledialog for now.

        # ID Input
        new_id_str = simpledialog.askstring(title, f"Enter String ID (numeric or symbolic):\n(Current: {current_id})", parent=self, initialvalue=current_id)
        if new_id_str is None: return None # Cancelled
        new_id_str = new_id_str.strip()
        if not new_id_str:
            messagebox.showerror("Error", "ID cannot be empty.", parent=self)
            return None

        # Name Input (optional, mainly if ID is numeric)
        # If ID is symbolic, name can be considered same as ID or left empty.
        is_numeric_id = new_id_str.isdigit() or (new_id_str.startswith("0x"))
        initial_name = current_name
        if not initial_name and not is_numeric_id: # If new ID is symbolic, prefill name with it
            initial_name = new_id_str

        new_name_str = simpledialog.askstring(title, f"Enter Symbolic Name (optional, if ID is numeric):\n(Current: {current_name})", parent=self, initialvalue=initial_name)
        if new_name_str is None: new_name_str = "" # Treat cancel as empty string for optional field
        new_name_str = new_name_str.strip()
        if not new_name_str and not is_numeric_id: # If ID is symbolic, name should be symbolic too
             new_name_str = new_id_str # Default symbolic name to ID if empty

        # Value Input
        new_value_str = simpledialog.askstring(title, f"Enter String Value:\n(Current: {current_value})", parent=self, initialvalue=current_value)
        if new_value_str is None: return None # Cancelled
        # new_value_str can be empty

        # Convert ID to int if possible
        final_id_val: Union[int, str]
        if new_id_str.isdigit() or (new_id_str.startswith("0x")):
            try:
                final_id_val = int(new_id_str, 0)
                # If ID is numeric, symbolic name should ideally be different or empty
                if new_name_str == str(final_id_val): new_name_str = ""
            except ValueError: # Should not happen if logic is correct
                final_id_val = new_id_str # Fallback to string if int conversion fails
        else: # Symbolic ID
            final_id_val = new_id_str
            if not new_name_str: new_name_str = final_id_val # Ensure name is set if ID is symbolic

        return final_id_val, new_name_str if new_name_str else None, new_value_str


    def on_add_entry(self):
        result = self._get_input_values("Add String Table Entry")
        if result:
            new_id, new_name, new_value = result
            # Check for duplicate IDs
            for i, entry in enumerate(self.entries):
                if str(entry.id_val) == str(new_id) or (entry.name_val and entry.name_val == str(new_id)):
                    messagebox.showerror("Error", f"An entry with ID '{new_id}' already exists.", parent=self)
                    return

            self.entries.append(StringTableEntry(id_val=new_id, value_str=new_value, name_val=new_name))
            self.populate_table()
            if self.app_callbacks.get('set_dirty_callback'):
                self.app_callbacks['set_dirty_callback'](True)

    def on_edit_selected_via_double_click(self, event):
        self.on_edit_selected()

    def on_edit_selected(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showinfo("Edit", "No entry selected to edit.", parent=self)
            return

        selected_item_iid = selected_items[0] # Treeview's internal IID (row index as string)
        try:
            item_index = int(selected_item_iid)
            original_entry = self.entries[item_index]
        except (ValueError, IndexError):
            messagebox.showerror("Error", "Could not find the selected entry for editing.", parent=self)
            return

        result = self._get_input_values("Edit String Table Entry",
                                        current_id=str(original_entry.id_val),
                                        current_name=original_entry.name_val or "",
                                        current_value=original_entry.value_str)
        if result:
            new_id, new_name, new_value = result
            # Check for duplicate IDs if ID was changed
            if str(new_id) != str(original_entry.id_val) or (new_name and original_entry.name_val and new_name != original_entry.name_val):
                for i, entry in enumerate(self.entries):
                    if i == item_index: continue # Skip self
                    if str(entry.id_val) == str(new_id) or (entry.name_val and entry.name_val == str(new_id)):
                        messagebox.showerror("Error", f"An entry with ID '{new_id}' already exists.", parent=self)
                        return

            self.entries[item_index] = StringTableEntry(id_val=new_id, value_str=new_value, name_val=new_name)
            self.populate_table()
            if self.app_callbacks.get('set_dirty_callback'):
                self.app_callbacks['set_dirty_callback'](True)

    def on_delete_selected(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showinfo("Delete", "No entry selected to delete.", parent=self)
            return

        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete the selected entr(y/ies)?", parent=self):
            # Iterate in reverse to avoid index issues when removing multiple items
            indices_to_delete = sorted([int(iid) for iid in selected_items], reverse=True)
            for item_index in indices_to_delete:
                try:
                    del self.entries[item_index]
                except IndexError:
                    pass # Item already deleted or index out of bounds

            self.populate_table()
            if self.app_callbacks.get('set_dirty_callback'):
                self.app_callbacks['set_dirty_callback'](True)

    def apply_changes_to_resource(self):
        # Update the actual StringTableResource object
        self.resource.entries = list(self.entries) # Assign the modified list
        self.resource.dirty = True # Mark the specific resource as dirty

        if self.app_callbacks.get('set_dirty_callback'):
            self.app_callbacks['set_dirty_callback'](True) # Mark the whole application as dirty

        messagebox.showinfo("Changes Applied", "Changes have been applied to the in-memory resource representation. Save the main file to persist them.", parent=self)


if __name__ == '__main__':
    # Test the StringTableEditorFrame
    class DummyApp(customtkinter.CTk):
        def __init__(self):
            super().__init__()
            self.title("StringTable Editor Test")
            self.geometry("700x500")

            # Create a dummy StringTableResource
            from ..core.resource_base import ResourceIdentifier, RT_STRING
            ident = ResourceIdentifier(type_id=RT_STRING, name_id=1, language_id=1033)
            initial_entries = [
                StringTableEntry(id_val="IDS_HELLO", value_str="Hello World", name_val="IDS_HELLO"),
                StringTableEntry(id_val=101, value_str="Another String", name_val=""),
                StringTableEntry(id_val="IDS_TEST_QUOTES", value_str='Test "quotes" here', name_val="IDS_TEST_QUOTES")
            ]
            self.str_res = StringTableResource(identifier=ident, entries=initial_entries)

            def set_dirty_test(is_dirty):
                print(f"App dirty state set to: {is_dirty}")
                self.title(f"StringTable Editor Test {'*' if is_dirty else ''}")

            editor = StringTableEditorFrame(self, self.str_res, app_callbacks={'set_dirty_callback': set_dirty_test})
            editor.pack(expand=True, fill="both")

            self.protocol("WM_DELETE_WINDOW", self.quit_app)

        def quit_app(self):
            print("Final resource entries on quit:")
            for entry in self.str_res.entries:
                print(entry)
            self.destroy()
            self.quit()

    customtkinter.set_appearance_mode("System")
    customtkinter.set_default_color_theme("blue")
    app = DummyApp()
    app.mainloop()

