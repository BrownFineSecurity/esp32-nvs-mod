import json
import os
import uuid
import argparse

def load_json_data(json_file_path):
    """Load and return JSON data from the specified file."""
    with open(json_file_path, 'r') as f:
        return json.load(f)

def map_type_encoding(json_type):
    """Map JSON data types to NVS utility encodings."""
    type_mapping = {
        'U8': 'u8',
        'I8': 'i8',
        'U16': 'u16',
        'I16': 'i16',
        'U32': 'u32',
        'I32': 'i32',
        'U64': 'u64',
        'I64': 'i64',
        'BLOB_DATA': 'binary',
        'BLOB_IDX': None  # BLOB_IDX entries are skipped
    }
    return type_mapping.get(json_type)

def write_blob_file(blob_values, output_dir):
    """Write concatenated BLOB data to a file and return the file path."""
    blob_filename = f"blob_{uuid.uuid4().hex}.bin"
    blob_path = os.path.join(output_dir, blob_filename)
    with open(blob_path, 'wb') as f:
        for blob_value in blob_values:
            f.write(bytes.fromhex(blob_value))
    return blob_path

def generate_csv(json_data, csv_output_path, blobs_output_dir):
    """Generate CSV file and BLOB files from JSON data."""
    os.makedirs(blobs_output_dir, exist_ok=True)
    csv_lines = ["key,type,encoding,value"]

    # Group entries by namespace
    namespace_map = json_data['namespaces']
    entries = json_data['entries']
    entries_by_namespace = {}
    for entry in entries:
        ns_name = entry['namespace']
        if ns_name not in entries_by_namespace:
            entries_by_namespace[ns_name] = []
        entries_by_namespace[ns_name].append(entry)

    # Write CSV entries, ensuring namespace entries come first
    for ns_id, ns_name in sorted(namespace_map.items(), key=lambda x: int(x[0])):
        # Add namespace entry
        csv_lines.append(f"{ns_name},namespace,,")
        
        # Group BLOB_DATA entries by key for this namespace
        blob_data_by_key = {}
        non_blob_entries = []
        for entry in entries_by_namespace.get(ns_name, []):
            key = entry['key']
            entry_type = entry['type']
            
            if entry_type == 'BLOB_DATA':
                if key not in blob_data_by_key:
                    blob_data_by_key[key] = []
                blob_data_by_key[key].append((entry['chunk_index'], entry['value']))
            elif entry_type != 'BLOB_IDX':  # Skip BLOB_IDX entries
                non_blob_entries.append(entry)

        # Process BLOB_DATA entries
        for key, blob_entries in blob_data_by_key.items():
            # Sort by chunk_index to ensure correct order
            blob_entries.sort(key=lambda x: x[0])
            # Extract values
            blob_values = [value for _, value in blob_entries]
            # Write concatenated BLOB data to file
            blob_path = write_blob_file(blob_values, blobs_output_dir)
            csv_lines.append(f"{key},file,binary,{blob_path}")

        # Process non-BLOB entries
        for entry in non_blob_entries:
            key = entry['key']
            entry_type = entry['type']
            encoding = map_type_encoding(entry_type)
            value = entry['value']
            
            # Handle non-BLOB data
            if isinstance(value, dict):
                value_str = json.dumps(value)
            else:
                value_str = str(value)
            csv_lines.append(f"{key},data,{encoding},{value_str}")

    # Write CSV file
    with open(csv_output_path, 'w', newline='') as f:
        f.write('\n'.join(csv_lines))

def main():
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description='Convert JSON data to CSV and BLOB files.')
    parser.add_argument('json_file', help='Path to the input JSON file')
    parser.add_argument('csv_output', help='Path to the output CSV file')
    args = parser.parse_args()

    # File paths
    json_file_path = args.json_file
    csv_output_path = args.csv_output
    blobs_output_dir = 'blobs'

    # Load JSON data
    json_data = load_json_data(json_file_path)

    # Generate CSV and BLOB files
    generate_csv(json_data, csv_output_path, blobs_output_dir)
    print(f"Generated CSV file at: {csv_output_path}")
    print(f"BLOB files stored in: {blobs_output_dir}")

if __name__ == '__main__':
    main()
