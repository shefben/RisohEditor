# src/core/resource_base.py

class ResourceIdentifier:
    """
    Handles resource type, name (numeric or string), and language.
    """
    def __init__(self, type_id, name_id, language_id):
        self.type_id = type_id
        self.name_id = name_id
        self.language_id = language_id

    def __repr__(self):
        return f"ResourceIdentifier(type={self.type_id}, name={self.name_id}, lang={self.language_id})"

class Resource:
    """
    Base class for resources with common attributes.
    """
    def __init__(self, identifier: ResourceIdentifier, data: bytes = b''):
        self.identifier = identifier
        self.data = data # Raw binary data
        self.dirty: bool = False # Has this specific resource been modified?

    @property
    def type_id(self):
        return self.identifier.type_id

    @property
    def name_id(self):
        return self.identifier.name_id

    @property
    def language_id(self):
        return self.identifier.language_id

    def __repr__(self):
        return f"Resource(identifier={self.identifier}, data_len={len(self.data)})"

    @classmethod
    def parse_from_data(cls, raw_data: bytes, identifier: ResourceIdentifier):
        """
        Placeholder for parsing logic from .res or PE data.
        This should be overridden by subclasses for specific resource types.
        """
        return cls(identifier, raw_data)

    def to_rc_text(self) -> str:
        """
        Generates RC script content for this resource.
        Base implementation returns a comment indicating it cannot be represented or raises error.
        Subclasses should override this.
        """
        type_str = self.identifier.type_id
        if isinstance(type_str, int): # Could map to RT_ constant string if available
            pass # type_str = RT_MAP.get(type_str, str(type_str))
        name_str = self.identifier.name_id
        if isinstance(name_str, int):
            name_str = str(name_str)
        else:
            name_str = f'"{name_str}"'

        # Default comment for resources that don't have a specific RC text representation
        return f"# Resource Type '{type_str}' Name {name_str} Lang {self.identifier.language_id} - Cannot be directly represented in RC text."
        # Alternatively, could raise NotImplementedError to force subclasses to implement
        # raise NotImplementedError(f"{self.__class__.__name__} (Type: {type_str}, Name: {name_str}) does not support RC text generation.")


    def to_binary_data(self) -> bytes:
        """
        Placeholder for generating binary resource data.
        This should be overridden by subclasses.
        """
        # Default implementation might just return self.data if it's already binary
        # or if no specific transformation is needed by the subclass.
        if self.data is None:
            # This case might indicate an issue if data was expected to be populated.
            # For some types, text_content or other fields might be the source of truth.
            print(f"Warning: Resource {self.identifier} has None for self.data in base to_binary_data().")
            return b'' # Return empty bytes if data is None
        return self.data

# Common Resource Type Constants
# These values are typically found in WinUser.h or similar Windows SDK headers.
RT_CURSOR = 1
RT_BITMAP = 2
RT_ICON = 3
RT_MENU = 4
RT_DIALOG = 5
RT_STRING = 6
RT_FONTDIR = 7
RT_FONT = 8
RT_ACCELERATOR = 9
RT_RCDATA = 10
RT_MESSAGETABLE = 11
RT_GROUP_CURSOR = 12 # RT_CURSOR + 11
RT_GROUP_ICON = 14   # RT_ICON + 11
RT_VERSION = 16
RT_DLGINCLUDE = 17
RT_PLUGPLAY = 19
RT_VXD = 20
RT_ANICURSOR = 21
RT_ANIICON = 22
RT_HTML = 23
RT_MANIFEST = 24
# Windows User Experience Guidelines section 2.1.3.3
# https://learn.microsoft.com/en-us/windows/win32/menurc/resource-types
RT_DLGINIT = 240
RT_TOOLBAR = 241

# Language ID constants (simplified, full list is extensive)
# MAKELANGID(LANG_NEUTRAL, SUBLANG_NEUTRAL) -> 0x00
# MAKELANGID(LANG_ENGLISH, SUBLANG_ENGLISH_US) -> 0x0409
LANG_NEUTRAL = 0x00
LANG_ENGLISH_US = 0x0409
LANG_JAPANESE = 0x0411
# Add more as needed

# Predefined resource names (some common ones)
VS_VERSION_INFO = 1


