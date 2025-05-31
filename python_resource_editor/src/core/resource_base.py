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
        import os
        try:
            # Ensure filepath is absolute or relative to a known base_dir
            effective_path = self.filepath
            if base_dir and not os.path.isabs(effective_path):
                effective_path = os.path.join(base_dir, self.filepath)

            with open(effective_path, "rb") as f:
                self.data = f.read()
            return self.data
        except Exception as e:
            # print(f"Error loading data for {self.filepath}: {e}") # Or log this
            self.data = b"" # Ensure data is bytes
            raise # Re-raise the exception so caller knows loading failed


class TextBlockResource(Resource): # For blocks of RC text like DIALOG, MENU
    def __init__(self, identifier: ResourceIdentifier, text_content: str, resource_type_name: str):
        super().__init__(identifier, data=text_content.encode('utf-8'))
        self.text_content = text_content
        self.resource_type_name = resource_type_name
        # self.dirty is inherited from Resource, initially False

    def __repr__(self):
        return f"<TextBlockResource {self.identifier} type '{self.resource_type_name}' len {len(self.text_content)}>"

    def to_rc_text(self) -> str:
        # This should ideally reconstruct the full RC block.
        # For now, it might just return the captured text content if it includes the header and BEGIN/END.
        # A more robust version would re-format based on internal structures if they get parsed later.
        return self.text_content
