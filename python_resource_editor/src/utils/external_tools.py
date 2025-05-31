# src/utils/external_tools.py
import subprocess
import os
import sys # For sys.frozen and sys._MEIPASS
import shutil # For shutil.which
from typing import List, Optional

class MCPPError(Exception):
    """Custom exception for mcpp execution errors."""
    pass

def get_tool_path(tool_filename: str) -> str:
    """
    Determines the path to an external tool (mcpp.exe, windres.exe).
    Checks PyInstaller bundle, then development paths, then system PATH.
    Returns the resolved path or the original tool_filename if not found (caller must check existence).
    """
    # Check if running in a PyInstaller bundle
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        bundle_dir = sys._MEIPASS

        # Path 1: Tool directly in MEIPASS (e.g., datas=[('path/to/tool.exe', '.')])
        tool_path_root = os.path.join(bundle_dir, tool_filename)
        if os.path.exists(tool_path_root):
            return tool_path_root

        # Path 2: Tool in 'data/bin' subdir of MEIPASS (e.g., datas=[('path/to/tool.exe', 'data/bin')])
        # This matches the build.spec structure.
        tool_path_databin = os.path.join(bundle_dir, "data", "bin", tool_filename)
        if os.path.exists(tool_path_databin):
            return tool_path_databin

        # Path 3: Tool in 'bin' subdir of MEIPASS (e.g., datas=[('path/to/tool.exe', 'bin')])
        tool_path_bin = os.path.join(bundle_dir, "bin", tool_filename)
        if os.path.exists(tool_path_bin):
            return tool_path_bin

    # Development mode paths
    try:
        this_file_dir = os.path.dirname(os.path.abspath(__file__)) # Absolute path to this file's directory
        # project_root is expected to be two levels up from src/utils (python_resource_editor directory)
        project_root_from_utils = os.path.abspath(os.path.join(this_file_dir, "..", ".."))

        # Path A: project_root/data/bin/tool_filename (primary dev structure)
        dev_path_a = os.path.join(project_root_from_utils, "data", "bin", tool_filename)
        if os.path.exists(dev_path_a):
            return dev_path_a

        # Path B: If CWD is the project_root (e.g., running `python -m src` from `python_resource_editor`)
        # This is common for development.
        cwd_dev_path = os.path.join(os.getcwd(), "data", "bin", tool_filename)
        if os.path.exists(cwd_dev_path) and os.path.samefile(os.getcwd(), project_root_from_utils): # Ensure CWD is actually project root
            return cwd_dev_path

    except Exception:
        # __file__ might not be defined in some contexts, or path ops might fail
        pass

    # Fallback to system PATH
    tool_on_path = shutil.which(tool_filename)
    if tool_on_path:
        return tool_on_path

    # If not found anywhere, return the original filename.
    # The App class (caller) will check os.path.exists and show a fatal error.
    return tool_filename


def run_mcpp(
    rc_filepath: str,
    mcpp_path: str, # Expected to be a resolved path
    include_paths: Optional[List[str]] = None,
    extra_args: Optional[List[str]] = None
) -> str:
    """
    Runs the mcpp.exe preprocessor on an RC file.
    Args:
        rc_filepath: Path to the .rc file.
        mcpp_path: Resolved path to mcpp.exe.
        include_paths: List of include directories for mcpp.
        extra_args: List of additional arguments for mcpp.exe.
    Returns:
        The preprocessed RC content as a string.
    Raises:
        MCPPError: If mcpp.exe execution fails or returns an error.
        FileNotFoundError: If rc_filepath does not exist.
    """
    if not os.path.exists(rc_filepath):
        raise FileNotFoundError(f"RC file not found: {rc_filepath}")

    # mcpp_path is now expected to be resolved by the caller (App class using get_tool_path)
    # A basic check here can still be useful, but App should ensure it's valid.
    if not os.path.exists(mcpp_path) or not os.access(mcpp_path, os.X_OK):
         raise MCPPError(f"mcpp.exe not found or not executable at the provided path: '{mcpp_path}'. Ensure it's resolved correctly before calling.")

    command = [mcpp_path]

    # Common arguments for RC preprocessing.
    # -P: Inhibit line # directives in output.
    # -C: Keep comments. (Not used by default as it complicates parsing)
    # -DRC_INVOKED: Define RC_INVOKED, common for resource compilation.
    # -D_WIN32: Common define.
    # -e <encoding>: Specify default encoding of input files. (mcpp might guess, or use system default)
    #                This should match the encoding of the RC file.
    #                For now, we assume mcpp handles encoding or it's ANSI/UTF-8 by default.
    # Add -P to suppress #line directives, which simplifies parsing.
    command.extend(["-P", "-DRC_INVOKED", "-D_WIN32"]) # -C can be added if comments are desired

    if extra_args:
        command.extend(extra_args)

    if include_paths:
        for path in include_paths:
            if os.path.isdir(path): # Ensure include path exists before passing to mcpp
                command.extend(["-I", path])
            else:
                print(f"Warning: Include path '{path}' does not exist. Skipping.")

    command.append(rc_filepath)

    try:
        # We expect mcpp to output to stdout.
        # The encoding of mcpp's output is assumed to be 'utf-8' or compatible.
        # If RC files are often in other encodings (like utf-16), mcpp needs to handle that
        # or its output needs to be decoded correctly. mcpp's -e option might be relevant.
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,  # Decodes stdout/stderr using system default encoding (locale.getpreferredencoding())
            check=False # Don't raise CalledProcessError automatically
        )

        if process.returncode != 0:
            error_message = f"mcpp.exe failed with return code {process.returncode}.\n" \
                            f"Command: {' '.join(command)}\n" \
                            f"Stderr: {process.stderr.strip()}"
            raise MCPPError(error_message)

        # It's possible mcpp outputs errors to stderr even on success (e.g., warnings)
        if process.stderr:
            # Suppress common "Note: No relevant classes found." from mcpp if only output
            if not ("Note: No relevant classes found." in process.stderr and process.returncode == 0):
                 print(f"mcpp.exe warnings/errors:\n{process.stderr.strip()}")

        return process.stdout

    except FileNotFoundError:
        raise MCPPError(f"mcpp.exe command '{' '.join(command)}' failed. Ensure mcpp_path ('{mcpp_path}') is correct and executable.")
    except Exception as e:
        raise MCPPError(f"An error occurred while running mcpp.exe: {e}\nCommand: {' '.join(command)}")