class FileResource(Resource): # To hold references to external files like .ico, .bmp
    def __init__(self, identifier: ResourceIdentifier, filepath: str, original_rc_statement: str):
        super().__init__(identifier, data=None)
        self.filepath = filepath
        self.original_rc_statement = original_rc_statement
        # self.dirty is inherited from Resource, initially False

    def __repr__(self):
        return f"<FileResource {self.identifier} linked to '{self.filepath}'>"

    def to_rc_text(self) -> str:
        # Returns the original statement that defined this file resource
        return self.original_rc_statement

    def load_data(self, base_dir: str = "") -> bytes:
        """Loads the data from the filepath associated with this resource."""
        import os # Moved import here as it's only used by this method and to_binary_data
        try:
            # Ensure filepath is absolute or relative to a known base_dir
            effective_path = self.filepath
            if base_dir and not os.path.isabs(effective_path):
                effective_path = os.path.join(base_dir, self.filepath)

            if not os.path.exists(effective_path):
                 raise FileNotFoundError(f"File not found: {effective_path}")

            with open(effective_path, "rb") as f:
                self.data = f.read()
            return self.data
        except Exception as e:
            # print(f"Error loading data for {self.filepath}: {e}") # Or log this
            self.data = None # Set to None on error to distinguish from successfully loaded empty file
            raise # Re-raise the exception so caller knows loading failed

    def to_binary_data(self) -> bytes | None:
        import os # For os.path.exists and os.path.isabs
        if self.data is not None: # Data might have been pre-loaded or set directly
            return self.data

        if self.filepath:
            # This assumes filepath is either absolute or resolvable from CWD if no other context.
            # In a real scenario, base_dir might need to be passed or determined.
            effective_path = self.filepath
            if not os.path.isabs(effective_path):
                print(f"Warning: FileResource {self.identifier} attempting to load relative path '{self.filepath}' from current working directory.")

            if os.path.exists(effective_path):
                try:
                    with open(effective_path, 'rb') as f:
                        # It might be good practice to set self.data here as well,
                        # but to_binary_data ideally shouldn't have side effects.
                        # However, for PE update, we need the bytes anyway.
                        return f.read()
                except Exception as e:
                    print(f"Error reading FileResource {self.identifier} from {effective_path} in to_binary_data: {e}")
                    return None
            else:
                print(f"Warning: File not found for FileResource {self.identifier} in to_binary_data: {effective_path}")
                return None

        print(f"Warning: FileResource {self.identifier} has no data and no valid filepath.")
        return None


class TextBlockResource(Resource): # For blocks of RC text like DIALOG, MENU, or HTML/Manifest
    def __init__(self, identifier: ResourceIdentifier, text_content: str, resource_type_name: str):
        super().__init__(identifier, data=None) # Data will be encoded on demand or if set from binary
        self.text_content: str = text_content
        self.resource_type_name: str = resource_type_name # e.g. "DIALOGEX", "MENU", "RT_MANIFEST"
        # self.dirty is inherited from Resource, initially False

    def __repr__(self):
        return f"<TextBlockResource {self.identifier} type '{self.resource_type_name}' len {len(self.text_content)}>"

    def to_rc_text(self) -> str:
        # This should ideally reconstruct the full RC block.
        # For now, it might just return the captured text content if it includes the header and BEGIN/END.
        # A more robust version would re-format based on internal structures if they get parsed later.
        return self.text_content

    def to_binary_data(self) -> bytes | None:
        if self.text_content is not None:
            try:
                # Determine type for encoding. self.identifier.type_id could be int or str.
                type_id_val = self.identifier.type_id
                type_name_val = self.resource_type_name.upper() if self.resource_type_name else ""

                # Check against known integer types or string type names
                if type_id_val == RT_MANIFEST or type_name_val == "MANIFEST" or \
                   type_id_val == RT_HTML or type_name_val == "HTML" or \
                   type_name_val == "XML": # Common text-based types often UTF-8
                    return self.text_content.encode('utf-8')

                # For other types that are text blocks (e.g., custom RCDATA defined as text,
                # or if a DIALOG/MENU was stored as TextBlockResource and needs to be passed as binary)
                # UTF-16LE is a common Windows default for "textual" resource data if not specified.
                # However, specific resource types (Dialog, Menu etc.) should have their own
                # to_binary_data methods that generate their specific binary format from structured data,
                # not from a generic text_content block. This method is a fallback for generic text blocks.
                # If this TextBlockResource holds, for example, a DIALOG definition as text,
                # it should ideally be converted to a DialogResource first, then DialogResource.to_binary_data() called.
                # For now, as a fallback for generic text blocks:
                print(f"Warning: TextBlockResource {self.identifier} (type: {type_name_val}) is being encoded to UTF-16LE as a default binary representation.")
                return self.text_content.encode('utf-16-le')
            except Exception as e:
                print(f"Error encoding TextBlockResource {self.identifier} to binary: {e}")
                return None

        # If text_content is None, but self.data might have been set (e.g. if parsed from binary originally)
        return super().to_binary_data()
