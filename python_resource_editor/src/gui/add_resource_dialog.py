import customtkinter
from tkinter import filedialog as tkfiledialog
from tkinter import messagebox as tkmessagebox

class AddResourceDialog(customtkinter.CTkToplevel):
    def __init__(self, master, available_types: list[str]):
        super().__init__(master)

        self.title("Add New Resource")
        self.geometry("450x300") # Adjusted size
        self.result = None
        self._available_types = available_types

        self.grid_columnconfigure(1, weight=1) # Allow entry fields to expand

        # Resource Type
        type_label = customtkinter.CTkLabel(self, text="Resource Type:")
        type_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.type_combobox = customtkinter.CTkComboBox(self, values=self._available_types, width=250)
        if self._available_types:
            self.type_combobox.set(self._available_types[0]) # Default to first type
        self.type_combobox.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        # Name/ID
        name_label = customtkinter.CTkLabel(self, text="Name/ID:")
        name_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.name_entry = customtkinter.CTkEntry(self, width=250)
        self.name_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        # Language ID
        lang_label = customtkinter.CTkLabel(self, text="Language ID:")
        lang_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.lang_entry = customtkinter.CTkEntry(self, width=250)
        self.lang_entry.insert(0, "1033")  # Default to English (US)
        self.lang_entry.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

        # File (Optional)
        file_label = customtkinter.CTkLabel(self, text="File (optional):")
        file_label.grid(row=3, column=0, padx=10, pady=5, sticky="w")

        self.file_entry_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.file_entry_frame.grid_columnconfigure(0, weight=1)
        self.file_entry_frame.grid(row=3, column=1, padx=10, pady=5, sticky="ew")

        self.file_entry = customtkinter.CTkEntry(self.file_entry_frame, width=180) # Adjusted width
        self.file_entry.grid(row=0, column=0, padx=(0,5), pady=0, sticky="ew")

        browse_button = customtkinter.CTkButton(self.file_entry_frame, text="Browse...", width=60, command=self.browse_file)
        browse_button.grid(row=0, column=1, pady=0, sticky="e")


        # Buttons Frame
        button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=4, column=0, columnspan=2, pady=20, sticky="s")
        button_frame.grid_columnconfigure((0,1), weight=1) # Center buttons

        ok_button = customtkinter.CTkButton(button_frame, text="OK", command=self.ok_pressed, width=100)
        ok_button.grid(row=0, column=0, padx=10)

        cancel_button = customtkinter.CTkButton(button_frame, text="Cancel", command=self.destroy, width=100)
        cancel_button.grid(row=0, column=1, padx=10)

        self.rowconfigure(4, weight=1) # Push buttons to bottom

        # Make modal
        self.transient(master) # Keep on top of master
        self.grab_set() # Block input to master window
        self.wait_window() # Wait until this window is destroyed

    def browse_file(self):
        filepath = tkfiledialog.askopenfilename(
            title="Select Resource File",
            filetypes=(("All files", "*.*"),) # Allow any file type
        )
        if filepath:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, filepath)

    def ok_pressed(self):
        res_type_str = self.type_combobox.get()
        res_name_or_id_str = self.name_entry.get().strip()
        res_lang_str = self.lang_entry.get().strip()
        res_filepath = self.file_entry.get().strip()

        if not res_type_str:
            tkmessagebox.showerror("Validation Error", "Resource Type must be selected.", parent=self)
            return
        if not res_name_or_id_str:
            tkmessagebox.showerror("Validation Error", "Name/ID must be provided.", parent=self)
            return
        if not res_lang_str:
            tkmessagebox.showerror("Validation Error", "Language ID must be provided.", parent=self)
            return

        try:
            # Try to convert lang_id to int.
            # Name/ID can be string or int, will be handled by caller.
            _ = int(res_lang_str)
        except ValueError:
            tkmessagebox.showerror("Validation Error", "Language ID must be a numeric value.", parent=self)
            return

        # Further validation (e.g. if filepath is required for certain types) can be added here or in the caller.

        self.result = (res_type_str, res_name_or_id_str, res_lang_str, res_filepath if res_filepath else None)
        self.destroy()

if __name__ == '__main__':
    # Test the dialog
    class DummyApp(customtkinter.CTk):
        def __init__(self):
            super().__init__()
            self.title("Dialog Test")
            self.geometry("300x200")
            button = customtkinter.CTkButton(self, text="Open Add Dialog", command=self.open_dialog)
            button.pack(pady=20)
            self.protocol("WM_DELETE_WINDOW", self.quit_app) # Handle main window close

        def open_dialog(self):
            # Example types
            types = ["RT_ICON", "RT_BITMAP", "STRINGTABLE", "RT_DIALOG", "RT_RCDATA", "CUSTOMTYPE"]
            dialog = AddResourceDialog(self, available_types=types)
            if dialog.result:
                print("Dialog Result:", dialog.result)
            else:
                print("Dialog Cancelled")

        def quit_app(self):
            self.destroy() # Destroy main window
            self.quit() # Terminate Tkinter mainloop if not already done

    customtkinter.set_appearance_mode("System")
    customtkinter.set_default_color_theme("blue")
    app = DummyApp()
    app.mainloop()

```
