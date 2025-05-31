# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['src/__main__.py'], # Main script
    pathex=['.'], # Include current directory (where spec file is, e.g., python_resource_editor)
    binaries=[],
    datas=[
        # Assuming mcpp.exe, windres.exe and their required DLLs
        # are in a 'data/bin' subdirectory relative to this spec file.
        # The second part of the tuple is the destination directory within the bundle.
        ('data/bin/mcpp.exe', 'data/bin'),
        ('data/bin/windres.exe', 'data/bin'),
        # Add required DLLs for windres if they are not found automatically
        # (e.g., libgcc_s_dw2-1.dll, libintl-8.dll, libiconv-2.dll for some MinGW versions)
        # Check windres dependencies if the bundled app fails.
        # Example: ('data/bin/libgcc_s_dw2-1.dll', 'data/bin'),
        #          ('data/bin/libwinpthread-1.dll', 'data/bin')
        # If pillow is used for icons/images and not picked up automatically:
        # from PyInstaller.utils.hooks import copy_metadata
        # datas += copy_metadata('Pillow')
    ],
    hiddenimports=[
        'customtkinter',
        'PIL', # Pillow, if used
        'pefile'
        # Add other hidden imports if PyInstaller misses them
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0, # 0, 1, or 2. 0 is no optimization.
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PythonResourceEditor', # Name of the executable
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True, # Compresses the executable further, requires UPX installed
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # False for GUI application, True for console application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None, # None for auto-detect, or 'x86_64', 'x86'
    codesign_identity=None,
    entitlements_file=None,
    icon=None, # Path to an .ico file for the application icon
    version=None, # Path to a version file (text file with version info)
)

# For macOS, to create an app bundle:
# app = BUNDLE(exe,
#              name='PythonResourceEditor.app',
#              icon='path/to/icon.icns', # macOS icon
#              bundle_identifier=None)

# For one-file bundle, use:
# coll = COLLECT(exe,
#                a.binaries,
#                a.zipfiles,
#                a.datas,
#                strip=False,
#                upx=True,
#                name='PythonResourceEditor')
# Note: One-file bundles might be slower to start.
# For one-folder (default), the above EXE definition is usually sufficient.
# The output will be in dist/PythonResourceEditor folder.
