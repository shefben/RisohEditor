# src/__main__.py

import customtkinter
from .gui.main_window import App # Import the App class from the gui module
import os # For path operations

def main():
    # Set appearance mode and color theme for customtkinter
    customtkinter.set_appearance_mode("System")
    customtkinter.set_default_color_theme("blue")

    app = App()

    # --- Configure paths for external tools (mcpp, windres) ---
    script_dir = os.path.dirname(__file__) # .../src/
    project_root_guess = os.path.abspath(os.path.join(script_dir, "..")) # .../python_resource_editor/

    # Path if data/ is sibling to src/ under project_root (e.g., python_resource_editor/data/bin/TOOL)
    common_path_style1 = os.path.join(project_root_guess, "data", "bin")
    # Path if data/ is one level above project_root (e.g., some_dev_root/data/bin/TOOL)
    common_path_style2 = os.path.abspath(os.path.join(project_root_guess, "..", "data", "bin"))

    # Configure mcpp_path
    mcpp_exe_name = "mcpp.exe"
    mcpp_path_options = [
        os.path.join(common_path_style1, mcpp_exe_name),
        os.path.join(common_path_style2, mcpp_exe_name),
        mcpp_exe_name # Fallback to PATH
    ]

    found_mcpp = False
    for path_option in mcpp_path_options:
        if os.path.exists(path_option) or \
           (not os.path.dirname(path_option) and any(os.access(os.path.join(p, path_option), os.X_OK) for p in os.environ["PATH"].split(os.pathsep))):
            app.mcpp_path = path_option
            print(f"INFO: Using mcpp from: {os.path.abspath(app.mcpp_path) if os.path.dirname(app.mcpp_path) else app.mcpp_path}")
            found_mcpp = True
            break
    if not found_mcpp:
        print(f"WARNING: mcpp.exe not found in common relative project paths or system PATH. RC file parsing might fail.")

    # Configure windres_path
    windres_exe_name = "windres.exe"
    windres_path_options = [
        os.path.join(common_path_style1, windres_exe_name),
        os.path.join(common_path_style2, windres_exe_name),
        windres_exe_name # Fallback to PATH
    ]

    found_windres = False
    for path_option in windres_path_options:
        if os.path.exists(path_option) or \
           (not os.path.dirname(path_option) and any(os.access(os.path.join(p, path_option), os.X_OK) for p in os.environ["PATH"].split(os.pathsep))):
            app.windres_path = path_option
            print(f"INFO: Using windres from: {os.path.abspath(app.windres_path) if os.path.dirname(app.windres_path) else app.windres_path}")
            found_windres = True
            break
    if not found_windres:
         print(f"WARNING: windres.exe not found in common relative project paths or system PATH. Compiling to .res might fail.")

    # Start the customtkinter event loop
    app.mainloop()

if __name__ == "__main__":
    main()
```
