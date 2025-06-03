# src/core/pe_parser.py

from typing import List
import pefile # External library for PE parsing

from .resource_base import Resource, ResourceIdentifier
# Import specific resource types if we were to do detailed parsing here.
# For now, we'll use RCDataResource as a generic container for raw data.
from .resource_types import RCDataResource, get_resource_class

# Utility to make a LANGID from primary and sub-language IDs
def MAKELANGID(primary_lang, sub_lang):
    return (sub_lang << 10) | primary_lang

def extract_resources_from_pe(pe_filepath: str) -> List[Resource]:
    """
    Extracts resources from a PE (Portable Executable) file using the pefile library.

    Args:
        pe_filepath: Path to the PE file (e.g., .exe, .dll).

    Returns:
        A list of Resource objects (mostly as RCDataResource instances containing raw data)
        extracted from the PE file. Returns an empty list if errors occur or no resources are found.
    """
    resources: List[Resource] = []

    try:
        pe = pefile.PE(pe_filepath)
    except pefile.PEFormatError as e:
        print(f"Error parsing PE file '{pe_filepath}': {e}")
        return resources
    except FileNotFoundError:
        print(f"Error: File not found '{pe_filepath}'")
        return resources
    except Exception as e: # Catch other potential errors from pefile loading
        print(f"An unexpected error occurred while loading PE file '{pe_filepath}': {e}")
        return resources

    if not hasattr(pe, 'DIRECTORY_ENTRY_RESOURCE'):
        print(f"No resource directory found in '{pe_filepath}'.")
        pe.close()
        return resources

    try:
        for rt_entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
            res_type_id = rt_entry.id
            # pefile gives type as a string if it's a standard known type, else None.
            # rt_entry.name can be the string representation of the type if not an ID.
            # We primarily use res_type_id (integer).

            if rt_entry.directory is None: continue

            for name_entry in rt_entry.directory.entries:
                if name_entry.name is not None: # Resource name is a string
                    res_name_id = str(name_entry.name)
                else: # Resource name is an ID
                    res_name_id = int(name_entry.id)

                if name_entry.directory is None: continue

                for lang_entry in name_entry.directory.entries:
                    if lang_entry.data is None: continue # Should not happen if directory entry exists

                    # Construct full LANGID from pefile's separate lang and sublang
                    # These are often available directly in lang_entry.id as well
                    full_lang_id = MAKELANGID(lang_entry.data.lang, lang_entry.data.sublang)
                    # Or, lang_entry.id usually holds the full LANGID already.
                    # Using lang_entry.id is simpler if available and correct.
                    # Let's prefer lang_entry.id if it seems valid.
                    if hasattr(lang_entry, 'id') and lang_entry.id is not None:
                        res_lang_id = int(lang_entry.id)
                    else: # Fallback to constructing it
                        res_lang_id = full_lang_id


                    data_rva = lang_entry.data.struct.OffsetToData
                    size = lang_entry.data.struct.Size

                    try:
                        raw_data = pe.get_data(data_rva, size)
                    except pefile.PEFormatError as e:
                        print(f"Error getting data for resource Type:{res_type_id} Name:{res_name_id} Lang:{res_lang_id}: {e}")
                        continue # Skip this resource entry

                    identifier = ResourceIdentifier(type_id=res_type_id, name_id=res_name_id, language_id=res_lang_id)

                    # For now, instantiate as RCDataResource (generic raw data)
                    # In the future, we can use get_resource_class(res_type_id)
                    # and then call a more specific parse_from_data if implemented for that type.
                    # Example:
                    #   resource_class = get_resource_class(res_type_id)
                    #   if resource_class.parse_from_data.__func__ is not Resource.parse_from_data.__func__:
                    #      instance = resource_class.parse_from_data(raw_data, identifier)
                    #   else:
                    #      instance = resource_class(identifier, raw_data) # Constructor if no specific parser
                    # For this subtask, always use RCDataResource or the base Resource.

                    # Using RCDataResource to hold the raw data.
                    resource_instance = RCDataResource(identifier, raw_data)
                    resources.append(resource_instance)

    except Exception as e: # Catch errors during resource iteration
        print(f"An error occurred while processing resources in '{pe_filepath}': {e}")
    finally:
        pe.close()

    return resources

if __name__ == '__main__':
    # This part is for basic testing if the module is run directly.
    # The main CLI testing will be in src/__main__.py as per the subtask.
    print("pe_parser.py executed directly for testing purposes.")

    # Example: Create a dummy PE file path for a non-existent file to test error handling
    # test_file = "non_existent_dummy.exe"
    # print(f"\nTesting with non-existent file: {test_file}")
    # extracted = extract_resources_from_pe(test_file)
    # print(f"Number of resources extracted: {len(extracted)}")

    # To test with a real PE file, you would replace "path/to/your/sample.exe"
    # with an actual file path.
    # Make sure you have a sample PE file (e.g., notepad.exe from C:\Windows\System32)
    # available in a path accessible by this script for a real test.
    # For example:
    # sample_pe_path = "C:\\Windows\\System32\\notepad.exe" # Adjust path as needed
    # print(f"\nTesting with sample PE file: {sample_pe_path}")
    # if os.path.exists(sample_pe_path):
    #     extracted_real = extract_resources_from_pe(sample_pe_path)
    #     print(f"Number of resources extracted from {sample_pe_path}: {len(extracted_real)}")
    #     for i, res in enumerate(extracted_real[:5]): # Print details of first 5 resources
    #         type_val = pefile.RESOURCE_TYPE.get(res.identifier.type_id, res.identifier.type_id)
    #         name_val = res.identifier.name_id
    #         if isinstance(name_val, int): name_val = str(name_val) # Ensure it's printable
    #         print(f"  Res {i+1}: Type={type_val}, Name/ID={name_val}, Lang={res.identifier.language_id}, Size={len(res.data)}")
    # else:
    #     print(f"Sample PE file {sample_pe_path} not found. Skipping real PE test.")
    print("To test, run through src.__main__.py with a PE file path argument.")


