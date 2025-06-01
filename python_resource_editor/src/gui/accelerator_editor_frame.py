import customtkinter
import tkinter.ttk as ttk
from tkinter import simpledialog, messagebox
from typing import List, Dict, Callable, Optional, Union
import copy

from ..core.accelerator_parser_util import AcceleratorEntry
from ..core.resource_types import AcceleratorResource # For type hinting

class AcceleratorEditorFrame(customtkinter.CTkFrame):
    def __init__(self, master, accelerator_resource: AcceleratorResource, app_callbacks: Dict[str, Callable]):
        super().__init__(master)
        self.resource = accelerator_resource
        self.app_callbacks = app_callbacks

        self.entries_copy: List[AcceleratorEntry] = copy.deepcopy(accelerator_resource.entries)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1) # Treeview/table
        self.grid_rowconfigure(1, weight=0) # Buttons frame

        # --- Treeview (Table) for Accelerator Entries ---
        self.tree = ttk.Treeview(self, columns=("Key", "CommandID", "Type", "Modifiers"), show="headings")
        self.tree.heading("Key", text="Key/Event")
        self.tree.heading("CommandID", text="Command ID/Name")
        self.tree.heading("Type", text="Type (ASCII/VIRTKEY)")
        self.tree.heading("Modifiers", text="Modifiers (Ctrl, Alt, Shift)")

        self.tree.column("Key", width=120, anchor="w")
        self.tree.column("CommandID", width=150, anchor="w")
        self.tree.column("Type", width=100, anchor="w")
        self.tree.column("Modifiers", width=150, anchor="w")

        self.tree.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.tree.bind("<Double-1>", lambda event: self.on_edit_selected())

        # Scrollbar for Treeview
        tree_scrollbar_y = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        tree_scrollbar_y.grid(row=0, column=1, sticky="ns", pady=5) # Place scrollbar next to tree
        self.tree.configure(yscrollcommand=tree_scrollbar_y.set)

        # --- Buttons Frame ---
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
        for i in self.tree.get_children(): self.tree.delete(i)
        for idx, entry in enumerate(self.entries_copy):
            key_event = entry.key_event_str
            cmd_id_display = entry.get_command_id_display()

            type_val = ""
            if "ASCII" in entry.type_flags_str: type_val = "ASCII"
            elif "VIRTKEY" in entry.type_flags_str: type_val = "VIRTKEY"

            modifiers = [f for f in entry.type_flags_str if f not in ["ASCII", "VIRTKEY"]]
            mods_display = ", ".join(modifiers)

            self.tree.insert("", "end", iid=str(idx), values=(key_event, cmd_id_display, type_val, mods_display))

    def _open_edit_dialog(self, entry: Optional[AcceleratorEntry] = None) -> Optional[AcceleratorEntry]:
        dialog = AcceleratorEntryDialog(self, entry_to_edit=entry)
        # This dialog needs to be modal and return the new/edited AcceleratorEntry or None
        # The dialog itself (AcceleratorEntryDialog) is not defined in this subtask,
        # so this part is conceptual for now.
        # For simplicity in this step, we'll use simpledialog for each field.

        title = "Edit Accelerator Entry" if entry else "Add Accelerator Entry"

        key_event = simpledialog.askstring(title, "Key/Event (e.g., VK_F1, ^C, \"A\"): ", parent=self,
                                           initialvalue=entry.key_event_str if entry else "")
        if key_event is None: return None

        cmd_id_str = simpledialog.askstring(title, "Command ID (numeric or symbolic): ", parent=self,
                                            initialvalue=entry.get_command_id_display() if entry else "")
        if cmd_id_str is None: return None

        cmd_id_val: Union[int, str]
        cmd_id_sym: Optional[str] = None
        if cmd_id_str.isdigit() or cmd_id_str.startswith("0x"):
            try: cmd_id_val = int(cmd_id_str, 0)
            except ValueError: cmd_id_val = cmd_id_str; cmd_id_sym = cmd_id_str # Fallback
        else:
            cmd_id_val = cmd_id_str; cmd_id_sym = cmd_id_str

        # Type: ASCII or VIRTKEY
        type_str = simpledialog.askstring(title, "Type (ASCII or VIRTKEY): ", parent=self,
                                          initialvalue="VIRTKEY" if entry and "VIRTKEY" in entry.type_flags_str else "ASCII")
        if type_str is None: return None
        type_str = type_str.upper().strip()
        if type_str not in ["ASCII", "VIRTKEY"]:
             messagebox.showerror("Error", "Type must be ASCII or VIRTKEY.", parent=self); return None

        flags = [type_str]
        if simpledialog.askyesno(title, "CONTROL modifier?", parent=self, initialvalue='yes' if entry and "CONTROL" in entry.type_flags_str else 'no'):
            flags.append("CONTROL")
        if simpledialog.askyesno(title, "ALT modifier?", parent=self, initialvalue='yes' if entry and "ALT" in entry.type_flags_str else 'no'):
            flags.append("ALT")
        if simpledialog.askyesno(title, "SHIFT modifier?", parent=self, initialvalue='yes' if entry and "SHIFT" in entry.type_flags_str else 'no'):
            flags.append("SHIFT")
        # NOINVERT is another possible flag, less common.

        return AcceleratorEntry(key_event_str, cmd_id_val, cmd_id_sym, flags)


    def on_add_entry(self):
        new_entry_data = self._open_edit_dialog(None)
        if new_entry_data:
            self.entries_copy.append(new_entry_data)
            self.populate_table()
            if self.app_callbacks.get('set_dirty_callback'):
                self.app_callbacks['set_dirty_callback'](True)

    def on_edit_selected(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showinfo("Edit", "No entry selected.", parent=self)
            return

        item_idx = int(selected_items[0]) # Assuming IID is index string
        original_entry = self.entries_copy[item_idx]

        updated_entry_data = self._open_edit_dialog(original_entry)
        if updated_entry_data:
            self.entries_copy[item_idx] = updated_entry_data
            self.populate_table()
            if self.app_callbacks.get('set_dirty_callback'):
                self.app_callbacks['set_dirty_callback'](True)

    def on_delete_selected(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showinfo("Delete", "No entry selected.", parent=self)
            return

        if messagebox.askyesno("Confirm Delete", "Delete selected accelerator entr(y/ies)?", parent=self):
            indices_to_delete = sorted([int(iid) for iid in selected_items], reverse=True)
            for idx in indices_to_delete:
                del self.entries_copy[idx]
            self.populate_table()
            if self.app_callbacks.get('set_dirty_callback'):
                self.app_callbacks['set_dirty_callback'](True)

    def apply_changes_to_resource(self):
        self.resource.entries = copy.deepcopy(self.entries_copy)
        self.resource.dirty = True
        if self.app_callbacks.get('set_dirty_callback'):
            self.app_callbacks['set_dirty_callback'](True)
        messagebox.showinfo("Changes Applied", "Accelerator changes applied to in-memory resource. Save file to persist.", parent=self)


# Minimal dialog for editing an accelerator entry (conceptual placeholder for _open_edit_dialog)
# A more complete implementation would use CTkToplevel with proper layout.
class AcceleratorEntryDialog(customtkinter.CTkToplevel): # Not used by above due to complexity
    def __init__(self, master, entry_to_edit: Optional[AcceleratorEntry] = None):
        super().__init__(master)
        self.title("Edit Accelerator Entry" if entry_to_edit else "Add Accelerator Entry")
        self.geometry("400x300")
        self.result: Optional[AcceleratorEntry] = None
        # ... UI elements for key, command_id, type, flags ...
        # ... OK and Cancel buttons ...
        self.grab_set()
        self.wait_window()


if __name__ == '__main__':
    # Test AcceleratorEditorFrame
    class DummyApp(customtkinter.CTk):
        def __init__(self):
            super().__init__()
            self.title("Accelerator Editor Test")
            self.geometry("700x500")

            from ..core.resource_base import ResourceIdentifier, RT_ACCELERATOR
            ident = ResourceIdentifier(type_id=RT_ACCELERATOR, name_id="IDA_ACCEL1", language_id=1033)
            initial_entries = [
                AcceleratorEntry("VK_F1", 101, "ID_HELP", ["VIRTKEY", "CONTROL"]),
                AcceleratorEntry("\"A\"", 102, "ID_A_KEY", ["ASCII", "SHIFT"]),
            ]
            self.accel_res = AcceleratorResource(identifier=ident, entries=initial_entries, table_name_rc="IDA_ACCEL1")

            def set_dirty_test(is_dirty):
                print(f"App dirty state set to: {is_dirty}")
                self.title(f"Accelerator Editor Test {'*' if is_dirty else ''}")

            editor = AcceleratorEditorFrame(self, self.accel_res, app_callbacks={'set_dirty_callback': set_dirty_test})
            editor.pack(expand=True, fill="both")

            self.protocol("WM_DELETE_WINDOW", self.quit_app)

        def quit_app(self):
            print("\nFinal AcceleratorResource entries on quit:")
            for entry in self.accel_res.entries: print(entry)
            self.destroy(); self.quit()

    customtkinter.set_appearance_mode("System")
    customtkinter.set_default_color_theme("blue")
    app = DummyApp()
    app.mainloop()


