import customtkinter
from tkinter import filedialog as tkfiledialog
from tkinter import messagebox as tkmessagebox
import os

class ImportResourceDialog(customtkinter.CTkToplevel):
    def __init__(self, master, available_types: list[str], initial_filepath: str = ""):
        super().__init__(master)

        self.title("Import Resource from File")
        self.geometry("500x300") # Adjusted size
        self.result = None
        self._available_types = available_types

        self.grid_columnconfigure(1, weight=1)

        # File Path (Mandatory)
        file_label = customtkinter.CTkLabel(self, text="Resource File:")
        file_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.file_entry_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.file_entry_frame.grid_columnconfigure(0, weight=1)
        self.file_entry_frame.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        self.filepath_entry = customtkinter.CTkEntry(self.file_entry_frame, width=250)
        self.filepath_entry.grid(row=0, column=0, padx=(0,5), pady=0, sticky="ew")
        if initial_filepath:
            self.filepath_entry.insert(0, initial_filepath)

        browse_button = customtkinter.CTkButton(self.file_entry_frame, text="Browse...", width=70, command=self.browse_file)
        browse_button.grid(row=0, column=1, pady=0, sticky="e")

        # Resource Type
        type_label = customtkinter.CTkLabel(self, text="Resource Type:")
        type_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.type_combobox = customtkinter.CTkComboBox(self, values=self._available_types, width=250)
        self.type_combobox.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        if initial_filepath: # Auto-suggest after browse or if initial path provided
            self._suggest_type_from_filepath(initial_filepath)


        # Name/ID
        name_label = customtkinter.CTkLabel(self, text="Name/ID:")
        name_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.name_entry = customtkinter.CTkEntry(self, width=250)
        self.name_entry.grid(row=2, column=1, padx=10, pady=5, sticky="ew")
        if initial_filepath: # Auto-suggest name from filename without extension
            base_name = os.path.splitext(os.path.basename(initial_filepath))[0]
            self.name_entry.insert(0, base_name.upper().replace(" ", "_"))


        # Language ID
        lang_label = customtkinter.CTkLabel(self, text="Language ID:")
        lang_label.grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.lang_entry = customtkinter.CTkEntry(self, width=250)
        self.lang_entry.insert(0, "1033")  # Default to English (US)
        self.lang_entry.grid(row=3, column=1, padx=10, pady=5, sticky="ew")

        # Buttons Frame
        button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=4, column=0, columnspan=2, pady=20, sticky="s")
        button_frame.grid_columnconfigure((0,1), weight=1)

        ok_button = customtkinter.CTkButton(button_frame, text="Import", command=self.ok_pressed, width=100)
        ok_button.grid(row=0, column=0, padx=10)

        cancel_button = customtkinter.CTkButton(button_frame, text="Cancel", command=self.destroy, width=100)
        cancel_button.grid(row=0, column=1, padx=10)

        self.rowconfigure(4, weight=1)

        self.transient(master)
        self.grab_set()
        self.wait_window()

    def _suggest_type_from_filepath(self, filepath: str):
        if not filepath: return
        _, ext = os.path.splitext(filepath)
        ext = ext.lower()

        suggestion = None
        if ext == ".ico": suggestion = "RT_ICON" # Or RT_GROUP_ICON if that's preferred for .ico files
        elif ext == ".bmp": suggestion = "RT_BITMAP"
        elif ext == ".cur": suggestion = "RT_CURSOR"
        elif ext in [".txt", ".md"]: suggestion = "RCDATA" # Or a custom "TEXTFILE" type if added
        elif ext in [".html", ".htm"]: suggestion = "RT_HTML"
        elif ext == ".xml": suggestion = "RT_MANIFEST" # Or generic RCDATA
        elif ext in [".bin", ".dat", ".dll", ".exe"]: suggestion = "RCDATA" # Generic binary

        if suggestion and suggestion in self._available_types:
            self.type_combobox.set(suggestion)
        elif self._available_types:
            self.type_combobox.set(self._available_types[0]) # Default if no good suggestion

    def browse_file(self):
        filepath = tkfiledialog.askopenfilename(
            title="Select File to Import",
            filetypes=(("All files", "*.*"),)
        )
        if filepath:
            self.filepath_entry.delete(0, "end")
            self.filepath_entry.insert(0, filepath)
            self._suggest_type_from_filepath(filepath)
            # Auto-fill Name/ID based on filename
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            self.name_entry.delete(0, "end")
            self.name_entry.insert(0, base_name.upper().replace(" ", "_").replace("-","_"))


    def ok_pressed(self):
        filepath = self.filepath_entry.get().strip()
        res_type_str = self.type_combobox.get()
        res_name_or_id_str = self.name_entry.get().strip()
        res_lang_str = self.lang_entry.get().strip()

        if not filepath:
            tkmessagebox.showerror("Validation Error", "Resource File path must be provided.", parent=self)
            return
        if not os.path.exists(filepath):
            tkmessagebox.showerror("Validation Error", f"File not found: {filepath}", parent=self)
            return
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
            _ = int(res_lang_str)
        except ValueError:
            tkmessagebox.showerror("Validation Error", "Language ID must be a numeric value.", parent=self)
            return

        self.result = (filepath, res_type_str, res_name_or_id_str, res_lang_str)
        self.destroy()

if __name__ == '__main__':
    class DummyApp(customtkinter.CTk):
        def __init__(self):
            super().__init__()
            self.title("Import Dialog Test")
            self.geometry("300x200")
            button = customtkinter.CTkButton(self, text="Open Import Dialog", command=self.open_dialog)
            button.pack(pady=20)

        def open_dialog(self):
            types = ["RT_ICON", "RT_BITMAP", "RT_CURSOR", "RT_HTML", "RT_MANIFEST", "RCDATA", "TEXTFILE"]
            dialog = ImportResourceDialog(self, available_types=types)
            if dialog.result:
                print("Dialog Result:", dialog.result)
            else:
                print("Dialog Cancelled")

    customtkinter.set_appearance_mode("System")
    customtkinter.set_default_color_theme("blue")
    app = DummyApp()
    app.mainloop()


