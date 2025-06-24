import argparse
import json
import os
import struct

nvs_types = {
    0x01: "U8", 0x11: "I8", 0x02: "U16", 0x12: "I16",
    0x04: "U32", 0x14: "I32", 0x08: "U64", 0x18: "I64",
    0x21: "STR", 0x41: "BLOB", 0x42: "BLOB_DATA", 0x48: "BLOB_IDX",
    0xFF: "ANY"
}

nvs_sector_states = {
    0xFFFFFFFF: "EMPTY",
    0xFFFFFFFE: "ACTIVE",
    0xFFFFFFFC: "FULL",
    0xFFFFFFF8: "FREEING",
    0xFFFFFFF0: "CORRUPT"
}

entry_state_descs = {
    3: "Empty",
    2: "Written",
    0: "Erased"
}

def parse_nvs_entries(entries, entry_state_bitmap, namespaces, page_num):
    result = []
    i = 0
    while i < 126:
        try:
            state = int(entry_state_bitmap[i])
            if state != 2:  # Only process Written entries
                i += 1
                continue

            entry = entries[i]
            entry_ns = entry[0]
            entry_type = entry[1]
            entry_span = entry[2]
            chunk_index = entry[3]
            key = entry[8:24].rstrip(b'\x00')
            data = entry[24:]

            if entry_type not in nvs_types:
                i += 1
                continue
            if entry_span < 1 or entry_span > 126 - i:
                i += 1
                continue

            entry_data = {
                "key": key.decode('ascii', errors='ignore'),
                "type": nvs_types[entry_type],
                "namespace": namespaces.get(entry_ns, f"NS_{entry_ns}"),
                "span": entry_span,
                "chunk_index": chunk_index
            }

            if nvs_types[entry_type] == "U8":
                value = struct.unpack("<B", data[0:1])[0]
                entry_data["value"] = value
                if entry_ns == 0:
                    namespaces[value] = entry_data["key"]
            elif nvs_types[entry_type] == "I8":
                entry_data["value"] = struct.unpack("<b", data[0:1])[0]
            elif nvs_types[entry_type] == "U16":
                entry_data["value"] = struct.unpack("<H", data[0:2])[0]
            elif nvs_types[entry_type] == "I16":
                entry_data["value"] = struct.unpack("<h", data[0:2])[0]
            elif nvs_types[entry_type] == "U32":
                entry_data["value"] = struct.unpack("<I", data[0:4])[0]
            elif nvs_types[entry_type] == "I32":
                entry_data["value"] = struct.unpack("<i", data[0:4])[0]
            elif nvs_types[entry_type] == "U64":
                entry_data["value"] = struct.unpack("<Q", data[0:8])[0]
            elif nvs_types[entry_type] == "I64":
                entry_data["value"] = struct.unpack("<q", data[0:8])[0]
            elif nvs_types[entry_type] in ["STR", "BLOB", "BLOB_DATA"]:
                size = struct.unpack("<H", data[0:2])[0]
                if size < 0 or size > 4032:  # Max size within 4KB page minus header
                    i += entry_span
                    continue
                data_chunks = [data[8:]]
                for x in range(1, entry_span):
                    if i + x >= 126:
                        break
                    data_chunks.append(entries[i + x])
                combined_data = b''.join(data_chunks)[:size]
                entry_data["value"] = (combined_data.decode('ascii', errors='ignore') if nvs_types[entry_type] == "STR"
                                      else combined_data.hex())
                entry_data["size"] = size
            elif nvs_types[entry_type] == "BLOB_IDX":
                size = struct.unpack("<I", data[0:4])[0]
                chunk_count = struct.unpack("<B", data[5:6])[0]
                chunk_start = struct.unpack("<B", data[6:7])[0]
                entry_data["value"] = {"size": size, "chunk_count": chunk_count, "chunk_start": chunk_start}
            elif nvs_types[entry_type] == "ANY":
                i += 1
                continue

            result.append(entry_data)
            i += entry_span
        except Exception as e:
            i += 1  # Skip to avoid infinite loop

    return result

def read_nvs_pages(fh):
    namespaces = {0: "System"}
    result = []
    fh.seek(0, os.SEEK_END)
    file_len = fh.tell()
    sector_pos = 0
    page_num = 0

    while sector_pos < file_len:
        try:
            fh.seek(sector_pos)
            page_state_raw = struct.unpack("<I", fh.read(4))[0]
            page_state = nvs_sector_states.get(page_state_raw, f"Unknown (0x{page_state_raw:08x})")
            seq_no = struct.unpack("<I", fh.read(4))[0]
            version = (fh.read(1)[0] ^ 0xff) + 1

            fh.read(19)  # unused
            crc_32 = struct.unpack("<I", fh.read(4))[0]

            if page_state not in ["ACTIVE", "FULL"]:
                sector_pos += 4096
                page_num += 1
                continue

            entry_state_bitmap = fh.read(32)
            entry_state_bitmap_decoded = ''
            for entry_num in range(126):
                bitnum = entry_num * 2
                byte_index = bitnum // 8
                temp = entry_state_bitmap[byte_index]
                temp = (temp >> (6 - (bitnum % 8))) & 3
                entry_state_bitmap_decoded += str(temp)

            entries = []
            for i in range(126):
                entry_data = fh.read(32)
                if len(entry_data) != 32:
                    break
                entries.append(entry_data)

            result.extend(parse_nvs_entries(entries, entry_state_bitmap_decoded, namespaces, page_num))
            sector_pos += 4096
            page_num += 1
        except Exception as e:
            sector_pos += 4096
            page_num += 1

    return result, namespaces

def main():
    parser = argparse.ArgumentParser(description="Read ESP32 NVS partition and output to JSON")
    parser.add_argument("nvs_bin_file", help="NVS partition binary file")
    parser.add_argument("output_json", help="Output JSON file")
    args = parser.parse_args()

    try:
        with open(args.nvs_bin_file, 'rb') as fh:
            data, namespaces = read_nvs_pages(fh)
            output = {
                "namespaces": namespaces,
                "entries": data
            }
            with open(args.output_json, 'w') as f:
                json.dump(output, f, indent=2)
        print(f"Successfully wrote NVS data to {args.output_json}")
    except FileNotFoundError as e:
        print(f"Error: File not found: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