class WindresError(Exception):
    """Custom exception for windres execution errors."""
    pass

def run_windres_compile(
    rc_filepath: str,
    res_filepath: str,
    windres_path: str,
    include_paths: Optional[List[str]] = None,
    resource_h_path: Optional[str] = None, # Currently unused, but could be for future define generation
    language: Optional[int] = None # Optional language for windres --language
) -> bool:
    """
    Compiles an RC file to a RES file using windres.exe.

    Args:
        rc_filepath: Path to the input .rc file.
        res_filepath: Path for the output .res file.
        windres_path: Path to windres.exe.
        include_paths: List of include directories for windres.
        resource_h_path: Path to a resource.h file (its directory will be added to includes).
        language: Optional language ID (decimal) for windres --language option.

    Returns:
        True on success, False on failure.

    Raises:
        WindresError: If windres.exe is not found or returns an error.
        FileNotFoundError: If rc_filepath does not exist.
    """
    if not os.path.exists(rc_filepath):
        raise FileNotFoundError(f"Input RC file not found: {rc_filepath}")

    # windres_path is now expected to be resolved by the caller (App class using get_tool_path)
    if not os.path.exists(windres_path) or not os.access(windres_path, os.X_OK):
        raise WindresError(f"windres.exe not found or not executable at the provided path: '{windres_path}'. Ensure it's resolved correctly.")

    command = [
        windres_path,
        "-i", rc_filepath,
        "-o", res_filepath,
        # "--input-format=rc", # Usually default
        # "--output-format=res", # Usually default
    ]

    if language is not None:
        command.extend(["--language", str(language)]) # Set default language for resources

    effective_include_paths = list(include_paths) if include_paths else []
    if resource_h_path and os.path.exists(resource_h_path):
        resource_h_dir = os.path.dirname(resource_h_path)
        if resource_h_dir not in effective_include_paths:
            effective_include_paths.append(resource_h_dir)

    for path in effective_include_paths:
        if os.path.isdir(path):
            command.extend(["-I", path])
        else:
            print(f"Warning (windres): Include path '{path}' does not exist. Skipping.")

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False
        )

        if process.returncode != 0:
            error_message = f"windres.exe failed with return code {process.returncode}.\n" \
                            f"Command: {' '.join(command)}\n" \
                            f"Stderr: {process.stderr.strip()}\n" \
                            f"Stdout: {process.stdout.strip()}"
            raise WindresError(error_message)

        if process.stderr: # windres might output warnings to stderr
            print(f"windres.exe warnings/info:\n{process.stderr.strip()}")

        return True

    except FileNotFoundError:
        raise WindresError(f"windres.exe command '{' '.join(command)}' failed. Ensure windres_path ('{windres_path}') is correct and executable.")
    except Exception as e:
        raise WindresError(f"An error occurred while running windres.exe: {e}\nCommand: {' '.join(command)}")


def main_test():
    # Test mcpp
    dummy_rc_mcpp_content = "#define TEST_ID 101\nTEST_ID ICON \"test.ico\""
    dummy_rc_mcpp_filepath = "dummy_mcpp_test.rc"
    with open(dummy_rc_mcpp_filepath, "w") as f: f.write(dummy_rc_mcpp_content)

    mcpp_exe_path = "mcpp" # Assume in PATH or configure
    try:
        print("Testing mcpp...")
        preprocessed = run_mcpp(dummy_rc_mcpp_filepath, mcpp_exe_path)
        print(f"mcpp output:\n{preprocessed}")
    except MCPPError as e:
        print(f"mcpp test error: {e}")
    finally:
        if os.path.exists(dummy_rc_mcpp_filepath): os.remove(dummy_rc_mcpp_filepath)

    # Test windres
    dummy_rc_windres_content = "101 ICON \"dummy.ico\"\nSTRINGTABLE\nBEGIN\n  1000, \"Hello\"\nEND"
    dummy_rc_windres_filepath = "dummy_windres_test.rc"
    dummy_ico_filepath = "dummy.ico" # windres needs the file to exist
    dummy_res_filepath = "dummy_test.res"

    with open(dummy_rc_windres_filepath, "w") as f: f.write(dummy_rc_windres_content)
    with open(dummy_ico_filepath, "wb") as f: f.write(b"dummy_icon_data") # Create dummy icon file

    windres_exe_path = "windres" # Assume in PATH or configure
    try:
        print("\nTesting windres...")
        success = run_windres_compile(dummy_rc_windres_filepath, dummy_res_filepath, windres_exe_path, include_paths=[os.getcwd()])
        if success and os.path.exists(dummy_res_filepath):
            print(f"windres compilation successful. Output: {dummy_res_filepath} (size: {os.path.getsize(dummy_res_filepath)} bytes)")
        else:
            print("windres compilation failed or output file not created.")
    except WindresError as e:
        print(f"windres test error: {e}")
    finally:
        for fpath in [dummy_rc_windres_filepath, dummy_ico_filepath, dummy_res_filepath]:
            if os.path.exists(fpath): os.remove(fpath)

if __name__ == "__main__":
    # Example Usage (for testing this module directly)
    # main_test() # Uncomment to run tests if mcpp/windres are configured
    print("external_tools.py - run main_test() for self-tests (requires mcpp/windres).")
    # Create a dummy RC file for testing
    dummy_rc_content = """
#define MY_ICON_ID 101
#define MY_STRING_ID 201
#include <windows.h> // This would be found if include paths are set

// This is a comment
MY_ICON_ID ICON "myicon.ico"

STRINGTABLE
BEGIN
    MY_STRING_ID, "Hello World"
END
"""
    dummy_rc_filepath = "dummy_test.rc"
    with open(dummy_rc_filepath, "w", encoding="utf-8") as f:
        f.write(dummy_rc_content)

    # Path to mcpp.exe - this needs to be adjusted for your environment
    # Option 1: Assume it's in PATH or provide full path
    mcpp_executable_path = "mcpp.exe" # Or "path/to/your/mcpp.exe"

    # Option 2: Try to locate it based on a common project structure assumption
    # This assumes this script is in python_resource_editor/src/utils
    # And mcpp is in python_resource_editor/../data/bin/mcpp.exe (i.e. a parallel 'data' dir to the project root)
    # Or in data/bin relative to where this script is run from.

    # For this test, let's assume a relative path from the project root `python_resource_editor`
    # If running `python src/utils/external_tools.py` from `python_resource_editor` directory:
    test_mcpp_path = os.path.join("..", "data", "bin", "mcpp.exe") # Relative from python_resource_editor/src
    if not os.path.exists(test_mcpp_path):
        test_mcpp_path = os.path.join("data", "bin", "mcpp.exe") # Relative from python_resource_editor/
        if not os.path.exists(test_mcpp_path):
             test_mcpp_path = "mcpp" # try to find in path

    print(f"Attempting to use mcpp at: {os.path.abspath(test_mcpp_path)}")

    # Dummy include path (e.g., where windows.h might be if not system-wide for mcpp)
    # For this test, it's not strictly necessary unless your mcpp needs it for <windows.h>
    dummy_include_paths = [] # e.g., ["C:/path/to/windows_sdk_includes"]

    try:
        print(f"\nPreprocessing '{dummy_rc_filepath}'...")
        preprocessed_content = run_mcpp(dummy_rc_filepath, test_mcpp_path, dummy_include_paths)
        print("\n--- Preprocessed Output ---")
        print(preprocessed_content)
        print("--- End of Output ---")
    except MCPPError as e:
        print(f"\nMCPP Error: {e}")
    except FileNotFoundError as e:
        print(f"\nFile Error: {e}")
    finally:
        if os.path.exists(dummy_rc_filepath):
            os.remove(dummy_rc_filepath)

```
